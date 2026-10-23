from __future__ import annotations

import json
from typing import Optional


class LanguageBackend:
    """目標語言後端。新增語言時繼承本類別並註冊到 LanguageRegistry 即可。"""

    name = "base"
    display_name = "Base"
    file_extension = ".txt"
    indent_unit = "    "
    supports_extensions = True
    supports_execution = True

    # ---------- 檔首 ----------

    def header_imports(self, libraries, custom_modules) -> list[str]:
        raise NotImplementedError

    def threading_header(self) -> Optional[str]:
        return None

    # ---------- 基本陳述 ----------

    def print_stmt(self, expr: str) -> str:
        raise NotImplementedError

    def comment(self, text: str) -> str:
        raise NotImplementedError

    def return_stmt(self, expr: str) -> str:
        raise NotImplementedError

    def assignment(self, name: str, value) -> str:
        raise NotImplementedError

    # ---------- 區塊結構（無大括號語言 block_close 回傳空串列）----------

    def if_open(self, cond: str) -> str:
        raise NotImplementedError

    def else_open(self) -> str:
        raise NotImplementedError

    def while_open(self, cond: str) -> str:
        raise NotImplementedError

    def for_open(self, cond: str) -> str:
        raise NotImplementedError

    def block_close(self, level: int = 0) -> list[str]:
        return []

    def block_open(self, label: str = "") -> Optional[str]:
        """無對應語法的區塊（例如 Python with）開啟行；Python 回傳 None。"""
        return None

    def empty_body(self, level: int = 0) -> Optional[str]:
        raise NotImplementedError

    # ---------- 函式 / 類別 ----------

    def function_open(self, name: str, params: str) -> str:
        raise NotImplementedError

    def lambda_head(self, name: str, params: str) -> str:
        raise NotImplementedError

    def lambda_tail(self) -> str:
        return ""

    def decorator_line(self, decorator: str) -> Optional[str]:
        return f"@{decorator}"

    def class_open(self, name: str, parent: str) -> str:
        raise NotImplementedError

    def method_open(self, name: str, params: str) -> str:
        raise NotImplementedError

    def class_attribute(self, name: str, value) -> str:
        raise NotImplementedError

    # ---------- 擴充元素 ----------

    def extension_declaration(self, decl: str) -> Optional[str]:
        return decl

    def unsupported_extension(self, label: str) -> str:
        return self.comment(f"{label}：僅支援 Python")

    def extension_code(self, element, ctx, ext) -> list[str]:
        try:
            return list(ext.emit_code(element, ctx))
        except Exception as exc:
            return [ctx.line(self.comment(f"擴充元素產生失敗：{exc}"))]


class PythonBackend(LanguageBackend):
    name = "python"
    display_name = "Python"
    file_extension = ".py"
    indent_unit = "    "
    supports_extensions = True
    supports_execution = True

    def header_imports(self, libraries, custom_modules) -> list[str]:
        lines = []
        for lib in libraries:
            lines.append(f"import {lib}")
        for mod_name, _path in custom_modules:
            lines.append(f"import {mod_name}")
        return lines

    def threading_header(self) -> Optional[str]:
        return "import threading"

    def print_stmt(self, expr: str) -> str:
        return f"print({expr})"

    def comment(self, text: str) -> str:
        return f"# {text}"

    def return_stmt(self, expr: str) -> str:
        return f"return {expr}"

    def assignment(self, name: str, value) -> str:
        return f"{name} = {value!r}"

    def if_open(self, cond: str) -> str:
        return f"if {cond}:"

    def else_open(self) -> str:
        return "else:"

    def while_open(self, cond: str) -> str:
        return f"while {cond}:"

    def for_open(self, cond: str) -> str:
        return f"for {cond}:"

    def empty_body(self, level: int = 0) -> Optional[str]:
        return "pass"

    def function_open(self, name: str, params: str) -> str:
        return f"def {name}({params}):"

    def lambda_head(self, name: str, params: str) -> str:
        return f"{name} = lambda {params}: "

    def lambda_tail(self) -> str:
        return ""

    def class_open(self, name: str, parent: str) -> str:
        return f"class {name}({parent}):" if parent else f"class {name}:"

    def method_open(self, name: str, params: str) -> str:
        return f"def {name}({params}):"

    def class_attribute(self, name: str, value) -> str:
        return f"{name} = {value!r}" if isinstance(value, str) else f"{name} = {value}"


