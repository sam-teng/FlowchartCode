import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, Text, PanedWindow
import json
import os
import ast
import re
import sys
import io
from collections import deque
import time
import traceback
import uuid
import builtins

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
            "methods": [] if element_type == "Class" else None
        }
        self.elements.append(element)

        self.canvas.tag_bind(canvas_id, "<B1-Motion>", lambda event, eid=element_id: main_gui.move_element(self, event, eid))
        self.canvas.tag_bind(label_id, "<B1-Motion>", lambda event, eid=element_id: main_gui.move_element(self, event, eid))
        self.canvas.tag_bind(canvas_id, "<Button-3>", lambda event: main_gui.edit_element(self, event))
        self.canvas.tag_bind(label_id, "<Button-3>", lambda event: main_gui.edit_element(self, event))

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
        ttk.Button(self.toolbar, text="匯入程式庫", command=self.import_library).pack(side=tk.LEFT, padx=2)

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

    def bind_canvas_events(self, canvas):
        canvas.canvas.bind("<Button-1>", lambda event: self.start_connection(canvas, event))
        canvas.canvas.bind("<B1-Motion>", lambda event: self.draw_connection(canvas, event))
        canvas.canvas.bind("<ButtonRelease-1>", lambda event: self.end_connection(canvas, event))
        canvas.canvas.bind("<Button-3>", lambda event: self.edit_connection(canvas, event))

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
            if element.get("is_lambda"):
                return f"lambda {element['function_params']}: {element['code']}"
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
        except:
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
            return False, f"語法錯誤：{str(e)}。請檢查語法是否正確。"

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
                            for cls_name, cls_info in self.class_signatures.items():
                                if attr_name not in cls_info["attributes"] and attr_name not in cls_info["methods"]:
                                    undefined_vars.add(f"{obj_name}.{attr_name}")
            if undefined_vars:
                return False, f"未定義變數或方法：{', '.join(undefined_vars)}。請在變數管理、類別定義或程式碼中宣告。"
        except:
            pass

        if not is_lambda:
            valid_operators = r'[\+\-\*/%=<>&|\^~!]=?|==|!=|<=|>=|and|or|not'
            if not re.search(valid_operators, code) and (is_condition or element["type"] in ["Process", "Decision", "Loop"]):
                return False, f"缺少有效運算子。建議使用：{', '.join(['+', '-', '*', '/', '==', '!=', '<', '>', 'and', 'or', 'not'])}"

        if element and element["type"] == "Input":
            if "int(" not in code and "float(" not in code and "str(" not in code and "input(" not in code:
                return False, "輸入元素應包含類型轉換或 input()（例如 int(input())）。"

        import_match = re.match(r'from\s+(\w+)\s+import\s+([\w\s,]+)', code)
        if import_match:
            module = import_match.group(1)
            names = [n.strip() for n in import_match.group(2).split(',')]
            try:
                __import__(module)
            except ImportError:
                return False, f"模組 '{module}' 不存在。請確認模組名稱或安裝（例如 pip install {module}）。"
            for name in names:
                self.imported_names[name] = (module, name)

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
        var_window.geometry("400x300")

        ttk.Label(var_window, text="變數名稱 | 初始值").pack(pady=5)
        tree = ttk.Treeview(var_window, columns=("Name", "Value"), show="headings")
        tree.heading("Name", text="變數名稱")
        tree.heading("Value", text="初始值")
        tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        for name, value in self.variables.items():
            tree.insert("", tk.END, values=(name, value))

        def add_variable():
            name = simpledialog.askstring("輸入", "輸入變數名稱：")
            if not name or not name.isidentifier():
                messagebox.showerror("錯誤", "變數名稱無效，必須是有效的 Python 識別字。")
                return
            value = simpledialog.askstring("輸入", f"輸入 {name} 的初始值（例如：10, 'text', True）：")
            try:
                eval(value)
                self.variables[name] = value
                self.defined_variables.add(name)
                tree.insert("", tk.END, values=(name, value))
            except:
                messagebox.showerror("錯誤", "初始值無效，必須是有效的 Python 表達式。")

        def edit_variable():
            selected = tree.selection()
            if not selected:
                messagebox.showinfo("提示", "請選擇一個變數")
                return
            name, value = tree.item(selected)["values"]
            new_value = simpledialog.askstring("輸入", f"編輯 {name} 的初始值：", initialvalue=value)
            try:
                eval(new_value)
                self.variables[name] = new_value
                tree.item(selected, values=(name, new_value))
            except:
                messagebox.showerror("錯誤", "初始值無效，必須是有效的 Python 表達式。")

        def delete_variable():
            selected = tree.selection()
            if not selected:
                messagebox.showinfo("提示", "請選擇一個變數")
                return
            name = tree.item(selected)["values"][0]
            del self.variables[name]
            self.defined_variables.discard(name)
            tree.delete(selected)

        ttk.Button(var_window, text="新增變數", command=add_variable).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(var_window, text="編輯變數", command=edit_variable).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(var_window, text="刪除變數", command=delete_variable).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(var_window, text="關閉", command=var_window.destroy).pack(side=tk.LEFT, padx=5, pady=5)

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
            if abs(event.x - element["x"]) < 60 and abs(event.y - element["y"]) < 40:
                self.selected_element = element
                break
        else:
            return

        if self.selected_element == canvas.elements[0]:
            messagebox.showinfo("提示", "無法編輯或刪除 Start 元素")
            return

        self.save_state(canvas)
        menu = tk.Toplevel(self.root)
        menu.title("元素操作")
        menu.geometry(f"200x150+{event.x_root}+{event.y_root}")
        menu.transient(self.root)
        menu.grab_set()

        def edit_action():
            menu.destroy()
            if self.selected_element["type"] in ["Process", "Input", "Output", "Comment"]:
                code = simpledialog.askstring("輸入", f"輸入 {self.selected_element['type'].lower()} 程式碼：", initialvalue=self.selected_element["code"])
                if code:
                    valid, error_msg = self.validate_code(code, element=self.selected_element, canvas=canvas)
                    if valid:
                        self.selected_element["code"] = code
                        canvas.canvas.itemconfig(self.selected_element["label_id"], text=code[:20] + "..." if len(code) > 20 else code)
                        self.update_defined_variables(code)
                    else:
                        messagebox.showerror("錯誤", error_msg)
            elif self.selected_element["type"] in ["Decision", "Loop"]:
                condition = simpledialog.askstring("輸入", f"輸入 {self.selected_element['type'].lower()} 條件：", initialvalue=self.selected_element["condition"])
                if condition:
                    valid, error_msg = self.validate_code(condition, is_condition=True, element=self.selected_element, canvas=canvas)
                    if valid:
                        self.selected_element["condition"] = condition
                        canvas.canvas.itemconfig(self.selected_element["label_id"], text=condition[:20] + "..." if len(condition) > 20 else condition)
                    else:
                        messagebox.showerror("錯誤", error_msg)
                if self.selected_element["type"] == "Loop":
                    loop_type = simpledialog.askstring("輸入", "輸入迴圈類型 (for/while)：", initialvalue=self.selected_element["loop_type"])
                    if loop_type in ["for", "while"]:
                        self.selected_element["loop_type"] = loop_type
            elif self.selected_element["type"] == "Function":
                func_dialog = tk.Toplevel(self.root)
                func_dialog.title("編輯函式")
                func_dialog.geometry("400x400")

                tk.Label(func_dialog, text="函式名稱：").pack(pady=5)
                name_entry = tk.Entry(func_dialog)
                name_entry.insert(0, self.selected_element["function_name"])
                name_entry.pack(pady=5)

                tk.Label(func_dialog, text="參數（例如：x, y）：").pack(pady=5)
                params_entry = tk.Entry(func_dialog)
                params_entry.insert(0, self.selected_element["function_params"])
                params_entry.pack(pady=5)

                is_lambda_var = tk.BooleanVar(value=self.selected_element.get("is_lambda", False))
                tk.Checkbutton(func_dialog, text="使用 Lambda 函式", variable=is_lambda_var).pack(pady=5)

                lambda_code_entry = tk.Entry(func_dialog)
                lambda_code_entry.pack(pady=5)
                if is_lambda_var.get():
                    lambda_code_entry.insert(0, self.selected_element["code"])

                def toggle_lambda_fields():
                    if is_lambda_var.get():
                        name_entry.config(state="disabled")
                        lambda_code_entry.config(state="normal")
                    else:
                        name_entry.config(state="normal")
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
                        valid, error_msg = self.validate_code(f"{params}: {code}", is_lambda=True)
                        if not valid:
                            messagebox.showerror("錯誤", error_msg)
                            return
                        self.selected_element["function_name"] = ""
                        self.selected_element["function_params"] = params
                        self.selected_element["code"] = code
                        self.selected_element["is_lambda"] = True
                        self.selected_element["subflowchart"] = None
                    else:
                        name = name_entry.get()
                        params = params_entry.get()
                        if not name.isidentifier():
                            messagebox.showerror("錯誤", "函式名稱無效，必須是有效的 Python 識別字。")
                            return
                        if self.selected_element["function_name"] in self.function_signatures:
                            del self.function_signatures[self.selected_element["function_name"]]
                        self.selected_element["function_name"] = name
                        self.selected_element["function_params"] = params
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

                # Basic Info
                tk.Label(basic_frame, text="類別名稱：").pack(pady=5)
                class_name_entry = tk.Entry(basic_frame)
                class_name_entry.insert(0, self.selected_element["class_name"])
                class_name_entry.pack(pady=5)

                tk.Label(basic_frame, text="父類別（可選，例如 object）：").pack(pady=5)
                parent_class_entry = tk.Entry(basic_frame)
                parent_class_entry.insert(0, self.selected_element["parent_class"])
                parent_class_entry.pack(pady=5)

                # Attributes
                ttk.Label(attr_frame, text="屬性名稱 | 初始值").pack(pady=5)
                attr_tree = ttk.Treeview(attr_frame, columns=("Name", "Value"), show="headings")
                attr_tree.heading("Name", text="屬性名稱")
                attr_tree.heading("Value", text="初始值")
                attr_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

                for name, value in (self.selected_element["attributes"] or {}).items():
                    attr_tree.insert("", tk.END, values=(name, value))

                def add_attribute():
                    name = simpledialog.askstring("輸入", "輸入屬性名稱：")
                    if not name or not name.isidentifier():
                        messagebox.showerror("錯誤", "屬性名稱無效，必須是有效的 Python 識別字。")
                        return
                    value = simpledialog.askstring("輸入", f"輸入 {name} 的初始值：")
                    try:
                        eval(value)
                        self.selected_element["attributes"][name] = value
                        attr_tree.insert("", tk.END, values=(name, value))
                    except:
                        messagebox.showerror("錯誤", "初始值無效，必須是有效的 Python 表達式。")

                def edit_attribute():
                    selected = attr_tree.selection()
                    if not selected:
                        messagebox.showinfo("提示", "請選擇一個屬性")
                        return
                    name, value = attr_tree.item(selected)["values"]
                    new_value = simpledialog.askstring("輸入", f"編輯 {name} 的初始值：", initialvalue=value)
                    try:
                        eval(new_value)
                        self.selected_element["attributes"][name] = new_value
                        attr_tree.item(selected, values=(name, new_value))
                    except:
                        messagebox.showerror("錯誤", "初始值無效，必須是有效的 Python 表達式。")

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

                # Methods
                ttk.Label(method_frame, text="方法名稱 | 參數 | Lambda").pack(pady=5)
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
                    method_name_entry = tk.Entry(method_dialog)
                    method_name_entry.pack(pady=5)

                    tk.Label(method_dialog, text="參數（例如：self, x）：").pack(pady=5)
                    method_params_entry = tk.Entry(method_dialog)
                    method_params_entry.insert(0, "self")
                    method_params_entry.pack(pady=5)

                    is_lambda_var = tk.BooleanVar()
                    tk.Checkbutton(method_dialog, text="使用 Lambda 函式", variable=is_lambda_var).pack(pady=5)

                    lambda_code_entry = tk.Entry(method_dialog)
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
                            valid, error_msg = self.validate_code(f"{params}: {code}", is_lambda=True)
                            if not valid:
                                messagebox.showerror("錯誤", error_msg)
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
                    method_name_entry = tk.Entry(method_dialog)
                    method_name_entry.insert(0, name)
                    method_name_entry.pack(pady=5)

                    tk.Label(method_dialog, text="參數（例如：self, x）：").pack(pady=5)
                    method_params_entry = tk.Entry(method_dialog)
                    method_params_entry.insert(0, params)
                    method_params_entry.pack(pady=5)

                    is_lambda_var = tk.BooleanVar(value=is_lambda == "是")
                    tk.Checkbutton(method_dialog, text="使用 Lambda 函式", variable=is_lambda_var).pack(pady=5)

                    lambda_code_entry = tk.Entry(method_dialog)
                    lambda_code_entry.insert(0, method["code"] if method["is_lambda"] else "")
                    lambda_code_entry.pack(pady=5)
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
                            valid, error_msg = self.validate_code(f"{new_params}: {code}", is_lambda=True)
                            if not valid:
                                messagebox.showerror("錯誤", error_msg)
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
                return_value = simpledialog.askstring("輸入", "輸入回傳值（例如：result）：", initialvalue=self.selected_element["return_value"])
                if return_value:
                    valid, error_msg = self.validate_code(return_value, canvas=canvas)
                    if valid:
                        self.selected_element["return_value"] = return_value
                        canvas.canvas.itemconfig(self.selected_element["label_id"], text=f"Return: {return_value}"[:20] + "..." if len(return_value) > 20 else f"Return: {return_value}")
                    else:
                        messagebox.showerror("錯誤", error_msg)

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
                    except:
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
        menu = tk.Toplevel(self.root)
        menu.title("連線操作")
        menu.geometry(f"200x150+{event.x_root}+{event.y_root}")
        menu.transient(self.root)
        menu.grab_set()

        def edit_priority():
            priority_str = simpledialog.askstring("輸入", "編輯連線優先級（整數，較低值優先）：", initialvalue=str(selected_conn[6]))
            try:
                priority = int(priority_str)
                conn_list = list(selected_conn)
                conn_list[6] = priority
                canvas.connections[canvas.connections.index(selected_conn)] = tuple(conn_list)
                canvas.canvas.itemconfig(selected_conn[3], text=f"Body ({priority})")
                menu.destroy()
            except (ValueError, TypeError):
                messagebox.showerror("錯誤", "優先級必須為整數")
                menu.destroy()

        def delete_connection():
            canvas.canvas.delete(selected_conn[2])
            canvas.canvas.delete(selected_conn[3])
            canvas.connections.remove(selected_conn)
            menu.destroy()

        ttk.Button(menu, text="編輯優先級（僅 Body 連線）", command=edit_priority, state="normal" if selected_conn[4] == "Body" else "disabled").pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(menu, text="刪除連線", command=delete_connection).pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(menu, text="取消", command=menu.destroy).pack(fill=tk.X, padx=5, pady=5)

        menu.protocol("WM_DELETE_WINDOW", menu.destroy)

    def import_library(self):
        library = simpledialog.askstring("輸入", "輸入要匯入的函式庫（例如：math, numpy as np）：")
        if library and library not in self.libraries:
            try:
                if ' as ' in library:
                    module, alias = library.split(' as ')
                    __import__(module.strip())
                    self.libraries.append(library)
                else:
                    __import__(library.strip())
                    self.libraries.append(library)
                messagebox.showinfo("成功", f"已新增函式庫 '{library}'")
            except ImportError:
                messagebox.showerror("錯誤", f"無法匯入 '{library}'，請確認模組存在或安裝（例如 pip install {library.split()[0]}）。")

    def start_connection(self, canvas, event):
        for element in canvas.elements:
            if abs(event.x - element["x"]) < 60 and abs(event.y - element["y"]) < 40:
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
                if abs(event.x - element["x"]) < 60 and abs(event.y - element["y"]) < 40 and element != canvas.start_point[2]:
                    if self.connection_var.get() == "Call" and element["type"] not in ["Function", "Class"]:
                        messagebox.showerror("錯誤", "Call 連線必須指向函式或類別元素")
                        break
                    if self.connection_var.get() in ["Body", "Exit"] and element["type"] in ["Function", "Class"]:
                        messagebox.showerror("錯誤", "Body/Exit 連線不能指向函式或類別元素")
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
                        call_params = simpledialog.askstring("輸入", f"輸入 {'方法' if element['type'] == 'Class' else '函式'} 呼叫參數（例如：x, 5）：", initialvalue="")
                        if call_params is None:
                            break
                        if element["type"] == "Function":
                            valid, error_msg = self.validate_function_call(element["function_name"], call_params)
                        else:
                            method_name = call_params.split('.')[1].split('(')[0] if '.' in call_params else ""
                            params = call_params.split('(')[1].rstrip(')') if '(' in call_params else call_params
                            valid, error_msg = self.validate_method_call(element["class_name"], method_name, params)
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
                messagebox.showerror("錯誤", f"更新連線失敗：{str(e)}")
                continue
        canvas.connections = updated_connections

    def generate_code(self):
        self.code_text.delete(1.0, tk.END)
        code = "# 自動生成的 Python 程式碼\n\n"

        imports = set(self.libraries)
        for element in self.main_canvas.elements:
            if element["type"] in ["Process", "Input", "Output"]:
                import_match = re.match(r'from\s+(\w+)\s+import\s+([\w\s,]+)', element["code"])
                if import_match:
                    module = import_match.group(1)
                    names = import_match.group(2)
                    imports.add(f"from {module} import {names}")
        for lib in sorted(imports):
            code += f"{lib}\n"
        if imports:
            code += "\n"

        for name, value in self.variables.items():
            code += f"{name} = {value}\n"
        if self.variables:
            code += "\n"

        def generate_class_code(element, indent_level=0):
            nonlocal code
            if element["type"] != "Class" or not element["class_name"]:
                return
            indent = "    " * indent_level
            parent = f"({element['parent_class']})" if element["parent_class"] else ""
            code += f"{indent}class {element['class_name']}{parent}:\n"
            indent_level += 1
            indent = "    " * indent_level

            if element["attributes"]:
                code += f"{indent}def __init__(self):\n"
                indent_level += 1
                indent = "    " * indent_level
                for attr_name, attr_value in element["attributes"].items():
                    code += f"{indent}self.{attr_name} = {attr_value}\n"
                indent_level -= 1
                indent = "    " * indent_level
                code += "\n"

            for method in element["methods"]:
                if method["is_lambda"]:
                    code += f"{indent}{method['name']} = lambda {method['params']}: {method['code']}\n"
                else:
                    code += f"{indent}def {method['name']}({method['params'] or 'self'}):\n"
                    if method["subflowchart"]:
                        indent_level += 1
                        visited = set()
                        def traverse(canvas, elem, in_loop=False, loop_stack=None):
                            nonlocal code, indent_level
                            if loop_stack is None:
                                loop_stack = []
                            if elem["id"] in visited:
                                return
                            visited.add(elem["id"])

                            indent = "    " * indent_level
                            if elem["type"] == "Process":
                                call_connections = [conn for conn in canvas.connections if conn[0] == elem and conn[4] == "Call"]
                                if call_connections:
                                    for conn in call_connections:
                                        target = conn[1]
                                        if target["type"] == "Function":
                                            params = conn[5] or target["function_params"]
                                            code += f"{indent}{elem['code'] or ''} = {target['function_name']}({params})\n"
                                        elif target["type"] == "Class":
                                            method_name = conn[5].split('.')[1].split('(')[0] if '.' in conn[5] else ""
                                            params = conn[5].split('(')[1].rstrip(')') if '(' in conn[5] else conn[5]
                                            code += f"{indent}{elem['code'] or ''} = self.{method_name}({params})\n"
                                else:
                                    code += f"{indent}{elem['code'] or 'pass'}\n"
                            elif elem["type"] == "Input":
                                code += f"{indent}{elem['code'] or 'input()'}\n"
                            elif elem["type"] == "Output":
                                code += f"{indent}print({elem['code'] or 'output'})\n"
                            elif elem["type"] == "Comment":
                                code += f"{indent}# {elem['code'] or 'comment'}\n"
                            elif elem["type"] == "Decision":
                                code += f"{indent}if {elem['condition'] or 'condition'}:\n"
                                indent_level += 1
                                true_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == elem and conn[4] == "Body"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                                for branch in true_branches:
                                    traverse(canvas, branch, in_loop, loop_stack)
                                if not true_branches:
                                    code += f"{'    ' * indent_level}pass\n"
                                indent_level -= 1
                                code += f"{indent}else:\n"
                                indent_level += 1
                                false_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == elem and conn[4] == "Exit"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                                for branch in false_branches:
                                    traverse(canvas, branch, in_loop, loop_stack)
                                if not false_branches:
                                    code += f"{'    ' * indent_level}pass\n"
                                indent_level -= 1
                            elif elem["type"] == "Loop":
                                if elem["loop_type"] == "for":
                                    code += f"{indent}for {elem['condition'] or 'i in range(5)'}:\n"
                                else:
                                    code += f"{indent}while {elem['condition'] or 'True'}:\n"
                                indent_level += 1
                                loop_stack.append(elem)
                                body_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == elem and conn[4] == "Body"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                                for branch in body_branches:
                                    traverse(canvas, branch, True, loop_stack)
                                if not body_branches:
                                    code += f"{'    ' * indent_level}pass\n"
                                indent_level -= 1
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
                                    traverse(canvas, next_elem, in_loop, loop_stack)
                                if in_loop and loop_stack and not next_elements:
                                    exit_elements = sorted([conn[1] for conn in canvas.connections if conn[0] == loop_stack[-1] and conn[4] == "Exit"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                                    for exit_elem in exit_elements:
                                        traverse(canvas, exit_elem, False, loop_stack)

                        if canvas.elements:
                            traverse(canvas, canvas.elements[0])
                    else:
                        code += f"{indent}    pass\n"
            code += "\n"

        def generate_function_code(element, indent_level=0):
            nonlocal code
            if element["type"] != "Function" or (not element["function_name"] and not element["is_lambda"]):
                return
            indent = "    " * indent_level
            if element["is_lambda"]:
                code += f"{indent}{element['code']} = lambda {element['function_params']}: {element['code']}\n"
            else:
                code += f"{indent}def {element['function_name']}({element['function_params'] or ''}):\n"
                if element["subflowchart"]:
                    indent_level += 1
                    visited = set()
                    def traverse(canvas, elem, in_loop=False, loop_stack=None):
                        nonlocal code, indent_level
                        if loop_stack is None:
                            loop_stack = []
                        if elem["id"] in visited:
                            return
                        visited.add(elem["id"])

                        indent = "    " * indent_level
                        if elem["type"] == "Process":
                            call_connections = [conn for conn in canvas.connections if conn[0] == elem and conn[4] == "Call"]
                            if call_connections:
                                for conn in call_connections:
                                    target = conn[1]
                                    if target["type"] == "Function":
                                        params = conn[5] or target["function_params"]
                                        code += f"{indent}{elem['code'] or ''} = {target['function_name']}({params})\n"
                                    elif target["type"] == "Class":
                                        method_name = conn[5].split('.')[1].split('(')[0] if '.' in conn[5] else ""
                                        params = conn[5].split('(')[1].rstrip(')') if '(' in conn[5] else conn[5]
                                        code += f"{indent}{elem['code'] or ''} = self.{method_name}({params})\n"
                            else:
                                code += f"{indent}{elem['code'] or 'pass'}\n"
                        elif elem["type"] == "Input":
                            code += f"{indent}{elem['code'] or 'input()'}\n"
                        elif elem["type"] == "Output":
                            code += f"{indent}print({elem['code'] or 'output'})\n"
                        elif elem["type"] == "Comment":
                            code += f"{indent}# {elem['code'] or 'comment'}\n"
                        elif elem["type"] == "Decision":
                            code += f"{indent}if {elem['condition'] or 'condition'}:\n"
                            indent_level += 1
                            true_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == elem and conn[4] == "Body"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                            for branch in true_branches:
                                traverse(canvas, branch, in_loop, loop_stack)
                            if not true_branches:
                                code += f"{'    ' * indent_level}pass\n"
                            indent_level -= 1
                            code += f"{indent} else:\n"
                            indent_level += 1
                            false_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == elem and conn[4] == "Exit"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                            for branch in false_branches:
                                traverse(canvas, branch, in_loop, loop_stack)
                            if not false_branches:
                                code += f"{'    ' * indent_level}pass\n"
                            indent_level -= 1
                        elif elem["type"] == "Loop":
                            if elem["loop_type"] == "for":
                                code += f"{indent}for {elem['condition'] or 'i in range(5)'}:\n"
                            else:
                                code += f"{indent}while {elem['condition'] or 'True'}:\n"
                            indent_level += 1
                            loop_stack.append(elem)
                            body_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == elem and conn[4] == "Body"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                            for branch in body_branches:
                                traverse(canvas, branch, True, loop_stack)
                            if not body_branches:
                                code += f"{'    ' * indent_level}pass\n"
                            indent_level -= 1
                            loop_stack.pop()
                        elif elem["type"] ==                             "Start/End" and elem != canvas.elements[0]:
                            if not in_loop:
                                if elem["return_value"]:
                                    code += f"{indent}return {elem['return_value']}\n"
                                else:
                                    code += f"{indent}\n"

                        if not in_loop or (in_loop and elem["type"] not in ["Decision", "Loop"]):
                            next_elements = sorted([conn[1] for conn in canvas.connections if conn[0] == elem and conn[4] == "Body"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                            for next_elem in next_elements:
                                traverse(canvas, next_elem, in_loop, loop_stack)
                            if in_loop and loop_stack and not next_elements:
                                exit_elements = sorted([conn[1] for conn in canvas.connections if conn[0] == loop_stack[-1] and conn[4] == "Exit"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                                for exit_elem in exit_elements:
                                    traverse(canvas, exit_elem, False, loop_stack)

                    if canvas.elements:
                        traverse(canvas, canvas.elements[0])
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
            indent = "    " * indent_level
            visited = set()
            def traverse(elem, in_loop=False, loop_stack=None):
                nonlocal code, indent_level
                if loop_stack is None:
                    loop_stack = []
                if elem["id"] in visited:
                    return
                visited.add(elem["id"])

                if elem["type"] == "Process":
                    call_connections = [conn for conn in canvas.connections if conn[0] == elem and conn[4] == "Call"]
                    if call_connections:
                        for conn in call_connections:
                            target = conn[1]
                            if target["type"] == "Function":
                                params = conn[5] or target["function_params"]
                                code += f"{indent}{elem['code'] or ''} = {target['function_name']}({params})\n"
                            elif target["type"] == "Class":
                                method_call = conn[5]
                                code += f"{indent}{elem['code'] or ''} = {method_call}\n"
                    else:
                        code += f"{indent}{elem['code'] or 'pass'}\n"
                elif elem["type"] == "Input":
                    code += f"{indent}{elem['code'] or 'input()'}\n"
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
                    indent_level -= 1
                    code += f"{indent}else:\n"
                    indent_level += 1
                    false_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == elem and conn[4] == "Exit"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                    for branch in false_branches:
                        traverse(branch, in_loop, loop_stack)
                    if not false_branches:
                        code += f"{'    ' * indent_level}pass\n"
                    indent_level -= 1
                elif elem["type"] == "Loop":
                    if elem["loop_type"] == "for":
                        code += f"{indent}for {elem['condition'] or 'i in range(5)'}:\n"
                    else:
                        code += f"{indent}while {elem['condition'] or 'True'}:\n"
                    indent_level += 1
                    loop_stack.append(elem)
                    body_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == elem and conn[4] == "Body"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                    for branch in body_branches:
                        traverse(branch, True, loop_stack)
                    if not body_branches:
                        code += f"{'    ' * indent_level}pass\n"
                    indent_level -= 1
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
                        exit_elements = sorted([conn[1] for conn in canvas.connections if conn[0] == loop_stack[-1] and conn[4] == "Exit"], key=lambda c: canvas.connections[canvas.connections.index(c)][6])
                        for exit_elem in exit_elements:
                            traverse(exit_elem, False, loop_stack)

            if canvas.elements:
                traverse(canvas.elements[0])

        code += "def main():\n"
        generate_main_flow(self.main_canvas, indent_level=1)
        code += "\nif __name__ == '__main__':\n    main()\n"

        self.code_text.insert(tk.END, code)
        messagebox.showinfo("成功", "程式碼已生成，請檢查程式碼視窗。")

    def run_code(self):
        self.output_text.config(state="normal")
        self.output_text.delete(1.0, tk.END)
        self.output_text.insert(tk.END, "執行中...\n")
        self.output_text.config(state="disabled")
        self.root.update()

        code = self.code_text.get(1.0, tk.END).strip()
        if not code:
            self.output_text.config(state="normal")
            self.output_text.delete(1.0, tk.END)
            self.output_text.insert(tk.END, "錯誤：無程式碼可執行\n")
            self.output_text.config(state="disabled")
            return

        self.execution_globals = {}
        for name in dir(builtins):
            self.execution_globals[name] = getattr(builtins, name)
        self.execution_globals.update(self.variables)

        sys.stdout = io.StringIO()
        highlight_duration, error_duration = self.get_animation_duration()
        visited_elements = set()
        visited_connections = set()

        def highlight_and_execute(canvas, elem, in_loop=False, loop_stack=None):
            if loop_stack is None:
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
                            if target["type"] == "Function" and target["subflowchart"]:
                                highlight_and_execute(target["subflowchart"], target["subflowchart"].elements[0])
                            elif target["type"] == "Class" and conn[5]:
                                method_name = conn[5].split('.')[1].split('(')[0] if '.' in conn[5] else ""
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
                    valid, error_msg = self.validate_code(elem["code"], element=elem, canvas=canvas)
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
                        iter_obj = eval(f"iter({elem['condition'].split(' in ')[1]})", self.execution_globals)
                        var_name = elem["condition"].split(' in ')[0].strip()
                        for val in iter_obj:
                            self.execution_globals[var_name] = val
                            body_branches = sorted([conn for conn in canvas.connections if conn[0] == elem and conn[4] == "Body"], key=lambda c: c[6])
                            for conn in body_branches:
                                if conn not in visited_connections:
                                    canvas.highlight_connection(conn, duration=highlight_duration)
                                    visited_connections.add(conn)
                                highlight_and_execute(canvas, conn[1], True, loop_stack)
                    else:
                        while eval(elem["condition"], self.execution_globals):
                            body_branches = sorted([conn for conn in canvas.connections if conn[0] == elem and conn[4] == "Body"], key=lambda c: c[6])
                            for conn in body_branches:
                                if conn not in visited_connections:
                                    canvas.highlight_connection(conn, duration=highlight_duration)
                                    visited_connections.add(conn)
                                highlight_and_execute(canvas, conn[1], True, loop_stack)
                    loop_stack.pop()
                elif elem["type"] == "Start/End" and elem != canvas.elements[0]:
                    if not in_loop and elem["return_value"]:
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
                self.output_text.delete(1.0, tk.END)
                self.output_text.insert(tk.END, f"執行錯誤：\n{error_msg}\n")
                self.output_text.config(state="disabled")
                sys.stdout = sys.__stdout__
                return

        try:
            exec(code, self.execution_globals)
            if self.main_canvas.elements:
                highlight_and_execute(self.main_canvas, self.main_canvas.elements[0])
            output = sys.stdout.getvalue()
            self.output_text.config(state="normal")
            self.output_text.delete(1.0, tk.END)
            self.output_text.insert(tk.END, output or "執行完成，無輸出。\n")
            self.output_text.insert(tk.END, "已自動載入內建函式 print, len 等。\n")
            self.output_text.config(state="disabled")
        except Exception as e:
            error_msg = traceback.format_exc()
            self.output_text.config(state="normal")
            self.output_text.delete(1.0, tk.END)
            self.output_text.insert(tk.END, f"執行錯誤：\n{error_msg}\n")
            self.output_text.config(state="disabled")
        finally:
            sys.stdout = sys.__stdout__

    def clear_canvas(self):
        if messagebox.askyesno("確認", "確定要清除畫布？所有元素和連線將被刪除。"):
            self.save_state(self.main_canvas)
            self.main_canvas.canvas.delete("all")
            self.main_canvas.elements = []
            self.main_canvas.connections = []
            self.defined_variables.clear()
            self.function_signatures.clear()
            self.class_signatures.clear()
            self.imported_names.clear()
            self.code_text.delete(1.0, tk.END)
            self.output_text.config(state="normal")
            self.output_text.delete(1.0, tk.END)
            self.output_text.config(state="disabled")

    def save_flowchart(self):
        filename = simpledialog.askstring("輸入", "輸入儲存檔案名稱（例如：flowchart.json）：")
        if filename:
            if not filename.endswith(".json"):
                filename += ".json"
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
                                    "methods": se.get("methods")
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
                "libraries": self.libraries
            }
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                messagebox.showinfo("成功", f"流程圖已儲存至 {filename}")
            except Exception as e:
                messagebox.showerror("錯誤", f"儲存失敗：{str(e)}")

    def load_flowchart(self):
        filename = simpledialog.askstring("輸入", "輸入要載入的檔案名稱（例如：flowchart.json）：")
        if filename:
            if not filename.endswith(".json"):
                filename += ".json"
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.clear_canvas()
                self.variables = data.get("variables", {})
                self.libraries = data.get("libraries", [])
                for var_name in self.variables:
                    self.defined_variables.add(var_name)

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
                    if elem["subflowchart"]:
                        new_elem["subflowchart"] = FlowchartCanvas(self.root, f"函式/方法：{elem['function_name'] or elem['class_name'] or '未命名'}", is_subflowchart=True, function_element=new_elem)
                        self.bind_canvas_events(new_elem["subflowchart"])
                        for sub_elem in elem["subflowchart"]["elements"]:
                            self.element_var.set(sub_elem["type"])
                            new_elem["subflowchart"].add_element(sub_elem["type"], sub_elem["x"], sub_elem["y"], self)
                            new_sub_elem = new_elem["subflowchart"].elements[-1]
                            new_sub_elem["x"], new_sub_elem["y"] = sub_elem["x"], sub_elem["y"]
                            new_sub_elem["code"] = sub_elem["code"]
                            new_sub_elem["condition"] = sub_elem["condition"]
                            new_sub_elem["loop_type"] = sub_elem["loop_type"]
                            new_sub_elem["function_name"] = sub_elem["function_name"]
                            new_sub_elem["function_params"] = sub_elem["function_params"]
                            new_sub_elem["is_lambda"] = sub_elem.get("is_lambda")
                            new_sub_elem["return_value"] = sub_elem["return_value"]
                            new_sub_elem["class_name"] = sub_elem.get("class_name")
                            new_sub_elem["parent_class"] = sub_elem.get("parent_class")
                            new_sub_elem["attributes"] = sub_elem.get("attributes")
                            new_sub_elem["methods"] = sub_elem.get("methods", [])
                            self.update_element_coords(new_sub_elem, new_elem["subflowchart"])
                            label_text = self.get_label_text(new_sub_elem)
                            new_elem["subflowchart"].canvas.itemconfig(new_sub_elem["label_id"], text=label_text[:20] + "..." if len(label_text) > 20 else label_text)
                        for conn in elem["subflowchart"]["connections"]:
                            start_elem = new_elem["subflowchart"].elements[conn[0]]
                            end_elem = new_elem["subflowchart"].elements[conn[1]]
                            conn_type, call_params, priority = conn[2], conn[3], conn[4]
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
                            "attributes": elem["attributes"] or {},
                            "methods": {m["name"]: len([p for p in m["params"].split(",") if p.strip()]) for m in elem["methods"] or []}
                        }

                for conn in data["connections"]:
                    start_elem = self.main_canvas.elements[conn[0]]
                    end_elem = self.main_canvas.elements[conn[1]]
                    conn_type, call_params, priority = conn[2], conn[3], conn[4]
                    color = "#5E81AC" if conn_type == "Body" else "#BF616A" if conn_type == "Exit" else "#A3BE8C"
                    line_id = self.main_canvas.canvas.create_line(start_elem["x"], start_elem["y"], end_elem["x"], end_elem["y"], arrow=tk.LAST, fill=color, tags="connection")
                    label_id = self.main_canvas.canvas.create_text((start_elem["x"] + end_elem["x"]) / 2, (start_elem["y"] + end_elem["y"]) / 2, text=f"{conn_type} ({priority})" if conn_type == "Body" else conn_type, font=("Arial", 8))
                    self.main_canvas.connections.append((start_elem, end_elem, line_id, label_id, conn_type, call_params, priority))

                messagebox.showinfo("成功", f"已載入流程圖 {filename}")
            except Exception as e:
                messagebox.showerror("錯誤", f"載入失敗：{str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    app = FlowchartToCodeGUI(root)
    root.mainloop()
