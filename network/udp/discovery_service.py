# DiscoveryService
# │
# ├── __init__(profile)
# │
# ├── start()
# │      ├── Start UDPListener
# │      ├── Start UDPBroadcaster
# │      └── Start Timeout Checker
# │
# ├── stop()
# │      └── Dừng các thread
# │
# ├── get_peer(username)
# │      └── Tìm một peer
# │
# ├── list_peers()
# │      └── Lấy danh sách online
# │
# └── set_status(status)
#        └── Thay đổi online / away


import threading

from models.peer import LocalProfile, Peer
from network.udp.listener import UDPListener
from network.udp.peer_registry import PeerRegistry
from network.udp.broadcaster import UDPBroadcaster

class DiscoveryService:
    """Điều phối việc phát hiện các peer trong mạng LAN qua UDP.

    Sở hữu PeerRegistry, UDPBroadcaster, UDPListener và thread kiểm tra timeout
    (composition: chứa và sử dụng, không kế thừa). Các thành phần cùng dùng
    LocalProfile; listener và timeout checker cùng dùng một registry.
    Cung cấp get_peer/list_peers cho TCP hoặc giao diện gọi về sau.
    Không gửi tin TCP, truyền file hay lưu lịch sử chat.
    """


    def __init__ (self, profile: LocalProfile) -> None:
        """
        Khởi tạo DiscoveryService.

        Tham số:
            profile (LocalProfile):
                Thông tin người đang chạy ứng dụng.

        Trả về:
            None.

        Chức năng:
            - Lưu LocalProfile.
            - Tạo PeerRegistry.
            - Tạo UDPBroadcaster.
            - Tạo UDPListener.
            - Chuẩn bị thread kiểm tra timeout.

        Lưu ý:
            Hàm này chưa khởi động UDP.
            UDP chỉ bắt đầu khi gọi start().
        """

        self._profile = profile

        # Registry duy nhất của module UDP.
        self._registry = PeerRegistry()

        # Phát thông tin bản thân ra mạng.
        self._broadcaster = UDPBroadcaster(
            profile=self._profile
        )

        # Nhận thông tin từ các peer khác.
        self._listener = UDPListener(
            profile=self._profile,
            registry=self._registry,
            on_peer_online=self._on_peer_online
        )

        # Sử dụng để yêu cầu dừng timeout checker.
        self._stop_event = threading.Event()

        # Thread sẽ được tạo trong start().
        self._timeout_thread = None

        # Cho biết service đã được khởi động chưa.
        self._running = False

    def _on_peer_online(self, username: str) -> None:
        """
        Thông báo khi phát hiện peer mới.

        Tham số:
            username (str):
                Username của peer vừa được phát hiện.

        Trả về:
            None.
        Được gọi bởi:
            UDPListener khi upsert_peer()
            trả về True.
        """

        print(f"\n[*] {username} is online")

    def start(self) -> None:
        """
        Khởi động toàn bộ hệ thống UDP Discovery.

        Tham số:
            Không có tham số ngoài self.

        Trả về:
            None.

        Chức năng:
            1. Khởi động UDPListener.
            2. Khởi động UDPBroadcaster.
            3. Tạo thread kiểm tra timeout.

        Lỗi đồng bộ khi gọi start() được báo ra ngoài.
        Lỗi xảy ra bên trong thread nền không tự truyền về đây.

        Điều kiện:
            TCP port trong LocalProfile phải hợp lệ.
            Trong ứng dụng thật, TCP server phải
            đang lắng nghe trước khi gọi start().
        """

        if self._running:
            return

        self._stop_event.clear()

        # Listener khởi động trước Broadcaster.
        self._listener.start()

        try:
            self._broadcaster.start()
        except Exception:
            self._listener.stop()
            raise

        # Thread chuyên kiểm tra peer offline.
        self._timeout_thread = threading.Thread(
            target=self._check_timeouts,
            name="UDP-Timeout-Checker",
            daemon=True
        )

        self._running = True

        self._timeout_thread.start()

    def _check_timeouts(self) -> None:
        """
        Kiểm tra và loại bỏ những peer hết hạn.

        Tham số:
            Không có tham số ngoài self.

        Trả về:
            None.

        Chức năng:
            - Kiểm tra Registry mỗi 0.5 giây.
            - Peer quá hạn PEER_TIMEOUT (config, mặc định 10 giây)
              sẽ được xóa khỏi Registry.
            - Hiển thị thông báo offline.

        Hàm chạy trong thread riêng.

        Giá trị 0.5 là chu kỳ kiểm tra,
        KHÔNG phải thời gian timeout của peer.
        """

        while not self._stop_event.wait(0.5):

            expired_peers = (
                self._registry.remove_expired_peers()
            )

            for peer in expired_peers:
                print(
                    f"\n[*] {peer.display_name} went offline"
                )

    def get_peer(self, username: str) -> Peer | None:
        """
        Tìm một peer trong danh sách đã phát hiện.

        Tham số:
            username (str):
                Username cần tìm.
                Ví dụ: "minh".

        Trả về:
            Peer:
                Bản sao thông tin peer nếu tìm thấy.

            None:
                Nếu username không tồn tại.

        Mục đích:
            Cung cấp IP và TCP port cho
            ConnectionManager của phần TCP.
        """

        return self._registry.get_peer(username)

    def list_peers(self) -> list[Peer]:
        """
        Lấy danh sách các peer hiện có.

        Tham số:
            Không có tham số ngoài self.

        Trả về:
            list[Peer]:
                Danh sách bản sao các Peer.

            []:
                Nếu chưa phát hiện peer nào.

        Mục đích:
            Cung cấp danh sách cho giao diện.
        """

        return self._registry.list_peers()

    def set_status(self, status: str) -> None:
        """
        Thay đổi trạng thái của chính mình.

        Tham số:
            status (str):
                "online" hoặc "away".

        Trả về:
            None.

        Ngoại lệ:
            ValueError nếu status không hợp lệ.

        Chức năng:
            Cập nhật status trong LocalProfile.

        UDPBroadcaster sẽ đọc giá trị mới
        và gửi trong lần broadcast tiếp theo.
        """

        if status not in ("online", "away"):
            raise ValueError("Invalid status")

        self._profile.status = status

    def stop(self) -> None:
        """
        Dừng toàn bộ UDP Discovery.

        Tham số:
            Không có tham số ngoài self.

        Trả về:
            None.

        Chức năng:
            1. Báo timeout checker dừng.
            2. Dừng UDPBroadcaster.
            3. Dừng UDPListener.
            4. Chờ timeout thread kết thúc.
            5. Cập nhật trạng thái service.

        Lưu ý:
            stop() không thay đổi trạng thái
            của peer khác trong Registry.
        """

        if not self._running:
            return

        self._stop_event.set()

        self._broadcaster.stop()
        self._listener.stop()

        if self._timeout_thread is not None:
            self._timeout_thread.join()
            self._timeout_thread = None

        self._running = False
