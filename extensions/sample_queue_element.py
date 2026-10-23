"""範例外掛：QueueSync — 示範如何以 ElementExtension 註冊自訂元素。

功能：QueuePush（將值放入佇列）、QueuePop（取出佇列值並存入變數）。
使用方式：將本檔放入 extensions/ 資料夾，啟動工具時自動載入。
"""
import queue
import threading

from flowchart_core import (
    ElementExtension, ElementMeta, EventKind, ExecutionEvent, FieldSpec,
    ValidationResult,
)


class _QueueBase(ElementExtension):
    indents_body = False

    def _qname(self, element) -> str:
        return (element.opt("queue_name") or "").strip()

    def validate(self, element, validator) -> ValidationResult:
        if not self._qname(element).isidentifier():
            return ValidationResult.failure(f"{self.meta.label} 需要有效的佇列名稱")
        return ValidationResult.success()

    def emit_declarations(self, flowchart, symbols) -> list[str]:
        lines = []
        for element in flowchart.elements:
            if element.type != self.meta.type_name:
                continue
            name = self._qname(element)
            if name.isidentifier():
                lines.append("import queue")
                lines.append(f"{name} = queue.Queue()")
        return lines

    def _ensure(self, ctx, name):
        q = ctx.globals.get(name)
        if not isinstance(q, queue.Queue):
            q = queue.Queue()
            ctx.globals[name] = q
            ctx.globals.setdefault("queue", queue)
        return q


class QueuePushExtension(_QueueBase):
    meta = ElementMeta(
        type_name="QueuePush",
        label="QueuePush",
        color="#F5A9B8",
        shape="rectangle",
        fields=[
            FieldSpec("queue_name", "佇列名稱", default="task_queue"),
            FieldSpec("value", "放入值", default="1"),
        ],
    )

    def emit_code(self, element, ctx) -> list[str]:
        return [ctx.line(f"{element.opt('queue_name')}.put({element.opt('value')})")]

    def execute(self, element, ctx) -> list:
        name = self._qname(element)
        q = self._ensure(ctx, name)
        raw = element.opt("value", "1")
        try:
            value = eval(raw, {"__builtins__": {}}, {}) if isinstance(raw, str) else raw
        except Exception:
            value = raw
        q.put(value)
        return [ExecutionEvent(
            EventKind.ELEMENT_EXIT, element_id=element.id,
            message=f"{name}.put({value!r})",
        )]


class QueuePopExtension(_QueueBase):
    meta = ElementMeta(
        type_name="QueuePop",
        label="QueuePop",
        color="#D5A9F5",
        shape="rectangle",
        fields=[
            FieldSpec("queue_name", "佇列名稱", default="task_queue"),
            FieldSpec("target", "存入變數", default="item"),
        ],
    )

    def validate(self, element, validator) -> ValidationResult:
        base = super().validate(element, validator)
        if not base.ok:
            return base
        if not (element.opt("target") or "").strip().isidentifier():
            return ValidationResult.failure("存入變數名稱必須為有效識別符")
        return ValidationResult.success()

    def emit_code(self, element, ctx) -> list[str]:
        return [ctx.line(
            f"{element.opt('target')} = {element.opt('queue_name')}.get()"
        )]

    def execute(self, element, ctx) -> list:
        name = self._qname(element)
        target = (element.opt("target") or "item").strip()
        q = self._ensure(ctx, name)
        try:
            value = q.get_nowait()
        except queue.Empty:
            return [ExecutionEvent(
                EventKind.ERROR, element_id=element.id,
                message=f"佇列 {name} 為空",
            )]
        ctx.globals[target] = value
        return [ExecutionEvent(
            EventKind.ELEMENT_EXIT, element_id=element.id,
            message=f"{target} = {name}.get() → {value!r}",
        )]


def register(registry) -> None:
    registry.register(QueuePushExtension())
    registry.register(QueuePopExtension())
