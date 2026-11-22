import socket

class TCPChatService:
    """Mở, nhận kết nối và đóng listener TCP của ứng dụng."""


    def __init__(self) -> None:
        """Khởi tạo service chưa có listener TCP."""
        self._listener: socket.socket | None = None #Gán _listener bằng None để biểu thị chưa mở socket.

    def start(self, port: int) -> int:
        """Mở listener và trả cổng TCP thực tế; port=0 để hệ điều hành chọn.
        Báo RuntimeError nếu đã chạy; đóng socket và báo lại lỗi nếu mở thất bại."""

        if self._listener is not None: 
            raise RuntimeError("TCP listener đã được khởi động.")

        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try: 
            # Nghe trên mọi giao diện IPv4 để máy khác trong LAN có thể kết nối.
            listener.bind(("0.0.0.0", port))
            listener.listen()

            # Đọc cổng sau bind(), đặc biệt khi người dùng yêu cầu cổng 0.
            actual_port = listener.getsockname()[1]

        except:
            
            listener.close()
            raise

        self._listener = listener

        return actual_port

    def stop(self):


        """Đóng listener nếu đang mở và đặt lại trạng thái chưa chạy."""
        if self._listener is not None:
            self._listener.close()
            self._listener = None
    
    def accept(self):
        """Chờ và trả (socket kết nối, địa chỉ peer); chặn tới khi có kết nối.
        Báo RuntimeError nếu listener chưa khởi động."""
        if self._listener is None:
            raise RuntimeError("TCP listener chưa khởi động.")
        return self._listener.accept()
            