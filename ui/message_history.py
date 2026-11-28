"""Lịch sử hội thoại và tiến độ truyền file trong RAM, độc lập với Tkinter và socket."""


class MessageHistory:
    """Lưu tin nhắn và cập nhật dòng tiến độ theo mã truyền file của từng peer."""

    def __init__(self) -> None:
        """Tạo lịch sử trống cho lần mở màn hình chat."""
        self.messages: dict[str, list[tuple[str, str]]] = {}
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
