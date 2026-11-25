"""Widget cho lời mời, lịch sử và ô soạn tin của một hội thoại."""

from collections.abc import Callable
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from ui.message_history import MessageHistory


def build_conversation(frame: ttk.Frame) -> tuple[ttk.Frame, tk.StringVar]:
    """Dựng cột hội thoại và tiêu đề của người đang được chọn."""
    conversation_container = ttk.Frame(frame, padding=16)
    conversation_container.grid(row=1, column=1, sticky="nsew")
    conversation_container.columnconfigure(0, weight=1)
    conversation_container.rowconfigure(2, weight=1)

    # Tiêu đề cuộc trò chuyện hiện hành
    chat_header_card = tk.Frame(
        conversation_container,
        bg="#ffffff",
        bd=0,
        highlightbackground="#e2e8f0",
        highlightthickness=1,
    )
    chat_header_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))

    chat_header_inner = ttk.Frame(chat_header_card, style="Card.TFrame", padding=(14, 10))
    chat_header_inner.pack(fill="both", expand=True)

    chat_title_var = tk.StringVar(frame, value="Chưa chọn người để chat")
    chat_title_label = ttk.Label(
        chat_header_inner,
        textvariable=chat_title_var,
        font=("Segoe UI", 12, "bold"),
        foreground="#0f172a",
        style="Card.TLabel",
    )
    chat_title_label.pack(fill="x")
    chat_title_label.bind(
        "<Configure>",
        lambda event: chat_title_label.configure(wraplength=max(1, event.width)),
    )
    return conversation_container, chat_title_var


def build_invitation(
    conversation_container: ttk.Frame, on_invite: Callable[[], None],
    on_accept: Callable[[], None], on_decline: Callable[[], None],
) -> tuple[tk.Frame, tk.StringVar, ttk.Button, ttk.Button, ttk.Button]:
    """Dựng thẻ mời và gắn các hành động của phiên chat."""
    invitation_frame = tk.Frame(
        conversation_container,
        bg="#eff6ff",
        bd=0,
        highlightbackground="#bfdbfe",
        highlightthickness=1,
        padx=14,
        pady=10,
    )
    invitation_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))

    invitation_var = tk.StringVar(
        conversation_container, value="Chọn một người trong danh sách để bắt đầu."
    )
    invitation_label = ttk.Label(
        invitation_frame,
        textvariable=invitation_var,
        wraplength=480,
        justify="left",
        style="Invite.TLabel",
    )
    invitation_label.pack(anchor="w", fill="x")
    invitation_label.bind(
        "<Configure>",
        lambda event: invitation_label.configure(wraplength=max(1, event.width)),
    )

    actions = ttk.Frame(invitation_frame, style="InviteCard.TFrame")
    actions.pack(anchor="w", pady=(8, 0))

    invite_button = ttk.Button(
        actions,
        text="Mời trò chuyện",
        style="Primary.TButton",
        command=on_invite,
    )
    accept_button = ttk.Button(
        actions,
        text="Đồng ý",
        style="Success.TButton",
        command=on_accept,
    )
    decline_button = ttk.Button(
        actions,
        text="Từ chối",
        style="Danger.TButton",
        command=on_decline,
    )
    return invitation_frame, invitation_var, invite_button, accept_button, decline_button


def build_history(conversation_container: ttk.Frame) -> ScrolledText:
    """Tạo vùng lịch sử chỉ đọc với màu của hai người gửi."""
    history_card = tk.Frame(
        conversation_container,
        bg="#ffffff",
        bd=0,
        highlightbackground="#e2e8f0",
        highlightthickness=1,
    )
    history_card.grid(row=2, column=0, sticky="nsew")

    history_text = ScrolledText(
        history_card,
        wrap="word",
        state="disabled",
        width=40,
        height=12,
        bg="#ffffff",
        fg="#0f172a",
        bd=0,
        relief="flat",
        padx=16,
        pady=14,
        font=("Segoe UI", 10),
        spacing1=2,
        spacing3=4,
    )
    history_text.pack(fill="both", expand=True)

    # Cấu hình các thẻ hiển thị kiểu dáng bong bóng tin nhắn (Message tags)
    history_text.tag_configure(
        "user_sender",
        foreground="#4f46e5",
        font=("Segoe UI", 9, "bold"),
        spacing1=6,
    )
    history_text.tag_configure(
        "partner_sender",
        foreground="#0d9488",
        font=("Segoe UI", 9, "bold"),
        spacing1=6,
    )
    history_text.tag_configure(
        "msg_content",
        foreground="#1e293b",
        font=("Segoe UI", 10),
        spacing3=8,
    )
    return history_text


def build_composer(
    conversation_container: ttk.Frame, on_send: Callable[..., str],
) -> tuple[tk.StringVar, ttk.Entry, ttk.Button, ttk.Button]:
    """Dựng ô nhập và các nút gửi tin, chọn file."""
    composer_card = tk.Frame(
        conversation_container,
        bg="#ffffff",
        bd=0,
        highlightbackground="#e2e8f0",
        highlightthickness=1,
    )
    composer_card.grid(row=3, column=0, sticky="ew", pady=(10, 0))

    composer = ttk.Frame(composer_card, style="Card.TFrame", padding=(10, 8))
    composer.pack(fill="both", expand=True)
    composer.columnconfigure(0, weight=1)

    message_var = tk.StringVar(conversation_container)
    message_entry = ttk.Entry(
        composer,
        state="disabled",
        textvariable=message_var,
        style="Modern.TEntry",
    )
    message_entry.bind("<Return>", on_send)
    message_entry.grid(row=0, column=0, sticky="ew")

    send_button = ttk.Button(
        composer,
        text="Gửi",
        state="disabled",
        style="Primary.TButton",
        command=on_send,
    )
    send_button.grid(row=0, column=1, padx=(8, 0))

    file_button = ttk.Button(
        composer,
        text="Chọn file",
        state="disabled",
        style="Secondary.TButton",
    )
    file_button.grid(row=0, column=2, padx=(8, 0))
    return message_var, message_entry, send_button, file_button


def build_attachment(panel: ttk.Frame, on_send: Callable, on_remove: Callable):
    """Hiện tên file đã chọn và hai thao tác trước khi gửi lời mời."""
    row = ttk.Frame(panel)
    row.grid(row=4, column=0, sticky="ew", pady=(4, 0))
    row.columnconfigure(0, weight=1)
    name = tk.StringVar(panel)
    ttk.Label(row, textvariable=name, width=1).grid(row=0, column=0, sticky="ew")
    ttk.Button(row, text="Bỏ chọn", command=on_remove).grid(row=0, column=1)
    send = ttk.Button(row, text="Gửi file", command=on_send, style="Primary.TButton")
    send.grid(row=0, column=2, padx=(8, 0))
    return row, name, send


def render_history(widget: ScrolledText, history: MessageHistory, username: str | None) -> None:
    """Vẽ các tin và trạng thái xác nhận của hội thoại được chọn."""
    widget.configure(state="normal")
    widget.delete("1.0", tk.END)
    if username is not None:
        for row, (sender, text) in enumerate(history.messages.get(username, [])):
            tag = "user_sender" if sender == "Bạn" else "partner_sender"
            widget.insert(tk.END, f"{sender}:\n", tag)
            status = history.delivery_status(username, row)
            suffix = f"\n{status}" if status else ""
            widget.insert(tk.END, f"{text}{suffix}\n\n", "msg_content")
    widget.configure(state="disabled")
    widget.see(tk.END)
