"""Lời mời và chat của UI; tái sử dụng TCP newline của bản console."""

import queue
import socket
import threading
import time
import uuid

from pathlib import Path

from network.tcp.file_transfer import build_file_offer, read_file_offer, receive_file_bytes, send_file_bytes
from collections.abc import Callable
from dataclasses import dataclass, field

from models.peer import LocalProfile, Peer
from network.tcp.framing import recv_frame, send_frame
from network.tcp.tcp_chat import connect_peer
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
    outgoing_files: dict[str, tuple[Path, dict]] = field(default_factory=dict)
    incoming_files: dict[str, dict] = field(default_factory=dict)
    accepted_files: dict[str, dict] = field(default_factory=dict)
    data_sockets: set[socket.socket] = field(default_factory=set)
    pending_ack_ids: set[str] = field(default_factory=set)
    closed: threading.Event = field(default_factory=threading.Event)
    duplicate: "_ChatConnection | None" = None


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
        downloads: Path = Path("downloads"),
    ) -> None:
        """Nhận listener đã mở và callback sự kiện; timeout tính bằng giây."""
        self.profile = profile
        self.downloads = downloads
        self.listener = listener
        self.emit = emit
        self.invite_timeout = invite_timeout
        self.handshake_timeout = handshake_timeout
        self._lock = threading.RLock()
        self._invites_changed = threading.Condition(self._lock)
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
        """Đọc từng frame trên socket của phiên và thu hồi phiên khi kết thúc."""
        reason = "Cuộc trò chuyện đã ngắt kết nối."
        try:
            while not self._stop.is_set() and not link.closed.is_set():
                packet = recv_frame(link.connection)
                if not link.username and packet.get("type") == "file.open":
                    self._receive_transfer(link, packet)
                    return
                self._handle_packet(link, packet)
        except EOFError:
            pass
        except OSError as error:
            reason = f"Lỗi kết nối TCP: {error}"
        except (ValueError, TypeError) as error:
            reason = f"Dữ liệu chat không hợp lệ: {error}"
        finally:
            self._drop(link, reason)

    def _handle_packet(self, link: _ChatConnection, packet: dict) -> None:
        """Kiểm tra giao thức và xử lý bản tin theo trạng thái của phiên."""
        if packet.get("protocol") != PROTOCOL:
            raise ValueError("Khác giao thức chat UI.")

         # 2. Nếu là kết nối mới chưa định danh -> Xử lý lời mời "request"
        if not link.username:
            self._register_request(link, packet)
            return
        with self._lock:
            if self._links.get(link.username) is not link or link.closed.is_set():
                return

            if packet.get("request_id") != link.request_id:
                raise ValueError("Sai mã cuộc trò chuyện.")

            kind = packet.get("type")

            if kind in ("message", "ack"):
                message_id = packet.get("message_id")
                if not isinstance(message_id, str) or len(message_id) != 32:
                    raise ValueError("Bản tin thiếu message_id hợp lệ.")
                if uuid.UUID(hex=message_id).hex != message_id:
                    raise ValueError("message_id sai định dạng.")

            if kind == "accept" and link.state == "waiting":
                if packet.get("username") != link.username:
                    raise ValueError("Sai người nhận lời mời.")
                self._close_duplicate(link)
                link.state, link.deadline = "ready", 0
                self._emit_state(link)

            elif kind == "decline" and link.state == "waiting":
                self._drop(link, "Người nhận đã từ chối lời mời.", state="declined")
            elif kind == "message" and link.state in ("ready", "accepting"):
                message = packet.get("text")
                self._validate_text(message)
                self.emit("message", link.username, {"text": message})

                # B đã tiếp nhận tin. Writer sẽ gửi ACK về A trên cùng socket.
                link.outbox.put({"type": "ack", "message_id": message_id})

            elif kind == "file.offer":
                if link.state not in ("ready", "accepting"):
                    raise ValueError("Phiên chưa được đồng ý chat.")
                offer = read_file_offer(packet)
                if offer["transfer_id"] in link.incoming_files or offer["transfer_id"] in link.accepted_files:
                    raise ValueError("Mã lời mời file bị trùng.")
                link.incoming_files[offer["transfer_id"]] = offer
                self.emit("file_offer", link.username, offer)

            elif kind == "file.reply" and link.state == "ready":
                transfer_id = packet.get("transfer_id")
                accepted = packet.get("accepted")
                if not isinstance(transfer_id, str) or type(accepted) is not bool:
                    raise ValueError("Phản hồi file không hợp lệ.")

                pending = link.outgoing_files.pop(transfer_id, None)
                if pending is None:
                    return
                path, offer = pending

                self.emit("file_reply", link.username, {
                    "transfer_id": transfer_id,
                    "name": path.name,
                    "accepted": accepted,
                })
                if accepted:
                    self._spawn(self._send_transfer, link, path, offer)

            elif kind == "ack" and link.state == "ready":
                if message_id not in link.pending_ack_ids:
                    return

                link.pending_ack_ids.remove(message_id)
                self.emit("ack_received", link.username, {"message_id": message_id})

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
                if not reciprocal or previous.duplicate is not None:
                    self._drop(link, notify=False)
                    return

                if previous.initiator < link.initiator:
                    # Giữ phiên đi của mình. Chờ bên kia xác nhận
                    # trước khi thu hồi socket của lời mời đi ngược lại.
                    previous.duplicate = link
                    link.connection.settimeout(None)
                    return

                # Phiên đến là phiên cả hai sẽ giữ.
                self._drop(previous, notify=False)

            self._links[username] = link
            link.connection.settimeout(None)
            link.deadline = time.monotonic() + self.invite_timeout
            link.state = "accepting" if reciprocal else "incoming"
            self._invites_changed.notify_all()
            self._spawn(self._write_loop, link)
            if reciprocal:
                link.outbox.put({"type": "accept", "username": self.profile.username})
            self._emit_state(link)

    def wait_for_invitation(self) -> str:
        """Chờ một lời mời cho lệnh /accept trống và trả username đang mời."""
        with self._invites_changed:
            while not self._stop.is_set():
                pending = [u for u, link in self._links.items() if link.state == "incoming"]
                if len(pending) == 1:
                    return pending[0]
                if pending:
                    raise ValueError("Hãy chọn /accept username: " + ", ".join(pending))
                self._invites_changed.wait()
            raise RuntimeError("Dịch vụ chat đã dừng.")

    def accept_chat(self, username: str) -> bool:
        """Trả True khi đã xếp phản hồi đồng ý lời mời của username."""
        with self._lock:
            link = self._links.get(username)
            if link is None or link.state != "incoming":
                return False
            link.state = "accepting"
            self._emit_state(link)
            link.outbox.put({"type": "accept", "username": self.profile.username})
            return True

    def decline_chat(self, username: str) -> None:
        """Gửi từ chối qua writer rồi đóng kết nối chờ."""
        with self._lock:
            link = self._links.get(username)
            if link is None or link.state != "incoming":
                return
            link.state = "declining"
            self._emit_state(link)
            link.outbox.put({"type": "decline"})

    def leave_chat(self, username: str) -> None:
        """Rời một cuộc chat, đóng socket của nó và giữ các phiên khác."""
        with self._lock:
            link = self._links.get(username)
            if link is not None:
                self._drop(link, "Bạn đã rời cuộc trò chuyện.")

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
            message_id = uuid.uuid4().hex
            link.pending_ack_ids.add(message_id)
            link.outbox.put({
                "type": "message",
                "message_id": message_id,
                "text": text,
            })

    def offer_file(self, username: str, path: Path, *, background: bool = False) -> None:
        """Tạo lời mời từ path và xếp vào phiên của username nếu phiên còn sẵn sàng."""
        with self._lock:
            link = self._links.get(username)
            if link is None or link.state != "ready":
                raise RuntimeError("Hãy mở cuộc chat trước khi gửi lời mời.")
            if background:
                self._spawn(self._prepare_file_offer, link, path)
                return
        self._queue_file_offer(link, path)

    def _prepare_file_offer(self, link: _ChatConnection, path: Path) -> None:
        """Tính hash ngoài luồng Tk, chuyển lỗi về đúng hội thoại."""
        try:
            self._queue_file_offer(link, path)
        except (OSError, RuntimeError, ValueError) as error:
            self.emit("file_prepare_error", link.username, {"path": str(path), "reason": str(error)})

    def _queue_file_offer(self, link: _ChatConnection, path: Path) -> None:
        """Chỉ chuyển lời mời vào đúng phiên đã chọn trước khi đọc file."""
        # Đọc đĩa ngoài khóa để reader và writer vẫn xử lý được tin nhắn.
        offer = build_file_offer(path)
        with self._lock:
            if self._links.get(link.username) is not link or link.state != "ready":
                raise RuntimeError("Phiên đã thay đổi trong lúc đọc file.")
            link.outgoing_files[offer["transfer_id"]] = (path, offer)
            self.emit("file_offered", link.username, offer)
            link.outbox.put({"type": "file.offer", **offer})

    def reply_file(self, username: str, transfer_id: str, accepted: bool) -> None:
        """Xếp phản hồi cho một lời mời còn chờ trong phiên với username."""
        with self._lock:
            link = self._links.get(username)
            if link is None or link.state != "ready":
                raise RuntimeError("Cuộc chat chưa sẵn sàng.")
            if transfer_id not in link.incoming_files:
                raise ValueError("Mã lời mời không tồn tại hoặc đã được trả lời.")

            offer = link.incoming_files.pop(transfer_id)
            if accepted:
                link.accepted_files[transfer_id] = offer
            link.outbox.put({
                "type": "file.reply",
                "transfer_id": transfer_id,
                "accepted": accepted,
            })

    def _progress_callback(self, username: str, offer: dict) -> Callable[[int], None]:
        """Chỉ báo khi phần trăm thay đổi. Mốc 100 dành cho file đã lưu."""
        previous = -1
        def report(count: int) -> None:
            nonlocal previous
            percent = min(99, count * 100 // max(1, offer["size"]))
            if percent != previous:
                previous = percent
                self.emit("file_progress", username, dict(offer, percent=percent))
        return report

    def _send_transfer(self, link: _ChatConnection, path: Path, offer: dict) -> None:
        """Mở socket dữ liệu, gửi byte rồi đợi máy nhận xác nhận đã lưu."""
        transfer_id = offer["transfer_id"]
        try:
            with connect_peer(link.ip, link.tcp_port) as connection:
                with self._lock:
                    if link.closed.is_set() or self._stop.is_set():
                        return
                    link.data_sockets.add(connection)
                try:
                    connection.settimeout(30)
                    send_frame(connection, {"type": "file.open", "protocol": PROTOCOL,
                               "request_id": link.request_id, "username": self.profile.username,
                               "transfer_id": transfer_id})
                    send_file_bytes(connection, path, offer["size"], self._progress_callback(link.username, offer))
                    send_frame(connection, {"type": "file.end", "transfer_id": transfer_id})
                    result = recv_frame(connection)
                    if result != {"type": "file.saved", "transfer_id": transfer_id}:
                        raise ValueError("Bên nhận chưa xác nhận đã lưu file.")
                    self.emit("file_sent", link.username, offer)
                finally:
                    with self._lock:
                        link.data_sockets.discard(connection)
        except (OSError, ValueError, EOFError) as error:
            self.emit("file_error", link.username, dict(offer, reason=str(error)))

    def _receive_transfer(self, data_link: _ChatConnection, packet: dict) -> None:
        """Nhận trên worker riêng khi socket khớp phiên chat và lời mời đã đồng ý."""
        connection = data_link.connection
        with self._lock:
            link = self._links.get(packet.get("username"))
            if (link is None or link.state != "ready" or link.ip != data_link.ip
                    or packet.get("protocol") != PROTOCOL or packet.get("request_id") != link.request_id):
                raise ValueError("Socket file không thuộc phiên chat.")
            offer = link.accepted_files.pop(packet.get("transfer_id"), None)
            if offer is None:
                raise ValueError("Chưa đồng ý nhận file này.")
            link.data_sockets.add(connection)
        try:
            connection.settimeout(30)
            saved = receive_file_bytes(connection, offer, self.downloads,
                                       self._progress_callback(link.username, offer))
            self.emit("file_received", link.username, dict(offer, path=str(saved)))
            send_frame(connection, {"type": "file.saved", "transfer_id": offer["transfer_id"]})
        except (OSError, EOFError, ValueError) as error:
            self.emit("file_error", link.username, dict(offer, reason=str(error)))
        finally:
            with self._lock:
                link.data_sockets.discard(connection)

    def _write_loop(self, link: _ChatConnection) -> None:
        """Một writer cho mỗi socket để phản hồi và tin nhắn không xen byte."""
        while not self._stop.is_set() and not link.closed.is_set():
            packet = link.outbox.get()
            if packet is None:
                return
            packet = dict(packet, protocol=PROTOCOL, request_id=link.request_id)
            try:
                send_frame(link.connection, packet)
            except (OSError, ValueError, TypeError) as error:
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
                    self.emit("sent", link.username, {
                        "text": packet["text"],
                        "message_id": packet["message_id"],
                    })
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

    def _close_duplicate(self, link: _ChatConnection) -> None:
        """Thu hồi socket dư của hai lời mời chéo nhau."""
        duplicate = link.duplicate
        link.duplicate = None

        if duplicate is not None:
            self._drop(duplicate, notify=False)

    def _drop(
        self, link: _ChatConnection, reason: str = "", *,
        state: str = "disconnected", notify: bool = True,
    ) -> None:
        """Đóng đúng socket sở hữu; reader cũ không được xóa phiên thay thế."""
        with self._lock:
            if link.closed.is_set():
                return
            link.closed.set()
            self._close_duplicate(link)
            for data_socket in link.data_sockets:
                try:
                    data_socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                data_socket.close()
            link.data_sockets.clear()
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

            link.closed.set()
            link.pending_ack_ids.clear()

    def stop(self) -> None:
        """Dừng listener, đánh thức reader/writer và join worker có giới hạn."""
        with self._lock:
            self._stop.set()
            self._invites_changed.notify_all()
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
