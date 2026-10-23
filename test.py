import tkinter as tk
from tkinter import ttk, messagebox, Text, PanedWindow, filedialog, simpledialog
import json
import pickle
import os
import sys
import io
import ast
import re
import time
import traceback
import uuid
import builtins
import importlib.util
import importlib
import math
from collections import deque
from functools import wraps

class FlowchartCanvas:
    def __init__(self, root, title, is_subflowchart=False, function_element=None):
        self.root = root
        self.is_subflowchart = is_subflowchart
        self.function_element = function_element
        self.elements = []
        self.connections = []
        self.canvas = tk.Canvas(root, bg="white", width=800, height=600)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        if not is_subflowchart:
            self.canvas.create_text(10, 10, text=title, anchor="nw", font=("Helvetica", 12, "bold"))
        self.temp_line = None
        self.start_x = None
        self.start_y = None
        self.selected_element = None

    def add_element(self, elem_type, x, y, app):
        element = {
            "id": str(uuid.uuid4()),
            "type": elem_type,
            "x": x,
            "y": y,
            "code": "",
            "condition": None,
            "loop_type": None,
            "function_name": None,
            "function_params": None,
            "is_lambda": False,
            "return_value": None,
            "class_name": None,
            "parent_class": None,
            "attributes": None,
            "methods": [],
            "decorator": None,
            "subflowchart": None
        }

        shape_id = None
        if elem_type == "Process":
            shape_id = self.canvas.create_rectangle(x - 50, y - 20, x + 50, y + 20, fill="lightblue")
        elif elem_type == "Decision":
            shape_id = self.canvas.create_polygon(x, y - 30, x + 50, y, x, y + 30, x - 50, y, fill="lightgreen")
        elif elem_type == "Loop":
            shape_id = self.canvas.create_oval(x - 40, y - 20, x + 40, y + 20, fill="lightyellow")
        elif elem_type == "Start/End":
            shape_id = self.canvas.create_oval(x - 40, y - 20, x + 40, y + 20, fill="pink")
        elif elem_type == "Input":
            shape_id = self.canvas.create_polygon(x - 50, y - 20, x + 50, y - 20, x + 60, y + 20, x - 60, y + 20, fill="lightgray")
        elif elem_type == "Output":
            shape_id = self.canvas.create_polygon(x - 50, y - 20, x + 50, y - 20, x + 40, y + 20, x - 40, y + 20, fill="lightcoral")
        elif elem_type == "Function":
            shape_id = self.canvas.create_rectangle(x - 50, y - 20, x + 50, y + 20, fill="purple")
        elif elem_type == "Class":
            shape_id = self.canvas.create_rectangle(x - 60, y - 30, x + 60, y + 30, fill="lightcyan")
        elif elem_type == "Comment":
            shape_id = self.canvas.create_text(x, y, text="// Comment", font=("Arial", 8), fill="gray")

        label_id = self.canvas.create_text(x, y, text=elem_type, font=("Arial", 8))
        element["shape_id"] = shape_id
        element["label_id"] = label_id
        self.elements.append(element)

        if elem_type in ["Function", "Class"]:
            element["subflowchart"] = FlowchartCanvas(self.root, f"函式/方法：{elem_type}", is_subflowchart=True, function_element=element)
            app.bind_canvas_events(element["subflowchart"])

    def highlight_element(self, element, duration=0.5):
        original_fill = self.canvas.itemcget(element["shape_id"], "fill")
        self.canvas.itemconfig(element["shape_id"], fill="yellow")
        self.canvas.update()
        time.sleep(duration)
        self.canvas.itemconfig(element["shape_id"], fill=original_fill)
        self.canvas.update()

    def highlight_connection(self, connection, duration=0.5):
        _, _, line_id, _, _, _, _ = connection
        original_fill = self.canvas.itemcget(line_id, "fill")
        self.canvas.itemconfig(line_id, fill="yellow")
        self.canvas.update()
        time.sleep(duration)
        self.canvas.itemconfig(line_id, fill=original_fill)
        self.canvas.update()

    def highlight_error(self, element, duration=1.0):
        original_fill = self.canvas.itemcget(element["shape_id"], "fill")
        self.canvas.itemconfig(element["shape_id"], fill="red")
        self.canvas.update()
        time.sleep(duration)
        self.canvas.itemconfig(element["shape_id"], fill=original_fill)
        self.canvas.update()

    def start_connection(self, event, canvas):
        # Clear any existing temporary line
        if self.temp_line:
            self.canvas.delete(self.temp_line)
            self.temp_line = None
        self.start_x, self.start_y, self.selected_element = None, None, None
        for element in canvas.elements:
            if abs(event.x - element["x"]) < 20 and abs(event.y - element["y"]) < 20:
                self.start_x, self.start_y, self.selected_element = (element["x"], element["y"], element)
                break

    def draw_connection(self, event, canvas):
        if self.start_x is not None and self.start_y is not None:
            if self.temp_line:
                self.canvas.delete(self.temp_line)
            color = "#5E81AC" if canvas.connection_var.get() == "Body" else "#BF616A" if canvas.connection_var.get() == "Exit" else "#A3BE8C"
            self.temp_line = self.canvas.create_line(self.start_x, self.start_y, event.x, event.y, arrow=tk.LAST, fill=color)

    def end_connection(self, event, canvas):
        if self.start_x is None or self.start_y is None or not self.selected_element:
            if self.temp_line:
                self.canvas.delete(self.temp_line)
                self.temp_line = None
            return

        end_element = None
        for element in canvas.elements:
            if abs(event.x - element["x"]) < 20 and abs(event.y - element["y"]) < 20 and element != self.selected_element:
                end_element = element
                break

        if end_element:
            # Prevent self-connection
            if self.selected_element == end_element:
                messagebox.showerror("錯誤", "不能連接到相同元素")
                self._reset_connection_state(canvas)
                return

            # Check for duplicate connection
            for conn in canvas.connections:
                if (conn[0] == self.selected_element and conn[1] == end_element and conn[4] == canvas.connection_var.get()):
                    messagebox.showerror("錯誤", f"已經存在相同的 {canvas.connection_var.get()} 連線")
                    self._reset_connection_state(canvas)
                    return

            conn_type = canvas.connection_var.get()
            # Validate connection type
            if conn_type == "Call" and end_element["type"] != "Function":
                messagebox.showerror("錯誤", "Call 連線必須指向函式元素")
            elif conn_type in ["Body", "Exit"] and end_element["type"] == "Function":
                messagebox.showerror("錯誤", "Body/Exit 連線不能指向函式元素")
            else:
                color = "#5E81AC" if conn_type == "Body" else "#BF616A" if conn_type == "Exit" else "#A3BE8C"
                call_params = ""
                priority = 0
                if conn_type == "Body":
                    priority_str = simpledialog.askstring("輸入", "輸入連線優先級（整數，較低值優先）：", initialvalue="0")
                    try:
                        priority = int(priority_str) if priority_str else 0
                        if priority < 0:
                            raise ValueError("優先級不能為負數")
                    except (ValueError, TypeError):
                        messagebox.showerror("錯誤", "優先級必須為非負整數")
                        self._reset_connection_state(canvas)
                        return
                if conn_type == "Call":
                    call_params = simpledialog.askstring("輸入", f"輸入 {end_element['function_name']} 的呼叫參數（例如：x, 5）：", initialvalue="")
                    if call_params is None:
                        self._reset_connection_state(canvas)
                        return
                    valid, error_msg = canvas.validate_function_call(end_element["function_name"], call_params)
                    if not valid:
                        messagebox.showerror("錯誤", error_msg)
                        self._reset_connection_state(canvas)
                        return

                canvas.save_state(canvas)
                try:
                    line_id = self.canvas.create_line(self.start_x, self.start_y, end_element["x"], end_element["y"], arrow=tk.LAST, fill=color, tags="connection")
                    label_id = self.canvas.create_text((self.start_x + end_element["x"]) / 2, (self.start_y + end_element["y"]) / 2, text=f"{conn_type} ({priority})" if conn_type == "Body" else conn_type, font=("Arial", 8))
                    canvas.connections.append((self.selected_element, end_element, line_id, label_id, conn_type, call_params, priority))
                except Exception as e:
                    messagebox.showerror("錯誤", f"連線失敗：{str(e)}")

        self._reset_connection_state(canvas)

    def _reset_connection_state(self, canvas):
        if self.temp_line:
            self.canvas.delete(self.temp_line)
            self.temp_line = None
        self.start_x, self.start_y, self.selected_element = None, None, None

    def edit_connection(self, connection, canvas):
        try:
            edit_dialog = tk.Toplevel(canvas.root)
            edit_dialog.title("編輯連線")
            edit_dialog.geometry("300x200")
        except tk.TclError as e:
            messagebox.showerror("錯誤", f"無法創建編輯視窗：{str(e)}")
            return

        start_elem, end_elem, line_id, label_id, conn_type, call_params, priority = connection

        ttk.Label(edit_dialog, text="連線類型：").pack(pady=5)
        conn_type_var = tk.StringVar(value=conn_type)
        ttk.OptionMenu(edit_dialog, conn_type_var, conn_type, "Body", "Exit", "Call").pack(pady=5)

        ttk.Label(edit_dialog, text="呼叫參數（僅限 Call）：").pack(pady=5)
        params_entry = ttk.Entry(edit_dialog)
        params_entry.insert(0, call_params or "")
        params_entry.pack(pady=5)

        ttk.Label(edit_dialog, text="優先級（整數）：").pack(pady=5)
        priority_entry = ttk.Entry(edit_dialog)
        priority_entry.insert(0, str(priority))
        priority_entry.pack(pady=5)

        def save_changes():
            try:
                new_type = conn_type_var.get()
                new_params = params_entry.get().strip()
                new_priority = priority_entry.get().strip()

                valid, error_msg = canvas.validate_connection_params(new_type, new_params, new_priority, end_elem)
                if not valid:
                    messagebox.showerror("錯誤", error_msg)
                    return

                # Check for duplicate connection with new type
                for conn in canvas.connections:
                    if (conn != connection and conn[0] == start_elem and conn[1] == end_elem and conn[4] == new_type):
                        messagebox.showerror("錯誤", f"已經存在相同的 {new_type} 連線")
                        return

                canvas.save_state(canvas)
                canvas.canvas.delete(line_id)
                canvas.canvas.delete(label_id)
                color = "#5E81AC" if new_type == "Body" else "#BF616A" if new_type == "Exit" else "#A3BE8C"
                new_line_id = canvas.canvas.create_line(
                    start_elem["x"], start_elem["y"], end_elem["x"], end_elem["y"],
                    arrow=tk.LAST, fill=color, tags="connection"
                )
                new_label_id = canvas.canvas.create_text(
                    (start_elem["x"] + end_elem["x"]) / 2, (start_elem["y"] + end_elem["y"]) / 2,
                    text=f"{new_type} ({new_priority})" if new_type == "Body" else new_type,
                    font=("Arial", 8)
                )

                canvas.connections.remove(connection)
                canvas.connections.append((
                    start_elem, end_elem, new_line_id, new_label_id,
                    new_type, new_params, int(new_priority)
                ))

                edit_dialog.destroy()
            except Exception as e:
                messagebox.showerror("錯誤", f"儲存連線失敗：{str(e)}")

        ttk.Button(edit_dialog, text="儲存", command=save_changes).pack(pady=5)
        ttk.Button(edit_dialog, text="取消", command=edit_dialog.destroy).pack(pady=5)
        edit_dialog.protocol("WM_DELETE_WINDOW", edit_dialog.destroy)

    def delete_connection(self, connection, canvas):
        try:
            canvas.save_state(canvas)
            start_elem, end_elem, line_id, label_id, _, _, _ = connection
            canvas.canvas.delete(line_id)
            canvas.canvas.delete(label_id)
            canvas.connections.remove(connection)
        except Exception as e:
            messagebox.showerror("錯誤", f"刪除連線失敗：{str(e)}")

    def update_connections(self, canvas):
        for conn in canvas.connections[:]:
            try:
                start, end, line_id, label_id, conn_type, call_params, priority = conn
                if start not in canvas.elements or end not in canvas.elements:
                    canvas.canvas.delete(line_id)
                    canvas.canvas.delete(label_id)
                    canvas.connections.remove(conn)
                    continue
                canvas.canvas.coords(line_id, start["x"], start["y"], end["x"], end["y"])
                canvas.canvas.coords(label_id, (start["x"] + end["x"]) / 2, (start["y"] + end["y"]) / 2)
            except Exception as e:
                messagebox.showerror("警告", f"更新連線失敗：{str(e)}")
                canvas.canvas.delete(conn[2])
                canvas.canvas.delete(conn[3])
                canvas.connections.remove(conn)

    def validate_function_call(self, function_name, call_params):
        if not function_name:
            return False, "函式名稱未定義"
        try:
            ast.parse(f"{function_name}({call_params})")
            param_count = len([p for p in call_params.split(",") if p.strip()])
            expected_params = self.function_signatures.get(function_name, 0)
            if param_count != expected_params:
                return False, f"參數數量不匹配：預期 {expected_params} 個，實際 {param_count} 個"
            return True, ""
        except SyntaxError as e:
            return False, f"呼叫參數語法錯誤：{str(e)}"

class FlowchartToCodeGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("流程圖轉程式碼工具")
        self.root.geometry("1200x800")
        self.element_var = tk.StringVar(value="Process")
        self.connection_var = tk.StringVar(value="Body")
        self.variables = {}
        self.libraries = []
        self.custom_modules = []
        self.defined_variables = set()
        self.function_signatures = {}
        self.class_signatures = {}
        self.imported_names = {}
        self.execution_globals = {}
        self.undo_stack = deque(maxlen=50)
        self.redo_stack = deque(maxlen=50)
        self.main_canvas = None
        self.syntax_sugar_templates = {
            "列表推導式": "[x*2 for x in iterable]",
            "字典推導式": "{k: v**2 for k, v in dict.items()}",
            "裝飾器": "@decorator\ndef func(): pass",
            "上下文管理器": "with open('file.txt') as f:\n    data = f.read()"
        }
        self.create_widgets()

    def validate_connection_params(self, conn_type, call_params, priority, end_elem):
        try:
            priority = int(priority)
            if priority < 0:
                return False, "優先級必須為非負整數"
        except ValueError:
            return False, "優先級必須為整數"

        if conn_type == "Call":
            if not call_params:
                return False, "Call 連線必須提供呼叫參數"
            if end_elem["type"] == "Function":
                valid, error_msg = self.main_canvas.validate_function_call(end_elem["function_name"], call_params)
                if not valid:
                    return False, error_msg
            elif end_elem["type"] == "Class":
                if "." not in call_params:
                    return False, "類別呼叫參數應為 obj.method(args) 格式"
                try:
                    ast.parse(f"{call_params}")
                except SyntaxError as e:
                    return False, f"呼叫參數語法錯誤：{str(e)}"
        elif call_params and conn_type != "Call":
            return False, f"{conn_type} 連線不應包含呼叫參數"

        return True, ""

    # Placeholder for other methods (not modifieddef create_widgets(self):
        paned_window = PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.Frame(paned_window, width=200)
        paned_window.add(left_frame, minsize=200)

        canvas_frame = ttk.Frame(paned_window)
        paned_window.add(canvas_frame, minsize=600)

        right_frame = ttk.Frame(paned_window, width=300)
        paned_window.add(right_frame, minsize=300)

        ttk.Label(left_frame, text="元素類型：").pack(pady=5)
        element_types = ["Process", "Decision", "Loop", "Start/End", "Input", "Output", "Function", "Class", "Comment"]
        ttk.OptionMenu(left_frame, self.element_var, "Process", *element_types).pack(pady=5)
        ttk.Button(left_frame, text="新增元素", command=lambda: self.add_element(self.main_canvas)).pack(pady=5)

        ttk.Label(left_frame, text="連線類型：").pack(pady=5)
        ttk.OptionMenu(left_frame, self.connection_var, "Body", "Body", "Exit", "Call").pack(pady=5)

        ttk.Button(left_frame, text="匯入模組", command=self.import_library).pack(pady=5)
        ttk.Button(left_frame, text="變數管理", command=self.manage_variables).pack(pady=5)
        ttk.Button(left_frame, text="儲存流程圖", command=self.save_flowchart).pack(pady=5)
        ttk.Button(left_frame, text="載入流程圖", command=self.load_flowchart).pack(pady=5)
        ttk.Button(left_frame, text="清除畫布", command=self.clear_canvas).pack(pady=5)
        ttk.Button(left_frame, text="使用說明", command=self.show_help).pack(pady=5)

        ttk.Button(left_frame, text="上一步", command=self.undo).pack(pady=5)
        ttk.Button(left_frame, text="下一步", command=self.redo).pack(pady=5)

        self.main_canvas = FlowchartCanvas(canvas_frame, "主流程圖")
        self.bind_canvas_events(self.main_canvas)

        code_frame = ttk.Frame(right_frame)
        code_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        ttk.Label(code_frame, text="程式碼：").pack()
        self.code_text = Text(code_frame, height=15, width=40)
        self.code_text.pack(fill=tk.BOTH, expand=True)
        ttk.Button(code_frame, text="產生程式碼", command=self.generate_code).pack(pady=5)
        ttk.Button(code_frame, text="執行程式碼", command=self.run_code).pack(pady=5)

        output_frame = ttk.Frame(right_frame)
        output_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        ttk.Label(output_frame, text="輸出：").pack()
        self.output_text = Text(output_frame, height=10, width=40, state="disabled")
        self.output_text.pack(fill=tk.BOTH, expand=True)

        self.animation_speed_var = tk.StringVar(value="正常")
        ttk.Label(right_frame, text="動畫速度：").pack(pady=5)
        ttk.OptionMenu(right_frame, self.animation_speed_var, "正常", "慢", "正常", "快").pack(pady=5)

    def get_animation_duration(self):
        speed = self.animation_speed_var.get()
        if speed == "慢":
            return 1.0, 2.0
        elif speed == "快":
            return 0.2, 0.5
        else:
            return 0.5, 1.0

    def bind_canvas_events(self, canvas):
        try:
            canvas.canvas.bind("<Button-1>", lambda event: self.handle_canvas_click(event, canvas))
            canvas.canvas.bind("<B1-Motion>", lambda event: self.handle_canvas_drag(event, canvas))
            canvas.canvas.bind("<ButtonRelease-1>", lambda event: self.end_connection(event, canvas))
            canvas.canvas.bind("<Button-2>", lambda event: self.show_context_menu(event, canvas))
            canvas.canvas.bind("<Button-3>", lambda event: self.show_context_menu(event, canvas))
        except Exception as e:
            messagebox.showerror("錯誤", f"綁定事件失敗：{str(e)}")

    def handle_canvas_click(self, event, canvas):
        canvas.start_x, canvas.start_y = event.x, event.y
        canvas.selected_element = None
        for elem in canvas.elements:
            if abs(elem["x"] - event.x) < 20 and abs(elem["y"] - event.y) < 20:
                canvas.selected_element = elem
                break
        self.start_connection(event, canvas)

    def handle_canvas_drag(self, event, canvas):
        if canvas.selected_element:
            canvas.selected_element["x"] = event.x
            canvas.selected_element["y"] = event.y
            self.update_element_coords(canvas.selected_element, canvas)
            self.update_connections(canvas)
            label_text = self.get_label_text(canvas.selected_element)
            canvas.canvas.itemconfig(canvas.selected_element["label_id"], text=label_text[:20] + "..." if len(label_text) > 20 else label_text)
        elif hasattr(canvas, "start_x"):
            end_elem = None
            for elem in canvas.elements:
                if abs(elem["x"] - event.x) < 20 and abs(elem["y"] - event.y) < 20:
                    end_elem = elem
                    break
            if end_elem and canvas.selected_element and end_elem != canvas.selected_element:
                color = "#5E81AC" if self.connection_var.get() == "Body" else "#BF616A" if self.connection_var.get() == "Exit" else "#A3BE8C"
                line_id = canvas.canvas.create_line(canvas.start_x, canvas.start_y, end_elem["x"], end_elem["y"], arrow=tk.LAST, fill=color, tags="connection")
                label_id = canvas.canvas.create_text((canvas.start_x + end_elem["x"]) / 2, (canvas.start_y + end_elem["y"]) / 2, text=self.connection_var.get(), font=("Arial", 8))
                canvas.connections.append((canvas.selected_element, end_elem, line_id, label_id, self.connection_var.get(), "", 1))
                canvas.start_x, canvas.start_y = None, None
                canvas.selected_element = None
            self.draw_connection(event, canvas)
         
    def update_element_coords(self, element, canvas):
        if element["shape_id"]:
            if element["type"] == "Process":
                self.main_canvas.canvas.coords(element["shape_id"], element["x"] - 50, element["y"] - 20, element["x"] + 50, element["y"] + 20)
            elif element["type"] == "Decision":
                self.main_canvas.canvas.coords(element["shape_id"], element["x"], element["y"] - 30, element["x"] + 50, element["y"], element["x"], element["y"] + 30, element["x"] - 50, element["y"])
            elif element["type"] == "Loop":
                self.main_canvas.canvas.coords(element["shape_id"], element["x"] - 40, element["y"] - 20, element["x"] + 40, element["y"] + 20)
            elif element["type"] == "Start/End":
                self.main_canvas.canvas.coords(element["shape_id"], element["x"] - 40, element["y"] - 20, element["x"] + 40, element["y"] + 20)
            elif element["type"] == "Input":
                self.main_canvas.canvas.coords(element["shape_id"], element["x"] - 50, element["y"] - 20, element["x"] + 50, element["y"] - 20, element["x"] + 40, element["y"] + 20, element["x"] - 40, element["y"] + 20)
            elif element["type"] == "Output":
                self.main_canvas.canvas.coords(element["shape_id"], element["x"] - 50, element["y"] - 20, element["x"] + 50, element["y"] - 20, element["x"] + 60, element["y"] + 20, element["x"] - 60, element["y"] + 20)
            elif element["type"] == "Function":
                self.main_canvas.canvas.coords(element["shape_id"], element["x"] - 50, element["y"] - 20, element["x"] + 50, element["y"] + 20)
            elif element["type"] == "Class":
                self.main_canvas.canvas.coords(element["shape_id"], element["x"] - 60, element["y"] - 30, element["x"] + 60, element["y"] + 30)
            self.main_canvas.canvas.coords(element["label_id"], element["x"], element["y"])

        for conn in canvas.connections:
            start, end, line_id, label_id, conn_type, call_params, priority = conn
            if (start == element or end == element) and not start and not end:
                self.main_canvas.canvas.coords(line_id, start["x"], start["y"], end["x"], end["y"])
                self.main_canvas.canvas.coords(label_id, (start["x"] + end["x"]) / 2, (start["y"] + end["y"]) / 2)

    def get_label_text(self, element):
        if element["type"] in ["Process", "Input", "Output"]:
            return element["code"] or element["type"]
        elif element["type"] == "Decision":
            return element["condition"] or "Decision"
        elif element["type"] == "Loop":
            return element["condition"] or "Loop"
        elif element["type"] == "Function":
            return element["function_name"] or "Function"
        elif element["type"] == "Class":
            return element["class_name"] or "Class"
        elif element["type"] == "Comment":
            return element["code"] or "Comment"
        return element["type"]

    def show_context_menu(self, event, canvas):
        try:
            context_menu = tk.Menu(self.root, tearoff=0)
            element = None
            connection = None

            # 檢查是否點擊元素
            for elem in canvas.elements:
                x, y = elem["x"], elem["y"]
                if abs(x - event.x) < 20 and abs(y - event.y) < 20:
                    element = elem
                    break

            # 若未點擊元素，檢查是否點擊連線
            if not element:
                for conn in canvas.connections:
                    start_elem, end_elem, line_id, _, _, _, _ = conn
                    x1, y1 = start_elem["x"], start_elem["y"]
                    x2, y2 = end_elem["x"], end_elem["y"]
                    px, py = event.x, event.y
                    length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
                    if length == 0:
                        continue
                    r = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / length ** 2
                    if r < 0:
                        dist = ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
                    elif r > 1:
                        dist = ((px - x2) ** 2 + (py - y2) ** 2) ** 0.5
                    else:
                        dist = abs((y2 - y1) * px - (x2 - x1) * py + x2 * y1 - y2 * x1) / length
                    dist_x, dist_y = abs(event.x - (x1 + x2) / 2), abs(event.y - (y1 + y2) / 2)
                    if dist_x < 30 and dist_y < 30:
                        connection = conn
                        break
                    #if dist < 30:
                    #    connection = conn
                    #    break

            # 根據點擊對象顯示選單
            if element:
                if element["type"] not in ["Start/End"]:
                    context_menu.add_command(label="編輯", command=lambda: self.edit_element(element, canvas))
                context_menu.add_command(label="刪除", command=lambda: self.delete_element(element, canvas))
            elif connection:
                context_menu.add_command(label="編輯連線", command=lambda: self.edit_connection(connection, canvas))
                context_menu.add_command(label="刪除連線", command=lambda: self.delete_connection(connection, canvas))
            else:
                context_menu.add_command(label="新增元素", command=lambda: self.add_element(canvas))
            context_menu.post(event.x_root, event.y_root)
        except Exception as e:
            messagebox.showerror("錯誤", f"顯示上下文選單失敗：{str(e)}")

    def edit_element(self, element, canvas):
        try:
            edit_dialog = tk.Toplevel(self.root)
            edit_dialog.title(f"編輯 {element['type']} 元素")
            edit_dialog.geometry("400x500")
        except tk.TclError as e:
            messagebox.showerror("錯誤", f"無法創建編輯視窗：{str(e)}")
            return

        ttk.Label(edit_dialog, text="程式碼/條件：").pack(pady=5)
        code_text = tk.Text(edit_dialog, height=5, width=40)
        code_text.pack(pady=5)

        if element["type"] in ["Process", "Input", "Output"]:
            code_text.insert("1.0", element["code"] or "")
        elif element["type"] == "Decision":
            code_text.insert("1.0", element["condition"] or "")
        elif element["type"] == "Loop":
            code_text.insert("1.0", element["condition"] or "")
            loop_type_var = tk.StringVar(value=element["loop_type"] or "for")
            ttk.Radiobutton(edit_dialog, text="For 迴圈", value="for", variable=loop_type_var).pack(pady=5)
            ttk.Radiobutton(edit_dialog, text="While 迴圈", value="while", variable=loop_type_var).pack(pady=5)
        elif element["type"] == "Function":
            code_text.insert("1.0", element["function_name"] or "")
            param_text = ttk.Entry(edit_dialog)
            param_text.insert(0, element["function_params"] or "")
            ttk.Label(edit_dialog, text="參數：").pack(pady=5)
            param_text.pack(pady=5)
            lambda_var = tk.BooleanVar(value=element.get("is_lambda", False))
            ttk.Checkbutton(edit_dialog, text="Lambda 函式", variable=lambda_var).pack(pady=5)
        elif element["type"] == "Class":
            code_text.insert("1.0", element["class_name"] or "")
            parent_text = ttk.Entry(edit_dialog)
            parent_text.insert(0, element["parent_class"] or "")
            ttk.Label(edit_dialog, text="父類別：").pack(pady=5)
            parent_text.pack(pady=5)
            ttk.Label(edit_dialog, text="屬性（JSON）：").pack(pady=5)
            attr_text = tk.Text(edit_dialog, height=3, width=40)
            attr_text.insert("1.0", json.dumps(element["attributes"] or {}, indent=2))
            attr_text.pack(pady=5)

        ttk.Label(edit_dialog, text="語法糖模板：").pack(pady=5)
        template_var = tk.StringVar(value="無")
        template_menu = ttk.OptionMenu(edit_dialog, template_var, "無", *self.syntax_sugar_templates.keys())
        template_menu.pack(pady=5)

        def apply_template():
            try:
                if template_var.get() != "無":
                    template_code = self.syntax_sugar_templates[template_var.get()]
                    valid, error_msg = self.validate_code(template_code, is_condition=False, element=element, canvas=canvas)
                    if not valid:
                        messagebox.showwarning("警告", f"模板無效：{error_msg}")
                        return
                    code_text.delete("1.0", tk.END)
                    code_text.insert("1.0", template_code)
            except Exception as e:
                messagebox.showerror("錯誤", f"套用模板失敗：{str(e)}")

        ttk.Button(edit_dialog, text="套用模板", command=apply_template).pack(pady=5)

        def save_changes():
            try:
                code = code_text.get("1.0", tk.END).strip()
                if element["type"] in ["Process", "Input", "Output"]:
                    valid, error_msg = self.validate_code(code, is_condition=False, element=element, canvas=canvas)
                    if not valid:
                        messagebox.showerror("錯誤", error_msg)
                        return
                    element["code"] = code
                    if element["type"] == "Process":
                        self.update_defined_variables(code)
                elif element["type"] == "Decision":
                    valid, error_msg = self.validate_code(code, is_condition=True, element=element, canvas=canvas)
                    if not valid:
                        messagebox.showerror("錯誤", error_msg)
                        return
                    element["condition"] = code
                elif element["type"] == "Loop":
                    valid, error_msg = self.validate_code(code, is_condition=True, element=element, canvas=canvas)
                    if not valid:
                        messagebox.showerror("錯誤", error_msg)
                        return
                    element["condition"] = code
                    element["loop_type"] = loop_type_var.get()
                elif element["type"] == "Function":
                    if not code or not re.match(r'^[a-zA-Z_]\w*$', code):
                        messagebox.showerror("錯誤", "函式名稱必須為有效 Python 標識符")
                        return
                    element["function_name"] = code
                    element["function_params"] = param_text.get().strip()
                    element["is_lambda"] = lambda_var.get()
                    if element["function_name"]:
                        param_count = len([p for p in element["function_params"].split(",") if p.strip()])
                        self.function_signatures[element["function_name"]] = param_count
                elif element["type"] == "Class":
                    if not code or not re.match(r'^[a-zA-Z_]\w*$', code):
                        messagebox.showerror("錯誤", "類別名稱必須為有效 Python 標識符")
                        return
                    element["class_name"] = code
                    element["parent_class"] = parent_text.get().strip()
                    try:
                        attr_data = attr_text.get("1.0", tk.END).strip()
                        element["attributes"] = json.loads(attr_data) if attr_data else {}
                    except json.JSONDecodeError as e:
                        messagebox.showerror("錯誤", f"屬性必須為有效的 JSON 格式：{str(e)}")
                        return
                    self.class_signatures[element["class_name"]] = {
                        "attributes": element["attributes"],
                        "methods": {m["name"]: len([p for p in m["params"].split(",") if p.strip()]) for m in element.get("methods", [])}
                    }

                self.update_element_coords(element, canvas)
                self.update_connections(canvas)
                label_text = self.get_label_text(element)
                canvas.canvas.itemconfig(element["label_id"], text=label_text[:20] + "..." if len(label_text) > 20 else label_text)
                edit_dialog.destroy()
            except Exception as e:
                messagebox.showerror("錯誤", f"儲存失敗：{str(e)}")

        ttk.Button(edit_dialog, text="儲存", command=save_changes).pack(pady=5)
        ttk.Button(edit_dialog, text="取消", command=edit_dialog.destroy).pack(pady=5)

        edit_dialog.protocol("WM_DELETE_WINDOW", edit_dialog.destroy)

    def add_element(self, canvas):
        elem_type = self.element_var.get()
        x, y = 400, 50 + len(canvas.elements) * 100
        canvas.add_element(elem_type, 100, 100, self)
        self.save_state(canvas)

    def delete_element(self, element, canvas):
        if messagebox.askyesno("確認", "確定要刪除此元素？"):
            self.save_state(canvas)
            canvas.canvas.delete(element["shape_id"])
            canvas.canvas.delete(element["label_id"])
            canvas.elements.remove(element)
            connections_to_remove = [conn for conn in canvas.connections if conn[0] == element or conn[1] == element]
            for conn in connections_to_remove:
                canvas.canvas.delete(conn[2])
                canvas.canvas.delete(conn[3])
                canvas.connections.remove(conn)

    
