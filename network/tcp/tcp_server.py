"""TCP listener đa luồng, mỗi kết nối nhận một CHAT và trả một ACK."""
import logging
import socket
import threading

from network.tcp.protocol import receive_packet, send_packet

logger = logging.getLogger(__name__)


class TCPServer:
    """Sở hữu socket lắng nghe và các worker; dùng callback, không kế thừa Thread."""

    def __init__(self, profile, on_message, host="0.0.0.0"):
        """Nhận LocalProfile, callback(dict)->None và IP bind; trả None.

        Chưa mở socket. Callback phải tiếp nhận tin xong trước khi server gửi ACK.
        """
        self.profile = profile
        self.on_message = on_message
        self.host = host
        self._socket = None
        self._thread = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._clients = set()
        self._workers = set()

    def start(self):
        """Không nhận tham số; bind/listen rồi chạy accept thread, trả None.

        OSError khi cổng bận được báo ngay cho bên gọi; không quảng bá cổng lỗi.
        """
        if self._thread and self._thread.is_alive():
            return
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            listener.bind((self.host, self.profile.tcp_port))
            listener.listen(32)
            listener.settimeout(0.2)
        except OSError:
            listener.close()
            raise
        self._socket = listener
        self._stop.clear()
        self._thread = threading.Thread(target=self._accept, name="TCP-Accept", daemon=True)
        self._thread.start()

    def _accept(self):
        """Không có đầu vào; nhận kết nối nền, giới hạn 32 worker; trả None khi dừng."""
        while not self._stop.is_set():
            try:
                connection, _ = self._socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            with self._lock:
                if self._stop.is_set() or len(self._clients) >= 32:
                    connection.close()
                    continue
                self._clients.add(connection)
                worker = threading.Thread(target=self._serve, args=(connection,),
                                          name="TCP-Receive", daemon=True)
                self._workers.add(worker)
                worker.start()

    def _serve(self, connection):
        """Nhận socket đã accept; đọc CHAT, gọi callback, trả ACK; trả None và đóng socket."""
        try:
            connection.settimeout(5)
            packet = receive_packet(connection)
            if packet["type"] != "CHAT" or packet["recipient"] != self.profile.username:
                raise ValueError("Tin nhắn không gửi tới peer này")
            self.on_message(packet)
            send_packet(connection, {
                "type": "ACK", "message_id": packet["message_id"],
                "sender": self.profile.username, "recipient": packet["sender"],
            })
        except (OSError, EOFError, ValueError) as error:
            if not self._stop.is_set():
                logger.debug("Bỏ kết nối TCP: %s", error)
        except Exception:
            logger.exception("Không tiếp nhận được tin nhắn; không gửi ACK")
        finally:
            connection.close()
            with self._lock:
                self._clients.discard(connection)
                self._workers.discard(threading.current_thread())

    def stop(self):
        """Không có đầu vào; ngắt listener/client và chờ worker dừng; trả None."""
        self._stop.set()
        if self._socket:
            self._socket.close()
        if self._thread:
            self._thread.join(timeout=2)
        with self._lock:
            clients, workers = list(self._clients), list(self._workers)
        for connection in clients:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()
        for worker in workers:
            worker.join(timeout=1)
