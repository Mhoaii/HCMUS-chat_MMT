import json
from models.peer import LocalProfile

class PresenceProtocol:
    """Chuyển đổi giữa hồ sơ và gói HELLO JSON UTF-8."""
    @staticmethod
    def encode(profile: LocalProfile) -> bytes: 
        """Chuyển LocalProfile thành bytes JSON UTF-8 để gửi qua UDP."""
        message = {
            "type" : "HELLO", #dùng để chào hỏi
            "username" : profile.username,
            "display_name": profile.display_name,
            "job_title": profile.job_title,
            "tcp_port": profile.tcp_port,
            "status": profile.status
        }

        # UDP gửi bytes; JSON được chuyển sang UTF-8.
        return json.dumps(message, ensure_ascii=False).encode("utf-8")


    
    @staticmethod
    def decode(data: bytes) -> dict: 
        """Đọc bytes UTF-8 và trả dict HELLO đã kiểm tra các trường bắt buộc.
        Báo ValueError nếu dữ liệu, cổng TCP hoặc trạng thái không hợp lệ."""
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
