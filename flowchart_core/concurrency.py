from __future__ import annotations

import threading
from typing import Iterator, Optional

from .events import EventKind, ExecutionEvent
from .extensions import ElementExtension, ElementMeta, FieldSpec
from .models import ConnectionType, ElementType
from .validator import ValidationResult


class ThreadCounter:
    def __init__(self):
        self._value = 0

    def next(self) -> int:
        self._value += 1
        return self._value

    def reset(self) -> None:
        self._value = 0


class CodegenContext:
    def __init__(self, indent: int = 0, symbols=None, thread_counter: Optional[ThreadCounter] = None,
                 flowchart=None):
        self.indent = indent
        self.symbols = symbols
        self.thread_counter = thread_counter or ThreadCounter()
        self.flowchart = flowchart

    def line(self, text: str, level: Optional[int] = None) -> str:
        level = self.indent if level is None else level
        return "    " * level + text

    def next_thread_id(self) -> int:
        return self.thread_counter.next()

    def child(self, level_delta: int = 1) -> "CodegenContext":
        return CodegenContext(
            indent=self.indent + level_delta,
            symbols=self.symbols,
            thread_counter=self.thread_counter,
            flowchart=self.flowchart,
        )


def _indent_block(code: str, indent: int) -> list[str]:
    prefix = "    " * indent
    return [prefix + line if line.strip() else "" for line in (code or "").split("\n")]


class ThreadExtension(ElementExtension):
    meta = ElementMeta(
        type_name=ElementType.THREAD,
        label="Thread/Task",
        color="#B7A6E8",
        shape="rectangle",
        fields=[
            FieldSpec("code", "執行內容（每行一列）", kind="text"),
            FieldSpec("start_delay", "啟動延遲（秒）", default="0"),
            FieldSpec("wait_event", "等待事件名稱"),
            FieldSpec("trigger_event", "觸發事件名稱"),
        ],
    )
    indents_body = False

    def validate(self, element, validator) -> ValidationResult:
        if not (element.code or "").strip():
            return ValidationResult.failure("Thread/Task 需要執行內容")
        for key in ("start_delay",):
            raw = str(element.opt(key, "0") or "0")
            try:
                float(raw)
            except ValueError:
                return ValidationResult.failure("啟動延遲必須為數字（秒）")
        return ValidationResult.success()

    def emit_declarations(self, flowchart, symbols) -> list[str]:
        lines = []
        for element in flowchart.elements:
            if element.type != ElementType.THREAD:
                continue
            for key in ("wait_event", "trigger_event"):
                name = (element.opt(key) or "").strip()
                if name.isidentifier():
                    lines.append(f"{name} = threading.Event()")
        return lines

    def emit_code(self, element, ctx: CodegenContext) -> list[str]:
        tid = ctx.next_thread_id()
        fname = f"thread_{tid}_func"
        lines = [ctx.line(f"def {fname}():")]
        body = _indent_block(element.code, ctx.indent + 1)
        lines.extend(body if body else [ctx.line("pass", ctx.indent + 1)])
        wait_event = (element.opt("wait_event") or "").strip()
        trigger_event = (element.opt("trigger_event") or "").strip()
        if wait_event:
            lines.append(ctx.line(f"{wait_event}.wait()", ctx.indent + 1))
        if trigger_event:
            lines.append(ctx.line(f"{trigger_event}.set()", ctx.indent + 1))
        lines.append("")
        lines.append(ctx.line(f"thread_{tid} = threading.Thread(target={fname})"))
        delay = str(element.opt("start_delay", "0") or "0").strip()
        if delay and delay != "0":
            lines.append(ctx.line(
                f"threading.Timer({delay}, thread_{tid}.start).start()"
            ))
        else:
            lines.append(ctx.line(f"thread_{tid}.start()"))
        return lines

    def execute(self, element, ctx) -> Iterator[ExecutionEvent]:
        globals_dict = ctx.globals
        wait_event = (element.opt("wait_event") or "").strip()
        trigger_event = (element.opt("trigger_event") or "").strip()
        for name in (wait_event, trigger_event):
            if name.isidentifier() and not isinstance(globals_dict.get(name), threading.Event):
                globals_dict[name] = threading.Event()

        def run_body() -> None:
            namespace = dict(globals_dict)
            try:
                exec(element.code or "pass", namespace)
            except Exception as exc:
                ctx.thread_errors.append((element.id, exc))
                return
            try:
                if wait_event:
                    namespace[wait_event].wait()
                if trigger_event:
                    namespace[trigger_event].set()
            except Exception as exc:
                ctx.thread_errors.append((element.id, exc))

        delay = float(element.opt("start_delay", "0") or 0)
        worker = threading.Thread(target=run_body, daemon=True)
        if delay > 0:
            timer = threading.Timer(delay, worker.start)
            timer.daemon = True
            timer.start()
        else:
            worker.start()
        yield ExecutionEvent(
            EventKind.THREAD_STARTED, element_id=element.id,
            message=f"執行緒已啟動（延遲 {delay}s）",
        )


