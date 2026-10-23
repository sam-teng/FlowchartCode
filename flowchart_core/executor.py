from __future__ import annotations

import builtins
import importlib
import importlib.util
import io
import os
import sys
import threading
from typing import Iterator, Optional

from .events import EventKind, ExecutionEvent
from .models import ConnectionType, ElementType
from .plan import DecisionNode, ElementNode, ExecutionPlan, LoopNode, WithBodyNode
from .policy import CodePolicy


class FlowchartExecutor:
    def __init__(self, plan: ExecutionPlan, policy: Optional[CodePolicy] = None):
        self.plan = plan
        self.policy = policy or CodePolicy.standard()
        self.globals: dict = {}
        self.thread_errors: list = []
        self.output = io.StringIO()
        self._call_stack: list[str] = []
        self._max_call_depth = 50

    def prepare(self, variables=None, libraries=None, custom_modules=None) -> list[str]:
        warnings: list[str] = []
        allowed = self.policy.allowed_builtin_names()
        policy = self.policy

        def _policy_import(name, globals=None, locals=None, fromlist=(), level=0):
            ok, msg = policy.check_import(str(name))
            if not ok:
                raise ImportError(msg)
            return builtins.__import__(name, globals, locals, fromlist, level)

        builtins_dict = {
            name: getattr(builtins, name)
            for name in dir(builtins)
            if name in allowed and not name.startswith("__")
        }
        builtins_dict["__import__"] = _policy_import
        self.globals = {"__builtins__": builtins_dict, "threading": threading}

        for name, raw in (variables or {}).items():
            if not str(name).isidentifier():
                warnings.append(f"變數名稱無效，已略過：{name}")
                continue
            if isinstance(raw, str):
                try:
                    self.globals[name] = eval(raw, self.globals)
                    continue
                except Exception:
                    pass
            self.globals[name] = raw

        for lib in libraries or []:
            ok, msg = self.policy.check_import(lib)
            if not ok:
                warnings.append(msg)
                continue
            try:
                self.globals[lib] = __import__(lib)
            except ImportError as exc:
                warnings.append(f"無法載入模組 {lib}：{exc}")

        for mod_name, path in custom_modules or []:
            ok, msg = self.policy.check_import(mod_name)
            if not ok:
                warnings.append(msg)
                continue
            try:
                if os.path.isdir(path):
                    if path not in sys.path:
                        sys.path.append(path)
                    module = importlib.import_module(mod_name)
                else:
                    spec = importlib.util.spec_from_file_location(mod_name, path)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[mod_name] = module
                    spec.loader.exec_module(module)
                self.globals[mod_name] = module
            except Exception as exc:
                warnings.append(f"無法載入自訂模組 {mod_name}：{exc}")

        for line in self.plan.declarations:
            try:
                exec(line, self.globals)
            except Exception as exc:
                warnings.append(f"宣告失敗：{line}（{exc}）")
        return warnings

    def run(self) -> Iterator[ExecutionEvent]:
        self.output = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = self.output
        try:
            yield from self._run_nodes(self.plan.nodes)
        except Exception as exc:
            yield ExecutionEvent(EventKind.ERROR, message=f"執行器內部錯誤：{exc}")
        finally:
            sys.stdout = old_stdout
        yield ExecutionEvent(EventKind.DONE, data={
            "output": self.output.getvalue(),
            "thread_errors": list(self.thread_errors),
        })

    def run_children(self, element, conn_type: str = ConnectionType.BODY) -> Iterator[ExecutionEvent]:
        for conn in self.plan.outgoing(element.id, conn_type):
            target = self.plan.element(conn.target_id)
            if target is None:
                continue
            yield ExecutionEvent(
                EventKind.CONNECTION,
                source_id=conn.source_id, target_id=conn.target_id,
                data={"type": conn.type},
            )
            yield from self._run_element_by_id(target.id)

    def _run_nodes(self, nodes: list) -> Iterator[ExecutionEvent]:
        for node in nodes or []:
            if isinstance(node, ElementNode):
                yield from self._run_element_by_id(node.element_id)
            elif isinstance(node, DecisionNode):
                yield from self._run_decision(node)
            elif isinstance(node, LoopNode):
                yield from self._run_loop(node)
            elif isinstance(node, WithBodyNode):
                yield from self._run_with_body(node)

    def _run_element_by_id(self, element_id: str) -> Iterator[ExecutionEvent]:
        element = self.plan.element(element_id)
        if element is None:
            return
        yield from self._run_element(element)

    def _validation_for(self, element):
        cached = self.plan.validation_cache.get(element.id)
        return cached

    def _run_element(self, element) -> Iterator[ExecutionEvent]:
        cached = self._validation_for(element)
        if cached is not None and not cached.ok and cached.severity == "error":
            yield ExecutionEvent(
                EventKind.ERROR, element_id=element.id, message=cached.message
            )
            return

        yield ExecutionEvent(EventKind.ELEMENT_ENTER, element_id=element.id)
        etype = element.type
        calls = self.plan.outgoing(element.id, ConnectionType.CALL)

        try:
            if etype == ElementType.PROCESS:
                if calls:
                    pass
                elif (element.code or "").strip():
                    exec(element.code, self.globals)
            elif etype == ElementType.INPUT:
                if (element.code or "").strip():
                    result = eval(element.code, self.globals)
                    if "=" in element.code:
                        target_name = element.code.split("=", 1)[0].strip()
                        if target_name.isidentifier():
                            self.globals[target_name] = result
            elif etype == ElementType.OUTPUT:
                if (element.code or "").strip():
                    value = eval(element.code, self.globals)
                    print(value)
                    yield ExecutionEvent(
                        EventKind.OUTPUT, element_id=element.id,
                        message=str(value), data={"value": value},
                    )
            elif etype == ElementType.START_END:
                is_entry = (
                    self.plan.flowchart.entry_element() is not None
                    and self.plan.flowchart.entry_element().id == element.id
                )
                if not is_entry and element.return_value:
                    value = eval(element.return_value, self.globals)
                    print(value)
                    yield ExecutionEvent(
                        EventKind.OUTPUT, element_id=element.id,
                        message=str(value), data={"value": value},
                    )
            elif etype in (ElementType.FUNCTION, ElementType.CLASS, ElementType.COMMENT,
                           ElementType.EXTERNAL):
                pass
            else:
                ext = self.plan.registry.get(etype) if self.plan.registry else None
                if ext is not None:
                    yield from ext.execute(element, self)
        except NameError as exc:
            msg = f"名稱錯誤（可能被安全政策封鎖或未定義）：{exc}"
            yield ExecutionEvent(EventKind.ERROR, element_id=element.id, message=msg)
            return
        except Exception as exc:
            yield ExecutionEvent(
                EventKind.ERROR, element_id=element.id, message=f"執行錯誤：{exc}"
            )
            return

        for conn in calls:
            yield from self._run_call(element, conn)

        yield ExecutionEvent(EventKind.ELEMENT_EXIT, element_id=element.id)

    def _run_call(self, source_element, conn) -> Iterator[ExecutionEvent]:
        target = self.plan.element(conn.target_id)
        if target is None:
            yield ExecutionEvent(
                EventKind.ERROR, element_id=source_element.id,
                message="Call 目標不存在",
            )
            return
        yield ExecutionEvent(
            EventKind.CONNECTION,
            source_id=conn.source_id, target_id=conn.target_id,
            data={"type": conn.type},
        )
        if target.type == ElementType.FUNCTION:
            nodes = self.plan.functions.get(target.id)
            if nodes is None:
                yield ExecutionEvent(
                    EventKind.WARNING, element_id=target.id,
                    message=f"函式 {target.function_name or target.id} 沒有子流程圖",
                )
                return
            yield from self._run_subflow(target.id, nodes, target, call_conn=conn,
                                         params_text=target.function_params)
        elif target.type == ElementType.CLASS:
            method_call = conn.call_params or ""
            method_name = ""
            if "." in method_call:
                method_name = method_call.split(".", 1)[1].split("(", 1)[0].strip()
            key = f"{target.id}:{method_name}"
            nodes = self.plan.method_nodes.get(key)
            if nodes is None:
                yield ExecutionEvent(
                    EventKind.WARNING, element_id=target.id,
                    message=f"找不到類別方法：{method_name}",
                )
                return
            yield from self._run_subflow(key, nodes, target)
        elif target.type == ElementType.EXTERNAL:
            yield from self._run_external(target, conn)
        else:
            yield ExecutionEvent(
                EventKind.WARNING, element_id=target.id,
                message="Call 目標不支援呼叫",
            )

    def _run_subflow(self, key: str, nodes: list, target,
                     call_conn=None, params_text=None) -> Iterator[ExecutionEvent]:
        if key in self._call_stack or len(self._call_stack) >= self._max_call_depth:
            yield ExecutionEvent(
                EventKind.ERROR, element_id=target.id,
                message="偵測到遞迴呼叫或深度超限，已中止",
            )
            return
        bound: dict = {}
        if call_conn is not None:
            try:
                bound = self._bind_params(params_text, call_conn.call_params)
            except Exception as exc:
                yield ExecutionEvent(
                    EventKind.ERROR, element_id=target.id,
                    message=f"呼叫參數求值失敗：{exc}",
                )
                return
        saved: dict = {}
        shadowed: set = set()
        for name, value in bound.items():
            if name in self.globals:
                saved[name] = self.globals[name]
                shadowed.add(name)
            self.globals[name] = value
        self._call_stack.append(key)
        try:
            yield from self._run_nodes(nodes)
        finally:
            self._call_stack.pop()
            for name in bound:
                if name in shadowed:
                    self.globals[name] = saved[name]
                else:
                    self.globals.pop(name, None)

    @staticmethod
    def _split_top_level(text: str) -> list[str]:
        parts: list[str] = []
        buf: list[str] = []
        depth = 0
        quote = ""
        for ch in text or "":
            if quote:
                buf.append(ch)
                if ch == quote and (len(buf) < 2 or buf[-2] != "\\"):
                    quote = ""
                continue
            if ch in "\"'":
                quote = ch
                buf.append(ch)
                continue
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            if ch == "," and depth == 0:
                parts.append("".join(buf).strip())
                buf = []
                continue
            buf.append(ch)
        if "".join(buf).strip():
            parts.append("".join(buf).strip())
        return parts

    def _bind_params(self, params_text, call_params) -> dict:
        import ast as _ast

        names: list[str] = []
        defaults: dict = {}
        for item in self._split_top_level(params_text or ""):
            if "=" in item:
                name, _, default_expr = item.partition("=")
                name = name.strip()
                if name:
                    names.append(name)
                    defaults[name] = default_expr.strip()
            elif item.strip():
                names.append(item.strip())

        args_text = (call_params or "").strip()
        if not args_text:
            return {name: eval(defaults[name], self.globals) for name in names
                    if name in defaults}

        if "(" in args_text and args_text.rstrip().endswith(")"):
            call_expr = args_text
        else:
            call_expr = f"f({args_text})"
        tree = _ast.parse(call_expr, mode="eval")
        first = tree.body
        if not isinstance(first, _ast.Call):
            raise ValueError("呼叫參數格式無效")
        values = [eval(_ast.unparse(arg), self.globals) for arg in first.args]
        for kw in first.keywords:
            if kw.arg:
                values.append((kw.arg, eval(_ast.unparse(kw.value), self.globals)))

        bound: dict = {}
        pos_index = 0
        for item in values:
            if isinstance(item, tuple):
                bound[item[0]] = item[1]
            else:
                while pos_index < len(names) and names[pos_index] in bound:
                    pos_index += 1
                if pos_index < len(names):
                    bound[names[pos_index]] = item
                    pos_index += 1
        for name in names:
            if name not in bound and name in defaults:
                bound[name] = eval(defaults[name], self.globals)
        return bound

    def _run_external(self, target, conn) -> Iterator[ExecutionEvent]:
        module = target.opt("module") or ""
        qualname = target.opt("qualname") or ""
        full = f"{module}.{qualname}" if module else qualname
        ok, msg = self.policy.check_name(full)
        if not ok:
            yield ExecutionEvent(
                EventKind.POLICY_VIOLATION, element_id=target.id, message=msg
            )
            return
        expr = f"{full}({conn.call_params or ''})"
        try:
            result = eval(expr, self.globals)
        except Exception as exc:
            yield ExecutionEvent(
                EventKind.ERROR, element_id=target.id,
                message=f"外部呼叫失敗 {expr}：{exc}",
            )
            return
        print(f"{expr} → {result!r}")
        yield ExecutionEvent(
            EventKind.OUTPUT, element_id=target.id,
            message=f"{expr} → {result!r}", data={"value": result},
        )

    def _run_decision(self, node: DecisionNode) -> Iterator[ExecutionEvent]:
        element = self.plan.element(node.element_id)
        if element is None:
            return
        cached = self._validation_for(element)
        if cached is not None and not cached.ok and cached.severity == "error":
            yield ExecutionEvent(
                EventKind.ERROR, element_id=element.id, message=cached.message
            )
            return
        yield ExecutionEvent(EventKind.ELEMENT_ENTER, element_id=element.id)
        try:
            result = bool(eval(element.condition, self.globals))
        except Exception as exc:
            yield ExecutionEvent(
                EventKind.ERROR, element_id=element.id,
                message=f"條件求值失敗：{exc}",
            )
            return
        yield ExecutionEvent(
            EventKind.ELEMENT_EXIT, element_id=element.id,
            message="成立" if result else "不成立",
            data={"condition_result": result},
        )
        branches = node.body if result else node.otherwise
        for target_id, branch_nodes in branches:
            yield ExecutionEvent(
                EventKind.CONNECTION,
                source_id=element.id, target_id=target_id,
                data={"type": ConnectionType.BODY if result else ConnectionType.EXIT},
            )
            yield from self._run_nodes(branch_nodes)

    def _run_loop(self, node: LoopNode) -> Iterator[ExecutionEvent]:
        element = self.plan.element(node.element_id)
        if element is None:
            return
        cached = self._validation_for(element)
        if cached is not None and not cached.ok and cached.severity == "error":
            yield ExecutionEvent(
                EventKind.ERROR, element_id=element.id, message=cached.message
            )
            return
        yield ExecutionEvent(EventKind.ELEMENT_ENTER, element_id=element.id)
        condition = element.condition or ""
        try:
            if element.loop_type == "for":
                if " in " not in condition:
                    yield ExecutionEvent(
                        EventKind.ERROR, element_id=element.id,
                        message="For 迴圈條件需包含 'in'，例如 'i in range(5)'",
                    )
                    return
                var_name, _, iter_expr = condition.partition(" in ")
                var_name = var_name.strip()
                iterable = eval(iter_expr.strip(), self.globals)
                for index, value in enumerate(iterable):
                    if index >= self.plan.loop_limit:
                        yield ExecutionEvent(
                            EventKind.LOOP_LIMIT, element_id=element.id,
                            message=f"迴圈超過安全上限 {self.plan.loop_limit} 次，已中止",
                        )
                        break
                    self.globals[var_name] = value
                    for target_id, branch_nodes in node.body:
                        yield ExecutionEvent(
                            EventKind.CONNECTION, source_id=element.id,
                            target_id=target_id,
                            data={"type": ConnectionType.BODY, "iteration": index},
                        )
                        yield from self._run_nodes(branch_nodes)
            else:
                iterations = 0
                while True:
                    try:
                        if not bool(eval(condition, self.globals)):
                            break
                    except Exception as exc:
                        yield ExecutionEvent(
                            EventKind.ERROR, element_id=element.id,
                            message=f"迴圈條件求值失敗：{exc}",
                        )
                        return
                    iterations += 1
                    if iterations > self.plan.loop_limit:
                        yield ExecutionEvent(
                            EventKind.LOOP_LIMIT, element_id=element.id,
                            message=f"迴圈超過安全上限 {self.plan.loop_limit} 次，已中止",
                        )
                        break
                    for target_id, branch_nodes in node.body:
                        yield ExecutionEvent(
                            EventKind.CONNECTION, source_id=element.id,
                            target_id=target_id,
                            data={"type": ConnectionType.BODY, "iteration": iterations},
                        )
                        yield from self._run_nodes(branch_nodes)
        except Exception as exc:
            yield ExecutionEvent(
                EventKind.ERROR, element_id=element.id, message=f"迴圈執行錯誤：{exc}"
            )
            return
        yield ExecutionEvent(EventKind.ELEMENT_EXIT, element_id=element.id)
        for target_id, branch_nodes in node.exit_branches:
            yield ExecutionEvent(
                EventKind.CONNECTION, source_id=element.id,
                target_id=target_id, data={"type": ConnectionType.EXIT},
            )
            yield from self._run_nodes(branch_nodes)

    def _run_with_body(self, node: WithBodyNode) -> Iterator[ExecutionEvent]:
        element = self.plan.element(node.element_id)
        if element is None:
            return
        ext = self.plan.registry.get(element.type) if self.plan.registry else None
        name = (element.opt("name") or "").strip()
        obj = self.globals.get(name)
        if obj is None:
            yield ExecutionEvent(
                EventKind.ERROR, element_id=element.id,
                message=f"同步物件 {name} 未宣告",
            )
            return
        yield ExecutionEvent(
            EventKind.ELEMENT_ENTER, element_id=element.id, message=f"取得 {name}"
        )
        try:
            with obj:
                for target_id, branch_nodes in node.body:
                    yield ExecutionEvent(
                        EventKind.CONNECTION, source_id=element.id,
                        target_id=target_id, data={"type": ConnectionType.BODY},
                    )
                    yield from self._run_nodes(branch_nodes)
        except Exception as exc:
            yield ExecutionEvent(
                EventKind.ERROR, element_id=element.id,
                message=f"同步區塊執行錯誤：{exc}",
            )
            return
        yield ExecutionEvent(EventKind.ELEMENT_EXIT, element_id=element.id)
        for target_id, branch_nodes in node.exit_branches:
            yield ExecutionEvent(
                EventKind.CONNECTION, source_id=element.id,
                target_id=target_id, data={"type": ConnectionType.EXIT},
            )
            yield from self._run_nodes(branch_nodes)
