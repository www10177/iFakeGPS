"""
tooltip.py — Reusable hover tooltip for tkinter / customtkinter widgets.

Usage:
    from src.ui.tooltip import ToolTip, add_tooltip_button

    # Attach to any existing widget
    ToolTip(some_label, text="Explain me")

    # OR create a small ❓ label that shows the tooltip on hover
    btn = add_tooltip_button(parent_frame, text="Tooltip text here")
    btn.grid(row=0, column=2, padx=(2, 0))
"""

import tkinter as tk

import customtkinter as ctk


class ToolTip:
    """
    Displays a styled floating tooltip window when the user hovers over a widget.
    Automatically positions itself to avoid going off-screen.
    """

    _BG = "#1e2535"
    _FG = "#e2e8f0"
    _BORDER = "#4b5563"
    _FONT = ("Segoe UI", 14)
    _DELAY_MS = 0  # ms before tooltip appears
    _WRAP_PX = 300  # max width before text wraps

    def __init__(self, widget: tk.Widget, text: str):
        self._widget = widget
        self._text = text
        self._tipwindow: tk.Toplevel | None = None
        self._after_id: str | None = None

        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<ButtonPress>", self._on_leave, add="+")

    # ------------------------------------------------------------------
    def _on_enter(self, event=None):
        self._cancel()
        self._after_id = self._widget.after(self._DELAY_MS, self._show)

    def _on_leave(self, event=None):
        self._cancel()
        self._hide()

    def _cancel(self):
        if self._after_id:
            self._widget.after_cancel(self._after_id)
            self._after_id = None

    # ------------------------------------------------------------------
    def _show(self):
        if self._tipwindow or not self._text:
            return

        # Position: just below + right of the widget
        try:
            x = self._widget.winfo_rootx() + 20
            y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        except tk.TclError:
            return

        tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)  # Borderless window
        tw.wm_attributes("-topmost", True)
        tw.configure(bg=self._BORDER)

        # Outer border frame
        border_frame = tk.Frame(tw, bg=self._BORDER, padx=1, pady=1)
        border_frame.pack()

        inner = tk.Frame(border_frame, bg=self._BG, padx=10, pady=7)
        inner.pack()

        label = tk.Label(
            inner,
            text=self._text,
            justify=tk.LEFT,
            bg=self._BG,
            fg=self._FG,
            font=self._FONT,
            wraplength=self._WRAP_PX,
        )
        label.pack()

        tw.update_idletasks()

        # Keep within screen bounds
        screen_w = tw.winfo_screenwidth()
        screen_h = tw.winfo_screenheight()
        tw_w = tw.winfo_reqwidth()
        tw_h = tw.winfo_reqheight()

        if x + tw_w > screen_w - 10:
            x = screen_w - tw_w - 10
        if y + tw_h > screen_h - 10:
            y = self._widget.winfo_rooty() - tw_h - 4

        tw.wm_geometry(f"+{x}+{y}")
        self._tipwindow = tw

    def _hide(self):
        if self._tipwindow:
            self._tipwindow.destroy()
            self._tipwindow = None


# ---------------------------------------------------------------------------
# Convenience helper: creates a small ❓ icon label with an attached tooltip
# ---------------------------------------------------------------------------


def add_tooltip_button(parent: tk.Widget, text: str) -> ctk.CTkLabel:
    """
    Returns a small '?' Label widget with the tooltip attached.
    The caller is responsible for placing it (grid/pack).
    """
    icon = ctk.CTkLabel(
        parent,
        text=" ？",
        text_color="#6b7280",
        font=ctk.CTkFont(family="Segoe UI", size=10),
        cursor="question_arrow",
        width=20,
    )
    ToolTip(icon, text=text)
    return icon
