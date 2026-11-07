# Giao diện LAN Chat

Chạy từ thư mục dự án bằng `python -m ui`. Chỉ dùng thư viện chuẩn Python và Tkinter.
Mặc định đã nối ChatManager để chat text thật qua UDP/TCP. Dùng `python -m ui --demo`
để mở dữ liệu mẫu cũ. Chi tiết giao thức, giới hạn và lệnh console: `../TCP_CHAT.md`.
Truyền file thật chưa được triển khai; các nút file sẽ thông báo chưa hỗ trợ.

Có nhập hồ sơ (không mật khẩu), online/away (mặc định away), tìm kiếm peer,
cuộc trò chuyện riêng, bộ đếm chưa đọc, bản nháp riêng từng người, Enter gửi,
Shift+Enter xuống dòng, chọn file, nhận/từ chối file, tiến độ và hủy qua backend.
Away vẫn là peer có thể liên lạc. Offline bị chặn gửi trực tiếp.
Tin gửi hiện trạng thái chờ ACK; chỉ sự kiện ACK thật mới đổi trạng thái.
Bản demo luôn ghi rõ chưa gửi qua mạng và không mô phỏng ACK thành công.
Lịch sử và bản nháp hiện chỉ lưu RAM, mất khi đóng ứng dụng. Chưa có SQLite.
Khung chat hiển thị 300 tin gần nhất; danh sách dùng Treeview có thanh cuộn,
chưa có pool tái sử dụng dòng/ảo hóa riêng cho danh sách rất lớn.

## Ghép phần mạng

Khởi tạo `ChatUI(backend_factory=TaoBackend).mainloop()` từ entry point tích hợp.
Factory nhận `(profile: LocalProfile, emit)` và trả backend.
UI gọi các hàm sau trên worker điều khiển, theo thứ tự:

- start(): khởi động discovery/TCP; emit snapshot peer định kỳ.
- set_status(status): cập nhật discovery.
- send_message(username, text, message_id): gửi qua TCP, KHÔNG tự báo ACK thành công.
- send_file(username, path, transfer_id): đề nghị gửi rồi chuyển tác vụ truyền sang worker riêng.
- decide_file(transfer_id, accept): xử lý quyết định nhận file.
- cancel_file(transfer_id): yêu cầu hủy.
- close(): ngắt socket và worker; được gọi từ thread riêng khi đóng cửa sổ,
  cần thread-safe kể cả khi start/send đang chạy. Các worker backend nên có shutdown hữu hạn.

Các hàm điều khiển phải trả về nhanh: tránh chờ ACK hoặc truyền toàn bộ file trong
hàm send_file vì sẽ giữ hàng đợi điều khiển. Backend phải tự điều phối worker mạng.
Không thao tác Tkinter từ thread mạng. Dùng `emit` an toàn qua queue:

```python
from dataclasses import asdict
emit("peers", peers=[asdict(p) for p in discovery.list_peers()])
emit("message", username="minh", text="Xin chào", message_id="msg-1")
emit("ack", message_id="outgoing-id", status="Đã nhận ACK")
emit("ack", message_id="outgoing-id", status="Hết thời gian chờ ACK")
emit("file_offer", username="minh", transfer_id="f-1", filename="a.pdf", size=1024)
emit("file_progress", transfer_id="f-1", percent=50, status="Đang nhận")
emit("file_progress", transfer_id="f-1", percent=100, status="Đã kiểm tra SHA-256")
emit("error", message="Kết nối bị ngắt")
emit("notice", message="Đã kết nối LAN")
```

Snapshot `peers` là danh sách đầy đủ hiện tại, không phải một peer cập nhật lẻ.
Peer vắng khỏi snapshot chuyển offline, hội thoại vẫn giữ lại.
Backend chịu trách nhiệm timeout ACK, chống giả ACK, nhận/gửi file thật,
kiểm tra size/hash, làm sạch đường dẫn, .part, giới hạn tài nguyên và đóng kết nối.
UI không được dùng trạng thái tiến độ 100% để tự khẳng định hash hợp lệ.

## Thử thủ công

1. Nhập hồ sơ sai cổng/rỗng tên: phải báo lỗi.
2. Chọn Minh, gõ bản nháp rồi chuyển Lan và quay lại: bản nháp giữ nguyên.
3. Gửi Unicode/emoji; Shift+Enter tạo dòng mới, Enter gửi; demo không báo ACK thật.
4. Tìm tên/chức danh; mở hội thoại Lan để xóa số chưa đọc.
5. Chọn file, kiểm tra ghi rõ không truyền thật ở demo; hủy lượt đã chọn.
6. Khi ghép backend, phát sự kiện từ thread nền khi đang gõ: không mất bản nháp.
7. Peer offline vẫn có hội thoại nhưng không gửi tin/file được.
