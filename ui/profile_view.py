"""Form hồ sơ trước khi tham gia mạng LAN."""

from collections.abc import Callable
import tkinter as tk
from tkinter import ttk

from ui.styles import ACCENT, BORDER, MUTED, SURFACE, TEXT


def build_profile_form(
    root: tk.Tk, username_var: tk.StringVar, display_name_var: tk.StringVar,
    job_title_var: tk.StringVar, notice_var: tk.StringVar, on_start: Callable[[], None],
) -> ttk.Frame:
    """Dựng form bằng các biến có sẵn, gắn callback Bắt đầu và trả frame để đóng."""
    root.geometry("560x620")
    root.minsize(460, 580)
    outer_frame = ttk.Frame(root, padding=24)
    outer_frame.pack(fill="both", expand=True)
    card = tk.Frame(outer_frame, bg=SURFACE, highlightbackground=BORDER,
                    highlightthickness=1, bd=0)
    card.pack(fill="both", expand=True)
    inner = ttk.Frame(card, style="Card.TFrame", padding=(28, 24))
    inner.pack(fill="both", expand=True)
    inner.columnconfigure(0, weight=1)

    tk.Label(inner, text="LC", bg=ACCENT, fg="white", font=("Segoe UI", 16, "bold"),
             padx=10, pady=6).grid(row=0, column=0, sticky="w", pady=(0, 14))
    ttk.Label(inner, text="LAN Chat", font=("Segoe UI", 25, "bold"),
              foreground=TEXT, style="Card.TLabel").grid(row=1, column=0, sticky="w")
    ttk.Label(inner, text="Tạo hồ sơ để trò chuyện trong mạng nội bộ.",
              font=("Segoe UI", 10), foreground=MUTED, style="Card.TLabel",
              wraplength=330, justify="left").grid(row=2, column=0, sticky="w", pady=(4, 18))

    for row, label, variable in (
        (3, "Username", username_var),
        (5, "Tên hiển thị", display_name_var),
        (7, "Chức danh", job_title_var),
    ):
        ttk.Label(inner, text=label, style="Card.TLabel",
                  font=("Segoe UI", 9, "bold")).grid(row=row, column=0, sticky="w", pady=(0, 5))
        entry = ttk.Entry(inner, textvariable=variable, style="Modern.TEntry")
        entry.grid(row=row + 1, column=0, sticky="ew", pady=(0, 12))
        entry.bind("<Return>", lambda event: on_start())
        if row == 3:
            entry.focus_set()

    ttk.Button(inner, text="Bắt đầu kết nối", style="Primary.TButton",
               command=on_start).grid(row=9, column=0, sticky="ew", pady=(6, 8))
    notice_label = ttk.Label(inner, textvariable=notice_var, foreground="#ae4a45",
                              wraplength=330, justify="left", style="Card.TLabel",
                              font=("Segoe UI", 9))
    notice_label.grid(row=10, column=0, sticky="ew")
    notice_label.bind("<Configure>",
                      lambda event: notice_label.configure(wraplength=max(1, event.width)))
    return outer_frame
