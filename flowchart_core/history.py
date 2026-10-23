from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class History:
    limit: int = 50
    undo_stack: deque = field(default_factory=lambda: deque())
    redo_stack: deque = field(default_factory=lambda: deque())

    def __post_init__(self):
        self.undo_stack = deque(maxlen=self.limit)
        self.redo_stack = deque(maxlen=self.limit)

    def push(self, state: Any) -> None:
        self.undo_stack.append(state)
        self.redo_stack.clear()

    def undo(self, current_state: Any) -> Optional[Any]:
        if not self.undo_stack:
            return None
        self.redo_stack.append(current_state)
        return self.undo_stack.pop()

    def redo(self) -> Optional[Any]:
        if not self.redo_stack:
            return None
        state = self.redo_stack.pop()
        self.undo_stack.append(state)
        return state

    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    def can_redo(self) -> bool:
        return bool(self.redo_stack)

    def clear(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()
