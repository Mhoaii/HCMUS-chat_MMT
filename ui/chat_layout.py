"""Khung chính, thanh hồ sơ và thông báo của màn hình chat."""

from collections.abc import Callable
import tkinter as tk
from tkinter import ttk


def build_header(
    frame: ttk.Frame, *, username: str, display_name: str, job_title: str, status: str,
    notifications_var: tk.BooleanVar, on_status_changed: Callable[[tk.Event], None],
    on_notifications_toggled: Callable[[], None],
) -> tuple[tk.StringVar, ttk.Combobox, ttk.Checkbutton]:
    """Hiển thị danh tính và chuyển thao tác đổi trạng thái qua callback."""
    header_container = tk.Frame(
        frame,
        bg="#ffffff",
        bd=0,
        highlightbackground="#dce6df",
        highlightthickness=1,
    )
    header_container.grid(
        row=0, column=0, columnspan=2, sticky="ew"
    )

    header = ttk.Frame(header_container, style="Header.TFrame", padding=(16, 10))
    header.pack(fill="both", expand=True)

    # Thông tin danh tính cá nhân bên trái
    user_badge = ttk.Frame(header, style="Header.TFrame")
    header.columnconfigure(0, weight=1)
    user_badge.grid(row=0, column=0, sticky="ew", padx=(0, 16))
    user_badge.columnconfigure(1, weight=1)

    avatar_lbl = tk.Label(
        user_badge,
        text=(display_name.strip() or username.strip() or "?")[0].upper(),
        font=("Segoe UI", 18, "bold"),
        bg="#dceee4",
        fg="#16796b",
        padx=14,
        pady=8,
    )
    avatar_lbl.grid(row=0, column=0, padx=(0, 10))

    user_text_frame = ttk.Frame(user_badge, style="Header.TFrame")
    user_text_frame.grid(row=0, column=1, sticky="ew")

    ttk.Label(
        user_text_frame,
        text=f"{display_name}",
        font=("Segoe UI", 12, "bold"),
        style="Card.TLabel",
    ).pack(anchor="w", fill="x")

    ttk.Label(
        user_text_frame,
        text=f"@{username} · {job_title}",
        font=("Segoe UI", 9),
        foreground="#647970",
        style="Card.TLabel",
    ).pack(anchor="w", fill="x")

    # Cụm điều khiển bên phải: Trạng thái & Thông báo
    controls_frame = ttk.Frame(header, style="Header.TFrame")
    controls_frame.grid(row=0, column=1, sticky="e")

    status_var = tk.StringVar(frame, value=status)

    status_box = ttk.Combobox(
        controls_frame,
        textvariable=status_var,
        values=("online", "away"),
        state="readonly",
        width=8,
    )
    status_box.pack(side="right")
    status_box.bind("<<ComboboxSelected>>", on_status_changed)

    ttk.Label(
        controls_frame,
        text="Trạng thái:",
        font=("Segoe UI", 9, "bold"),
        style="Card.TLabel",
    ).pack(side="right", padx=(0, 8))

    notifications_toggle = ttk.Checkbutton(
        controls_frame,
        text="Hiện thông báo",
        variable=notifications_var,
        command=on_notifications_toggled,
    )
    notifications_toggle.pack(side="right", padx=(0, 20))
    return status_var, status_box, notifications_toggle


def build_footer(frame: ttk.Frame) -> tk.StringVar:
    """Tạo thanh thông báo và trả biến điều khiển nội dung."""
    footer = tk.Frame(
        frame,
        bg="#f3f6f4",
        bd=0,
        highlightbackground="#dce6df",
        highlightthickness=1,
        padx=14,
        pady=6,
    )
    footer.grid(
        row=2, column=0, columnspan=2, sticky="ew", pady=(0, 0)
    )

    connection_notice_var = tk.StringVar(frame, value="Chưa kết nối mạng.")
    connection_notice_label = ttk.Label(
        footer,
        textvariable=connection_notice_var,
        wraplength=800,
        justify="left",
        style="Notice.TLabel",
    )
    connection_notice_label.pack(fill="x")
    connection_notice_label.bind(
        "<Configure>",
        lambda event: connection_notice_label.configure(wraplength=max(1, event.width)),
    )
    return connection_notice_var
