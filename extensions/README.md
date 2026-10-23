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

## 目標語言擴充（多語言程式碼產生）

內建 Python 與 JavaScript 後端；「目標語言」選單可切換，選擇會存入
`settings.json`。新增語言方式：繼承 `flowchart_core.LanguageBackend`
並呼叫 `flowchart_core.register_language(backend)`：

```python
from flowchart_core import LanguageBackend, register_language

class RubyBackend(LanguageBackend):
    name = "ruby"                 # 內部名稱（settings / API 用）
    display_name = "Ruby"         # 顯示名稱
    file_extension = ".rb"
    supports_extensions = False   # True 時沿用 Python 擴充元素 emit_code
    supports_execution = False    # 動畫執行固定走 Python 流程語意

    def header_imports(self, libraries, custom_modules):
        return [f'require "{lib}"' for lib in libraries]

    def threading_header(self):
        return None

    def print_stmt(self, expr):
        return f"puts {expr}"

    def comment(self, text):
        return f"# {text}"

    def return_stmt(self, expr):
        return f"return {expr}"

    def assignment(self, name, value):
        return f"{name} = {value!r}"

    def if_open(self, cond):
        return f"if {cond}"

    def else_open(self):
        return "else"

    def while_open(self, cond):
        return f"while {cond}"

    def for_open(self, cond):
        return f"for {cond}"

    def empty_body(self, level=0):
        return "end"

    def block_close(self, level=0):
        return ["end"]

    def function_open(self, name, params):
        return f"def {name}({params})"

    def lambda_head(self, name, params):
        return f"{name} = lambda {params} "

    def lambda_tail(self):
        return ""

    def class_open(self, name, parent):
        return f"class {name} < {parent}" if parent else f"class {name}"

    def method_open(self, name, params):
        return f"def {name}({params})"

    def class_attribute(self, name, value):
        return f"{name} = {value!r}"

register_language(RubyBackend())
```

說明：

- 大括號語言在 `if_open`/`while_open` 等開頭行加 `{`，並實作
  `block_close()` 回傳收尾行（如 `"}"`）；Python 類縮排語言
  `block_close()` 回傳 `[]`、`empty_body()` 回傳 `"pass"`。
- `supports_extensions=False` 時，Python 專屬擴充元素（Thread、
  SyncEvent 等）會自動降級為註解。
- 執行動畫（F5）始終以 Python 流程語意執行，與目標語言選項無關。