class JavaScriptBackend(LanguageBackend):
    name = "javascript"
    display_name = "JavaScript"
    file_extension = ".js"
    indent_unit = "    "
    supports_extensions = False
    supports_execution = False

    def header_imports(self, libraries, custom_modules) -> list[str]:
        lines = []
        for lib in libraries:
            lines.append(f'const {lib} = require("{lib}");')
        for mod_name, _path in custom_modules:
            lines.append(f'const {mod_name} = require("{mod_name}");')
        return lines

    def threading_header(self) -> Optional[str]:
        return None

    def print_stmt(self, expr: str) -> str:
        return f"console.log({expr});"

    def comment(self, text: str) -> str:
        return f"// {text}"

    def return_stmt(self, expr: str) -> str:
        return f"return {expr};"

    def assignment(self, name: str, value) -> str:
        return f"let {name} = {self._value(value)};"

    def _value(self, value) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "null"
        if isinstance(value, str):
            return json.dumps(value, ensure_ascii=False)
        try:
            return json.dumps(value)
        except (TypeError, ValueError):
            return str(value)

    def if_open(self, cond: str) -> str:
        return f"if ({cond}) {{"

    def else_open(self) -> str:
        return "} else {"

    def while_open(self, cond: str) -> str:
        return f"while ({cond}) {{"

    def for_open(self, cond: str) -> str:
        return f"for ({cond}) {{"

    def block_close(self, level: int = 0) -> list[str]:
        return ["}"]

    def empty_body(self, level: int = 0) -> Optional[str]:
        return None

    def function_open(self, name: str, params: str) -> str:
        return f"function {name}({params}) {{"

    def lambda_head(self, name: str, params: str) -> str:
        return f"const {name} = ({params}) => "

    def lambda_tail(self) -> str:
        return ";"

    def decorator_line(self, decorator: str) -> Optional[str]:
        return f"// 裝飾器 {decorator} 不適用於 JavaScript"

    def class_open(self, name: str, parent: str) -> str:
        return f"class {name} extends {parent} {{" if parent else f"class {name} {{"

    def method_open(self, name: str, params: str) -> str:
        return f"{name}({params}) {{"

    def class_attribute(self, name: str, value) -> str:
        return f"{name} = {self._value(value)};"

    def extension_declaration(self, decl: str) -> Optional[str]:
        return None


class LanguageRegistry:
    def __init__(self):
        self._backends: dict[str, LanguageBackend] = {}

    def register(self, backend: LanguageBackend) -> None:
        if not isinstance(backend, LanguageBackend):
            raise TypeError("必須為 LanguageBackend 實例")
        if not backend.name:
            raise ValueError("後端必須有 name")
        self._backends[backend.name] = backend

    def get(self, name: str) -> LanguageBackend:
        key = (name or "python").strip().lower()
        return self._backends.get(key) or self._backends["python"]

    def names(self) -> list[str]:
        return list(self._backends.keys())

    def display_names(self) -> list[str]:
        return [self._backends[n].display_name for n in self._backends]

    def display_to_name(self, display: str) -> str:
        for backend in self._backends.values():
            if backend.display_name == display:
                return backend.name
        return "python"


_registry = LanguageRegistry()
_registry.register(PythonBackend())
_registry.register(JavaScriptBackend())


def register_language(backend: LanguageBackend) -> None:
    _registry.register(backend)


def get_language(name: Optional[str] = None) -> LanguageBackend:
    return _registry.get(name or "python")


def list_languages() -> list[str]:
    return _registry.names()


def language_display_names() -> list[str]:
    return _registry.display_names()


def language_registry() -> LanguageRegistry:
    return _registry
