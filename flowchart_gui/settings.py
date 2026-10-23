from __future__ import annotations

import json
from typing import Optional

CONNECTION_MODES = ("窄環", "連線埠", "兩次點擊", "右鍵拖曳")
DEFAULT_CONNECTION_MODE = "窄環"
DEFAULT_LANGUAGE = "python"


class SettingsManager:
    def __init__(self, path: str):
        self.path = path
        self.connection_mode = DEFAULT_CONNECTION_MODE
        self.language = DEFAULT_LANGUAGE
        self.load()

    def load(self) -> None:
        self.connection_mode = DEFAULT_CONNECTION_MODE
        self.language = DEFAULT_LANGUAGE
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            mode = data.get("connection_mode", DEFAULT_CONNECTION_MODE)
            if mode in CONNECTION_MODES:
                self.connection_mode = mode
            lang = data.get("language", DEFAULT_LANGUAGE)
            if isinstance(lang, str) and lang.strip():
                self.language = lang.strip().lower()
        except (OSError, ValueError, TypeError):
            pass

    def save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump({"connection_mode": self.connection_mode,
                           "language": self.language}, fh,
                          ensure_ascii=False, indent=2)
        except OSError:
            pass

    def set_connection_mode(self, mode: str) -> bool:
        if mode not in CONNECTION_MODES:
            return False
        self.connection_mode = mode
        self.save()
        return True

    def set_language(self, language: str) -> bool:
        if not language or not language.strip():
            return False
        self.language = language.strip().lower()
        self.save()
        return True
