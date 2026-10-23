import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, Text, PanedWindow, filedialog
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
from collections import deque
from functools import wraps

class FlowchartCanvas:
    def __init__(self, parent, title, is_subflowchart=False, function_element=None):
        self.window = tk.Toplevel(parent) if is_subflowchart else parent
        self.window.title = title
        self.is_subflowchart = is_subflowchart
        self.function_element = function_element
        self.canvas = tk.Canvas(self.window, width=800, height=600, bg="white", bd=2, relief="sunken", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.elements = []
        self.connections = []
        self.start_point = None
        self.temp_line = None
        self.selected_element = None

    def add_element(self, element_type, x, y, main_gui):
        element_id = str(uuid.uuid4())
        if element_type == "Start/End":
            canvas_id = self.canvas.create_oval(x-40, y-20, x+40, y+20, fill="#A3BE8C", tags="element")
            label = "Start" if not self.elements else "End"
        elif element_type == "Process":
            canvas_id = self.canvas.create_rectangle(x-50, y-20, x+50, y+20, fill="#88C0D0", tags="element")
            label = "Process"
        elif element_type == "Decision":
            canvas_id = self.canvas.create_polygon(x, y-30, x+50, y, x, y+30, x-50, y, fill="#EBCB8B", tags="element")
            label = "Decision"
        elif element_type == "Input":
            canvas_id = self.canvas.create_polygon(x-50, y-20, x+50, y-20, x+40, y+20, x-60, y+20, fill="#D08770", tags="element")
            label = "Input"
        elif element_type == "Output":
            canvas_id = self.canvas.create_polygon(x-50, y-20, x+50, y-20, x+60, y+20, x-40, y+20, fill="#BF616A", tags="element")
            label = "Output"
        elif element_type == "Loop":
            canvas_id = self.canvas.create_polygon(x-40, y-20, x+40, y-20, x+50, y, x+40, y+20, x-40, y+20, x-50, y, fill="#B48EAD", tags="element")
            label = "Loop"
        elif element_type == "Comment":
            canvas_id = self.canvas.create_rectangle(x-50, y-20, x+50, y+20, fill="#D8DEE9", tags="element")
            label = "Comment"
        elif element_type == "Function":
            canvas_id = self.canvas.create_rectangle(x-50, y-20, x+50, y+20, fill="#8FBCBB", tags="element", outline="#5E81AC", width=3, dash=(4, 4))
            label = "Function"
        elif element_type == "Class":
            canvas_id = self.canvas.create_rectangle(x-60, y-30, x+60, y+30, fill="#9B59B6", tags="element", outline="#8E44AD", width=2, dash=(2, 2))
            label = "Class"

        label_id = self.canvas.create_text(x, y, text=label, tags="label", font=("Arial", 10))
        element = {
            "id": element_id,
            "canvas_id": canvas_id,
            "label_id": label_id,
            "type": element_type,
            "x": x,
            "y": y,
            "code": "",
            "condition": "" if element_type in ["Decision", "Loop"] else None,
            "loop_type": "for" if element_type == "Loop" else None,
            "function_name": "" if element_type == "Function" else None,
            "function_params": "" if element_type == "Function" else None,
            "is_lambda": False if element_type == "Function" else None,
            "subflowchart": None if element_type in ["Function", "Class"] else None,
            "return_value": "" if element_type == "Start/End" and self.elements else None,
            "class_name": "" if element_type == "Class" else None,
            "parent_class": "" if element_type == "Class" else None,
            "attributes": {} if element_type == "Class" else None,
            "methods": [] if element_type == "Class" else None,
            "decorator": "" if element_type == "Function" else None
        }
        self.elements.append(element)
        self.canvas.tag_bind(canvas_id, "<B1-Motion>", lambda event, eid=element_id: main_gui.move_element(self, event, eid))
        self.canvas.tag_bind(label_id, "<B1-Motion>", lambda event, eid=element_id: main_gui.move_element(self, event, eid))
        #self.canvas.tag_bind(canvas_id, "<Button-3>", lambda event: main_gui.edit_element(self, event)) # MacOS
        #self.canvas.tag_bind(label_id, "<Button-2>", lambda event: main_gui.edit_element(self, event))
        #self.canvas.tag_bind(canvas_id, "<Button-2>", lambda event: main_gui.edit_element(self, event)) # Windows/Linux
        #self.canvas.tag_bind(label_id, "<Button-3>", lambda event: main_gui.edit_element(self, event))

    def highlight_element(self, element, color="#BF616A", duration=0.5):
        self.canvas.itemconfig(element["canvas_id"], outline=color, width=3)
        self.canvas.update()
        time.sleep(duration)
        self.canvas.itemconfig(element["canvas_id"], outline="black" if element["type"] != "Class" else "#8E44AD", width=1 if element["type"] != "Class" else 2)
        self.canvas.update()

    def highlight_connection(self, conn, color="#BF616A", duration=0.5):
        self.canvas.itemconfig(conn[2], fill=color, width=3)
        self.canvas.update()
        time.sleep(duration)
        original_color = "#5E81AC" if conn[4] == "Body" else "#BF616A" if conn[4] == "Exit" else "#A3BE8C"
        self.canvas.itemconfig(conn[2], fill=original_color, width=1)
        self.canvas.update()

    def highlight_error(self, item, is_connection=False, duration=1.0):
        if is_connection:
            self.canvas.itemconfig(item[2], fill="#B48EAD", width=5)
        else:
            self.canvas.itemconfig(item["canvas_id"], outline="#B48EAD", width=5)
        self.canvas.update()
        time.sleep(duration)
        if is_connection:
            original_color = "#5E81AC" if item[4] == "Body" else "#BF616A" if item["type"] == "Exit" else "#A3BE8C"
            self.canvas.itemconfig(item[2], fill=original_color, width=1)
        else:
            self.canvas.itemconfig(item["canvas_id"], outline="black" if item["type"] != "Class" else "#8E44AD", width=1 if item["type"] != "Class" else 2)
        self.canvas.update()

class FlowchartToCodeGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("流程圖轉程式碼工具（進階版）")
        self.root.state('zoomed')
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.toolbar = ttk.Frame(self.main_frame)
        self.toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        self.element_var = tk.StringVar(value="Process")
        elements = ["Start/End", "Process", "Decision", "Input", "Output", "Loop", "Comment", "Function", "Class"]
        ttk.Label(self.toolbar, text="元素：").pack(side=tk.LEFT, padx=2)
        ttk.OptionMenu(self.toolbar, self.element_var, "Process", *elements).pack(side=tk.LEFT, padx=2)

        self.connection_var = tk.StringVar(value="Body")
        ttk.Label(self.toolbar, text="連線：").pack(side=tk.LEFT, padx=2)
        ttk.OptionMenu(self.toolbar, self.connection_var, "Body", "Body", "Exit", "Call").pack(side=tk.LEFT, padx=2)

        self.animation_speed = tk.StringVar(value="Normal")
        ttk.Label(self.toolbar, text="動畫速度：").pack(side=tk.LEFT, padx=10)
        ttk.OptionMenu(self.toolbar, self.animation_speed, "Normal", "Slow", "Normal", "Fast").pack(side=tk.LEFT, padx=2)

        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=5)

        ttk.Button(self.toolbar, text="新增元素", command=lambda: self.add_element(self.main_canvas)).pack(side=tk.LEFT, padx=2)
        ttk.Button(self.toolbar, text="產生程式碼", command=self.generate_code).pack(side=tk.LEFT, padx=2)
        ttk.Button(self.toolbar, text="執行程式碼", command=self.run_code).pack(side=tk.LEFT, padx=2)

        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=5)

        ttk.Button(self.toolbar, text="變數管理", command=self.manage_variables).pack(side=tk.LEFT, padx=2)
        ttk.Button(self.toolbar, text="清除畫布", command=self.clear_canvas).pack(side=tk.LEFT, padx=2)
        ttk.Button(self.toolbar, text="儲存流程圖", command=self.save_flowchart).pack(side=tk.LEFT, padx=2)
        ttk.Button(self.toolbar, text="載入流程圖", command=self.load_flowchart).pack(side=tk.LEFT, padx=2)
        ttk.Button(self.toolbar, text="匯入模組", command=self.import_library).pack(side=tk.LEFT, padx=2)
        ttk.Button(self.toolbar, text="說明", command=self.show_help).pack(side=tk.LEFT, padx=2)

        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=5)

        ttk.Button(self.toolbar, text="上一步", command=self.undo).pack(side=tk.LEFT, padx=2)
        ttk.Button(self.toolbar, text="下一步", command=self.redo).pack(side=tk.LEFT, padx=2)

        self.paned_window = PanedWindow(self.main_frame, orient=tk.VERTICAL, sashwidth=5)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.canvas_frame = ttk.Frame(self.paned_window)
        self.paned_window.add(self.canvas_frame, minsize=400)

        self.main_canvas = FlowchartCanvas(self.canvas_frame, "主流程圖")
        self.bind_canvas_events(self.main_canvas)

        self.bottom_frame = ttk.Frame(self.paned_window)
        self.paned_window.add(self.bottom_frame, minsize=100)

        self.bottom_paned = PanedWindow(self.bottom_frame, orient=tk.HORIZONTAL, sashwidth=5)
        self.bottom_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.code_frame = ttk.LabelFrame(self.bottom_paned, text="程式碼", padding=5)
        self.bottom_paned.add(self.code_frame, minsize=200)
        self.code_text = Text(self.code_frame, width=50, height=15, font=("Consolas", 11), wrap="none")
        self.code_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self.output_frame = ttk.LabelFrame(self.bottom_paned, text="輸出", padding=5)
        self.bottom_paned.add(self.output_frame, minsize=200)
        self.output_text = Text(self.output_frame, width=50, height=15, font=("Consolas", 11), wrap="none", state="disabled")
        self.output_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self.libraries = []
        self.custom_modules = []
        self.variables = {}
        self.undo_stack = deque(maxlen=50)
        self.redo_stack = deque(maxlen=50)
        self.execution_globals = {}
        self.defined_variables = set()
        self.function_signatures = {}
        self.class_signatures = {}
        self.imported_names = {}

        self.style = ttk.Style()
        self.style.configure("TFrame", background="#ECEFF4")
        self.style.configure("TButton", padding=6)
        self.style.configure("TLabelFrame", background="#ffffff")

        self.syntax_sugar_templates = {
            "列表推導式": "[x*2 for x in iterable]",
            "字典推導式": "{k: v**2 for k, v in dict.items()}",
            "裝飾器": "@decorator\ndef func(): pass",
            "上下文管理器": "with open('file.txt') as f:\n    data = f.read()"
        }

    def bind_canvas_events(self, canvas):
        canvas.canvas.bind("<Button-1>", lambda event: self.start_connection(canvas, event))
        canvas.canvas.bind("<B1-Motion>", lambda event: self.draw_connection(canvas, event))
        canvas.canvas.bind("<ButtonRelease-1>", lambda event: self.end_connection(canvas, event))
        #canvas.canvas.bind("<Button-2>", lambda event: self.edit_connection(canvas, event)) # MacOS
        #canvas.canvas.bind("<Button-3>", lambda event: self.edit_connection(canvas, event)) # Windows/Linux
        
        #canvas.canvas.bind("<Button-1>", lambda e: self.handle_canvas_click(e, canvas))
        #canvas.canvas.bind("<B1-Motion>", lambda e: self.handle_canvas_drag(e, canvas))
        canvas.canvas.bind("<Button-2>", lambda e: self.show_context_menu(canvas, e))  # macOS
        canvas.canvas.bind("<Button-3>", lambda e: self.show_context_menu(canvas, e))  # Windows/Linux
        
    def get_animation_duration(self):
        speed = self.animation_speed.get()
        if speed == "Slow":
            return 1.0, 2.0
        elif speed == "Fast":
            return 0.2, 0.5
        else:
            return 0.5, 1.0

    def save_state(self, canvas):
        def serialize_canvas(canvas):
            elements_data = []
            for element in canvas.elements:
                elem_data = {
                    "id": element["id"],
                    "type": element["type"],
                    "x": element["x"],
                    "y": element["y"],
                    "code": element["code"],
                    "condition": element["condition"],
                    "loop_type": element["loop_type"],
                    "function_name": element["function_name"],
                    "function_params": element["function_params"],
                    "is_lambda": element.get("is_lambda"),
                    "return_value": element["return_value"],
                    "class_name": element.get("class_name"),
                    "parent_class": element.get("parent_class"),
                    "attributes": element.get("attributes"),
                    "methods": element.get("methods"),
                    "decorator": element.get("decorator"),
                    "subflowchart": serialize_canvas(element["subflowchart"]) if element["subflowchart"] else None
                }
                elements_data.append(elem_data)
            connections_data = [(canvas.elements.index(c[0]), canvas.elements.index(c[1]), c[4], c[5], c[6]) for c in canvas.connections]
            return {"elements": elements_data, "connections": connections_data}

        state = serialize_canvas(canvas)
        self.undo_stack.append(state)
        self.redo_stack.clear()

    def undo(self):
        if not self.undo_stack:
            messagebox.showinfo("提示", "無可取消的操作")
            return
        current_state = self.undo_stack.pop()
        self.redo_stack.append(current_state)
        previous_state = self.undo_stack[-1] if self.undo_stack else None
        self.restore_state(self.main_canvas, previous_state)

    def redo(self):
        if not self.redo_stack:
            messagebox.showinfo("提示", "無可重做的操作")
            return
        next_state = self.redo_stack.pop()
        self.undo_stack.append(next_state)
        self.restore_state(self.main_canvas, next_state)

    def restore_state(self, canvas, state):
        if not state:
            canvas.canvas.delete("all")
            canvas.elements = []
            canvas.connections = []
            self.defined_variables.clear()
            self.function_signatures.clear()
            self.class_signatures.clear()
            self.imported_names.clear()
            return

        canvas.canvas.delete("all")
        canvas.elements = []
        canvas.connections = []
        self.defined_variables.clear()
        self.function_signatures.clear()
        self.class_signatures.clear()
        self.imported_names.clear()

        for elem in state["elements"]:
            self.element_var.set(elem["type"])
            canvas.add_element(elem["type"], elem["x"], elem["y"], self)
            new_elem = canvas.elements[-1]
            new_elem["x"], new_elem["y"] = elem["x"], elem["y"]
            new_elem["code"] = elem["code"]
            new_elem["condition"] = elem["condition"]
            new_elem["loop_type"] = elem["loop_type"]
            new_elem["function_name"] = elem["function_name"]
            new_elem["function_params"] = elem["function_params"]
            new_elem["is_lambda"] = elem.get("is_lambda")
            new_elem["return_value"] = elem["return_value"]
            new_elem["class_name"] = elem.get("class_name")
            new_elem["parent_class"] = elem.get("parent_class")
            new_elem["attributes"] = elem.get("attributes")
            new_elem["methods"] = elem.get("methods", [])
            new_elem["decorator"] = elem.get("decorator")
            if elem["subflowchart"]:
                new_elem["subflowchart"] = FlowchartCanvas(self.root, f"函式/方法：{elem['function_name'] or elem['class_name'] or '未命名'}", is_subflowchart=True, function_element=new_elem)
                self.bind_canvas_events(new_elem["subflowchart"])
                self.restore_state(new_elem["subflowchart"], elem["subflowchart"])
            self.update_element_coords(new_elem, canvas)
            label_text = self.get_label_text(new_elem)
            canvas.canvas.itemconfig(new_elem["label_id"], text=label_text[:20] + "..." if len(label_text) > 20 else label_text)

            if elem["type"] in ["Process", "Input"]:
                self.update_defined_variables(elem["code"])
            elif elem["type"] == "Function" and elem["function_name"]:
                param_count = len([p for p in elem["function_params"].split(",") if p.strip()])
                self.function_signatures[elem["function_name"]] = param_count
            elif elem["type"] == "Class" and elem["class_name"]:
                self.class_signatures[elem["class_name"]] = {
                    "attributes": elem["attributes"] or {},
                    "methods": {m["name"]: len([p for p in m["params"].split(",") if p.strip()]) for m in elem["methods"] or []}
                }

    def update_element_coords(self, element, canvas):
        x, y = element["x"], element["y"]
        if element["type"] == "Start/End":
            canvas.canvas.coords(element["canvas_id"], x-40, y-20, x+40, y+20)
        elif element["type"] == "Decision":
            canvas.canvas.coords(element["canvas_id"], x, y-30, x+50, y, x, y+30, x-50, y)
        elif element["type"] == "Input":
            canvas.canvas.coords(element["canvas_id"], x-50, y-20, x+50, y-20, x+40, y+20, x-60, y+20)
        elif element["type"] == "Output":
            canvas.canvas.coords(element["canvas_id"], x-50, y-20, x+50, y-20, x+60, y+20, x-40, y+20)
        elif element["type"] == "Loop":
            canvas.canvas.coords(element["canvas_id"], x-40, y-20, x+40, y-20, x+50, y, x+40, y+20, x-40, y+20, x-50, y)
        elif element["type"] == "Class":
            canvas.canvas.coords(element["canvas_id"], x-60, y-30, x+60, y+30)
        else:
            canvas.canvas.coords(element["canvas_id"], x-50, y-20, x+50, y+20)
        canvas.canvas.coords(element["label_id"], x, y)

    def get_label_text(self, element):
        if element["type"] == "Start/End" and element["return_value"]:
            return f"Return: {element['return_value']}"
        elif element["type"] == "Function" and element["function_name"]:
            if element["decorator"]:
                return f"@{element['decorator']}\ndef {element['function_name']}({element['function_params']})"
            if element["is_lambda"]:
                return f"lambda element[{element['function_params']}]:{element['code']}"
            return f"def {element['function_name']}({element['function_params']})"
        elif element["type"] == "Class" and element["class_name"]:
            parent = f"({element['parent_class']})" if element["parent_class"] else ""
            return f"class {element['class_name']}{parent}"
        return element["code"] or element["condition"] or element["type"]

    def update_defined_variables(self, code):
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            self.defined_variables.add(target.id)
                elif isinstance(node, ast.For):
                    if isinstance(node.target, ast.Name):
                        self.defined_variables.add(node.target.id)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        self.imported_names[alias.asname or alias.name] = alias.name
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        self.imported_names[alias.asname or alias.name] = (node.module, alias.name)
        except SyntaxError as e:
            print(f"變數解析錯誤：{e}")
            pass

    def validate_code(self, code, is_condition=False, is_lambda=False, element=None, canvas=None):
        try:
            if is_lambda:
                ast.parse(f"lambda {code}")
            elif is_condition:
                ast.parse(f"if {code}: pass")
            else:
                ast.parse(code)
        except SyntaxError as e:
            return False, f"語法錯誤：{str(e)}"

        undefined_vars = set()
        try:
            tree = ast.parse(f"lambda x: {code}" if is_lambda else code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    if (node.id not in self.defined_variables and
                        node.id not in self.execution_globals and
                        node.id not in self.variables and
                        node.id not in self.imported_names and
                        node.id not in dir(builtins) and
                        node.id not in self.class_signatures):
                        undefined_vars.add(node.id)
                elif isinstance(node, ast.Attribute):
                    if isinstance(node.value, ast.Name):
                        obj_name = node.value.id
                        attr_name = node.attr
                        if obj_name in self.defined_variables:
                            found = False
                            for cls_name, cls_info in self.class_signatures.items():
                                if attr_name in cls_info["attributes"] or attr_name in cls_info["methods"]:
                                    found = True
                                    break
                            if not found:
                                undefined_vars.add(f"{obj_name}.{attr_name}")
            if undefined_vars:
                return False, f"未定義變數或方法：{', '.join(undefined_vars)}"
        except SyntaxError as e:
            print(f"驗證錯誤：{e}")
            pass

        if not is_lambda:
            valid_operators = r'[\+\-\*/%=<>&|\^~!]=?|==|!=|<=|>=|and|or|not|in'
            if not re.search(valid_operators, code) and (is_condition or element["type"] in ["Process", "Decision", "Loop"]):
                return False, f"缺少有效運算子。建議使用：{', '.join(['+', '-', '*', '/', '==', '!=', '<', '>', 'and', 'or', 'not'])}"

        if element and element["type"] == "Input":
            if "int(" not in code and "float(" not in code and "str(" not in code and "input(" not in code:
                return False, f"輸入元素應包含類型轉換或 input()（例如 int(input())）。"

        import_match = re.match(r'from\s+(\w+)\s+import\s+([\w\s*,]+)', code)
        if import_match:
            module = import_match.group(1)
            names = [n.strip() for n in import_match.group(2).split(',')]
            try:
                __import__(module)
                for name in names:
                    self.imported_names[name] = (module, name)
                return True, ""
            except ImportError:
                return False, f"模組 '{module}' 不存在。請確認模組名稱或安裝（例如 pip install {module}）。"

        if re.search(r'\[.*for.*in.*\]|\{.*:.*for.*in.*\}', code):
            try:
                ast.parse(code)
                return True, ""
            except SyntaxError as e:
                return False, f"推導式語法錯誤：{str(e)}。請檢查 [x for x in iterable] 或 {k: v for k, v in dict.items()} 的格式。"
        elif re.search(r'@\w+', code):
            try:
                ast.parse(code)
                if element["type"] == "Function":
                    decorator_name = re.search(r'@(\w+)', code).group(1)
                    if decorator_name not in self.function_signatures and decorator_name not in self.imported_names:
                        return False, f"裝飾器 '{decorator_name}' 未定義。"
                return True, ""
            except SyntaxError as e:
                return False, f"裝飾器語法錯誤：{str(e)}。請使用 @decorator 格式。"
        elif re.search(r'with\s+\w+\s+as\s+\w+', code):
            try:
                ast.parse(code)
                return True, ""
            except SyntaxError as e:
                return False, f"上下文管理器語法錯誤：{str(e)}。請使用 with open('file.txt') as f 格式。"

        return True, ""

    def validate_function_call(self, func_name, params):
        if func_name not in self.function_signatures:
            return False, f"函式 '{func_name}' 未定義。"
        param_count = len([p for p in params.split(",") if p.strip()])
        expected_count = self.function_signatures[func_name]
        if param_count != expected_count:
            return False, f"函式 '{func_name}' 期望 {expected_count} 個參數，但提供了 {param_count} 個。"
        return True, ""

    def validate_method_call(self, class_name, method_name, params):
        if class_name not in self.class_signatures:
            return False, f"類別 '{class_name}' 未定義。"
        if method_name not in self.class_signatures[class_name]["methods"]:
            return False, f"方法 '{method_name}' 未在類別 '{class_name}' 中定義。"
        param_count = len([p for p in params.split(",") if p.strip()])
        expected_count = self.class_signatures[class_name]["methods"][method_name]
        if param_count != expected_count:
            return False, f"方法 '{method_name}' 期望 {expected_count} 個參數，但提供了 {param_count} 個。"
        return True, ""

    def manage_variables(self):
        var_window = tk.Toplevel(self.root)
        var_window.title("變數管理")
        var_window.geometry("400x400")

        ttk.Label(var_window, text="變數名稱 | 初始值").pack(pady=5)
        tree = ttk.Treeview(var_window, columns=("Name", "Value"), show="headings")
        tree.heading("Name", text="變數名稱")
        tree.heading("Value", text="初始值")
        tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        for name, value in self.variables.items():
            tree.insert("", tk.END, values=(name, value))

        def add_variable():
            name = tk.simpledialog.askstring("輸入", "輸入變數名稱：")
            if not name or not name.isidentifier():
                messagebox.showerror("錯誤", "變數名稱無效，必須是有效的 Python 識別字。")
                return
            value = tk.simpledialog.askstring("輸入", f"輸入 {name} 的初始值（例如：10, 'text', True）：")
            try:
                eval(value)
                self.variables[name] = value
                self.defined_variables.add(name)
                tree.insert("", tk.END, values=(name, value))
            except Exception as e:
                messagebox.showerror("錯誤", f"初始值無效：{e}")

        def edit_variable():
            selected = tree.selection()
            if not selected:
                messagebox.showinfo("提示", "請選擇一個變數")
                return
            name, value = tree.item(selected)["values"]
            new_value = tk.simpledialog.askstring("輸入", f"編輯 {name} 的初始值：", initialvalue=value)
            try:
                eval(new_value)
                self.variables[name].values = new_value
                tree.item(selected, values=(name, new_value))
            except Exception as e:
                messagebox.showerror("錯誤", f"初始值無效：{e}")

        def delete_variable():
            selected = tree.selection()
            if not selected:
                messagebox.showinfo("提示", "請選擇一個變數")
                return
            name = tree.item(selected)["values"][0]
            try:
                del self.variables[name]
                self.defined_variables.discard(name)
                tree.delete(selected)
            except Exception as e:
                messagebox.showerror("錯誤", f"刪除變數失敗：{e}")

        ttk.Button(var_window, text="新增變數", command=add_variable).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(var_window, text="編輯變數", command=edit_variable).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(var_window, text="刪除變數", command=delete_variable).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(var_window, text="關閉", command=var_window.destroy).pack(side=tk.LEFT, padx=5, pady=5)

    def show_context_menu(self, canvas, event):
        context_menu = tk.Menu(self.root, tearoff=0)
        self.edit_connection(canvas, event)
        element = None
        for elem in canvas.elements:
            x, y = elem["x"], elem["y"]
            if abs(x - event.x) < 20 and abs(y - event.y) < 20:
                element = elem
                break
        if element:
            if element["type"] not in ["Start/End"]:
                context_menu.add_command(label="編輯", command=lambda: self.edit_element(canvas, element))
            context_menu.add_command(label="刪除", command=lambda: self.delete_element(canvas, element))
        else:
            context_menu.add_command(label="新增元素", command=lambda: self.add_element(canvas))
        context_menu.post(event.x_root, event.y_root)

    def add_element(self, canvas):
        self.save_state(canvas)
        element_type = self.element_var.get()
        x, y = 400, 50 + len(canvas.elements) * 100
        canvas.add_element(element_type, x, y, self)

    def move_element(self, canvas, event, element_id):
        for element in canvas.elements:
            if element["id"] == element_id:
                element["x"], element["y"] = event.x, event.y
                self.update_element_coords(element, canvas)
                self.update_connections(canvas)
                break

    def edit_element(self, canvas, event):
        for element in canvas.elements:
            if abs(event.x - element["x"]) < 50 and abs(event.y - element["x"]) < 30:
                self.selected_element = element
                break
        else:
            return

        if self.selected_element == canvas.elements[0]:
            messagebox.showinfo("提示", "無法編輯或刪除 Start 元素")
            return
        
        self.selected_element = element
        self.save_state(canvas)
        menu = tk.Toplevel(self.root)
        menu.title("元素操作")
        menu.geometry(f"200x150+{event.x_root}+{event.y_root}")
        menu.transient(self.root)
        menu.grab_set()

        def edit_action():
            menu.destroy()
            if self.selected_element["type"] in ["Process", "Input", "Output", "Comment"]:
                code_dialog = tk.Toplevel(self.root)
                code_dialog.title("編輯程式碼")
                code_dialog.geometry("400x300")

                tk.Label(code_dialog, text="選擇語法糖模板：").pack(pady=5)
                template_var = tk.StringVar(value="")
                template_combobox = ttk.Combobox(code_dialog, textvariable=template_var, values=list(self.syntax_sugar_templates.keys()))
                template_combobox.pack(pady=5)

                tk.Label(code_dialog, text="程式碼：").pack(pady=5)
                code_text = tk.Text(code_dialog, height=5, width=50)
                code_text.pack(pady=5)
                code_text.insert("1.0", self.selected_element["code"])

                def apply_template():
                    if template_var.get() != "無":
                        template_code = self.syntax_sugar_templates[template_var.get()]
                        valid, error_msg = self.validate_code(template_code, is_condition=False, element=element, canvas=canvas)
                        if not valid:
                            messagebox.showwarning("警告", f"模板無效：{error_msg}")
                            return
                        code_text.delete("1.0", tk.END)
                        code_text.insert("1.0", template_code)

                template_combobox.bind("<<ComboboxSelected>>", "<ComboboxSelected>", lambda e: apply_template())

                def save_code():
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

                    try:
                        self.update_element_coords(element, canvas)
                        label_text = self.get_label_text(element)
                        canvas.canvas.itemconfig(element["label_id"], text=label_text[:20] + "..." if len(label_text) > 20 else label_text)
                        code_dialog.destroy()
                    except Exception as e:
                        messagebox.showerror("錯誤", f"更新元素失敗：{str(e)}")
                ttk.Button(code_dialog, text="保存", command=save_code).pack(pady=10)
                code_dialog.protocol("WM_DELETE_WINDOW", code_dialog.destroy)

            elif self.selected_element["type"] in ["Decision", "Loop"]:
                condition = tk.simpledialog.askstring("輸入", f"輸入 {self.selected_element['type'].lower()} 條件：", initialvalue=self.selected_element["condition"])
                if condition:
                    valid, message = self.validate_code(condition, is_condition=True, element=self.selected_element, canvas=canvas)
                    if valid:
                        self.selected_element["condition"] = condition
                        canvas.canvas.itemconfig(self.selected_element["label_id"], text="condition"[:20] + "..." if len(condition) > 20 else "condition")
                    else:
                        messagebox.showerror("錯誤", message)
                if self.selected_element["type"] == "Loop":
                    loop_type = tk.simpledialog.askstring("輸入", "輸入迴圈類型 (for/while):", initialvalue=self.selected_element["loop_type"])
                    if loop_type in ["for", "while"]:
                        self.selected_element["loop_type"] = loop_type

            elif self.selected_element["type"] == "Function":
                func_dialog = tk.Toplevel(self.root)
                func_dialog.title("編輯函式")
                func_dialog.geometry("400x400")

                tk.Label(func_dialog, text="函式名稱：").pack(pady=5)
                name_entry = ttk.Entry(func_dialog)
                name_entry.pack(pady=5)
                name_entry.insert(0, self.selected_element["function_name"])

                tk.Label(func_dialog, text="參數（例如：x, y）：").pack(pady=5)
                param_entry = ttk.Entry(func_dialog)
                params_entry.pack(pady=5)
                params_entry.insert(0, params_entry["function_params"])

                tk.Label(func_dialog, text="裝飾器（例如：@timer，可選）：").pack(pady=5)
                decorator_entry = ttk.Entry(func_dialog)
                decorator_entry.pack(pady=5)
                decorator_entry.insert(0, self.selected_element["decorator"] or "")

                is_lambda_var = tk.BooleanVar(value=self.selected_lambda_var.get("is_lambda", False))
                ttk.Checkbutton(func_dialog, text="使用 Lambda 函式", variable=is_lambda_var).pack(pady=5)

                lambda_code_entry = ttk.Entry(func_dialog)
                lambda_code_entry.pack(pady=5)
                if is_lambda_var.get():
                    lambda_code_entry.insert(0, self.selected_lambda["code"])

                def toggle_lambda_fields():
                    if is_lambda_var.get():
                        name_entry.config(state="disabled")
                        decorator_entry.config(state="disabled")
                        lambda_code_entry.config(state="normal")
                    else:
                        name_entry.config(state="normal")
                        decorator_entry.config(state="normal")
                        lambda_code_entry.config(state="disabled")

                is_lambda_var.trace("w", lambda *args: toggle_lambda_fields())
                toggle_lambda_fields()

                def open_subflowchart():
                    if is_lambda_var.get():
                        messagebox.showinfo("提示", "Lambda 函式不支援子流程圖")
                        return
                    if not self.selected_element["subflowchart"]:
                        self.selected_element["subflowchart"] = FlowchartCanvas(self.root, f"函式：{name_entry.get() or '未命名'}", is_subflowchart=True, function_element=self.selected_element)
                        self.bind_canvas_events(self.selected_element["subflowchart"])
                    self.selected_element["subflowchart"].window.deiconify()

                ttk.Button(func_dialog, text="開啟子流程圖", command=open_subflowchart).pack(pady=5)

                def save_function():
                    if is_lambda_var.get():
                        code = lambda_code_entry.get()
                        params = params_entry.get()
                        valid, message = self.validate_code(f"{params}: {code}", is_lambda=True)
                        if not valid:
                            messagebox.showerror("錯誤", message)
                            return
                        self.selected_element["function_name"] = ""
                        self.selected_element["function_params"] = params
                        self.selected_element["code"] = code
                        self.selected_element["is_lambda"] = True
                        self.selected_element["decorator"] = ""
                        self.selected_element["subflowchart"] = None
                    else:
                        name = name_entry.get()
                        params = params_entry.get()
                        decorator = decorator_entry.get()
                        if not name.isidentifier():
                            messagebox.showerror("錯誤", "函式名稱無效，必須是有效的 Python 識別字。")
                            return
                        if decorator and not decorator.isidentifier():
                            messagebox.showerror("錯誤", "裝飾器名稱無效，必須是有效的 Python 識別字。")
                            return
                        if self.selected_element["function_name"] in self.function_signatures:
                            del self.function_signatures[self.selected_element["function_name"]]
                        self.selected_element["function_name"] = name
                        self.selected_element["function_params"] = params
                        self.selected_element["decorator"] = decorator
                        self.selected_element["is_lambda"] = False
                        self.selected_element["code"] = ""
                        param_count = len([p for p in params.split(",") if p.strip()])
                        self.function_signatures[name] = param_count
                    label = self.get_label_text(self.selected_element)
                    canvas.canvas.itemconfig(self.selected_element["label_id"], text=label[:20] + "..." if len(label) > 20 else label)
                    func_dialog.destroy()

                ttk.Button(func_dialog, text="儲存", command=save_function).pack(pady=10)
                func_dialog.protocol("WM_DELETE_WINDOW", func_dialog.destroy)

            elif self.selected_element["type"] == "Class":
                class_dialog = tk.Toplevel(self.root)
                class_dialog.title("編輯類別")
                class_dialog.geometry("600x500")

                notebook = ttk.Notebook(class_dialog)
                notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

                basic_frame = ttk.Frame(notebook)
                attr_frame = ttk.Frame(notebook)
                method_frame = ttk.Frame(notebook)
                notebook.add(basic_frame, text="基本資訊")
                notebook.add(attr_frame, text="屬性")
                notebook.add(method_frame, text="方法")

                tk.Label(basic_frame, text="類別名稱：").pack(pady=5)
                class_name_entry = ttk.Entry(basic_frame)
                class_name_entry.pack(pady=5)
                class_name_entry.insert(0, self.selected_element["class_name"])

                tk.Label(basic_frame, text="父類別（可選，例如 object）：").pack(pady=5)
                parent_class_entry = ttk.Entry(basic_frame)
                parent_class_entry.pack(pady=5)
                parent_class_entry.insert(0, self.selected_element["parent_class"])

                ttk.Label(attr_frame, text="屬性名稱 | 初始值").pack(pady=5)
                attr_tree = ttk.Treeview(attr_frame, columns=("Name", "Value"), show="headings")
                attr_tree.heading("Name", text="屬性名稱")
                attr_tree.heading("Value", text="初始值")
                attr_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

                for name, value in (self.selected_element["attributes"] or {}).items():
                    attr_tree.insert("", tk.END, values=(name, value))

                def add_attribute():
                    name = tk.simpledialog.askstring("輸入", "輸入屬性名稱：")
                    if not name or not name.isidentifier():
                        messagebox.showerror("錯誤", "屬性名稱無效，必須是有效的 Python 識別字。")
                        return
                    value = tk.simpledialog.askstring("輸入", f"輸入 {name} 的初始值：")
                    try:
                        eval(value)
                        self.selected_element["attributes"][name] = value
                        attr_tree.insert("", tk.END, values=(name, value))
                    except Exception as e:
                        messagebox.showerror("錯誤", f"初始值無效：{e}")

                def edit_attribute():
                    selected = attr_tree.selection()
                    if not selected:
                        messagebox.showinfo("提示", "請選擇一個屬性")
                        return
                    name, value = attr_tree.item(selected)["values"]
                    new_value = tk.simpledialog.askstring("輸入", f"編輯 {name} 的初始值：", initialvalue=value)
                    try:
                        eval(new_value)
                        self.selected_element["attributes"][name] = new_value
                        attr_tree.item(selected, values=(name, new_value))
                    except Exception as e:
                        messagebox.showerror("錯誤", f"初始值無效：{e}")

                def delete_attribute():
                    selected = attr_tree.selection()
                    if not selected:
                        messagebox.showinfo("提示", "請選擇一個屬性")
                        return
                    name = attr_tree.item(selected)["values"][0]
                    del self.selected_element["attributes"][name]
                    attr_tree.delete(selected)

                ttk.Button(attr_frame, text="新增屬性", command=add_attribute).pack(side=tk.LEFT, padx=5, pady=5)
                ttk.Button(attr_frame, text="編輯屬性", command=edit_attribute).pack(side=tk.LEFT, padx=5, pady=5)
                ttk.Button(attr_frame, text="刪除屬性", command=delete_attribute).pack(side=tk.LEFT, padx=5, pady=5)

                ttk.Label(method_frame, text="方法名稱 | 參數 | Lambda 是否").pack(pady=5)
                method_tree = ttk.Treeview(method_frame, columns=("Name", "Params", "Lambda"), show="headings")
                method_tree.heading("Name", text="方法名稱")
                method_tree.heading("Params", text="參數")
                method_tree.heading("Lambda", text="是否 Lambda")
                method_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

                for method in self.selected_element["methods"] or []:
                    method_tree.insert("", tk.END, values=(method["name"], method["params"], "是" if method["is_lambda"] else "否"))

                def add_method():
                    method_dialog = tk.Toplevel(class_dialog)
                    method_dialog.title("新增方法")
                    method_dialog.geometry("400x300")

                    tk.Label(method_dialog, text="方法名稱：").pack(pady=5)
                    method_name_entry = ttk.Entry(method_dialog)
                    method_name_entry.pack(pady=5)

                    tk.Label(method_dialog, text="參數（例如：self, x）：").pack(pady=5)
                    method_params_entry = ttk.Entry(method_dialog)
                    method_params_entry.pack(pady=5)
                    method_params_entry.insert(0, "self")

                    is_lambda_var = tk.BooleanVar()
                    ttk.Checkbutton(method_dialog, text="使用 Lambda 函式", variable=is_lambda_var).pack(pady=5)

                    lambda_code_entry = ttk.Entry(method_dialog)
                    lambda_code_entry.pack(pady=5)
                    lambda_code_entry.config(state="disabled")

                    def toggle_lambda_fields():
                        if is_lambda_var.get():
                            method_name_entry.config(state="normal")
                            lambda_code_entry.config(state="normal")
                        else:
                            method_name_entry.config(state="normal")
                            lambda_code_entry.config(state="disabled")

                    is_lambda_var.trace("w", lambda *args: toggle_lambda_fields())

                    def save_method():
                        name = method_name_entry.get()
                        params = method_params_entry.get()
                        if not name.isidentifier():
                            messagebox.showerror("錯誤", "方法名稱無效，必須是有效的 Python 識別字。")
                            return
                        if name == "__init__":
                            messagebox.showerror("錯誤", "__init__ 方法由系統自動生成。")
                            return
                        if is_lambda_var.get():
                            code = lambda_code_entry.get()
                            valid, message = self.validate_code(f"{params}: {code}", is_lambda=True)
                            if not valid:
                                messagebox.showerror("錯誤", message)
                                return
                            method = {"name": name, "params": params, "is_lambda": True, "code": code, "subflowchart": None}
                        else:
                            method = {"name": name, "params": params, "is_lambda": False, "code": "", "subflowchart": None}
                        self.selected_element["methods"].append(method)
                        method_tree.insert("", tk.END, values=(name, params, "是" if is_lambda_var.get() else "否"))
                        method_dialog.destroy()

                    ttk.Button(method_dialog, text="儲存", command=save_method).pack(pady=10)
                    method_dialog.protocol("WM_DELETE_WINDOW", method_dialog.destroy)

                def edit_method():
                    selected = method_tree.selection()
                    if not selected:
                        messagebox.showinfo("提示", "請選擇一個方法")
                        return
                    name, params, is_lambda = method_tree.item(selected)["values"]
                    method = next(m for m in self.selected_element["methods"] if m["name"] == name)

                    method_dialog = tk.Toplevel(class_dialog)
                    method_dialog.title("編輯方法")
                    method_dialog.geometry("400x300")

                    tk.Label(method_dialog, text="方法名稱：").pack(pady=5)
                    method_name_entry = ttk.Entry(method_dialog)
                    method_name_entry.pack(pady=5)
                    method_name_entry.insert(0, name)

                    tk.Label(method_dialog, text="參數（例如：self, x）：").pack(pady=5)
                    method_params_entry = ttk.Entry(method_dialog)
                    method_params_entry.pack(pady=5)
                    method_params_entry.insert(0, params)

                    is_lambda_var = tk.BooleanVar(value=is_lambda == "是")
                    ttk.Checkbutton(method_dialog, text="使用 Lambda 函式", variable=is_lambda_var).pack(pady=5)

                    lambda_code_entry = ttk.Entry(method_dialog)
                    lambda_code_entry.pack(pady=5)
                    lambda_code_entry.insert(0, method["code"] if method["is_lambda"] else "")
                    lambda_code_entry.config(state="normal" if is_lambda == "是" else "disabled")

                    def toggle_lambda_fields():
                        if is_lambda_var.get():
                            method_name_entry.config(state="normal")
                            lambda_code_entry.config(state="normal")
                        else:
                            method_name_entry.config(state="normal")
                            lambda_code_entry.config(state="disabled")

                    is_lambda_var.trace("w", lambda *args: toggle_lambda_fields())

                    def open_subflowchart():
                        if is_lambda_var.get():
                            messagebox.showinfo("提示", "Lambda 方法不支援子流程圖")
                            return
                        if not method["subflowchart"]:
                            method["subflowchart"] = FlowchartCanvas(self.root, f"方法：{name}", is_subflowchart=True, function_element=self.selected_element)
                            self.bind_canvas_events(method["subflowchart"])
                        method["subflowchart"].window.deiconify()

                    ttk.Button(method_dialog, text="開啟子流程圖", command=open_subflowchart).pack(pady=5)

                    def save_method():
                        new_name = method_name_entry.get()
                        new_params = method_params_entry.get()
                        if not new_name.isidentifier():
                            messagebox.showerror("錯誤", "方法名稱無效，必須是有效的 Python 識別字。")
                            return
                        if new_name == "__init__":
                            messagebox.showerror("錯誤", "__init__ 方法由系統自動生成。")
                            return
                        if is_lambda_var.get():
                            code = lambda_code_entry.get()
                            valid, message = self.validate_code(f"{new_params}: {code}", is_lambda=True)
                            if not valid:
                                messagebox.showerror("錯誤", message)
                                return
                            method.update({
                                "name": new_name,
                                "params": new_params,
                                "is_lambda": True,
                                "code": code,
                                "subflowchart": None
                            })
                        else:
                            method.update({
                                "name": new_name,
                                "params": new_params,
                                "is_lambda": False,
                                "code": "",
                                "subflowchart": method["subflowchart"]
                            })
                        method_tree.item(selected, values=(new_name, new_params, "是" if is_lambda_var.get() else "否"))
                        method_dialog.destroy()

                    ttk.Button(method_dialog, text="儲存", command=save_method).pack(pady=10)
                    method_dialog.protocol("WM_DELETE_WINDOW", method_dialog.destroy)

                def delete_method():
                    selected = method_tree.selection()
                    if not selected:
                        messagebox.showinfo("提示", "請選擇一個方法")
                        return
                    name = method_tree.item(selected)["values"][0]
                    self.selected_element["methods"] = [m for m in self.selected_element["methods"] if m["name"] != name]
                    method_tree.delete(selected)

                ttk.Button(method_frame, text="新增方法", command=add_method).pack(side=tk.LEFT, padx=5, pady=5)
                ttk.Button(method_frame, text="編輯方法", command=edit_method).pack(side=tk.LEFT, padx=5, pady=5)
                ttk.Button(method_frame, text="刪除方法", command=delete_method).pack(side=tk.LEFT, padx=5, pady=5)

                def save_class():
                    class_name = class_name_entry.get()
                    parent_class = parent_class_entry.get()
                    if not class_name.isidentifier():
                        messagebox.showerror("錯誤", "類別名稱無效，必須是有效的 Python 識別字。")
                        return
                    if parent_class and not parent_class.isidentifier() and parent_class not in self.class_signatures:
                        messagebox.showerror("錯誤", "父類別無效，必須是有效的 Python 識別字或已定義的類別。")
                        return
                    if self.selected_element["class_name"] in self.class_signatures:
                        del self.class_signatures[self.selected_element["class_name"]]
                    self.selected_element["class_name"] = class_name
                    self.selected_element["parent_class"] = parent_class
                    self.class_signatures[class_name] = {
                        "attributes": self.selected_element["attributes"],
                        "methods": {m["name"]: len([p for p in m["params"].split(",") if p.strip()]) for m in self.selected_element["methods"]}
                    }
                    label = self.get_label_text(self.selected_element)
                    canvas.canvas.itemconfig(self.selected_element["label_id"], text=label[:20] + "..." if len(label) > 20 else label)
                    class_dialog.destroy()

                ttk.Button(class_dialog, text="儲存", command=save_class).pack(pady=10)
                class_dialog.protocol("WM_DELETE_WINDOW", class_dialog.destroy)

            elif self.selected_element["type"] == "Start/End" and self.selected_element in canvas.elements[1:]:
                return_value = tk.simpledialog.askstring("輸入", "輸入回傳值（例如：result）：", initialvalue=self.selected_element["return_value"])
                if return_value:
                    valid, message = self.validate_code(return_value, canvas=canvas)
                    if valid:
                        self.selected_element["return_value"] = return_value
                        canvas.canvas.itemconfig(self.selected_element["label_id"], text=f"Return: {return_value}"[:20] + "..." if len(return_value) > 20 else f"Return: {return_value}")
                    else:
                        messagebox.showerror("錯誤", message)

        def delete_action():
            menu.destroy()
            try:
                canvas.canvas.delete(self.selected_element["canvas_id"])
                canvas.canvas.delete(self.selected_element["label_id"])
                connections_to_remove = [conn for conn in canvas.connections if conn[0] == self.selected_element or conn[1] == self.selected_element]
                for conn in connections_to_remove:
                    canvas.canvas.delete(conn[2])
                    canvas.canvas.delete(conn[3])
                    canvas.connections.remove(conn)
                if self.selected_element["type"] in ["Function", "Class"] and self.selected_element["subflowchart"]:
                    try:
                        self.selected_element["subflowchart"].window.destroy()
                    except Exception as e:
                        pass
                if self.selected_element["type"] == "Function" and self.selected_element["function_name"]:
                    if self.selected_element["function_name"] in self.function_signatures:
                        del self.function_signatures[self.selected_element["function_name"]]
                elif self.selected_element["type"] == "Class" and self.selected_element["class_name"]:
                    if self.selected_element["class_name"] in self.class_signatures:
                        del self.class_signatures[self.selected_element["class_name"]]
                canvas.elements.remove(self.selected_element)
                self.selected_element = None
            except Exception as e:
                messagebox.showerror("錯誤", f"刪除元素失敗：{str(e)}")

        ttk.Button(menu, text="編輯內容", command=edit_action).pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(menu, text="刪除元素及其連線", command=delete_action).pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(menu, text="取消", command=menu.destroy).pack(fill=tk.X, padx=5, pady=5)

        menu.protocol("WM_DELETE_WINDOW", menu.destroy)

    def edit_element(self, canvas, element):
        self.selected_element = element
        if self.selected_element["type"] in ["Process", "Input", "Output", "Comment"]:
            code_dialog = tk.Toplevel(self.root)
            code_dialog.title("編輯程式碼")
            code_dialog.geometry("400x300")

            tk.Label(code_dialog, text="選擇語法糖模板：").pack(pady=5)
            template_var = tk.StringVar(value="")
            template_combobox = ttk.Combobox(code_dialog, textvariable=template_var, values=list(self.syntax_sugar_templates.keys()))
            template_combobox.pack(pady=5)

            tk.Label(code_dialog, text="程式碼：").pack(pady=5)
            code_text = tk.Text(code_dialog, height=5, width=50)
            code_text.pack(pady=5)
            code_text.insert("1.0", self.selected_element["code"])

            def apply_template():
                if template_var.get() != "無":
                    template_code = self.syntax_sugar_templates[template_var.get()]
                    valid, error_msg = self.validate_code(template_code, is_condition=False, element=element, canvas=canvas)
                    if not valid:
                        messagebox.showwarning("警告", f"模板無效：{error_msg}")
                        return
                    code_text.delete("1.0", tk.END)
                    code_text.insert("1.0", template_code)

            template_combobox.bind("<<ComboboxSelected>>", "<ComboboxSelected>", lambda e: apply_template())

            def save_code():
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

                try:
                    self.update_element_coords(element, canvas)
                    label_text = self.get_label_text(element)
                    canvas.canvas.itemconfig(element["label_id"], text=label_text[:20] + "..." if len(label_text) > 20 else label_text)
                    code_dialog.destroy()
                except Exception as e:
                    messagebox.showerror("錯誤", f"更新元素失敗：{str(e)}")
            ttk.Button(code_dialog, text="保存", command=save_code).pack(pady=10)
            code_dialog.protocol("WM_DELETE_WINDOW", code_dialog.destroy)

        elif self.selected_element["type"] in ["Decision", "Loop"]:
            condition = tk.simpledialog.askstring("輸入", f"輸入 {self.selected_element['type'].lower()} 條件：", initialvalue=self.selected_element["condition"])
            if condition:
                valid, message = self.validate_code(condition, is_condition=True, element=self.selected_element, canvas=canvas)
                if valid:
                    self.selected_element["condition"] = condition
                    canvas.canvas.itemconfig(self.selected_element["label_id"], text="condition"[:20] + "..." if len(condition) > 20 else "condition")
                else:
                    messagebox.showerror("錯誤", message)
            if self.selected_element["type"] == "Loop":
                loop_type = tk.simpledialog.askstring("輸入", "輸入迴圈類型 (for/while):", initialvalue=self.selected_element["loop_type"])
                if loop_type in ["for", "while"]:
                    self.selected_element["loop_type"] = loop_type

        elif self.selected_element["type"] == "Function":
            func_dialog = tk.Toplevel(self.root)
            func_dialog.title("編輯函式")
            func_dialog.geometry("400x400")

            tk.Label(func_dialog, text="函式名稱：").pack(pady=5)
            name_entry = ttk.Entry(func_dialog)
            name_entry.pack(pady=5)
            name_entry.insert(0, self.selected_element["function_name"])

            tk.Label(func_dialog, text="參數（例如：x, y）：").pack(pady=5)
            param_entry = ttk.Entry(func_dialog)
            params_entry.pack(pady=5)
            params_entry.insert(0, params_entry["function_params"])

            tk.Label(func_dialog, text="裝飾器（例如：@timer，可選）：").pack(pady=5)
            decorator_entry = ttk.Entry(func_dialog)
            decorator_entry.pack(pady=5)
            decorator_entry.insert(0, self.selected_element["decorator"] or "")

            is_lambda_var = tk.BooleanVar(value=self.selected_lambda_var.get("is_lambda", False))
            ttk.Checkbutton(func_dialog, text="使用 Lambda 函式", variable=is_lambda_var).pack(pady=5)

            lambda_code_entry = ttk.Entry(func_dialog)
            lambda_code_entry.pack(pady=5)
            if is_lambda_var.get():
                lambda_code_entry.insert(0, self.selected_lambda["code"])

            def toggle_lambda_fields():
                if is_lambda_var.get():
                    name_entry.config(state="disabled")
                    decorator_entry.config(state="disabled")
                    lambda_code_entry.config(state="normal")
                else:
                    name_entry.config(state="normal")
                    decorator_entry.config(state="normal")
                    lambda_code_entry.config(state="disabled")

            is_lambda_var.trace("w", lambda *args: toggle_lambda_fields())
            toggle_lambda_fields()

            def open_subflowchart():
                if is_lambda_var.get():
                    messagebox.showinfo("提示", "Lambda 函式不支援子流程圖")
                    return
                if not self.selected_element["subflowchart"]:
                    self.selected_element["subflowchart"] = FlowchartCanvas(self.root, f"函式：{name_entry.get() or '未命名'}", is_subflowchart=True, function_element=self.selected_element)
                    self.bind_canvas_events(self.selected_element["subflowchart"])
                self.selected_element["subflowchart"].window.deiconify()

            ttk.Button(func_dialog, text="開啟子流程圖", command=open_subflowchart).pack(pady=5)

            def save_function():
                if is_lambda_var.get():
                    code = lambda_code_entry.get()
                    params = params_entry.get()
                    valid, message = self.validate_code(f"{params}: {code}", is_lambda=True)
                    if not valid:
                        messagebox.showerror("錯誤", message)
                        return
                    self.selected_element["function_name"] = ""
                    self.selected_element["function_params"] = params
                    self.selected_element["code"] = code
                    self.selected_element["is_lambda"] = True
                    self.selected_element["decorator"] = ""
                    self.selected_element["subflowchart"] = None
                else:
                    name = name_entry.get()
                    params = params_entry.get()
                    decorator = decorator_entry.get()
                    if not name.isidentifier():
                        messagebox.showerror("錯誤", "函式名稱無效，必須是有效的 Python 識別字。")
                        return
                    if decorator and not decorator.isidentifier():
                        messagebox.showerror("錯誤", "裝飾器名稱無效，必須是有效的 Python 識別字。")
                        return
                    if self.selected_element["function_name"] in self.function_signatures:
                        del self.function_signatures[self.selected_element["function_name"]]
                    self.selected_element["function_name"] = name
                    self.selected_element["function_params"] = params
                    self.selected_element["decorator"] = decorator
                    self.selected_element["is_lambda"] = False
                    self.selected_element["code"] = ""
                    param_count = len([p for p in params.split(",") if p.strip()])
                    self.function_signatures[name] = param_count
                label = self.get_label_text(self.selected_element)
                canvas.canvas.itemconfig(self.selected_element["label_id"], text=label[:20] + "..." if len(label) > 20 else label)
                func_dialog.destroy()

            ttk.Button(func_dialog, text="儲存", command=save_function).pack(pady=10)
            func_dialog.protocol("WM_DELETE_WINDOW", func_dialog.destroy)

        elif self.selected_element["type"] == "Class":
            class_dialog = tk.Toplevel(self.root)
            class_dialog.title("編輯類別")
            class_dialog.geometry("600x500")

            notebook = ttk.Notebook(class_dialog)
            notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            basic_frame = ttk.Frame(notebook)
            attr_frame = ttk.Frame(notebook)
            method_frame = ttk.Frame(notebook)
            notebook.add(basic_frame, text="基本資訊")
            notebook.add(attr_frame, text="屬性")
            notebook.add(method_frame, text="方法")

            tk.Label(basic_frame, text="類別名稱：").pack(pady=5)
            class_name_entry = ttk.Entry(basic_frame)
            class_name_entry.pack(pady=5)
            class_name_entry.insert(0, self.selected_element["class_name"])

            tk.Label(basic_frame, text="父類別（可選，例如 object）：").pack(pady=5)
            parent_class_entry = ttk.Entry(basic_frame)
            parent_class_entry.pack(pady=5)
            parent_class_entry.insert(0, self.selected_element["parent_class"])

            ttk.Label(attr_frame, text="屬性名稱 | 初始值").pack(pady=5)
            attr_tree = ttk.Treeview(attr_frame, columns=("Name", "Value"), show="headings")
            attr_tree.heading("Name", text="屬性名稱")
            attr_tree.heading("Value", text="初始值")
            attr_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            for name, value in (self.selected_element["attributes"] or {}).items():
                attr_tree.insert("", tk.END, values=(name, value))

            def add_attribute():
                name = tk.simpledialog.askstring("輸入", "輸入屬性名稱：")
                if not name or not name.isidentifier():
                    messagebox.showerror("錯誤", "屬性名稱無效，必須是有效的 Python 識別字。")
                    return
                value = tk.simpledialog.askstring("輸入", f"輸入 {name} 的初始值：")
                try:
                    eval(value)
                    self.selected_element["attributes"][name] = value
                    attr_tree.insert("", tk.END, values=(name, value))
                except Exception as e:
                    messagebox.showerror("錯誤", f"初始值無效：{e}")

            def edit_attribute():
                selected = attr_tree.selection()
                if not selected:
                    messagebox.showinfo("提示", "請選擇一個屬性")
                    return
                name, value = attr_tree.item(selected)["values"]
                new_value = tk.simpledialog.askstring("輸入", f"編輯 {name} 的初始值：", initialvalue=value)
                try:
                    eval(new_value)
                    self.selected_element["attributes"][name] = new_value
                    attr_tree.item(selected, values=(name, new_value))
                except Exception as e:
                    messagebox.showerror("錯誤", f"初始值無效：{e}")

            def delete_attribute():
                selected = attr_tree.selection()
                if not selected:
                    messagebox.showinfo("提示", "請選擇一個屬性")
                    return
                name = attr_tree.item(selected)["values"][0]
                del self.selected_element["attributes"][name]
                attr_tree.delete(selected)

            ttk.Button(attr_frame, text="新增屬性", command=add_attribute).pack(side=tk.LEFT, padx=5, pady=5)
            ttk.Button(attr_frame, text="編輯屬性", command=edit_attribute).pack(side=tk.LEFT, padx=5, pady=5)
            ttk.Button(attr_frame, text="刪除屬性", command=delete_attribute).pack(side=tk.LEFT, padx=5, pady=5)

            ttk.Label(method_frame, text="方法名稱 | 參數 | Lambda 是否").pack(pady=5)
            method_tree = ttk.Treeview(method_frame, columns=("Name", "Params", "Lambda"), show="headings")
            method_tree.heading("Name", text="方法名稱")
            method_tree.heading("Params", text="參數")
            method_tree.heading("Lambda", text="是否 Lambda")
            method_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            for method in self.selected_element["methods"] or []:
                method_tree.insert("", tk.END, values=(method["name"], method["params"], "是" if method["is_lambda"] else "否"))

            def add_method():
                method_dialog = tk.Toplevel(class_dialog)
                method_dialog.title("新增方法")
                method_dialog.geometry("400x300")

                tk.Label(method_dialog, text="方法名稱：").pack(pady=5)
                method_name_entry = ttk.Entry(method_dialog)
                method_name_entry.pack(pady=5)

                tk.Label(method_dialog, text="參數（例如：self, x）：").pack(pady=5)
                method_params_entry = ttk.Entry(method_dialog)
                method_params_entry.pack(pady=5)
                method_params_entry.insert(0, "self")

                is_lambda_var = tk.BooleanVar()
                ttk.Checkbutton(method_dialog, text="使用 Lambda 函式", variable=is_lambda_var).pack(pady=5)

                lambda_code_entry = ttk.Entry(method_dialog)
                lambda_code_entry.pack(pady=5)
                lambda_code_entry.config(state="disabled")

                def toggle_lambda_fields():
                    if is_lambda_var.get():
                        method_name_entry.config(state="normal")
                        lambda_code_entry.config(state="normal")
                    else:
                        method_name_entry.config(state="normal")
                        lambda_code_entry.config(state="disabled")

                is_lambda_var.trace("w", lambda *args: toggle_lambda_fields())

                def save_method():
                    name = method_name_entry.get()
                    params = method_params_entry.get()
                    if not name.isidentifier():
                        messagebox.showerror("錯誤", "方法名稱無效，必須是有效的 Python 識別字。")
                        return
                    if name == "__init__":
                        messagebox.showerror("錯誤", "__init__ 方法由系統自動生成。")
                        return
                    if is_lambda_var.get():
                        code = lambda_code_entry.get()
                        valid, message = self.validate_code(f"{params}: {code}", is_lambda=True)
                        if not valid:
                            messagebox.showerror("錯誤", message)
                            return
                        method = {"name": name, "params": params, "is_lambda": True, "code": code, "subflowchart": None}
                    else:
                        method = {"name": name, "params": params, "is_lambda": False, "code": "", "subflowchart": None}
                    self.selected_element["methods"].append(method)
                    method_tree.insert("", tk.END, values=(name, params, "是" if is_lambda_var.get() else "否"))
                    method_dialog.destroy()

                ttk.Button(method_dialog, text="儲存", command=save_method).pack(pady=10)
                method_dialog.protocol("WM_DELETE_WINDOW", method_dialog.destroy)

            def edit_method():
                selected = method_tree.selection()
                if not selected:
                    messagebox.showinfo("提示", "請選擇一個方法")
                    return
                name, params, is_lambda = method_tree.item(selected)["values"]
                method = next(m for m in self.selected_element["methods"] if m["name"] == name)

                method_dialog = tk.Toplevel(class_dialog)
                method_dialog.title("編輯方法")
                method_dialog.geometry("400x300")

                tk.Label(method_dialog, text="方法名稱：").pack(pady=5)
                method_name_entry = ttk.Entry(method_dialog)
                method_name_entry.pack(pady=5)
                method_name_entry.insert(0, name)

                tk.Label(method_dialog, text="參數（例如：self, x）：").pack(pady=5)
                method_params_entry = ttk.Entry(method_dialog)
                method_params_entry.pack(pady=5)
                method_params_entry.insert(0, params)

                is_lambda_var = tk.BooleanVar(value=is_lambda == "是")
                ttk.Checkbutton(method_dialog, text="使用 Lambda 函式", variable=is_lambda_var).pack(pady=5)

                lambda_code_entry = ttk.Entry(method_dialog)
                lambda_code_entry.pack(pady=5)
                lambda_code_entry.insert(0, method["code"] if method["is_lambda"] else "")
                lambda_code_entry.config(state="normal" if is_lambda == "是" else "disabled")

                def toggle_lambda_fields():
                    if is_lambda_var.get():
                        method_name_entry.config(state="normal")
                        lambda_code_entry.config(state="normal")
                    else:
                        method_name_entry.config(state="normal")
                        lambda_code_entry.config(state="disabled")

                is_lambda_var.trace("w", lambda *args: toggle_lambda_fields())

                def open_subflowchart():
                    if is_lambda_var.get():
                        messagebox.showinfo("提示", "Lambda 方法不支援子流程圖")
                        return
                    if not method["subflowchart"]:
                        method["subflowchart"] = FlowchartCanvas(self.root, f"方法：{name}", is_subflowchart=True, function_element=self.selected_element)
                        self.bind_canvas_events(method["subflowchart"])
                    method["subflowchart"].window.deiconify()

                ttk.Button(method_dialog, text="開啟子流程圖", command=open_subflowchart).pack(pady=5)

                def save_method():
                    new_name = method_name_entry.get()
                    new_params = method_params_entry.get()
                    if not new_name.isidentifier():
                        messagebox.showerror("錯誤", "方法名稱無效，必須是有效的 Python 識別字。")
                        return
                    if new_name == "__init__":
                        messagebox.showerror("錯誤", "__init__ 方法由系統自動生成。")
                        return
                    if is_lambda_var.get():
                        code = lambda_code_entry.get()
                        valid, message = self.validate_code(f"{new_params}: {code}", is_lambda=True)
                        if not valid:
                            messagebox.showerror("錯誤", message)
                            return
                        method.update({
                            "name": new_name,
                            "params": new_params,
                            "is_lambda": True,
                            "code": code,
                            "subflowchart": None
                        })
                    else:
                        method.update({
                            "name": new_name,
                            "params": new_params,
                            "is_lambda": False,
                            "code": "",
                            "subflowchart": method["subflowchart"]
                        })
                    method_tree.item(selected, values=(new_name, new_params, "是" if is_lambda_var.get() else "否"))
                    method_dialog.destroy()

                ttk.Button(method_dialog, text="儲存", command=save_method).pack(pady=10)
                method_dialog.protocol("WM_DELETE_WINDOW", method_dialog.destroy)

            def delete_method():
                selected = method_tree.selection()
                if not selected:
                    messagebox.showinfo("提示", "請選擇一個方法")
                    return
                name = method_tree.item(selected)["values"][0]
                self.selected_element["methods"] = [m for m in self.selected_element["methods"] if m["name"] != name]
                method_tree.delete(selected)

            ttk.Button(method_frame, text="新增方法", command=add_method).pack(side=tk.LEFT, padx=5, pady=5)
            ttk.Button(method_frame, text="編輯方法", command=edit_method).pack(side=tk.LEFT, padx=5, pady=5)
            ttk.Button(method_frame, text="刪除方法", command=delete_method).pack(side=tk.LEFT, padx=5, pady=5)

            def save_class():
                class_name = class_name_entry.get()
                parent_class = parent_class_entry.get()
                if not class_name.isidentifier():
                    messagebox.showerror("錯誤", "類別名稱無效，必須是有效的 Python 識別字。")
                    return
                if parent_class and not parent_class.isidentifier() and parent_class not in self.class_signatures:
                    messagebox.showerror("錯誤", "父類別無效，必須是有效的 Python 識別字或已定義的類別。")
                    return
                if self.selected_element["class_name"] in self.class_signatures:
                    del self.class_signatures[self.selected_element["class_name"]]
                self.selected_element["class_name"] = class_name
                self.selected_element["parent_class"] = parent_class
                self.class_signatures[class_name] = {
                    "attributes": self.selected_element["attributes"],
                    "methods": {m["name"]: len([p for p in m["params"].split(",") if p.strip()]) for m in self.selected_element["methods"]}
                }
                label = self.get_label_text(self.selected_element)
                canvas.canvas.itemconfig(self.selected_element["label_id"], text=label[:20] + "..." if len(label) > 20 else label)
                class_dialog.destroy()

            ttk.Button(class_dialog, text="儲存", command=save_class).pack(pady=10)
            class_dialog.protocol("WM_DELETE_WINDOW", class_dialog.destroy)

        elif self.selected_element["type"] == "Start/End" and self.selected_element in canvas.elements[1:]:
            return_value = tk.simpledialog.askstring("輸入", "輸入回傳值（例如：result）：", initialvalue=self.selected_element["return_value"])
            if return_value:
                valid, message = self.validate_code(return_value, canvas=canvas)
                if valid:
                    self.selected_element["return_value"] = return_value
                    canvas.canvas.itemconfig(self.selected_element["label_id"], text=f"Return: {return_value}"[:20] + "..." if len(return_value) > 20 else f"Return: {return_value}")
                else:
                    messagebox.showerror("錯誤", message)

    def delete_element(self, canvas, element):
        self.selected_element = element
        try:
            canvas.canvas.delete(self.selected_element["canvas_id"])
            canvas.canvas.delete(self.selected_element["label_id"])
            connections_to_remove = [conn for conn in canvas.connections if conn[0] == self.selected_element or conn[1] == self.selected_element]
            for conn in connections_to_remove:
                canvas.canvas.delete(conn[2])
                canvas.canvas.delete(conn[3])
                canvas.connections.remove(conn)
            if self.selected_element["type"] in ["Function", "Class"] and self.selected_element["subflowchart"]:
                try:
                    self.selected_element["subflowchart"].window.destroy()
                except Exception as e:
                    pass
            if self.selected_element["type"] == "Function" and self.selected_element["function_name"]:
                if self.selected_element["function_name"] in self.function_signatures:
                    del self.function_signatures[self.selected_element["function_name"]]
            elif self.selected_element["type"] == "Class" and self.selected_element["class_name"]:
                if self.selected_element["class_name"] in self.class_signatures:
                    del self.class_signatures[self.selected_element["class_name"]]
            canvas.elements.remove(self.selected_element)
            self.selected_element = None
        except Exception as e:
            messagebox.showerror("錯誤", f"刪除元素失敗：{str(e)}")

    def edit_connection(self, canvas, event):
        selected_conn = None
        for conn in canvas.connections:
            x1, y1, x2, y2 = canvas.canvas.coords(conn[2])
            if abs(event.x - (x1 + x2) / 2) < 30 and abs(event.y - (y1 + y2) / 2) < 30:
                selected_conn = conn
                break
        if not selected_conn:
            return

        self.save_state(canvas)
        menu = tk.Menu(self.root, tearoff=0)
        #menu.title("連線操作")
        #menu.geometry(f"200x150+{event.x_root}+{event.y_root}")
        #menu.transient(self.root)
        #menu.grab_set()

        def edit_priority():
            priority_str = tk.simpledialog.askstring("輸入", "編輯連線優先級（整數，較低值優先）：", initialvalue=str(selected_conn[6]))
            try:
                priority = int(priority_str)
                conn_list = list(selected_conn)
                conn_list[6] = priority
                canvas.connections[canvas.connections.index(selected_conn)] = tuple(conn_list)
                canvas.canvas.itemconfig(selected_conn[3], text=f"Body({priority})")
                menu.destroy()
            except (ValueError, TypeError) as e:
                messagebox.showerror("錯誤", f"優先級必須為整數：{e}")
                menu.destroy()

        def delete_connection():
            try:
                canvas.canvas.delete(selected_conn[2])
                canvas.canvas.delete(selected_conn[3])
                canvas.connections.remove(selected_conn)
                menu.destroy()
            except Exception as e:
                messagebox.showerror("錯誤", f"刪除連線失敗：{e}")

        ttk.Button(menu, text="編輯優先級（僅 Body 連線）", command=edit_priority, state="normal" if selected_conn[4] == "Body" else "disabled").pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(menu, text="刪除連線", command=delete_connection).pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(menu, text="取消", command=menu.destroy).pack(fill=tk.X, padx=5, pady=5)

        #menu.protocol("WM_DELETE_WINDOW", menu.destroy)

    def start_connection(self, canvas, event):
        for element in canvas.elements:
            if abs(event.x - element["x"]) < 50 and abs(event.y - element["y"]) < 30:
                canvas.start_point = (element["x"], element["y"], element)
                break

    def draw_connection(self, canvas, event):
        if canvas.start_point:
            if canvas.temp_line:
                canvas.canvas.delete(canvas.temp_line)
            color = "#5E81AC" if self.connection_var.get() == "Body" else "#BF616A" if self.connection_var.get() == "Exit" else "#A3BE8C"
            canvas.temp_line = canvas.canvas.create_line(canvas.start_point[0], canvas.start_point[1], event.x, event.y, arrow=tk.LAST, fill=color)

    def end_connection(self, canvas, event):
        if canvas.start_point:
            for element in canvas.elements:
                if abs(event.x - element["x"]) < 50 and abs(event.y - element["y"]) < 30 and element != canvas.start_point[2]:
                    if self.connection_var.get() == "Call" and element["type"] != "Function":
                        messagebox.showerror("錯誤", "Call 連線必須指向函式元素")
                        break
                    if self.connection_var.get() == ["Body", "Exit"] and element["type"] == "Function":
                        messagebox.showerror("錯誤", "Body/Exit 連線不能指向函式元素")
                        break
                    color = "#5E81AC" if self.connection_var.get() == "Body" else "#BF616A" if self.connection_var.get() == "Exit" else "#A3BE8C"
                    call_params = ""
                    priority = 0
                    if self.connection_var.get() == "Body":
                        priority_str = simpledialog.askstring("輸入", "輸入連線優先級（整數，較低值優先）：", initialvalue="0")
                        try:
                            priority = int(priority_str)
                        except (ValueError, TypeError):
                            messagebox.showerror("錯誤", "優先級必須為整數")
                            break
                    if self.connection_var.get() == "Call":
                        call_params = simpledialog.askstring("Input", f"輸入 {element['function_name']} 的呼叫參數（例如：x, 5）：", initialvalue="")
                        if call_params is None:
                            break
                        valid, error_msg = self.validate_function_call(element["function_name"], call_params)
                        if not valid:
                            messagebox.showerror("錯誤", error_msg)
                            break
                    self.save_state(canvas)
                    try:
                        line_id = canvas.canvas.create_line(canvas.start_point[0], canvas.start_point[1], element["x"], element["y"], arrow=tk.LAST, fill=color, tags="connection")
                        label_id = canvas.canvas.create_text((canvas.start_point[0] + element["x"]) / 2, (canvas.start_point[1] + element["y"]) / 2, text=f"{self.connection_var.get()} ({priority})" if self.connection_var.get() == "Body" else self.connection_var.get(), font=("Arial", 8))
                        canvas.connections.append((canvas.start_point[2], element, line_id, label_id, self.connection_var.get(), call_params, priority))
                    except Exception as e:
                        messagebox.showerror("錯誤", f"連線失敗：{str(e)}")
                    break
            if canvas.temp_line:
                canvas.canvas.delete(canvas.temp_line)
            canvas.start_point = None
            canvas.temp_line = None

    def update_connections(self, canvas):
        updated_connections = []
        for conn in canvas.connections:
            try:
                start, end, old_line_id, old_label_id, conn_type, call_params, priority = conn
                canvas.canvas.delete(old_line_id)
                canvas.canvas.delete(old_label_id)
                color = "#5E81AC" if conn_type == "Body" else "#BF616A" if conn_type == "Exit" else "#A3BE8C"
                new_line_id = canvas.canvas.create_line(start["x"], start["y"], end["x"], end["y"], arrow=tk.LAST, fill=color, tags="connection")
                new_label_id = canvas.canvas.create_text((start["x"] + end["x"]) / 2, (start["y"] + end["y"]) / 2, text=f"{conn_type} ({priority})" if conn_type == "Body" else conn_type, font=("Arial", 8))
                updated_connections.append((start, end, new_line_id, new_label_id, conn_type, call_params, priority))
            except Exception as e:
                messagebox.showerror("警告", f"更新連線失敗：{str(e)}")
                continue
        canvas.connections = updated_connections

    def import_library(self):
        lib_dialog = tk.Toplevel(self.root)
        lib_dialog.title("匯入模組")
        lib_dialog.geometry("400x400")

        ttk.Label(lib_dialog, text="已匯入模組：").pack(pady=5)
        lib_tree = ttk.Treeview(lib_dialog, columns=("Name", "Type"), show="headings")
        lib_tree.heading("Name", text="模組名稱/路徑")
        lib_tree.heading("Type", text="類型")
        lib_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        for lib in self.libraries:
            lib_tree.insert("", tk.END, values=(lib, "標準/第三方庫"))
        for mod_name, path in self.custom_modules:
            lib_tree.insert("", tk.END, values=(mod_name, path))

        def import_file():
            file_path = filedialog.askopenfilename(filetypes=[("Python (.py)", "*.py")])
            if file_path:
                try:
                    module_name = os.path.splitext(os.path.basename(file_path))[0]
                    spec = importlib.util.spec_from_file_location(module_name, file_path)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    self.custom_modules.append((module_name, file_path))
                    lib_tree.insert("", tk.END, values=(module_name, file_path))
                    self.imported_names[module_name] = module_name
                    messagebox.showinfo("成功", f"Successfully imported module '{module_name}' from {file_path}")
                except Exception as e:
                    messagebox.showerror("錯誤", f"無法匯入檔案 '{file_path}'：{str(e)}")

        def import_folder():
            folder_path = filedialog.askdirectory()
            if folder_path:
                try:
                    sys.path.append(folder_path)
                    module_name = os.path.basename(folder_path)
                    module = importlib.import_module(module_name)
                    self.custom_modules.append((module_name, folder_path))
                    lib_tree.insert("", tk.END, values=(module_name, folder_path))
                    self.imported_names[module_name] = folder_path
                    messagebox.showinfo("成功", f"成功匯入資料夾 '{folder_path}' 作為模組 '{module_name}'")
                except Exception as e:
                    messagebox.showerror("錯誤", f"無法匯入資料夾 '{folder_path}'：{e}")

        def delete_module():
            selected = lib_tree.selection()
            if not selected:
                messagebox.showinfo("提示", "請選擇一個模組")
                return
            name = lib_tree.item(selected)["values"][0]
            if name in self.libraries:
                self.libraries.remove(name)
                lib_tree.delete(selected)
            else:
                for mod_name, path in self.custom_modules[:]:
                    if mod_name == name:
                        self.custom_modules.remove((mod_name, path))
                        lib_tree.delete(selected)
                        if mod_name in sys.modules:
                            del sys.modules[mod_name]
                        if path in sys.path:
                            sys.path.remove(path)
                        if mod_name in self.imported_names:
                            del self.imported_names[mod_name]
                        break

        ttk.Button(lib_dialog, text="匯入檔案 (.py)", command=import_file).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(lib_dialog, text="匯入資料夾", command=import_folder).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(lib_dialog, text="移除模組", command=delete_module).pack(side=tk.LEFT        , padx=5, pady=5)
        ttk.Button(lib_dialog, text="關閉", command=lib_dialog.destroy).pack(side=tk.LEFT, padx=5, pady=5)

        lib_dialog.protocol("WM_DELETE_WINDOW", lib_dialog.destroy)

    def save_flowchart(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON 檔案", "*.json"), ("Pickle 檔案", "*.pickle")],
            title="儲存流程圖"
        )
        if not file_path:
            return

        self.save_state(self.main_canvas)
        data = {
            "elements": [
                {
                    "id": e["id"],
                    "type": e["type"],
                    "x": e["x"],
                    "y": e["y"],
                    "code": e["code"],
                    "condition": e["condition"],
                    "loop_type": e["loop_type"],
                    "function_name": e["function_name"],
                    "function_params": e["function_params"],
                    "is_lambda": e.get("is_lambda"),
                    "return_value": e["return_value"],
                    "class_name": e.get("class_name"),
                    "parent_class": e.get("parent_class"),
                    "attributes": e.get("attributes"),
                    "methods": e.get("methods"),
                    "decorator": e.get("decorator"),
                    "subflowchart": {
                        "elements": [
                            {
                                "id": se["id"],
                                "type": se["type"],
                                "x": se["x"],
                                "y": se["y"],
                                "code": se["code"],
                                "condition": se["condition"],
                                "loop_type": se["loop_type"],
                                "function_name": se["function_name"],
                                "function_params": se["function_params"],
                                "is_lambda": se.get("is_lambda"),
                                "return_value": se["return_value"],
                                "class_name": se.get("class_name"),
                                "parent_class": se.get("parent_class"),
                                "attributes": se.get("attributes"),
                                "methods": se.get("methods"),
                                "decorator": se.get("decorator")
                            } for se in e["subflowchart"].elements
                        ],
                        "connections": [
                            (e["subflowchart"].elements.index(c[0]), e["subflowchart"].elements.index(c[1]), c[4], c[5], c[6])
                            for c in e["subflowchart"].connections
                        ]
                    } if e["subflowchart"] else None
                } for e in self.main_canvas.elements
            ],
            "connections": [
                (self.main_canvas.elements.index(c[0]), self.main_canvas.elements.index(c[1]), c[4], c[5], c[6])
                for c in self.main_canvas.connections
            ],
            "variables": self.variables,
            "libraries": self.libraries,
            "custom_modules": self.custom_modules
        }

        try:
            if file_path.endswith(".pickle"):
                with open(file_path, "wb") as f:
                    pickle.dump(data, f)
            else:
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("成功", f"流程圖已儲存至 {file_path}")
        except Exception as e:
            messagebox.showerror("錯誤", f"儲存失敗：{str(e)}")

    def load_flowchart(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON 檔案", "*.json"), ("Pickle 檔案", "*.pickle")],
            title="載入流程圖"
        )
        if not file_path:
            return

        if file_path.endswith(".pickle"):
            if not messagebox.askyesno("警告", "載入 .pickle 檔案可能包含不安全內容，是否繼續？"):
                return

        try:
            if file_path.endswith(".pickle"):
                with open(file_path, "rb") as f:
                    data = pickle.load(f)
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

            if not self.clear_canvas():
                return
            self.variables = data.get("variables", {})
            self.libraries = data.get("libraries", [])
            self.custom_modules = data.get("custom_modules", [])
            for var_name in self.variables:
                self.defined_variables.add(var_name)
            for lib in self.libraries:
                self.imported_names[lib] = lib
            for mod_name, path in self.custom_modules:
                self.imported_names[mod_name] = path
                if os.path.isdir(path):
                    if path not in sys.path:
                        sys.path.append(path)
                else:
                    spec = importlib.util.spec_from_file_location(mod_name, path)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[mod_name] = module
                    spec.loader.exec_module(module)

            for elem in data["elements"]:
                self.element_var.set(elem["type"])
                self.main_canvas.add_element(elem["type"], elem["x"], elem["y"], self)
                new_elem = self.main_canvas.elements[-1]
                new_elem["x"], new_elem["y"] = elem["x"], elem["y"]
                new_elem["code"] = elem["code"]
                new_elem["condition"] = elem["condition"]
                new_elem["loop_type"] = elem["loop_type"]
                new_elem["function_name"] = elem["function_name"]
                new_elem["function_params"] = elem["function_params"]
                new_elem["is_lambda"] = elem.get("is_lambda")
                new_elem["return_value"] = elem["return_value"]
                new_elem["class_name"] = elem.get("class_name")
                new_elem["parent_class"] = elem.get("parent_class")
                new_elem["attributes"] = elem.get("attributes")
                new_elem["methods"] = elem.get("methods", [])
                new_elem["decorator"] = elem.get("decorator")
                if elem["subflowchart"]:
                    new_elem["subflowchart"] = FlowchartCanvas(self.root, f"函式/方法：{elem.get('function_name') or elem.get('class_name') or '未命名'}", is_subflowchart=True, function_element=new_elem)
                    self.bind_canvas_events(new_elem["subflowchart"])
                    for sub_elem in elem["subflowchart"]["elements"]:
                        self.element_var.set(sub_elem["type"])
                        new_elem["subflowchart"].add_element(sub_elem["type"], sub_elem["x"], sub_elem["y"], self)
                        new_sub_elem = new_elem["subflowchart"].elements[-1]
                        new_sub_elem["x"], new_sub_elem["y"] = sub_elem["x"], sub_elem["y"]
                        new_sub_elem["code"] = sub_elem["code"]
                        new_sub_elem["condition"] = sub_elem.get("condition")
                        new_sub_elem["loop_type"] = sub_elem.get("loop_type")
                        new_sub_elem["function_name"] = sub_elem.get("function_name")
                        new_sub_elem["function_params"] = sub_elem.get("function_params")
                        new_sub_elem["is_lambda"] = sub_elem.get("is_lambda")
                        new_sub_elem["return_value"] = sub_elem.get("return_value")
                        new_sub_elem["class_name"] = sub_elem.get("class_name")
                        new_sub_elem["parent_class"] = sub_elem.get("parent_class")
                        new_sub_elem["attributes"] = sub_elem.get("attributes")
                        new_sub_elem["methods"] = sub_elem.get("methods", [])
                        new_sub_elem["decorator"] = sub_elem.get("decorator")
                        self.update_element_coords(new_sub_elem, new_elem["subflowchart"])
                        label_text = self.get_label_text(new_sub_elem)
                        new_elem["subflowchart"].canvas.itemconfig(new_sub_elem["label_id"], text=label_text[:20] + "..." if len(label_text) > 20 else label_text)
                    for sub_conn in elem["subflowchart"]["connections"]:
                        start_elem = new_elem["subflowchart"].elements[sub_conn[0]]
                        end_elem = new_elem["subflowchart"].elements[sub_conn[1]]
                        conn_type, call_params, priority = sub_conn[2], sub_conn[3], sub_conn[4]
                        color = "#5E81AC" if conn_type == "Body" else "#BF616A" if conn_type == "Exit" else "#A3BE8C"
                        line_id = new_elem["subflowchart"].canvas.create_line(start_elem["x"], start_elem["y"], end_elem["x"], end_elem["y"], arrow=tk.LAST, fill=color, tags="connection")
                        label_id = new_elem["subflowchart"].canvas.create_text((start_elem["x"] + end_elem["x"]) / 2, (start_elem["y"] + end_elem["y"]) / 2, text=f"{conn_type} ({priority})" if conn_type == "Body" else conn_type, font=("Arial", 8))
                        new_elem["subflowchart"].connections.append((start_elem, end_elem, line_id, label_id, conn_type, call_params, priority))
                self.update_element_coords(new_elem, self.main_canvas)
                label_text = self.get_label_text(new_elem)
                self.main_canvas.canvas.itemconfig(new_elem["label_id"], text=label_text[:20] + "..." if len(label_text) > 20 else label_text)

                if elem["type"] in ["Process", "Input"]:
                    self.update_defined_variables(elem["code"])
                elif elem["type"] == "Function" and elem["function_name"]:
                    param_count = len([p for p in elem["function_params"].split(",") if p.strip()])
                    self.function_signatures[elem["function_name"]] = param_count
                elif elem["type"] == "Class" and elem["class_name"]:
                    self.class_signatures[elem["class_name"]] = {
                        "attributes": elem.get("attributes") or {},
                        "methods": {m["name"]: len([p for p in m["params"].split(",") if p.strip()]) for m in elem.get("methods", [])}
                    }

            for conn in data["connections"]:
                start_elem = self.main_canvas.elements[conn[0]]
                end_elem = self.main_canvas.elements[conn[1]]
                conn_type, call_params, priority = conn[2], conn[3], conn[4]
                color = "#5E81AC" if conn_type == "Body" else "#BF616A" if conn_type == "Exit" else "#A3BE8C"
                line_id = self.main_canvas.canvas.create_line(start_elem["x"], start_elem["y"], end_elem["x"], end_elem["y"], arrow=tk.LAST, fill=color, tags="connection")
                label_id = self.main_canvas.canvas.create_text((start_elem["x"] + end_elem["x"]) / 2, (start_elem["y"] + end_elem["y"]) / 2, text=f"{conn_type} ({priority})" if conn_type == "Body" else conn_type, font=("Arial", 8))
                self.main_canvas.connections.append((start_elem, end_elem, line_id, label_id, conn_type, call_params, priority))

            messagebox.showinfo("成功", f"已載入流程圖 {file_path}")
        except Exception as e:
            messagebox.showerror("錯誤", f"載入失敗：{str(e)}")

    def show_help(self):
        help_window = tk.Toplevel(self.root)
        help_window.title("使用說明")
        help_window.geometry("600x400")

        help_text = tk.Text(help_window, wrap="word", font=("Arial", 10))
        help_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        help_content = """
流程圖轉程式碼工具使用說明：

1. **新增元素**：
   - 選擇元素類型（如 Process、Function、Class），點擊「新增元素」按鈕。
   - 右鍵元素可編輯或刪除。

2. **連線元素**：
   - 選擇連線類型（Body、Exit、Call），左鍵拖曳在元素間建立連線。
   - 右鍵連線可編輯優先級或刪除。

3. **語法糖支援**：
   - 在 Process 或 Input 元素編輯時，可選擇語法糖模板：
     - 列表推導式：例如 [x*2 for x in numbers]
     - 字典推導式：例如 {k: v**2 for k, v in dict.items()}
     - 裝飾器：例如 @timer
     - 上下文管理器：例如 with open('file.txt') as f
   - 模板自動填入程式碼框架，修改後儲存。

4. **匯入模組**：
   - 點擊「匯入模組」，選擇 .py 檔案或資料夾。
   - 支援標準庫（如 math）、第三方庫（如 numpy）及自訂模組。
   - 已匯入模組可移除。

5. **儲存與載入**：
   - 點擊「儲存流程圖」，選擇 .json 或 .pickle 格式。
   - 點擊「載入流程圖」，選擇現有檔案。
   - 注意：載入 .pickle 檔案可能有安全風險，請確認來源。

6. **變數管理**：
   - 點擊「變數管理」，新增、編輯或刪除全域變數。
   - 變數自動記錄至執行環境。

7. **執行程式碼**：
   - 點擊「產生程式碼」生成 Python 程式碼。
   - 點擊「執行程式碼」運行，結果顯示於輸出視窗。
   - 動畫高亮顯示執行流程，速度可調（慢、正常、快）。

8. **其他功能**：
   - 支援 Undo/Redo 操作。
   - 自動載入內建函式（如 print、len）。
   - 類別支援屬性、方法及子流程圖。
   - 錯誤提示提供詳細建議。
        """
        help_text.insert("1.0", help_content)
        help_text.config(state="disabled")

        ttk.Button(help_window, text="關閉", command=help_window.destroy).pack(pady=5)
        help_window.protocol("WM_DELETE_WINDOW", help_window.destroy)

    def generate_code(self):
        self.code_text.delete(1.0, tk.END)
        code = ""
        for lib in self.libraries:
            code += f"import {lib}\n"
        for mod_name, _ in self.custom_modules:
            code += f"import {mod_name}\n"

        for name, value in self.variables.items():
            code += f"{name} = {value}\n"
        code += "\n"

        def generate_class_code(element, indent_level=0):
            nonlocal code
            indent = "    " * indent_level
            parent_class = element["parent_class"] or "object"
            code += f"{indent}class {element['class_name']}({parent_class}):\n"
            indent_level += 1
            if element["attributes"]:
                code += f"{indent}def __init__(self):\n"
                indent_level += 1
                for attr_name, attr_value in element["attributes"].items():
                    code += f"{indent}self.{attr_name} = {attr_value}\n"
                indent_level += -1
            else:
                code += f"{indent}pass\n"

            for method in method["element"].get("methods", []):
                if method["is_lambda"]:
                    code += f"{indent}{method['name']} = lambda {method['params']}: {method['code']}\n"
                else:
                    code += f"{indent}def {method['name']}({method['params']}):\n"
                    indent_level += 1
                    if method["subflowchart"]:
                        def generate_subflowchart(canvas, indent_level):
                            nonlocal code, indent
                            indent = indent_level * "    " * indent_level
                            visited = set()

                            def traverse(elem, in_loop=False, loop_stack=None):
                                nonlocal code, indent_level
                                if not loop_stack:
                                    loop_stack.append(None)
                                if elem["id"] in visited:
                                    return
                                visited.add(elem["id"])

                                if elem["type"] == "Process":
                                    code += f"{indent}{elem['code'] or 'pass'}\n"
                                elif elem["type"] == "Input":
                                    code += f"{indent}{elem['code'] or input()}\n"
                                elif elem["type"] == "Output":
                                    print(f"{indent}{elem['code'] or 'output'}\n")
                                elif elem["type"] == "Comment":
                                    code += f"{indent}# {elem['code'] or 'comment'}\n"
                                elif elem["type"] == "Decision":
                                    code += f"{indent}if {elem['condition'] or 'condition'}:\n"
                                    indent_level += 1
                                    true_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == elem and conn[4] == "Body"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                                    for branch in branches:
                                        traverse(branch, in_loop, loop_stack)
                                    if not true_branches:
                                        code += f"{'    ' * indent_level}pass\n"
                                    indent_level += -1
                                    code += f"{indent}else:\n"
                                    indent_level += 1
                                    false_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == elem and conn[4] == "Exit"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                                    for branch in false_branches:
                                        traverse(branch, in_loop, loop_stack)
                                    if not false_branches:
                                        code += f"{'    ' * indent_level}pass\n"
                                    indent_level += -1
                                elif elem["type"] == "Loop":
                                    if elem["loop_type"] == "for":
                                        code += f"{indent}for {elem['condition'] or 'i' in range(5)}:\n"
                                    else:
                                        code += f"{indent}while {elem['condition'] or 'True'}:\n"
                                    indent_level += 1
                                    loop_stack.append(elem)
                                    body_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == elem and conn[4] == "Body"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                                    for branch in body_branches:
                                        traverse(branch, True, loop_stack)
                                    if not body_branches:
                                        code += f"{'    ' * indent_level}pass\n"
                                    indent_level += -1
                                    loop_stack.pop()
                                elif elem["type"] == "Start/End" and elem != canvas.elements[0]:
                                    if not in_loop:
                                        if elem["return_value"]:
                                            code += f"{indent}return {elem['return_value']}\n"
                                        else:
                                            code += f"{indent}\n"

                                    if not in_loop or (in_loop and elem["type"] not in ["Decision", "Loop"]):
                                        next_elements = sorted([conn[1] for conn in canvas.connections if conn[0] == elem and conn["4"] == "Body"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                                        for next_elem in next_elements:
                                            traverse(next_elem, in_loop, loop_stack)
                                        if in_loop and loop_stack and not next_elements:
                                            exit_elements = sorted([conn[1] for conn in canvas.connections if conn[0] == loop_stack[-1] and conn[4] == "Exit"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                                            for exit_elem in exit_elements:
                                                traverse(exit_elem, False, loop_stack)

                                        if canvas.elements:
                                            traverse(canvas.elements[0])
                                        else:
                                            code += f"{indent}    pass\n"
                                    generate_subflowchart(method["subflowchart"], indent_level=1)
                                else:
                                        code += f"{indent_level}    pass\n"
                            indent_level += -1
            code += "\n"

        def generate_function_code(element, indent_level=0):
            nonlocal code
            indent = "    " * indent_level
            if element["is_lambda"]:
                code += f"{indent}{element['function_name']} = lambda {element['function_params']}': {element['code']}\n"
            else:
                if element["decorator"]:
                    code += f"{indent}@{element['decorator']}\n"
                code += f"{indent}def {element['function_name']}({element['function_params']}):\n"
                indent_level += 1
                if element["subflowchart"]:
                    def generate_subflowchart(canvas, indent_level):
                        nonlocal code
                        indent = "    " * indent_level
                        visited = set()

                        def traverse(elem, in_loop=False, loop_stack=None):
                            nonlocal code
                            if not loop_stack:
                                loop_stack.append(None)
                            if elem["id"] in visited:
                                return
                            visited.add(elem["id"])

                            if elem["type"] == "Process":
                                code += f"{indent}{elem['code'] or 'pass'}\n"
                            elif elem["type"] == "Input":
                                code += f"{indent}{elem['code'] or 'input()'}\n"
                            elif elem["type"] == "Output":
                                code += f"{indent}print({elem['code'] or 'output'})\n"
                            elif elem["type"] == "Comment":
                                code += f"{indent}{elem['code'] or 'comment'}\n"
                            elif elem["type"] == "Decision":
                                code += f"{indent}if {elem['condition'] or 'condition'}:\n"
                                indent_level += 1
                                true_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == elem and conn[4] == "Body"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                                for branch in true_branches:
                                    traverse(branch, in_loop, loop_stack)
                                if not true_branches:
                                    code += f"{'    ' * indent_level}pass\n"
                                indent_level += -1
                                code += f"{indent}\nelse:"
                                indent_level += 1
                                false_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == elem and conn[4] == "Exit"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                                for branch in false_branches:
                                    traverse(branch, in_loop, loop_stack)
                                if not false_branches:
                                    code += f"{'    ' * indent_level}pass\n"
                                indent_level += -1
                            elif elem["type"] == "Loop":
                                if elem["loop_type"] == "for":
                                    code += f"{indent}for {elem['condition'] or 'i' in range(5)}:\n"
                                else:
                                    code += f"{indent}while {elem['condition'] or 'True'}:\n"
                                    indent_level += 1
                                    loop_stack.append(elem)
                                    body_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == elem and conn[4] == "Body"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                                    for branch in body_branches:
                                        traverse(branch, True, loop_stack)
                                    if not body_branches:
                                        code += f"{'    ' * indent_level}pass\n"
                                    indent_level += -1
                                    loop_stack.pop()
                            elif elem["type"] == "Start/End" and elem != canvas.elements[0]:
                                    if not in_loop:
                                        if elem["return_value"]:
                                            code += f"{indent}return {elem['return_value']}\n"
                                        else:
                                            code += f"{indent}\n"

                                    if not in_loop or (in_loop and elem["type"] not in ["Decision", "Loop"]):
                                        next_elements = sorted([conn[1] for conn in canvas.connections if conn[0] == elem and conn[4] == "Body"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                                    for next_elem in next_elements:
                                        traverse(next_elem, in_loop, loop_stack)
                                    if in_loop and loop_stack and not next_elements:
                                        exit_elements = sorted([conn[1] for conn in canvas.connections if conn[0] == loop_stack[-1] and conn[4] == "Exit"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                                        for exit_elem in exit_elements:
                                            traverse(exit_elem, False, loop_stack)

                                    if canvas.elements:
                                        traverse(canvas.elements[0])
                                    else:
                                        code += f"{indent}    pass\n"
                        generate_subflowchart(element["subflowchart"], indent_level=1)
                else:
                    code += f"{indent}    pass\n"
                    code += "\n"

        for element in self.main_canvas.elements:
            if element["type"] == "Class":
                generate_class_code(element)
        for element in self.main_canvas.elements:
            if element["type"] == "Function":
                generate_function_code(element)

        def generate_main_flow(canvas, indent_level=0):
            nonlocal code
            if not canvas.elements:
                return
            indent = indent_level * indent_level
            visited = set()
            def traverse(elem, in_loop=False, loop_stack=None):
                nonlocal code, indent_level
                if not loop_stack:
                    loop_stack.append(None)
                if elem["id"] in visited:
                    return
                visited.add(elem["id"]).append(elem["id"])

                if elem["type"] == "Process":
                    call_connections = [conn for conn in canvas.connections if conn[0] == elem and conn[4] == "Call"]
                    if call_connections:
                        for conn in call_connections:
                            target = conn[1]
                            if target["type"] == "Function":
                                params = conn["5"] or target["function_params"]
                                code += f"{indent}{elem['code'] or ''} = {target['function_name']}({params}))\n"
                            elif target["type"] == "Class":
                                method_call = conn["5"].get()
                                code += f"{indent}{elem['code']} or '' = {method_call}\n"
                    else:
                        code += f"{indent}{elem['code'] or 'pass'}\n"
                elif elem["type"] == "Input":
                    code += f"{indent}{elem['code'] or 'input()'}'\n"
                elif elem["type"] == "Output":
                    code += f"{indent}print({elem['code'] or 'output'})\n"
                elif elem["type"] == "Comment":
                    code += f"{indent}# {elem['code'] or 'comment'}\n"
                elif elem["type"] == "Decision":
                    code += f"{indent}if {elem['condition'] or 'condition'}:\n"
                    indent_level += 1
                    true_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == elem and conn[4] == "Body"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                    for branch in true_branches:
                        traverse(branch, in_loop, loop_stack)
                    if not true_branches:
                        code += f"{'    ' * indent_level}pass\n"
                    indent_level += -1
                    code += f"{indent}\nelse:"
                    indent_level += 1
                    false_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == elem and conn[4] == "Exit"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                    for branch in false_branches:
                        traverse(branch, in_loop, loop_stack)
                    if not false_branches:
                        code += f"{'    ' * indent_level}pass\n"
                    indent_level += -1
                elif elem["type"] == "Loop":
                    if elem["loop_type"] == "for":
                        code += str(f"{indent}for {elem['condition'] or 'i' in range(5)}:\n")
                    else:
                        code += f"{indent}while {elem['condition'] or 'True'}:\n"
                        indent_level += 1
                        loop_stack.append(elem)
                        body_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == elem and conn["4"] == "Body"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                        for branch in body_branches:
                            traverse(branch, True, loop_stack)
                        if not body_branches:
                            code += f"{'    ' * indent_level}'\npass\n"
                        indent_level += -1
                        loop_stack.pop()
                elif elem["type"] == "Start/End" and elem != canvas.elements[0]:
                        if not in_loop:
                            if elem["return_value"]:
                                code += f"{indent}print({elem['return_value']})\n"
                            else:
                                code += f"{indent}\n"

                        if not in_loop or (in_loop and elem["type"] not in ["Decision", "Loop"]):
                            next_elements = sorted([conn[1] for conn in canvas.connections if conn[0] == elem and conn[4] == "Body"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                            for next_elem in next_elements:
                                traverse(next_elem, in_loop, loop_stack)
                            if in_loop and loop_stack and not next_elements:
                                exit_elements = sorted([conn[1] for conn in canvas.connections if conn["0"] == loop_stack["[-1]"] and conn["4"] == "Exit"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                                for exit_elem in exit_elements:
                                    traverse(exit_elem, False, loop_stack)

                        if canvas.elements:
                            traverse(canvas.elements[0])
                            canvas.get_elements()[0]

        code += "def main():\n"
        generate_main_flow(self.main_canvas, indent_level=1)
        code += "\n\nif __name__ == '__main__'"
        code += '\n    main()'

        self.code_text.insert(tk.END, code)
        messagebox.showinfo("成功", "程式碼已生成，請檢查程式碼視窗。")

    def run_code(self):
        self.output_text.config(state="normal")
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert("1.0", "執行中...\n")
        self.output_text.config(state="disabled")
        self.root.update()

        code = self.code_text.get("1.0", tk.END).strip()
        if not code:
            self.output_text.config(state="normal")
            self.output_text.delete("1.0", tk.END)
            self.output_text.insert("1.0", "錯誤：無程式碼可執行\n")
            self.output_text.config(state="disabled")
            return

        self.execution_globals = {}
        for name in dir(builtins):
            self.execution_globals[name] = getattr(builtins, name)
        for lib in self.libraries:
            try:
                self.execution_globals[lib] = __import__(lib)
            except ImportError as e:
                messagebox.showerror("錯誤", f"無法載入模組 {lib}：{str(e)}")
                return
        for mod_name, path in self.custom_modules:
            try:
                if os.path.isdir(path):
                    module = importlib.import_module(mod_name)
                else:
                    spec = importlib.util.spec_from_file_location(mod_name, path)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[mod_name] = module
                    spec.loader.exec_module(module)
                self.execution_globals[mod_name] = module
            except Exception as e:
                messagebox.showerror("錯誤", f"無法載入自訂模組 {mod_name}：{str(e)}")
                return
        self.execution_globals.update(self.variables)

        sys.stdout = io.StringIO()
        highlight_duration, error_duration = self.get_animation_duration()
        visited_elements = set()
        visited_connections = set()

        def highlight_and_execute(canvas, elem, in_loop=False, loop_stack=None):
            if not loop_stack:
                loop_stack = []
            if elem["id"] in visited_elements:
                return
            visited_elements.add(elem["id"])

            if elem["type"] not in ["Start/End"]:
                canvas.highlight_element(elem, duration=highlight_duration)

            try:
                if elem["type"] == "Process":
                    call_connections = [conn for conn in canvas.connections if conn[0] == elem and conn[4] == "Call"]
                    if call_connections:
                        for conn in call_connections:
                            if conn not in visited_connections:
                                canvas.highlight_connection(conn, duration=highlight_duration)
                                visited_connections.add(conn)
                            target = conn[1]
                            if target["type"] == "Function":
                                if target["subflowchart"]:
                                    highlight_and_execute(target["subflowchart"], target["subflowchart"].elements[0])
                            elif target["type"] == "Class":
                                method_call = conn[5]
                                if '.' in method_call:
                                    method_name = method_call.split('.')[1].split('(')[0]
                                    for method in target["methods"]:
                                        if method["name"] == method_name and method["subflowchart"]:
                                            highlight_and_execute(method["subflowchart"], method["subflowchart"].elements[0])
                    else:
                        valid, error_msg = self.validate_code(elem["code"], element=elem, canvas=canvas)
                        if not valid:
                            canvas.highlight_error(elem, duration=error_duration)
                            raise SyntaxError(error_msg)
                        exec(elem["code"], self.execution_globals)
                elif elem["type"] == "Input":
                    valid, error_msg = self.validate_code(elem["code"], is_condition=False, element=elem, canvas=canvas)
                    if not valid:
                        canvas.highlight_error(elem, duration=error_duration)
                        raise SyntaxError(error_msg)
                    result = eval(elem["code"], self.execution_globals)
                    self.execution_globals[elem["code"].split("=")[0].strip()] = result
                elif elem["type"] == "Output":
                    valid, error_msg = self.validate_code(elem["code"], element=elem, canvas=canvas)
                    if not valid:
                        canvas.highlight_error(elem, duration=error_duration)
                        raise SyntaxError(error_msg)
                    print(eval(elem["code"], self.execution_globals))
                elif elem["type"] == "Decision":
                    valid, error_msg = self.validate_code(elem["condition"], is_condition=True, element=elem, canvas=canvas)
                    if not valid:
                        canvas.highlight_error(elem, duration=error_duration)
                        raise SyntaxError(error_msg)
                    condition_result = eval(elem["condition"], self.execution_globals)
                    branches = sorted([conn for conn in canvas.connections if conn[0] == elem and conn[4] == ("Body" if condition_result else "Exit")], key=lambda c: c[6])
                    for conn in branches:
                        if conn not in visited_connections:
                            canvas.highlight_connection(conn, duration=highlight_duration)
                            visited_connections.add(conn)
                        highlight_and_execute(canvas, conn[1], in_loop, loop_stack)
                    return
                elif elem["type"] == "Loop":
                    valid, error_msg = self.validate_code(elem["condition"], is_condition=True, element=elem, canvas=canvas)
                    if not valid:
                        canvas.highlight_error(elem, duration=error_duration)
                        raise SyntaxError(error_msg)
                    loop_stack.append(elem)
                    if elem["loop_type"] == "for":
                        if " in " not in elem["condition"]:
                            canvas.highlight_error(elem, duration=error_duration)
                            raise SyntaxError("For 迴圈條件需包含 'in' 關鍵字，例如 'i in range(5)'")
                        try:
                            condition_parts = elem["condition"].split(" in ")
                            var_name = condition_parts[0].strip()
                            iter_expr = condition_parts[1]
                            iter_obj = eval(f"iter({iter_expr})", self.execution_globals)
                        except Exception as e:
                            canvas.highlight_error(elem, duration=error_duration)
                            raise SyntaxError(f"Invalid for loop condition: {str(e)}")
                        for val in iter_obj:
                            self.execution_globals[var_name] = val
                            body_branches = sorted([conn for conn in canvas.connections if conn[0] == elem and conn[4] == "Body"], key=lambda c: c[6])
                            for conn in body_branches:
                                if conn not in visited_connections:
                                    canvas.highlight_connection(conn, duration=highlight_duration)
                                    visited_connections.add(conn)
                                highlight_and_execute(canvas, conn[1], True, loop_stack)
                    else:  # while loop
                        while eval(elem["condition"], self.execution_globals):
                            body_branches = sorted([conn for conn in canvas.connections if conn[0] == elem and conn[4] == "Body"], key=lambda c: c[6])
                            for conn in body_branches:
                                if conn not in visited_connections:
                                    canvas.highlight_connection(conn, duration=highlight_duration)
                                    visited_connections.add(conn)
                                highlight_and_execute(canvas, conn[1], True, loop_stack)
                    loop_stack.pop()
                elif elem["type"] == "Start/End" and elem != canvas.elements[0]:
                    if not in_loop:
                        if elem["return_value"]:
                            valid, error_msg = self.validate_code(elem["return_value"], element=elem, canvas=canvas)
                            if not valid:
                                canvas.highlight_error(elem, duration=error_duration)
                                raise SyntaxError(error_msg)
                            result = eval(elem["return_value"], self.execution_globals)
                            print(result)

                if not in_loop or (in_loop and elem["type"] not in ["Decision", "Loop"]):
                    next_elements = sorted([conn for conn in canvas.connections if conn[0] == elem and conn[4] == "Body"], key=lambda c: c[6])
                    for conn in next_elements:
                        if conn not in visited_connections:
                            canvas.highlight_connection(conn, duration=highlight_duration)
                            visited_connections.add(conn)
                        highlight_and_execute(canvas, conn[1], in_loop, loop_stack)
                    if in_loop and loop_stack and not next_elements:
                        exit_elements = sorted([conn for conn in canvas.connections if conn[0] == loop_stack[-1] and conn[4] == "Exit"], key=lambda c: c[6])
                        for conn in exit_elements:
                            if conn not in visited_connections:
                                canvas.highlight_connection(conn, duration=highlight_duration)
                                visited_connections.add(conn)
                            highlight_and_execute(canvas, conn[1], False, loop_stack)

            except Exception as e:
                canvas.highlight_error(elem, duration=error_duration)
                error_msg = traceback.format_exc()
                self.output_text.config(state="normal")
                self.output_text.delete("1.0", tk.END)
                self.output_text.insert("1.0", f"執行錯誤：\n{error_msg}\n")
                self.output_text.config(state="disabled")
                sys.stdout = sys.__stdout__
                return

            try:
                exec(code, self.execution_globals)
                if self.main_canvas.elements:
                    highlight_and_execute(self.main_canvas, self.main_canvas.elements[0])
                output = sys.stdout.getvalue()
                self.output_text.config(state="normal")
                self.output_text.delete("1.0", tk.END)
                self.output_text.insert("1.0", output or "執行完成，無輸出。\n")
                self.output_text.insert(tk.END, "已自動載入內建函式 print、len 等。\n")
                self.output_text.config(state="disabled")
            except Exception as e:
                error_msg = traceback.format_exc()
                self.output_text.config(state="normal")
                self.output_text.delete("1.0", tk.END)
                self.output_text.insert("1.0", f"執行錯誤：\n{error_msg}\n")
                self.output_text.config(state="disabled")
            finally:
                sys.stdout = sys.__stdout__


    def clear_canvas(self):
        if messagebox.askyesno("確認", "確定要清除畫布？所有元素和連線將被刪除。"):
            self.save_state(self.main_canvas)
            self.main_canvas.canvas.delete("all")
            self.main_canvas.elements = []
            self.main_canvas.connections.clear()
            self.defined_variables.clear()
            self.function_signatures.clear()
            self.class_signatures.clear()
            self.imported_names.clear()
            self.libraries.clear()
            self.custom_modules.clear()
            self.code_text.delete("1.0", tk.END)
            self.output_text.config(state="normal")
            self.output_text.delete(1.0, tk.END)
            self.output_text.config(state="disabled")
            return True
        return False

if __name__ == "__main__":
    root = tk.Tk()
    app = FlowchartToCodeGUI(root)
    root.mainloop()

