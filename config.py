#UDP port dùng chung cho các peer trong mạng Lan
UDP_PORT = 1717
BROADCAST_IP = "255.255.255.255"

# time giữa các lần gửi
PRESENCE_INTERVAL = 3

# Số GIÂY không nhận presence trước khi loại peer khỏi registry (không phải số lần).
PEER_TIMEOUT = 10

#Trạng thái mặc định
DEFAULT_STATUS = "away"

#g Gán cổng port tcp cho máy (dùng để test)
PORT_DEFAULT = 0  # Cổng thử nghiệm. bind(port=0) có thể xin cổng trống, nhưng LocalProfile hiện yêu cầu 1..65535.


MAX_FILE_BYTES = 100 * 1024 * 1024