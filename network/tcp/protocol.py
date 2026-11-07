"""Giao thức chat: 4 byte độ dài big-endian + JSON UTF-8 (không dùng newline).

Tham khảo luồng socket/thread của Mhoaii/HCMUS-chat_MMT, tcp_chat.py,
commit 2c711c8e7e58f8dee7a3896d529e0ed5f6de5382. Wire format đã thay đổi.
"""
import json
import struct

MAX_PACKET_SIZE = 1024 * 1024


def recv_exact(connection, size):
    """Nhận socket và số byte cần đọc; trả bytes đủ size hoặc báo EOFError.

    TCP có thể chia một gói thành nhiều lần recv(), nên phải đọc lặp.
    """
    parts = bytearray()
    while len(parts) < size:
        chunk = connection.recv(size - len(parts))
        if not chunk:
            raise EOFError("Peer đã đóng kết nối trước khi nhận đủ dữ liệu")
        parts.extend(chunk)
    return bytes(parts)


def validate_packet(packet):
    """Nhận đối tượng JSON; trả dict CHAT/ACK hợp lệ, lỗi thì ValueError.

    sender/recipient là định danh tự khai trong LAN, chưa có xác thực.
    """
    if not isinstance(packet, dict) or packet.get("type") not in ("CHAT", "ACK"):
        raise ValueError("Loại packet TCP không hợp lệ")
    for field in ("message_id", "sender", "recipient"):
        value = packet.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > 128:
            raise ValueError(f"Trường {field} không hợp lệ")
    if packet["type"] == "CHAT":
        text = packet.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Nội dung tin nhắn không được rỗng")
    return packet


def encode_packet(packet):
    """Nhận dict hợp lệ; trả bytes gồm header 4 byte và payload JSON UTF-8."""
    validate_packet(packet)
    payload = json.dumps(packet, ensure_ascii=False).encode("utf-8")
    if len(payload) > MAX_PACKET_SIZE:
        raise ValueError("Packet vượt giới hạn 1 MiB")
    return struct.pack("!I", len(payload)) + payload


def send_packet(connection, packet):
    """Nhận socket và dict; sendall toàn bộ frame, trả None; lỗi socket được báo ra."""
    connection.sendall(encode_packet(packet))


def receive_packet(connection):
    """Nhận socket; trả dict đã kiểm tra; lỗi frame/JSON/UTF-8 thì ValueError.

    Giới hạn độ dài trước khi đọc payload để tránh cấp phát theo header tùy ý.
    Socket timeout và EOFError được truyền ra cho worker đóng kết nối.
    """
    size = struct.unpack("!I", recv_exact(connection, 4))[0]
    if not 1 <= size <= MAX_PACKET_SIZE:
        raise ValueError("Độ dài packet không hợp lệ")
    try:
        packet = json.loads(recv_exact(connection, size).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError("Payload phải là JSON UTF-8 hợp lệ") from error
    return validate_packet(packet)
