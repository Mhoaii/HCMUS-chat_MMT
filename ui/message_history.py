"""Lịch sử tin nhắn và ACK trong RAM, độc lập với Tkinter và socket."""


class MessageHistory:
    """Ghép từng dòng tin gửi với xác nhận của đúng peer."""

    def __init__(self) -> None:
        """Tạo lịch sử trống cho lần mở màn hình chat."""
        self.messages: dict[str, list[tuple[str, str]]] = {}
        self._sent_ids: dict[tuple[str, int], str] = {}
        self._received_acks: set[tuple[str, str]] = set()
        self._file_rows: dict[tuple[str, str], int] = {}

    def file_status(self, username: str, transfer_id: str, text: str, *, finished: bool = False) -> None:
        """Cập nhật một dòng cho mỗi lần truyền, kể cả khi tên file trùng nhau."""
        rows = self.messages.setdefault(username, [])
        key = username, transfer_id
        index = self._file_rows.setdefault(key, len(rows))
        if index == len(rows):
            rows.append(("File", text))
        else:
            rows[index] = ("File", text)
        if finished:
            del self._file_rows[key]

    def interrupt_files(self, username: str) -> None:
        """Đánh dấu các file đang chờ khi phiên chat đóng."""
        for key, index in list(self._file_rows.items()):
            if key[0] == username:
                sender, text = self.messages[username][index]
                self.messages[username][index] = (sender, text + " · Đã ngắt kết nối")
                del self._file_rows[key]

    def sent(self, username: str, text: str, message_id: str) -> None:
        """Thêm tin gửi và nhớ vị trí để cập nhật trạng thái theo ID."""
        rows = self.messages.setdefault(username, [])
        self._sent_ids[(username, len(rows))] = message_id
        rows.append(("Bạn", text))

    def received(self, username: str, sender: str, text: str) -> None:
        """Thêm tin đến vào lịch sử của người gửi."""
        self.messages.setdefault(username, []).append((sender, text))

    def acknowledge(self, username: str, message_id: str) -> None:
        """Ghi nhận cả ACK đến trước sự kiện sent."""
        self._received_acks.add((username, message_id))

    def delivery_status(self, username: str, row: int) -> str:
        """Trả nhãn gửi/nhận của dòng tin, hoặc chuỗi rỗng cho tin đến."""
        message_id = self._sent_ids.get((username, row))
        if message_id is None:
            return ""
        return "Đã nhận" if (username, message_id) in self._received_acks else "Đã gửi"
