"""Kiểm tra bố cục bằng widget Tk thật, không khởi động dịch vụ mạng."""

import tkinter as tk
import unittest
from tkinter import ttk
from unittest.mock import Mock

from models.peer import LocalProfile, Peer
from ui.app import ChatWindow


class ChatLayoutTests(unittest.TestCase):
    """Xác nhận nội dung vẫn truy cập được khi thu nhỏ và làm mới danh sách."""

    def setUp(self) -> None:
        """Không nhận tham số; tạo cửa sổ và thu lỗi callback để kiểm tra cuối test."""
        self.app = ChatWindow()
        self.errors = []
        self.app.root.report_callback_exception = lambda *args: self.errors.append(args)

    def tearDown(self) -> None:
        """Không nhận tham số; đóng cửa sổ, xác nhận callback không lỗi; trả None."""
        self.app._on_close()
        self.assertEqual(self.errors, [])

    def assert_visible(self, widget: tk.Widget) -> None:
        """Nhận widget Tk; kiểm tra widget nằm trọn trong các khung cha; trả None."""
        self.assertTrue(widget.winfo_ismapped(), str(widget))
        child = widget
        while child.master is not None:
            parent = child.master
            self.assertGreaterEqual(child.winfo_x(), 0, str(child))
            self.assertGreaterEqual(child.winfo_y(), 0, str(child))
            self.assertLessEqual(
                child.winfo_x() + child.winfo_width(), parent.winfo_width(), str(child),
            )
            self.assertLessEqual(
                child.winfo_y() + child.winfo_height(), parent.winfo_height(), str(child),
            )
            child = parent

    def build_chat(self) -> None:
        """Không nhận tham số; dựng chat ở kích thước nhỏ nhất, không mở socket; trả None."""
        app = self.app
        app.profile = LocalProfile("local", app.display_name or "Local", "SV", 9999)
        app.profile_frame.destroy()
        app._build_chat_view()
        width, height = app.root.minsize()
        app.root.geometry(f"{width}x{height}")
        app.root.update()

    def test_profile_validation_at_minimum_size(self) -> None:
        """Không nhận tham số; nút bắt đầu và báo lỗi rỗng tên đều hiện đủ; trả None."""
        app = self.app
        width, height = app.root.minsize()
        app.root.geometry(f"{width}x{height}")
        app._on_start()
        app.root.update()
        self.assertTrue(app.notice_var.get())
        card = app.profile_frame.winfo_children()[0].winfo_children()[0]
        for widget in card.winfo_children():
            self.assert_visible(widget)

    def test_long_identity_does_not_hide_status_controls(self) -> None:
        """Không nhận tham số; tên dài vẫn chừa đủ chỗ cho trạng thái, checkbox; trả None."""
        app = self.app
        app.display_name = "Tên người dùng dài " * 12
        app.username = "username_rat_dai_" * 12
        app.job_title = "Chức danh rất dài " * 12
        self.build_chat()
        for widget in (app.status_box, app.notifications_toggle, app.send_button):
            self.assert_visible(widget)
            self.assertEqual(widget.winfo_width(), widget.winfo_reqwidth())

    def test_long_chat_labels_wrap_at_minimum_size(self) -> None:
        """Không nhận tham số; tên, lời mời, thông báo dài hiện đủ mà vẫn còn ô chat; trả None."""
        self.build_chat()
        app = self.app
        app._remember_chat_peer("peer", {"display_name": "Tên hiển thị của người dùng " * 3})
        app._chat_states["peer"] = "incoming"
        app._show_conversation("peer")
        app.connection_notice_var.set("Người dùng vừa xuất hiện trong mạng nội bộ. " * 3)
        app.root.update()
        for widget in (app.accept_button, app.decline_button, app.message_entry):
            self.assert_visible(widget)
        self.assertGreater(app.history_text.winfo_height(), 40)
        variables = {str(app.chat_title_var), str(app.invitation_var), str(app.connection_notice_var)}
        pending = [app.root]
        found = 0
        while pending:
            widget = pending.pop()
            pending.extend(widget.winfo_children())
            if isinstance(widget, ttk.Label) and str(widget.cget("textvariable")) in variables:
                found += 1
                self.assert_visible(widget)
                self.assertEqual(widget.winfo_height(), widget.winfo_reqheight())
                self.assertLessEqual(int(widget.cget("wraplength")), widget.winfo_width())
        self.assertEqual(found, 3)

    def test_refresh_preserves_list_scroll_and_keyboard_selection(self) -> None:
        """Không nhận tham số; reload không nhảy cuộn hoặc làm phím xuống chọn sai; trả None."""
        self.build_chat()
        app = self.app
        peers = [
            Peer(f"peer{i:02}", f"Tên dài của người dùng {i} " * 4, "SV", "127.0.0.1", "online", 0, 9999)
            for i in range(80)
        ]
        app.discovery = Mock()
        app.discovery.list_peers.return_value = peers
        app._refresh_online_peers(schedule_next=False)
        app._conversation_order = list(app._peer_order)
        app._refresh_conversation_list()
        app.root.update()
        for widget in (app.peer_list, app.conversation_list):
            widget.selection_set(42)
            widget.activate(42)
            widget.selection_anchor(42)
            widget.yview_moveto(0.5)
            widget.xview_moveto(0.2)
        app.root.update()
        views = [(w.yview(), w.xview()) for w in (app.peer_list, app.conversation_list)]
        app.reload_peers_button.invoke()
        app.root.update()
        for widget, (vertical, horizontal) in zip((app.peer_list, app.conversation_list), views):
            self.assertEqual(widget.curselection(), (42,))
            self.assertEqual(widget.index(tk.ACTIVE), 42)
            self.assertEqual(widget.yview(), vertical)
            self.assertEqual(widget.xview(), horizontal)
            self.assertLess(horizontal[1] - horizontal[0], 1)
            scrollbars = [w for w in widget.master.winfo_children() if isinstance(w, ttk.Scrollbar)]
            self.assertEqual(len(scrollbars), 2)
            for scrollbar in scrollbars:
                self.assert_visible(scrollbar)
        app.conversation_list.focus_force()
        app.root.update()
        app.conversation_list.event_generate("<Down>")
        app.root.update()
        self.assertEqual(app.conversation_list.curselection(), (43,))
        self.assertEqual(app.current_chat, "peer43")


if __name__ == "__main__":
    unittest.main()
