from __future__ import annotations

from typing import Optional

from .concurrency import CodegenContext, ThreadCounter
from .extensions import ExtensionRegistry, collect_declarations
from .languages import LanguageBackend, get_language
from .models import ConnectionType, ElementType, Flowchart
from .symbols import SymbolTable


class CodeGenerator:
    def __init__(self, flowchart: Flowchart, symbols: Optional[SymbolTable] = None,
                 registry: Optional[ExtensionRegistry] = None,
                 libraries=None, custom_modules=None, variables=None,
                 language: Optional[LanguageBackend | str] = None):
        self.flowchart = flowchart
        self.symbols = symbols or SymbolTable()
        self.registry = registry or ExtensionRegistry()
        self.libraries = list(libraries or [])
        self.custom_modules = list(custom_modules or [])
        self.variables = dict(variables or {})
        if isinstance(language, LanguageBackend):
            self.lang = language
        else:
            self.lang = get_language(language)
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

        header: list[str] = []
        threading_line = self.lang.threading_header()
        if threading_line:
            header.append(threading_line)
        header.extend(self.lang.header_imports(self.libraries, self.custom_modules))

        lines: list[str] = []
        lines.extend(header)
        lines.append("")
        emitted_decls: list[str] = []
        if self.lang.supports_extensions:
            for decl in declarations:
                emitted = self.lang.extension_declaration(decl)
                if emitted is not None:
                    emitted_decls.append(emitted)
        lines.extend(emitted_decls)
        if emitted_decls:
            lines.append("")
        for name, value in self.variables.items():
            lines.append(self.lang.assignment(name, value))
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

    def _emit_block_body(self, flowchart: Flowchart, element, ctx: CodegenContext,
                         visited: set) -> tuple[list[str], bool]:
        """產生 BODY 連線子流程，回傳 (行, 是否有內容)。"""
        lines: list[str] = []
        emitted = False
        for conn in self.outgoing(flowchart, element.id, ConnectionType.BODY):
            target = flowchart.element_by_id(conn.target_id)
            if target is None:
                continue
            sub = self._traverse(flowchart, target, ctx.child(1), visited)
            if sub:
                lines.extend(sub)
                emitted = True
        return lines, emitted

    def _maybe_empty(self, ctx: CodegenContext, emitted: bool) -> list[str]:
        if emitted:
            return []
        empty = self.lang.empty_body(ctx.indent + 1)
        return [ctx.line(empty, ctx.indent + 1)] if empty else []

    def _close(self, ctx: CodegenContext) -> list[str]:
        closed = self.lang.block_close(ctx.indent)
        return [ctx.line(c, ctx.indent) for c in closed] if closed else []

    def _emit_element(self, flowchart: Flowchart, element, ctx: CodegenContext,
                      visited: set) -> list[str]:
        lines: list[str] = []
        lang = self.lang
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
                lines.append(ctx.line(lang.print_stmt(element.code)))
        elif etype == ElementType.DECISION:
            if element.condition:
                lines.append(ctx.line(lang.if_open(element.condition)))
                body_lines, body_emitted = self._emit_block_body(
                    flowchart, element, ctx, visited)
                lines.extend(body_lines)
                lines.extend(self._maybe_empty(ctx, body_emitted))
                exit_conns = self.outgoing(flowchart, element.id, ConnectionType.EXIT)
                if exit_conns:
                    lines.append(ctx.line(lang.else_open()))
                    else_lines: list[str] = []
                    else_emitted = False
                    for conn in exit_conns:
                        target = flowchart.element_by_id(conn.target_id)
                        if target is None:
                            continue
                        sub = self._traverse(flowchart, target, ctx.child(1), visited)
                        if sub:
                            else_lines.extend(sub)
                            else_emitted = True
                    lines.extend(else_lines)
                    lines.extend(self._maybe_empty(ctx, else_emitted))
                lines.extend(self._close(ctx))
        elif etype == ElementType.LOOP:
            if element.condition:
                opener = (lang.for_open if element.loop_type == "for"
                          else lang.while_open)
                lines.append(ctx.line(opener(element.condition)))
                body_lines, body_emitted = self._emit_block_body(
                    flowchart, element, ctx, visited)
                lines.extend(body_lines)
                lines.extend(self._maybe_empty(ctx, body_emitted))
                lines.extend(self._close(ctx))
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
                    dec = lang.decorator_line(element.decorator)
                    if dec:
                        lines.append(ctx.line(dec))
                if element.is_lambda:
                    lines.append(ctx.line(
                        lang.lambda_head(element.function_name, params)
                    ))
                    if element.subflowchart:
                        ret = self._first_expression(element.subflowchart)
                        lines[-1] = lines[-1] + (ret or "None") + lang.lambda_tail()
                else:
                    lines.append(ctx.line(
                        lang.function_open(element.function_name, params)
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
                    lines.extend(self._maybe_empty(ctx, body_emitted))
                    lines.extend(self._close(ctx))
        elif etype == ElementType.CLASS:
            if element.class_name:
                lines.append(ctx.line(
                    lang.class_open(element.class_name, element.parent_class or "")
                ))
                class_emitted = False
                if element.attributes:
                    for attr, value in element.attributes.items():
                        lines.append(ctx.line(
                            lang.class_attribute(attr, value), ctx.indent + 1))
                        class_emitted = True
                for method in element.methods or []:
                    lines.append(ctx.line(
                        lang.method_open(method.get('name', ''), method.get('params', '')),
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
                    method_ctx = ctx.child(1)
                    lines.extend(self._maybe_empty(method_ctx, method_emitted))
                    closed = lang.block_close(method_ctx.indent)
                    for c in closed:
                        lines.append(method_ctx.line(c))
                    class_emitted = True
                if not class_emitted:
                    lines.extend(self._maybe_empty(ctx, False))
                lines.extend(self._close(ctx))
        elif etype == ElementType.START_END:
            if element.return_value:
                lines.append(ctx.line(lang.return_stmt(element.return_value)))
        elif etype == ElementType.COMMENT:
            if element.code:
                lines.append(ctx.line(lang.comment(element.code)))
        else:
            ext = self.registry.get(etype)
            if ext is not None:
                label = getattr(getattr(ext, "meta", None), "label", str(etype))
                if lang.supports_extensions:
                    try:
                        lines.extend(lang.extension_code(element, ctx, ext))
                    except Exception as exc:
                        lines.append(ctx.line(lang.comment(f"擴充元素產生失敗：{exc}")))
                else:
                    lines.append(ctx.line(lang.unsupported_extension(label)))
                if getattr(ext, "indents_body", False):
                    body_lines, body_emitted = self._emit_block_body(
                        flowchart, element, ctx, visited)
                    if lang.supports_extensions:
                        lines.extend(body_lines)
                        lines.extend(self._maybe_empty(ctx, body_emitted))
                    elif body_emitted:
                        opener = lang.block_open(label)
                        if opener is not None:
                            lines.append(ctx.line(opener))
                            lines.extend(body_lines)
                            lines.extend(self._close(ctx))
                        else:
                            lines.extend(body_lines)
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
