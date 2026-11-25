import socket
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

from network.tcp import file_transfer


class FileTransferTests(unittest.TestCase):
    """Kiểm tra byte đi qua socket dữ liệu riêng."""

    def test_send_file_bytes(self):
        """Nhận nguyên vẹn file rỗng và file nhị phân lớn hơn hai khối đọc."""
        with TemporaryDirectory() as folder:
            path = Path(folder, "sample.bin")
            for data in (b"", bytes(range(256)) * 600):
                with self.subTest(size=len(data)):
                    path.write_bytes(data)
                    sender, receiver = socket.socketpair()
                    with sender, receiver, ThreadPoolExecutor(max_workers=1) as pool:
                        sender.settimeout(3)
                        receiver.settimeout(3)
                        pending = pool.submit(file_transfer.send_file_bytes, sender, path, len(data))
                        received = bytearray()
                        while len(received) < len(data):
                            chunk = receiver.recv(8192)
                            self.assertTrue(chunk, "Socket đóng trước khi nhận đủ file")
                            received.extend(chunk)
                        self.assertEqual(pending.result(timeout=3), len(data))
                        self.assertEqual(received, data)

    def test_changed_size_before_sending(self):
        """Từ chối file có kích thước khác lời mời trước khi ghi vào socket."""
        with TemporaryDirectory() as folder:
            path = Path(folder, "changed.bin")
            path.write_bytes(b"abcd")
            sender, receiver = socket.socketpair()
            with sender, receiver:
                with self.assertRaises(ValueError):
                    file_transfer.send_file_bytes(sender, path, 3)
                sender.shutdown(socket.SHUT_WR)
                self.assertEqual(receiver.recv(1), b"")
