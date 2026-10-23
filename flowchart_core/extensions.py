from __future__ import annotations

import importlib
import importlib.util
import os
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Optional

from .events import ExecutionEvent
from .validator import ValidationResult


@dataclass
class FieldSpec:
    name: str
    label: str
    kind: str = "text"
    default: Any = ""
    choices: list = field(default_factory=list)


@dataclass
class ElementMeta:
    type_name: str
    label: str
    color: str = "#cccccc"
    shape: str = "rectangle"
    fields: list = field(default_factory=list)
    has_subflowchart: bool = False
    in_palette: bool = True


class ElementExtension:
    meta: ElementMeta

    def validate(self, element, validator) -> ValidationResult:
        return ValidationResult.success()

    def emit_declarations(self, flowchart, symbols) -> list[str]:
        return []

    def emit_code(self, element, ctx) -> list[str]:
        raise NotImplementedError

    def execute(self, element, ctx) -> Iterator[ExecutionEvent]:
        raise NotImplementedError
        yield  # pragma: no cover


class ExtensionRegistry:
    def __init__(self):
        self._by_type: dict[str, ElementExtension] = {}
        self.load_errors: list[tuple[str, str]] = []

    def register(self, extension: ElementExtension) -> None:
        meta = getattr(extension, "meta", None)
        if meta is None or not getattr(meta, "type_name", None):
            raise ValueError("擴充缺少 meta.type_name")
        self._by_type[meta.type_name] = extension

    def unregister(self, type_name: str) -> None:
        self._by_type.pop(type_name, None)

    def get(self, type_name: str) -> Optional[ElementExtension]:
        return self._by_type.get(type_name)

    def all_extensions(self) -> list[ElementExtension]:
        return list(self._by_type.values())

    def palette_metas(self) -> list[ElementMeta]:
        return [
            ext.meta for ext in self._by_type.values()
            if getattr(ext.meta, "in_palette", True)
        ]

    def meta_for(self, type_name: str) -> Optional[ElementMeta]:
        ext = self.get(type_name)
        return ext.meta if ext else None

    def load_directory(self, directory: str) -> None:
        self.load_errors.clear()
        if not os.path.isdir(directory):
            return
        for filename in sorted(os.listdir(directory)):
            if not filename.endswith(".py") or filename.startswith("_"):
                continue
            path = os.path.join(directory, filename)
            module_name = f"flowchart_extension_{os.path.splitext(filename)[0]}"
            try:
                spec = importlib.util.spec_from_file_location(module_name, path)
                if spec is None or spec.loader is None:
                    continue
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if hasattr(module, "register"):
                    module.register(self)
                elif hasattr(module, "EXTENSIONS"):
                    for ext in module.EXTENSIONS:
                        self.register(ext)
                else:
                    self.load_errors.append(
                        (filename, "缺少 register(registry) 或 EXTENSIONS")
                    )
            except Exception as exc:
                self.load_errors.append((filename, f"{exc}\n{traceback.format_exc()}"))


def collect_declarations(flowchart, registry: ExtensionRegistry) -> list[str]:
    seen: set[str] = set()
    lines: list[str] = []

    def visit(fc) -> None:
        if fc is None:
            return
        for element in fc.elements:
            ext = registry.get(element.type)
            if ext is None:
                continue
            try:
                for line in ext.emit_declarations(fc, None) or []:
                    if line not in seen:
                        seen.add(line)
                        lines.append(line)
            except Exception:
                continue
            if element.subflowchart:
                visit(element.subflowchart)
            for method in element.methods or []:
                if method.get("subflowchart"):
                    visit(method["subflowchart"])

    visit(flowchart)
    return lines
