import unittest

from models.peer import LocalProfile
from network.udp.components.presence_protocol import PresenceProtocol

class TestPresenceProtocol(unittest.TestCase):
    """Kiểm thử chuyển đổi và kiểm tra gói presence."""
    def test_encode_decode(self):
        """Kiểm tra encode/decode giữ đúng thông tin hồ sơ và tiếng Việt."""
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
        """Kiểm tra decode báo ValueError khi dữ liệu không phải JSON."""
        with self.assertRaises(ValueError):
            PresenceProtocol.decode(b"not json")


if __name__ == "__main__":
    unittest.main()
