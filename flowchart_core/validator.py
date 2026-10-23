from __future__ import annotations

import ast
import builtins
import re
from dataclasses import dataclass
from typing import Optional

from .models import ConnectionType, Element, ElementType
from .policy import CodePolicy
from .symbols import SymbolTable, _count_params


@dataclass
class ValidationResult:
    ok: bool
    message: str = ""
    severity: str = "error"

    @staticmethod
    def success() -> "ValidationResult":
        return ValidationResult(True, "")

    @staticmethod
    def failure(message: str) -> "ValidationResult":
        return ValidationResult(False, message)

    @staticmethod
    def warning(message: str) -> "ValidationResult":
        return ValidationResult(True, message, severity="warning")


_VALID_OPERATORS = re.compile(
    r"[\+\-\*/%=<>&|\^~!]=?|==|!=|<=|>=|\band\b|\bor\b|\bnot\b|\bin\b|\bnot in\b"
)
_IDENTIFIER = re.compile(r"^[a-zA-Z_]\w*$")


class CodeValidator:
    def __init__(self, symbols: SymbolTable, policy: Optional[CodePolicy] = None):
        self.symbols = symbols
        self.policy = policy or CodePolicy.standard()
        self._builtin_names = frozenset(dir(builtins))
        self._policy_builtins = self.policy.allowed_builtin_names()

    def refresh_policy(self, policy: CodePolicy) -> None:
        self.policy = policy
        self._policy_builtins = policy.allowed_builtin_names()

    def validate_code(self, code: str, role: str = "statement",
                      element: Optional[Element] = None,
                      check_names: bool = True) -> ValidationResult:
        code = (code or "").strip()
        if not code:
            return ValidationResult.failure("程式碼為空")

        syntax = self._check_syntax(code, role)
        if not syntax.ok:
            return syntax

        if check_names:
            name_check = self._check_names(code, role)
            if not name_check.ok:
                return name_check

        if element is not None and element.type == ElementType.INPUT:
            if not self._looks_like_input(code):
                return ValidationResult.failure(
                    "輸入元素應包含型別轉換或 input()（例如 int(input())）"
                )

        if role == "statement" and element is not None and element.type in (
                ElementType.PROCESS, ElementType.INPUT, ElementType.OUTPUT):
            if not _VALID_OPERATORS.search(code) and not self._is_import_or_def(code):
                return ValidationResult.warning(
                    "缺少有效運算子。建議使用：+, -, *, /, ==, !=, <, >, and, or, not"
                )

        sugar = self._check_syntax_sugar(code, role, element)
        if not sugar.ok:
            return sugar

        violations = self.policy.check_code(code)
        if violations:
            return ValidationResult.failure(
                "安全政策封鎖：" + violations[0].message
            )
        return ValidationResult.success()

    def validate_connection(self, conn_type: str, call_params: str, priority_str: str,
                            target: Optional[Element]) -> ValidationResult:
        try:
            priority = int(priority_str if priority_str not in ("", None) else 0)
            if priority < 0:
                return ValidationResult.failure("優先級必須為非負整數")
        except (ValueError, TypeError):
            return ValidationResult.failure("優先級必須為整數")

        if conn_type not in ConnectionType.ALL:
            return ValidationResult.failure(f"未知連線類型：{conn_type}")

        target_check = self.validate_connection_target(conn_type, target)
        if not target_check.ok:
            return target_check

        if conn_type == ConnectionType.CALL:
            if not (call_params or "").strip():
                return ValidationResult.failure("Call 連線必須提供呼叫參數")
            if target is not None and target.type == ElementType.FUNCTION:
                return self.validate_function_call(target.function_name, call_params)
            if target is not None and target.type == ElementType.CLASS:
                if "." not in call_params:
                    return ValidationResult.failure(
                        "類別呼叫參數應為 obj.method(args) 格式"
                    )
                try:
                    ast.parse(call_params if "(" in call_params else f"{call_params}()")
                except SyntaxError as exc:
                    return ValidationResult.failure(f"呼叫參數語法錯誤：{exc}")
            if target is not None and target.type == ElementType.EXTERNAL:
                return self._validate_external_call(target, call_params)
        elif call_params:
            return ValidationResult.failure(f"{conn_type} 連線不應包含呼叫參數")
        return ValidationResult.success()

    def validate_connection_target(self, conn_type: str,
                                   target: Optional[Element]) -> ValidationResult:
        if conn_type not in ConnectionType.ALL:
            return ValidationResult.failure(f"未知連線類型：{conn_type}")
        if target is None:
            return ValidationResult.success()
        if conn_type == ConnectionType.CALL and target.type not in (
                ElementType.FUNCTION, ElementType.CLASS, ElementType.EXTERNAL):
            return ValidationResult.failure("Call 連線必須指向函式、類別或外部函式元素")
        if conn_type in (ConnectionType.BODY, ConnectionType.EXIT) \
                and target.type in (ElementType.FUNCTION, ElementType.EXTERNAL):
            return ValidationResult.failure("Body/Exit 連線不能指向函式或外部函式元素")
        return ValidationResult.success()

    def validate_function_call(self, function_name: Optional[str],
                               call_params: str) -> ValidationResult:
        if not function_name:
            return ValidationResult.failure("函式名稱未定義")
        try:
            ast.parse(f"{function_name}({call_params})")
        except SyntaxError as exc:
            return ValidationResult.failure(f"呼叫參數語法錯誤：{exc}")
        param_count = len([p for p in (call_params or "").split(",") if p.strip()])
        expected = self.symbols.function_signatures.get(function_name)
        if expected is not None and param_count != expected:
            return ValidationResult.failure(
                f"參數數量不匹配：預期 {expected} 個，實際 {param_count} 個"
            )
        return ValidationResult.success()

    def _validate_external_call(self, target: Element, call_params: str) -> ValidationResult:
        module = target.opt("module") or ""
        qualname = target.opt("qualname") or ""
        full = f"{module}.{qualname}" if module else qualname
        expr = call_params
        if "(" not in expr:
            expr = f"{expr}()" if "(" not in call_params else expr
        try:
            ast.parse(expr if "(" in expr else f"{expr}()")
        except SyntaxError as exc:
            return ValidationResult.failure(f"呼叫參數語法錯誤：{exc}")
        ok, msg = self.policy.check_import(module)
        if not ok:
            return ValidationResult.failure(msg)
        ok, msg = self.policy.check_name(full)
        if not ok:
            return ValidationResult.failure(msg)
        return ValidationResult.success()

    def _check_syntax(self, code: str, role: str) -> ValidationResult:
        wrapper = {
            "statement": code,
            "expression": code,
            "condition": f"if {code}: pass",
            "lambda": f"lambda x: {code}",
            "input": code,
        }.get(role, code)
        try:
            ast.parse(wrapper)
        except SyntaxError as exc:
            return ValidationResult.failure(f"語法錯誤：{exc}")
        return ValidationResult.success()

    def _check_names(self, code: str, role: str) -> ValidationResult:
        parse_src = f"lambda x: {code}" if role == "lambda" else (
            f"if {code}: pass" if role == "condition" else code
        )
        try:
            tree = ast.parse(parse_src)
        except SyntaxError:
            return ValidationResult.success()
        known_builtins = self._policy_builtins
        undefined = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                name = node.id
                if name in known_builtins or name in self._builtin_names and not self._is_blocked_builtin(name):
                    continue
                if self.symbols.is_known(name):
                    continue
                undefined.add(name)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                chain = _attr_chain(node.func)
                root = chain.split(".")[0]
                if root in known_builtins or self.symbols.is_known(root):
                    continue
                if self.symbols.class_signatures:
                    attr = node.func.attr
                    for info in self.symbols.class_signatures.values():
                        if attr in info.get("methods", {}) or attr in info.get("attributes", {}):
                            break
                    else:
                        undefined.add(chain)
                else:
                    undefined.add(chain)
        if undefined:
            return ValidationResult.failure(
                f"未定義變數或方法：{', '.join(sorted(undefined))}"
            )
        return ValidationResult.success()

    def _is_blocked_builtin(self, name: str) -> bool:
        return name not in self._policy_builtins

    def _check_syntax_sugar(self, code: str, role: str,
                            element: Optional[Element]) -> ValidationResult:
        if role in ("condition", "lambda"):
            return ValidationResult.success()
        import_match = re.match(r"from\s+([\w\.]+)\s+import\s+([\w\s*,]+)", code)
        if import_match:
            module = import_match.group(1)
            ok, msg = self.policy.check_import(module)
            if not ok:
                return ValidationResult.failure(msg)
            try:
                __import__(module)
            except ImportError:
                return ValidationResult.failure(
                    f"模組 '{module}' 不存在。請確認模組名稱或安裝（例如 pip install {module}）。"
                )
        plain_import = re.match(r"import\s+([\w\.]+)", code)
        if plain_import:
            module = plain_import.group(1)
            ok, msg = self.policy.check_import(module)
            if not ok:
                return ValidationResult.failure(msg)
            try:
                __import__(module)
            except ImportError:
                return ValidationResult.failure(
                    f"模組 '{module}' 不存在。請確認模組名稱或安裝（例如 pip install {module}）。"
                )
        return ValidationResult.success()

    @staticmethod
    def _looks_like_input(code: str) -> bool:
        return any(tok in code for tok in ("int(", "float(", "str(", "input("))

    @staticmethod
    def _is_import_or_def(code: str) -> bool:
        return bool(re.match(r"^\s*(import|from|def|class|@|with|for|while|if)\b", code))


def _attr_chain(node: ast.Attribute) -> str:
    parts = [node.attr]
    value = node.value
    while isinstance(value, ast.Attribute):
        parts.append(value.attr)
        value = value.value
    if isinstance(value, ast.Name):
        parts.append(value.id)
    return ".".join(reversed(parts))


def validate_identifier(name: str) -> ValidationResult:
    if not name or not _IDENTIFIER.match(name):
        return ValidationResult.failure("名稱必須為有效 Python 標識符")
    return ValidationResult.success()
