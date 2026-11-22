from dataclasses import dataclass

@dataclass
class LocalProfile:
    """Hồ sơ cục bộ: username, tên, chức danh, cổng TCP và online/away."""
    username: str
    display_name: str
    job_title: str
    tcp_port: int
    status: str = "away"
    def __post_init__(self):
        """Kiểm tra tên hiển thị, cổng TCP và trạng thái; sai thì báo ValueError."""
        if not self.display_name:
            raise ValueError("Tên hiển thị không được để rỗng")
        
        if not 1 <= self.tcp_port <= 65535:
            raise ValueError("Invalid TCP port")

        if self.status not in ("online", "away"):
            raise ValueError("Invalid status")


@dataclass
class Peer:
    """Thông tin peer qua UDP, gồm endpoint, trạng thái và last_seen monotonic."""
    username: str
    display_name: str
    job_title: str
    ip: str
    status:str
    last_seen: float
    tcp_port: int = 0 # Giá trị mặc định của dữ liệu; lớp này không thực hiện bind socket.       

