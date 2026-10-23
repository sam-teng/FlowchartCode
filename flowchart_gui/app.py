from __future__ import annotations

import os
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Optional

from flowchart_core import (
    CodeGenerator, CodePolicy, CodeValidator, Connection, ConnectionType,
    Element, ElementType, ExecutionEvent, ExtensionRegistry, Flowchart,
    FlowchartExecutor, History, Project, SnippetLibrary, SymbolTable,
    analyze, compile_plan, create_default_registry, format_diagnostics,
    load_project, save_project,
)
from flowchart_core.completion import CompletionProvider
from flowchart_core.events import EventKind

from .animation import AnimationPlayer
from .canvas_view import CONNECTION_COLORS, CanvasView, SHAPE_DEFAULTS, SIZE_DEFAULTS
from .dialogs import (
    ConnectionEditDialog, DocLookupDialog, ElementEditDialog, HelpDialog,
    ModulesDialog, PolicyDialog, ShortcutDialog, SnippetDialog, VariablesDialog,
    place_geometry,
)
from .module_browser import ModuleBrowserDialog
from .pypi_browser import PyPIBrowserDialog
from .settings import CONNECTION_MODES, DEFAULT_CONNECTION_MODE, SettingsManager
from .shortcuts import ACTION_LABELS, ShortcutManager, display_name

BUILTIN_PALETTE = [
    ElementType.PROCESS, ElementType.DECISION, ElementType.LOOP,
    ElementType.START_END, ElementType.INPUT, ElementType.OUTPUT,
    ElementType.FUNCTION, ElementType.CLASS, ElementType.COMMENT,
    ElementType.THREAD, ElementType.SYNC_EVENT, ElementType.SYNC_LOCK,
    ElementType.SYNC_SEMAPHORE, ElementType.SYNC_BARRIER, ElementType.EXTERNAL,
]

SYNC_TYPES = {
    ElementType.THREAD, ElementType.SYNC_EVENT, ElementType.SYNC_LOCK,
    ElementType.SYNC_SEMAPHORE, ElementType.SYNC_BARRIER,
}


