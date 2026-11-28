import json
import socket
import struct


HEADER = struct.Struct("!BI")
MAX_PAYLOAD = 128 * 1024

TYPE_CODES = {
    "message": 1,
    "request": 2,
    "accept": 3,
    "decline": 4,
    "ack": 5,
    "file.offer": 6,
    "file.reply": 7,
    "file.open": 8,
    "file.end": 9,
    "file.saved": 10,
}

CODE_TYPES = {code: kind for kind, code in TYPE_CODES.items()}


def encode_frame(packet: dict) -> bytes:
    """Đóng gói bản tin thành header 5 byte và payload JSON."""
    body = packet.copy()
    kind = body.pop("type", None)

    if not isinstance(kind, str) or kind not in TYPE_CODES:
        raise ValueError(f"Loại bản tin không hợp lệ: {kind!r}")

    payload = json.dumps(
        body,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    if len(payload) > MAX_PAYLOAD:
        raise ValueError(f"Payload vượt quá {MAX_PAYLOAD} byte")

    header = HEADER.pack(TYPE_CODES[kind], len(payload))
    return header + payload

def send_frame(connection: socket.socket, packet: dict) -> None:
    """Đóng gói và gửi trọn một bản tin qua socket TCP."""
    connection.sendall(encode_frame(packet))

def recv_exact(connection: socket.socket, size: int) -> bytes:
    """Đọc đủ size byte từ socket, báo EOFError nếu kết nối đóng sớm."""
    if size < 0:
        raise ValueError("Số byte cần đọc phải từ 0 trở lên.")

    data = bytearray()
    while len(data) < size:
        chunk = connection.recv(size - len(data))
        if not chunk:
            raise EOFError(f"Kết nối đã đóng sau khi nhận {len(data)}/{size} byte.")
        data.extend(chunk)

    return bytes(data)


def recv_frame(connection: socket.socket) -> dict:
    """Đọc một frame, kiểm tra header và trả về bản tin có trường type."""
    header = recv_exact(connection, HEADER.size)
    code, size = HEADER.unpack(header)

    if code not in CODE_TYPES:
        raise ValueError(f"Mã loại bản tin không hợp lệ: {code}")
    if size > MAX_PAYLOAD:
        raise ValueError(f"Payload vượt quá {MAX_PAYLOAD} byte.")

    payload = recv_exact(connection, size)
    packet = json.loads(payload.decode("utf-8"))

    if not isinstance(packet, dict) or "type" in packet:
        raise ValueError("Payload phải là một JSON object và không được chứa 'type'.")

    packet["type"] = CODE_TYPES[code]
    return packet
