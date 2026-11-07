"""Backend dùng chung cho console/Tkinter: nối UDP discovery với TCP chat."""
from collections import OrderedDict
from dataclasses import asdict
import threading

from chat.connection_manager import ConnectionManager
from network.tcp.protocol import validate_packet
from network.tcp.tcp_server import TCPServer
from network.udp.discovery_service import DiscoveryService


class ChatManager:
    """Chứa DiscoveryService, TCPServer, ConnectionManager (composition).

    Không kế thừa chúng. Lịch sử UI và chống trùng hiện chỉ nằm trong RAM.
    """

    def __init__(self, profile, emit):
        """Nhận LocalProfile và emit(event, **data) an toàn đa luồng; trả None."""
        self.profile = profile
        self.emit = emit
        self.discovery = DiscoveryService(profile)
        self.connections = ConnectionManager(emit)
        self.server = TCPServer(profile, self._receive)
        self._lifecycle = threading.Lock()
        self._received_lock = threading.Lock()
        self._received = OrderedDict()
        self._stop = threading.Event()
        self._closed = False
        self._running = False
        self._peer_thread = None

    def start(self):
        """Không có đầu vào; mở TCP trước UDP rồi phát snapshot peer; trả None.

        Lỗi khởi động được rollback và truyền ra; close/start dùng chung lock.
        """
        with self._lifecycle:
            if self._closed:
                raise RuntimeError("Backend đã đóng")
            if self._running:
                return
            try:
                self.server.start()
                self.discovery.start()
            except Exception:
                self.server.stop()
                self.discovery.stop()
                raise
            self._running = True
            self._peer_thread = threading.Thread(target=self._publish_peers,
                                                 name="Peer-Snapshot", daemon=True)
            self._peer_thread.start()
            self.emit("notice", message=f"Đã mở TCP {self.profile.tcp_port} và UDP discovery")

    def _publish_peers(self):
        """Không có đầu vào; phát danh sách Peer dạng dict mỗi 0.5 giây; trả None khi dừng."""
        while not self._stop.is_set():
            self.emit("peers", peers=[asdict(p) for p in self.discovery.list_peers()])
            self._stop.wait(0.5)

    def _receive(self, packet):
        """Nhận CHAT đã kiểm tra; đưa tin vào hàng đợi UI rồi trả None để server ACK.

        Giữ tối đa 4096 cặp (sender, message_id) để bỏ tin trùng trong phiên.
        ACK không đồng nghĩa đã xem hay đã lưu tin vào SQLite.
        """
        key = (packet["sender"], packet["message_id"])
        with self._received_lock:
            if key in self._received:
                return
            self.emit("message", username=packet["sender"], text=packet["text"],
                      message_id=packet["message_id"])
            self._received[key] = None
            if len(self._received) > 4096:
                self._received.popitem(last=False)

    def send_message(self, username, text, message_id):
        """Nhận username/text/message_id (str); gửi nền tới Peer tìm qua UDP; trả None.

        ValueError nếu không tìm thấy người nhận/hồ sơ tin sai; không gửi offline.
        Không tự retry khi mất ACK vì chưa có lưu trữ bền vững.
        """
        if not self._running or self._closed:
            raise RuntimeError("Backend chưa chạy hoặc đã đóng")
        peer = self.discovery.get_peer(username)
        if peer is None or username == self.profile.username:
            raise ValueError("Không tìm thấy peer nhận trong LAN")
        packet = validate_packet({"type": "CHAT", "sender": self.profile.username,
                                  "recipient": username, "text": text,
                                  "message_id": message_id})
        self.connections.send(peer, packet)

    def set_status(self, status):
        """Nhận 'online'/'away'; cập nhật hồ sơ dùng cho UDP, trả None; sai thì ValueError."""
        self.discovery.set_status(status)

    def send_file(self, username, path, transfer_id):
        """Nhận tham số từ UI; trả None và thông báo chưa hỗ trợ truyền file thật."""
        self.emit("file_progress", transfer_id=transfer_id, percent=0,
                  status="Chưa hỗ trợ truyền file TCP")
        self.emit("notice", message="Đã tích hợp chat TCP; truyền file chưa được triển khai")

    def decide_file(self, transfer_id, accept):
        """Nhận ID và quyết định nhận file từ UI; trả None, thông báo chưa hỗ trợ."""
        self.emit("notice", message="Chưa hỗ trợ nhận file")

    def cancel_file(self, transfer_id):
        """Nhận ID file từ UI; trả None, không có tác vụ truyền file thật để hủy."""
        self.emit("notice", message="Không có tác vụ truyền file TCP đang chạy")

    def close(self):
        """Không có đầu vào; dừng snapshot, discovery, socket và worker; trả None."""
        with self._lifecycle:
            if self._closed:
                return
            self._closed = True
            self._stop.set()
            self.discovery.stop()
            self.connections.close()
            self.server.stop()
            if self._peer_thread:
                self._peer_thread.join(timeout=2)
            self._running = False
