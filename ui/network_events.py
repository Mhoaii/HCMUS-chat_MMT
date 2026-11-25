"""Chuyển sự kiện từ luồng mạng tới luồng Tkinter."""

from collections.abc import Iterator
import queue
import threading


class NetworkEventQueue:
    """Nhận sự kiện qua các worker và ngừng nhận khi cửa sổ đóng."""

    def __init__(self) -> None:
        """Tạo hàng đợi và khóa đồng bộ thao tác đóng với thao tác đăng sự kiện."""
        self._events: queue.Queue[tuple[str, str, dict]] = queue.Queue()
        self._lock = threading.Lock()
        self.closed = threading.Event()

    def post(self, kind: str, username: str, data: dict | str = "") -> None:
        """Đăng sự kiện nếu hàng đợi còn mở."""
        with self._lock:
            if not self.closed.is_set():
                payload = data if isinstance(data, dict) else {"text": data}
                self._events.put((kind, username, payload))

    def poll(self, limit: int = 50) -> Iterator[tuple[str, str, dict]]:
        """Rút tối đa limit sự kiện mỗi lượt để UI tiếp tục phản hồi."""
        for _ in range(limit):
            try:
                yield self._events.get_nowait()
            except queue.Empty:
                return

    def close(self) -> None:
        """Ngừng nhận và bỏ các sự kiện còn chờ trước khi hủy Tk."""
        with self._lock:
            self.closed.set()
            while True:
                try:
                    self._events.get_nowait()
                except queue.Empty:
                    return
