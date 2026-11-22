import time # dùng để kiểm tra quá thời gian timeout chưa
import threading #dùng để tránh nhiều thao tác sửa cùng một lúc

from dataclasses import replace 

from config import PEER_TIMEOUT
from models.peer import Peer


class PeerRegistry:
    """Quản lý peer theo username bằng Lock; các hàm tra cứu trả bản sao."""
    def __init__(self):
        """Tạo dictionary peer rỗng và khóa bảo vệ truy cập đa luồng."""
        self.__peers = {} # Lưu Peer theo username, chỉ truy cập trong vùng có khóa.
        self._lock = threading.Lock() # Bảo vệ dictionary khi nhiều thread truy cập.

    def upsert_peer(self, message, sender_ip, now = None):
        """Thêm/cập nhật peer từ HELLO đã kiểm tra và IP nguồn; trả True nếu mới.
        now là mốc monotonic, mặc định lấy thời điểm hiện tại."""
        if now is None:
            now = time.monotonic() # get time now

        username = message["username"]

        peer = Peer(
            username= username, 
            display_name= message["display_name"],
            job_title=message["job_title"],
            ip=sender_ip,
            tcp_port=message["tcp_port"],
            status=message["status"],
            last_seen=now
            )
        with self._lock: 
            is_new = username not in self.__peers
            self.__peers[username] = peer

        return is_new


    def get_peer(self, username):
        """Trả bản sao Peer theo username, hoặc None nếu không tìm thấy."""
        with self._lock: 
            peer = self.__peers.get(username)

            if peer is None: 
                return None

            return replace(peer)   # Trả bản sao để tránh sửa dữ liệu nội bộ.


    def list_peers(self):

        """Trả danh sách bản sao các peer hiện có; chưa có thì trả []."""
        with self._lock:
            return [
                replace(peer)
                for peer in self.__peers.values()
            ]



    #xác định timeout và xóa người dùng khỏi list online
    def remove_expired_peers(self, now = None):
        """Xóa và trả các peer vắng ít nhất PEER_TIMEOUT giây.
        now là mốc monotonic, mặc định lấy thời điểm hiện tại."""
        if now is None:
            now = time.monotonic()

        expired_peers = []

        with self._lock:
            for username, peer in list(self.__peers.items()):
                elapsed = now - peer.last_seen

                if elapsed >= PEER_TIMEOUT:
                    expired_peers.append(replace(peer))
                    del self.__peers[username]

        return expired_peers