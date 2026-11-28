import socket
import unittest
from unittest.mock import Mock

from network.tcp.tcp_chat import connect_peer, receive_messages, send_message


class TestTCPChat(unittest.TestCase):
    """Kiểm tra API gửi và nhận văn bản của TCP hiện tại."""

    def test_connect_and_send_utf8_line(self):
        """Kết nối thật và kiểm tra các byte bên nhận đọc được."""
        with socket.socket() as server:
            server.bind(("127.0.0.1", 0))
            server.listen()
            server.settimeout(2)
            host, port = server.getsockname()

            with connect_peer(host, port) as sender:
                receiver, _ = server.accept()
                with receiver:
                    receiver.settimeout(2)
                    send_message(sender, "Chào Hoài 👋")
                    sender.shutdown(socket.SHUT_WR)

                    with receiver.makefile("rb") as stream:
                        self.assertEqual(
                            stream.read(),
                            "Chào Hoài 👋\n".encode("utf-8"),
                        )

    def test_receive_split_utf8_and_two_lines(self):
        """Ghép ký tự UTF-8 bị chia giữa hai recv và tách đúng từng tin."""
        connection = Mock(spec=socket.socket)
        connection.recv.side_effect = [
            b"Ch\xc3",
            b"\xa0o\nOK\n",
            b"",
        ]
        messages = []
        disconnected = Mock()

        receive_messages(connection, messages.append, disconnected)

        self.assertEqual(messages, ["Chào", "OK"])
        disconnected.assert_called_once_with()

    def test_connect_rejects_invalid_port(self):
        """Từ chối cổng nằm ngoài khoảng 1..65535."""
        for port in (0, 65536):
            with self.subTest(port=port), self.assertRaises(ValueError):
                connect_peer("127.0.0.1", port)


if __name__ == "__main__":
    unittest.main()