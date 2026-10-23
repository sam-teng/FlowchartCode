from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .concurrency import ThreadCounter
from .events import ExecutionEvent  # noqa: F401  (re-export convenience)
from .extensions import ExtensionRegistry, collect_declarations
from .models import Connection, ConnectionType, ElementType, Flowchart
from .symbols import SymbolTable
from .validator import CodeValidator, ValidationResult, validate_identifier


@dataclass
class ElementNode:
    element_id: str


@dataclass
class DecisionNode:
    element_id: str
    body: list = field(default_factory=list)
    otherwise: list = field(default_factory=list)


@dataclass
class LoopNode:
    element_id: str
    body: list = field(default_factory=list)
    exit_branches: list = field(default_factory=list)


@dataclass
class WithBodyNode:
    element_id: str
    body: list = field(default_factory=list)
    exit_branches: list = field(default_factory=list)


@dataclass
class ExecutionPlan:
    flowchart: Flowchart
    nodes: list = field(default_factory=list)
    functions: dict = field(default_factory=dict)
    method_nodes: dict = field(default_factory=dict)
    declarations: list = field(default_factory=list)
    validation_cache: dict = field(default_factory=dict)
    loop_limit: int = 10000
    symbols: Optional[SymbolTable] = None
    registry: Optional[ExtensionRegistry] = None
    _outgoing: dict = field(default_factory=dict)
    _incoming: dict = field(default_factory=dict)

    def build_index(self) -> None:
        self._outgoing = {}
        self._incoming = {}
        for conn in self.flowchart.connections:
            self._outgoing.setdefault((conn.source_id, conn.type), []).append(conn)
            self._incoming.setdefault((conn.target_id, conn.type), []).append(conn)
        for key, conns in self._outgoing.items():
            conns.sort(key=lambda c: (c.priority, c.target_id))
        for key, conns in self._incoming.items():
            conns.sort(key=lambda c: (c.priority, c.source_id))

    def outgoing(self, element_id: str, conn_type: Optional[str] = None) -> list[Connection]:
        if conn_type is not None:
            return list(self._outgoing.get((element_id, conn_type), []))
        result = []
        for ctype in ConnectionType.ALL:
            result.extend(self._outgoing.get((element_id, ctype), []))
        return result

    def incoming(self, element_id: str, conn_type: Optional[str] = None) -> list[Connection]:
        if conn_type is not None:
            return list(self._incoming.get((element_id, conn_type), []))
        result = []
        for ctype in ConnectionType.ALL:
            result.extend(self._incoming.get((element_id, ctype), []))
        return result

    def element(self, element_id: str):
        return self.flowchart.element_by_id(element_id)


def compile_plan(flowchart: Flowchart, symbols: SymbolTable,
                 validator: CodeValidator, registry: ExtensionRegistry,
                 loop_limit: int = 10000) -> ExecutionPlan:
    plan = ExecutionPlan(
        flowchart=flowchart,
        loop_limit=loop_limit,
        symbols=symbols,
        registry=registry,
    )
    plan.build_index()
    _cache_validations(flowchart, validator, registry, plan.validation_cache)
    plan.declarations = collect_declarations(flowchart, registry)
    entry = flowchart.entry_element()
    if entry is not None:
        plan.nodes = _compile_chain(flowchart, entry, set(), plan, registry)
    for element in flowchart.elements:
        if element.type == ElementType.FUNCTION and element.subflowchart is not None:
            sub_entry = element.subflowchart.entry_element()
            if sub_entry is not None:
                plan.functions[element.id] = _compile_chain(
                    element.subflowchart, sub_entry, set(), plan, registry
                )
        if element.type == ElementType.CLASS:
            for method in element.methods or []:
                sub = method.get("subflowchart")
                if sub is not None:
                    m_entry = sub.entry_element()
                    if m_entry is not None:
                        key = f"{element.id}:{method.get('name', '')}"
                        plan.method_nodes[key] = _compile_chain(
                            sub, m_entry, set(), plan, registry
                        )
    return plan


