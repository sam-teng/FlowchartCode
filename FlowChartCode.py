import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, Text
import json
import os
import ast
import sys
import io
from collections import deque
import time
import types
import traceback
#import astor  # 用於將 AST 轉回程式碼

class FlowchartCanvas:
    def __init__(self, parent, title, is_subflowchart=False, function_element=None):
        self.window = tk.Toplevel(parent) if is_subflowchart else parent
        self.window.title(title)
        self.is_subflowchart = is_subflowchart
        self.function_element = function_element

        self.canvas = tk.Canvas(self.window, width=800, height=700, bg="white", bd=2, relief="sunken")
        self.canvas.pack(side=tk.LEFT, padx=10, pady=10)

        self.elements = []
        self.connections = []
        self.start_point = None
        self.temp_line = None
        self.selected_element = None

    def add_element(self, element_type, x, y, main_gui):
        if element_type == "Start/End":
            element_id = self.canvas.create_oval(x-40, y-20, x+40, y+20, fill="lightgreen", tags="element")
            label = "Start" if not self.elements else "End"
        elif element_type == "Process":
            element_id = self.canvas.create_rectangle(x-50, y, x+50, y-20, fill="green", tags="element")
            label = "Process"
        elif element_type == "Decision":
            element_id = self.canvas.create_polygon(x, y-30, x+50, y, x, y+30, x-50, y, fill="lightyellow", tags="element")
            label = "Decision"
        elif element_type == "Input":
            element_id = self.canvas.create_polygon(x-50, y-20, x+50, y-20, x+40, y+20, x-60, y+20, fill="lightpink", tags="element")
            label = "Input"
        elif element_type == "Output":
            element_id = self.canvas.create_polygon(x-50, y-20, x+50, y-20, x+60, y+20, x-40, y+20, fill="lightcoral", tags="element")
            label = "Output"
        elif element_type == "Loop":
            element_id = self.canvas.create_polygon(x-40, y-20, x+40, y-20, x+50, y, x+40, y+20, x-40, y+20, x-50, y, fill="lightpurple", tags="element")
            label = "Loop"
        elif element_type == "Comment":
            element_id = self.canvas.create_rectangle(x-50, y-20, x+50, y+20, fill="lightgray", tags="element")
            label = "Comment"
        elif element_type == "Function":
            element_id = self.canvas.create_rectangle(x-50, y-20, x+50, y+20, fill="lightcyan", tags="element", outline="blue", width=3, dash=(4, 4))
            label = "Function"

        label_id = self.canvas.create_text(x, y, text=label, tags="label")
        element = {
            "id": element_id,
            "label_id": label_id,
            "type": element_type,
            "x": x,
            "y": y,
            "code": "",
            "condition": "" if element_type in ["Decision", "Loop"] else None,
            "loop_type": "for" if element_type == "Loop" else None,
            "function_name": "" if element_type == "Function" else None,
            "function_params": "" if element_type == "Function" else None,
            "subflowchart": None if element_type == "Function" else None,
            "return_value": "" if element_type == "Start/End" and self.elements else None
        }
        self.elements.append(element)

        self.canvas.tag_bind(element_id, "<B1-Motion>", lambda event, eid=element_id: main_gui.move_element(self, event, eid))
        self.canvas.tag_bind(label_id, "<B1-Motion>", lambda event, eid=element_id: main_gui.move_element(self, event, eid))
        self.canvas.tag_bind(element_id, "<Button-3>", lambda event: main_gui.edit_element(self, event))
        self.canvas.tag_bind(label_id, "<Button-3>", lambda event: main_gui.edit_element(self, event))

    def highlight_element(self, element, color="red"):
        self.canvas.itemconfig(element["id"], outline=color, width=3)
        self.canvas.update()
        time.sleep(0.5)
        self.canvas.itemconfig(element["id"], outline="black", width=1)
        self.canvas.update()

    def highlight_connection(self, conn, color="red"):
        self.canvas.itemconfig(conn[2], fill=color, width=3)
        self.canvas.update()
        time.sleep(0.5)
        original_color = "blue" if conn[4] == "Body" else "red" if conn[4] == "Exit" else "green"
        self.canvas.itemconfig(conn[2], fill=original_color, width=1)
        self.canvas.update()

    def highlight_error(self, item, is_connection=False):
        if is_connection:
            self.canvas.itemconfig(item[2], fill="purple", width=5)
        else:
            self.canvas.itemconfig(item["id"], outline="purple", width=5)
        self.canvas.update()
        time.sleep(1)
        if is_connection:
            original_color = "blue" if item[4] == "Body" else "red" if item[4] == "Exit" else "green"
            self.canvas.itemconfig(item[2], fill=original_color, width=1)
        else:
            self.canvas.itemconfig(item["id"], outline="black", width=1)
        self.canvas.update()

class FlowchartToCodeGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("流程圖轉程式碼工具（進階錯誤預防）")
        self.root.geometry("1400x800")

        self.main_canvas = FlowchartCanvas(self.root, "主流程圖")
        self.right_frame = tk.Frame(self.root)
        self.right_frame.pack(side=tk.RIGHT, padx=10, pady=10)

        self.code_text = tk.Text(self.right_frame, width=50, height=25)
        self.code_text.pack(pady=5)

        self.output_text = tk.Text(self.right_frame, width=50, height=10, state="disabled")
        self.output_text.pack(pady=5)

        self.toolbar = tk.Frame(self.root)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)

        self.element_var = tk.StringVar(value="Process")
        elements = ["Start/End", "Process", "Decision", "Input", "Output", "Loop", "Comment", "Function"]
        tk.Label(self.toolbar, text="元素：").pack(side=tk.LEFT)
        tk.OptionMenu(self.toolbar, self.element_var, *elements).pack(side=tk.LEFT, padx=5)

        self.connection_label = tk.StringVar(value="Body")
        tk.Label(self.toolbar, text="連線類型：").pack(side=tk.LEFT, padx=5)
        tk.OptionMenu(self.toolbar, self.connection_label, "Body", "Exit", "Call").pack(side=tk.LEFT, padx=5)

        tk.Button(self.toolbar, text="新增元素", command=lambda: self.add_element(self.main_canvas)).pack(side=tk.LEFT, padx=5)
        tk.Button(self.toolbar, text="產生程式碼", command=self.generate_code).pack(side=tk.LEFT, padx=5)
        tk.Button(self.toolbar, text="執行程式碼", command=self.run_code).pack(side=tk.LEFT, padx=5)
        tk.Button(self.toolbar, text="清除畫布", command=self.clear_canvas).pack(side=tk.LEFT, padx=5)
        tk.Button(self.toolbar, text="儲存流程圖", command=self.save_flowchart).pack(side=tk.LEFT, padx=5)
        tk.Button(self.toolbar, text="載入流程圖", command=self.load_flowchart).pack(side=tk.LEFT, padx=5)
        tk.Button(self.toolbar, text="匯入函式庫", command=self.import_library).pack(side=tk.LEFT, padx=5)
        tk.Button(self.toolbar, text="上一步", command=self.undo).pack(side=tk.LEFT, padx=5)
        tk.Button(self.toolbar, text="下一步", command=self.redo).pack(side=tk.LEFT, padx=5)

        self.libraries = []
        self.undo_stack = deque(maxlen=50)
        self.redo_stack = deque(maxlen=50)
        self.execution_globals = {}
        self.defined_variables = set()  # 追蹤已定義的變數
        self.function_signatures = {}  # 儲存函式簽名 {name: param_count}

        self.main_canvas.canvas.bind("<Button-1>", lambda event: self.start_connection(self.main_canvas, event))
        self.main_canvas.canvas.bind("<B1-Motion>", lambda event: self.draw_connection(self.main_canvas, event))
        self.main_canvas.canvas.bind("<ButtonRelease-1>", lambda event: self.end_connection(self.main_canvas, event))
        self.main_canvas.canvas.bind("<Button-3>", lambda event: self.edit_connection(self.main_canvas, event))

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
                    "return_value": element["return_value"],
                    "subflowchart": serialize_canvas(element["subflowchart"]) if element["subflowchart"] else None
                }
                elements_data.append(elem_data)
            connections_data = [(canvas.elements.index(c[0]), canvas.elements.index(c[1]), c[4], c[5], c[6] if len(c) > 6 else 0) for c in canvas.connections]
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
            new_elem["return_value"] = elem["return_value"]
            if elem["subflowchart"]:
                new_elem["subflowchart"] = FlowchartCanvas(self.root, f"函式：{elem['function_name']}", is_subflowchart=True, function_element=new_elem)
                new_elem["subflowchart"].canvas.bind("<Button-1>", lambda event: self.start_connection(new_elem["subflowchart"], event))
                new_elem["subflowchart"].canvas.bind("<B1-Motion>", lambda event: self.draw_connection(new_elem["subflowchart"], event))
                new_elem["subflowchart"].canvas.bind("<ButtonRelease-1>", lambda event: self.end_connection(new_elem["subflowchart"], event))
                new_elem["subflowchart"].canvas.bind("<Button-3>", lambda event: self.edit_connection(new_elem["subflowchart"], event))
                self.restore_state(new_elem["subflowchart"], elem["subflowchart"])
            canvas.canvas.coords(new_elem["id"], elem["x"]-50, elem["y"]-20, elem["x"]+50, elem["y"]+20)
            canvas.canvas.coords(new_elem["label_id"], elem["x"], elem["y"])
            label_text = elem["code"] or elem["condition"] or (f"def {elem['function_name']}({elem['function_params']})" if elem["type"] == "Function" else elem["type"])
            if elem["type"] == "Start/End" and elem["return_value"]:
                label_text = f"Return: {elem['return_value']}"
            canvas.canvas.itemconfig(new_elem["label_id"], text=label_text[:20] + "..." if len(label_text) > 20 else label_text)

            # 更新已定義變數和函式簽名
            if elem["type"] in ["Process", "Input"]:
                self.update_defined_variables(elem["code"])
            elif elem["type"] == "Function" and elem["function_name"]:
                param_count = len([p for p in elem["function_params"].split(",") if p.strip()])
                self.function_signatures[elem["function_name"]] = param_count

        for conn in state["connections"]:
            start, end = canvas.elements[conn[0]], canvas.elements[conn[1]]
            color = "blue" if conn[2] == "Body" else "red" if conn[2] == "Exit" else "green"
            line_id = canvas.canvas.create_line(start["x"], start["y"], end["x"], end["y"], arrow=tk.LAST, fill=color, tags="connection")
            label_id = canvas.canvas.create_text((start["x"] + end["x"]) / 2, (start["y"] + end["y"]) / 2, text=f"{conn[2]} ({conn[4]})" if conn[2] == "Body" else conn[2])
            canvas.connections.append((start, end, line_id, label_id, conn[2], conn[3], conn[4]))

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

    def validate_code(self, code, is_condition=False, element=None, canvas=None):
        # 語法驗證
        try:
            if is_condition:
                ast.parse(f"if {code}: pass")
            else:
                ast.parse(code)
        except SyntaxError as e:
            return False, f"語法錯誤：{str(e)}"

        # 變數使用驗證
        undefined_vars = set()
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    if node.id not in self.defined_variables and node.id not in self.execution_globals:
                        undefined_vars.add(node.id)
            if undefined_vars:
                return False, f"未定義變數：{', '.join(undefined_vars)}。請先宣告這些變數。"
        except:
            pass

        # 類型檢查（簡單模擬）
        if element and element["type"] == "Input":
            if "int(" in code or "float(" in code:
                return True, ""
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

    def add_element(self, canvas):
        self.save_state(canvas)
        element_type = self.element_var.get()
        x, y = 400, 50 + len(canvas.elements) * 100
        canvas.add_element(element_type, x, y, self)

    def move_element(self, canvas, event, element_id):
        for element in canvas.elements:
            if element["id"] == element_id:
                canvas.canvas.coords(element_id, event.x-50, event.y-20, event.x+50, event.y+20)
                canvas.canvas.coords(element["label_id"], event.x, event.y)
                element["x"], element["y"] = event.x, event.y
                self.update_connections(canvas)

    def edit_element(self, canvas, event):
        for element in canvas.elements:
            x, y = element["x"], element["y"]
            if abs(event.x - x) < 50 and abs(event.y - y) < 30:
                self.selected_element = element
                break
        else:
            return

        if self.selected_element == canvas.elements[0]:
            messagebox.showinfo("提示", "無法編輯或刪除 Start 元素")
            return

        self.save_state(canvas)
        action = simpledialog.askstring("元素操作", "輸入操作：edit（編輯內容）或 delete（刪除元素及其連線）")
        if action == "edit":
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
                func_dialog.geometry("400x300")

                tk.Label(func_dialog, text="函式名稱：").pack(pady=5)
                name_entry = tk.Entry(func_dialog)
                name_entry.insert(0, self.selected_element["function_name"])
                name_entry.pack(pady=5)

                tk.Label(func_dialog, text="參數（例如：x, y）：").pack(pady=5)
                params_entry = tk.Entry(func_dialog)
                params_entry.insert(0, self.selected_element["function_params"])
                params_entry.pack(pady=5)

                def open_subflowchart():
                    if not self.selected_element["subflowchart"]:
                        self.selected_element["subflowchart"] = FlowchartCanvas(self.root, f"函式：{name_entry.get()}", is_subflowchart=True, function_element=self.selected_element)
                        self.selected_element["subflowchart"].canvas.bind("<Button-1>", lambda event: self.start_connection(self.selected_element["subflowchart"], event))
                        self.selected_element["subflowchart"].canvas.bind("<B1-Motion>", lambda event: self.draw_connection(self.selected_element["subflowchart"], event))
                        self.selected_element["subflowchart"].canvas.bind("<ButtonRelease-1>", lambda event: self.end_connection(self.selected_element["subflowchart"], event))
                        self.selected_element["subflowchart"].canvas.bind("<Button-3>", lambda event: self.edit_connection(self.selected_element["subflowchart"], event))
                    else:
                        messagebox.showinfo("提示", "子流程圖已存在")

                tk.Button(func_dialog, text="開啟子流程圖", command=open_subflowchart).pack(pady=5)

                def save_function():
                    name = name_entry.get()
                    params = params_entry.get()
                    if name:
                        # 更新函式簽名
                        if self.selected_element["function_name"] in self.function_signatures:
                            del self.function_signatures[self.selected_element["function_name"]]
                        self.selected_element["function_name"] = name
                        self.selected_element["function_params"] = params
                        param_count = len([p for p in params.split(",") if p.strip()])
                        self.function_signatures[name] = param_count
                        label = f"def {name}({params})"
                        canvas.canvas.itemconfig(self.selected_element["label_id"], text=label[:20] + "..." if len(label) > 20 else label)
                        func_dialog.destroy()
                    else:
                        messagebox.showerror("錯誤", "函式名稱為必填")

                tk.Button(func_dialog, text="儲存", command=save_function).pack(pady=10)
            elif self.selected_element["type"] == "Start/End" and self.selected_element in canvas.elements[1:]:
                return_value = simpledialog.askstring("輸入", "輸入回傳值（例如：result）：", initialvalue=self.selected_element["return_value"])
                if return_value:
                    valid, error_msg = self.validate_code(return_value, canvas=canvas)
                    if valid:
                        self.selected_element["return_value"] = return_value
                        canvas.canvas.itemconfig(self.selected_element["label_id"], text=f"Return: {return_value}"[:20] + "..." if len(return_value) > 20 else f"Return: {return_value}")
                    else:
                        messagebox.showerror("錯誤", error_msg)
        elif action == "delete":
            canvas.canvas.delete(self.selected_element["id"])
            canvas.canvas.delete(self.selected_element["label_id"])
            connections_to_remove = [conn for conn in canvas.connections if conn[0] == self.selected_element or conn[1] == self.selected_element]
            for conn in connections_to_remove:
                canvas.canvas.delete(conn[2])
                canvas.canvas.delete(conn[3])
                canvas.connections.remove(conn)
            canvas.elements.remove(self.selected_element)
            if self.selected_element["type"] == "Function" and self.selected_element["subflowchart"]:
                self.selected_element["subflowchart"].window.destroy()
                if self.selected_element["function_name"] in self.function_signatures:
                    del self.function_signatures[self.selected_element["function_name"]]
        else:
            messagebox.showerror("錯誤", "無效操作")

    def edit_connection(self, canvas, event):
        for conn in canvas.connections:
            x1, y1, x2, y2 = canvas.canvas.coords(conn[2])
            if abs(event.x - (x1 + x2) / 2) < 30 and abs(event.y - (y1 + y2) / 2) < 30:
                self.save_state(canvas)
                action = simpledialog.askstring("連線操作", "輸入操作：edit_priority（編輯優先級，僅 Body 連線）或 delete（刪除連線）")
                if action == "edit_priority" and conn[4] == "Body":
                    priority_str = simpledialog.askstring("輸入", "編輯連線優先級（整數，較低值優先）：", initialvalue=str(conn[6]))
                    try:
                        priority = int(priority_str)
                        conn_list = list(conn)
                        conn_list[6] = priority
                        canvas.connections[canvas.connections.index(conn)] = tuple(conn_list)
                        canvas.canvas.itemconfig(conn[3], text=f"Body ({priority})")
                    except (ValueError, TypeError):
                        messagebox.showerror("錯誤", "優先級必須為整數")
                elif action == "delete":
                    canvas.canvas.delete(conn[2])
                    canvas.canvas.delete(conn[3])
                    canvas.connections.remove(conn)
                else:
                    messagebox.showerror("錯誤", "無效操作或連線類型不支援編輯優先級")
                break

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
            color = "blue" if self.connection_label.get() == "Body" else "red" if self.connection_label.get() == "Exit" else "green"
            canvas.temp_line = canvas.canvas.create_line(canvas.start_point[0], canvas.start_point[1], event.x, event.y, arrow=tk.LAST, fill=color)

    def end_connection(self, canvas, event):
        if canvas.start_point:
            for element in canvas.elements:
                if abs(event.x - element["x"]) < 50 and abs(event.y - element["y"]) < 30 and element != canvas.start_point[2]:
                    if self.connection_label.get() == "Call" and element["type"] != "Function":
                        messagebox.showerror("錯誤", "Call 連線必須指向函式元素")
                        break
                    if self.connection_label.get() in ["Body", "Exit"] and element["type"] == "Function":
                        messagebox.showerror("錯誤", "Body/Exit 連線不能指向函式元素")
                        break
                    color = "blue" if self.connection_label.get() == "Body" else "red" if self.connection_label.get() == "Exit" else "green"
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
                        call_params = simpledialog.askstring("輸入", f"輸入 {element['function_name']} 的呼叫參數（例如：x, 5）：", initialvalue="")
                        if call_params is None:
                            break
                        valid, error_msg = self.validate_function_call(element["function_name"], call_params)
                        if not valid:
                            messagebox.showerror("錯誤", error_msg)
                            break
                    self.save_state(canvas)
                    line_id = canvas.canvas.create_line(canvas.start_point[0], canvas.start_point[1], element["x"], element["y"], arrow=tk.LAST, fill=color, tags="connection")
                    label_id = canvas.canvas.create_text((canvas.start_point[0] + element["x"]) / 2, (canvas.start_point[1] + element["y"]) / 2, text=f"{self.connection_label.get()} ({priority})" if self.connection_label.get() == "Body" else self.connection_label.get())
                    canvas.connections.append((canvas.start_point[2], element, line_id, label_id, self.connection_label.get(), call_params, priority))
                    break
            if canvas.temp_line:
                canvas.canvas.delete(canvas.temp_line)
            canvas.start_point = None
            canvas.temp_line = None

    def update_connections(self, canvas):
        for conn in canvas.connections:
            canvas.canvas.delete(conn[2])
            canvas.canvas.delete(conn[3])
            start, end = conn[0], conn[1]
            color = "blue" if conn[4] == "Body" else "red" if conn[4] == "Exit" else "green"
            conn[2] = canvas.canvas.create_line(start["x"], start["y"], end["x"], end["y"], arrow=tk.LAST, fill=color, tags="connection")
            conn[3] = canvas.canvas.create_text((start["x"] + end["x"]) / 2, (start["y"] + end["y"]) / 2, text=f"{conn[4]} ({conn[6]})" if conn[4] == "Body" else conn[4])
            canvas.connections[canvas.connections.index(conn)] = (start, end, conn[2], conn[3], conn[4], conn[5], conn[6])

    def generate_code(self):
        self.code_text.delete(1.0, tk.END)
        code = "# 自動生成的 Python 程式碼\n\n"

        for lib in self.libraries:
            code += f"import {lib}\n"
        if self.libraries:
            code += "\n"

        def generate_function_code(element, indent_level=0):
            nonlocal code
            if element["type"] != "Function" or not element["function_name"]:
                return
            code += f"{'    ' * indent_level}def {element['function_name']}({element['function_params'] or ''}):\n"
            if element["subflowchart"]:
                indent_level += 1
                visited = set()
                def traverse(canvas, element, in_loop=False, loop_stack=None):
                    nonlocal code, indent_level
                    if loop_stack is None:
                        loop_stack = []
                    if element in visited:
                        return
                    visited.add(element)

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
                code += f"{'    ' * (indent_level + 1)}pass\n"

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
        indent = 1
        visited = set()
        def traverse(canvas, element, in_loop=False, loop_stack=None):
            nonlocal code, indent
            if loop_stack is None:
                loop_stack = []
            if element in visited:
                return
            visited.add(element)

            if element["type"] == "Process":
                call_connections = [conn for conn in canvas.connections if conn[0] == element and conn[4] == "Call"]
                if call_connections:
                    for conn in call_connections:
                        target = conn[1]
                        if target["type"] == "Function":
                            params = conn[5] or target["function_params"]
                            code += f"{'    ' * indent}{element['code'] or ''} = {target['function_name']}({params})\n"
                else:
                    code += f"{'    ' * indent}{element['code'] or 'pass'}\n"
            elif element["type"] == "Input":
                code += f"{'    ' * indent}{element['code'] or 'input()'}\n"
            elif element["type"] == "Output":
                code += f"{'    ' * indent}print({element['code'] or 'output'})\n"
            elif element["type"] == "Comment":
                code += f"{'    ' * indent}# {element['code'] or 'comment'}\n"
            elif element["type"] == "Decision":
                code += f"{'    ' * indent}if {element['condition'] or 'condition'}:\n"
                indent += 1
                true_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == element and conn[4] == "Body"], key=lambda c: canvas.connections[[c2[1] for c2 in canvas.connections if c2[0] == element and c2[4] == "Body"].index(c)][6])
                for branch in true_branches:
                    traverse(canvas, branch, in_loop, loop_stack)
                if not true_branches:
                    code += f"{'    ' * indent}pass\n"
                indent -= 1
                code += f"{'    ' * indent}else:\n"
                indent += 1
                false_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == element and conn[4] == "Exit"], key=lambda c: canvas.connections[[c2[1] for c2 in canvas.connections if c2[0] == element and c2[4] == "Exit"].index(c)][6])
                for branch in false_branches:
                    traverse(canvas, branch, in_loop, loop_stack)
                if not false_branches:
                    code += f"{'    ' * indent}pass\n"
                indent -= 1
            elif element["type"] == "Loop":
                if element["loop_type"] == "for":
                    code += f"{'    ' * indent}for {element['condition'] or 'i in range(5)'}:\n"
                else:
                    code += f"{'    ' * indent}while {element['condition'] or 'True'}:\n"
                indent += 1
                loop_stack.append(element)
                body_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == element and conn[4] == "Body"], key=lambda c: canvas.connections[[c2[1] for c2 in canvas.connections if c2[0] == element and c2[4] == "Body"].index(c)][6])
                for branch in body_branches:
                    traverse(canvas, branch, True, loop_stack)
                if not body_branches:
                    code += f"{'    ' * indent}pass\n"
                indent -= 1
                loop_stack.pop()
            elif element["type"] == "Start/End" and element != canvas.elements[0]:
                if not in_loop:
                    if element["return_value"]:
                        code += f"{'    ' * indent}return {element['return_value']}\n"
                    else:
                        code += f"{'    ' * indent}return\n"

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
        self.code_text.insert(tk.END, code)

    def provide_error_suggestion(self, exception, element=None, connection=None):
        suggestion = ""
        if isinstance(exception, NameError):
            var_name = str(exception).split("'")[1]
            suggestion = f"建議：變數 '{var_name}' 未定義。請檢查是否在之前的元素中正確宣告或賦值，或確認拼寫正確。"
            if element and element["type"] in ["Process", "Output", "Decision", "Loop"]:
                suggestion += f"\n當前元素程式碼：{element.get('code') or element.get('condition')}"
        elif isinstance(exception, TypeError):
            suggestion = f"建議：類型錯誤，可能使用了不兼容的資料類型（例如對字串執行數學運算）。請檢查變數類型或運算操作。"
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
            self.output_text.insert(tk.END, f"語法錯誤：{str(e)}\n{suggestion}\n")
            self.output_text.config(state="disabled")
            return

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

            error_item = None
            error_is_connection = False

            try:
                if element["type"] == "Process":
                    call_connections = [conn for conn in canvas.connections if conn[0] == element and conn[4] == "Call"]
                    if call_connections:
                        for conn in call_connections:
                            target = conn[1]
                            if target["type"] == "Function" and target["subflowchart"]:
                                self.execution_path.append((canvas, conn))
                                params = conn[5] or target["function_params"]
                                try:
                                    eval(f"{target['function_name']}({params})", globals_dict)
                                    sub_error_item, sub_error_is_connection = instrument_code(target["subflowchart"], target["subflowchart"].elements[0], in_loop, loop_stack, globals_dict)
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
                            sub_error_item, sub_error_is_connection = instrument_code(canvas, branch, in_loop, loop_stack, globals_dict)
                            if sub_error_item:
                                error_item = sub_error_item
                                error_is_connection = sub_error_is_connection
                                raise Exception("分支執行錯誤")
                        except Exception as e:
                            error_item = conn
                            error_is_connection = True
                            raise e
                elif element["type"] == "Loop":
                    loop_stack.append(element)
                    if element["loop_type"] == "for":
                        loop_iter = eval(f"list({element['condition'].split(' in ')[1]})", globals_dict)
                        loop_var = element["condition"].split(' in ')[0].strip()
                        for val in loop_iter:
                            globals_dict[loop_var] = val
                            self.execution_path.append((canvas, element))
                            body_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == element and conn[4] == "Body"], key=lambda c: canvas.connections[[c2[1] for c2 in canvas.connections if c2[0] == element and c2[4] == "Body"].index(c)][6])
                            for branch in body_branches:
                                conn = next(c for c in canvas.connections if c[0] == element and c[1] == branch and c[4] == "Body")
                                self.execution_path.append((canvas, conn))
                                try:
                                    sub_error_item, sub_error_is_connection = instrument_code(canvas, branch, True, loop_stack, globals_dict)
                                    if sub_error_item:
                                        error_item = sub_error_item
                                        error_is_connection = sub_error_is_connection
                                        raise Exception("迴圈執行錯誤")
                                except Exception as e:
                                    error_item = conn
                                    error_is_connection = True
                                    raise e
                    else:  # while loop
                        max_iterations = 100
                        iteration = 0
                        while evaluate_condition(element["condition"], globals_dict) and iteration < max_iterations:
                            self.execution_path.append((canvas, element))
                            body_branches = sorted([conn[1] for conn in canvas.connections if conn[0] == element and conn[4] == "Body"], key=lambda c: canvas.connections[[c2[1] for c2 in canvas.connections if c2[0] == element and c2[4] == "Body"].index(c)][6])
                            for branch in body_branches:
                                conn = next(c for c in canvas.connections if c[0] == element and c[1] == branch and c[4] == "Body")
                                self.execution_path.append((canvas, conn))
                                try:
                                    sub_error_item, sub_error_is_connection = instrument_code(canvas, branch, True, loop_stack, globals_dict)
                                    if sub_error_item:
                                        error_item = sub_error_item
                                        error_is_connection = sub_error_is_connection
                                        raise Exception("迴圈執行錯誤")
                                except Exception as e:
                                    error_item = conn
                                    error_is_connection = True
                                    raise e
                            iteration += 1
                    loop_stack.pop()
                elif element["type"] == "Start/End" and element != canvas.elements[0]:
                    pass

                if not in_loop or (in_loop and element["type"] not in ["Decision", "Loop"]):
                    next_elements = sorted([conn[1] for conn in canvas.connections if conn[0] == element and conn[4] == "Body"], key=lambda c: canvas.connections[[c2[1] for c2 in canvas.connections if c2[0] == element and c2[4] == "Body"].index(c)][6])
                    for next_element in next_elements:
                        conn = next(c for c in canvas.connections if c[0] == element and c[1] == next_element and c[4] == "Body")
                        self.execution_path.append((canvas, conn))
                        try:
                            sub_error_item, sub_error_is_connection = instrument_code(canvas, next_element, in_loop, loop_stack, globals_dict)
                            if sub_error_item:
                                error_item = sub_error_item
                                error_is_connection = sub_error_is_connection
                                raise Exception("後續執行錯誤")
                        except Exception as e:
                            error_item = conn
                            error_is_connection = True
                            raise e
                    if in_loop and loop_stack and not next_elements:
                        exit_elements = sorted([conn[1] for conn in canvas.connections if conn[0] == loop_stack[-1] and conn[4] == "Exit"], key=lambda c: canvas.connections[[c2[1] for c2 in canvas.connections if c2[0] == loop_stack[-1] and c2[4] == "Exit"].index(c)][6])
                        for exit_element in exit_elements:
                            conn = next(c for c in canvas.connections if c[0] == loop_stack[-1] and c[1] == exit_element and c[4] == "Exit")
                            self.execution_path.append((canvas, conn))
                            try:
                                sub_error_item, sub_error_is_connection = instrument_code(canvas, exit_element, False, loop_stack, globals_dict)
                                if sub_error_item:
                                    error_item = sub_error_item
                                    error_is_connection = sub_error_is_connection
                                    raise Exception("退出執行錯誤")
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
        sys.stdout = redirected_output

        try:
            if self.main_canvas.elements:
                self.execution_path = []
                error_item, error_is_connection = instrument_code(self.main_canvas, self.main_canvas.elements[0])
            exec(code, self.execution_globals)
            for canvas, item in self.execution_path:
                if isinstance(item, tuple):
                    canvas.highlight_connection(item)
                else:
                    canvas.highlight_element(item)
            output = redirected_output.getvalue()
            self.output_text.insert(tk.END, output or "無輸出")
        except Exception as e:
            error_msg = f"錯誤：{str(e)}\n詳細信息：\n{''.join(traceback.format_tb(e.__traceback__))}"
            suggestion = self.provide_error_suggestion(e, error_item if not error_is_connection else None, error_item if error_is_connection else None)
            self.output_text.insert(tk.END, f"{error_msg}\n{suggestion}")
            if error_item:
                canvas.highlight_error(error_item, error_is_connection)
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
                    "return_value": element["return_value"],
                    "subflowchart": serialize_canvas(element["subflowchart"]) if element["subflowchart"] else None
                }
                elements_data.append(elem_data)
            connections_data = [(canvas.elements.index(c[0]), canvas.elements.index(c[1]), c[4], c[5], c[6]) for c in canvas.connections]
            return {"elements": elements_data, "connections": connections_data}

        flowchart_data = {
            "main_canvas": serialize_canvas(self.main_canvas),
            "libraries": self.libraries,
            "defined_variables": list(self.defined_variables),
            "function_signatures": self.function_signatures
        }
        with open("flowchart.json", "w") as f:
            json.dump(flowchart_data, f)
        messagebox.showinfo("成功", "流程圖已儲存")

    def load_flowchart(self):
        if os.path.exists("flowchart.json"):
            with open("flowchart.json", "r") as f:
                data = json.load(f)
            self.clear_canvas()

            self.libraries = data.get("libraries", [])
            self.defined_variables = set(data.get("defined_variables", []))
            self.function_signatures = data.get("function_signatures", {})

            def load_canvas(canvas_data, parent_canvas, is_subflowchart=False, function_element=None):
                new_canvas = FlowchartCanvas(self.root, "載入流程圖" if not is_subflowchart else f"函式：{function_element['function_name']}", is_subflowchart, function_element)
                new_canvas.canvas.bind("<Button-1>", lambda event: self.start_connection(new_canvas, event))
                new_canvas.canvas.bind("<B1-Motion>", lambda event: self.draw_connection(new_canvas, event))
                new_canvas.canvas.bind("<ButtonRelease-1>", lambda event: self.end_connection(new_canvas, event))
                new_canvas.canvas.bind("<Button-3>", lambda event: self.edit_connection(new_canvas, event))

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
                    new_elem["return_value"] = elem["return_value"]
                    if elem["subflowchart"]:
                        new_elem["subflowchart"] = load_canvas(elem["subflowchart"], new_canvas, True, new_elem)
                    new_canvas.canvas.coords(new_elem["id"], elem["x"]-50, elem["y"]-20, elem["x"]+50, elem["y"]+20)
                    new_canvas.canvas.coords(new_elem["label_id"], elem["x"], elem["y"])
                    label_text = elem["code"] or elem["condition"] or (f"def {elem['function_name']}({elem['function_params']})" if elem["type"] == "Function" else elem["type"])
                    if elem["type"] == "Start/End" and elem["return_value"]:
                        label_text = f"Return: {elem['return_value']}"
                    new_canvas.canvas.itemconfig(new_elem["label_id"], text=label_text[:20] + "..." if len(label_text) > 20 else label_text)

                for conn in canvas_data["connections"]:
                    start, end = new_canvas.elements[conn[0]], new_canvas.elements[conn[1]]
                    color = "blue" if conn[2] == "Body" else "red" if conn[2] == "Exit" else "green"
                    line_id = new_canvas.canvas.create_line(start["x"], start["y"], end["x"], end["y"], arrow=tk.LAST, fill=color, tags="connection")
                    label_id = new_canvas.canvas.create_text((start["x"] + end["x"]) / 2, (start["y"] + end["y"]) / 2, text=f"{conn[2]} ({conn[4]})" if conn[2] == "Body" else conn[2])
                    new_canvas.connections.append((start, end, line_id, label_id, conn[2], conn[3], conn[4]))

                return new_canvas

            self.main_canvas = load_canvas(data["main_canvas"], None)
            messagebox.showinfo("成功", "流程圖已載入")

    def clear_canvas(self):
        self.main_canvas.canvas.delete("all")
        self.main_canvas.elements = []
        self.main_canvas.connections = []
        self.libraries = []
        self.defined_variables.clear()
        self.function_signatures.clear()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.code_text.delete(1.0, tk.END)
        self.output_text.config(state="normal")
        self.output_text.delete(1.0, tk.END)
        self.output_text.config(state="disabled")

if __name__ == "__main__":
    root = tk.Tk()
    app = FlowchartToCodeGUI(root)
    root.mainloop()