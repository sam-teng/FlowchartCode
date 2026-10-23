from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Optional


class ElementType:
    PROCESS = "Process"
    DECISION = "Decision"
    LOOP = "Loop"
    START_END = "Start/End"
    INPUT = "Input"
    OUTPUT = "Output"
    FUNCTION = "Function"
    CLASS = "Class"
    COMMENT = "Comment"
    THREAD = "Thread/Task"
    SYNC_EVENT = "SyncEvent"
    SYNC_LOCK = "SyncLock"
    SYNC_SEMAPHORE = "SyncSemaphore"
    SYNC_BARRIER = "SyncBarrier"
    EXTERNAL = "External"

    BUILTIN = frozenset({
        PROCESS, DECISION, LOOP, START_END, INPUT, OUTPUT, FUNCTION, CLASS,
        COMMENT, THREAD, SYNC_EVENT, SYNC_LOCK, SYNC_SEMAPHORE, SYNC_BARRIER,
        EXTERNAL,
    })
    BRANCHING = frozenset({DECISION, LOOP})
    CONTAINERS = frozenset({FUNCTION, CLASS})


class ConnectionType:
    BODY = "Body"
    EXIT = "Exit"
    CALL = "Call"
    ALL = (BODY, EXIT, CALL)


@dataclass
class Connection:
    source_id: str
    target_id: str
    type: str = ConnectionType.BODY
    call_params: str = ""
    priority: int = 0

    def to_dict(self, elements: list["Element"]) -> dict:
        index = {e.id: i for i, e in enumerate(elements)}
        return [
            index[self.source_id], index[self.target_id],
            self.type, self.call_params, int(self.priority),
        ]

    @staticmethod
    def from_dict(data: list, elements: list["Element"]) -> "Connection":
        src_idx, tgt_idx, conn_type, call_params, priority = data[:5]
        return Connection(
            source_id=elements[int(src_idx)].id,
            target_id=elements[int(tgt_idx)].id,
            type=str(conn_type),
            call_params=str(call_params or ""),
            priority=int(priority or 0),
        )


@dataclass
class Element:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = ElementType.PROCESS
    x: float = 0.0
    y: float = 0.0
    code: str = ""
    condition: Optional[str] = None
    loop_type: Optional[str] = None
    function_name: Optional[str] = None
    function_params: Optional[str] = None
    is_lambda: bool = False
    return_value: Optional[str] = None
    class_name: Optional[str] = None
    parent_class: Optional[str] = None
    attributes: Optional[dict] = None
    methods: list = field(default_factory=list)
    decorator: Optional[str] = None
    subflowchart: Optional["Flowchart"] = None
    options: dict = field(default_factory=dict)

    def label_text(self) -> str:
        t = self.type
        if t in (ElementType.PROCESS, ElementType.INPUT, ElementType.OUTPUT,
                 ElementType.COMMENT, ElementType.THREAD, ElementType.EXTERNAL):
            return self.code or t
        if t in (ElementType.DECISION, ElementType.LOOP):
            return self.condition or t
        if t == ElementType.FUNCTION:
            return self.function_name or t
        if t == ElementType.CLASS:
            return self.class_name or t
        if t == ElementType.SYNC_EVENT:
            return f"{self.options.get('event_name', '')} {self.options.get('action', 'set')}".strip() or t
        if t in (ElementType.SYNC_LOCK, ElementType.SYNC_SEMAPHORE, ElementType.SYNC_BARRIER):
            return self.options.get("name", "") or t
        return t

    def opt(self, key: str, default: Any = "") -> Any:
        return self.options.get(key, default)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "x": self.x,
            "y": self.y,
            "code": self.code,
            "condition": self.condition,
            "loop_type": self.loop_type,
            "function_name": self.function_name,
            "function_params": self.function_params,
            "is_lambda": self.is_lambda,
            "return_value": self.return_value,
            "class_name": self.class_name,
            "parent_class": self.parent_class,
            "attributes": self.attributes,
            "methods": [
                {
                    "name": m.get("name", ""),
                    "params": m.get("params", ""),
                    "subflowchart": (
                        m["subflowchart"].to_dict() if m.get("subflowchart") else None
                    ),
                }
                for m in (self.methods or [])
            ],
            "decorator": self.decorator,
            "options": dict(self.options),
            "subflowchart": self.subflowchart.to_dict() if self.subflowchart else None,
        }

    @staticmethod
    def from_dict(data: dict) -> "Element":
        legacy_options = {}
        for legacy_key in ("start_delay", "wait_event", "trigger_event"):
            if legacy_key in data and legacy_key not in (data.get("options") or {}):
                legacy_options[legacy_key] = data[legacy_key]
        options = dict(data.get("options") or {})
        options.update(legacy_options)
        sub = data.get("subflowchart")
        methods = []
        for m in data.get("methods") or []:
            msub = m.get("subflowchart")
            methods.append({
                "name": m.get("name", ""),
                "params": m.get("params", ""),
                "subflowchart": Flowchart.from_dict(msub) if msub else None,
            })
        return Element(
            id=str(data.get("id") or uuid.uuid4()),
            type=str(data.get("type") or ElementType.PROCESS),
            x=float(data.get("x") or 0),
            y=float(data.get("y") or 0),
            code=data.get("code") or "",
            condition=data.get("condition"),
            loop_type=data.get("loop_type"),
            function_name=data.get("function_name"),
            function_params=data.get("function_params"),
            is_lambda=bool(data.get("is_lambda")),
            return_value=data.get("return_value"),
            class_name=data.get("class_name"),
            parent_class=data.get("parent_class"),
            attributes=data.get("attributes"),
            methods=methods,
            decorator=data.get("decorator"),
            subflowchart=Flowchart.from_dict(sub) if sub else None,
            options=options,
        )