def _cache_validations(flowchart: Flowchart, validator: CodeValidator,
                       registry: ExtensionRegistry, cache: dict) -> None:
    for element in flowchart.elements:
        cache[element.id] = _validate_element(element, validator, registry)
        if element.subflowchart:
            _cache_validations(element.subflowchart, validator, registry, cache)
        for method in element.methods or []:
            if method.get("subflowchart"):
                _cache_validations(method["subflowchart"], validator, registry, cache)


def _validate_element(element, validator: CodeValidator,
                      registry: ExtensionRegistry) -> ValidationResult:
    etype = element.type
    if etype in (ElementType.PROCESS, ElementType.INPUT, ElementType.OUTPUT):
        if not (element.code or "").strip():
            return ValidationResult.warning(f"{etype} 程式碼為空")
        return validator.validate_code(
            element.code, role="statement", element=element, check_names=False
        )
    if etype in (ElementType.DECISION, ElementType.LOOP):
        if not (element.condition or "").strip():
            return ValidationResult.failure(f"{etype} 缺少條件")
        return validator.validate_code(
            element.condition, role="condition", element=element, check_names=False
        )
    if etype == ElementType.FUNCTION:
        if not element.function_name:
            return ValidationResult.failure("Function 缺少函式名稱")
        return validate_identifier(element.function_name)
    if etype == ElementType.CLASS:
        if not element.class_name:
            return ValidationResult.failure("Class 缺少類別名稱")
        return validate_identifier(element.class_name)
    if etype == ElementType.EXTERNAL:
        module = element.opt("module") or ""
        if not module:
            return ValidationResult.failure("外部函式缺少模組名")
        ok, msg = validator.policy.check_import(module)
        if not ok:
            return ValidationResult.failure(msg)
        return ValidationResult.success()
    ext = registry.get(etype) if registry else None
    if ext is not None:
        return ext.validate(element, validator)
    return ValidationResult.success()


def _compile_chain(flowchart: Flowchart, start, path: set, plan: ExecutionPlan,
                   registry: ExtensionRegistry) -> list:
    nodes: list = []
    current = start
    while current is not None and current.id not in path:
        path.add(current.id)
        node = _compile_element(flowchart, current, path, plan, registry)
        if node is not None:
            nodes.append(node)
        if current.type in (ElementType.DECISION, ElementType.LOOP):
            break
        ext = registry.get(current.type) if registry else None
        if ext is not None and getattr(ext, "indents_body", False):
            break
        body = plan.outgoing(current.id, ConnectionType.BODY)
        current = flowchart.element_by_id(body[0].target_id) if body else None
    return nodes


def _compile_element(flowchart: Flowchart, element, path: set,
                     plan: ExecutionPlan, registry: ExtensionRegistry):
    etype = element.type
    if etype == ElementType.DECISION:
        body_nodes = _compile_targets(flowchart, plan, element.id, ConnectionType.BODY, path, registry)
        exit_nodes = _compile_targets(flowchart, plan, element.id, ConnectionType.EXIT, path, registry)
        return DecisionNode(element.id, body=body_nodes, otherwise=exit_nodes)
    if etype == ElementType.LOOP:
        body_nodes = _compile_targets(flowchart, plan, element.id, ConnectionType.BODY, path, registry)
        exit_nodes = _compile_targets(flowchart, plan, element.id, ConnectionType.EXIT, path, registry)
        return LoopNode(element.id, body=body_nodes, exit_branches=exit_nodes)
    ext = registry.get(etype) if registry else None
    if ext is not None and getattr(ext, "indents_body", False):
        body_nodes = _compile_targets(flowchart, plan, element.id, ConnectionType.BODY, path, registry)
        exit_nodes = _compile_targets(flowchart, plan, element.id, ConnectionType.EXIT, path, registry)
        return WithBodyNode(element.id, body=body_nodes, exit_branches=exit_nodes)
    return ElementNode(element.id)


def _compile_targets(flowchart: Flowchart, plan: ExecutionPlan, source_id: str,
                     conn_type: str, path: set, registry: ExtensionRegistry) -> list:
    branches: list = []
    for conn in plan.outgoing(source_id, conn_type):
        target = flowchart.element_by_id(conn.target_id)
        if target is None:
            continue
        nodes = _compile_chain(flowchart, target, set(path), plan, registry)
        branches.append((target.id, nodes))
    return branches
