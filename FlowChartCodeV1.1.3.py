
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

class FlowchartCanvas:
    def __init__(self, parent, title, is_subflowchart=False, function_element=None):
        self.window = tk.Toplevel(parent) if is_subflowchart else parent
        self.window.title(title)
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
        element_id = str(uuid.uuid4())  # Unique ID for elements
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
            "subflowchart": None if element_type == "Function" else None,
            "return_value": "" if element_type == "Start/End" and self.elements else None
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
        self.canvas.itemconfig(element["canvas_id"], outline="black", width=1)
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
            original_color = "#5E81AC" if item[4] == "Body" else "#BF616A" if item[4] == "Exit" else "#A3BE8C"
            self.canvas.itemconfig(item[2], fill=original_color, width=1)
        else:
            self.canvas.itemconfig(item["canvas_id"], outline="black", width=1)
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
        elements = ["Start/End", "Process", "Decision", "Input", "Output", "Loop", "Comment", "Function"]
        ttk.Label(self.toolbar, text="元素：").pack(side=tk.LEFT, padx=2)
        ttk.OptionMenu(self.toolbar, self.element_var, "Process", *elements).pack(side=tk.LEFT, padx=2)

        self.connection_label = tk.StringVar(value="Body")
        ttk.Label(self.toolbar, text="連線：").pack(side=tk.LEFT, padx=2)
        ttk.OptionMenu(self.toolbar, self.connection_label, "Body", "Body", "Exit", "Call").pack(side=tk.LEFT, padx=2)

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
        self.variables = {}  # Store variable name: value pairs
        self.undo_stack = deque(maxlen=50)
        self.redo_stack = deque(maxlen=50)
        self.execution_globals = {}
        self.defined_variables = set()
        self.function_signatures = {}

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
            return

        canvas.canvas.delete("all")
        canvas.elements = []
        canvas.connections = []
        self.defined_variables.clear()
        self.function_signatures.clear()

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
            if elem["subflowchart"]:
                new_elem["subflowchart"] = FlowchartCanvas(self.root, f"函式：{elem['function_name']}", is_subflowchart=True, function_element=new_elem)
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

        for conn in state["connections"]:
            start, end = canvas.elements[conn[0]], canvas.elements[conn[1]]
            color = "#5E81AC" if conn[2] == "Body" else "#BF616A" if conn[2] == "Exit" else "#A3BE8C"
            line_id = canvas.canvas.create_line(start["x"], start["y"], end["x"], end["y"], arrow=tk.LAST, fill=color, tags="connection")
            label_id = canvas.canvas.create_text((start["x"] + end["x"]) / 2, (start["y"] + end["y"]) / 2, text=f"{conn[2]} ({conn[4]})" if conn[2] == "Body" else conn[2], font=("Arial", 8))
            canvas.connections.append((start, end, line_id, label_id, conn[2], conn[3], conn[4]))

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
                    if node.id not in self.defined_variables and node.id not in self.execution_globals and node.id not in self.variables:
                        undefined_vars.add(node.id)
            if undefined_vars:
                return False, f"未定義變數：{', '.join(undefined_vars)}。請在變數管理中宣告或在程式碼中定義。"
        except:
            pass

        if not is_lambda:
            valid_operators = r'[\+\-\*/%=<>&|\^~!]=?|==|!=|<=|>=|and|or|not'
            if not re.search(valid_operators, code) and (is_condition or element["type"] in ["Process", "Decision", "Loop"]):
                return False, f"缺少有效運算子。建議使用：{', '.join(['+', '-', '*', '/', '==', '!=', '<', '>', 'and', 'or', 'not'])}"

        if element and element["type"] == "Input":
            if "int(" not in code and "float(" not in code and "str(" not in code:
                return False, "輸入元素應包含類型轉換（例如 int(input())），以確保正確的資料類型。"

        return True, ""

    def validate_function_call(self, func_name, params):
        if func_name not in self.function_signatures:
            return False, f"函式 '{func_name}' 未定義。"
        param_count = len([p for p in params.split(",") if p.strip()])
        expected_count = self.function_signatures[func_name]
        if param_count != expected_count:
            return False, f"函式 '{func_name}' 期望 {expected_count} 個參數，但提供了 {param_count} 個。"
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
            if abs(event.x - element["x"]) < 50 and abs(event.y - element["y"]) < 30:
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
                connections_to_remove = [conn for conn in canvas.connections if conn[0] == "self.selected_element or conn[1] == self.selected_element"]
                for conn in connections_to_remove:
                    canvas.canvas.delete(conn[2])
                    canvas.canvas.delete(conn[3])
                    canvas.connections.remove(conn)
                if self.selected_element["type"] == "Function" and self.selected_element["subflowchart"]:
                    try:
                        self.selected_element["subflowchart"].window.destroy()
                    except:
                        pass
                    if self.selected_element["function_name"] in self.function_signatures:
                        del self.function_signatures["self.selected_element['function_name']"]
                canvas.elements.remove(self.selected_element)
                self.selected_element = None
            except Exception as e:
                messagebox.showerror("警告", f"刪除元素失敗：{str(e)}")

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
            self.libraries.append(library)
            messagebox.showinfo("成功", f"已新增函式庫 '{library}'")

    def start_connection(self, canvas, event):
        for element in canvas.elements:
            if abs(event.x - element["x"]) < 50 and abs(event.y - element["y"]) < 30:
                canvas.start_point = (element["x"], element["y"], element)
                break

    def draw_connection(self, canvas, event):
        if canvas.start_point:
            if canvas.temp_line:
                canvas.canvas.delete(canvas.temp_line)
            color = "#5E81AC" if self.connection_label.get() == "Body" else "#BF616A" if self.connection_label.get() == "Exit" else "#A3BE8C"
            canvas.temp_line = canvas.canvas.create_line(canvas.start_point[0], canvas.start_point[1], event.x, event.y, arrow=tk.LAST, fill=color)

    def end_connection(self, canvas, event):
        if canvas.start_point:
            for element in canvas.elements:
                if abs(event.x - element["x"]) < 50 and abs(event.y - element["y"]) < 30 and element != canvas.start_point[2]:
                    if self.connection_label.get() == "Call" and element["type"] != "Function":
                        messagebox.showerror("錯誤", "Call 連線必須指向函式元素")
                        break
                    if self.connection_label.get() == ["Body", "Exit"] and element["type"] == "Function":
                        messagebox.showerror("錯誤", "Body/Exit 連線不能指向函式元素")
                        break
                    color = "#5E81AC" if self.connection_label.get() == "Body" else "#BF616A" if self.connection_label.get() == "Exit" else "#A3BE8C"
                    call_params = ""
                    priority = 0
                    if self.connection_label.get() == "Body":
                        priority_str = simpledialog.askstring("輸入", "輸入連線優先級（整數，較低值優先）：", initialvalue="0")
                        try:
                            priority = int(priority_str)
                        except (ValueError, TypeError):
                            messagebox.showerror("錯誤", "優先級必須為整數")
                            break
                    if self.connection_label.get() == "Call":
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
                        label_id = canvas.canvas.create_text((canvas.start_point[0] + element["x"]) / 2, (canvas.start_point[1] + element["y"]) / 2, text=f"{self.connection_label.get()} ({priority})" if self.connection_label.get() == "Body" else self.connection_label.get(), font=("Arial", 8))
                        canvas.connections.append((canvas.start_point[2], element, line_id, label_id, self.connection_label.get(), call_params, priority))
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

    def generate_code(self):
        self.code_text.delete(1.0, tk.END)
        code = "# 自動生成的 Python 程式碼\n\n"

        for lib in sorted(self.libraries):
            code += f"import {lib}\n"
        if self.libraries:
            code += "\n"

        for name, value in self.variables.items():
            code += f"{name} = {value}\n"
        if self.variables:
            code += "\n"

        def generate_function_code(element, indent_level=0):
            nonlocal code
            if element["type"] != "Function" or (not element["function_name"] and not element["is_lambda"]):
                return
            indent = "    " * indent_level
            if element["is_lambda"]:
                code += f"{indent}{element['code']} = lambda {element['function_params']}: {element['code']}\n"
            else:
                code += f"{indent}def {element['function_name']}({element['function_params'] or ''}):"
                if element["subflowchart"]:
                    indent_level += 1
                    visited = set()
                    def traverse(canvas, element, in_loop=False, loop_stack=None):
                        nonlocal code, indent_level
                        if loop_stack is None:
                            loop_stack = []
                        if element["id"] in visited:
                            return
                        visited.add(element["id"])

                        indent = "    " * indent_level
                        if element["type"] == "Process":
                            call_connections = [conn for conn in canvas.connections if conn[0] == element and conn[4] == "Call"]
                            if call_connections:
                                for conn in call_connections:
                                    target = conn[1]
                                    if target["type"] == "Function":
                                        params = conn[5] or target["function_params"]
                                        code += f"{indent}{element['code'] or ''} = {target['function_name']}({params})\n"
                            else:
                                code += f"{indent}{element['code'] or 'pass'}\n"
                        elif element["type"] == "Input":
                            code += f"{indent}{element['code'] or 'input()'}\n"
                        elif element["type"] == "Output":
                            code += f"{indent}print({element['code'] or 'output'})\n"
                        elif element["type"] == "Comment":
                            code += f"{indent}# {element['code'] or 'comment'}\n"
                        elif element["type"] == "Decision":
                            code += f"{indent}if {element['condition'] or 'condition'}:\n"
                            indent_level += 1
                            true_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == element and conn[4] == "Body"], key=lambda c: canvas.connections[[c2[1] for c2 in canvas.connections if c2[0] == element and c2[4] == "Body"].index(c)][6])
                            for branch in true_branches:
                                traverse(canvas, branch, in_loop, loop_stack)
                            if not true_branches:
                                code += f"{'    ' * indent_level}pass\n"
                            indent_level -= 1
                            code += f"{indent}else:\n"
                            indent_level += 1
                            false_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == element and conn[4] == "Exit"], key=lambda c: canvas.connections[[c2[1] for c2 in canvas.connections if c2[0] == element and c2[4] == "Exit"].index(c)][6])
                            for branch in false_branches:
                                traverse(canvas, branch, in_loop, loop_stack)
                            if not false_branches:
                                code += f"{indent_level}pass\n"
                            indent_level -= 1
                        elif element["type"] == "Loop":
                            if element["loop_type"] == "for":
                                code += f"{indent}for {element['condition'] or 'i in range(5)'}:\n"
                            else:
                                code += f"{indent}while {element['condition'] or {'True'}}:\n"
                            indent_level += 1
                            loop_stack.append(element)
                            body_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == element and conn[4] == "Body"], key=lambda c: canvas.connections[[c2[1] for c2 in canvas.connections if c2[0] == element and c2[4] == "Body"].index(c)][6])
                            for branch in body_branches:
                                traverse(canvas, branch, True, loop_stack)
                            if not body_branches:
                                code += f"{'    ' * indent_level}pass\n"
                            indent_level -= 1
                            loop_stack.pop()
                        elif element["type"] == "Start/End" and element != canvas.elements[0]:
                            if not in_loop:
                                if element["return_value"]:
                                    code += f"{indent}return {element['return_value']}\n"
                                else:
                                    code += f"{indent}return\n"

                        if not in_loop or (in_loop and element["type"] not in ["Decision", "Loop"]):
                            next_elements = sorted([conn[1] for conn in canvas.connections if conn[0] == element and conn[4] == "Body"], key=lambda c: canvas.connections[[c2[1] for c2 in canvas.connections if c2[0] == element and c2[4] == "Body"].index(c)][6])
                            for next_element in next_elements:
                                traverse(canvas, next_element, in_loop, loop_stack)
                            if in_loop and loop_stack and not next_elements:
                                exit_elements = sorted([conn[1] for conn in canvas.connections if conn[0] == loop_stack[-1] and conn[4] == "Exit"], key=lambda c: canvas.connections[[c2[1] for c2 in canvas.connections if c2[0] == loop_stack[-1] and c2[4] == "Exit"].index(c)][6])
                                for exit_element in exit_elements:
                                    traverse(canvas, exit_element, False, loop_stack)

                    if canvas.elements:
                        traverse(canvas, canvas.elements[0])
                else:
                    code += f"{indent}    pass\n"

        all_functions = []
        def collect_functions(canvas):
            for element in canvas.elements:
                if element["type"] == "Function":
                    all_functions.append(element)
                if element["subflowchart"]:
                    collect_functions(element["subflowchart"])

        collect_functions(self.main_canvas)
        for func in all_functions:
            generate_function_code(func)

        code += "\ndef main():\n"
        indent_level = 1
        visited = set()
        def traverse(canvas, element, in_loop=False, loop_stack=None):
            nonlocal code, indent_level
            if loop_stack is None:
                loop_stack = []
                if element["id"] == "in visited":
                    return
                visited.add(element["id"])

            indent = "    " * indent_level
            if element["type"] == "Process":
                call_connections = [conn for conn in canvas.connections if conn[0] == element and conn[4] == "Call"]
                if call_connections:
                    for conn in call_connections:
                        target = conn[1]
                        if target["type"] == "Function":
                            params = conn[5] or target["function_params"]
                            code += f"{indent}{element['code'] or ''} = {target['function_name']}({params})\n"
                else:
                    code += f"{indent}{element['code'] or 'pass'}\n"
            elif element["type"] == "Input":
                code += f"{indent}{element['code'] or 'input()'}\n"
            elif element["type"] == "Output":
                code += f"{indent}print({element['code'] or 'output'})\n"
            elif element["type"] == "Comment":
                code += f"{indent}# {element['code'] or 'comment'}\n"
            elif element["type"] == "Decision":
                code += f"{indent}if {element['condition'] or 'condition'}:\n"
                indent_level += 1
                true_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == element and conn[4] == "Body"], key=lambda c: canvas.connections[[c2[1] for c2 in canvas.connections if c2[0] == element and c2[4] == "Body"].index(c)][6])
                for branch in true_branches:
                    traverse(canvas, branch, in_loop, loop_stack)
                if not true_branches:
                    code += f"{'    ' * indent_level}pass\n"
                indent_level -= 1
                code += f"{indent}else:\n"
                indent_level += 1
                false_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == element and conn[4] == "Exit"], key=lambda c: canvas.connections[[c2[1] for c2 in canvas.connections if c2[0] == element and c2[4] == "Exit"].index(c)][6])
                for branch in false_branches:
                    traverse(canvas, branch, in_loop, loop_stack)
                if not false_branches:
                    code += f"{'    ' * indent_level}pass\n"
                indent_level -= 1
            elif element["type"] == "Loop":
                if element["loop_type"] == "for":
                    code += f"{indent}for {element['condition'] or 'i in range(5)'}:\n"
                else:
                    code += f"{indent}while {element['condition'] or 'True'}:\n"
            else:
                code += f"{indent}while loop_stack:\n"
                indent_level += 1
                loop_stack.append(element)
                body_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == element and conn[4] == "Body"], key=lambda c: canvas.connections[[c2[1] for c2 in canvas.connections if c2[0] == element and c2[4] == "Body"].index(c)][6])
                for branch in body_branches:
                    traverse(canvas, branch, True, loop_stack)
                if not body_branches:
                    code += f"{'    ' * indent_level}pass\n"
                    indent_level -= 1
                    loop_stack.pop()
                elif element["type"] == "Start/End" and element != canvas.elements[0]:
                    if not in_loop:
                        if element["return_value"]:
                            code += f"{indent}return {element['return_value']}\n"
                        else:
                            code += f"{indent}return\n"

                if not in_loop or (in_loop and element["type"] not in ["Decision", "Loop"]):
                    next_elements = sorted([conn[1] for conn in canvas.connections if conn[0] == element and conn[4] == "Body"], key=lambda c: canvas.connections[[c2[1] for c2 in canvas.connections if c2[0] == element and c2[4] == "Body"].index(c)][6])
                    for next_element in next_elements:
                        traverse(canvas, next_element, in_loop, loop_stack)
                    if in_loop and loop_stack and not next_elements:
                        exit_elements = sorted([conn[1] for conn in canvas.connections if conn[0] == loop_stack[-1] and conn[4] == "Exit"], key=lambda c: canvas.connections[[c2[1] for c2 in canvas.connections if c2[0] == loop_stack[-1] and c2[4] == "Exit"].index(c)][6])
                        for exit_element in exit_elements:
                            traverse(canvas, exit_element, False, loop_stack)

        if self.main_canvas.elements:
            traverse(self.main_canvas, self.main_canvas.elements[0])
        else:
            code += "# 無流程圖元素\n"
        self.code_text.insert(tk.END, code)

    def provide_error_suggestion(self, exception, element=None, connection=None):
        suggestion = ""
        if isinstance(exception, NameError):
            var_name = str(exception).split("'")[1]
            suggestion = f"建議：變數 '{var_name}' 未定義。請檢查是否在變數管理或之前的元素中正確宣告，或確認拼寫正確。"
            if element and element["type"] in ["Process", "Output", "Decision", "Loop"]:
                suggestion += f"\n當前元素程式碼：{element.get('code') or element.get('condition')}"
        elif isinstance(exception, TypeError):
            suggestion = f"建議：類型錯誤，可能使用了不兼容的資料類型（例如對字串執行數學運算）。請檢查變數類型或運算子。"
            if element and element["type"] in ["Process", "Output", "Decision", "Loop"]:
                suggestion += f"\n當前元素程式碼：{element.get('code') or element.get('condition')}"
            if connection and connection[4] == "Call":
                suggestion += f"\n函式呼叫參數：{connection[5]}。請確認參數類型與函式定義匹配。"
        elif isinstance(exception, SyntaxError):
            suggestion = "建議：語法錯誤，請檢查程式碼語法是否正確（例如遺漏冒號、縮進錯誤）。"
            if element:
                suggestion += f"\n當前元素程式碼：{element.get('code') or element.get('condition')}"
        elif isinstance(exception, ValueError):
            suggestion = "建議：值錯誤，可能輸入的資料格式不正確（例如將字串轉換為整數時輸入非數字）。請檢查輸入值或轉換邏輯。"
            if element and element["type"] == "Input":
                suggestion += f"\n當前輸入程式碼：{element['code']}"
        else:
            suggestion = "建議：發生未知錯誤，請檢查程式碼邏輯或聯繫支援。"
        return suggestion

    def run_code(self):
        self.output_text.config(state="normal")
        self.output_text.delete(1.0, tk.END)
        self.execution_globals.clear()

        code = self.code_text.get(1.0, tk.END).strip()
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            suggestion = self.provide_error_suggestion(e)
            self.output_text.insert(tk.END, f"語言法錯誤：{str(e)}\n{suggestion}\n")
            self.output_text.config(state="disabled")
            return

        normal_duration, error_duration = self.get_animation_duration()

        def evaluate_condition(condition, globals_dict):
            try:
                return eval(condition, globals_dict)
            except:
                return False

        def instrument_code(canvas, element, in_loop=False, loop_stack=None, globals_dict=None):
            if loop_stack is None:
                loop_stack = []
                if globals_dict is None:
                    globals_dict = self.execution_globals
                if not hasattr(self, 'execution_path'):
                    self.execution_path = []
                if element in canvas.elements:
                    self.execution_path.append((canvas, element))
                else:
                    return None, False

            visited = set()
            error_item = None
            error_is_connection = False

            try:
                if element["id"] in visited:
                    return None, False
                visited.add(element["id"])

                if element["type"] == "Process":
                    call_connections = [conn for conn in canvas.connections if conn[0] == element and conn[4] == "Call"]
                    if call_connections:
                        for conn in call_connections:
                            target = conn[1]
                            if target["type"] == "Function":
                                self.execution_path.append((canvas, conn))
                                params = conn[5] or target["function_params"]
                                try:
                                    eval(f"{target['function_name']}({params})", globals_dict)
                                    if target["is_lambda"]:
                                        exec(f"{element['code']} = lambda {target['function_params']}: {target['code']}", globals_dict)
                                    elif target["subflowchart"]:
                                        sub_error_item, sub_error_is_connection = error instrument_code(target["subflowchart"], target["subflowchart"].elements[0], in_loop, loop_stack, globals_dict)
                                        if sub_error_item:
                                            error_item = sub_error_item
                                            error_is_connection = sub_error_is_connection
                                            raise Exception("子流程圖執行錯誤")
                                except Exception as e:
                                    error_item = conn
                                    error_is_connection = True
                                    raise e
                                else:
                                    exec(element["code"], globals_dict)
                            elif element["type"] == "Input":
                                exec(element["code"], globals_dict)
                            elif element["type"] == "Output":
                                exec(f"print({element['code']})", globals_dict)
                            elif element["type"] == "Decision":
                                condition_result = evaluate_condition(element["condition"], globals_dict)
                                    branches = sorted([conn[1] for conn in canvas.connections if conn[0] == element and conn[4] == ("Body" if condition_result else "Exit")], key=lambda c: canvas.connections[[c2[1] for c2 in canvas.connections if c2[0] == element and c2[4] == ("Body" if condition_result else "Exit")].index(c)][6])
                                    for branch in branches:
                                        conn = next(c for c in canvas.connections if c[0] == element and c[1] == branch and c[4] == ("Body" if condition_result else "Exit"))
                                        self.execution_path.append((canvas, conn))
                                        try:
                                            sub_error_item, sub_error_is_connection = error instrument_code(canvas, branch, in_loop, loop_stack, globals_dict)
                                            if sub_error_item:
                                                error_item = sub_error_item
                                                error_is_connection = sub_error_is_connection
                                                raise Exception("分支執行錯誤")
                                            except Exception as e:
                                                error_item = conn
                                                error_is_connection = True
                                                raise e
                                        except element["type"] == "Loop":
                                            loop_stack.append(element)
                                            if element["loop_type"] == "for":
                                                try:
                                                    loop_iter = eval(f"list({element['condition'].split('(' in ')[1]})", globals_dict)
                                                    loop_var = element["condition"].split(' in ')[0].strip()
                                                    for val in loop_iter:
                                                        globals_dict[loop_var] = val
                                                        self.execution_path.append((canvas, element))
                                                        body_branches.append = sorted([conn[1] for conn in canvas.connections if conn[0] == element and conn[4] == "Body"], key=lambda c: canvas.connections[[c2[1] for c2 in canvas.connections if c2[0] == element and c2[4] == "Body"].index(c)][6])
                                                        for branch in body_branches:
                                                            conn = next(c for c in canvas.connections if c[0] == element and c[1] == branch and c[4] == "Body"))
                                                            self.execution_path.append((canvas, conn))
                                                            try:
                                                                sub_error_item, sub_error_is_connection = error instrument_code(canvas, branch, True, loop_stack, globals_dict)
                                                                if sub_error_item:
                                                                    error_item = sub_error_item
                                                                    error_is_connection = sub_error_is_connection
                                                                    raise Exception("迴圈執行錯誤")
                                                            except Exception as e:
                                                                    error_item = conn
                                                                            error_is_connection = True
                                                                    raise e
                                                                except:
                                                                    max_iterations = = 100
                                                                    iteration = 0
                                                                    while evaluate_condition(element["condition"], globals_dict) and iteration < max_iterations:
                                                                        self.execution_path.append((canvas, element))
                                                                        body_branches.append = sorted([conn[1] for conn in canvas.connections if conn[0] == element and c[4] == "Body"], key=lambda c: canvas.connections[[c2[1] for c2 in canvas.connections if c2[0] == element and c2[4] == "Body"].index(c)][6])
                                                                        for branch in body_branches:
                                                                            conn = next(c for c in canvas.connections if c[0] == element and c[1] == branch and c[4] == "Body")
                                                                            self.execution_path.append((canvas, conn))
                                                                            try:
                                                                                sub_error_item, sub_error_is_connection = error instrument_code(canvas, branch, True, loop_stack, globals_dict)
                                                                                if sub_error_item:
                                                                                    error_item = sub_error_item
                                                                                    error_is_connection = sub_error_is_connection
                                                                                    raise Exception("迴圈執行錯誤")
                                                                                except Exception as e
                                                                                :
                                                                                    error_item = conn
                                                                                            error_is_connection = True
                                                                                    raise e
                                                                                iteration += 1
                                                                        loop_stack.pop()
                                                                    except element["type"] == "Start/End" and element != canvas.elements[0]:
                                                                            pass

                                                                            if not in_loop or (in_loop and element["type"] == ["Decision", "Loop"].index(c)):
                                                                                next_elements = sorted([conn[1] for conn in c in canvas.connections if conn[0] == element and conn[4] == "Body"], key=lambda c: canvas.connections[[c2[1]] for c2 in canvas.connections if c2[0] == element and c2[4] == "Body"].index(c)][6])
                                                                                for next_element in next_elements:
                                                                                    conn = next(c for c in canvas.connections if c[0] == element and c[1] == next_element and c[4] == "Body")
                                                                                    self.execution_path.append((canvas, conn))
                                                                                    try:
                                                                                        sub_error_item, sub_error_is_connection = error instrument_code(canvas, next_element, in_loop, loop_stack, c2)
                                                                                        if sub_error_item:
                                                                                            error_item = sub_error_item
                                                                                            error_is_connection = True
                                                                                            raise Exception("後續執行錯誤")
                                                                                            except Exception as e:
                                                                                                    error_item = conn
                                                                                                    error_is_connection = True
                                                                                                    raise e
                                                                                            except:
                                                                                            if in_loop and loop_stack and not next_elements:
                                                                                                exit_elements = sorted([conn[1] for conn in canvas.connections if conn[0] == loop_stack[-1] and c[4] == "Exit"], key=lambda c: canvas.connections[[c2[1]] for c2 in canvas.connections if c2[0] == loop_stack[-1] and c2[4] == []"Exit"].index(c)][6])
                                                                                                for exit_element in exit_elements:
                                                                                                    conn = next(c for c in canvas.connections if c[0] == loop_stack[-1] and c[1] == exit_element and c[4] == "Exit")
                                                                                                    self.execution_path.append((canvas, conn))
                                                                                                    try:
                                                                                                        sub_error_item, sub_error_is_connection = error instrument_code(canvas, exit_element, False, c2)
                                                                                                        if sub_error_item:
                                                                                                            error_item = sub_error_item
                                                                                                            error_is_connection = sub_error_is_connection
                                                                                                            raise Exception("退出錯誤執行")
                                                                                                        except Exception as e:
                                                                                                            error_item = conn
                                                                                                            error_is_connection = True
                                                                                                            raise e

            except Exception as e:
                if not error_item:
                    error_item = element
                    error_is_connection = False
                raise e

            return error_item, error_is_connection

        old_stdout = sys.stdout
        redirected_output = io.StringIO()
        sys.stdout = redirect_output = redirected_output

        try:
            if self.main_canvas.elements:
                self.execution_path = []
                error_item, error_is_connection = instrument_code(self.main_canvas, self.main_canvas.elements[0])
                exec(code, self.execution_globals)
            for canvas, item in self.execution_path:
                if isinstance(item, tuple):
                    canvas.highlight_connection(item['highlight_connection'], duration=normal_duration)
                else:
                    canvas.highlight_element(item['item'], duration=normal_duration)
            output = redirected_output.getvalue()
            self.output_text.insert(tk.END, output or "無輸出")
        except Exception as e:
            error_msg = f"錯誤：{str(e)}\n"
            error_msg = f"詳細資訊：\n{''.join(traceback.format_tb(e.__traceback__))}\n"
            suggestion = self.provide_error_suggestion(e, error_item if not error_is_connection else None, error_item if error_is_connection else None)
            self.output_text.insert(tk.END, error_msg + suggestion)
            if error_item:
                canvas.highlight_error(error_item, error_is_connection, duration=error_duration)
        finally:
            sys.stdout = old_stdout
            redirected_output.close()
            self.output_text.config(state="disabled")

    def save_flowchart(self):
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
                    "subflowchart": serialize_canvas(element["subflowchart"]) if element["subflowchart"] else None
                }
                elements_data.append(elem_data)
            connections_data = [(canvas.elements.index(c[0]), canvas.elements.index(c[1]), c[4], c[5], c[6]) for c in canvas.connections]
            return {"elements": elements_data, "connections": connections_data}

        flowchart_data = {
            "main_canvas": serialize_canvas(self.main_canvas),
            "libraries": self.libraries,
            "variables": self.variables,
            "defined_variables": list(self.defined_variables),
            "function_signatures": self.function_signatures
        }
        try:
            with open("flowchart.json", "w", encoding="utf-8") as f:
                json.dump(flowchart_data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("成功", "流程圖已成功儲存")
        except Exception as e:
            messagebox.showerror("錯誤", f"儲存失敗：{str(e)}")

    def load_flowchart(self):
        if not os.path.exists("flowchart.json"):
            messagebox.showerror("錯誤", "找不到流程圖檔案")
            return

        try:
            with open("flowchart.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            self.clear_canvas()

            self.libraries = data.get("libraries", [])
            self.variables = data.get("variables", {})
            self.defined_variables = set(data.get("defined_variables", []))
            self.function_signatures = data.get("function_signatures", {})

            def load_canvas(canvas_data, parent_canvas, is_subflowchart=False, function_element=None):
                new_canvas = FlowchartCanvas(self.root, "主流程圖" if not is_subflowchart else f"函式：{function_element['function_name'] or '未命名'}", is_subflowchart, function_element)
                self.bind_canvas_events(new_canvas)

                for elem in canvas_data["elements"]:
                    self.element_var.set(elem["type"])
                    new_canvas.add_element(elem["type"], elem["x"], elem["y"], self)
                    new_elem = new_canvas.elements[-1]
                    new_elem["x"], new_elem["y"] = elem["x"], elem["y"]
                    new_elem["code"] = elem["code"]
                    new_elem["condition"] = elem["condition"]
                    new_elem["loop_type"] = elem["loop_type"]
                    new_elem["function_name"] = elem["function_name"]
                    new_elem["function_params"] = elem["function_params"]
                    new_elem["is_lambda"] = elem.get("is_lambda", False)
                    new_elem["return_value"] = elem["return_value"]
                    if elem["subflowchart"]:
                        new_elem["subflowchart"] = load_canvas(elem["subflowchart"], new_canvas, True, new_elem)
                    self.update_element_coords(new_elem, new_canvas)
                    label_text = self.get_label_text(new_elem)
                    new_canvas.canvas.itemconfig(new_elem["label_id"], text=label_text[:20] + "..." if len(label_text) > 20 else label_text)

                    if elem["type"] in ["Process", "Input"]:
                        self.update_defined_variables(elem["code"])
                    elif elem["type"] == "Function" and elem["function_name"]:
                        param_count = len([p for p in elem["function_params"].split(",") if p.strip()])
                        self.function_signatures[elem["function_name"]] = param_count

                for conn in canvas_data["connections", []]:
                    start, end = new_canvas.elements[conn[0]], new_canvas.elements[conn[1]]]
                    color = "#5E81AC" if conn[2] == "Body" else "#BF616A" if conn[2] == "Exit" else "#A3BE8C"
                    line_id = new_canvas.canvas.create_line(start["x"], start["y"], end["x"], end["y"], arrow=tk.LAST, fill=color, tags="connection")
                    label_id = new_canvas.canvas.create_text((start["x"] + end["x"]) / 2, (start["y"] + end["y"]) / 2, text=f"{conn[2]} ({conn[4]})" if conn[2] == "Body" else conn[2], font=("Arial", 8))
                    new_canvas.connections.append((start, end, line_id, label_id, conn[2], conn[3], conn[4]))

                return new_canvas

            self.main_canvas = load_canvas(data["main_canvas"], None)
            for name in self.variables:
                self.defined_variables.add(name)
            messagebox.showinfo("成功", "流程圖已成功載入")
        except Exception as e:
            messagebox.showerror("錯誤", f"載入失敗：{str(e)}")

    def clear_canvas(self):
        try:
            self.main_canvas.canvas.delete("all")
            for elem in self.main_canvas.elements:
                if elem["type"] == "Function" and elem["subflowchart"]:
                    try:
                        elem["subflowchart"].window.destroy()
                    except:
                        pass
                    except Exception:
                        continue
            self.main_canvas.elements = []
            self.main_canvas.connections = []
            self.libraries.clear()
            self.variables.clear()
            self.defined_variables.clear()
            self.function_signatures.clear()
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.code_text.delete(1.0, tk.END)
            self.output_text.config(state="normal")
            self.output_text.delete(1.0, tk.END)
            self.output_text.config(state="disabled")
            messagebox.showinfo("成功", "畫布已清空")
        except Exception as e:
            messagebox.showerror("錯誤", f"清除畫布失敗：{str(e)}")

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = FlowchartToCodeGUI(root)
        root.mainloop()
    except Exception as e:
        messagebox.showerror("啟動錯誤", f"程式啟動失敗：{str(e)}")
