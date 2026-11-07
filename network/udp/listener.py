# UDPListener
# │
# ├── Thuộc tính
# │   ├── _profile
# │   ├── _registry
# │   ├── _socket
# │   ├── _thread
# │   ├── _stop_event
# │   └── _on_peer_online
# │
# └── Phương thức
#     ├── __init__()
#     ├── start() v 
#     ├── _run()
#     └── stop()


import socket
import threading
import logging

from config import UDP_PORT
from models.peer import LocalProfile
from network.udp.peer_registry import PeerRegistry
from network.udp.presence_protocol import PresenceProtocol


logger = logging.getLogger(__name__)

class UDPListener:
    """Nhận UDP presence, bỏ gói lỗi/gói của mình và cập nhật danh sách peer.

    Sử dụng LocalProfile, PeerRegistry và PresenceProtocol, không kế thừa chúng.
    Giữ callback tùy chọn để báo peer mới; sở hữu socket, Thread và Event.
    Luồng nhận riêng tránh để recvfrom() chặn luồng giao diện.
    """
    def __init__(self, profile: LocalProfile, registry: PeerRegistry, on_peer_online = None):
        """Chuẩn bị bộ nhận UDP, chưa mở socket hay chạy thread.

        Đầu vào:
            profile (LocalProfile): Hồ sơ mình, dùng bỏ qua gói cùng username.
            registry (PeerRegistry): Nơi dùng chung để thêm/cập nhật peer.
            on_peer_online (callable | None): Hàm nhận username (str) khi thấy
                peer mới; kết quả trả về của callback không được sử dụng.
        Trả về: None. Callback sẽ chạy trong thread listener, không phải UI thread.
        """
        self._profile = profile
        self._registry = registry

        self._on_peer_online = on_peer_online
#         Đây là một hàm callback tùy chọn.
# Khi phát hiện peer mới, listener có thể gọi callback này.

        self._socket = None
        self._thread = None
        self._stop_event = threading.Event()



    def start(self):
        """Bind socket UDP trên mọi địa chỉ IPv4 và khởi động thread nhận.

        Đầu vào: Không có tham số ngoài self.
        Trả về: None; bỏ qua nếu thread đã chạy.
        Ngoại lệ: OSError khi bind/settimeout thất bại, sau khi đóng socket lỗi.
        Timeout 0.5 giây giúp vòng nhận định kỳ kiểm tra yêu cầu dừng.
        Cổng bind là UDP_PORT trong config, không phải TCP port của hồ sơ.
        """
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
        """Nhận, giải mã và đăng ký peer cho tới khi có yêu cầu dừng.

        Đầu vào: Không có tham số ngoài self; sử dụng socket đã bind.
        Trả về: None; khối finally đóng socket khi vòng lặp kết thúc.
        recvfrom(4096) cung cấp bytes và (IP nguồn, cổng nguồn).
        Bỏ gói không hợp lệ hoặc có username của mình; cập nhật registry bằng
        IP nguồn thật. Chỉ gọi callback khi upsert_peer() trả True.
        Lỗi callback chưa được bắt ở đây và có thể làm thread nhận kết thúc.
        """
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
        """Đặt cờ dừng và chờ thread nhận kết thúc, socket được đóng trong _run().

        Đầu vào: Không có tham số ngoài self.
        Trả về: None. Socket timeout giúp worker có cơ hội kiểm tra cờ dừng.
        Gọi từ luồng điều phối, không gọi từ callback của chính listener.
        """
        self._stop_event.set()

        if self._thread is not None:
            self._thread.join()
            self._thread = None

