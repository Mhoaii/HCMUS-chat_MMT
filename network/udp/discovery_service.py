import threading

from models.peer import LocalProfile, Peer
from network.udp.listener import UDPListener
from network.udp.peer_registry import PeerRegistry
from network.udp.broadcaster import UDPBroadcaster

class DiscoveryService:
    """Điều phối UDP listener, broadcaster và việc loại peer hết hạn."""


    def __init__ (self, profile: LocalProfile) -> None:
        """Lưu hồ sơ, tạo registry và các thành phần UDP; chưa khởi động mạng."""

        self._profile = profile

        # Registry dùng chung cho listener và timeout checker trong discovery.
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
        """In thông báo peer mới; được UDPListener gọi với username."""

        print(f"\n[*] {username} is online")

    def start(self) -> None:
        """Chạy listener, broadcaster và thread timeout; bỏ qua nếu đã chạy.
        Cần mở TCP trước để hồ sơ quảng bá đúng cổng đang lắng nghe."""

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
        """Mỗi 0.5 giây, xóa peer hết hạn và in thông báo offline."""

        while not self._stop_event.wait(0.5):

            expired_peers = (
                self._registry.remove_expired_peers()
            )

            for peer in expired_peers:
                print(
                    f"\n[*] {peer.display_name} went offline"
                )

    def get_peer(self, username: str) -> Peer | None:
        """Trả bản sao Peer theo username để lấy IP/cổng TCP, hoặc None nếu chưa có."""

        return self._registry.get_peer(username)

    def list_peers(self) -> list[Peer]:
        """Trả danh sách bản sao peer để hiển thị; chưa có thì trả []."""

        return self._registry.list_peers()

    def set_status(self, status: str) -> None:
        """Đổi online/away cho lần broadcast tiếp theo; sai thì báo ValueError."""

        if status not in ("online", "away"):
            raise ValueError("Invalid status")

        self._profile.status = status

    def stop(self) -> None:
        """Dừng và chờ các thread UDP/timeout; giữ nguyên dữ liệu registry."""

        if not self._running:
            return

        self._stop_event.set()

        self._broadcaster.stop()
        self._listener.stop()

        if self._timeout_thread is not None:
            self._timeout_thread.join()
            self._timeout_thread = None

        self._running = False
