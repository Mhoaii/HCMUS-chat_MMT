
import unittest

from network.udp.peer_registry import PeerRegistry


class TestPeerRegistry(unittest.TestCase):

    """Kiểm thử thêm, cập nhật và hết hạn peer bằng thời gian giả lập."""
    def setUp(self):
        """Tạo registry rỗng và gói HELLO mẫu trước mỗi test."""
        self.registry = PeerRegistry()

        self.message = {
            "type": "HELLO",
            "username": "minh",
            "display_name": "Anh Minh",
            "job_title": "Developer",
            "tcp_port": 5002,
            "status": "online"
        }

    def test_add_peer(self):
        """Kiểm tra peer mới trả True và lưu đúng IP/cổng TCP."""
        is_new = self.registry.upsert_peer(
            self.message,
            "192.168.1.11",
            now=100
        )

        self.assertTrue(is_new)

        peer = self.registry.get_peer("minh")

        self.assertIsNotNone(peer)
        self.assertEqual(peer.ip, "192.168.1.11")
        self.assertEqual(peer.tcp_port, 5002)

    def test_update_peer(self):
        """Kiểm tra peer cũ trả False và cập nhật status/last_seen."""
        self.registry.upsert_peer(
            self.message,
            "192.168.1.11",
            now=100
        )

        updated = dict(self.message)
        updated["status"] = "away"

        is_new = self.registry.upsert_peer(
            updated,
            "192.168.1.11",
            now=105
        )

        self.assertFalse(is_new)

        peer = self.registry.get_peer("minh")

        self.assertEqual(peer.status, "away")
        self.assertEqual(peer.last_seen, 105)

    def test_timeout(self):
        """Kiểm tra peer còn trước hạn và bị xóa đúng mốc timeout."""
        self.registry.upsert_peer(
            self.message,
            "192.168.1.11",
            now=100
        )

        # Chưa đủ 10 giây: Minh vẫn tồn tại.
        expired = self.registry.remove_expired_peers(now=109)

        self.assertEqual(expired, [])
        self.assertIsNotNone(
            self.registry.get_peer("minh")
        )

        # Đủ 10 giây: Minh bị loại khỏi registry.
        expired = self.registry.remove_expired_peers(now=110)

        self.assertEqual(len(expired), 1)
        self.assertEqual(expired[0].username, "minh")
        self.assertIsNone(
            self.registry.get_peer("minh")
        )


if __name__ == "__main__":
    unittest.main()
