import socket
import threading
import logging

from config import UDP_PORT
from models.peer import LocalProfile
from .peer_registry import PeerRegistry
from .presence_protocol import PresenceProtocol


logger = logging.getLogger(__name__)

class UDPListener:
    """Nhận presence ở thread nền, cập nhật registry và thông báo peer mới."""
    def __init__(self, profile: LocalProfile, registry: PeerRegistry, on_peer_online = None):
        """Lưu hồ sơ, registry và callback tùy chọn; chưa mở socket.
        on_peer_online(username) chạy trong thread nhận khi phát hiện peer mới."""
        self._profile = profile
        self._registry = registry

        self._on_peer_online = on_peer_online
        self._socket = None
        self._thread = None
        self._stop_event = threading.Event()



    def start(self):
        """Bind cổng UDP discovery và chạy thread nhận; bỏ qua nếu đã chạy.
        Báo OSError nếu mở socket thất bại; timeout nhận là 0.5 giây."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._socket = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM
        )

        try:
            # Các terminal trên cùng máy cần dùng chung cổng UDP discovery.
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.bind(("0.0.0.0", UDP_PORT))
            self._socket.settimeout(0.5)
        except OSError:
            self._socket.close()
            self._socket = None
            raise

        self._stop_event.clear()

        self._thread = threading.Thread(
            target = self._run,
            name = "UDP-Listener",
            daemon = True
        )

        self._thread.start()

    def _run(self):
        """Bỏ gói lỗi/gói của mình, cập nhật peer bằng IP nguồn rồi báo peer mới.
        Luôn đóng socket khi kết thúc; lỗi callback có thể làm thread dừng."""
        try: 
            while not self._stop_event.is_set():

                try: 
                    data, address = self._socket.recvfrom(4096)

                except socket.timeout:
                    continue

                except OSError as error:
                    if not self._stop_event.is_set():
                        logger.error(
                            "UDP receive error: %s",
                            error
                        )

                    break


                 # 1. Giải mã UDP packet
                try:
                    message = PresenceProtocol.decode(data)

                except ValueError:
                    # Bỏ qua packet không hợp lệ
                    continue

                # 2. Bỏ qua presence của chính mình
                if message["username"] == self._profile.username:
                    continue

                # 3. Lấy IP nguồn của peer
                sender_ip = address[0]

                # 4. Thêm hoặc cập nhật PeerRegistry
                is_new = self._registry.upsert_peer(
                    message,
                    sender_ip
                )

                # 5. Thông báo nếu đây là peer mới
                if is_new and self._on_peer_online is not None:
                    self._on_peer_online(
                        message["username"]
                    )

        finally:
            if self._socket is not None:
                self._socket.close()
                self._socket = None
 

    def stop(self):
        """Báo dừng và chờ thread nhận đóng socket; gọi từ luồng điều phối."""
        self._stop_event.set()

        if self._thread is not None:
            self._thread.join()
            self._thread = None

