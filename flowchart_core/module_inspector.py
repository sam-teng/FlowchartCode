from __future__ import annotations

import importlib
import inspect
import sys
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CallableInfo:
    module: str
    qualname: str
    name: str
    kind: str
    signature: str = ""
    doc: str = ""
    source_file: str = ""
    params: list = field(default_factory=list)

    @property
    def full_name(self) -> str:
        return f"{self.module}.{self.qualname}" if self.module else self.qualname


_module_cache: dict[str, list[CallableInfo]] = {}
_info_cache: dict[str, Optional[CallableInfo]] = {}


def clear_cache() -> None:
    _module_cache.clear()
    _info_cache.clear()


def import_module_safe(module_name: str):
    try:
        return importlib.import_module(module_name)
    except Exception:
        return None


def _format_signature(obj) -> str:
    try:
        return str(inspect.signature(obj))
    except (ValueError, TypeError):
        return "(...)"


def _doc_summary(doc: Optional[str], limit: int = 200) -> str:
    if not doc:
        return ""
    text = inspect.cleandoc(doc)
    return text[:limit]


def describe_callable(module_name: str, qualname: str, obj) -> CallableInfo:
    if inspect.isclass(obj):
        kind = "class"
    elif inspect.isbuiltin(obj) or inspect.ismethod(obj):
        kind = "builtin"
    elif inspect.isfunction(obj):
        kind = "function"
    elif callable(obj):
        kind = "callable"
    else:
        kind = "value"
    source_file = ""
    try:
        source_file = inspect.getsourcefile(obj) or ""
    except (TypeError, OSError):
        source_file = ""
    params = []
    if kind in ("function", "builtin", "method"):
        try:
            for name, param in inspect.signature(obj).parameters.items():
                params.append({
                    "name": name,
                    "default": str(param.default) if param.default is not inspect.Parameter.empty else "",
                    "kind": str(param.kind),
                })
        except (ValueError, TypeError):
            params = []
    return CallableInfo(
        module=module_name,
        qualname=qualname,
        name=qualname.split(".")[-1],
        kind=kind,
        signature=_format_signature(obj),
        doc=_doc_summary(obj.__doc__),
        source_file=source_file,
        params=params,
    )


def list_module_callables(module_name: str) -> list[CallableInfo]:
    if module_name in _module_cache:
        return _module_cache[module_name]
    module = import_module_safe(module_name)
    results: list[CallableInfo] = []
    if module is not None:
        for name, obj in inspect.getmembers(module):
            if name.startswith("_"):
                continue
            if not (inspect.isfunction(obj) or inspect.isclass(obj)
                    or inspect.isbuiltin(obj) or callable(obj)):
                continue
            if getattr(obj, "__module__", None) not in (None, module_name) \
                    and not inspect.isbuiltin(obj):
                if not inspect.isclass(obj):
                    continue
            results.append(describe_callable(module_name, name, obj))
        results.sort(key=lambda info: (info.kind, info.name))
    _module_cache[module_name] = results
    return results


def get_callable_info(qualname_path: str) -> Optional[CallableInfo]:
    qualname_path = (qualname_path or "").strip()
    if not qualname_path:
        return None
    if qualname_path in _info_cache:
        return _info_cache[qualname_path]
    parts = qualname_path.split(".")
    info = None
    for split in range(len(parts), 0, -1):
        module_name = ".".join(parts[:split])
        remainder = parts[split:]
        module = import_module_safe(module_name)
        if module is None:
            continue
        obj = module
        ok = True
        for attr in remainder:
            obj = getattr(obj, attr, None)
            if obj is None:
                ok = False
                break
        if ok:
            info = describe_callable(module_name, ".".join(remainder) or module_name, obj)
            break
    _info_cache[qualname_path] = info
    return info


def list_installed_distributions() -> list[tuple[str, str]]:
    try:
        from importlib import metadata
        items = []
        for dist in metadata.distributions():
            name = dist.metadata["Name"] or ""
            version = dist.version or ""
            if name:
                items.append((name, version))
        items.sort(key=lambda t: t[0].lower())
        return items
    except Exception:
        return []
