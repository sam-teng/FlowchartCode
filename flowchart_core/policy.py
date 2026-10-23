from __future__ import annotations

import ast
import builtins
import json
import os
import re
from dataclasses import dataclass, field
from typing import Optional


PRESET_LENIENT = "寬鬆"
PRESET_STANDARD = "標準"
PRESET_STRICT = "嚴格"

_DEFAULT_BLACK_MODULES = {
    "os", "sys", "subprocess", "ctypes", "shutil", "socket", "importlib",
    "multiprocessing", "signal", "resource", "pty", "webbrowser", "pathlib",
}
_DEFAULT_BLACK_FUNCTIONS = {
    "eval", "exec", "compile", "__import__", "open",
    "globals", "locals", "vars", "getattr", "setattr", "delattr",
}
_DEFAULT_ALLOWED_MODULES_STRICT = {
    "math", "cmath", "json", "random", "itertools", "functools", "collections",
    "string", "re", "decimal", "fractions", "statistics", "operator", "textwrap",
    "datetime", "time", "typing", "heapq", "bisect", "array", "enum", "dataclasses",
}
_DEFAULT_ALLOWED_FUNCTIONS_STRICT = {
    "abs", "all", "any", "bool", "bytes", "callable", "chr", "dict", "dir",
    "divmod", "enumerate", "filter", "float", "format", "frozenset", "hash",
    "hex", "id", "int", "isinstance", "issubclass", "iter", "len", "list",
    "map", "max", "min", "next", "oct", "ord", "pow", "print", "range", "repr",
    "reversed", "round", "set", "slice", "sorted", "str", "sum", "tuple", "zip",
    "True", "False", "None", "Exception", "ValueError", "TypeError",
    "KeyError", "IndexError", "ZeroDivisionError", "ArithmeticError",
    "AssertionError", "RuntimeError", "StopIteration", "NotImplementedError",
    "input", "help", "ascii", "bin", "complex", "object", "super",
}


@dataclass
class PolicyViolation:
    category: str
    message: str
    matched: str = ""


