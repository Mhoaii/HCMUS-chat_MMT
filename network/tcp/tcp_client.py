"""Phía chủ động kết nối TCP; mỗi lần gửi sử dụng một kết nối riêng."""
from network.tcp.protocol import receive_packet, send_packet


class TCPClient:
    """Gửi một CHAT và đợi ACK thật từ đầu nhận; không sở hữu thread."""

    @staticmethod
    def exchange(connection, address, packet):
        """Nhận socket, (IP, port), dict CHAT; trả ACK đúng ID và hai định danh.

        Timeout/OSError/ValueError được báo cho ConnectionManager xử lý.
        ACK nghĩa là ứng dụng bên kia đã tiếp nhận, chưa phải đã xem/lưu đĩa.
        """
        connection.settimeout(5)
        connection.connect(address)
        send_packet(connection, packet)
        ack = receive_packet(connection)
        if (ack["type"] != "ACK" or ack["message_id"] != packet["message_id"]
                or ack["sender"] != packet["recipient"]
                or ack["recipient"] != packet["sender"]):
            raise ValueError("ACK không khớp tin nhắn đã gửi")
        return ack
