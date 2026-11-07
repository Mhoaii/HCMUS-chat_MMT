import time # dùng để kiểm tra quá thời gian timeout chưa
import threading #dùng để tránh nhiều thao tác sửa cùng một lúc

from dataclasses import replace 

from config import PEER_TIMEOUT
from models.peer import Peer


class PeerRegistry:
    """Quản lý các Peer đã phát hiện, tra cứu theo username.

    Chứa dictionary username -> Peer và một Lock để bảo vệ truy cập đồng thời
    giữa listener, timeout checker và luồng giao diện.
    Quan hệ chứa/sử dụng với Peer và Lock, không kế thừa chúng.
    get/list trả bản sao để bên gọi không sửa trực tiếp dữ liệu trong registry.
    """
    def __init__(self):
        """Tạo registry rỗng và khóa bảo vệ dữ liệu dùng chung.

        Đầu vào: Không có tham số ngoài self.
        Trả về: None. Chưa tạo thread hay mở socket.
        """
        self.__peers = {} # Lưu Peer theo username, chỉ truy cập trong vùng có khóa.
        self._lock = threading.Lock() #là đối tượng khóa dùng bảo vệ việc truy cập dictionary. #cấm ai đụng vào !!!!!!!!!!!!!!!!!!

    def upsert_peer(self, message, sender_ip, now = None): #update + insert, nghĩa là chưa tồn tại thì insert còn tồn tại thì update
        """Thêm peer mới hoặc thay toàn bộ thông tin peer đã tồn tại.

        Đầu vào:
            message (dict): Gói HELLO đã được PresenceProtocol.decode kiểm tra.
            sender_ip (str): IP nguồn từ recvfrom(), không lấy từ nội dung JSON.
            now (float | None): Mốc monotonic; None dùng time.monotonic().
        Trả về: bool, True khi username mới; False khi cập nhật username cũ.
        last_seen được cập nhật cả khi peer đã tồn tại. now cho phép test không
        phải chờ thật; phải cùng hệ mốc thời gian với lần kiểm tra timeout.
        Hàm không tự giải mã hoặc kiểm tra lại các trường của message.
        """
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
        # self._lock.acquire()  # Bắt đầu khóa
        # try:
        #     is_new = username not in self.__peers
        #     self._peers[username] = peer
        # finally:
        #     self._lock.release()  # Luôn luôn mở khóa dù có lỗi xảy ra

        return is_new


    def get_peer(self, username):
        """Tìm một peer theo username trong vùng dữ liệu có khóa.

        Đầu vào: username (str), khóa cần tra cứu.
        Trả về: Peer là bản sao nếu tìm thấy; None nếu không tồn tại.
        replace() tạo bản sao nông, không biến đối tượng thành bất biến.
        """
        with self._lock: 
            peer = self.__peers.get(username)

            if peer is None: 
                return None

            return replace(peer)   #tạo một object Peer mới có cùng dữ liệu, chứ không làm object bất biến.


# ONLINE USERS
# 1. Minh   online
# 2. Huy    away
    def list_peers(self):

        """Lấy ảnh chụp danh sách peer hiện đang được lưu.

        Đầu vào: Không có tham số ngoài self.
        Trả về: list[Peer] gồm các bản sao; [] nếu registry rỗng.
        Không tự sắp xếp hay xóa peer hết hạn; timeout checker làm việc xóa.
        """
        with self._lock:
            return [
                replace(peer)
                for peer in self.__peers.values()
            ]



    #xác định timeout và xóa người dùng khỏi list online
    def remove_expired_peers(self, now = None):
        """Xóa peer đã quá lâu không nhận được presence mới.

        Đầu vào: now (float | None), mốc monotonic; None dùng thời điểm hiện tại.
        Trả về: list[Peer] là bản sao những peer vừa bị xóa; [] nếu không có.
        Điều kiện xóa: now - last_seen >= PEER_TIMEOUT (đơn vị giây).
        Duyệt bản chụp các phần tử để có thể xóa dictionary an toàn khi đang lặp.
        """
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