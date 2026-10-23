from __future__ import annotations

from typing import Optional

from .concurrency import CodegenContext, ThreadCounter
from .extensions import ExtensionRegistry, collect_declarations
from .models import ConnectionType, ElementType, Flowchart
from .symbols import SymbolTable


class CodeGenerator:
    def __init__(self, flowchart: Flowchart, symbols: Optional[SymbolTable] = None,
                 registry: Optional[ExtensionRegistry] = None,
                 libraries=None, custom_modules=None, variables=None):
        self.flowchart = flowchart
        self.symbols = symbols or SymbolTable()
        self.registry = registry or ExtensionRegistry()
        self.libraries = list(libraries or [])
        self.custom_modules = list(custom_modules or [])
        self.variables = dict(variables or {})
        self._outgoing_index: dict = {}
        self._build_index(flowchart)

    def _build_index(self, flowchart: Flowchart) -> None:
        index: dict = {}
        for conn in flowchart.connections:
            index.setdefault((conn.source_id, conn.type), []).append(conn)
        for key, conns in index.items():
            conns.sort(key=lambda c: (c.priority, c.target_id))
        self._outgoing_index = index

    def outgoing(self, flowchart: Flowchart, element_id: str, conn_type: str) -> list:
        if flowchart is not self.flowchart:
            result = [c for c in flowchart.connections
                      if c.source_id == element_id and c.type == conn_type]
            result.sort(key=lambda c: (c.priority, c.target_id))
            return result
        return list(self._outgoing_index.get((element_id, conn_type), []))

    def generate(self) -> str:
        thread_counter = ThreadCounter()
        declarations = collect_declarations(self.flowchart, self.registry)
        ctx = CodegenContext(0, self.symbols, thread_counter, self.flowchart)
        visited: set = set()
        container_lines: list[str] = []
        for element in self.flowchart.elements:
            if element.type in (ElementType.FUNCTION, ElementType.CLASS):
                sub = self._emit_element(self.flowchart, element, ctx, visited)
                if sub:
                    container_lines.extend(sub)
                    container_lines.append("")
        body_lines = self._traverse(
            self.flowchart, self.flowchart.entry_element(),
            ctx, visited,
        )

        header = ["import threading"]
        for lib in self.libraries:
            header.append(f"import {lib}")
        for mod_name, _path in self.custom_modules:
            header.append(f"import {mod_name}")

        lines: list[str] = []
        lines.extend(header)
        lines.append("")
        for decl in declarations:
            lines.append(decl)
        if declarations:
            lines.append("")
        for name, value in self.variables.items():
            lines.append(f"{name} = {value!r}" if isinstance(value, str) else f"{name} = {value!r}")
        if self.variables:
            lines.append("")
        lines.extend(container_lines)
        lines.extend(body_lines)
        text = "\n".join(lines).strip()
        return text + "\n" if text else ""

    def _traverse(self, flowchart: Flowchart, element, ctx: CodegenContext,
                  visited: set) -> list[str]:
        lines: list[str] = []
        current = element
        while current is not None and current.id not in visited:
            visited.add(current.id)
            lines.extend(self._emit_element(flowchart, current, ctx, visited))
            if current.type in (ElementType.DECISION, ElementType.LOOP):
                break
            ext = self.registry.get(current.type)
            if ext is not None and getattr(ext, "indents_body", False):
                break
            body = self.outgoing(flowchart, current.id, ConnectionType.BODY)
            current = flowchart.element_by_id(body[0].target_id) if body else None
        return lines

    def _emit_element(self, flowchart: Flowchart, element, ctx: CodegenContext,
                      visited: set) -> list[str]:
        lines: list[str] = []
        etype = element.type
        calls = self.outgoing(flowchart, element.id, ConnectionType.CALL)

        if etype == ElementType.PROCESS:
            if not calls and (element.code or "").strip():
                lines.append(ctx.line(element.code))
        elif etype == ElementType.INPUT:
            if (element.code or "").strip():
                lines.append(ctx.line(element.code))
        elif etype == ElementType.OUTPUT:
            if (element.code or "").strip():
                lines.append(ctx.line(f"print({element.code})"))
        elif etype == ElementType.DECISION:
            if element.condition:
                lines.append(ctx.line(f"if {element.condition}:"))
                body_emitted = False
                for target_id, _prior in [(c.target_id, c.priority)
                                          for c in self.outgoing(flowchart, element.id, ConnectionType.BODY)]:
                    target = flowchart.element_by_id(target_id)
                    if target is None:
                        continue
                    sub = self._traverse(flowchart, target, ctx.child(1), visited)
                    if sub:
                        lines.extend(sub)
                        body_emitted = True
                if not body_emitted:
                    lines.append(ctx.line("pass", ctx.indent + 1))
                exit_conns = self.outgoing(flowchart, element.id, ConnectionType.EXIT)
                if exit_conns:
                    lines.append(ctx.line("else:"))
                    else_emitted = False
                    for conn in exit_conns:
                        target = flowchart.element_by_id(conn.target_id)
                        if target is None:
                            continue
                        sub = self._traverse(flowchart, target, ctx.child(1), visited)
                        if sub:
                            lines.extend(sub)
                            else_emitted = True
                    if not else_emitted:
                        lines.append(ctx.line("pass", ctx.indent + 1))
        elif etype == ElementType.LOOP:
            if element.condition:
                keyword = "for" if element.loop_type == "for" else "while"
                lines.append(ctx.line(f"{keyword} {element.condition}:"))
                body_emitted = False
                for conn in self.outgoing(flowchart, element.id, ConnectionType.BODY):
                    target = flowchart.element_by_id(conn.target_id)
                    if target is None:
                        continue
                    sub = self._traverse(flowchart, target, ctx.child(1), visited)
                    if sub:
                        lines.extend(sub)
                        body_emitted = True
                if not body_emitted:
                    lines.append(ctx.line("pass", ctx.indent + 1))
                for conn in self.outgoing(flowchart, element.id, ConnectionType.EXIT):
                    target = flowchart.element_by_id(conn.target_id)
                    if target is None:
                        continue
                    sub = self._traverse(flowchart, target, ctx, visited)
                    if sub:
                        lines.extend(sub)
        elif etype == ElementType.FUNCTION:
            if element.function_name:
                params = element.function_params or ""
                if element.decorator:
                    lines.append(ctx.line(f"@{element.decorator}"))
                if element.is_lambda:
                    lines.append(ctx.line(
                        f"{element.function_name} = lambda {params}: "
                    ))
                    if element.subflowchart:
                        ret = self._first_expression(element.subflowchart)
                        lines[-1] = lines[-1] + (ret or "None")
                else:
                    lines.append(ctx.line(
                        f"def {element.function_name}({params}):"
                    ))
                    body_emitted = False
                    if element.subflowchart is not None:
                        sub_entry = element.subflowchart.entry_element()
                        sub = self._traverse(
                            element.subflowchart, sub_entry,
                            ctx.child(1), set(),
                        ) if sub_entry is not None else []
                        if sub:
                            lines.extend(sub)
                            body_emitted = True
                    if not body_emitted:
                        lines.append(ctx.line("pass", ctx.indent + 1))
        elif etype == ElementType.CLASS:
            if element.class_name:
                parent = f"({element.parent_class})" if element.parent_class else ""
                lines.append(ctx.line(f"class {element.class_name}{parent}:"))
                class_emitted = False
                if element.attributes:
                    for attr, value in element.attributes.items():
                        lines.append(ctx.line(f"{attr} = {value!r}" if isinstance(value, str)
                                              else f"{attr} = {value}", ctx.indent + 1))
                        class_emitted = True
                for method in element.methods or []:
                    lines.append(ctx.line(
                        f"def {method.get('name', '')}({method.get('params', '')}):",
                        ctx.indent + 1,
                    ))
                    method_emitted = False
                    sub = method.get("subflowchart")
                    if sub is not None and sub.entry_element() is not None:
                        sub_lines = self._traverse(
                            sub, sub.entry_element(), ctx.child(2), set(),
                        )
                        if sub_lines:
                            lines.extend(sub_lines)
                            method_emitted = True
                    if not method_emitted:
                        lines.append(ctx.line("pass", ctx.indent + 2))
                    class_emitted = True
                if not class_emitted:
                    lines.append(ctx.line("pass", ctx.indent + 1))
        elif etype == ElementType.START_END:
            if element.return_value:
                lines.append(ctx.line(f"return {element.return_value}"))
        elif etype == ElementType.COMMENT:
            if element.code:
                lines.append(ctx.line(f"# {element.code}"))
        else:
            ext = self.registry.get(etype)
            if ext is not None:
                try:
                    lines.extend(ext.emit_code(element, ctx))
                except Exception as exc:
                    lines.append(ctx.line(f"# 擴充元素產生失敗：{exc}"))
                if getattr(ext, "indents_body", False):
                    body_emitted = False
                    for conn in self.outgoing(flowchart, element.id, ConnectionType.BODY):
                        target = flowchart.element_by_id(conn.target_id)
                        if target is None:
                            continue
                        sub = self._traverse(flowchart, target, ctx.child(1), visited)
                        if sub:
                            lines.extend(sub)
                            body_emitted = True
                    if not body_emitted:
                        lines.append(ctx.line("pass", ctx.indent + 1))
                    for conn in self.outgoing(flowchart, element.id, ConnectionType.EXIT):
                        target = flowchart.element_by_id(conn.target_id)
                        if target is None:
                            continue
                        sub = self._traverse(flowchart, target, ctx, visited)
                        if sub:
                            lines.extend(sub)

        for conn in calls:
            target = flowchart.element_by_id(conn.target_id)
            if target is None:
                continue
            params = conn.call_params or ""
            if target.type == ElementType.FUNCTION:
                lines.append(ctx.line(f"{target.function_name}({params})"))
            elif target.type == ElementType.CLASS:
                if "." in params:
                    obj, _, method = params.partition(".")
                    lines.append(ctx.line(f"{obj}.{method}"))
                else:
                    lines.append(ctx.line(f"{params}"))
            elif target.type == ElementType.EXTERNAL:
                module = target.opt("module") or ""
                qualname = target.opt("qualname") or ""
                full = f"{module}.{qualname}" if module else qualname
                lines.append(ctx.line(f"{full}({params})"))
        return lines

    def _first_expression(self, flowchart: Flowchart) -> str:
        element = flowchart.entry_element()
        while element is not None:
            if element.type in (ElementType.PROCESS, ElementType.INPUT) and element.code:
                return element.code
            if element.type == ElementType.OUTPUT and element.code:
                return element.code
            body = self.outgoing(flowchart, element.id, ConnectionType.BODY)
            element = flowchart.element_by_id(body[0].target_id) if body else None
        return ""
