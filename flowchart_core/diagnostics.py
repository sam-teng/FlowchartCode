from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .extensions import ExtensionRegistry
from .models import ConnectionType, ElementType, Flowchart
from .symbols import SymbolTable
from .validator import CodeValidator


@dataclass
class Diagnostic:
    severity: str  # error / warning / info
    element_id: Optional[str]
    message: str


def analyze(flowchart: Flowchart, symbols: SymbolTable,
            validator: Optional[CodeValidator] = None,
            registry: Optional[ExtensionRegistry] = None) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    if flowchart is None or not flowchart.elements:
        diagnostics.append(Diagnostic("info", None, "畫布是空的"))
        return diagnostics

    start_ends = [e for e in flowchart.elements if e.type == ElementType.START_END]
    if not start_ends:
        diagnostics.append(Diagnostic("warning", None, "缺少 Start/End 元素"))

    function_names: dict[str, str] = {}
    for element in flowchart.elements:
        _analyze_element(flowchart, element, symbols, validator, registry, diagnostics)
        if element.type == ElementType.FUNCTION and element.function_name:
            if element.function_name in function_names:
                diagnostics.append(Diagnostic(
                    "error", element.id,
                    f"函式名稱重複：{element.function_name}",
                ))
            function_names[element.function_name] = element.id
        if element.subflowchart:
            diagnostics.extend(
                analyze_subflow(element.subflowchart, symbols, validator, registry, element)
            )

    ids = {e.id for e in flowchart.elements}
    for conn in flowchart.connections:
        if conn.source_id not in ids or conn.target_id not in ids:
            diagnostics.append(Diagnostic(
                "error", None,
                f"連線指向不存在的元素：{conn.source_id} → {conn.target_id}",
            ))
    return diagnostics


def analyze_subflow(flowchart: Flowchart, symbols, validator, registry,
                    owner) -> list[Diagnostic]:
    result = []
    for element in flowchart.elements:
        _analyze_element(flowchart, element, symbols, validator, registry, result)
        if element.subflowchart:
            result.extend(analyze_subflow(
                element.subflowchart, symbols, validator, registry, element
            ))
    return result


def _analyze_element(flowchart: Flowchart, element, symbols, validator,
                     registry, diagnostics: list[Diagnostic]) -> None:
    etype = element.type
    outgoing = flowchart.outgoing
    body = outgoing(element.id, ConnectionType.BODY)
    exit_conns = outgoing(element.id, ConnectionType.EXIT)
    calls = outgoing(element.id, ConnectionType.CALL)
    incoming = flowchart.incoming(element.id)

    if etype not in (ElementType.COMMENT,) and not incoming and not body \
            and not calls and len(flowchart.elements) > 1:
        if not (etype == ElementType.FUNCTION or etype == ElementType.EXTERNAL):
            diagnostics.append(Diagnostic("warning", element.id, "孤立元素（無任何連線）"))

    if etype == ElementType.DECISION:
        if not element.condition or not str(element.condition).strip():
            diagnostics.append(Diagnostic("error", element.id, "Decision 缺少條件"))
        if not body:
            diagnostics.append(Diagnostic("warning", element.id, "Decision 沒有 Body（成立）分支"))
        if not exit_conns:
            diagnostics.append(Diagnostic("warning", element.id, "Decision 沒有 Exit（else）分支"))

    if etype == ElementType.LOOP:
        if not element.condition or not str(element.condition).strip():
            diagnostics.append(Diagnostic("error", element.id, "Loop 缺少條件"))
        if not body:
            diagnostics.append(Diagnostic("error", element.id, "Loop 沒有 Body 迴圈主體"))
        if element.loop_type not in ("for", "while"):
            diagnostics.append(Diagnostic("warning", element.id, "Loop 未選擇 for/while"))

    if etype in (ElementType.PROCESS, ElementType.INPUT, ElementType.OUTPUT,
                 ElementType.COMMENT):
        if not (element.code or "").strip() and etype != ElementType.COMMENT:
            diagnostics.append(Diagnostic("warning", element.id, f"{etype} 元素程式碼為空"))
        elif validator is not None and (element.code or "").strip():
            role = "condition" if etype == ElementType.DECISION else "statement"
            result = validator.validate_code(element.code, role=role, element=element)
            if not result.ok:
                diagnostics.append(Diagnostic("error", element.id, result.message))
            elif result.severity == "warning" and result.message:
                diagnostics.append(Diagnostic("warning", element.id, result.message))

    if etype in (ElementType.DECISION, ElementType.LOOP):
        if element.condition and validator is not None:
            result = validator.validate_code(element.condition, role="condition",
                                             element=element)
            if not result.ok:
                diagnostics.append(Diagnostic("error", element.id, result.message))

    if etype == ElementType.FUNCTION:
        if not element.function_name:
            diagnostics.append(Diagnostic("error", element.id, "Function 缺少函式名稱"))

    if etype == ElementType.CLASS:
        if not element.class_name:
            diagnostics.append(Diagnostic("error", element.id, "Class 缺少類別名稱"))

    if etype == ElementType.INPUT:
        if element.code and "input(" not in element.code and not any(
                t in element.code for t in ("int(", "float(", "str(")):
            diagnostics.append(Diagnostic(
                "warning", element.id, "Input 建議使用型別轉換（如 int(input())）"
            ))

    if etype == ElementType.EXTERNAL:
        module = element.opt("module") or ""
        if not module:
            diagnostics.append(Diagnostic("error", element.id, "外部函式缺少模組名"))

    if registry is not None:
        ext = registry.get(etype)
        if ext is not None:
            result = ext.validate(element, validator)
            if not result.ok:
                diagnostics.append(Diagnostic("error", element.id, result.message))

    ids = {e.id for e in flowchart.elements}
    for conn in calls:
        if conn.target_id not in ids:
            diagnostics.append(Diagnostic("error", element.id, "Call 目標不存在"))


def format_diagnostics(diagnostics: list[Diagnostic]) -> list[str]:
    icon = {"error": "[錯誤]", "warning": "[警告]", "info": "[資訊]"}
    return [f"{icon.get(d.severity, '')} {d.message}" for d in diagnostics]
