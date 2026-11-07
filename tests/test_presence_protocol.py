import unittest

from models.peer import LocalProfile
from network.udp.presence_protocol import PresenceProtocol

class TestPresenceProtocol(unittest.TestCase):
    """Nhóm kiểm thử định dạng presence, kế thừa unittest.TestCase.

    Sử dụng các hàm assert do lớp cha cung cấp để kiểm tra kết quả và ngoại lệ.
    """
    def test_encode_decode(self):
        """Kiểm tra hồ sơ được encode thành bytes và decode giữ các trường đã chọn.

        Đầu vào: Chỉ self; tạo LocalProfile mẫu bên trong bài test.
        Trả về: None; assertion thất bại sẽ làm unittest báo test không đạt.
        """
        profile = LocalProfile(
            username="hoang",
            display_name="Anh Hoàng",
            job_title="Marketing",
            tcp_port=5001,
            status="away"
        )

        packet = PresenceProtocol.encode(profile)

        self.assertIsInstance(packet, bytes)

        message = PresenceProtocol.decode(packet)

        self.assertEqual(message["type"], "HELLO")
        self.assertEqual(message["username"], "hoang")
        self.assertEqual(message["display_name"], "Anh Hoàng")
        self.assertEqual(message["tcp_port"], 5001)
        self.assertEqual(message["status"], "away")

    def test_invalid_packet(self):
        """Kiểm tra dữ liệu không phải JSON bị decode từ chối bằng ValueError.

        Đầu vào: Chỉ self; dữ liệu thử là bytes b"not json".
        Trả về: None; unittest báo lỗi nếu ngoại lệ mong đợi không xuất hiện.
        """
        with self.assertRaises(ValueError):
            PresenceProtocol.decode(b"not json")


if __name__ == "__main__":
    unittest.main()
