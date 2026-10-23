from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


class EventKind:
    ELEMENT_ENTER = "element_enter"
    ELEMENT_EXIT = "element_exit"
    CONNECTION = "connection"
    OUTPUT = "output"
    THREAD_STARTED = "thread_started"
    SYNC_WAIT = "sync_wait"
    POLICY_VIOLATION = "policy_violation"
    ERROR = "error"
    WARNING = "warning"
    LOOP_LIMIT = "loop_limit"
    DONE = "done"


@dataclass
class ExecutionEvent:
    kind: str
    element_id: Optional[str] = None
    source_id: Optional[str] = None
    target_id: Optional[str] = None
    message: str = ""
    data: dict = field(default_factory=dict)
