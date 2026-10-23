from __future__ import annotations

import builtins
import re
from dataclasses import dataclass, field
from typing import Optional

from .module_inspector import get_callable_info, list_module_callables
from .policy import CodePolicy
from .symbols import SymbolTable


@dataclass
class CompletionItem:
    label: str
    insert: str
    kind: str
    detail: str = ""
    doc: str = ""


_TOKEN_RE = re.compile(r"([A-Za-z_][\w\.]*)$")
_MEMBER_SPLIT = re.compile(r"^([A-Za-z_][\w]*)\.([\w\.]*)$")


class CompletionProvider:
    def __init__(self, symbols: SymbolTable, policy: Optional[CodePolicy] = None,
                 snippets_provider=None):
        self.symbols = symbols
        self.policy = policy or CodePolicy.standard()
        self.snippets_provider = snippets_provider
        self._builtin_names = sorted(
            n for n in dir(builtins)
            if not n.startswith("_") and self.policy.check_name(n)[0]
        )

    def refresh_policy(self, policy: CodePolicy) -> None:
        self.policy = policy
        self._builtin_names = sorted(
            n for n in dir(builtins)
            if not n.startswith("_") and policy.check_name(n)[0]
        )

    def complete(self, text_before_cursor: str) -> list[CompletionItem]:
        match = _TOKEN_RE.search(text_before_cursor or "")
        if not match:
            return []
        token = match.group(1)
        if "." in token:
            base, _, prefix = token.rpartition(".")
            return self._complete_member(base, prefix)
        return self._complete_names(token)

    def _complete_names(self, prefix: str) -> list[CompletionItem]:
        items: list[CompletionItem] = []
        seen = set()

        def add(label: str, insert: str, kind: str, detail: str = "") -> None:
            if label in seen or not label.startswith(prefix):
                return
            seen.add(label)
            items.append(CompletionItem(label, insert, kind, detail))

        for name in sorted(self.symbols.defined_variables | set(self.symbols.variables)):
            add(name, name, "var")
        for name, count in sorted(self.symbols.function_signatures.items()):
            add(name, name, "func", f"({count} 參數)")
        for name in sorted(self.symbols.class_signatures):
            add(name, name, "class")
        for name in sorted(self.symbols.imported_names):
            add(name, name, "module")
        for name in self._builtin_names:
            add(name, name, "builtin")
        if self.snippets_provider is not None:
            for snippet in self.snippets_provider():
                add(snippet.name, snippet.code, "snippet", "程式碼片段")
        return items

    def _complete_member(self, base: str, prefix: str) -> list[CompletionItem]:
        items: list[CompletionItem] = []
        info = get_callable_info(base)
        if info is not None and info.kind == "class":
            try:
                import importlib
                module = importlib.import_module(info.module)
                obj = module
                for attr in info.qualname.split("."):
                    obj = getattr(obj, attr)
                for name in dir(obj):
                    if name.startswith("_") or not name.startswith(prefix):
                        continue
                    items.append(CompletionItem(
                        label=name, insert=name, kind="member",
                        detail=info.full_name,
                    ))
            except Exception:
                pass
        if not items and (base in self.symbols.imported_names
                          or base in (self.symbols.libraries or [])):
            members = list_module_callables(base)
            for member in members:
                if member.name.startswith(prefix):
                    items.append(CompletionItem(
                        label=member.name, insert=member.name,
                        kind="member", detail=member.signature,
                    ))
        return items

    def describe(self, item: CompletionItem) -> tuple[str, str]:
        if item.kind in ("func", "builtin", "member", "class"):
            for candidate in (item.detail if "." in item.detail else "", item.label, item.insert):
                if not candidate:
                    continue
                info = get_callable_info(candidate)
                if info is not None:
                    return info.signature, info.doc
        return item.detail, item.doc

    def describe_name(self, name: str) -> tuple[bool, str, str]:
        info = get_callable_info(name)
        if info is not None:
            return True, info.signature, info.doc
        if name in self.symbols.function_signatures:
            count = self.symbols.function_signatures[name]
            return True, f"(流程圖函式，{count} 參數)", ""
        if name in self.symbols.defined_variables or name in self.symbols.variables:
            return True, "(已定義變數)", ""
        if name in self.symbols.class_signatures:
            return True, "(流程圖類別)", ""
        return False, "", ""
