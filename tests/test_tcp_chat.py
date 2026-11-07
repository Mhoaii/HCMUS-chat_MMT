"""Kiểm thử giao thức và tích hợp TCP bằng socket thật trên loopback."""
import queue
import socket
import struct
import threading
import time
import unittest
from unittest.mock import patch

from chat.chat_manager import ChatManager
from models.peer import LocalProfile
from network.tcp.protocol import encode_packet, receive_packet, send_packet
from network.tcp.tcp_client import TCPClient
from network.tcp.tcp_server import TCPServer
from network.udp.peer_registry import PeerRegistry


def packet(sender="a", recipient="b", message_id="id-1", text="Xin chào 👋\nDòng hai"):
    """Nhận các trường mẫu; trả dict CHAT phục vụ test."""
    return dict(type="CHAT", sender=sender, recipient=recipient,
                message_id=message_id, text=text)


class LocalDiscovery:
    """Discovery giả cho test TCP độc lập, dùng PeerRegistry thật."""

    def __init__(self, profile):
        """Nhận hồ sơ; trả None và tạo registry riêng."""
        self.profile = profile
        self.registry = PeerRegistry()

    def start(self):
        """Không có đầu vào; không mở UDP trong unit test; trả None."""

    def stop(self):
        """Không có đầu vào; không có UDP cần dừng; trả None."""

    def list_peers(self):
        """Không có đầu vào; trả list[Peer] từ registry thật."""
        return self.registry.list_peers()

    def get_peer(self, username):
        """Nhận username; trả Peer hoặc None từ registry thật."""
        return self.registry.get_peer(username)

    def set_status(self, status):
        """Nhận trạng thái; cập nhật hồ sơ thử nghiệm, trả None."""
        self.profile.status = status


class TestTCPProtocol(unittest.TestCase):
    """Kiểm tra framing không phụ thuộc cách TCP chia/gộp byte."""

    def test_fragmented_and_combined_frames(self):
        """Không có đầu vào; header bị chia và hai frame nối nhau vẫn đọc đúng; trả None."""
        left, right = socket.socketpair()
        self.addCleanup(left.close)
        self.addCleanup(right.close)
        right.settimeout(2)
        first, second = packet(), packet(message_id="id-2", text="Kế tiếp")
        frame = encode_packet(first) + encode_packet(second)

        def feed():
            """Không có đầu vào; gửi header từng mảnh rồi gộp payload; trả None."""
            left.sendall(frame[:1])
            time.sleep(0.02)
            left.sendall(frame[1:3])
            time.sleep(0.02)
            left.sendall(frame[3:])

        worker = threading.Thread(target=feed)
        worker.start()
        self.assertEqual(receive_packet(right), first)
        self.assertEqual(receive_packet(right), second)
        worker.join(2)
        self.assertFalse(worker.is_alive())

    def test_bad_header_json_utf8_and_fields(self):
        """Không có đầu vào; từ chối frame quá dài, UTF-8/JSON/trường sai; trả None."""
        for payload in (b'[]', b'not-json', b'\xff', b'{"type":"CHAT"}'):
            with self.subTest(payload=payload):
                left, right = socket.socketpair()
                try:
                    left.sendall(struct.pack("!I", len(payload)) + payload)
                    with self.assertRaises(ValueError):
                        receive_packet(right)
                finally:
                    left.close()
                    right.close()
        for size in (0, 1024 * 1024 + 1):
            left, right = socket.socketpair()
            try:
                left.sendall(struct.pack("!I", size))
                with self.assertRaises(ValueError):
                    receive_packet(right)
            finally:
                left.close()
                right.close()

    def test_truncated_frame(self):
        """Không có đầu vào; peer đóng giữa payload phải báo EOFError; trả None."""
        left, right = socket.socketpair()
        self.addCleanup(right.close)
        left.sendall(struct.pack("!I", 100) + b'{}')
        left.close()
        with self.assertRaises(EOFError):
            receive_packet(right)

    def test_mismatched_ack(self):
        """Không có đầu vào; ACK sai ID bị TCPClient từ chối; trả None."""
        listener = socket.socket()
        self.addCleanup(listener.close)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)

        def wrong_ack():
            """Không có đầu vào; nhận một tin rồi cố tình ACK sai; trả None."""
            connection, _ = listener.accept()
            with connection:
                receive_packet(connection)
                send_packet(connection, dict(type="ACK", sender="b", recipient="a",
                                             message_id="wrong"))

        worker = threading.Thread(target=wrong_ack, daemon=True)
        worker.start()
        with socket.socket() as connection:
            with self.assertRaises(ValueError):
                TCPClient.exchange(connection, listener.getsockname(), packet())
        worker.join(2)
        self.assertFalse(worker.is_alive())


