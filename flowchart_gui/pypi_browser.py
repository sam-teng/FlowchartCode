from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

from flowchart_core import pypi_client
from flowchart_core.pypi_client import PackageInfo

from .dialogs import place_geometry


class PyPIClientHelper:
    @staticmethod
    def lookup(name: str) -> Optional[PackageInfo]:
        return pypi_client.get_package_info(name, timeout=4)


class PyPIBrowserDialog:
    def __init__(self, parent, on_installed: Optional[Callable[[], None]] = None):
        self.on_installed = on_installed
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("pip 套件搜尋")
        place_geometry(self.dialog, 760, 520)
        self.dialog.transient(parent)

        self.notebook = ttk.Notebook(self.dialog)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        search_tab = ttk.Frame(self.notebook)
        self.notebook.add(search_tab, text="PyPI 搜尋")
        installed_tab = ttk.Frame(self.notebook)
        self.notebook.add(installed_tab, text="已安裝")

        top = ttk.Frame(search_tab)
        top.pack(fill=tk.X, padx=4, pady=4)
        ttk.Label(top, text="關鍵字：").pack(side=tk.LEFT)
        self._query = ttk.Entry(top, width=40)
        self._query.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self._query.bind("<Return>", lambda e: self._search())
        ttk.Button(top, text="搜尋", command=self._search).pack(side=tk.LEFT)

        self._results = ttk.Treeview(
            search_tab, columns=("Name", "Version", "Summary"), show="headings"
        )
        self._results.heading("Name", text="名稱")
        self._results.heading("Version", text="版本")
        self._results.heading("Summary", text="簡介")
        self._results.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self._results.bind("<<TreeviewSelect>>", lambda e: self._load_info())

        detail_frame = ttk.LabelFrame(search_tab, text="詳情")
        detail_frame.pack(fill=tk.BOTH, padx=4, pady=4)
        self._detail = tk.Text(detail_frame, height=8, state="disabled")
        self._detail.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        actions = ttk.Frame(search_tab)
        actions.pack(fill=tk.X, padx=4, pady=4)
        ttk.Button(actions, text="安裝（寫入目前環境）",
                   command=self._install).pack(side=tk.LEFT)
        ttk.Button(actions, text="開啟官網", command=self._open_home).pack(
            side=tk.LEFT, padx=4
        )

        installed_top = ttk.Frame(installed_tab)
        installed_top.pack(fill=tk.X, padx=4, pady=4)
        ttk.Button(installed_top, text="重新整理",
                   command=self._refresh_installed).pack(side=tk.LEFT)
        self._installed = ttk.Treeview(
            installed_tab, columns=("Name", "Version"), show="headings"
        )
        self._installed.heading("Name", text="名稱")
        self._installed.heading("Version", text="版本")
        self._installed.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        log_frame = ttk.LabelFrame(self.dialog, text="安裝輸出")
        log_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
        self._log = tk.Text(log_frame, height=6, state="disabled")
        self._log.pack(fill=tk.X, padx=4, pady=4)

        self._info: Optional[PackageInfo] = None
        self._refresh_installed()

    def _search(self) -> None:
        query = self._query.get().strip()
        if not query:
            return
        for item in self._results.get_children():
            self._results.delete(item)
        self._append_log(f"搜尋 '{query}' …")
        try:
            results = pypi_client.search_packages(query, timeout=8)
        except Exception as exc:
            self._append_log(f"搜尋失敗：{exc}")
            return
        if not results:
            self._append_log("沒有結果（網路不可用或 PyPI 改版，請見「已安裝」分頁）")
            return
        for result in results:
            self._results.insert(
                "", tk.END, iid=result.name,
                values=(result.name, result.version, result.summary[:120]),
            )
        self._append_log(f"找到 {len(results)} 個結果")

    def _load_info(self) -> None:
        selection = self._results.selection()
        if not selection:
            return
        name = selection[0]
        self._append_log(f"取得 {name} 詳情 …")
        self._info = pypi_client.get_package_info(name, timeout=8)
        self._detail.config(state="normal")
        self._detail.delete("1.0", tk.END)
        if self._info:
            lines = [
                f"{self._info.name} {self._info.version}",
                f"作者：{self._info.author}",
                f"Python：{self._info.requires_python}",
                f"官網：{self._info.home_page}",
                "",
                self._info.summary,
            ]
            if self._info.requires_dist:
                lines.append("")
                lines.append("相依：" + ", ".join(self._info.requires_dist[:10]))
            self._detail.insert("1.0", "\n".join(lines))
        else:
            self._detail.insert("1.0", "無法取得詳情")
        self._detail.config(state="disabled")

    def _install(self) -> None:
        selection = self._results.selection()
        if not selection:
            messagebox.showinfo("提示", "請先搜尋並選擇套件", parent=self.dialog)
            return
        name = selection[0]
        if not messagebox.askyesno(
                "確認安裝",
                f"將執行 pip install {name}，寫入目前 Python 環境：\n"
                f"{__import__('sys').executable}\n確定繼續？",
                parent=self.dialog):
            return
        self._append_log(f"安裝 {name} 開始 …")
        self.dialog.update()

        def on_line(line: str) -> None:
            self._append_log(line)

        ok, message = pypi_client.install_package(name, on_output=on_line)
        if ok:
            self._append_log(f"✓ {name} 安裝完成")
            self._refresh_installed()
            if self.on_installed:
                self.on_installed()
        else:
            self._append_log(f"✗ 安裝失敗：\n{message}")

    def _open_home(self) -> None:
        if self._info and self._info.home_page:
            import webbrowser
            webbrowser.open(self._info.home_page)

    def _refresh_installed(self) -> None:
        for item in self._installed.get_children():
            self._installed.delete(item)
        for result in pypi_client.list_installed():
            self._installed.insert(
                "", tk.END, values=(result.name, result.version)
            )

    def _append_log(self, text: str) -> None:
        self._log.config(state="normal")
        self._log.insert(tk.END, text.rstrip() + "\n")
        self._log.see(tk.END)
        self._log.config(state="disabled")
