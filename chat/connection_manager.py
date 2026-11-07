"""Điều phối tác vụ gửi TCP, tách khỏi luồng điều khiển/UI."""
import socket
import threading

from network.tcp.tcp_client import TCPClient


class ConnectionManager:
    """Sở hữu tối đa 16 worker gửi; mỗi socket chỉ có một luồng đọc/ghi."""

    def __init__(self, emit):
        """Nhận callback emit(event, **data); trả None, chưa tạo kết nối."""
        self._emit = emit
        self._lock = threading.Lock()
        self._closed = False
        self._jobs = {}

    def send(self, peer, packet):
        """Nhận Peer và CHAT dict; khởi động gửi nền, trả None ngay.

        RuntimeError nếu đã đóng hoặc đạt 16 tác vụ; lỗi mạng phát qua emit.
        """
        with self._lock:
            if self._closed:
                raise RuntimeError("Bộ gửi đã đóng")
            if len(self._jobs) >= 16:
                raise RuntimeError("Đang gửi quá nhiều tin, vui lòng thử lại")
            connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            worker = threading.Thread(target=self._send, args=(connection, peer, packet),
                                      name="TCP-Send", daemon=True)
            self._jobs[worker] = connection
            worker.start()

    def _send(self, connection, peer, packet):
        """Nhận socket/Peer/CHAT; phát ack hoặc error về UI; trả None và đóng socket."""
        try:
            TCPClient.exchange(connection, (peer.ip, peer.tcp_port), packet)
            self._emit("ack", message_id=packet["message_id"], status="Đã nhận ACK")
        except (OSError, EOFError, ValueError) as error:
            self._emit("ack", message_id=packet["message_id"], status="Lỗi gửi / chưa có ACK")
            self._emit("error", message=f"Gửi tới {peer.username}: {error}")
        finally:
            connection.close()
            with self._lock:
                self._jobs.pop(threading.current_thread(), None)

    def close(self):
        """Không có đầu vào; ngắt các socket gửi và chờ worker dừng; trả None."""
        with self._lock:
            self._closed = True
            jobs = list(self._jobs.items())
        for _, connection in jobs:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()
        for worker, _ in jobs:
            worker.join(timeout=6)
