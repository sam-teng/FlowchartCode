from __future__ import annotations

import json
import os
from typing import Callable, Optional


DEFAULT_SHORTCUTS = {
    "new": "<Control-n>",
    "open": "<Control-o>",
    "save": "<Control-s>",
    "undo": "<Control-z>",
    "redo": "<Control-y>",
    "generate": "<Control-g>",
    "run": "<F5>",
    "preview": "<Control-F5>",
    "stop": "<Escape>",
    "delete": "<Delete>",
    "autocomplete": "<Control-space>",
    "doc_lookup": "<Control-k>",
    "pip_search": "<Control-p>",
    "help": "<F1>",
}

ACTION_LABELS = {
    "new": "新增專案",
    "open": "載入流程圖",
    "save": "儲存流程圖",
    "undo": "復原",
    "redo": "重做",
    "generate": "產生程式碼",
    "run": "執行程式碼（動畫）",
    "preview": "快速預覽",
    "stop": "停止執行",
    "delete": "刪除選取",
    "autocomplete": "自動補全",
    "doc_lookup": "函式說明查詢",
    "pip_search": "pip 套件搜尋",
    "help": "使用說明",
}


def display_name(sequence: str) -> str:
    text = sequence or ""
    text = text.replace("<Control-", "Ctrl+").replace("<Shift-", "Shift+")
    text = text.replace("<Alt-", "Alt+").replace("<", "").replace(">", "")
    text = text.replace("space", "Space").replace("F5", "F5").replace("F1", "F1")
    return text


class ShortcutManager:
    def __init__(self, path: str):
        self.path = path
        self.bindings: dict[str, str] = dict(DEFAULT_SHORTCUTS)
        self.load()

    def load(self) -> None:
        self.bindings = dict(DEFAULT_SHORTCUTS)
        if not os.path.exists(self.path):
            self.save()
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for action, seq in (data.get("shortcuts") or {}).items():
                if action in DEFAULT_SHORTCUTS and isinstance(seq, str) and seq:
                    self.bindings[action] = seq
        except (json.JSONDecodeError, OSError):
            self.bindings = dict(DEFAULT_SHORTCUTS)
            self.save()

    def save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"shortcuts": self.bindings}, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def get(self, action: str) -> str:
        return self.bindings.get(action, DEFAULT_SHORTCUTS.get(action, ""))

    def set(self, action: str, sequence: str) -> Optional[str]:
        if action not in DEFAULT_SHORTCUTS:
            return f"未知動作：{action}"
        if sequence:
            for other, existing in self.bindings.items():
                if other != action and existing == sequence:
                    return f"{sequence} 已綁定到「{ACTION_LABELS.get(other, other)}」"
        self.bindings[action] = sequence
        self.save()
        return None

    def reset(self) -> None:
        self.bindings = dict(DEFAULT_SHORTCUTS)
        self.save()

    def bind_all(self, widget, handlers: dict[str, Callable]) -> None:
        for action, handler in handlers.items():
            seq = self.get(action)
            if not seq:
                continue
            def make_wrapper(h):
                def wrapper(event=None):
                    try:
                        h()
                    except Exception:
                        pass
                    return "break"
                return wrapper
            try:
                widget.bind_all(seq, make_wrapper(handler))
            except Exception:
                pass

    def unbind_all(self, widget) -> None:
        for action in self.bindings:
            seq = self.get(action)
            if seq:
                try:
                    widget.unbind_all(seq)
                except Exception:
                    pass