@dataclass
class CodePolicy:
    mode: str = "blacklist"
    modules: set = field(default_factory=set)
    functions: set = field(default_factory=set)
    deny_dunder: bool = True
    deny_reflection: bool = True
    regex_rules: list = field(default_factory=list)
    preset_name: str = PRESET_STANDARD

    @staticmethod
    def lenient() -> "CodePolicy":
        return CodePolicy(
            mode="blacklist",
            modules={"subprocess", "ctypes", "pty", "resource"},
            functions={"eval", "exec", "compile", "__import__"},
            deny_dunder=False,
            deny_reflection=False,
            regex_rules=[],
            preset_name=PRESET_LENIENT,
        )

    @staticmethod
    def standard() -> "CodePolicy":
        return CodePolicy(
            mode="blacklist",
            modules=set(_DEFAULT_BLACK_MODULES),
            functions=set(_DEFAULT_BLACK_FUNCTIONS),
            deny_dunder=True,
            deny_reflection=True,
            regex_rules=[r"__\w+__\s*\(", r"os\s*\.\s*system\s*\("],
            preset_name=PRESET_STANDARD,
        )

    @staticmethod
    def strict() -> "CodePolicy":
        return CodePolicy(
            mode="whitelist",
            modules=set(_DEFAULT_ALLOWED_MODULES_STRICT),
            functions=set(_DEFAULT_ALLOWED_FUNCTIONS_STRICT),
            deny_dunder=True,
            deny_reflection=True,
            regex_rules=[r"__\w+__\s*\("],
            preset_name=PRESET_STRICT,
        )

    @staticmethod
    def from_preset(name: str) -> "CodePolicy":
        if name == PRESET_LENIENT:
            return CodePolicy.lenient()
        if name == PRESET_STRICT:
            return CodePolicy.strict()
        return CodePolicy.standard()

    def check_import(self, module: str) -> tuple[bool, str]:
        root = (module or "").split(".")[0].strip()
        if not root:
            return False, "模組名稱為空"
        if self.mode == "whitelist":
            if root not in self.modules:
                return False, f"白名單模式：模組 '{root}' 未在允許清單中"
            return True, ""
        if root in self.modules:
            return False, f"模組 '{root}' 被黑名單封鎖"
        return True, ""

    def check_name(self, name: str) -> tuple[bool, str]:
        root = (name or "").split(".")[0].strip()
        if not root:
            return True, ""
        if self.mode == "whitelist":
            if root in self.functions:
                return True, ""
            if root.isidentifier() and root in vars(builtins):
                return False, f"白名單模式：內建函式 '{root}' 未在允許清單中"
            return True, ""
        if root in self.functions:
            return False, f"'{root}' 被黑名單封鎖"
        return True, ""

    def check_code(self, code: str) -> list[PolicyViolation]:
        violations: list[PolicyViolation] = []
        if not code or not code.strip():
            return violations
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return violations
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    ok, msg = self.check_import(alias.name)
                    if not ok:
                        violations.append(PolicyViolation("module", msg, alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    ok, msg = self.check_import(node.module)
                    if not ok:
                        violations.append(PolicyViolation("module", msg, node.module))
            elif isinstance(node, ast.Call):
                func = node.func
                call_name = ""
                if isinstance(func, ast.Name):
                    call_name = func.id
                elif isinstance(func, ast.Attribute):
                    call_name = _attribute_chain(func)
                if call_name:
                    ok, msg = self.check_name(call_name)
                    if not ok:
                        violations.append(PolicyViolation("function", msg, call_name))
            if self.deny_dunder and isinstance(node, ast.Attribute):
                if node.attr.startswith("__") and node.attr.endswith("__"):
                    violations.append(PolicyViolation(
                        "ast", f"禁止存取 dunder 屬性 '{node.attr}'", node.attr
                    ))
            if self.deny_reflection and isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in (
                        "getattr", "setattr", "delattr", "vars", "globals", "locals"):
                    violations.append(PolicyViolation(
                        "ast", f"禁止反射呼叫 '{node.func.id}'", node.func.id
                    ))
        for pattern in self.regex_rules:
            try:
                if re.search(pattern, code):
                    violations.append(PolicyViolation(
                        "regex", f"命中封鎖模式：{pattern}", pattern
                    ))
            except re.error:
                continue
        return _dedupe_violations(violations)

    def allowed_builtin_names(self) -> frozenset:
        base = frozenset(dir(builtins))
        if self.mode == "whitelist":
            return frozenset(n for n in base if n in self.functions) | {
                "True", "False", "None", "print", "len", "range", "int", "float",
                "str", "list", "dict", "set", "tuple", "bool", "input", "sum",
                "min", "max", "abs", "sorted", "enumerate", "zip", "map", "filter",
                "any", "all", "round", "Exception", "ValueError", "TypeError",
            }
        return frozenset(n for n in base if n not in self.functions)

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "modules": sorted(self.modules),
            "functions": sorted(self.functions),
            "deny_dunder": self.deny_dunder,
            "deny_reflection": self.deny_reflection,
            "regex_rules": list(self.regex_rules),
            "preset_name": self.preset_name,
        }

    @staticmethod
    def from_dict(data: dict) -> "CodePolicy":
        return CodePolicy(
            mode=data.get("mode") or "blacklist",
            modules=set(data.get("modules") or []),
            functions=set(data.get("functions") or []),
            deny_dunder=bool(data.get("deny_dunder", True)),
            deny_reflection=bool(data.get("deny_reflection", True)),
            regex_rules=list(data.get("regex_rules") or []),
            preset_name=data.get("preset_name") or PRESET_STANDARD,
        )

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @staticmethod
    def load(path: str) -> "CodePolicy":
        if not os.path.exists(path):
            policy = CodePolicy.standard()
            policy.save(path)
            return policy
        try:
            with open(path, "r", encoding="utf-8") as f:
                return CodePolicy.from_dict(json.load(f))
        except (json.JSONDecodeError, OSError):
            policy = CodePolicy.standard()
            policy.save(path)
            return policy


def _attribute_chain(node: ast.Attribute) -> str:
    parts = [node.attr]
    value = node.value
    while isinstance(value, ast.Attribute):
        parts.append(value.attr)
        value = value.value
    if isinstance(value, ast.Name):
        parts.append(value.id)
    return ".".join(reversed(parts))


def _dedupe_violations(violations: list[PolicyViolation]) -> list[PolicyViolation]:
    seen = set()
    result = []
    for v in violations:
        key = (v.category, v.message)
        if key not in seen:
            seen.add(key)
            result.append(v)
    return result