class TestTCPIntegration(unittest.TestCase):
    """Ghép ChatManager, TCPServer/Client và registry, chỉ giả tầng UDP discovery."""

    def setUp(self):
        """Không có đầu vào; mở ba peer ở cổng tạm để không đụng cổng người dùng; trả None."""
        patcher = patch("chat.chat_manager.DiscoveryService", LocalDiscovery)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.backends = []
        self.events = []
        for username in ("a", "b", "c"):
            events = queue.Queue()
            profile = LocalProfile(username, username, "Test", 5001)
            # Dataclass yêu cầu cổng thực; test nội bộ cho phép bind 0 để xin cổng tạm.
            profile.tcp_port = 0
            backend = ChatManager(profile, lambda event, q=events, **data: q.put((event, data)))
            self.addCleanup(backend.close)
            backend.start()
            profile.tcp_port = backend.server._socket.getsockname()[1]
            self.backends.append(backend)
            self.events.append(events)
        for backend in self.backends:
            for other in self.backends:
                if backend is not other:
                    backend.discovery.registry.upsert_peer(
                        dict(username=other.profile.username, display_name=other.profile.username,
                             job_title="Test", tcp_port=other.profile.tcp_port, status="away"),
                        "127.0.0.1")

    def wait_event(self, index, event, message_id):
        """Nhận chỉ số peer, tên event, ID; trả dữ liệu sự kiện hoặc fail sau 4 giây."""
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            try:
                name, data = self.events[index].get(timeout=0.1)
            except queue.Empty:
                continue
            if name == event and data.get("message_id") == message_id:
                return data
        self.fail(f"Không nhận được {event}/{message_id}")

    def test_three_peers_two_way_and_real_ack(self):
        """Không có đầu vào; A-B, A-C, B-C chat hai chiều, Unicode và ACK thật; trả None."""
        for source, target in ((0, 1), (0, 2), (1, 2), (1, 0), (2, 0), (2, 1)):
            mid = f"{source}-{target}"
            text = f"Chào 👋 {mid}\nDòng mới"
            self.backends[source].send_message(self.backends[target].profile.username, text, mid)
            received = self.wait_event(target, "message", mid)
            self.assertEqual(received["text"], text)
            self.assertEqual(received["username"], self.backends[source].profile.username)
            self.assertEqual(self.wait_event(source, "ack", mid)["status"], "Đã nhận ACK")

    def test_simultaneous_senders(self):
        """Không có đầu vào; 8 client đồng thời gửi tới B đều nhận ACK; trả None."""
        results = queue.Queue()

        def send(index):
            """Nhận số thứ tự; gửi socket thật và đưa ACK/lỗi vào queue; trả None."""
            try:
                with socket.socket() as connection:
                    ack = TCPClient.exchange(connection, ("127.0.0.1", self.backends[1].profile.tcp_port),
                                             packet(message_id=f"parallel-{index}"))
                    results.put(ack["message_id"])
            except Exception as error:
                results.put(error)

        workers = [threading.Thread(target=send, args=(i,)) for i in range(8)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(6)
            self.assertFalse(worker.is_alive())
        self.assertEqual({results.get(timeout=1) for _ in workers},
                         {f"parallel-{i}" for i in range(8)})

    def test_duplicate_is_acked_but_not_displayed_twice(self):
        """Không có đầu vào; gửi lại cùng ID được ACK nhưng chỉ phát một message; trả None."""
        for _ in range(2):
            with socket.socket() as connection:
                ack = TCPClient.exchange(connection, ("127.0.0.1", self.backends[1].profile.tcp_port), packet())
                self.assertEqual(ack["type"], "ACK")
        self.wait_event(1, "message", "id-1")
        remaining = []
        while not self.events[1].empty():
            remaining.append(self.events[1].get())
        self.assertFalse(any(event == "message" for event, _ in remaining))

    def test_wrong_recipient_and_unknown_peer(self):
        """Không có đầu vào; server không ACK tin gửi sai người, lookup lạ bị chặn; trả None."""
        with socket.socket() as connection:
            with self.assertRaises(EOFError):
                TCPClient.exchange(connection, ("127.0.0.1", self.backends[1].profile.tcp_port),
                                   packet(recipient="someone-else"))
        with self.assertRaises(ValueError):
            self.backends[0].send_message("missing", "Hi", "id-missing")

    def test_shutdown_interrupts_partial_reader(self):
        """Không có đầu vào; close ngắt worker đang chờ đủ payload và đóng cổng; trả None."""
        backend = self.backends[0]
        address = ("127.0.0.1", backend.profile.tcp_port)
        with socket.create_connection(address, timeout=2) as connection:
            connection.sendall(struct.pack("!I", 100) + b'{')
            deadline = time.monotonic() + 2
            while not backend.server._clients and time.monotonic() < deadline:
                time.sleep(0.01)
            backend.close()
        self.assertFalse(backend.server._thread.is_alive())
        self.assertFalse(backend._peer_thread.is_alive())
        self.assertFalse(backend.server._workers)
        with socket.socket() as probe:
            probe.settimeout(0.5)
            self.assertNotEqual(probe.connect_ex(address), 0)


if __name__ == "__main__":
    unittest.main()