@dataclass
class Flowchart:
    elements: list[Element] = field(default_factory=list)
    connections: list[Connection] = field(default_factory=list)

    def element_by_id(self, element_id: str) -> Optional[Element]:
        for element in self.elements:
            if element.id == element_id:
                return element
        return None

    def add_element(self, element: Element) -> Element:
        self.elements.append(element)
        return element

    def remove_element(self, element_id: str) -> None:
        self.elements = [e for e in self.elements if e.id != element_id]
        self.connections = [
            c for c in self.connections
            if c.source_id != element_id and c.target_id != element_id
        ]

    def add_connection(self, connection: Connection) -> tuple[bool, str]:
        if connection.source_id == connection.target_id:
            return False, "不能連接到相同元素"
        if self.element_by_id(connection.source_id) is None:
            return False, "連線起點元素不存在"
        target = self.element_by_id(connection.target_id)
        if target is None:
            return False, "連線終點元素不存在"
        for c in self.connections:
            if (c.source_id == connection.source_id
                    and c.target_id == connection.target_id
                    and c.type == connection.type):
                return False, f"已經存在相同的 {connection.type} 連線"
        if connection.type == ConnectionType.CALL and target.type not in (
                ElementType.FUNCTION, ElementType.CLASS, ElementType.EXTERNAL):
            return False, "Call 連線必須指向函式、類別或外部函式元素"
        if connection.type in (ConnectionType.BODY, ConnectionType.EXIT) \
                and target.type in (ElementType.FUNCTION, ElementType.EXTERNAL):
            return False, "Body/Exit 連線不能指向函式或外部函式元素"
        if connection.type != ConnectionType.CALL and connection.call_params:
            return False, f"{connection.type} 連線不應包含呼叫參數"
        if connection.priority < 0:
            return False, "優先級不能為負數"
        self.connections.append(connection)
        return True, ""

    def remove_connection(self, connection: Connection) -> None:
        if connection in self.connections:
            self.connections.remove(connection)

    def find_connection(self, source_id: str, target_id: str,
                        conn_type: Optional[str] = None) -> Optional[Connection]:
        for c in self.connections:
            if c.source_id == source_id and c.target_id == target_id:
                if conn_type is None or c.type == conn_type:
                    return c
        return None

    def outgoing(self, element_id: str, conn_type: Optional[str] = None) -> list[Connection]:
        result = [
            c for c in self.connections
            if c.source_id == element_id and (conn_type is None or c.type == conn_type)
        ]
        result.sort(key=lambda c: (c.priority, c.target_id))
        return result

    def incoming(self, element_id: str, conn_type: Optional[str] = None) -> list[Connection]:
        result = [
            c for c in self.connections
            if c.target_id == element_id and (conn_type is None or c.type == conn_type)
        ]
        result.sort(key=lambda c: (c.priority, c.source_id))
        return result

    def entry_element(self) -> Optional[Element]:
        for element in self.elements:
            if element.type == ElementType.START_END and not self.incoming(element.id):
                return element
        return self.elements[0] if self.elements else None

    def to_dict(self) -> dict:
        return {
            "elements": [e.to_dict() for e in self.elements],
            "connections": [c.to_dict(self.elements) for c in self.connections],
        }

    @staticmethod
    def from_dict(data: dict) -> "Flowchart":
        elements = [Element.from_dict(d) for d in data.get("elements") or []]
        connections = []
        for cdata in data.get("connections") or []:
            try:
                connections.append(Connection.from_dict(cdata, elements))
            except (IndexError, ValueError, TypeError):
                continue
        return Flowchart(elements=elements, connections=connections)


@dataclass
class Project:
    flowchart: Flowchart = field(default_factory=Flowchart)
    variables: dict = field(default_factory=dict)
    libraries: list = field(default_factory=list)
    custom_modules: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            **self.flowchart.to_dict(),
            "variables": dict(self.variables),
            "libraries": list(self.libraries),
            "custom_modules": [list(m) for m in self.custom_modules],
        }

    @staticmethod
    def from_dict(data: dict) -> "Project":
        if "main_canvas" in data:
            data = _convert_legacy_project(data)
        flowchart = Flowchart.from_dict(data)
        return Project(
            flowchart=flowchart,
            variables=dict(data.get("variables") or {}),
            libraries=list(data.get("libraries") or []),
            custom_modules=[tuple(m) for m in data.get("custom_modules") or []],
        )


def _convert_legacy_project(data: dict) -> dict:
    canvas = data.get("main_canvas") or {}
    elements = []
    id_map = {}
    for old in canvas.get("elements") or []:
        new_id = str(old.get("id") or uuid.uuid4())
        id_map[old.get("id")] = new_id
        converted = dict(old)
        converted["id"] = new_id
        elements.append(converted)
    order = {eid: i for i, eid in enumerate(id_map.values())}
    fixed = []
    for c in canvas.get("connections") or []:
        try:
            fixed.append([
                order[id_map[c[0]]], order[id_map[c[1]]],
                c[2] if len(c) > 2 else "Body",
                c[3] if len(c) > 3 else "",
                int(c[4] or 0) if len(c) > 4 else 0,
            ])
        except (KeyError, IndexError, ValueError, TypeError):
            continue
    return {
        "elements": elements,
        "connections": fixed,
        "variables": data.get("variables") or {},
        "libraries": data.get("libraries") or [],
        "custom_modules": data.get("custom_modules") or [],
    }