class SyncEventExtension(ElementExtension):
    meta = ElementMeta(
        type_name=ElementType.SYNC_EVENT,
        label="SyncEvent",
        color="#FFE08A",
        shape="oval",
        fields=[
            FieldSpec("event_name", "事件名稱"),
            FieldSpec("action", "動作", kind="choice", default="set",
                      choices=["set", "clear", "wait"]),
        ],
    )
    indents_body = False

    def validate(self, element, validator) -> ValidationResult:
        name = (element.opt("event_name") or "").strip()
        if not name.isidentifier():
            return ValidationResult.failure("事件名稱必須為有效識別符")
        if element.opt("action", "set") not in ("set", "clear", "wait"):
            return ValidationResult.failure("動作必須是 set / clear / wait")
        return ValidationResult.success()

    def emit_declarations(self, flowchart, symbols) -> list[str]:
        lines = []
        for element in flowchart.elements:
            if element.type != ElementType.SYNC_EVENT:
                continue
            name = (element.opt("event_name") or "").strip()
            if name.isidentifier():
                lines.append(f"{name} = threading.Event()")
        return lines

    def emit_code(self, element, ctx: CodegenContext) -> list[str]:
        name = element.opt("event_name")
        action = element.opt("action", "set")
        return [ctx.line(f"{name}.{action}()")]

    def execute(self, element, ctx) -> Iterator[ExecutionEvent]:
        name = element.opt("event_name")
        action = element.opt("action", "set")
        event_obj = ctx.globals.get(name)
        if not isinstance(event_obj, threading.Event):
            event_obj = threading.Event()
            ctx.globals[name] = event_obj
        if action == "wait":
            yield ExecutionEvent(
                EventKind.SYNC_WAIT, element_id=element.id,
                message=f"等待事件 {name}",
            )
            event_obj.wait()
        elif action == "clear":
            event_obj.clear()
        else:
            event_obj.set()
        yield ExecutionEvent(
            EventKind.ELEMENT_EXIT, element_id=element.id,
            message=f"{name}.{action}()",
        )


class _WithBlockExtension(ElementExtension):
    indents_body = True

    def _name(self, element) -> str:
        return (element.opt("name") or "").strip()

    def validate(self, element, validator) -> ValidationResult:
        if not self._name(element).isidentifier():
            return ValidationResult.failure(f"{self.meta.label} 需要有效名稱")
        return ValidationResult.success()

    def emit_declarations(self, flowchart, symbols) -> list[str]:
        lines = []
        for element in flowchart.elements:
            if element.type != self.meta.type_name:
                continue
            name = self._name(element)
            if name.isidentifier():
                lines.append(self.declaration_fmt(element, name))
        return lines

    def declaration_fmt(self, element, name: str) -> str:
        raise NotImplementedError

    def emit_code(self, element, ctx: CodegenContext) -> list[str]:
        return [ctx.line(f"with {self._name(element)}:")]

    def execute(self, element, ctx) -> Iterator[ExecutionEvent]:
        import contextlib
        name = self._name(element)
        lock_obj = ctx.globals.get(name)
        if lock_obj is None:
            yield ExecutionEvent(
                EventKind.ERROR, element_id=element.id,
                message=f"同步物件 {name} 未宣告",
            )
            return
        yield ExecutionEvent(
            EventKind.ELEMENT_ENTER, element_id=element.id,
            message=f"取得 {name}",
        )
        with contextlib.ExitStack() as stack:
            stack.enter_context(lock_obj)
            yield from ctx.run_children(element, ConnectionType.BODY)


