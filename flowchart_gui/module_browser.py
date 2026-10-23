from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from flowchart_core import Element, ElementType, SymbolTable, list_module_callables

from .dialogs import place_geometry


class ModuleBrowserDialog:
    def __init__(self, parent, symbols: SymbolTable,
                 on_create_external: Optional[Callable[[str, object], None]] = None):
        self.symbols = symbols
        self.on_create_external = on_create_external
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("模組函式瀏覽器")
        place_geometry(self.dialog, 700, 480)
        self.dialog.transient(parent)
        ttk.Label(self.dialog, text="已匯入模組的公開函式（雙擊建立外部函式元素）").pack(
            anchor="w", padx=6, pady=4
        )
        pane = ttk.PanedWindow(self.dialog, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        left = ttk.Frame(pane)
        pane.add(left, minsize=220)
        self.module_tree = ttk.Treeview(left, columns=("Name",), show="headings")
        self.module_tree.heading("Name", text="模組")
        self.module_tree.pack(fill=tk.BOTH, expand=True)
        self.module_tree.bind("<<TreeviewSelect>>", lambda e: self._load_callables())

        right = ttk.Frame(pane)
        pane.add(right, minsize=360)
        self.callable_tree = ttk.Treeview(
            right, columns=("Name", "Kind", "Signature"), show="headings"
        )
        self.callable_tree.heading("Name", text="名稱")
        self.callable_tree.heading("Kind", text="類型")
        self.callable_tree.heading("Signature", text="簽名")
        self.callable_tree.pack(fill=tk.BOTH, expand=True)
        self.callable_tree.bind("<<TreeviewSelect>>", lambda e: self._load_detail())
        self.callable_tree.bind("<Double-Button-1>", lambda e: self._create())

        self.detail = tk.Text(right, height=8, state="disabled")
        self.detail.pack(fill=tk.X, pady=4)

        buttons = ttk.Frame(self.dialog)
        buttons.pack(pady=6)
        ttk.Button(buttons, text="建立外部函式元素", command=self._create).pack(side=tk.LEFT)
        ttk.Button(buttons, text="重新整理", command=self._refresh).pack(side=tk.LEFT, padx=6)
        ttk.Button(buttons, text="關閉", command=self.dialog.destroy).pack(side=tk.LEFT)
        self._refresh()

    def _refresh(self) -> None:
        for item in self.module_tree.get_children():
            self.module_tree.delete(item)
        for lib in self.symbols.libraries:
            self.module_tree.insert("", tk.END, iid=lib, values=(lib,))
        for mod_name, _path in self.symbols.custom_modules:
            self.module_tree.insert("", tk.END, iid=mod_name, values=(mod_name,))

    def _current_module(self) -> Optional[str]:
        selection = self.module_tree.selection()
        return selection[0] if selection else None

    def _load_callables(self) -> None:
        for item in self.callable_tree.get_children():
            self.callable_tree.delete(item)
        module = self._current_module()
        if not module:
            return
        for info in list_module_callables(module):
            self.callable_tree.insert(
                "", tk.END, iid=info.qualname,
                values=(info.name, info.kind, info.signature),
            )

    def _current_callable(self):
        selection = self.callable_tree.selection()
        if not selection:
            return None
        module = self._current_module()
        qualname = selection[0]
        for info in list_module_callables(module or ""):
            if info.qualname == qualname:
                return info
        return None

    def _load_detail(self) -> None:
        info = self._current_callable()
        self.detail.config(state="normal")
        self.detail.delete("1.0", tk.END)
        if info:
            lines = [
                f"{info.full_name}  ({info.kind})",
                f"簽名：{info.signature}",
            ]
            if info.source_file:
                lines.append(f"來源：{info.source_file}")
            lines.append("")
            lines.append(info.doc or "（無 docstring）")
            self.detail.insert("1.0", "\n".join(lines))
        self.detail.config(state="disabled")

    def _create(self) -> None:
        module = self._current_module()
        info = self._current_callable()
        if not module or info is None or self.on_create_external is None:
            return
        self.on_create_external(module, info)
        self.dialog.destroy()
