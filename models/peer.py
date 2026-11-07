from dataclasses import dataclass

@dataclass
class LocalProfile:
    """Lưu hồ sơ của chính người đang chạy ứng dụng, không phải tài khoản xác thực.

    Đầu vào khi tạo: username (str), display_name (str), job_title (str),
    tcp_port (int, 1..65535), status (str, mặc định "away").
    @dataclass tự sinh __init__, __repr__ và __eq__ từ các trường dữ liệu.
    Sau __init__, Python tự gọi __post_init__ để kiểm tra một số giá trị.
    Lớp này không kế thừa Peer; broadcaster và listener giữ tham chiếu tới nó.
    """
    username: str
    display_name: str
    job_title: str
    tcp_port: int
    status: str = "away"
    def __post_init__(self):
        """Kiểm tra hồ sơ ngay sau khi dataclass khởi tạo xong.

        Đầu vào: Chỉ self, tức đối tượng LocalProfile vừa được tạo.
        Trả về: None.
        Ngoại lệ: ValueError nếu tên hiển thị rỗng, cổng ngoài 1..65535,
        hoặc trạng thái khác "online"/"away".
        Chú ý: Type hint không tự kiểm tra kiểu dữ liệu lúc chạy.
        """
        if not self.display_name:
            raise ValueError("Tên hiển thị không được để rỗng")
        
        if not 1 <= self.tcp_port <= 65535:
            raise ValueError("Invalid TCP port")

        if self.status not in ("online", "away"):
            raise ValueError("Invalid status")

@dataclass
class Peer:
    """Lưu thông tin một người khác được phát hiện qua UDP.

    Đầu vào khi tạo: username, display_name, job_title, ip, status (str);
    last_seen (float, mốc time.monotonic()); tcp_port (int, mặc định 0).
    last_seen dùng tính thời gian vắng mặt, không phải ngày giờ trên đồng hồ.
    tcp_port=0 là giá trị mặc định dữ liệu, không tự mở hay cấp phát socket.
    @dataclass tự sinh các phương thức cơ bản; lớp không kế thừa LocalProfile.
    PeerRegistry chứa các Peer; Peer không tự gửi/nhận dữ liệu mạng.
    """
    username: str
    display_name: str
    job_title: str
    ip: str
    status:str
    last_seen: float
    tcp_port: int = 0 # Giá trị mặc định của dữ liệu; lớp này không thực hiện bind socket.       