class _ScrollFrame(ttk.Frame):
    """垂直可捲動的容器：內容高度超過可視區時以滑鼠滾輪捲動。"""

    def __init__(self, parent):
        super().__init__(parent)
        self._canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, width=120)
        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scrollbar.set)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.inner = ttk.Frame(self._canvas)
        self._window = self._canvas.create_window(
            (0, 0), window=self.inner, anchor="nw"
        )
        self.bind("<Configure>", lambda _e: self._canvas.itemconfigure(
            self._window, width=max(self.winfo_width() - 16, 80)))
        self.inner.bind(
            "<Configure>",
            lambda _e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.bind("<MouseWheel>", self._on_wheel)
        self.inner.bind("<MouseWheel>", self._on_wheel)

    def bind_wheel_recursive(self) -> None:
        self._bind_wheel_tree(self.inner)

    def _bind_wheel_tree(self, widget) -> None:
        widget.bind("<MouseWheel>", self._on_wheel)
        for child in widget.winfo_children():
            self._bind_wheel_tree(child)

    def _on_wheel(self, event) -> str:
        delta = getattr(event, "delta", 0)
        if delta:
            self._canvas.yview_scroll(-int(delta / 120), "units")
        return "break"


class FlowchartApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("流程圖轉程式碼工具")
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        width = min(1280, int(screen_w * 0.9))
        height = min(860, int(screen_h * 0.92))
        x = max((screen_w - width) // 2, 0)
        y = max((screen_h - height) // 2, 0)
        root.geometry(f"{width}x{height}+{x}+{y}")
        self.project_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.policy_path = os.path.join(self.project_dir, "policy.json")
        self.shortcuts_path = os.path.join(self.project_dir, "shortcuts.json")
        self.snippets_path = os.path.join(self.project_dir, "snippets.json")
        self.settings_path = os.path.join(self.project_dir, "settings.json")
        self.extensions_dir = os.path.join(self.project_dir, "extensions")

        self.policy = CodePolicy.load(self.policy_path)
        self.snippets = SnippetLibrary()
        self.snippets.load(self.snippets_path)
        self.settings = SettingsManager(self.settings_path)
        self.registry: ExtensionRegistry = create_default_registry(self.extensions_dir)
        self._register_extension_shapes()

        self.project = Project()
        self.symbols = SymbolTable()
        self.validator = CodeValidator(self.symbols, self.policy)
        self.provider = CompletionProvider(
            self.symbols, self.policy,
            snippets_provider=lambda: list(self.snippets.snippets),
        )
        self.history = History()
        self.player = AnimationPlayer(root)
        self.shortcuts = ShortcutManager(self.shortcuts_path)

        self._drag_element: Optional[Element] = None
        self._conn_source: Optional[Element] = None
        self._pressed_pos = None
        self._drag_snapshotted = False
        self._selected_element: Optional[Element] = None
        self._pending_conn_source: Optional[Element] = None
        self._two_click_candidate: Optional[Element] = None
        self._right_pressed_pos = None
        self._executor: Optional[FlowchartExecutor] = None
        self._sub_views: dict[str, tuple] = {}
        self._diag_after = None
        self._element_var = tk.StringVar(value=ElementType.PROCESS)
        self._connection_var = tk.StringVar(value=ConnectionType.BODY)
        self._mode_var = tk.StringVar(value=self.settings.connection_mode)
        self._speed_var = tk.StringVar(value="正常")
        self._diag_items: list = []

        self._build_ui()
        self.shortcuts.bind_all(root, self._shortcut_handlers())
        self.view.attach(self.project.flowchart)
        self.view.set_ports_visible(self.settings.connection_mode == "連線埠")
        self._refresh_diagnostics()

    # ---------- setup ----------

    def _register_extension_shapes(self) -> None:
        for ext in self.registry.all_extensions():
            meta = ext.meta
            if meta.type_name not in SHAPE_DEFAULTS:
                SHAPE_DEFAULTS[meta.type_name] = (meta.shape, meta.color)
                SIZE_DEFAULTS[meta.type_name] = (50, 20)

    def _palette_types(self) -> list:
        types = list(BUILTIN_PALETTE)
        for meta in self.registry.palette_metas():
            if meta.type_name not in types:
                types.append(meta.type_name)
        return types

    def _build_ui(self) -> None:
        self._build_menu()
        self.root.minsize(960, 600)

        self.status = ttk.Label(self.root, text="就緒", anchor="w")
        self.status.pack(fill=tk.X, side=tk.BOTTOM)

        container = ttk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=True)

        outer = ttk.PanedWindow(container, orient=tk.VERTICAL)
        outer.pack(fill=tk.BOTH, expand=True)

        work = ttk.PanedWindow(outer, orient=tk.HORIZONTAL)
        outer.add(work, weight=1)

        left = _ScrollFrame(work)
        work.add(left, weight=0)
        left_inner = left.inner

        ttk.Label(left_inner, text="元素類型：").pack(pady=(8, 2), padx=6, anchor="w")
        ttk.OptionMenu(left_inner, self._element_var, ElementType.PROCESS,
                       *self._palette_types()).pack(fill=tk.X, padx=6)
        ttk.Button(left_inner, text="新增元素",
                   command=lambda: self.add_element(self.view)).pack(fill=tk.X, padx=6, pady=4)

        ttk.Label(left_inner, text="連線類型：").pack(pady=(8, 2), padx=6, anchor="w")
        ttk.OptionMenu(left_inner, self._connection_var, ConnectionType.BODY,
                       *ConnectionType.ALL).pack(fill=tk.X, padx=6)

        ttk.Label(left_inner, text="連線方式：").pack(pady=(8, 2), padx=6, anchor="w")
        ttk.OptionMenu(
            left_inner, self._mode_var, self.settings.connection_mode,
            *CONNECTION_MODES, command=self._on_connection_mode_changed,
        ).pack(fill=tk.X, padx=6)

        for label, command in [
            ("上一步（復原）", self.undo),
            ("下一步（重做）", self.redo),
            ("產生程式碼", self.generate_code),
            ("執行動畫（F5）", self.run_code),
            ("快速預覽（Ctrl+F5）", self.preview_code),
            ("停止（Esc）", self.stop_execution),
            ("清除畫布", self.clear_canvas),
        ]:
            ttk.Button(left_inner, text=label, command=command).pack(
                fill=tk.X, padx=6, pady=2)

        ttk.Separator(left_inner).pack(fill=tk.X, padx=6, pady=8)
        for label, command in [
            ("變數管理", lambda: VariablesDialog(self.root, self.project.variables, self.symbols)),
            ("匯入模組", self._open_modules),
            ("模組函式瀏覽器", self._open_module_browser),
            ("pip 套件搜尋", self._open_pypi),
            ("片段庫", lambda: SnippetDialog(self.root, self.snippets)),
            ("安全政策", self._open_policy),
            ("快速鍵設定", self._open_shortcuts),
        ]:
            ttk.Button(left_inner, text=label, command=command).pack(
                fill=tk.X, padx=6, pady=2)

        center = ttk.Frame(work)
        work.add(center, weight=1)
        self.view = CanvasView(center, "主流程圖")
        self._bind_canvas_events(self.view)

        right = ttk.Frame(work, width=320)
        work.add(right, weight=0)

        code_frame = ttk.LabelFrame(right, text="程式碼")
        code_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.code_text = tk.Text(code_frame, width=30, height=8, undo=True)
        self.code_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        output_frame = ttk.LabelFrame(right, text="輸出")
        output_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.output_text = tk.Text(output_frame, width=30, height=5, state="disabled")
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        ttk.Label(right, text="動畫速度：").pack(anchor="w", padx=4)
        ttk.OptionMenu(right, self._speed_var, "正常", "慢", "正常", "快").pack(
            fill=tk.X, padx=4, pady=(0, 6)
        )

        diag_frame = ttk.LabelFrame(outer, text="診斷面板")
        outer.add(diag_frame, weight=0)
        self.diag_list = tk.Listbox(diag_frame)
        self.diag_list.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)
        self.diag_list.bind("<Double-Button-1>", self._locate_diagnostic)

        left.bind_wheel_recursive()

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(
            label=f"新增（{display_name(self.shortcuts.get('new'))}）", command=self.new_project)
        file_menu.add_command(
            label=f"載入（{display_name(self.shortcuts.get('open'))}）", command=self.load_flowchart)
        file_menu.add_command(
            label=f"儲存（{display_name(self.shortcuts.get('save'))}）", command=self.save_flowchart)
        file_menu.add_separator()
        file_menu.add_command(label="結束", command=self.root.destroy)
        menubar.add_cascade(label="檔案", menu=file_menu)

        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(
            label=f"pip 套件搜尋（{display_name(self.shortcuts.get('pip_search'))}）",
            command=self._open_pypi)
        tools_menu.add_command(label="模組函式瀏覽器", command=self._open_module_browser)
        tools_menu.add_command(label="安全政策", command=self._open_policy)
        tools_menu.add_command(label="快速鍵設定", command=self._open_shortcuts)
        tools_menu.add_command(label="片段庫", command=lambda: SnippetDialog(self.root, self.snippets))
        menubar.add_cascade(label="工具", menu=tools_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(
            label=f"使用說明（{display_name(self.shortcuts.get('help'))}）",
            command=lambda: HelpDialog(self.root))
        menubar.add_cascade(label="說明", menu=help_menu)

    def _shortcut_handlers(self) -> dict:
        return {
            "new": self.new_project,
            "open": self.load_flowchart,
            "save": self.save_flowchart,
            "undo": self.undo,
            "redo": self.redo,
            "generate": self.generate_code,
            "run": self.run_code,
            "preview": self.preview_code,
            "stop": self.stop_execution,
            "delete": self._delete_selected,
            "autocomplete": self._trigger_autocomplete,
            "doc_lookup": lambda: DocLookupDialog(self.root, self.provider),
            "pip_search": self._open_pypi,
            "help": lambda: HelpDialog(self.root),
        }

    # ---------- canvas events ----------

    def _bind_canvas_events(self, view: CanvasView) -> None:
        view.canvas.bind("<Button-1>", lambda e: self._on_press(e, view))
        view.canvas.bind("<B1-Motion>", lambda e: self._on_drag(e, view))
        view.canvas.bind("<ButtonRelease-1>", lambda e: self._on_release(e, view))
        view.canvas.bind("<Button-2>", lambda e: self._on_right_press(e, view))
        view.canvas.bind("<B2-Motion>", lambda e: self._on_right_drag(e, view))
        view.canvas.bind("<ButtonRelease-2>", lambda e: self._on_right_release(e, view))
        view.canvas.bind("<Button-3>", lambda e: self._on_right_press(e, view))
        view.canvas.bind("<B3-Motion>", lambda e: self._on_right_drag(e, view))
        view.canvas.bind("<ButtonRelease-3>", lambda e: self._on_right_release(e, view))

    def _mode(self) -> str:
        mode = self.settings.connection_mode
        if mode not in CONNECTION_MODES:
            mode = DEFAULT_CONNECTION_MODE
        return mode

    def _on_connection_mode_changed(self, value: str) -> None:
        self.settings.set_connection_mode(value)
        self._cancel_pending_connection()
        for view in self._all_views():
            view.set_ports_visible(value == "連線埠")
        self._set_status(f"連線方式：{value}")

    def _all_views(self):
        yield self.view
        for _eid, (_toplevel, view) in list(self._sub_views.items()):
            yield view

    def _on_press(self, event, view: CanvasView) -> None:
        self._pressed_pos = (event.x, event.y)
        self._drag_snapshotted = False
        mode = self._mode()

        if mode == "連線埠":
            port_source = view.find_port_at(event.x, event.y, tolerance=8)
            if port_source is not None:
                self._start_connection(port_source, view,
                                       origin=(event.x, event.y))
                return
            element = view.find_element_at(event.x, event.y, tolerance=28)
            self._select_element(element, view)
            if element is not None:
                self._drag_element = element
            return

        element = view.find_element_at(event.x, event.y, tolerance=28)
        if element is not None:
            self._select_element(element, view)
            self._drag_element = element
            if mode == "兩次點擊":
                self._two_click_candidate = element
            return

        if mode == "窄環":
            near = view.find_element_at(event.x, event.y, tolerance=60)
            if near is not None:
                self._start_connection(near, view, origin=None)
                return
        self._select_element(None, view)

    def _handle_two_click_source(self, element: Element, view: CanvasView) -> None:
        pending = self._pending_conn_source
        if pending is None:
            self._pending_conn_source = element
            view.set_selected(element.id)
            self._set_status("已選連線起點，再點目標元素完成連線（Esc 取消）")
            return
        if pending.id == element.id:
            self._pending_conn_source = None
            view.set_selected(element.id)
            self._set_status("已取消連線")
            return
        self._pending_conn_source = None
        self._complete_connection(pending, element, view)
        view.set_selected(element.id)

    def _start_connection(self, source: Element, view: CanvasView,
                          origin=None) -> None:
        self._conn_source = source
        color = CONNECTION_COLORS.get(self._connection_var.get(), "#5E81AC")
        start = origin
        if start is None:
            start = (source.x, source.y)
        view.start_temp_line(start[0], start[1], color=color)
        view.set_selected(source.id)
        self._set_status("拖曳到目標元素以建立連線（Esc 取消）")

    def _on_drag(self, event, view: CanvasView) -> None:
        if self._drag_element is not None and view.flowchart is not None:
            if view.flowchart.element_by_id(self._drag_element.id) is None:
                self._drag_element = None
                return
            if not self._drag_snapshotted:
                self._snapshot()
                self._drag_snapshotted = True
            self._drag_element.x = event.x
            self._drag_element.y = event.y
            view.move_element_visual(self._drag_element)
        elif self._conn_source is not None:
            view.update_temp_line(event.x, event.y)

    def _on_release(self, event, view: CanvasView) -> None:
        if self._drag_element is not None:
            element = self._drag_element
            self._drag_element = None
            moved = True
            if self._pressed_pos is not None:
                moved = (abs(event.x - self._pressed_pos[0])
                         + abs(event.y - self._pressed_pos[1])) > 6
            if self._mode() == "兩次點擊" and not moved \
                    and self._two_click_candidate is not None:
                self._handle_two_click_source(self._two_click_candidate, view)
                self._two_click_candidate = None
                return
            self._two_click_candidate = None
            if moved and view.flowchart is not None \
                    and view.flowchart.element_by_id(element.id) is not None:
                self._mark_dirty()
            return
        if self._conn_source is not None:
            self._finish_connection(event, view)
            view.end_temp_line()
            self._conn_source = None

    # ---------- right-drag connection mode ----------

    def _on_right_press(self, event, view: CanvasView) -> None:
        self._right_pressed_pos = (event.x, event.y)
        if self._mode() != "右鍵拖曳":
            return
        near = view.find_element_at(event.x, event.y, tolerance=60)
        if near is not None:
            self._start_connection(near, view, origin=(event.x, event.y))

    def _on_right_drag(self, event, view: CanvasView) -> None:
        if self._mode() != "右鍵拖曳" or self._conn_source is None:
            return
        view.update_temp_line(event.x, event.y)

    def _on_right_release(self, event, view: CanvasView) -> None:
        pressed = self._right_pressed_pos
        self._right_pressed_pos = None
        moved = False
        if pressed is not None:
            moved = (abs(event.x - pressed[0]) + abs(event.y - pressed[1])) > 6
        if self._mode() == "右鍵拖曳" and self._conn_source is not None:
            if moved:
                self._finish_connection(event, view)
            view.end_temp_line()
            self._conn_source = None
            if moved:
                return
        if not moved:
            self._on_context(event, view)

    def _cancel_pending_connection(self) -> None:
        if self._pending_conn_source is not None:
            self._pending_conn_source = None
            self._set_status("已取消連線")
        if self._conn_source is not None:
            self.view.end_temp_line()
            self._conn_source = None

    def _finish_connection(self, event, view: CanvasView) -> None:
        source = self._conn_source
        flowchart = view.flowchart
        if source is None or flowchart is None:
            return
        target = view.find_element_at(event.x, event.y, tolerance=60)
        if target is None or target.id == source.id:
            return
        conn_type = self._connection_var.get()

        pre = self.validator.validate_connection_target(conn_type, target)
        if not pre.ok:
            messagebox.showerror("錯誤", pre.message)
            return
        for existing in flowchart.connections:
            if (existing.source_id == source.id
                    and existing.target_id == target.id
                    and existing.type == conn_type):
                messagebox.showerror("錯誤", f"已經存在相同的 {conn_type} 連線")
                return

        call_params = ""
        priority = 0
        if conn_type == ConnectionType.BODY:
            raw = simpledialog.askstring(
                "輸入", "輸入連線優先級（整數，較低值優先）：",
                initialvalue="0", parent=self.root,
            )
            if raw is None:
                return
            try:
                priority = int(raw or 0)
            except ValueError:
                messagebox.showerror("錯誤", "優先級必須為整數")
                return
        elif conn_type == ConnectionType.CALL:
            target_label = (target.function_name or target.class_name
                            or f"{target.opt('module')}.{target.opt('qualname')}"
                            or target.type)
            call_params = simpledialog.askstring(
                "輸入", f"輸入 {target_label} 的呼叫參數（例如：x, 5）：",
                parent=self.root,
            )
            if call_params is None:
                return
        result = self.validator.validate_connection(
            conn_type, call_params, str(priority), target
        )
        if not result.ok:
            messagebox.showerror("錯誤", result.message)
            return
        self._snapshot()
        connection = Connection(source.id, target.id, conn_type, call_params, priority)
        ok, message = flowchart.add_connection(connection)
        if not ok:
            self.history.undo_stack.pop() if self.history.undo_stack else None
            messagebox.showerror("錯誤", message)
            return
        view.draw_connection(connection)
        self._mark_dirty()
        self._set_status(f"已建立 {conn_type} 連線")

    def _complete_connection(self, source: Element, target: Element,
                             view: CanvasView) -> None:
        self._conn_source = source
        flowchart = view.flowchart
        if flowchart is None:
            self._conn_source = None
            return
        fake_event = type("_Ev", (), {"x": target.x, "y": target.y})()
        self._finish_connection(fake_event, view)
        self._conn_source = None

    def _select_element(self, element: Optional[Element], view: CanvasView) -> None:
        self._selected_element = element
        view.set_selected(element.id if element is not None else None)

    def _on_context(self, event, view: CanvasView) -> None:
        menu = tk.Menu(self.root, tearoff=0)
        element = view.find_element_at(event.x, event.y, tolerance=28)
        connection = None
        if element is None and view.flowchart is not None:
            connection = view.find_connection_at(event.x, event.y, tolerance=16)
        if element is not None:
            if element.type != ElementType.START_END:
                menu.add_command(
                    label="編輯", command=lambda: self.edit_element(element, view))
            if element.type in (ElementType.FUNCTION, ElementType.CLASS):
                menu.add_command(
                    label="編輯子流程圖",
                    command=lambda: self.open_subflowchart(element))
            menu.add_command(
                label="刪除", command=lambda: self.delete_element(element, view))
        elif connection is not None:
            menu.add_command(
                label="編輯連線",
                command=lambda: self.edit_connection(connection, view))
            menu.add_command(
                label="刪除連線",
                command=lambda: self.delete_connection(connection, view))
        else:
            menu.add_command(label="新增元素", command=lambda: self.add_element(view))
        menu.tk_popup(event.x_root, event.y_root)

    # ---------- element operations ----------

    def add_element(self, view: CanvasView) -> None:
        flowchart = view.flowchart
        if flowchart is None:
            return
        elem_type = self._element_var.get()
        self._snapshot()
        count = len(flowchart.elements)
        element = Element(type=elem_type, x=140, y=80 + (count % 8) * 90)
        flowchart.add_element(element)
        view.draw_element(element)
        self._mark_dirty()
        if elem_type in SYNC_TYPES or elem_type == ElementType.EXTERNAL \
                or elem_type == ElementType.THREAD:
            self.edit_element(element, view)

    def edit_element(self, element: Element, view: CanvasView) -> None:
        self._snapshot()
        dialog = ElementEditDialog(
            self.root, element, self.symbols, self.validator, self.provider,
            self.snippets, self.registry,
            on_saved=lambda el: self._on_element_saved(el, view),
        )
        dialog.show()

    def _on_element_saved(self, element: Element, view: CanvasView) -> None:
        view.update_label(element)
        view.move_element_visual(element)
        if element.type == ElementType.FUNCTION and element.subflowchart is None:
            element.subflowchart = Flowchart()
        self._mark_dirty()
        self._set_status(f"已更新 {element.label_text()}")

    def delete_element(self, element: Element, view: CanvasView) -> None:
        if not messagebox.askyesno("確認", "確定要刪除此元素？"):
            return
        flowchart = view.flowchart
        if flowchart is None:
            return
        self._snapshot()
        for conn in list(flowchart.connections):
            if conn.source_id == element.id or conn.target_id == element.id:
                view.remove_connection_visual(conn)
                flowchart.remove_connection(conn)
        view.remove_element_visual(element.id)
        flowchart.remove_element(element.id)
        self._close_subview(element.id)
        self._mark_dirty()

    def edit_connection(self, connection: Connection, view: CanvasView) -> None:
        self._snapshot()
        dialog = ConnectionEditDialog(
            self.root, connection, view.flowchart, self.validator,
            on_saved=lambda conn: self._on_connection_saved(conn, view),
        )
        dialog.show()

    def _on_connection_saved(self, connection: Connection, view: CanvasView) -> None:
        view.remove_connection_visual(connection)
        view.draw_connection(connection)
        self._mark_dirty()

    def delete_connection(self, connection: Connection, view: CanvasView) -> None:
        if view.flowchart is None:
            return
        self._snapshot()
        view.remove_connection_visual(connection)
        view.flowchart.remove_connection(connection)
        self._mark_dirty()

    def _delete_selected(self) -> None:
        element = self._selected_element
        if element is None:
            return
        view = self._view_for_element(element.id) or self.view
        self.delete_element(element, view)

    def _view_for_element(self, element_id: str) -> Optional[CanvasView]:
        if self.view.flowchart and self.view.flowchart.element_by_id(element_id):
            return self.view
        for _eid, (toplevel, view) in list(self._sub_views.items()):
            if view.flowchart and view.flowchart.element_by_id(element_id):
                return view
        return None

    def open_subflowchart(self, element: Element) -> None:
        if element.subflowchart is None:
            self._snapshot()
            element.subflowchart = Flowchart()
        if element.id in self._sub_views:
            self._sub_views[element.id][0].lift()
            return
        toplevel = tk.Toplevel(self.root)
        name = element.function_name or element.class_name or element.type
        toplevel.title(f"函式/方法：{name}")
        place_geometry(toplevel, 720, 520)
        view = CanvasView(toplevel, is_subflowchart=True)
        view.attach(element.subflowchart)
        view.set_ports_visible(self._mode() == "連線埠")
        self._bind_canvas_events(view)
        self._sub_views[element.id] = (toplevel, view)
        toplevel.protocol(
            "WM_DELETE_WINDOW", lambda eid=element.id: self._close_subview(eid)
        )

    def _close_subview(self, element_id: str) -> None:
        entry = self._sub_views.pop(element_id, None)
        if entry:
            try:
                entry[0].destroy()
            except tk.TclError:
                pass

    # ---------- history ----------

    def _snapshot(self) -> None:
        self.history.push(self.project.to_dict())

    def undo(self) -> None:
        state = self.history.undo(self.project.to_dict())
        if state is None:
            self._set_status("無可復原的操作")
            return
        self._restore_project(Project.from_dict(state))
        self._set_status("已復原")

    def redo(self) -> None:
        state = self.history.redo()
        if state is None:
            self._set_status("無可重做的操作")
            return
        self._restore_project(Project.from_dict(state))
        self._set_status("已重做")

    def _restore_project(self, project: Project) -> None:
        self.project = project
        self.symbols.libraries = list(project.libraries)
        self.symbols.custom_modules = [tuple(m) for m in project.custom_modules]
        self.symbols.variables = dict(project.variables)
        self._rebuild_symbols()
        for eid in list(self._sub_views):
            self._close_subview(eid)
        self._cancel_pending_connection()
        self._selected_element = None
        self._pending_conn_source = None
        self.view.attach(project.flowchart)
        self.view.set_ports_visible(self._mode() == "連線埠")
        self._mark_dirty()

    # ---------- symbols / codegen / run ----------

    def _rebuild_symbols(self) -> None:
        self.symbols.libraries = list(self.project.libraries)
        self.symbols.custom_modules = [tuple(m) for m in self.project.custom_modules]
        self.symbols.variables = dict(self.project.variables)
        self.symbols.rebuild_from_flowchart(self.project.flowchart)

    def generate_code(self) -> None:
        self._rebuild_symbols()
        generator = CodeGenerator(
            self.project.flowchart, self.symbols, self.registry,
            libraries=self.project.libraries,
            custom_modules=self.project.custom_modules,
            variables=self.project.variables,
        )
        code = generator.generate()
        self.code_text.delete("1.0", tk.END)
        self.code_text.insert("1.0", code)
        self._set_status("已產生程式碼")

    def _speed_delays(self) -> tuple:
        speed = self._speed_var.get()
        if speed == "慢":
            return 900, 1500, 900
        if speed == "快":
            return 200, 450, 150
        return 450, 900, 400

    def _compile(self):
        self._rebuild_symbols()
        self.validator.refresh_policy(self.policy)
        return compile_plan(
            self.project.flowchart, self.symbols, self.validator, self.registry
        )

    def run_code(self) -> None:
        if self.player.running:
            self._set_status("執行中，先按 Esc 停止")
            return
        if not self.project.flowchart.elements:
            messagebox.showinfo("提示", "畫布是空的")
            return
        plan = self._compile()
        executor = FlowchartExecutor(plan, self.policy)
        warnings = executor.prepare(
            self.project.variables, self.project.libraries, self.project.custom_modules
        )
        self._executor = executor
        self._set_output("執行中…\n" + "".join(f"{w}\n" for w in warnings))
        step_delay, highlight, error_delay = self._speed_delays()
        self._highlight_ms = highlight
        self._error_ms = error_delay
        self.player.play(
            executor.run(),
            on_event=self._on_exec_event,
            step_delay_ms=step_delay,
            on_done=self._on_exec_done,
        )
        self._set_status("執行中…（Esc 停止）")

    def preview_code(self) -> None:
        if not self.project.flowchart.elements:
            messagebox.showinfo("提示", "畫布是空的")
            return
        plan = self._compile()
        executor = FlowchartExecutor(plan, self.policy)
        warnings = executor.prepare(
            self.project.variables, self.project.libraries, self.project.custom_modules
        )
        start = time.perf_counter()
        events = list(executor.run())
        elapsed_ms = (time.perf_counter() - start) * 1000
        errors = [e for e in events if e.kind in (EventKind.ERROR, EventKind.POLICY_VIOLATION)]
        lines = [f"（快速預覽：{elapsed_ms:.1f} ms，{len(events)} 個事件）"]
        lines.extend(f"[警告] {w}" for w in warnings)
        if errors:
            lines.append("")
            lines.append("執行錯誤：")
            lines.extend(f"  {e.message}" for e in errors)
        lines.append("")
        lines.append("輸出：")
        output = executor.output.getvalue()
        lines.append(output if output.strip() else "（無輸出）")
        if executor.thread_errors:
            lines.append("執行緒錯誤：")
            lines.extend(f"  {name}: {err}" for name, err in executor.thread_errors)
        self._set_output("\n".join(lines))
        self._set_status(f"預覽完成（{elapsed_ms:.1f} ms）")

    def stop_execution(self) -> None:
        if self._conn_source is not None or self._pending_conn_source is not None:
            self._cancel_pending_connection()
            for view in self._all_views():
                view.end_temp_line()
            self._conn_source = None
            self.view.set_selected(self._selected_element.id
                                   if self._selected_element else None)
            self._set_status("已取消連線")
            return
        if self.player.running:
            self.player.cancel()
            self._set_status("已停止執行")
            self._restore_all_fills()

    def _on_exec_event(self, event: ExecutionEvent) -> int:
        kind = event.kind
        highlight = getattr(self, "_highlight_ms", 450)
        error_delay = getattr(self, "_error_ms", 900)
        if kind == EventKind.ELEMENT_ENTER and event.element_id:
            view = self._view_for_element(event.element_id)
            if view:
                view.set_fill(event.element_id, "yellow")
                self.root.after(highlight,
                                lambda eid=event.element_id, v=view: v.restore_fill(eid))
            return highlight // 2
        if kind == EventKind.CONNECTION and event.source_id and event.target_id:
            view = self._view_for_element(event.source_id) or self.view
            flowchart = view.flowchart
            if flowchart:
                conn = flowchart.find_connection(event.source_id, event.target_id)
                if conn:
                    view.set_connection_highlight(conn)
                    self.root.after(highlight, lambda c=conn, v=view: v.restore_connection(c))
            return 0
        if kind == EventKind.OUTPUT and event.message:
            self._append_output(event.message + "\n")
            return 0
        if kind in (EventKind.ERROR, EventKind.POLICY_VIOLATION):
            if event.element_id:
                view = self._view_for_element(event.element_id)
                if view:
                    view.flash_error(event.element_id, error_delay, self.root)
            self._append_output(f"[錯誤] {event.message}\n")
            self._set_status(event.message)
            return error_delay
        if kind == EventKind.THREAD_STARTED:
            self._set_status(event.message)
            return 0
        if kind == EventKind.SYNC_WAIT:
            return highlight // 2
        if kind == EventKind.LOOP_LIMIT:
            self._append_output(f"[上限] {event.message}\n")
            return error_delay
        if kind == EventKind.WARNING:
            self._append_output(f"[警告] {event.message}\n")
            return 0
        return 0

    def _on_exec_done(self, error=None, **kwargs) -> None:
        if error is not None:
            self._append_output(f"[執行器錯誤] {error}\n")
        executor = self._executor
        if executor is not None:
            output = executor.output.getvalue()
            if output:
                self._append_output("\n--- 完整輸出 ---\n" + output)
            for name, err in executor.thread_errors:
                self._append_output(f"[執行緒錯誤] {name}: {err}\n")
        self._restore_all_fills()
        self._set_status("執行完成")

    def _restore_all_fills(self) -> None:
        self.view._fills.clear()
        self.view.canvas.update_idletasks()

    # ---------- project io ----------

    def new_project(self) -> None:
        if self.project.flowchart.elements:
            if not messagebox.askyesno("確認", "建立新專案將清除目前畫布，繼續？"):
                return
        self._snapshot()
        self._restore_project(Project())

    def save_flowchart(self) -> None:
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON 檔案", "*.json"), ("Pickle 檔案", "*.pickle")],
            title="儲存流程圖",
        )
        if not file_path:
            return
        if file_path.endswith(".pickle") or file_path.endswith(".pkl"):
            if not messagebox.askyesno("警告", "Pickle 檔案可能有安全風險，確定儲存？"):
                return
        try:
            self.project.libraries = list(self.symbols.libraries)
            self.project.custom_modules = [tuple(m) for m in self.symbols.custom_modules]
            self.project.variables = dict(self.project.variables)
            save_project(file_path, self.project)
            self._set_status(f"已儲存：{file_path}")
        except Exception as exc:
            messagebox.showerror("錯誤", f"儲存失敗：{exc}")

    def load_flowchart(self) -> None:
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON 檔案", "*.json"), ("Pickle 檔案", "*.pickle"),
                       ("所有檔案", "*.*")],
            title="載入流程圖",
        )
        if not file_path:
            return
        if file_path.endswith((".pickle", ".pkl")):
            if not messagebox.askyesno("警告", "載入 .pickle 可能有安全風險，是否繼續？"):
                return
        try:
            project = load_project(file_path)
        except Exception as exc:
            messagebox.showerror("錯誤", f"載入失敗：{exc}")
            return
        self._snapshot()
        self._restore_project(project)
        self._set_status(f"已載入：{file_path}")

    def clear_canvas(self) -> None:
        if not messagebox.askyesno("確認", "確定要清除畫布？"):
            return
        self._snapshot()
        self._restore_project(Project())
        self.code_text.delete("1.0", tk.END)
        self._set_output("")

    # ---------- diagnostics ----------

    def _mark_dirty(self) -> None:
        if self._diag_after is not None:
            try:
                self.root.after_cancel(self._diag_after)
            except Exception:
                pass
        self._diag_after = self.root.after(350, self._refresh_diagnostics)

    def _refresh_diagnostics(self) -> None:
        self._diag_after = None
        self._rebuild_symbols()
        self.validator.refresh_policy(self.policy)
        diagnostics = analyze(
            self.project.flowchart, self.symbols, self.validator, self.registry
        )
        self.diag_list.delete(0, tk.END)
        self._diag_items = diagnostics
        for text in format_diagnostics(diagnostics):
            self.diag_list.insert(tk.END, text)

    def _locate_diagnostic(self, event=None) -> None:
        selection = self.diag_list.curselection()
        if not selection:
            return
        diagnostic = self._diag_items[selection[0]]
        if diagnostic.element_id is None:
            return
        view = self._view_for_element(diagnostic.element_id) or self.view
        view.set_fill(diagnostic.element_id, "#FFB347")
        self.root.after(1200,
                        lambda: view.restore_fill(diagnostic.element_id))
        self._set_status(diagnostic.message)

    # ---------- tools ----------

    def _open_modules(self) -> None:
        ModulesDialog(self.root, self.symbols, on_changed=self._mark_dirty)

    def _open_module_browser(self) -> None:
        self._rebuild_symbols()
        ModuleBrowserDialog(self.root, self.symbols, on_create_external=self._create_external)

    def _create_external(self, module: str, info) -> None:
        self._snapshot()
        element = Element(
            type=ElementType.EXTERNAL,
            x=160, y=100 + (len(self.project.flowchart.elements) % 8) * 90,
            code=info.name,
            options={"module": module, "qualname": info.qualname},
        )
        self.project.flowchart.add_element(element)
        self.view.draw_element(element)
        self._mark_dirty()
        self._set_status(f"已建立外部函式元素：{module}.{info.qualname}")

    def _open_pypi(self) -> None:
        PyPIBrowserDialog(self.root, on_installed=self._mark_dirty)

    def _open_policy(self) -> None:
        def apply(new_policy: CodePolicy) -> None:
            self.policy = new_policy
            self.validator.refresh_policy(self.policy)
            self.provider.refresh_policy(self.policy)
            self.policy.save(self.policy_path)
            self._refresh_diagnostics()
            self._set_status("安全政策已更新")

        PolicyDialog(self.root, self.policy, on_applied=apply).open()

    def _open_shortcuts(self) -> None:
        def changed() -> None:
            self.shortcuts.unbind_all(self.root)
            self.shortcuts.bind_all(self.root, self._shortcut_handlers())
            self._set_status("快速鍵已更新")

        ShortcutDialog(self.root, self.shortcuts, on_changed=changed)

    def _trigger_autocomplete(self) -> None:
        self.code_text.event_generate("<Control-space>")

    # ---------- helpers ----------

    def _set_status(self, text: str) -> None:
        self.status.config(text=text)

    def _set_output(self, text: str) -> None:
        self.output_text.config(state="normal")
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert("1.0", text)
        self.output_text.see(tk.END)
        self.output_text.config(state="disabled")

    def _append_output(self, text: str) -> None:
        self.output_text.config(state="normal")
        self.output_text.insert(tk.END, text)
        self.output_text.see(tk.END)
        self.output_text.config(state="disabled")


def main() -> int:
    root = tk.Tk()
    try:
        FlowchartApp(root)
    except Exception as exc:
        messagebox.showerror("錯誤", f"初始化失敗：{exc}")
        return 1
    root.mainloop()
    return 0
