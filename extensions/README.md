# 自訂元素外掛（extensions/）

將 `.py` 檔案放入本資料夾，啟動工具時自動載入。
每個外掛必須提供下列兩種註冊方式之一：

1. 模組層級函式：`def register(registry): registry.register(MyExtension())`
2. 或模組層級清單：`EXTENSIONS = [MyExtension(), ...]`

檔案名稱以 `_` 開頭者會被忽略。載入失敗的外掛會記錄於
`registry.load_errors`（不會中斷主程式）。

## 外掛介面

繼承 `flowchart_core.ElementExtension`，實作：

```python
from flowchart_core import (
    ElementExtension, ElementMeta, EventKind, ExecutionEvent,
    FieldSpec, ValidationResult,
)

class MyElement(ElementExtension):
    meta = ElementMeta(
        type_name="MyElement",          # 元素型別名稱（不可與內建重複）
        label="我的元素",
        color="#88CCFF",                # 畫布填色
        shape="rectangle",              # rectangle / oval / diamond / input / output / text
        fields=[                        # 編輯對話框動態欄位
            FieldSpec("name", "名稱", default="x"),
            FieldSpec("mode", "模式", kind="choice", default="a", choices=["a", "b"]),
        ],
    )
    indents_body = False                # True 時 Body 分支會縮排成 with/區塊內容

    def validate(self, element, validator) -> ValidationResult:
        return ValidationResult.success()

    def emit_declarations(self, flowchart, symbols) -> list[str]:
        """文件層級宣告（自動去重），例如 name = queue.Queue()。"""
        return []

    def emit_code(self, element, ctx) -> list[str]:
        """產生此元素的程式碼（使用 ctx.line() 加上縮排）。"""
        return [ctx.line(f"print({element.opt('name')!r})")]

    def execute(self, element, ctx) -> iterator:
        """圖形遍歷執行：yield ExecutionEvent 事件供動畫與輸出使用。
        ctx.globals 為執行環境；ctx.run_children(element) 可執行 Body 分支。"""
        yield ExecutionEvent(EventKind.ELEMENT_EXIT, element_id=element.id)
```

元素資料存取：

- `element.opt("欄位名")` 讀取 options 欄位（編輯對話框自動對應 meta.fields）
- `element.code` 為通用程式碼欄位（meta.fields 中名為 "code" 的欄位會對應它）

## 注意事項

- 外掛以完整 Python 權限載入，**只放可信檔案**。
- 外掛程式碼仍會受到「安全政策」對流程圖程式碼的黑/白名單檢核
  （emit_code 產生的程式碼在驗證與執行時同樣受政策約束）。
- 範例：`sample_queue_element.py`（QueuePush / QueuePop 佇列元素）。
