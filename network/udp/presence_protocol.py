
# Bây giờ chúng ta muốn máy Hoàng thông báo cho các máy khác rằng:
# Tôi là Hoàng, đang chạy chương trình, sử dụng TCP port 5001 và có trạng thái away.

# Vấn đề là UDP socket không thể gửi trực tiếp một đối tượng LocalProfile.

# Hàm socket.sendto() yêu cầu dữ liệu dạng bytes.
# LocalProfile ->
# Đối tượng Python chứa thông tin Hoàng ->
# Encode — Mã hóa dữ liệu ->
# Bytes ->
# Dữ liệu có thể đưa vào UDP datagram ->
# UDP Socket → Máy Minh ->
# Decode — Giải mã dữ liệu ->
# Dictionary chứa thông tin Hoàng


import json
from models.peer import LocalProfile

class PresenceProtocol:
    """Quy định cách chuyển hồ sơ thành gói HELLO JSON UTF-8 và đọc ngược lại.

    Không giữ trạng thái; hai staticmethod được gọi trực tiếp qua tên lớp.
    Broadcaster/listener sử dụng lớp này, không kế thừa nó.
    Encode/decode ở đây là chuyển định dạng, không phải mã hóa bảo mật.
    """
    @staticmethod #encode
    def encode(profile: LocalProfile) -> bytes: 
        """Chuyển LocalProfile thành bytes để socket.sendto() có thể gửi.

        Đầu vào: profile (LocalProfile), chứa thông tin của máy gửi.
        Trả về: bytes chứa JSON UTF-8 với type="HELLO", username, display_name,
        job_title, tcp_port và status. ensure_ascii=False giữ chữ có dấu trong JSON.
        Không tự kiểm tra toàn bộ hồ sơ và không tự gửi gói tin.
        """
        message = {
            "type" : "HELLO", #dùng để chào hỏi
            "username" : profile.username,
            "display_name": profile.display_name,
            "job_title": profile.job_title,
            "tcp_port": profile.tcp_port,
            "status": profile.status
        }

#     json.dumps(message)
#    Chuyển dictionary Python thành chuỗi JSON.ensure_ascii=False

#    Giúp giữ nguyên chữ tiếng Việt trong chuỗi JSON, chẳng hạn Anh Hoàng, thay vì chuyển ký tự có dấu thành dạng Unicode escape.

#    .encode("utf-8")

#   Chuyển str thành bytes.

#   Đây là phần quan trọng vì UDP socket sẽ gửi bytes, không gửi trực tiếp dictionary.
        return json.dumps(message, ensure_ascii=False).encode("utf-8")


    
# bytes
#   ↓
# decode UTF-8
#   ↓
# JSON string
#   ↓
# json.loads()
#   ↓
# Dictionary
    @staticmethod
    def decode(data: bytes) -> dict: 
        """Giải mã và kiểm tra cấu trúc một UDP presence packet.

        Đầu vào: data (bytes), phần dữ liệu lấy từ socket.recvfrom().
        Trả về: dict hợp lệ với type="HELLO", các trường chuỗi, username không
        trắng, tcp_port là int 1..65535 và status là "online" hoặc "away".
        Ngoại lệ: ValueError khi UTF-8, JSON hoặc các trường bắt buộc không hợp lệ.
        Luồng xử lý: bytes -> chuỗi UTF-8 -> đối tượng JSON -> kiểm tra -> dict.
        Không tạo Peer, không xác thực danh tính, không cập nhật PeerRegistry.
        strip() chỉ kiểm tra username rỗng; không sửa username trong kết quả.
        """
        try:
            message = json.loads(
                data.decode("utf-8")
            )
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("Invalid JSON packet")

        if not isinstance(message, dict):
            raise ValueError("Packet must be an object")

        if message.get("type") != "HELLO":
            raise ValueError("Invalid packet type")

        for field in ("username", "display_name", "job_title"):
            value = message.get(field)

            if not isinstance(value, str):
                raise ValueError(f"Invalid {field}")

        if not message["username"].strip():
            raise ValueError("Username cannot be empty")

        port = message.get("tcp_port")

        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("Invalid TCP port")

        if message.get("status") not in ("online", "away"):
            raise ValueError("Invalid status")

        return message
