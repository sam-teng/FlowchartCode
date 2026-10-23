from __future__ import annotations

from typing import Callable, Iterator, Optional


class AnimationPlayer:
    def __init__(self, root):
        self.root = root
        self._after_id = None
        self._iterator: Optional[Iterator] = None
        self._on_event: Optional[Callable] = None
        self._on_done: Optional[Callable] = None
        self._delay = 400
        self.running = False

    def play(self, iterator: Iterator, on_event: Callable,
             step_delay_ms: int = 400, on_done: Optional[Callable] = None) -> None:
        self.cancel()
        self._iterator = iterator
        self._on_event = on_event
        self._on_done = on_done
        self._delay = max(0, int(step_delay_ms))
        self.running = True
        self._pump()

    def _pump(self) -> None:
        if not self.running or self._iterator is None:
            return
        try:
            event = next(self._iterator)
        except StopIteration:
            self._finish()
            return
        except Exception as exc:
            self.running = False
            if self._on_done is not None:
                self._on_done(error=exc)
            return
        extra_ms = 0
        try:
            extra_ms = self._on_event(event) or 0
        except Exception as exc:
            self.running = False
            if self._on_done is not None:
                self._on_done(error=exc)
            return
        if not self.running:
            return
        self._after_id = self.root.after(self._delay + int(extra_ms), self._pump)

    def _finish(self) -> None:
        self.running = False
        self._after_id = None
        if self._on_done is not None:
            self._on_done()

    def cancel(self) -> None:
        self.running = False
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        self._iterator = None
