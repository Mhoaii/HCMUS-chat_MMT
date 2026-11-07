import socket

class TCPChatService:
    """Quản lý socket lắng nghe kết nối TCP của ứng dụng chat.

    Đầu vào khi tạo: Không có.
    Kết quả khi tạo: Đối tượng service ở trạng thái chưa mở listener.
    Quy trình: start() mở và giữ socket, stop() đóng socket đã lưu.
    Lưu ý: Thread điều phối gọi các phương thức vòng đời theo thứ tự.
    """


    def __init__(self) -> None:
        self._listener: socket.socket | None = None #Gán _listener bằng None để biểu thị chưa mở socket.

    def start(self, port: int) -> int:
        """Mở listener TCP IPv4 và lấy cổng hệ điều hành đã cấp.

        Đầu vào: port (int), cổng cần mở từ 0 đến 65535.
            Truyền 0 để hệ điều hành chọn cổng trống.
        Trả về: int, số cổng TCP thực tế đang lắng nghe.
        Quy trình: Tạo socket, bind, listen rồi lưu socket vào service.
        Ngoại lệ: ValueError nếu cổng ngoài khoảng cho phép,
            RuntimeError nếu service đã chạy, OSError nếu mở cổng thất bại.
        """

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


        if self._listener is not None:
            self._listener.close()
            self._listener = None
    
    def accept(self):
        if self._listener is None:
            raise RuntimeError("TCP listener chưa khởi động.")
        return self._listener.accept()
            