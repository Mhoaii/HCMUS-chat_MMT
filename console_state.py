"""Trạng thái hội thoại terminal, độc lập với socket và bộ đọc bàn phím."""

import threading
from collections import defaultdict
from collections.abc import Callable


class ConsoleState:
    """Bảo vệ lựa chọn, lịch sử và tin chưa đọc dùng chung giữa các thread."""

    def __init__(self, display: Callable[[str, str, dict], None]) -> None:
        """Nhận hàm hiển thị sự kiện và khởi tạo trạng thái terminal trống."""
        self._lock = threading.RLock()
        self._current = ""
        self._states: dict[str, str] = {}
        self._history: dict[str, list[tuple[str, str]]] = defaultdict(list)
        self._unread: dict[str, int] = defaultdict(int)
        self._offers: dict[str, dict[str, dict]] = defaultdict(dict)
        self.display = display
        self.invalidate: Callable[[], None] = lambda: None

    @property
    def current(self) -> str:
        """Trả username đang chọn dưới khóa, hoặc chuỗi rỗng ở prompt chính."""
        with self._lock:
            return self._current

    def prompt(self) -> str:
        """Trả prompt động để bộ đọc vẽ lại ngay khi phiên hiện tại đóng."""
        username = self.current
        return f"[{username}] > " if username else "> "

    def status(self, username: str) -> str:
        """Trả trạng thái cuối cùng của username, rỗng nếu chưa có sự kiện."""
        with self._lock:
            return self._states.get(username, "")

    def select(self, username: str) -> None:
        """Chọn hội thoại, hiển thị lịch sử và lời mời file; đánh dấu tin đã đọc."""
        with self._lock:
            self._current = username
            if username:
                print(f"\nĐang chọn {username} · {self._unread[username]} tin chưa đọc")
                for sender, text in self._history[username]:
                    print(f"{sender}: {text}")
                self._unread[username] = 0
                for offer in self._offers[username].values():
                    self.display("file_offer", username, offer)
        self.invalidate()

    def pending_invitation(self) -> str:
        """Trả lời mời đến đầu tiên đang chờ; báo ValueError nếu chưa có."""
        with self._lock:
            for username, state in self._states.items():
                if state == "incoming":
                    return username
        raise ValueError("Chưa có lời mời chat. Bạn có thể tiếp tục nhập lệnh.")

    def answered_file(self, username: str, transfer_id: str) -> None:
        """Gỡ lời mời file sau khi service đã xếp phản hồi thành công."""
        with self._lock:
            self._offers[username].pop(transfer_id, None)

    def show_chats(self) -> None:
        """In các hội thoại đã biết cùng trạng thái và bộ đếm chưa đọc."""
        with self._lock:
            if not self._states:
                print("Chưa có hội thoại.")
            for username, state in self._states.items():
                print(f"{username} | {state} | {self._unread[username]} tin chưa đọc")

    def on_event(self, kind: str, username: str, data: dict) -> None:
        """Nhận callback mạng, cập nhật dưới khóa rồi yêu cầu vẽ lại prompt."""
        with self._lock:
            if kind == "message":
                self._history[username].append((username, data["text"]))
                if username != self._current:
                    self._unread[username] += 1
                    print(f"\nTin mới từ {username} ({self._unread[username]} tin chưa đọc).")
                else:
                    self.display(kind, username, data)
            elif kind == "sent":
                self._history[username].append(("Bạn", data["text"]))
                print(f"\n[Bạn → {username}] {data['text']}")
            else:
                if kind == "chat_state":
                    state = data["state"]
                    self._states[username] = state
                    if state in ("disconnected", "error", "declined", "expired"):
                        self._offers[username].clear()
                        if self._current == username:
                            self._current = ""
                elif kind == "file_offer":
                    self._offers[username][data["transfer_id"]] = dict(data)
                self.display(kind, username, data)
        self.invalidate()
