from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SymbolTable:
    variables: dict = field(default_factory=dict)
    defined_variables: set = field(default_factory=set)
    imported_names: dict = field(default_factory=dict)
    function_signatures: dict = field(default_factory=dict)
    class_signatures: dict = field(default_factory=dict)
    libraries: list = field(default_factory=list)
    custom_modules: list = field(default_factory=list)

    def update_from_code(self, code: str) -> None:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.defined_variables.add(target.id)
            elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
                if isinstance(getattr(node, "target", None), ast.Name):
                    self.defined_variables.add(node.target.id)
            elif isinstance(node, ast.For):
                if isinstance(node.target, ast.Name):
                    self.defined_variables.add(node.target.id)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    self.imported_names[alias.asname or alias.name.split(".")[0]] = alias.name
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    self.imported_names[alias.asname or alias.name] = (
                        f"{node.module}.{alias.name}"
                    )

    def register_function(self, name: str, params: str) -> None:
        if name:
            self.function_signatures[name] = _count_params(params)

    def register_class(self, name: str, attributes: Optional[dict], methods: list) -> None:
        if not name:
            return
        self.class_signatures[name] = {
            "attributes": dict(attributes or {}),
            "methods": {
                m.get("name", ""): _count_params(m.get("params", ""))
                for m in (methods or [])
            },
        }

    def is_known(self, name: str) -> bool:
        return (
            name in self.defined_variables
            or name in self.variables
            or name in self.imported_names
            or name in self.function_signatures
            or name in self.class_signatures
            or name in self.libraries
        )

    def rebuild_from_flowchart(self, flowchart) -> None:
        self.defined_variables.clear()
        self.function_signatures.clear()
        self.class_signatures.clear()
        self.imported_names.clear()
        for name in self.variables:
            self.defined_variables.add(name)
        for lib in self.libraries:
            self.imported_names[lib] = lib
        for mod_name, _path in self.custom_modules:
            self.imported_names[mod_name] = mod_name
        _walk_flowchart_symbols(flowchart, self)

    def snapshot(self) -> dict:
        return {
            "variables": dict(self.variables),
            "defined_variables": set(self.defined_variables),
            "imported_names": dict(self.imported_names),
            "function_signatures": dict(self.function_signatures),
            "class_signatures": {k: dict(v) for k, v in self.class_signatures.items()},
            "libraries": list(self.libraries),
            "custom_modules": [tuple(m) for m in self.custom_modules],
        }

    def restore(self, snap: dict) -> None:
        self.variables = dict(snap.get("variables") or {})
        self.defined_variables = set(snap.get("defined_variables") or set())
        self.imported_names = dict(snap.get("imported_names") or {})
        self.function_signatures = dict(snap.get("function_signatures") or {})
        self.class_signatures = {
            k: dict(v) for k, v in (snap.get("class_signatures") or {}).items()
        }
        self.libraries = list(snap.get("libraries") or [])
        self.custom_modules = [tuple(m) for m in snap.get("custom_modules") or []]


def _walk_flowchart_symbols(flowchart, symbols: SymbolTable) -> None:
    if flowchart is None:
        return
    for element in flowchart.elements:
        if element.type in ("Process", "Input", "Output") and element.code:
            symbols.update_from_code(element.code)
        if element.type == "Function" and element.function_name:
            symbols.register_function(element.function_name, element.function_params or "")
        if element.type == "Class" and element.class_name:
            symbols.register_class(
                element.class_name, element.attributes, element.methods or []
            )
        if element.subflowchart:
            _walk_flowchart_symbols(element.subflowchart, symbols)
        for method in element.methods or []:
            if method.get("subflowchart"):
                _walk_flowchart_symbols(method["subflowchart"], symbols)


def _count_params(params: str) -> int:
    return len([p for p in (params or "").split(",") if p.strip()])
