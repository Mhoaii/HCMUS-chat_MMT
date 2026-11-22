"""Lời mời và chat của UI; tái sử dụng TCP newline của bản console."""

import json
import queue
import socket
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from models.peer import LocalProfile, Peer
from network.tcp.tcp_chat import connect_peer, receive_messages, send_message
from network.tcp.tcp_service import TCPChatService

PROTOCOL = "lan-chat-ui/1"
MAX_TEXT_BYTES = 16_000


@dataclass(eq=False)
class _ChatConnection:
    """Socket, trạng thái và hàng gửi của một kết nối; chỉ dùng nội bộ."""

    username: str = ""
    display_name: str = ""
    ip: str = ""
    tcp_port: int = 0
    request_id: str = ""
    initiator: str = ""
    state: str = "connecting"
    connection: socket.socket | None = None
    deadline: float = 0
    outbox: queue.Queue = field(default_factory=queue.Queue)
    closed: threading.Event = field(default_factory=threading.Event)


class ChatSessionService:
    """Quản lý lời mời, reader/writer và socket; emit không được gọi widget."""

    def __init__(
        self,
        profile: LocalProfile,
        listener: TCPChatService,
        emit: Callable[[str, str, dict], None],
        *,
        invite_timeout: float = 30,
        handshake_timeout: float = 5,
    ) -> None:
        """Nhận listener đã mở và callback sự kiện; timeout tính bằng giây."""
        self.profile = profile
        self.listener = listener
        self.emit = emit
        self.invite_timeout = invite_timeout
        self.handshake_timeout = handshake_timeout
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._links: dict[str, _ChatConnection] = {}
        self._sockets: set[socket.socket] = set()
        self._workers: set[threading.Thread] = set()
        self._started = False

    def start(self) -> None:
        """Khởi chạy accept nền một lần trên listener đã có."""
        with self._lock:
            if self._started or self._stop.is_set():
                raise RuntimeError("Dịch vụ chat đã chạy hoặc đã dừng.")
            self._started = True
            self._spawn(self._accept_loop)

    def _spawn(self, target: Callable, *args) -> None:
        """Theo dõi worker để thu hồi khi đóng ứng dụng."""
        def run() -> None:
            """Chạy công việc và gỡ worker khỏi danh sách khi kết thúc."""
            try:
                target(*args)
            finally:
                with self._lock:
                    self._workers.discard(threading.current_thread())

        with self._lock:
            if self._stop.is_set():
                return
            worker = threading.Thread(target=run, name="LAN-Chat", daemon=True)
            self._workers.add(worker)
            worker.start()

    def _emit_state(self, link: _ChatConnection, reason: str = "") -> None:
        """Phát trạng thái theo đúng thứ tự dưới khóa; không thao tác Tk."""
        if not self._stop.is_set():
            self.emit("chat_state", link.username, {
                "state": link.state, "reason": reason,
                "display_name": link.display_name, "ip": link.ip,
                "tcp_port": link.tcp_port,
            })

    def invite(self, peer: Peer) -> None:
        """Mời peer bằng địa chỉ UDP; bỏ qua nếu đã có phiên đang hoạt động."""
        if peer.username == self.profile.username:
            raise ValueError("Không thể mời chính mình.")
        if not peer.ip or not 1 <= peer.tcp_port <= 65535:
            raise ValueError("Peer chưa có địa chỉ TCP hợp lệ.")
        with self._lock:
            if self._stop.is_set():
                raise RuntimeError("Dịch vụ chat đã dừng.")
            if peer.username in self._links:
                return
            link = _ChatConnection(
                username=peer.username, display_name=peer.display_name,
                ip=peer.ip, tcp_port=peer.tcp_port,
                request_id=uuid.uuid4().hex, initiator=self.profile.username,
            )
            self._links[peer.username] = link
            self._emit_state(link)
            self._spawn(self._connect, link)

    def _connect(self, link: _ChatConnection) -> None:
        """Kết nối ngoài UI rồi dùng chính worker này làm reader."""
        try:
            connection = connect_peer(link.ip, link.tcp_port)
        except (OSError, ValueError, OverflowError) as error:
            self._drop(link, f"Không thể kết nối: {error}", state="error")
            return
        with self._lock:
            if self._stop.is_set() or self._links.get(link.username) is not link:
                connection.close()
                return
            link.connection = connection
            self._sockets.add(connection)
            link.state = "waiting"
            link.deadline = time.monotonic() + self.invite_timeout
            link.outbox.put({
                "type": "request", "username": self.profile.username,
                "display_name": self.profile.display_name,
                "tcp_port": self.profile.tcp_port, "to": link.username,
            })
            self._emit_state(link)
            self._spawn(self._write_loop, link)
        self._read_loop(link)

    def _accept_loop(self) -> None:
        """Nhận socket liên tục và quét lời mời hết hạn, không chặn UI."""
        while not self._stop.is_set():
            try:
                connection, address = self.listener.accept(timeout=0.2)
            except socket.timeout:
                self._expire_invitations()
                continue
            except (OSError, RuntimeError) as error:
                with self._lock:
                    if not self._stop.is_set():
                        self.emit("network_error", "", {"reason": str(error)})
                return
            with self._lock:
                if self._stop.is_set():
                    connection.close()
                    return
                # Socket chưa tự giới thiệu chỉ được chờ trong thời gian ngắn.
                connection.settimeout(self.handshake_timeout)
                self._sockets.add(connection)
                self._spawn(self._read_loop, _ChatConnection(
                    connection=connection, ip=address[0],
                ))
            self._expire_invitations()

    def _read_loop(self, link: _ChatConnection) -> None:
        """Mỗi socket có đúng một reader; lỗi giao thức đóng riêng socket đó."""
        reason = "Cuộc trò chuyện đã ngắt kết nối."
        try:
            receive_messages(
                link.connection,
                lambda text: self._handle_packet(link, text),
                lambda: None,
            )
        except (ValueError, TypeError) as error:
            reason = f"Dữ liệu chat không hợp lệ: {error}"
        finally:
            self._drop(link, reason)

    def _handle_packet(self, link: _ChatConnection, text: str) -> None:
        """Đọc JSON phân loại; nội dung chat không được coi là lệnh điều khiển."""
        if len(text.encode("utf-8")) > 100_000:
            raise ValueError("Gói tin quá lớn.")
        packet = json.loads(text)
        if not isinstance(packet, dict) or packet.get("protocol") != PROTOCOL:
            raise ValueError("Khác giao thức chat UI.")
        if not link.username:
            self._register_request(link, packet)
            return
        with self._lock:
            if self._links.get(link.username) is not link or link.closed.is_set():
                return
            if packet.get("request_id") != link.request_id:
                raise ValueError("Sai mã cuộc trò chuyện.")
            kind = packet.get("type")
            if kind == "accept" and link.state == "waiting":
                if packet.get("username") != link.username:
                    raise ValueError("Sai người nhận lời mời.")
                link.state, link.deadline = "ready", 0
                self._emit_state(link)
            elif kind == "decline" and link.state == "waiting":
                self._drop(link, "Người nhận đã từ chối lời mời.", state="declined")
            elif kind == "message" and link.state in ("ready", "accepting"):
                message = packet.get("text")
                self._validate_text(message)
                self.emit("message", link.username, {"text": message})
            else:
                raise ValueError("Gói tin không phù hợp trạng thái hội thoại.")

    def _register_request(self, link: _ChatConnection, packet: dict) -> None:
        """Lấy danh tính từ lời mời; không suy đoán username bằng IP/cổng nguồn."""
        username, name = packet.get("username"), packet.get("display_name")
        port, request_id = packet.get("tcp_port"), packet.get("request_id")
        if (
            packet.get("type") != "request"
            or packet.get("to") != self.profile.username
            or not isinstance(username, str) or not username.strip()
            or len(username) > 128 or username == self.profile.username
            or not isinstance(name, str) or not name.strip() or len(name) > 256
            or type(port) is not int or not 1 <= port <= 65535
            or not isinstance(request_id, str) or len(request_id) != 32
        ):
            raise ValueError("Lời mời thiếu thông tin hoặc sai người nhận.")
        uuid.UUID(hex=request_id)
        with self._lock:
            if self._stop.is_set() or link.closed.is_set():
                return
            link.username, link.display_name = username, name
            link.tcp_port, link.request_id = port, request_id
            link.initiator = username
            previous = self._links.get(username)
            reciprocal = previous is not None and previous.state in (
                "connecting", "waiting",
            )
            if previous is not None:
                # Hai bên cùng mời: giữ socket do username nhỏ hơn khởi tạo.
                # Cả hai đã bày tỏ muốn chat nên tự xác nhận socket được giữ.
                if not reciprocal or previous.initiator < link.initiator:
                    self._drop(link, notify=False)
                    return
                self._drop(previous, notify=False)
            self._links[username] = link
            link.connection.settimeout(None)
            link.deadline = time.monotonic() + self.invite_timeout
            link.state = "accepting" if reciprocal else "incoming"
            self._spawn(self._write_loop, link)
            if reciprocal:
                link.outbox.put({"type": "accept", "username": self.profile.username})
            self._emit_state(link)

    def accept_chat(self, username: str) -> None:
        """Đồng ý lời mời; writer gửi phản hồi trước khi cho gửi tin."""
        with self._lock:
            link = self._links.get(username)
            if link is None or link.state != "incoming":
                return
            link.state = "accepting"
            self._emit_state(link)
            link.outbox.put({"type": "accept", "username": self.profile.username})

    def decline_chat(self, username: str) -> None:
        """Gửi từ chối qua writer rồi đóng kết nối chờ."""
        with self._lock:
            link = self._links.get(username)
            if link is None or link.state != "incoming":
                return
            link.state = "declining"
            self._emit_state(link)
            link.outbox.put({"type": "decline"})

    @staticmethod
    def _validate_text(text: str) -> None:
        """Giới hạn tin UTF-8; chuỗi chỉ có khoảng trắng không được gửi."""
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Tin nhắn không được để trống.")
        if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
            raise ValueError("Tin nhắn vượt giới hạn 16.000 byte UTF-8.")

    def send_text(self, username: str, text: str) -> None:
        """Đưa tin vào writer; báo RuntimeError nếu chưa được đồng ý chat."""
        self._validate_text(text)
        with self._lock:
            link = self._links.get(username)
            if link is None or link.state != "ready":
                raise RuntimeError("Cuộc trò chuyện chưa sẵn sàng.")
            link.outbox.put({"type": "message", "text": text})

    def _write_loop(self, link: _ChatConnection) -> None:
        """Một writer cho mỗi socket để phản hồi và tin nhắn không xen byte."""
        while not self._stop.is_set() and not link.closed.is_set():
            packet = link.outbox.get()
            if packet is None:
                return
            packet = dict(packet, protocol=PROTOCOL, request_id=link.request_id)
            try:
                send_message(link.connection, json.dumps(packet, ensure_ascii=False))
            except OSError as error:
                with self._lock:
                    if packet["type"] == "message" and not self._stop.is_set():
                        self.emit("send_failed", link.username, {
                            "text": packet["text"], "reason": str(error),
                        })
                self._drop(link, f"Không thể gửi dữ liệu: {error}")
                return
            with self._lock:
                # sendall có thể vừa xong thì reader nhận EOF. Vẫn ghi nhận
                # thao tác gửi đã hoàn tất, không làm mất tin khỏi lịch sử local.
                if packet["type"] == "message" and not self._stop.is_set():
                    self.emit("sent", link.username, {"text": packet["text"]})
                if self._links.get(link.username) is not link or link.closed.is_set():
                    return
                if packet["type"] == "accept":
                    link.state, link.deadline = "ready", 0
                    self._emit_state(link)
                elif packet["type"] == "decline":
                    self._drop(link, "Bạn đã từ chối lời mời.", state="declined")
                    return

    def _expire_invitations(self) -> None:
        """Thu hồi lời mời không được xử lý trong thời gian cho phép."""
        with self._lock:
            now = time.monotonic()
            for link in list(self._links.values()):
                if link.deadline and now >= link.deadline:
                    self._drop(link, "Lời mời đã hết thời gian chờ.", state="expired")

    def _drop(
        self, link: _ChatConnection, reason: str = "", *,
        state: str = "disconnected", notify: bool = True,
    ) -> None:
        """Đóng đúng socket sở hữu; reader cũ không được xóa phiên thay thế."""
        with self._lock:
            if link.closed.is_set():
                return
            link.closed.set()
            current = self._links.get(link.username) is link
            if current:
                del self._links[link.username]
                link.state = state
                if notify:
                    self._emit_state(link, reason)
            while True:
                try:
                    pending = link.outbox.get_nowait()
                except queue.Empty:
                    break
                if pending and pending["type"] == "message" and not self._stop.is_set():
                    self.emit("send_failed", link.username, {
                        "text": pending["text"], "reason": reason,
                    })
            link.outbox.put(None)
            if link.connection is not None:
                self._sockets.discard(link.connection)
                try:
                    link.connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                link.connection.close()

    def stop(self) -> None:
        """Dừng listener, đánh thức reader/writer và join worker có giới hạn."""
        with self._lock:
            self._stop.set()
            self.listener.stop()
            for link in list(self._links.values()):
                self._drop(link, notify=False)
            for connection in list(self._sockets):
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                connection.close()
            self._sockets.clear()
            workers = list(self._workers)
        deadline = time.monotonic() + 1
        for worker in workers:
            if worker is not threading.current_thread():
                worker.join(max(0, deadline - time.monotonic()))
