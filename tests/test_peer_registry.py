
import unittest

from network.udp.peer_registry import PeerRegistry


class TestPeerRegistry(unittest.TestCase):

    """Nhóm kiểm thử PeerRegistry, kế thừa unittest.TestCase.

    TestCase cung cấp assertEqual/assertTrue và cơ chế chạy setUp trước mỗi test.
    Các bài test truyền now giả lập nên không cần chờ timeout ngoài đời thật.
    """
    def setUp(self):
        """Chuẩn bị registry rỗng và gói HELLO mẫu trước mỗi bài test.

        Đầu vào: Chỉ self do unittest cung cấp.
        Trả về: None; lưu dữ liệu vào self.registry và self.message.
        """
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
        """Kiểm tra thêm peer lần đầu trả True và lưu đúng IP/TCP port.

        Đầu vào: Chỉ self với dữ liệu đã được setUp chuẩn bị.
        Trả về: None; assertion thất bại sẽ làm unittest báo test không đạt.
        """
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
        """Kiểm tra peer cũ được cập nhật status/last_seen và trả False.

        Đầu vào: Chỉ self với dữ liệu từ setUp.
        Trả về: None; assertion thất bại sẽ làm unittest báo test không đạt.
        """
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
        """Kiểm tra peer còn tồn tại trước hạn và bị xóa đúng mốc timeout.

        Đầu vào: Chỉ self; các mốc now được giả lập ngay trong bài test.
        Trả về: None; assertion thất bại sẽ làm unittest báo test không đạt.
        """
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
