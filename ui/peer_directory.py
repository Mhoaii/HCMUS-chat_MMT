"""Thông tin peer mà UI nhận qua UDP và lời mời TCP."""

from models.peer import Peer


class PeerDirectory:
    """Giữ danh tính cho hội thoại kể cả sau khi peer rời danh sách online."""

    def __init__(self) -> None:
        """Khởi tạo danh bạ trước lượt cập nhật UDP đầu tiên."""
        self.info: dict[str, dict] = {}
        self.online: list[str] = []
        self._snapshot: list[tuple] | None = None

    def remember(self, username: str, data: dict) -> dict:
        """Bổ sung tên và endpoint từ TCP khi UDP chưa cung cấp."""
        info = self.info.setdefault(username, {
            "display_name": username, "status": "chưa có presence",
            "ip": None, "tcp_port": None,
        })
        if data.get("display_name"):
            info["display_name"] = data["display_name"]
        for key in ("ip", "tcp_port"):
            if not info.get(key) and data.get(key):
                info[key] = data[key]
        return info

    def refresh(self, peers: list[Peer], *, force: bool, notify: bool) -> str | None:
        """Cập nhật snapshot đã sắp xếp. Trả None khi UI có thể bỏ qua lượt vẽ."""
        snapshot = [(p.username, p.display_name, p.status, p.ip, p.tcp_port) for p in peers]
        if snapshot == self._snapshot and not force:
            return None
        current = {p.username: p for p in peers}
        notice = self._changes(current) if notify else ""
        for username, info in self.info.items():
            if username not in current:
                info["status"] = "offline"
        for peer in peers:
            self.info[peer.username] = {
                "display_name": peer.display_name, "status": peer.status,
                "ip": peer.ip, "tcp_port": peer.tcp_port,
            }
        self.online = list(current)
        self._snapshot = snapshot
        return notice

    def _changes(self, current: dict[str, Peer]) -> str:
        """Mô tả các peer mới xuất hiện hoặc biến mất kể từ lượt trước."""
        previous = set(self.online)
        messages = []
        for username in sorted(current.keys() - previous):
            peer = current[username]
            messages.append(f"{peer.display_name} ({username}) vừa xuất hiện · {peer.status}.")
        for username in sorted(previous - current.keys()):
            name = self.info[username]["display_name"]
            messages.append(f"{name} ({username}) went offline")
        return " ".join(messages)
