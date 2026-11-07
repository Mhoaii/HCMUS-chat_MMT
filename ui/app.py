"""Giao diện LAN Chat. Chạy: python -m ui (từ thư mục dự án)."""
from __future__ import annotations

import queue
import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from models.peer import LocalProfile

NEN = "#f3f6fb"
XANH = "#2563eb"
CHU = "#17243b"


class ChatUI(tk.Tk):
    """Mọi widget chỉ được cập nhật trên main thread.

    backend_factory(profile, emit) trả backend có start(), close(),
    set_status(status), send_message(username, text, message_id),
    send_file(username, path, transfer_id), decide_file(transfer_id, accept),
    cancel_file(transfer_id). Các hàm backend chạy tuần tự trên worker.
    emit(event, **data) là cổng nhận sự kiện an toàn từ thread mạng.
    Xem README_UI.md để biết cấu trúc sự kiện.
    """
    def __init__(self, backend_factory=None):
        super().__init__()
        self.title("LAN Chat • Không gian làm việc")
        self.geometry("1120x740")
        self.minsize(900, 620)
        self.configure(bg=NEN)
        self.backend_factory = backend_factory
        self.backend = None
        self.demo = backend_factory is None
        self.su_kien = queue.Queue()
        self.tac_vu = queue.Queue(maxsize=100)
        self.dung = threading.Event()
        self.peers = {}
        self.lich_su = {}
        self.chua_doc = {}
        self.ban_nhap = {}
        self.truyen = {}
        self.dang_chat = None
        self.protocol("WM_DELETE_WINDOW", self.dong)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=NEN)
        style.configure("TLabel", background=NEN, foreground=CHU, font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=8)
        style.configure("Accent.TButton", background=XANH, foreground="white")
        style.configure("Treeview", font=("Segoe UI", 10), rowheight=40,
                        background="white", fieldbackground="white", borderwidth=0)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        self.khung = ttk.Frame(self, padding=24)
        self.khung.pack(fill="both", expand=True)
        self.man_hinh_ho_so()
        self.after(80, self.doc_su_kien)

    def emit(self, event, **data):
        if not self.dung.is_set():
            self.su_kien.put((event, data))

    def worker(self):
        while not self.dung.is_set():
            try:
                viec = self.tac_vu.get(timeout=0.2)
            except queue.Empty:
                continue
            if viec is None:
                return
            ten, args = viec
            try:
                getattr(self.backend, ten)(*args)
            except Exception as exc:
                self.emit("error", message=str(exc))
                if ten == "send_message":
                    self.emit("ack", message_id=args[2], status="Lỗi gửi")
                elif ten == "send_file":
                    self.emit("file_progress", transfer_id=args[2],
                              status="Lỗi gửi", percent=0)

    def goi(self, ten, *args):
        if self.demo:
            return
        try:
            self.tac_vu.put_nowait((ten, args))
        except queue.Full:
            self.emit("error", message="Hàng đợi đang đầy, vui lòng thử lại.")

    def man_hinh_ho_so(self):
        hop = ttk.Frame(self.khung, padding=32)
        hop.place(relx=.5, rely=.5, anchor="center", width=470)
        ttk.Label(hop, text="LAN Chat", font=("Segoe UI", 28, "bold")).pack(anchor="w")
        ttk.Label(hop, text="Kết nối đồng nghiệp trong cùng mạng LAN").pack(anchor="w", pady=(4, 24))
        self.truong = {}
        for key, nhan, value in [("username", "Tên định danh", "hoang"),
                                  ("display_name", "Tên hiển thị", "Hoàng"),
                                  ("job_title", "Chức danh", "Nhân viên"),
                                  ("tcp_port", "Cổng TCP", "5001")]:
            ttk.Label(hop, text=nhan).pack(anchor="w", pady=(8, 4))
            var = tk.StringVar(value=value)
            ttk.Entry(hop, textvariable=var, font=("Segoe UI", 11)).pack(fill="x")
            self.truong[key] = var
        ttk.Label(hop, text="Mặc định: Away • Không yêu cầu mật khẩu").pack(anchor="w", pady=16)
        ttk.Button(hop, text="Vào bản demo" if self.demo else "Vào LAN Chat",
                   style="Accent.TButton", command=self.bat_dau).pack(fill="x")
        ttk.Label(hop, text="Dữ liệu mẫu • Chưa kết nối mạng" if self.demo else "Chế độ kết nối backend").pack(pady=(12, 0))

    def bat_dau(self):
        data = {k: v.get().strip() for k, v in self.truong.items()}
        data["username"] = re.sub(r"\s+", "_", data["username"])
        if not re.fullmatch(r"\w{1,32}", data["username"], re.UNICODE):
            messagebox.showerror("Hồ sơ chưa hợp lệ", "Tên định danh gồm 1–32 chữ, số hoặc dấu gạch dưới.")
            return
        try:
            data["tcp_port"] = int(data["tcp_port"])
            self.profile = LocalProfile(**data, status="away")
            if not self.demo:
                self.backend = self.backend_factory(self.profile, self.emit)
        except Exception as exc:
            messagebox.showerror("Không thể bắt đầu", str(exc))
            return
        for w in self.khung.winfo_children():
            w.destroy()
        self.man_hinh_chat()
        if self.demo:
            self.du_lieu_mau()
        else:
            threading.Thread(target=self.worker, daemon=True).start()
            self.goi("start")

    def man_hinh_chat(self):
        top = ttk.Frame(self.khung)
        top.pack(fill="x", pady=(0, 18))
        ttk.Label(top, text="LAN Chat", font=("Segoe UI", 22, "bold")).pack(side="left")
        ttk.Label(top, text=f"   {self.profile.job_title} | {self.profile.display_name}").pack(side="left")
        self.trang_thai = tk.StringVar(value="away")
        combo = ttk.Combobox(top, textvariable=self.trang_thai,
                             values=("online", "away"), state="readonly", width=10)
        combo.pack(side="right")
        combo.bind("<<ComboboxSelected>>", lambda e: self.doi_trang_thai())
        ttk.Label(top, text="Trạng thái của bạn  ").pack(side="right")
        self.thong_bao = tk.StringVar(value="BẢN DEMO — tin nhắn và file đều mô phỏng" if self.demo else "Đang khởi động kết nối…")
        ttk.Label(self.khung, textvariable=self.thong_bao, foreground="#975b15").pack(fill="x", pady=(0, 12))
        panes = ttk.Panedwindow(self.khung, orient="horizontal")
        panes.pack(fill="both", expand=True)
        trai = ttk.Frame(panes, padding=(0, 0, 16, 0))
        phai = ttk.Frame(panes)
        panes.add(trai, weight=1)
        panes.add(phai, weight=3)
        self.tim = tk.StringVar()
        ttk.Entry(trai, textvariable=self.tim).pack(fill="x", pady=(0, 10))
        self.tim.trace_add("write", lambda *a: self.cap_nhat_danh_sach())
        ttk.Label(trai, text="ĐANG HOẠT ĐỘNG", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=6)
        self.ds_online = self.tao_danh_sach(trai, 4)
        ttk.Label(trai, text="HỘI THOẠI GẦN ĐÂY", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(16, 6))
        self.ds_chat = self.tao_danh_sach(trai, 6)
        self.tieu_de = tk.StringVar(value="Chọn một đồng nghiệp để bắt đầu")
        ttk.Label(phai, textvariable=self.tieu_de, font=("Segoe UI", 15, "bold")).pack(anchor="w", pady=(0, 10))
        vung = ttk.Frame(phai)
        vung.pack(fill="both", expand=True)
        self.noi_dung = tk.Text(vung, wrap="word", bg="white", fg=CHU,
                               font=("Segoe UI", 11), relief="flat", padx=20, pady=16, state="disabled")
        scroll = ttk.Scrollbar(vung, command=self.noi_dung.yview)
        self.noi_dung.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.noi_dung.pack(fill="both", expand=True)
        self.noi_dung.tag_configure("gui", foreground=XANH, spacing1=12)
        self.noi_dung.tag_configure("nhan", foreground="#167255", spacing1=12)
        self.noi_dung.tag_configure("meta", foreground="#748198", font=("Segoe UI", 9))
        self.file_text = tk.StringVar(value="Chưa có lượt truyền file")
        ttk.Label(phai, textvariable=self.file_text).pack(anchor="w", pady=(12, 4))
        self.progress = ttk.Progressbar(phai, maximum=100)
        self.progress.pack(fill="x")
        self.ds_file = ttk.Combobox(phai, state="readonly")
        self.ds_file.pack(fill="x", pady=4)
        self.ds_file.bind("<<ComboboxSelected>>", lambda e: self.hien_file())
        hang = ttk.Frame(phai)
        hang.pack(fill="x", pady=(12, 0))
        self.o_nhap = tk.Text(hang, height=3, wrap="word", font=("Segoe UI", 11), relief="solid", bd=1)
        self.o_nhap.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.o_nhap.bind("<Return>", self.enter_gui)
        self.o_nhap.bind("<Shift-Return>", lambda e: None)
        nut = ttk.Frame(hang)
        nut.pack(side="right")
        ttk.Button(nut, text="Gửi tin", style="Accent.TButton", command=self.gui_tin).pack(fill="x")
        ttk.Button(nut, text="Chọn file…", command=self.gui_file).pack(fill="x", pady=3)
        ttk.Button(phai, text="Hủy lượt truyền đã chọn", command=self.huy_file).pack(anchor="e", pady=4)
        ttk.Label(phai, text="Enter để gửi • Shift+Enter xuống dòng • Away vẫn nhận được tin").pack(anchor="w")

    def tao_danh_sach(self, parent, height):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, show="tree", selectmode="browse", height=height)
        tree.column("#0", width=260, minwidth=190)
        scroll = ttk.Scrollbar(frame, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True)
        tree.bind("<<TreeviewSelect>>", lambda e: self.chon_tu_ds(tree))
        return tree

    def cap_nhat_danh_sach(self):
        query = self.tim.get().casefold()
        for tree, keys in [(self.ds_online, [u for u,p in self.peers.items() if p.get("status") in ("online", "away")]),
                           (self.ds_chat, sorted(self.lich_su, key=lambda u: self.lich_su[u][-1]["time"] if self.lich_su[u] else "", reverse=True))]:
            selected = tree.selection()
            tree.delete(*tree.get_children())
            for u in keys:
                p = self.peers.get(u, {"display_name": u, "status": "offline"})
                ten = p.get("display_name", u)
                if query not in (ten + " " + u + " " + p.get("job_title", "")).casefold():
                    continue
                count = self.chua_doc.get(u, 0)
                label = f"{ten}  • {p.get('status', 'offline')}" + (f"  ({count} mới)" if count else "")
                tree.insert("", "end", iid=u, text=label)
            if selected and tree.exists(selected[0]):
                tree.selection_set(selected[0])

    def chon_tu_ds(self, tree):
        items = tree.selection()
        if items and items[0] != self.dang_chat:
            self.chon_chat(items[0])

    def chon_chat(self, username):
        if self.dang_chat:
            self.ban_nhap[self.dang_chat] = self.o_nhap.get("1.0", "end-1c")
        self.dang_chat = username
        self.chua_doc[username] = 0
        self.lich_su.setdefault(username, [])
        self.o_nhap.delete("1.0", "end")
        self.o_nhap.insert("1.0", self.ban_nhap.get(username, ""))
        self.ve_chat()
        self.cap_nhat_danh_sach()
        self.o_nhap.focus_set()

    def ve_chat(self):
        u = self.dang_chat
        if not u:
            return
        p = self.peers.get(u, {})
        self.tieu_de.set(f"{p.get('job_title', 'Đồng nghiệp')} | {p.get('display_name', u)} • {p.get('status', 'offline')}")
        self.noi_dung.configure(state="normal")
        self.noi_dung.delete("1.0", "end")
        for m in self.lich_su.get(u, [])[-300:]:
            self.noi_dung.insert("end", ("Bạn" if m["out"] else p.get("display_name", u)) + "\n", "gui" if m["out"] else "nhan")
            self.noi_dung.insert("end", m["text"] + "\n")
            self.noi_dung.insert("end", m["time"][11:16] + " • " + m["status"] + "\n", "meta")
        self.noi_dung.configure(state="disabled")
        self.noi_dung.see("end")

    def them_tin(self, username, text, out=False, message_id=None, status="Đã nhận"):
        mid = message_id or uuid4().hex
        if any(m["id"] == mid for m in self.lich_su.get(username, [])):
            return
        self.lich_su.setdefault(username, []).append(dict(id=mid, text=text, out=out, status=status,
                                                        time=datetime.now().isoformat()))
        if not out and username != self.dang_chat:
            self.chua_doc[username] = self.chua_doc.get(username, 0) + 1
            self.thong_bao.set(f"Tin mới từ {username} • {self.chua_doc[username]} chưa đọc")
        self.cap_nhat_danh_sach()
        self.ve_chat()
        return mid

    def enter_gui(self, event):
        self.gui_tin()
        return "break"

    def cho_phep_gui(self):
        if not self.dang_chat:
            messagebox.showinfo("Chọn người nhận", "Hãy chọn một đồng nghiệp trước.")
            return False
        if self.peers.get(self.dang_chat, {}).get("status") not in ("online", "away"):
            messagebox.showinfo("Peer đã offline", "Người nhận chưa kết nối. Hãy thử lại khi họ xuất hiện trong LAN.")
            return False
        return True

    def gui_tin(self):
        text = self.o_nhap.get("1.0", "end-1c").strip()
        if not text:
            return
        if not self.cho_phep_gui():
            return
        if text in ("/online", "/away"):
            self.trang_thai.set(text[1:])
            self.doi_trang_thai()
        else:
            mid = self.them_tin(self.dang_chat, text, True, status="Demo • chưa gửi mạng" if self.demo else "Đang chờ ACK")
            if not self.demo:
                self.goi("send_message", self.dang_chat, text, mid)
        self.o_nhap.delete("1.0", "end")
        self.ban_nhap[self.dang_chat] = ""

    def doi_trang_thai(self):
        self.profile.status = self.trang_thai.get()
        self.goi("set_status", self.profile.status)

    def gui_file(self):
        if not self.cho_phep_gui():
            return
        path = filedialog.askopenfilename(title="Chọn file gửi")
        if not path:
            return
        tid = uuid4().hex
        self.truyen[tid] = dict(name=Path(path).name, percent=0,
                                status="Demo • không truyền dữ liệu" if self.demo else "Đang đề nghị")
        self.ds_file.configure(values=list(self.truyen))
        self.ds_file.set(tid)
        self.hien_file()
        if not self.demo:
            self.goi("send_file", self.dang_chat, path, tid)

    def hien_file(self):
        f = self.truyen.get(self.ds_file.get())
        if f:
            self.file_text.set(f"{f['name']} • {f['status']} • {f['percent']:.0f}%")
            self.progress["value"] = f["percent"]

    def huy_file(self):
        tid = self.ds_file.get()
        if not tid:
            return
        if self.demo:
            self.truyen[tid]["status"] = "Đã hủy demo"
            self.hien_file()
        else:
            self.goi("cancel_file", tid)

    def doc_su_kien(self):
        try:
            for _ in range(100):
                event, data = self.su_kien.get_nowait()
                try:
                    self.xu_ly(event, data)
                except Exception as exc:
                    if hasattr(self, "thong_bao"):
                        self.thong_bao.set(f"Sự kiện không hợp lệ: {exc}")
        except queue.Empty:
            pass
        if not self.dung.is_set():
            self.after(80, self.doc_su_kien)

    def xu_ly(self, event, d):
        if event == "peers":
            for p in self.peers.values():
                p["status"] = "offline"
            for p in d["peers"]:
                if p["username"] != self.profile.username:
                    self.peers[p["username"]] = dict(p)
            self.cap_nhat_danh_sach()
            self.ve_chat()
        elif event == "message":
            self.them_tin(d["username"], d["text"], message_id=d.get("message_id"))
        elif event == "ack":
            for messages in self.lich_su.values():
                for m in messages:
                    if m["id"] == d["message_id"] and m["out"]:
                        m["status"] = d.get("status", "Đã nhận ACK")
            self.ve_chat()
        elif event == "file_offer":
            tid = d["transfer_id"]
            self.truyen[tid] = dict(name=d["filename"], percent=0, status="Chờ quyết định")
            self.ds_file.configure(values=list(self.truyen))
            self.ds_file.set(tid)
            self.hien_file()
            # Hộp thoại được tạo trên UI thread; worker mạng vẫn tiếp tục chạy.
            accept = messagebox.askyesno("Đề nghị gửi file", f"{d['username']} gửi {d['filename']}\nDung lượng: {d['size']:,} byte\nBạn muốn nhận file?")
            self.truyen[tid]["status"] = "Đã đồng ý" if accept else "Đã từ chối"
            self.goi("decide_file", tid, accept)
            self.hien_file()
        elif event == "file_progress":
            f = self.truyen.setdefault(d["transfer_id"], dict(name=d.get("filename", "File"), percent=0, status="Đang truyền"))
            f["percent"] = max(0, min(100, float(d.get("percent", f["percent"]))))
            f["status"] = d.get("status", "Đang truyền")
            self.ds_file.configure(values=list(self.truyen))
            if not self.ds_file.get():
                self.ds_file.set(d["transfer_id"])
            self.hien_file()
        elif event in ("error", "notice"):
            self.thong_bao.set(d["message"])

    def du_lieu_mau(self):
        self.xu_ly("peers", {"peers": [
            dict(username="minh", display_name="Minh", job_title="Lập trình viên", status="online", ip="192.168.1.11", tcp_port=5002),
            dict(username="lan", display_name="Lan", job_title="Thiết kế", status="away", ip="192.168.1.12", tcp_port=5003),
            dict(username="quan", display_name="Quân", job_title="Trưởng nhóm", status="online", ip="192.168.1.13", tcp_port=5004)]})
        self.them_tin("minh", "Chào bạn! Đây là giao diện thử nghiệm, chưa có kết nối mạng.")
        self.them_tin("lan", "Mình có thể vừa soạn tin vừa theo dõi các cuộc trò chuyện khác.")
        self.chon_chat("minh")

    def dong(self):
        self.dung.set()
        if self.backend:
            # close phải ngắt socket/worker backend, có thể gọi đồng thời với send.
            threading.Thread(target=self.backend.close, daemon=True).start()
        self.destroy()


def main(demo=False):
    """Nhận demo (bool); chạy Tkinter với backend TCP/UDP hoặc dữ liệu mẫu; trả None."""
    from chat.chat_manager import ChatManager
    ChatUI(backend_factory=None if demo else ChatManager).mainloop()


if __name__ == "__main__":
    main()
