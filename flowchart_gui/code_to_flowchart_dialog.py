from __future__ import annotations

import ast
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Optional

from flowchart_core import Project, code_to_project
from .dialogs import place_geometry


class CodeToFlowchartDialog:
    """Dialog for entering/loading Python code and converting it to a Flowchart."""

    def __init__(self, parent: tk.Tk, initial_code: str = "",
                 on_converted: Optional[Callable[[Project, bool], None]] = None):
        self.parent = parent
        self.on_converted = on_converted
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("程式碼轉流程圖")
        place_geometry(self.dialog, 700, 560)
        self.dialog.transient(parent)

        self._replace_var = tk.BooleanVar(value=True)
        self._build_ui(initial_code)
        self.dialog.protocol("WM_DELETE_WINDOW", self.dialog.destroy)

    def show(self) -> None:
        self.dialog.wait_window()

    def _build_ui(self, initial_code: str) -> None:
        top_bar = ttk.Frame(self.dialog, padding=(8, 8, 8, 4))
        top_bar.pack(fill=tk.X)

        ttk.Label(top_bar, text="請在下方貼上或輸入 Python 程式碼：").pack(side=tk.LEFT)
        ttk.Button(top_bar, text="載入 .py 檔...", command=self._load_file).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top_bar, text="清空", command=self._clear).pack(side=tk.RIGHT)

        text_frame = ttk.Frame(self.dialog, padding=(8, 0, 8, 4))
        text_frame.pack(fill=tk.BOTH, expand=True)

        self.text = tk.Text(text_frame, wrap="none", undo=True, font=("Consolas", 10))
        h_scroll = ttk.Scrollbar(text_frame, orient="horizontal", command=self.text.xview)
        v_scroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.text.yview)
        self.text.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)

        self.text.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)

        if initial_code:
            self.text.insert("1.0", initial_code)

        opt_frame = ttk.Frame(self.dialog, padding=(8, 4))
        opt_frame.pack(fill=tk.X)

        ttk.Radiobutton(opt_frame, text="取代目前畫布", variable=self._replace_var,
                        value=True).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(opt_frame, text="附加至現有流程圖", variable=self._replace_var,
                        value=False).pack(side=tk.LEFT)

        btn_frame = ttk.Frame(self.dialog, padding=(8, 8))
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="轉換為流程圖", command=self._convert).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_frame, text="取消", command=self.dialog.destroy).pack(side=tk.RIGHT)

    def _load_file(self) -> None:
        file_path = filedialog.askopenfilename(
            parent=self.dialog,
            filetypes=[("Python 檔案", "*.py"), ("所有檔案", "*.*")],
            title="選擇 Python 檔案",
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.text.delete("1.0", tk.END)
            self.text.insert("1.0", content)
        except Exception as exc:
            messagebox.showerror("錯誤", f"讀取檔案失敗：{exc}", parent=self.dialog)

    def _clear(self) -> None:
        self.text.delete("1.0", tk.END)

    def _convert(self) -> None:
        code = self.text.get("1.0", tk.END).strip()
        if not code:
            messagebox.showinfo("提示", "請先輸入或載入程式碼", parent=self.dialog)
            return

        try:
            project = code_to_project(code)
        except SyntaxError as syn_err:
            messagebox.showerror(
                "語法錯誤",
                f"Python 語法錯誤（第 {syn_err.lineno} 行）：\n{syn_err.msg}\n{syn_err.text or ''}",
                parent=self.dialog,
            )
            return
        except Exception as exc:
            messagebox.showerror("轉換失敗", f"無法轉換程式碼：{exc}", parent=self.dialog)
            return

        replace = self._replace_var.get()
        if self.on_converted:
            self.on_converted(project, replace)
        self.dialog.destroy()
