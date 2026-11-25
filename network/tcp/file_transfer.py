from hashlib import sha256
import re
from pathlib import Path, PureWindowsPath
from uuid import uuid4
from config import MAX_FILE_BYTES
import os
import socket
from collections.abc import Callable
from tempfile import NamedTemporaryFile
from network.tcp.framing import recv_frame

def build_file_offer(path: Path) -> dict:
    """Đọc file tại path và trả về mã lần gửi, tên, số byte và SHA-256.

    Báo ValueError nếu đường dẫn không phải file hoặc file vượt giới hạn.
    Lỗi mở hoặc đọc file được chuyển cho nơi gọi xử lý.
    """
    if not path.is_file():
        raise ValueError("Hãy chọn một file đang tồn tại.")

    size = 0
    digest = sha256()

    with path.open("rb") as source:
        while chunk := source.read(64 * 1024):
            size += len(chunk)
            if size > MAX_FILE_BYTES:
                raise ValueError("File vượt quá dung lượng cho phép.")
            digest.update(chunk)

    return {
        "transfer_id": uuid4().hex,
        "name": path.name,
        "size": size,
        "sha256": digest.hexdigest(),
    }


def read_file_offer(packet: dict) -> dict:
    """Lấy bốn trường của lời mời đến, báo ValueError nếu metadata sai."""
    transfer_id = packet.get("transfer_id")
    name = packet.get("name")
    size = packet.get("size")
    digest = packet.get("sha256")

    if not isinstance(transfer_id, str) or not re.fullmatch(r"[0-9a-f]{32}", transfer_id):
        raise ValueError("Mã lần gửi không hợp lệ.")
    if (not isinstance(name, str) or not name.isprintable() or not name.strip()
            or name.endswith((" ", ".")) or PureWindowsPath(name).name != name
            or PureWindowsPath(name).is_reserved() or any(c in '<>:"|?*' for c in name)):
        raise ValueError("Tên file không hợp lệ.")
    if type(size) is not int or not 0 <= size <= MAX_FILE_BYTES:
        raise ValueError("Dung lượng file không hợp lệ.")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("SHA-256 không hợp lệ.")
    return {"transfer_id": transfer_id, "name": name, "size": size, "sha256": digest}


def send_file_bytes(
    connection: socket.socket,
    path: Path,
    expected_size: int,
    progress: Callable[[int], None] | None = None,
) -> int:
    """Gửi đúng số byte đã báo trong lời mời và trả số byte đã gửi.

    Báo ValueError nếu dung lượng đã đổi trước khi gửi, EOFError nếu file
    kết thúc sớm. Lỗi mở file hoặc lỗi socket được chuyển cho bên gọi.
    """
    sent = 0

    with path.open("rb") as source:
        if os.fstat(source.fileno()).st_size != expected_size:
            raise ValueError("Dung lượng file đã thay đổi từ lúc gửi lời mời.")

        while sent < expected_size:
            remaining = expected_size - sent
            chunk = source.read(min(64 * 1024, remaining))
            if not chunk:
                raise EOFError("File kết thúc trước khi đọc đủ số byte đã báo.")

            connection.sendall(chunk)
            sent += len(chunk)
            if progress:
                progress(sent)

    return sent


def receive_file_bytes(connection: socket.socket, offer: dict, directory: Path,
                       progress: Callable[[int], None]) -> Path:
    """Ghi file tạm, kiểm tra gói kết thúc và SHA-256 trước khi công bố tên tải về."""
    directory.mkdir(parents=True, exist_ok=True)
    digest = sha256()
    received = 0
    partial = NamedTemporaryFile(dir=directory, suffix=".part", delete=False)
    temp_path = Path(partial.name)
    try:
        with partial:
            while received < offer["size"]:
                chunk = connection.recv(min(65536, offer["size"] - received))
                if not chunk:
                    raise EOFError("Kết nối đóng khi đang nhận file.")
                partial.write(chunk)
                digest.update(chunk)
                received += len(chunk)
                progress(received)
        end = recv_frame(connection)
        if end != {"type": "file.end", "transfer_id": offer["transfer_id"]}:
            raise ValueError("Thiếu xác nhận kết thúc file.")
        if digest.hexdigest() != offer["sha256"]:
            raise ValueError("SHA-256 của file nhận khác lời mời.")
        original = directory / offer["name"]
        destination = original
        index = 1
        while True:
            try:
                # Công bố file hoàn chỉnh, kể cả khi hai worker cùng nhận trùng tên.
                os.link(temp_path, destination)
                return destination
            except FileExistsError:
                destination = original.with_name(f"{original.stem} ({index}){original.suffix}")
                index += 1
    finally:
        temp_path.unlink(missing_ok=True)
