from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from flowchart_core import CompletionProvider

IDENTIFIER_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.")


class CompletionPopup:
    def __init__(self, text_widget, provider: CompletionProvider,
                 on_describe: Optional[Callable] = None):
        self.text = text_widget
        self.provider = provider
        self.on_describe = on_describe
        self._window: Optional[tk.Toplevel] = None
        self._listbox: Optional[tk.Listbox] = None
        self._preview: Optional[tk.Label] = None
        self._items = []
        self._after_id = None
        self._attached = False
        self.attach()

    def attach(self) -> None:
        if self._attached:
            return
        self._attached = True
        self.text.bind("<Control-space>", self._on_manual, add="+")
        self.text.bind("<Key>", self._on_key, add="+")

    def detach(self) -> None:
        self._attached = False
        try:
            self.text.unbind("<Control-space>")
            self.text.unbind("<Key>")
        except Exception:
            pass
        self.close()

    def _on_manual(self, event=None):
        self._show()
        return "break"

    def _on_key(self, event) -> None:
        if event.keysym in ("Control_L", "Control_R", "Shift_L", "Shift_R",
                            "Alt_L", "Alt_R"):
            return
        if event.char and event.char in IDENTIFIER_CHARS:
            if self._after_id is not None:
                try:
                    self.text.after_cancel(self._after_id)
                except Exception:
                    pass
            self._after_id = self.text.after(300, self._show)
        elif event.keysym not in ("Down", "Up", "Return", "Tab", "Escape"):
            self.close()

    def _text_before_cursor(self) -> str:
        try:
            return self.text.get("1.0", "insert")
        except tk.TclError:
            return ""

    def _show(self) -> None:
        self._after_id = None
        before = self._text_before_cursor()
        items = self.provider.complete(before)
        self._items = items
        if not items:
            self.close()
            return
        self._build_window()
        self._listbox.delete(0, tk.END)
        for item in items:
            suffix = {"var": "變數", "func": "函式", "module": "模組",
                      "builtin": "內建", "class": "類別", "member": "成員",
                      "snippet": "片段"}.get(item.kind, "")
            self._listbox.insert(tk.END, f"{item.label}  [{suffix}]")
        self._listbox.selection_clear(0, tk.END)
        self._listbox.selection_set(0)
        self._listbox.activate(0)
        self._update_preview()
        self._position()

    def _build_window(self) -> None:
        if self._window is not None:
            return
        self._window = tk.Toplevel(self.text.winfo_toplevel())
        self._window.wm_overrideredirect(True)
        self._window.attributes("-topmost", True)
        frame = tk.Frame(self._window, bd=1, relief=tk.SOLID, bg="white")
        frame.pack(fill=tk.BOTH, expand=True)
        self._listbox = tk.Listbox(frame, height=8, width=36, font=("Consolas", 10))
        self._listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = tk.Scrollbar(frame, command=self._listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._listbox.config(yscrollcommand=scrollbar.set)
        self._preview = tk.Label(
            frame, text="", width=42, justify=tk.LEFT, anchor="nw",
            bg="#f5f5f5", wraplength=300, font=("Arial", 9),
        )
        self._preview.pack(side=tk.RIGHT, fill=tk.BOTH, padx=2, pady=2)
        self._listbox.bind("<<ListboxSelect>>", lambda e: self._update_preview())
        self._listbox.bind("<Double-Button-1>", lambda e: self._apply())
        self._listbox.bind("<Return>", lambda e: self._apply())
        self._listbox.bind("<Tab>", lambda e: self._apply())
        self._listbox.bind("<Escape>", lambda e: self.close())
        self._listbox.bind("<Up>", self._move(-1))
        self._listbox.bind("<Down>", self._move(1))
        self._window.bind("<Focus-Out>", lambda e: self.close())
        self._window.bind("<Escape>", lambda e: self.close())

    def _move(self, delta: int):
        def handler(event=None):
            if not self._listbox:
                return
            count = self._listbox.size()
            if not count:
                return
            current = self._listbox.curselection()
            index = (current[0] if current else 0) + delta
            index = max(0, min(count - 1, index))
            self._listbox.selection_clear(0, tk.END)
            self._listbox.selection_set(index)
            self._listbox.activate(index)
            self._listbox.see(index)
            self._update_preview()
            return "break"
        return handler

    def _update_preview(self, *args) -> None:
        if not self._listbox or not self._preview:
            return
        selection = self._listbox.curselection()
        if not selection or selection[0] >= len(self._items):
            self._preview.config(text="")
            return
        item = self._items[selection[0]]
        signature, doc = self.provider.describe(item)
        text = f"{signature}\n\n{doc[:300]}" if doc else str(signature)
        self._preview.config(text=text)

    def _position(self) -> None:
        try:
            bbox = self.text.bbox("insert")
        except tk.TclError:
            bbox = None
        if not bbox:
            self._window.withdraw()
            return
        x = self.text.winfo_rootx() + bbox[0]
        y = self.text.winfo_rooty() + bbox[3] + 2
        self._window.geometry(f"+{x}+{y}")
        self._window.deiconify()
        self._window.lift()
        self._listbox.focus_set()

    def _apply(self, event=None) -> None:
        selection = self._listbox.curselection() if self._listbox else ()
        if not selection or selection[0] >= len(self._items):
            self.close()
            return
        item = self._items[selection[0]]
        before = self._text_before_cursor()
        token = ""
        for ch in reversed(before):
            if ch in IDENTIFIER_CHARS:
                token = ch + token
            else:
                break
        try:
            self.text.delete("insert - %d chars" % len(token), "insert")
            self.text.insert("insert", item.insert)
        except tk.TclError:
            pass
        self.close()

    def close(self) -> None:
        if self._window is not None:
            try:
                self._window.destroy()
            except tk.TclError:
                pass
            self._window = None
            self._listbox = None
            self._preview = None
