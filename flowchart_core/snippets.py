from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass


PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_]\w*)\}")


@dataclass
class Snippet:
    name: str
    code: str
    category: str = "一般"


DEFAULT_SNIPPETS = [
    Snippet("列表推導式", "[x * 2 for x in iterable]", "語法糖"),
    Snippet("字典推導式", "{k: v ** 2 for k, v in data.items()}", "語法糖"),
    Snippet("上下文管理器", "with open('file.txt') as f:\n    data = f.read()", "語法糖"),
    Snippet("try/except", "try:\n    result = 1 / value\nexcept ZeroDivisionError:\n    result = 0", "結構"),
    Snippet("字串格式化", 'message = f"值為 {value}"', "常用"),
    Snippet("排序", "sorted_items = sorted(items)", "常用"),
    Snippet("計數迴圈", "for i in range(5):\n    print(i)", "結構"),
    Snippet("函式定義", "def my_func(a, b):\n    return a + b", "結構"),
]


class SnippetLibrary:
    def __init__(self):
        self.snippets: list[Snippet] = []

    @staticmethod
    def parse_placeholders(code: str) -> list[str]:
        seen = []
        for match in PLACEHOLDER_RE.finditer(code or ""):
            if match.group(1) not in seen:
                seen.append(match.group(1))
        return seen

    @staticmethod
    def render(code: str, values: dict) -> str:
        result = code or ""
        for key, value in (values or {}).items():
            result = result.replace("{" + key + "}", str(value))
        return result

    def by_name(self, name: str) -> Snippet | None:
        for snippet in self.snippets:
            if snippet.name == name:
                return snippet
        return None

    def add(self, snippet: Snippet) -> None:
        existing = self.by_name(snippet.name)
        if existing:
            existing.code = snippet.code
            existing.category = snippet.category
        else:
            self.snippets.append(snippet)

    def remove(self, name: str) -> None:
        self.snippets = [s for s in self.snippets if s.name != name]

    def categories(self) -> list[str]:
        result = []
        for snippet in self.snippets:
            if snippet.category not in result:
                result.append(snippet.category)
        return result

    def to_dict(self) -> dict:
        return {
            "snippets": [
                {"name": s.name, "code": s.code, "category": s.category}
                for s in self.snippets
            ]
        }

    def load(self, path: str) -> None:
        if not os.path.exists(path):
            self.snippets = list(DEFAULT_SNIPPETS)
            self.save(path)
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.snippets = [
                Snippet(s.get("name", ""), s.get("code", ""), s.get("category", "一般"))
                for s in data.get("snippets") or []
                if s.get("name")
            ]
        except (json.JSONDecodeError, OSError):
            self.snippets = list(DEFAULT_SNIPPETS)
            self.save(path)

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