class LockExtension(_WithBlockExtension):
    meta = ElementMeta(
        type_name=ElementType.SYNC_LOCK,
        label="SyncLock",
        color="#9CCFE7",
        shape="rectangle",
        fields=[FieldSpec("name", "鎖名稱")],
    )

    def declaration_fmt(self, element, name: str) -> str:
        return f"{name} = threading.Lock()"


class SemaphoreExtension(_WithBlockExtension):
    meta = ElementMeta(
        type_name=ElementType.SYNC_SEMAPHORE,
        label="SyncSemaphore",
        color="#A3BE8C",
        shape="rectangle",
        fields=[
            FieldSpec("name", "信號量名稱"),
            FieldSpec("count", "計數", default="1"),
        ],
    )

    def validate(self, element, validator) -> ValidationResult:
        base = super().validate(element, validator)
        if not base.ok:
            return base
        try:
            if int(element.opt("count", "1") or 1) < 1:
                return ValidationResult.failure("信號量計數必須 >= 1")
        except ValueError:
            return ValidationResult.failure("信號量計數必須為整數")
        return ValidationResult.success()

    def declaration_fmt(self, element, name: str) -> str:
        count = element.opt("count", "1") or "1"
        return f"{name} = threading.Semaphore({count})"


class BarrierExtension(ElementExtension):
    meta = ElementMeta(
        type_name=ElementType.SYNC_BARRIER,
        label="SyncBarrier",
        color="#EBCB8B",
        shape="diamond",
        fields=[
            FieldSpec("name", "屏障名稱"),
            FieldSpec("parties", "參與者數", default="2"),
        ],
    )
    indents_body = False

    def validate(self, element, validator) -> ValidationResult:
        if not (element.opt("name") or "").strip().isidentifier():
            return ValidationResult.failure("屏障需要有效名稱")
        try:
            if int(element.opt("parties", "2") or 2) < 2:
                return ValidationResult.failure("屏障參與者數必須 >= 2")
        except ValueError:
            return ValidationResult.failure("屏障參與者數必須為整數")
        return ValidationResult.success()

    def emit_declarations(self, flowchart, symbols) -> list[str]:
        lines = []
        for element in flowchart.elements:
            if element.type != ElementType.SYNC_BARRIER:
                continue
            name = (element.opt("name") or "").strip()
            parties = element.opt("parties", "2") or "2"
            if name.isidentifier():
                lines.append(f"{name} = threading.Barrier({parties})")
        return lines

    def emit_code(self, element, ctx: CodegenContext) -> list[str]:
        return [ctx.line(f"{element.opt('name')}.wait()")]

    def execute(self, element, ctx) -> Iterator[ExecutionEvent]:
        name = element.opt("name")
        barrier = ctx.globals.get(name)
        if barrier is None:
            yield ExecutionEvent(
                EventKind.ERROR, element_id=element.id,
                message=f"屏障 {name} 未宣告",
            )
            return
        yield ExecutionEvent(
            EventKind.SYNC_WAIT, element_id=element.id,
            message=f"屏障 {name}.wait()",
        )
        try:
            barrier.wait()
        except Exception as exc:
            yield ExecutionEvent(
                EventKind.ERROR, element_id=element.id,
                message=f"屏障等待失敗：{exc}",
            )
            return
        yield ExecutionEvent(EventKind.ELEMENT_EXIT, element_id=element.id)


def register_builtins(registry) -> None:
    for ext in (
        ThreadExtension(), SyncEventExtension(), LockExtension(),
        SemaphoreExtension(), BarrierExtension(),
    ):
        registry.register(ext)
