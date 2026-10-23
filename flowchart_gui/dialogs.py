from __future__ import annotations

import json
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Callable, Optional

from flowchart_core import (
    CodePolicy, Connection, ConnectionType, Element, ElementType,
    ExtensionRegistry, Snippet, SnippetLibrary, SymbolTable,
    get_callable_info, list_module_callables,
)
from flowchart_core.completion import CompletionProvider
from flowchart_core.policy import PRESET_LENIENT, PRESET_STANDARD, PRESET_STRICT

from .autocomplete import CompletionPopup
from .shortcuts import ACTION_LABELS, ShortcutManager, display_name

_WORD_RE = re.compile(r"[A-Za-z_][\w\.]*")


def place_geometry(window, width: int, height: int) -> None:
    """設定視窗尺寸，超出螢幕時縮小，並置中於父視窗。"""
    parent = window.master
    try:
        sw = window.winfo_screenwidth()
        sh = window.winfo_screenheight()
        width = min(width, sw - 40)
        height = min(height, sh - 80)
        if parent is not None:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            x = px + max((pw - width) // 2, 0)
            y = py + max((ph - height) // 2, 0)
            x = min(x, max(sw - width, 0))
            y = min(y, max(sh - height, 0))
        else:
            x = max((sw - width) // 2, 0)
            y = max((sh - height) // 2, 0)
        window.geometry(f"{width}x{height}+{x}+{y}")
    except tk.TclError:
        window.geometry(f"{width}x{height}")


def _word_at_cursor(text_widget) -> str:
    try:
        line, col = map(int, text_widget.index("insert").split("."))
        line_text = text_widget.get(f"{line}.0", f"{line}.end")
    except tk.TclError:
        return ""
    start = col
    while start > 0 and (line_text[start - 1].isalnum() or line_text[start - 1] in "_."):
        start -= 1
    end = col
    while end < len(line_text) and (line_text[end].isalnum() or line_text[end] in "_."):
        end += 1
    return line_text[start:end]


class ElementEditDialog:
    def __init__(self, parent, element: Element, symbols: SymbolTable,
                 validator, provider: CompletionProvider,
                 snippets: SnippetLibrary, registry: ExtensionRegistry,
                 on_saved: Optional[Callable] = None):
        self.parent = parent
        self.element = element
        self.symbols = symbols
        self.validator = validator
        self.provider = provider
        self.snippets = snippets
        self.registry = registry
        self.on_saved = on_saved
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"編輯 {element.type} 元素")
        place_geometry(self.dialog, 460, 620)
        self.dialog.transient(parent)
        self._validate_after = None
        self._fields: dict[str, dict] = {}
        self._completion: Optional[CompletionPopup] = None
        self._build()
        self.dialog.protocol("WM_DELETE_WINDOW", self.dialog.destroy)

    def show(self) -> None:
        self.dialog.wait_window()

    def _build(self) -> None:
        container = ttk.Frame(self.dialog, padding=8)
        container.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._build_fields(inner)

        ttk.Label(inner, text="插入片段：").pack(anchor="w", pady=(8, 0))
        snippet_names = [s.name for s in self.snippets.snippets] or ["（無片段）"]
        self._snippet_var = tk.StringVar(value=snippet_names[0])
        row = ttk.Frame(inner)
        row.pack(fill=tk.X)
        ttk.OptionMenu(row, self._snippet_var, snippet_names[0], *snippet_names).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        ttk.Button(row, text="插入", command=self._insert_snippet).pack(side=tk.LEFT, padx=4)

        self._hint = tk.Label(inner, text="", wraplength=400, justify=tk.LEFT,
                              anchor="w", font=("Arial", 9))
        self._hint.pack(fill=tk.X, pady=6)

        buttons = ttk.Frame(inner)
        buttons.pack(fill=tk.X, pady=6)
        ttk.Button(buttons, text="儲存", command=self._save).pack(side=tk.LEFT)
        ttk.Button(buttons, text="取消", command=self.dialog.destroy).pack(side=tk.LEFT, padx=6)
        ttk.Label(inner, text="提示：Ctrl+Space 自動補全，Ctrl+K 查詢函式說明",
                  font=("Arial", 8), foreground="gray").pack(anchor="w")

    def _build_fields(self, parent) -> None:
        element = self.element
        etype = element.type
        if etype in (ElementType.PROCESS, ElementType.INPUT, ElementType.OUTPUT,
                     ElementType.COMMENT):
            self._add_code_text(parent, "程式碼/內容：", element.code or "")
        elif etype in (ElementType.DECISION, ElementType.LOOP):
            self._add_code_text(parent, "條件：", element.condition or "")
            if etype == ElementType.LOOP:
                self._loop_type = tk.StringVar(value=element.loop_type or "for")
                ttk.Radiobutton(parent, text="For 迴圈", value="for",
                                variable=self._loop_type).pack(anchor="w")
                ttk.Radiobutton(parent, text="While 迴圈", value="while",
                                variable=self._loop_type).pack(anchor="w")
        elif etype == ElementType.FUNCTION:
            name_entry = self._add_entry(parent, "函式名稱：", element.function_name or "")
            params_entry = self._add_entry(parent, "參數：", element.function_params or "")
            decorator_entry = self._add_entry(parent, "裝飾器：", element.decorator or "")
            lambda_var = tk.BooleanVar(value=bool(element.is_lambda))
            ttk.Checkbutton(parent, text="Lambda 函式", variable=lambda_var).pack(anchor="w")
            self._fields["function_name"] = {"widget": name_entry, "kind": "entry"}
            self._fields["function_params"] = {"widget": params_entry, "kind": "entry"}
            self._fields["decorator"] = {"widget": decorator_entry, "kind": "entry"}
            self._fields["is_lambda"] = {"var": lambda_var, "kind": "bool"}
        elif etype == ElementType.CLASS:
            name_entry = self._add_entry(parent, "類別名稱：", element.class_name or "")
            parent_entry = self._add_entry(parent, "父類別：", element.parent_class or "")
            ttk.Label(parent, text="屬性（JSON）：").pack(anchor="w")
            attr_text = tk.Text(parent, height=4, width=44)
            attr_text.insert("1.0", json.dumps(element.attributes or {}, ensure_ascii=False))
            attr_text.pack(fill=tk.X, pady=2)
            self._bind_completion(attr_text)
            self._fields["class_name"] = {"widget": name_entry, "kind": "entry"}
            self._fields["parent_class"] = {"widget": parent_entry, "kind": "entry"}
            self._fields["attributes"] = {"widget": attr_text, "kind": "json"}
            method_count = len(element.methods or [])
            ttk.Label(parent, text=f"（方法 {method_count} 個，由子流程圖編輯）",
                      foreground="gray").pack(anchor="w")
        elif etype == ElementType.EXTERNAL:
            ttk.Label(parent, text=f"外部函式：{element.opt('module')}."
                                   f"{element.opt('qualname')}",
                      font=("Arial", 10, "bold")).pack(anchor="w", pady=4)
            module_entry = self._add_entry(parent, "模組：", element.opt("module"))
            qual_entry = self._add_entry(parent, "函式路徑：", element.opt("qualname"))
            self._fields["_opt_module"] = {"widget": module_entry, "kind": "entry"}
            self._fields["_opt_qualname"] = {"widget": qual_entry, "kind": "entry"}

        ext = self.registry.get(etype)
        if ext is not None:
            for spec in ext.meta.fields:
                if spec.name == "code" and "code" in self._fields:
                    continue
                initial = str(element.opt(spec.name, spec.default) or spec.default or "")
                if spec.kind == "choice":
                    var = tk.StringVar(value=initial or (spec.choices[0] if spec.choices else ""))
                    ttk.Label(parent, text=spec.label + "：").pack(anchor="w", pady=(4, 0))
                    ttk.OptionMenu(parent, var, var.get(),
                                   *(spec.choices or [var.get()])).pack(fill=tk.X)
                    self._fields[f"_opt_{spec.name}"] = {"var": var, "kind": "choice"}
                else:
                    entry = self._add_entry(parent, spec.label + "：", initial)
                    self._fields[f"_opt_{spec.name}"] = {"widget": entry, "kind": "entry"}

        if etype in (ElementType.PROCESS, ElementType.DECISION, ElementType.LOOP):
            ttk.Label(parent, text="（Process/Decision/Loop 亦可由片段選單插入語法糖）",
                      foreground="gray", font=("Arial", 8)).pack(anchor="w", pady=(4, 0))

    def _add_code_text(self, parent, label: str, initial: str) -> None:
        ttk.Label(parent, text=label).pack(anchor="w")
        text = tk.Text(parent, height=6, width=44, undo=True)
        text.insert("1.0", initial)
        text.pack(fill=tk.X, pady=2)
        text.bind("<KeyRelease>", self._schedule_validate)
        self._fields["code"] = {"widget": text, "kind": "text"}
        self._code_text = text
        self._bind_completion(text)

    def _add_entry(self, parent, label: str, initial: str) -> ttk.Entry:
        ttk.Label(parent, text=label).pack(anchor="w", pady=(4, 0))
        entry = ttk.Entry(parent, width=44)
        entry.insert(0, initial)
        entry.pack(fill=tk.X)
        return entry

    def _bind_completion(self, text_widget) -> None:
        self._completion = CompletionPopup(text_widget, self.provider)
        text_widget.bind("<Control-k>", lambda e: self._lookup_doc(text_widget), add="+")

    def _lookup_doc(self, text_widget) -> None:
        name = _word_at_cursor(text_widget) or simpledialog.askstring(
            "查詢函式說明", "輸入名稱（如 math.sqrt）：", parent=self.dialog
        )
        if not name:
            return
        DocLookupDialog(self.dialog, self.provider, initial=name)

    def _schedule_validate(self, event=None) -> None:
        if self._validate_after is not None:
            try:
                self.dialog.after_cancel(self._validate_after)
            except Exception:
                pass
        self._validate_after = self.dialog.after(300, self._live_validate)

    def _live_validate(self) -> None:
        self._validate_after = None
        code_field = self._fields.get("code")
        if not code_field or code_field.get("kind") != "text":
            return
        code = code_field["widget"].get("1.0", tk.END).strip()
        if not code:
            self._hint.config(text="", foreground="black")
            return
        role = "condition" if self.element.type in (ElementType.DECISION, ElementType.LOOP) \
            else "statement"
        result = self.validator.validate_code(code, role=role, element=self.element)
        if not result.ok:
            self._hint.config(text="✗ " + result.message, foreground="red")
        elif result.severity == "warning" and result.message:
            self._hint.config(text="⚠ " + result.message, foreground="#b58900")
        else:
            self._hint.config(text="✓ 語法檢查通過", foreground="green")

    def _insert_snippet(self) -> None:
        snippet = self.snippets.by_name(self._snippet_var.get())
        if snippet is None:
            return
        code = snippet.code
        placeholders = SnippetLibrary.parse_placeholders(code)
        values = {}
        for name in placeholders:
            value = simpledialog.askstring(
                "片段佔位符", f"輸入 {name} 的值：", parent=self.dialog
            )
            if value is None:
                return
            values[name] = value
        rendered = SnippetLibrary.render(code, values)
        code_field = self._fields.get("code")
        if code_field and code_field.get("kind") == "text":
            widget = code_field["widget"]
            widget.insert("insert", rendered)
            self._schedule_validate()

    def _save(self) -> None:
        element = self.element
        etype = element.type
        try:
            if "code" in self._fields and self._fields["code"].get("kind") == "text":
                code = self._fields["code"]["widget"].get("1.0", tk.END).strip()
                if etype in (ElementType.DECISION, ElementType.LOOP):
                    result = self.validator.validate_code(
                        code, role="condition", element=element
                    )
                    if not result.ok:
                        messagebox.showerror("錯誤", result.message, parent=self.dialog)
                        return
                    element.condition = code
                elif etype == ElementType.LOOP:
                    pass
                else:
                    result = self.validator.validate_code(
                        code, role="statement", element=element
                    )
                    if not result.ok:
                        messagebox.showerror("錯誤", result.message, parent=self.dialog)
                        return
                    element.code = code

            if etype == ElementType.LOOP and hasattr(self, "_loop_type"):
                element.loop_type = self._loop_type.get()

            if etype == ElementType.FUNCTION:
                name = self._fields["function_name"]["widget"].get().strip()
                if not name or not re.match(r"^[a-zA-Z_]\w*$", name):
                    messagebox.showerror("錯誤", "函式名稱必須為有效 Python 標識符",
                                         parent=self.dialog)
                    return
                element.function_name = name
                element.function_params = self._fields["function_params"]["widget"].get().strip()
                element.decorator = self._fields["decorator"]["widget"].get().strip() or None
                element.is_lambda = bool(self._fields["is_lambda"]["var"].get())

            if etype == ElementType.CLASS:
                name = self._fields["class_name"]["widget"].get().strip()
                if not name or not re.match(r"^[a-zA-Z_]\w*$", name):
                    messagebox.showerror("錯誤", "類別名稱必須為有效 Python 標識符",
                                         parent=self.dialog)
                    return
                element.class_name = name
                element.parent_class = self._fields["parent_class"]["widget"].get().strip() or None
                attr_raw = self._fields["attributes"]["widget"].get("1.0", tk.END).strip()
                try:
                    element.attributes = json.loads(attr_raw) if attr_raw else {}
                except json.JSONDecodeError as exc:
                    messagebox.showerror("錯誤", f"屬性必須為有效 JSON：{exc}",
                                         parent=self.dialog)
                    return

            for key, spec in self._fields.items():
                if not key.startswith("_opt_"):
                    continue
                opt_key = key[len("_opt_"):]
                if spec.get("kind") == "bool":
                    continue
                if "widget" in spec:
                    element.options[opt_key] = spec["widget"].get().strip()
                elif "var" in spec:
                    element.options[opt_key] = spec["var"].get()

            if etype in (ElementType.PROCESS,) and element.code:
                self.symbols.update_from_code(element.code)
            if etype == ElementType.FUNCTION and element.function_name:
                self.symbols.register_function(
                    element.function_name, element.function_params or ""
                )
            if etype == ElementType.CLASS and element.class_name:
                self.symbols.register_class(
                    element.class_name, element.attributes, element.methods or []
                )
            if self.on_saved:
                self.on_saved(element)
            self.dialog.destroy()
        except Exception as exc:
            messagebox.showerror("錯誤", f"儲存失敗：{exc}", parent=self.dialog)


class ConnectionEditDialog:
    def __init__(self, parent, connection: Connection, flowchart, validator,
                 on_saved: Optional[Callable] = None):
        self.connection = connection
        self.flowchart = flowchart
        self.validator = validator
        self.on_saved = on_saved
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("編輯連線")
        place_geometry(self.dialog, 320, 240)
        self.dialog.transient(parent)

        ttk.Label(self.dialog, text="連線類型：").pack(pady=4)
        self._type = tk.StringVar(value=connection.type)
        ttk.OptionMenu(self.dialog, self._type, connection.type,
                       *ConnectionType.ALL).pack(pady=4)
        ttk.Label(self.dialog, text="呼叫參數（僅限 Call）：").pack()
        self._params = ttk.Entry(self.dialog, width=36)
        self._params.insert(0, connection.call_params or "")
        self._params.pack(pady=4)
        ttk.Label(self.dialog, text="優先級：").pack()
        self._priority = ttk.Entry(self.dialog, width=12)
        self._priority.insert(0, str(connection.priority))
        self._priority.pack(pady=4)
        buttons = ttk.Frame(self.dialog)
        buttons.pack(pady=10)
        ttk.Button(buttons, text="儲存", command=self._save).pack(side=tk.LEFT)
        ttk.Button(buttons, text="取消", command=self.dialog.destroy).pack(side=tk.LEFT, padx=6)
        self.dialog.protocol("WM_DELETE_WINDOW", self.dialog.destroy)

    def show(self) -> None:
        self.dialog.wait_window()

    def _save(self) -> None:
        target = self.flowchart.element_by_id(self.connection.target_id)
        result = self.validator.validate_connection(
            self._type.get(), self._params.get().strip(),
            self._priority.get().strip(), target,
        )
        if not result.ok:
            messagebox.showerror("錯誤", result.message, parent=self.dialog)
            return
        for other in self.flowchart.connections:
            if (other is not self.connection
                    and other.source_id == self.connection.source_id
                    and other.target_id == self.connection.target_id
                    and other.type == self._type.get()):
                messagebox.showerror("錯誤", f"已經存在相同的 {self._type.get()} 連線",
                                     parent=self.dialog)
                return
        self.connection.type = self._type.get()
        self.connection.call_params = self._params.get().strip()
        self.connection.priority = int(self._priority.get().strip() or 0)
        if self.on_saved:
            self.on_saved(self.connection)
        self.dialog.destroy()


class VariablesDialog:
    def __init__(self, parent, variables: dict, symbols: SymbolTable):
        self.variables = variables
        self.symbols = symbols
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("變數管理")
        place_geometry(self.dialog, 420, 380)
        self.dialog.transient(parent)
        ttk.Label(self.dialog, text="變數名稱 | 初始值").pack(pady=4)
        self.tree = ttk.Treeview(self.dialog, columns=("Name", "Value"), show="headings")
        self.tree.heading("Name", text="變數名稱")
        self.tree.heading("Value", text="初始值")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self._refresh()
        buttons = ttk.Frame(self.dialog)
        buttons.pack(pady=6)
        ttk.Button(buttons, text="新增", command=self._add).pack(side=tk.LEFT)
        ttk.Button(buttons, text="編輯", command=self._edit).pack(side=tk.LEFT, padx=4)
        ttk.Button(buttons, text="刪除", command=self._delete).pack(side=tk.LEFT)
        ttk.Button(buttons, text="關閉", command=self.dialog.destroy).pack(side=tk.LEFT, padx=4)

    def _refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for name, value in self.variables.items():
            self.tree.insert("", tk.END, values=(name, value))

    def _add(self) -> None:
        name = simpledialog.askstring("輸入", "輸入變數名稱：", parent=self.dialog)
        if not name or not name.isidentifier():
            messagebox.showerror("錯誤", "變數名稱無效", parent=self.dialog)
            return
        value = simpledialog.askstring(
            "輸入", f"輸入 {name} 的初始值（例如：10, 'text', True）：", parent=self.dialog
        )
        if value is None:
            return
        try:
            eval(value, {"__builtins__": {}})
        except Exception as exc:
            messagebox.showerror("錯誤", f"初始值無效：{exc}", parent=self.dialog)
            return
        self.variables[name] = value
        self.symbols.variables[name] = value
        self.symbols.defined_variables.add(name)
        self._refresh()

    def _edit(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("提示", "請選擇一個變數", parent=self.dialog)
            return
        name, value = self.tree.item(selected[0], "values")
        new_value = simpledialog.askstring(
            "輸入", f"編輯 {name} 的初始值：", initialvalue=value, parent=self.dialog
        )
        if new_value is None:
            return
        try:
            eval(new_value, {"__builtins__": {}})
        except Exception as exc:
            messagebox.showerror("錯誤", f"初始值無效：{exc}", parent=self.dialog)
            return
        self.variables[name] = new_value
        self.symbols.variables[name] = new_value
        self._refresh()

    def _delete(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("提示", "請選擇一個變數", parent=self.dialog)
            return
        name = self.tree.item(selected[0], "values")[0]
        self.variables.pop(name, None)
        self.symbols.variables.pop(name, None)
        self.symbols.defined_variables.discard(name)
        self._refresh()


class ModulesDialog:
    def __init__(self, parent, symbols: SymbolTable, on_changed: Optional[Callable] = None):
        self.symbols = symbols
        self.on_changed = on_changed
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("匯入模組")
        place_geometry(self.dialog, 520, 400)
        self.dialog.transient(parent)
        ttk.Label(self.dialog, text="已匯入模組：").pack(pady=4)
        self.tree = ttk.Treeview(self.dialog, columns=("Name", "Type"), show="headings")
        self.tree.heading("Name", text="模組名稱/路徑")
        self.tree.heading("Type", text="類型")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self._refresh()
        buttons = ttk.Frame(self.dialog)
        buttons.pack(pady=6)
        ttk.Button(buttons, text="匯入檔案 (.py)", command=self._import_file).pack(side=tk.LEFT)
        ttk.Button(buttons, text="匯入資料夾", command=self._import_folder).pack(side=tk.LEFT, padx=4)
        ttk.Button(buttons, text="移除", command=self._delete).pack(side=tk.LEFT)
        ttk.Button(buttons, text="關閉", command=self.dialog.destroy).pack(side=tk.LEFT, padx=4)

    def _refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for lib in self.symbols.libraries:
            self.tree.insert("", tk.END, values=(lib, "標準/第三方庫"))
        for mod_name, path in self.symbols.custom_modules:
            self.tree.insert("", tk.END, values=(mod_name, path))

    def _notify(self) -> None:
        self._refresh()
        if self.on_changed:
            self.on_changed()

    def _import_file(self) -> None:
        file_path = filedialog.askopenfilename(
            filetypes=[("Python 檔案", "*.py")], parent=self.dialog
        )
        if not file_path:
            return
        import importlib.util
        module_name = os.path.splitext(os.path.basename(file_path))[0]
        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            if module_name not in [m[0] for m in self.symbols.custom_modules]:
                self.symbols.custom_modules.append((module_name, file_path))
            self.symbols.imported_names[module_name] = module_name
            self._notify()
        except Exception as exc:
            messagebox.showerror("錯誤", f"無法匯入 '{file_path}'：{exc}", parent=self.dialog)

    def _import_folder(self) -> None:
        folder_path = filedialog.askdirectory(parent=self.dialog)
        if not folder_path:
            return
        import importlib
        module_name = os.path.basename(folder_path)
        try:
            if folder_path not in sys.path:
                sys.path.append(folder_path)
            importlib.import_module(module_name)
            if module_name not in [m[0] for m in self.symbols.custom_modules]:
                self.symbols.custom_modules.append((module_name, folder_path))
            self.symbols.imported_names[module_name] = module_name
            self._notify()
        except Exception as exc:
            messagebox.showerror("錯誤", f"無法匯入資料夾：{exc}", parent=self.dialog)

    def _delete(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("提示", "請選擇一個模組", parent=self.dialog)
            return
        name = self.tree.item(selected[0], "values")[0]
        if name in self.symbols.libraries:
            self.symbols.libraries.remove(name)
        else:
            for mod_name, path in list(self.symbols.custom_modules):
                if mod_name == name:
                    self.symbols.custom_modules.remove((mod_name, path))
                    if mod_name in sys.modules:
                        del sys.modules[mod_name]
                    if path in sys.path:
                        sys.path.remove(path)
                    break
        self.symbols.imported_names.pop(name, None)
        self._notify()


class DocLookupDialog:
    def __init__(self, parent, provider: CompletionProvider, initial: str = ""):
        self.provider = provider
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("函式說明")
        place_geometry(self.dialog, 520, 420)
        self.dialog.transient(parent)
        top = ttk.Frame(self.dialog, padding=8)
        top.pack(fill=tk.X)
        ttk.Label(top, text="名稱：").pack(side=tk.LEFT)
        self._entry = ttk.Entry(top, width=40)
        self._entry.insert(0, initial)
        self._entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        ttk.Button(top, text="查詢", command=self._lookup).pack(side=tk.LEFT)
        self._body = tk.Text(self.dialog, wrap=tk.WORD, state="disabled")
        self._body.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.dialog.bind("<Return>", lambda e: self._lookup())
        if initial:
            self._lookup()

    def show(self) -> None:
        self.dialog.wait_window()

    def _lookup(self) -> None:
        name = self._entry.get().strip()
        self._body.config(state="normal")
        self._body.delete("1.0", tk.END)
        if not name:
            self._body.insert("1.0", "請輸入名稱")
        else:
            info = get_callable_info(name)
            if info is not None:
                lines = [
                    f"名稱：{info.full_name}",
                    f"類型：{info.kind}",
                    f"簽名：{info.signature}",
                ]
                if info.params:
                    lines.append("參數：")
                    for p in info.params:
                        default = f" = {p['default']}" if p["default"] else ""
                        lines.append(f"  - {p['name']}{default}")
                if info.source_file:
                    lines.append(f"來源：{info.source_file}")
                lines.append("")
                lines.append("說明：")
                lines.append(info.doc or "（無 docstring）")
                self._body.insert("1.0", "\n".join(lines))
            else:
                found, signature, doc = self.provider.describe_name(name)
                if found:
                    self._body.insert(
                        "1.0", f"名稱：{name}\n簽名：{signature}\n\n說明：\n{doc or '（無）'}"
                    )
                else:
                    from .pypi_browser import PyPIClientHelper
                    info = PyPIClientHelper.lookup(name.split(".")[0])
                    if info is not None:
                        self._body.insert(
                            "1.0",
                            f"本機未找到 '{name}'。\n\nPyPI 套件資訊：\n"
                            f"{info.name} {info.version}\n{info.summary}\n{info.home_page}",
                        )
                    else:
                        self._body.insert("1.0", f"未找到 '{name}'（本機與 PyPI）")
        self._body.config(state="disabled")


class ShortcutDialog:
    def __init__(self, parent, manager: ShortcutManager, on_changed: Optional[Callable] = None):
        self.manager = manager
        self.on_changed = on_changed
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("快速鍵設定")
        place_geometry(self.dialog, 420, 420)
        self.dialog.transient(parent)
        ttk.Label(self.dialog, text="選擇動作後按「變更」，再按下新按鍵").pack(pady=4)
        self.tree = ttk.Treeview(self.dialog, columns=("Action", "Keys"), show="headings")
        self.tree.heading("Action", text="動作")
        self.tree.heading("Keys", text="快速鍵")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self._refresh()
        buttons = ttk.Frame(self.dialog)
        buttons.pack(pady=6)
        ttk.Button(buttons, text="變更", command=self._rebind).pack(side=tk.LEFT)
        ttk.Button(buttons, text="還原預設", command=self._reset).pack(side=tk.LEFT, padx=4)
        ttk.Button(buttons, text="關閉", command=self.dialog.destroy).pack(side=tk.LEFT)

    def _refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for action, label in ACTION_LABELS.items():
            self.tree.insert("", tk.END, iid=action, values=(
                label, display_name(self.manager.get(action))
            ))

    def _rebind(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("提示", "請選擇一個動作", parent=self.dialog)
            return
        action = selected[0]
        capture = {"seq": None}

        def on_key(event):
            if event.keysym in ("Control_L", "Control_R", "Shift_L", "Shift_R",
                                "Alt_L", "Alt_R", "Meta_L", "Meta_R"):
                return
            parts = []
            if event.state & 0x4:
                parts.append("Control")
            if event.state & 0x1:
                parts.append("Shift")
            if event.state & 0x8:
                parts.append("Alt")
            key = event.keysym
            if len(key) == 1:
                key = key.lower()
            parts.append(key)
            capture["seq"] = "<" + "-".join(parts) + ">"
            self.dialog.unbind("<KeyPress>")
            self._ask_conflict(action, capture["seq"])

        self.dialog.bind("<KeyPress>", on_key)
        messagebox.showinfo("變更快速鍵", "請按下新的按鍵組合…", parent=self.dialog)

    def _ask_conflict(self, action: str, sequence: str) -> None:
        error = self.manager.set(action, sequence)
        if error:
            if messagebox.askyesno("衝突", f"{error}\n仍要使用嗎？", parent=self.dialog):
                for other, existing in list(self.manager.bindings.items()):
                    if other != action and existing == sequence:
                        self.manager.bindings[other] = ""
                self.manager.set(action, sequence)
            else:
                return
        self._refresh()
        if self.on_changed:
            self.on_changed()

    def _reset(self) -> None:
        self.manager.reset()
        self._refresh()
        if self.on_changed:
            self.on_changed()


class PolicyDialog:
    def __init__(self, parent, policy: CodePolicy, on_applied: Optional[Callable] = None):
        self.original = policy
        self.policy = CodePolicy.from_dict(policy.to_dict())
        self.on_applied = on_applied
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("安全政策（黑/白名單）")
        place_geometry(self.dialog, 560, 520)
        self.dialog.transient(parent)

        top = ttk.Frame(self.dialog, padding=6)
        top.pack(fill=tk.X)
        ttk.Label(top, text="預設檔：").pack(side=tk.LEFT)
        self._preset = tk.StringVar(value=self.policy.preset_name)
        ttk.OptionMenu(top, self._preset, self.policy.preset_name,
                       PRESET_LENIENT, PRESET_STANDARD, PRESET_STRICT,
                       "自訂").pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="套用預設", command=self._apply_preset).pack(side=tk.LEFT)
        ttk.Label(top, text="模式：").pack(side=tk.LEFT, padx=(12, 0))
        self._mode = tk.StringVar(value=self.policy.mode)
        ttk.Radiobutton(top, text="黑名單", value="blacklist",
                        variable=self._mode).pack(side=tk.LEFT)
        ttk.Radiobutton(top, text="白名單", value="whitelist",
                        variable=self._mode).pack(side=tk.LEFT)

        notebook = ttk.Notebook(self.dialog)
        notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self._modules = self._make_list_tab(notebook, "模組名單")
        self._functions = self._make_list_tab(notebook, "函式/內建名單")
        self._regex = self._make_list_tab(notebook, "Regex 規則")

        options = ttk.Frame(self.dialog)
        options.pack(fill=tk.X, padx=6)
        self._dunder = tk.BooleanVar(value=self.policy.deny_dunder)
        self._reflection = tk.BooleanVar(value=self.policy.deny_reflection)
        ttk.Checkbutton(options, text="禁止 dunder 屬性存取",
                        variable=self._dunder).pack(side=tk.LEFT)
        ttk.Checkbutton(options, text="禁止反射呼叫（getattr/setattr 等）",
                        variable=self._reflection).pack(side=tk.LEFT)

        buttons = ttk.Frame(self.dialog)
        buttons.pack(pady=8)
        ttk.Button(buttons, text="儲存並套用", command=self._save).pack(side=tk.LEFT)
        ttk.Button(buttons, text="取消", command=self.dialog.destroy).pack(side=tk.LEFT, padx=6)

    def _make_list_tab(self, notebook, title: str):
        frame = ttk.Frame(notebook)
        notebook.add(frame, text=title)
        tree = ttk.Treeview(frame, columns=("Value",), show="headings")
        tree.heading("Value", text="值")
        tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        row = ttk.Frame(frame)
        row.pack(fill=tk.X, padx=4, pady=2)
        entry = ttk.Entry(row)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        def add():
            value = entry.get().strip()
            if value:
                tree.insert("", tk.END, values=(value,))
                entry.delete(0, tk.END)
        def remove():
            for item in tree.selection():
                tree.delete(item)
        ttk.Button(row, text="新增", command=add).pack(side=tk.LEFT, padx=2)
        ttk.Button(row, text="刪除", command=remove).pack(side=tk.LEFT)
        frame._tree = tree
        return frame

    def _fill(self, tab, values):
        tree = tab._tree
        for item in tree.get_children():
            tree.delete(item)
        for value in sorted(values):
            tree.insert("", tk.END, values=(value,))

    def _collect(self, tab):
        return [tab._tree.item(item, "values")[0] for item in tab._tree.get_children()]

    def _apply_preset(self) -> None:
        name = self._preset.get()
        if name not in (PRESET_LENIENT, PRESET_STANDARD, PRESET_STRICT):
            return
        self.policy = CodePolicy.from_preset(name)
        self._mode.set(self.policy.mode)
        self._dunder.set(self.policy.deny_dunder)
        self._reflection.set(self.policy.deny_reflection)
        self._fill(self._modules, self.policy.modules)
        self._fill(self._functions, self.policy.functions)
        self._fill(self._regex, self.policy.regex_rules)

    def _save(self) -> None:
        self.policy.mode = self._mode.get()
        self.policy.modules = set(self._collect(self._modules))
        self.policy.functions = set(self._collect(self._functions))
        self.policy.regex_rules = list(self._collect(self._regex))
        self.policy.deny_dunder = bool(self._dunder.get())
        self.policy.deny_reflection = bool(self._reflection.get())
        self.policy.preset_name = (
            self._preset.get() if self._preset.get() != "自訂" else "自訂"
        )
        if self.on_applied:
            self.on_applied(self.policy)
        self.dialog.destroy()

    def open(self) -> None:
        self._fill(self._modules, self.policy.modules)
        self._fill(self._functions, self.policy.functions)
        self._fill(self._regex, self.policy.regex_rules)
        self.dialog.wait_window()


class SnippetDialog:
    def __init__(self, parent, library: SnippetLibrary):
        self.library = library
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("程式碼片段庫")
        place_geometry(self.dialog, 520, 420)
        self.dialog.transient(parent)
        self.tree = ttk.Treeview(
            self.dialog, columns=("Name", "Category"), show="headings"
        )
        self.tree.heading("Name", text="名稱")
        self.tree.heading("Category", text="分類")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._load_selected())
        self._code = tk.Text(self.dialog, height=8)
        self._code.pack(fill=tk.X, padx=6)
        self._refresh()
        buttons = ttk.Frame(self.dialog)
        buttons.pack(pady=6)
        ttk.Button(buttons, text="新增", command=self._add).pack(side=tk.LEFT)
        ttk.Button(buttons, text="刪除", command=self._delete).pack(side=tk.LEFT, padx=4)
        ttk.Button(buttons, text="儲存", command=self._save).pack(side=tk.LEFT)
        ttk.Button(buttons, text="關閉", command=self.dialog.destroy).pack(side=tk.LEFT, padx=4)

    def _refresh(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for snippet in self.library.snippets:
            self.tree.insert("", tk.END, iid=snippet.name,
                             values=(snippet.name, snippet.category))

    def _load_selected(self) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        snippet = self.library.by_name(selected[0])
        if snippet:
            self._code.delete("1.0", tk.END)
            self._code.insert("1.0", snippet.code)

    def _add(self) -> None:
        name = simpledialog.askstring("新增片段", "片段名稱：", parent=self.dialog)
        if not name:
            return
        category = simpledialog.askstring("新增片段", "分類：", initialvalue="一般",
                                          parent=self.dialog) or "一般"
        self.library.add(Snippet(name, "", category))
        self._refresh()

    def _delete(self) -> None:
        selected = self.tree.selection()
        if selected:
            self.library.remove(selected[0])
            self._refresh()

    def _save(self) -> None:
        selected = self.tree.selection()
        if selected:
            snippet = self.library.by_name(selected[0])
            if snippet:
                snippet.code = self._code.get("1.0", tk.END).rstrip("\n")


class HelpDialog:
    CONTENT = """流程圖轉程式碼工具使用說明

1. 新增元素：左側選擇類型後按「新增元素」，或畫布右鍵選單。
2. 連線：選擇 Body/Exit/Call，連線方式可在左側切換：
   - 窄環（預設）：按元素=移動，按元素外側起始連線拖到目標。
   - 連線埠：元素四邊藍色圓點，從圓點拖出到目標。
   - 兩次點擊：點來源元素、再點目標元素即完成連線。
   - 右鍵拖曳：左鍵移動元素，右鍵拖曳畫連線。
   連線建立中按 Esc 取消；右鍵連線可編輯/刪除。
3. 同步元素：SyncEvent/Lock/Semaphore/Barrier 與 Thread/Task 可建立多執行緒流程。
4. 外部函式：工具 → 模組函式瀏覽器，選擇函式建立 External 元素，用 Call 連線呼叫。
5. 自訂外掛：extensions/ 資料夾放入 .py 外掛（詳見 extensions/README.md）。
6. 程式碼片段：編輯對話框可插入片段並代換 {佔位符}。
7. 自動補全：編輯時 Ctrl+Space；Ctrl+K 查詢函式說明。
8. 安全政策：工具 → 安全政策，設定模組/函式黑名單或白名單。
9. 執行：F5 動畫執行（Esc 停止）、Ctrl+F5 快速預覽。
10. 快速鍵：工具 → 快速鍵設定，可自訂並存於 shortcuts.json。
11. pip 搜尋：工具 → pip 套件搜尋（Ctrl+P），可搜尋並安裝套件。
12. 診斷面板：下方即時列出流程圖問題，點選可定位元素。
"""

    def __init__(self, parent):
        dialog = tk.Toplevel(parent)
        dialog.title("使用說明")
        place_geometry(dialog, 640, 480)
        dialog.transient(parent)
        text = tk.Text(dialog, wrap=tk.WORD, font=("Microsoft JhengHei", 10))
        text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        text.insert("1.0", self.CONTENT)
        text.config(state="disabled")
        ttk.Button(dialog, text="關閉", command=dialog.destroy).pack(pady=6)
