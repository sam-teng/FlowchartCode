from __future__ import annotations

import ast
import uuid
from typing import Optional, Tuple, List, Dict, Any

from .models import Connection, ConnectionType, Element, ElementType, Flowchart, Project


def _expr_to_str(node: ast.AST) -> str:
    """Convert an AST expression or statement to a code string."""
    try:
        return ast.unparse(node).strip()
    except Exception:
        return ""


class ASTToFlowchartConverter:
    """Convert Python code into a Flowchart / Project model."""

    def __init__(self, code: str):
        self.code = code
        self.flowchart = Flowchart()
        self.variables: Dict[str, Any] = {}
        self.libraries: List[str] = []
        self.custom_modules: List[Tuple[str, str]] = []

    def convert(self) -> Project:
        tree = ast.parse(self.code)
        
        # 1. First pass: extract imports and top-level simple literal assignments
        filtered_body: List[ast.stmt] = []
        for stmt in tree.body:
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    name = alias.asname or alias.name
                    if name not in self.libraries:
                        self.libraries.append(name)
            elif isinstance(stmt, ast.ImportFrom):
                mod = stmt.module or ""
                for alias in stmt.names:
                    name = f"{mod}.{alias.name}" if mod else alias.name
                    if name not in self.libraries:
                        self.libraries.append(name)
            elif isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                var_name = stmt.targets[0].id
                try:
                    val = ast.literal_eval(stmt.value)
                    self.variables[var_name] = val
                    filtered_body.append(stmt)
                except Exception:
                    filtered_body.append(stmt)
            else:
                filtered_body.append(stmt)

        # 2. Convert function/class definitions and executable body statements
        start_el = Element(type=ElementType.START_END)
        self.flowchart.add_element(start_el)

        curr_tails = [start_el]

        for stmt in filtered_body:
            if isinstance(stmt, ast.FunctionDef):
                fn_el = self._convert_function_def(stmt)
                self.flowchart.add_element(fn_el)
            elif isinstance(stmt, ast.ClassDef):
                cls_el = self._convert_class_def(stmt)
                self.flowchart.add_element(cls_el)
            else:
                new_heads, new_tails = self._convert_stmt(stmt, self.flowchart)
                if new_heads:
                    for tail in curr_tails:
                        for head in new_heads:
                            self.flowchart.add_connection(Connection(tail.id, head.id, ConnectionType.BODY))
                    curr_tails = new_tails

        # Add End node
        end_el = Element(type=ElementType.START_END)
        self.flowchart.add_element(end_el)
        for tail in curr_tails:
            self.flowchart.add_connection(Connection(tail.id, end_el.id, ConnectionType.BODY))

        # Check for function calls to link Call connections
        self._link_function_calls(self.flowchart)

        # 3. Layout elements
        self._auto_layout(self.flowchart)

        return Project(
            flowchart=self.flowchart,
            variables=self.variables,
            libraries=self.libraries,
            custom_modules=self.custom_modules,
        )

    def _convert_function_def(self, node: ast.FunctionDef) -> Element:
        params = [arg.arg for arg in node.args.args]
        decorator = ""
        if node.decorator_list:
            decorator = _expr_to_str(node.decorator_list[0])

        fn_el = Element(
            type=ElementType.FUNCTION,
            function_name=node.name,
            function_params=", ".join(params),
            decorator=decorator if decorator else None,
        )

        subfc = Flowchart()
        sub_start = Element(type=ElementType.START_END)
        subfc.add_element(sub_start)
        curr_tails = [sub_start]

        for stmt in node.body:
            new_heads, new_tails = self._convert_stmt(stmt, subfc)
            if new_heads:
                for tail in curr_tails:
                    for head in new_heads:
                        subfc.add_connection(Connection(tail.id, head.id, ConnectionType.BODY))
                curr_tails = new_tails

        sub_end = Element(type=ElementType.START_END)
        subfc.add_element(sub_end)
        for tail in curr_tails:
            subfc.add_connection(Connection(tail.id, sub_end.id, ConnectionType.BODY))

        self._auto_layout(subfc)
        fn_el.subflowchart = subfc
        return fn_el

    def _convert_class_def(self, node: ast.ClassDef) -> Element:
        parent_class = ""
        if node.bases:
            parent_class = _expr_to_str(node.bases[0])

        attributes = {}
        methods = []

        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        try:
                            attributes[target.id] = ast.literal_eval(item.value)
                        except Exception:
                            attributes[target.id] = _expr_to_str(item.value)
            elif isinstance(item, ast.FunctionDef):
                params = [arg.arg for arg in item.args.args]
                m_subfc = Flowchart()
                m_start = Element(type=ElementType.START_END)
                m_subfc.add_element(m_start)
                curr_tails = [m_start]
                for stmt in item.body:
                    new_heads, new_tails = self._convert_stmt(stmt, m_subfc)
                    if new_heads:
                        for tail in curr_tails:
                            for head in new_heads:
                                m_subfc.add_connection(Connection(tail.id, head.id, ConnectionType.BODY))
                        curr_tails = new_tails
                m_end = Element(type=ElementType.START_END)
                m_subfc.add_element(m_end)
                for tail in curr_tails:
                    m_subfc.add_connection(Connection(tail.id, m_end.id, ConnectionType.BODY))
                self._auto_layout(m_subfc)

                methods.append({
                    "name": item.name,
                    "params": ", ".join(params),
                    "subflowchart": m_subfc,
                })

        return Element(
            type=ElementType.CLASS,
            class_name=node.name,
            parent_class=parent_class or None,
            attributes=attributes,
            methods=methods,
        )

    def _convert_stmt(self, stmt: ast.stmt, fc: Flowchart) -> Tuple[List[Element], List[Element]]:
        """
        Convert a statement into element(s) in flowchart `fc`.
        Returns (head_elements, tail_elements) representing entry and exit points.
        """
        if isinstance(stmt, ast.If):
            return self._convert_if(stmt, fc)
        elif isinstance(stmt, ast.While):
            return self._convert_while(stmt, fc)
        elif isinstance(stmt, ast.For):
            return self._convert_for(stmt, fc)
        elif isinstance(stmt, ast.Return):
            ret_val = _expr_to_str(stmt.value) if stmt.value else ""
            el = Element(type=ElementType.START_END, return_value=ret_val)
            fc.add_element(el)
            return [el], []
        elif isinstance(stmt, ast.Expr):
            val = stmt.value
            if isinstance(val, ast.Call) and isinstance(val.func, ast.Name) and val.func.id == "print":
                args_str = ", ".join(_expr_to_str(a) for a in val.args)
                el = Element(type=ElementType.OUTPUT, code=args_str)
                fc.add_element(el)
                return [el], [el]
            elif isinstance(val, ast.Constant) and isinstance(val.value, str):
                el = Element(type=ElementType.COMMENT, code=val.value.strip())
                fc.add_element(el)
                return [el], [el]
            else:
                code_str = _expr_to_str(stmt)
                el = Element(type=ElementType.PROCESS, code=code_str)
                fc.add_element(el)
                return [el], [el]
        elif isinstance(stmt, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            code_str = _expr_to_str(stmt)
            if "input(" in code_str:
                el = Element(type=ElementType.INPUT, code=code_str)
            else:
                el = Element(type=ElementType.PROCESS, code=code_str)
            fc.add_element(el)
            return [el], [el]
        elif isinstance(stmt, ast.Pass):
            return [], []
        else:
            code_str = _expr_to_str(stmt)
            el = Element(type=ElementType.PROCESS, code=code_str)
            fc.add_element(el)
            return [el], [el]

    def _convert_if(self, node: ast.If, fc: Flowchart) -> Tuple[List[Element], List[Element]]:
        cond_str = _expr_to_str(node.test)
        decision_el = Element(type=ElementType.DECISION, condition=cond_str)
        fc.add_element(decision_el)

        body_tails: List[Element] = []
        prev_body = [decision_el]
        for s in node.body:
            h, t = self._convert_stmt(s, fc)
            if h:
                for p in prev_body:
                    ctype = ConnectionType.BODY
                    for head in h:
                        fc.add_connection(Connection(p.id, head.id, ctype))
                prev_body = t
        body_tails = prev_body

        else_tails: List[Element] = []
        if node.orelse:
            prev_else = [decision_el]
            first_else = True
            for s in node.orelse:
                h, t = self._convert_stmt(s, fc)
                if h:
                    for p in prev_else:
                        ctype = ConnectionType.EXIT if first_else and p == decision_el else ConnectionType.BODY
                        for head in h:
                            fc.add_connection(Connection(p.id, head.id, ctype))
                    prev_else = t
                    first_else = False
            else_tails = prev_else
        else:
            else_tails = [decision_el]

        combined_tails = []
        for el in body_tails:
            if el not in combined_tails:
                combined_tails.append(el)
        for el in else_tails:
            if el not in combined_tails:
                combined_tails.append(el)

        return [decision_el], combined_tails

    def _convert_while(self, node: ast.While, fc: Flowchart) -> Tuple[List[Element], List[Element]]:
        cond_str = _expr_to_str(node.test)
        loop_el = Element(type=ElementType.LOOP, condition=cond_str, loop_type="while")
        fc.add_element(loop_el)

        prev = [loop_el]
        for s in node.body:
            h, t = self._convert_stmt(s, fc)
            if h:
                for p in prev:
                    ctype = ConnectionType.BODY
                    for head in h:
                        fc.add_connection(Connection(p.id, head.id, ctype))
                prev = t

        return [loop_el], [loop_el]

    def _convert_for(self, node: ast.For, fc: Flowchart) -> Tuple[List[Element], List[Element]]:
        target_str = _expr_to_str(node.target)
        iter_str = _expr_to_str(node.iter)
        cond_str = f"{target_str} in {iter_str}"
        loop_el = Element(type=ElementType.LOOP, condition=cond_str, loop_type="for")
        fc.add_element(loop_el)

        prev = [loop_el]
        for s in node.body:
            h, t = self._convert_stmt(s, fc)
            if h:
                for p in prev:
                    ctype = ConnectionType.BODY
                    for head in h:
                        fc.add_connection(Connection(p.id, head.id, ctype))
                prev = t

        return [loop_el], [loop_el]

    def _link_function_calls(self, fc: Flowchart) -> None:
        """Find calls to defined functions and create Call connections."""
        fn_map = {e.function_name: e for e in fc.elements if e.type == ElementType.FUNCTION and e.function_name}
        if not fn_map:
            return

        for el in list(fc.elements):
            if el.type not in (ElementType.PROCESS, ElementType.OUTPUT, ElementType.INPUT) or not el.code:
                continue
            try:
                tree = ast.parse(el.code)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        fn_name = node.func.id
                        if fn_name in fn_map:
                            target_fn = fn_map[fn_name]
                            args = ", ".join(_expr_to_str(a) for a in node.args)
                            fc.add_connection(Connection(
                                source_id=el.id,
                                target_id=target_fn.id,
                                type=ConnectionType.CALL,
                                call_params=args,
                            ))
            except Exception:
                pass

    def _auto_layout(self, fc: Flowchart) -> None:
        """
        Simple topological layered layout for flowchart elements.
        Positions main flow vertically (center x=350), with branches spreading horizontally.
        """
        if not fc.elements:
            return

        containers = [e for e in fc.elements if e.type in (ElementType.FUNCTION, ElementType.CLASS)]
        main_elements = [e for e in fc.elements if e.type not in (ElementType.FUNCTION, ElementType.CLASS)]

        entry = None
        for e in main_elements:
            if e.type == ElementType.START_END and not fc.incoming(e.id):
                entry = e
                break
        if not entry and main_elements:
            entry = main_elements[0]

        levels: Dict[str, int] = {}
        x_offsets: Dict[str, float] = {}
        queue: List[Tuple[Element, int, float]] = []
        if entry:
            queue.append((entry, 0, 0.0))
            levels[entry.id] = 0
            x_offsets[entry.id] = 0.0

        visited = set()
        while queue:
            curr, lvl, x_off = queue.pop(0)
            if curr.id in visited:
                continue
            visited.add(curr.id)
            levels[curr.id] = max(levels.get(curr.id, 0), lvl)
            x_offsets[curr.id] = x_off

            out_conns = fc.outgoing(curr.id)
            body_conns = [c for c in out_conns if c.type == ConnectionType.BODY]
            exit_conns = [c for c in out_conns if c.type == ConnectionType.EXIT]

            if curr.type == ElementType.DECISION:
                for c in body_conns:
                    t = fc.element_by_id(c.target_id)
                    if t and t.id not in visited:
                        queue.append((t, lvl + 1, x_off - 80))
                for c in exit_conns:
                    t = fc.element_by_id(c.target_id)
                    if t and t.id not in visited:
                        queue.append((t, lvl + 1, x_off + 120))
            elif curr.type == ElementType.LOOP:
                for c in body_conns:
                    t = fc.element_by_id(c.target_id)
                    if t and t.id not in visited:
                        queue.append((t, lvl + 1, x_off))
                for c in exit_conns:
                    t = fc.element_by_id(c.target_id)
                    if t and t.id not in visited:
                        queue.append((t, lvl + 2, x_off + 100))
            else:
                for c in out_conns:
                    if c.type in (ConnectionType.BODY, ConnectionType.EXIT):
                        t = fc.element_by_id(c.target_id)
                        if t and t.id not in visited:
                            queue.append((t, lvl + 1, x_off))

        curr_unvisited_lvl = max(levels.values(), default=0) + 1
        for e in main_elements:
            if e.id not in levels:
                levels[e.id] = curr_unvisited_lvl
                x_offsets[e.id] = 0.0
                curr_unvisited_lvl += 1

        start_x = 350.0
        start_y = 60.0
        y_step = 85.0

        for e in main_elements:
            lvl = levels.get(e.id, 0)
            off = x_offsets.get(e.id, 0.0)
            e.x = start_x + off
            e.y = start_y + lvl * y_step

        container_x = 650.0
        container_y = 60.0
        for i, c in enumerate(containers):
            c.x = container_x
            c.y = container_y + i * 110.0


def code_to_project(code: str) -> Project:
    """Parse Python code string into a Project containing Flowchart, variables, and libraries."""
    converter = ASTToFlowchartConverter(code)
    return converter.convert()


def code_to_flowchart(code: str) -> Flowchart:
    """Convenience helper to convert Python code string directly to Flowchart."""
    return code_to_project(code).flowchart
