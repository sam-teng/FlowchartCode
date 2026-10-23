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
        self.selected_element = None
        self.start_x, self.start_y, self.end_x, self.end_y = None, None, None, None
        self.dragging = False

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
        try:
            self.root = root
            self.root.title("流程圖轉程式碼工具")
            self.root.geometry("1200x800")
        except Exception as e:
            messagebox.showerror("錯誤", f"初始化失敗：{str(e)}")
            sys.exit(1)
        
        self.dragging = False
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
        self.syntax_sugar_templates = {
            "列表推導式": "[x*2 for x in iterable]",
            "字典推導式": "{k: v**2 for k, v in dict.items()}",
            "裝飾器": "@decorator\ndef func(): pass",
            "上下文管理器": "with open('file.txt') as f:\n    data = f.read()"
        }

        self.create_widgets()

    def create_widgets(self):
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
            #canvas.canvas.bind("<Button-1>", lambda event: self.handle_canvas_click(event, canvas))
            #canvas.canvas.bind("<B1-Motion>", lambda event: self.handle_canvas_drag(event, canvas))
            canvas.canvas.bind("<Button-1>", lambda event: self.handle_click_start(event, canvas))
            canvas.canvas.bind("<B1-Motion>", lambda event: self.handle_drag_motion(event, canvas))
            canvas.canvas.bind("<ButtonRelease-1>", lambda event: self.handle_release(event, canvas))
            canvas.canvas.bind("<Button-2>", lambda event: self.show_context_menu(event, canvas))
            canvas.canvas.bind("<Button-3>", lambda event: self.show_context_menu(event, canvas))
        except Exception as e:
            messagebox.showerror("錯誤", f"綁定事件失敗：{str(e)}")

    def handle_canvas_click(self, event, canvas):
        canvas.start_x, canvas.start_y = event.x, event.y
        #canvas.selected_element = None
        #for elem in canvas.elements:
        #    if abs(elem["x"] - event.x) < 20 and abs(elem["y"] - event.y) < 20:
        #        canvas.selected_element = elem
        #        break
        #if canvas.selected_element:
        #    self.start_connection(event, canvas)
        clicked_element = None
        for elem in canvas.elements:
            if abs(elem["x"] - event.x) < 20 and abs(elem["y"] - event.y) < 20:
                clicked_element = elem
                break

        if clicked_element:
            canvas.selected_element = clicked_element
            
        else:
            self.start_connection(event, canvas)
            pass

    def handle_click_start(self, event, canvas):
        canvas.dragging = False
        canvas.selected_element = None
        for elem in canvas.elements:
            if abs(event.x - elem["x"]) < 20 and abs(event.y - elem["y"]) < 20:
                canvas.selected_element = elem
                canvas.dragging = True
                return
        # 沒選到元素，改為開始畫線
        self.start_connection(event, canvas)


    def handle_canvas_drag(self, event, canvas):
        if canvas.selected_element:
            for element in canvas.elements:
                if element["id"] == canvas.selected_element["id"]:
                    element["x"], element["y"] = event.x, event.y
                    self.update_element_coords(element, canvas)
                    self.update_connections(canvas)
                    label_text = self.get_label_text(element)
                    canvas.canvas.itemconfig(element["label_id"], text=label_text[:20] + "..." if len(label_text) > 20 else label_text)
                    break
                #canvas.selected_element["x"] = event.x
                #canvas.selected_element["y"] = event.y
                #self.update_element_coords(canvas.selected_element, canvas)
                #self.update_connections(canvas)
                #label_text = self.get_label_text(canvas.selected_element)
                #canvas.canvas.itemconfig(canvas.selected_element["label_id"], text=label_text[:20] + "..." if len(label_text) > 20 else label_text)
        #elif hasattr(canvas, "start_x"):
        elif canvas.start_x is not None and canvas.start_y is not None:
            self.draw_connection(event, canvas)
            #end_elem = None
            #for elem in canvas.elements:
            #    if abs(elem["x"] - event.x) < 20 and abs(elem["y"] - event.y) < 20:
            #        end_elem = elem
            #        break
            #if end_elem and canvas.selected_element and end_elem != canvas.selected_element:
            #    self.end_connection(event, canvas)
            #    color = "#5E81AC" if self.connection_var.get() == "Body" else "#BF616A" if self.connection_var.get() == "Exit" else "#A3BE8C"
            #    line_id = canvas.canvas.create_line(canvas.start_x, canvas.start_y, end_elem["x"], end_elem["y"], arrow=tk.LAST, fill=color, tags="connection")
            #    label_id = canvas.canvas.create_text((canvas.start_x + end_elem["x"]) / 2, (canvas.start_y + end_elem["y"]) / 2, text=self.connection_var.get(), font=("Arial", 8))
            #    canvas.connections.append((canvas.selected_element, end_elem, line_id, label_id, self.connection_var.get(), "", 1))
            #    canvas.start_x, canvas.start_y = None, None
            #    canvas.selected_element = None
                
    """
    def handle_drag_motion(self, event, canvas):
        if canvas.dragging and canvas.selected_element:
            canvas.selected_element["x"] = event.x
            canvas.selected_element["y"] = event.y
            self.update_element_coords(canvas.selected_element, canvas)
            self.update_connections(canvas)
        elif canvas.temp_line:
            # 畫線時更新暫時連線線條
            self.draw_connection(event, canvas)   
    """
    
    def handle_release(self, event, canvas):
        if canvas.dragging:
            canvas.dragging = False
            canvas.selected_element = None
        if canvas.temp_line:
            self.end_connection(event, canvas)
        self.dragging = False

    def update_element_coords(self, element, canvas):
        if element["shape_id"]:
            if element["type"] == "Process":
                canvas.canvas.coords(element["shape_id"], element["x"] - 50, element["y"] - 20, element["x"] + 50, element["y"] + 20)
            elif element["type"] == "Decision":
                canvas.canvas.coords(element["shape_id"], element["x"], element["y"] - 30, element["x"] + 50, element["y"], element["x"], element["y"] + 30, element["x"] - 50, element["y"])
            elif element["type"] == "Loop":
                canvas.canvas.coords(element["shape_id"], element["x"] - 40, element["y"] - 20, element["x"] + 40, element["y"] + 20)
            elif element["type"] == "Start/End":
                canvas.canvas.coords(element["shape_id"], element["x"] - 40, element["y"] - 20, element["x"] + 40, element["y"] + 20)
            elif element["type"] == "Input":
                canvas.canvas.coords(element["shape_id"], element["x"] - 50, element["y"] - 20, element["x"] + 50, element["y"] - 20, element["x"] + 40, element["y"] + 20, element["x"] - 40, element["y"] + 20)
            elif element["type"] == "Output":
                canvas.canvas.coords(element["shape_id"], element["x"] - 50, element["y"] - 20, element["x"] + 50, element["y"] - 20, element["x"] + 60, element["y"] + 20, element["x"] - 60, element["y"] + 20)
            elif element["type"] == "Function":
                canvas.canvas.coords(element["shape_id"], element["x"] - 50, element["y"] - 20, element["x"] + 50, element["y"] + 20)
            elif element["type"] == "Class":
                canvas.canvas.coords(element["shape_id"], element["x"] - 60, element["y"] - 30, element["x"] + 60, element["y"] + 30)
            canvas.canvas.coords(element["label_id"], element["x"], element["y"])

        for conn in canvas.connections:
            start, end, line_id, label_id, conn_type, call_params, priority = conn
            if (start == element or end == element) and not start and not end:
                canvas.canvas.coords(line_id, start["x"], start["y"], end["x"], end["y"])
                canvas.canvas.coords(label_id, (start["x"] + end["x"]) / 2, (start["y"] + end["y"]) / 2)

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

    """
    def start_connection(self, event, canvas):
        # Clear any existing temporary line
        if canvas.temp_line:
            canvas.canvas.delete(canvas.temp_line)
            canvas.temp_line = None
        canvas.start_x, canvas.start_y, canvas.selected_element = None, None, None
        for element in canvas.elements:
            if abs(event.x - element["x"]) < 60 and abs(event.y - element["y"]) < 40:
                canvas.start_x, canvas.start_y, canvas.selected_element = (element["x"], element["y"], element)
                break

    def start_connection(self, event, canvas):
        canvas.start_x = None
        canvas.start_y = None
        canvas.selected_element = None
        canvas.temp_line = None

        # 嘗試找起點元素
        for element in canvas.elements:
            if abs(event.x - element["x"]) < 20 and abs(event.y - element["y"]) < 20:
                canvas.start_x = element["x"]
                canvas.start_y = element["y"]
                canvas.selected_element = element
                break

        if canvas.selected_element:
            # 建立暫時箭頭
            canvas.temp_line = canvas.canvas.create_line(
                canvas.start_x, canvas.start_y, event.x, event.y,
                arrow=tk.LAST, dash=(4, 2), fill="gray"
            )


    def draw_connection(self, event, canvas):
        if canvas.start_x and canvas.start_y:
            if canvas.temp_line:
                canvas.canvas.delete(canvas.temp_line)
            color = "#5E81AC" if self.connection_var.get() == "Body" else "#BF616A" if self.connection_var.get() == "Exit" else "#A3BE8C"
            canvas.temp_line = canvas.canvas.create_line(canvas.start_x, canvas.start_y, event.x, event.y, arrow=tk.LAST, fill=color)

    def draw_connection(self, event, canvas):
        if canvas.temp_line:
            canvas.canvas.coords(canvas.temp_line, canvas.start_x, canvas.start_y, event.x, event.y)

    def end_connection(self, event, canvas):
        if not canvas.start_x or not canvas.start_y or not canvas.selected_element:
            if canvas.temp_line:
                canvas.canvas.delete(canvas.temp_line)
                canvas.temp_line = None
            return

        end_element = None
                    
        for element in canvas.elements:
            #x1, y1 = canvas.start_x, canvas.start_y
            #x2, y2 = element["x"], element["y"]
            #dist_x, dist_y = abs(-event.x - (x1 - x2) / 2), abs(-event.y - (y1 - y2) / 2)
            #if dist_x < 30 and dist_y < 30:
            if abs(event.x - element["x"]) < 60 and abs(event.y - element["y"]) < 40 and not canvas.selected_element is element:
                canvas.end_x, canvas.end_y, end_element = (element["x"], element["y"], element)
                break

        if end_element:
            # Prevent self-connection
            if canvas.selected_element == end_element:
                messagebox.showerror("錯誤", "不能連接到相同元素")
                self._reset_connection_state(canvas)
                return

            # Check for duplicate connection
            for conn in canvas.connections:
                if (conn[0] == canvas.selected_element and conn[1] == end_element and conn[4] == self.connection_var.get()):
                    messagebox.showerror("錯誤", f"已經存在相同的 {self.connection_var.get()} 連線")
                    self._reset_connection_state(canvas)
                    return

            conn_type = self.connection_var.get()
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

                self.save_state(canvas)
                try:
                    line_id = canvas.canvas.create_line(canvas.start_x, canvas.start_y, end_element["x"], end_element["y"], arrow=tk.LAST, fill=color, tags="connection")
                    label_id = canvas.canvas.create_text((canvas.start_x + end_element["x"]) / 2, (canvas.start_y + end_element["y"]) / 2, text=f"{conn_type} ({priority})" if conn_type == "Body" else conn_type, font=("Arial", 8))
                    canvas.connections.append((canvas.selected_element, end_element, line_id, label_id, conn_type, call_params, priority))
                except Exception as e:
                    messagebox.showerror("錯誤", f"連線失敗：{str(e)}")

        self._reset_connection_state(canvas)

    def end_connection(self, event, canvas):
        if canvas.start_x is None or canvas.start_y is None or canvas.selected_element is None:
            if canvas.temp_line:
                canvas.canvas.delete(canvas.temp_line)
                canvas.temp_line = None
            return

        # 嘗試找終點元素
        end_element = None
        for element in canvas.elements:
            if abs(event.x - element["x"]) < 60 and abs(event.y - element["y"]) < 40:
                end_element = element
                break

        if end_element and end_element != canvas.selected_element:
            conn_type = self.connection_var.get()
            call_params, priority = "", ""
            if conn_type == "Call":
                call_params = simpledialog.askstring("輸入參數", "請輸入呼叫的參數（以逗號分隔）：") or ""
            elif conn_type == "Body":
                priority = simpledialog.askstring("輸入優先級", "請輸入流程優先級：") or ""

            line_id = canvas.canvas.create_line(
                canvas.selected_element["x"], canvas.selected_element["y"],
                end_element["x"], end_element["y"],
                arrow=tk.LAST, width=2, fill="black"
            )

            label_x = (canvas.selected_element["x"] + end_element["x"]) / 2
            label_y = (canvas.selected_element["y"] + end_element["y"]) / 2
            label_text = f"{conn_type} ({priority})" if conn_type == "Body" else conn_type
            label_id = canvas.canvas.create_text(label_x, label_y, text=label_text, font=("Arial", 8))

            canvas.connections.append([
                canvas.selected_element, end_element, line_id, label_id, conn_type, call_params, priority
            ])

        # 清理暫時線
        if canvas.temp_line:
            canvas.canvas.delete(canvas.temp_line)
            canvas.temp_line = None

        # 清除選取
        canvas.selected_element = None
        canvas.start_x = None
        canvas.start_y = None
    """
    def handle_click_start(self, event, canvas):
        # 清除之前的選中狀態
        canvas.selected_element = None
        canvas.dragging = False
        
        # 檢查是否點擊到元素
        clicked_element = None
        for elem in canvas.elements:
            if abs(elem["x"] - event.x) < 20 and abs(elem["y"] - event.y) < 15:
                clicked_element = elem
                break
        
        if clicked_element:
            canvas.selected_element = clicked_element
            #self.start_connection(event, canvas)
        elif not self.dragging:
            # 未點擊元素，允許開始畫線
            self.start_connection(event, canvas)

    def handle_drag_motion(self, event, canvas):
        # 檢查是否點擊到元素以啟動拖曳
        for elem in canvas.elements:
            if abs(event.x - elem["x"]) < 20 and abs(event.y - elem["y"]) < 15:
                elem["x"] = event.x
                elem["y"] = event.y
                self.update_element_coords(elem, canvas)
                canvas.selected_element = elem
                self.update_connections(canvas)
                canvas.dragging = True
                return
        # 未點擊元素，啟動連線
        self.draw_connection(event, canvas)

    def start_connection(self, event, canvas):
        # 重置連線狀態
        self._reset_connection_state(canvas)
        
        # 檢查是否點擊到元素作為連線起點
        for element in canvas.elements:
            if self.dragging:
                pass#break
            if abs(event.x - element["x"]) < 60 and abs(event.y - element["y"]) < 40 and not self.dragging:
                canvas.start_x = element["x"]
                canvas.start_y = element["y"]
                canvas.selected_element = element
                self.dragging = True
                canvas.temp_line = canvas.canvas.create_line(
                canvas.start_x, canvas.start_y, event.x, event.y,
                arrow=tk.LAST, fill="gray"
            )
        #
        if self.dragging and canvas.start_x is not None and canvas.start_y is not None:
            #canvas.canvas.delete(canvas.temp_line)
            
            pass

    def start_connection(self, event, canvas):
        canvas.start_x = None
        canvas.start_y = None
        canvas.selected_element = None
        canvas.temp_line = None

        # 嘗試找起點元素
        for element in canvas.elements:
            if abs(event.x - element["x"]) < 60 and abs(event.y - element["y"]) < 40:
                canvas.start_x = element["x"]
                canvas.start_y = element["y"]
                canvas.selected_element = element
                break

        if canvas.selected_element:
            # 建立暫時箭頭
            canvas.temp_line = canvas.canvas.create_line(
                canvas.start_x, canvas.start_y, event.x, event.y,
                arrow=tk.LAST, dash=(4, 2), fill="gray"
            )

    def draw_connection(self, event, canvas):
        # 創建臨時線
        #color = "#5E81AC" if self.connection_var.get() == "Body" else "#BF616A" if self.connection_var.get() == "Exit" else "#A3BE8C"

        #canvas.temp_line = canvas.canvas.create_line(canvas.start_x, canvas.start_y, event.x, event.y, arrow=tk.LAST, dash=(4, 2), tags="temp_line", fill=color)
        canvas.canvas.delete(canvas.temp_line)
        if canvas.selected_element:
            # 建立暫時箭頭
            canvas.temp_line = canvas.canvas.create_line(
                canvas.start_x, canvas.start_y, event.x, event.y,
                arrow=tk.LAST, dash=(4, 2), fill="gray"
            )
        self.dragging = True
        # 更新臨時連線線條的終點座標
        if canvas.temp_line and self.dragging:# and canvas.start_x is not None and canvas.start_y is not None:
            canvas.canvas.coords(canvas.temp_line, canvas.start_x, canvas.start_y, event.x, event.y)
            pass

    def end_connection(self, event, canvas):
        # 如果沒有起點或選中元素，清除臨時線並退出
        if canvas.start_x is None or canvas.start_y is None or canvas.selected_element is None:
            self._reset_connection_state(canvas)
            return

        # 檢查是否點擊到終點元素
        end_element = None
        for element in canvas.elements:
            if abs(event.x - element["x"]) < 60 and abs(event.y - element["y"]) < 40:
                end_element = element
                self.dragging = False
                break

        if end_element and end_element != canvas.selected_element:
            # 防止自連線
            if canvas.selected_element == end_element:
                messagebox.showerror("錯誤", "不能連接到相同元素")
                self._reset_connection_state(canvas)
                return

            # 檢查是否已存在相同連線
            conn_type = self.connection_var.get()
            for conn in canvas.connections:
                if (conn[0] == canvas.selected_element and 
                    conn[1] == end_element and 
                    conn[4] == conn_type):
                    messagebox.showerror("錯誤", f"已經存在相同的 {conn_type} 連線")
                    self._reset_connection_state(canvas)
                    return

            # 驗證連線類型
            if conn_type == "Call" and end_element["type"] != "Function":
                messagebox.showerror("錯誤", "Call 連線必須指向函式元素")
                self._reset_connection_state(canvas)
                return
            elif conn_type in ["Body", "Exit"] and end_element["type"] == "Function":
                messagebox.showerror("錯誤", "Body/Exit 連線不能指向函式元素")
                self._reset_connection_state(canvas)
                return

            # 處理連線參數和優先級
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
            elif conn_type == "Call":
                call_params = simpledialog.askstring("輸入", f"輸入 {end_element['function_name']} 的呼叫參數（例如：x, 5）：", initialvalue="")
                if call_params is None:
                    self._reset_connection_state(canvas)
                    return
                valid, error_msg = canvas.validate_function_call(end_element["function_name"], call_params)
                if not valid:
                    messagebox.showerror("錯誤", error_msg)
                    self._reset_connection_state(canvas)
                    return

            # 儲存當前狀態以支援撤銷
            self.save_state(canvas)

            # 創建正式連線
            try:
                color = "#5E81AC" if conn_type == "Body" else "#BF616A" if conn_type == "Exit" else "#A3BE8C"
                line_id = canvas.canvas.create_line(
                    canvas.selected_element["x"], canvas.selected_element["y"],
                    end_element["x"], end_element["y"],
                    arrow=tk.LAST, fill=color, tags="connection"
                )
                label_text = f"{conn_type} ({priority})" if conn_type == "Body" else conn_type
                label_id = canvas.canvas.create_text(
                    (canvas.selected_element["x"] + end_element["x"]) / 2,
                    (canvas.selected_element["y"] + end_element["y"]) / 2,
                    text=label_text, font=("Arial", 8)
                )
                canvas.connections.append((
                    canvas.selected_element, end_element, line_id, label_id, conn_type, call_params, priority
                ))
            except Exception as e:
                messagebox.showerror("錯誤", f"連線失敗：{str(e)}")

        # 重置連線狀態
        self._reset_connection_state(canvas)
    
    def _reset_connection_state(self, canvas):
        if canvas.temp_line:
            canvas.canvas.delete(canvas.temp_line)
            canvas.temp_line = None
        canvas.start_x, canvas.start_y, canvas.end_x, canvas.end_y, canvas.selected_element = None, None, None, None, None

    def edit_connection(self, connection, canvas):
        try:
            edit_dialog = tk.Toplevel(self.root)
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

                valid, error_msg = self.validate_connection_params(new_type, new_params, new_priority, end_elem)
                if not valid:
                    messagebox.showerror("錯誤", error_msg)
                    return

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
                try:
                    ast.parse(f"func({call_params})")
                except SyntaxError as e:
                    return False, f"呼叫參數語法錯誤：{str(e)}"
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

    def delete_connection(self, connection, canvas):
        try:
            start_elem, end_elem, line_id, label_id, _, _, _ = connection
            canvas.canvas.delete(line_id)
            canvas.canvas.delete(label_id)
            canvas.connections.remove(connection)
        except Exception as e:
            messagebox.showerror("錯誤", f"刪除連線失敗：{str(e)}")

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

    def save_state(self, canvas):
        #state = {
        #    "elements": canvas.elements.copy(),
        #    "connections": canvas.connections.copy()
        #}
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
            self.update_connections(canvas)
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
        except SyntaxError:
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
        except SyntaxError:
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
            file_path = filedialog.askopenfilename(filetypes=[("Python 檔案", "*.py")])
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
                    messagebox.showinfo("成功", f"成功從 {file_path} 匯入模組 '{module_name}'")
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
            #name_entry = ttk.Entry(tree)
            #name_entry.insert(0, "")
            #name_entry.pack(pady=5)
            #name = name_entry.get().strip()
            #if not name or not name.isidentifier():
            #    messagebox.showerror("錯誤", "變數名稱無效，必須是有效的 Python 識別字。")
            #    return
            
            #value_entry = ttk.Entry(tree)
            #value_entry.insert(0, "")
            #value_entry.pack(pady=5)
            #value = value_entry.get().strip()
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
            if not messagebox.askyesno("警告", "載入 .pickle 檔案可能有安全風險，是否繼續？"):
                return

        try:
            if file_path.endswith(".pickle"):
                with open(file_path, "rb") as f:
                    data = pickle.load(f)
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

            self.clear_canvas()
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

            # 載入元素
            for elem_data in data.get("elements", []):
                element = {
                    "id": elem_data["id"],
                    "type": elem_data["type"],
                    "x": elem_data["x"],
                    "y": elem_data["y"],
                    "code": elem_data.get("code", ""),
                    "condition": elem_data.get("condition"),
                    "loop_type": elem_data.get("loop_type"),
                    "function_name": elem_data.get("function_name"),
                    "function_params": elem_data.get("function_params"),
                    "is_lambda": elem_data.get("is_lambda", False),
                    "return_value": elem_data.get("return_value"),
                    "class_name": elem_data.get("class_name"),
                    "parent_class": elem_data.get("parent_class"),
                    "attributes": elem_data.get("attributes"),
                    "methods": elem_data.get("methods", []),
                    "decorator": elem_data.get("decorator"),
                    "subflowchart": None,
                    "shape_id": None,
                    "label_id": None
                }

                # 創建畫布元素
                x, y, elem_type = element["x"], element["y"], element["type"]
                if elem_type == "Process":
                    shape_id = self.main_canvas.canvas.create_rectangle(x - 50, y - 20, x + 50, y + 20, fill="lightblue")
                elif elem_type == "Decision":
                    shape_id = self.main_canvas.canvas.create_polygon(x, y - 30, x + 50, y, x, y + 30, x - 50, y, fill="lightgreen")
                elif elem_type == "Loop":
                    shape_id = self.main_canvas.canvas.create_oval(x - 40, y - 20, x + 40, y + 20, fill="lightyellow")
                elif elem_type == "Start/End":
                    shape_id = self.main_canvas.canvas.create_oval(x - 40, y - 20, x + 40, y + 20, fill="pink")
                elif elem_type == "Input":
                    shape_id = self.main_canvas.canvas.create_polygon(x - 50, y - 20, x + 50, y - 20, x + 40, y + 20, x - 15, y + 10, fill="lightgray")
                elif elem_type == "Output":
                    shape_id = self.main_canvas.canvas.create_polygon(x - 50, y - 20, x + 50, y - 20, x + 60, y + 20, x - 10, y + 10, fill="lightcoral")
                elif elem_type == "Function":
                    shape_id = self.main_canvas.canvas.create_rectangle(x - 50, y - 20, x + 50, y + 20, fill="lightpurple")
                elif elem_type == "Class":
                    shape_id = self.main_canvas.canvas.create_rectangle(x - 60, y - 30, x + 60, y + 30, fill="lightcyan")
                elif elem_type == "Comment":
                    shape_id = self.main_canvas.canvas.create_text(x, y, text="// Comment", font=("Arial", 8), fill="gray")

                label_text = self.get_label_text(element)
                label_id = self.main_canvas.canvas.create_text(x, y, text=label_text[:20] + "..." if len(label_text) > 20 else label_text, font=("Arial", 8))
                element["shape_id"] = shape_id
                element["label_id"] = label_id
                self.main_canvas.elements.append(element)

                # 載入子流程圖
                if elem_data.get("subflowchart"):
                    element["subflowchart"] = FlowchartCanvas(self.root, f"函式/方法：{element['type']}", is_subflowchart=True, function_element=element)
                    self.bind_canvas_events(element["subflowchart"])
                    for sub_elem_data in elem_data["subflowchart"]["elements"]:
                        sub_element = {
                            "id": sub_elem_data["id"],
                            "type": sub_elem_data["type"],
                            "x": sub_elem_data["x"],
                            "y": sub_elem_data["y"],
                            "code": sub_elem_data.get("code", ""),
                            "condition": sub_elem_data.get("condition"),
                            "loop_type": sub_elem_data.get("loop_type"),
                            "function_name": sub_elem_data.get("function_name"),
                            "function_params": sub_elem_data.get("function_params"),
                            "is_lambda": sub_elem_data.get("is_lambda", False),
                            "return_value": sub_elem_data.get("return_value"),
                            "class_name": sub_elem_data.get("class_name"),
                            "parent_class": sub_elem_data.get("parent_class"),
                            "attributes": sub_elem_data.get("attributes"),
                            "methods": sub_elem_data.get("methods", []),
                            "decorator": sub_elem_data.get("decorator"),
                            "subflowchart": None,
                            "shape_id": None,
                            "label_id": None
                        }
                        element["subflowchart"].add_element(sub_element["type"], sub_element["x"], sub_element["y"], self)
                        element["subflowchart"].elements[-1].update(sub_element)

                    for conn_data in elem_data["subflowchart"]["connections"]:
                        start_idx, end_idx, conn_type, call_params, priority = conn_data
                        start_elem = element["subflowchart"].elements[start_idx]
                        end_elem = element["subflowchart"].elements[end_idx]
                        color = "#5E81AC" if conn_type == "Body" else "#BF616A" if conn_type == "Exit" else "#A3BE8C"
                        line_id = element["subflowchart"].canvas.create_line(
                            start_elem["x"], start_elem["y"], end_elem["x"], end_elem["y"],
                            arrow=tk.LAST, fill=color, tags="connection"
                        )
                        label_id = element["subflowchart"].canvas.create_text(
                            (start_elem["x"] + end_elem["x"]) / 2, (start_elem["y"] + end_elem["y"]) / 2,
                            text=f"{conn_type} ({priority})" if conn_type == "Body" else conn_type,
                            font=("Arial", 8)
                        )
                        element["subflowchart"].connections.append((
                            start_elem, end_elem, line_id, label_id, conn_type, call_params, priority
                        ))

            # 載入連線
            for conn_data in data.get("connections", []):
                start_idx, end_idx, conn_type, call_params, priority = conn_data
                start_elem = self.main_canvas.elements[start_idx]
                end_elem = self.main_canvas.elements[end_idx]
                color = "#5E81AC" if conn_type == "Body" else "#BF616A" if conn_type == "Exit" else "#A3BE8C"
                line_id = self.main_canvas.canvas.create_line(
                    start_elem["x"], start_elem["y"], end_elem["x"], end_elem["y"],
                    arrow=tk.LAST, fill=color, tags="connection"
                )
                label_id = self.main_canvas.canvas.create_text(
                    (start_elem["x"] + end_elem["x"]) / 2, (start_elem["y"] + end_elem["y"]) / 2,
                    text=f"{conn_type} ({priority})" if conn_type == "Body" else conn_type,
                    font=("Arial", 8)
                )
                self.main_canvas.connections.append((
                    start_elem, end_elem, line_id, label_id, conn_type, call_params, priority
                ))

            # 更新簽名
            for elem in self.main_canvas.elements:
                if elem["type"] == "Function" and elem["function_name"]:
                    param_count = len([p for p in (elem["function_params"] or "").split(",") if p.strip()])
                    self.function_signatures[elem["function_name"]] = param_count
                elif elem["type"] == "Class" and elem["class_name"]:
                    self.class_signatures[elem["class_name"]] = {
                        "attributes": elem["attributes"] or {},
                        "methods": {m["name"]: len([p for p in m["params"].split(",") if p.strip()]) for m in elem.get("methods", [])}
                    }

            messagebox.showinfo("成功", f"流程圖已從 {file_path} 載入")
        except Exception as e:
            messagebox.showerror("錯誤", f"載入失敗：{str(e)}")

    def generate_code(self):
        self.code_text.delete("1.0", tk.END)
        code_lines = []
        visited_elements = set()

        def traverse(canvas, elem, indent=0):
            if elem["id"] in visited_elements:
                return
            visited_elements.add(elem["id"])

            indent_str = "    " * indent
            if elem["type"] == "Process":
                if elem["code"]:
                    code_lines.append(f"{indent_str}{elem['code']}")
            elif elem["type"] == "Input":
                if elem["code"]:
                    code_lines.append(f"{indent_str}{elem['code']}")
            elif elem["type"] == "Output":
                if elem["code"]:
                    code_lines.append(f"{indent_str}print({elem['code']})")
            elif elem["type"] == "Decision":
                if elem["condition"]:
                    code_lines.append(f"{indent_str}if {elem['condition']}:")
                    true_branches = sorted([conn for conn in canvas.connections if conn[0] == elem and conn[4] == "Body"], key=lambda c: c[6])
                    for conn in true_branches:
                        traverse(canvas, conn[1], indent + 1)
                    false_branches = sorted([conn for conn in canvas.connections if conn[0] == elem and conn[4] == "Exit"], key=lambda c: c[6])
                    if false_branches:
                        code_lines.append(f"{indent_str}else:")
                        for conn in false_branches:
                            traverse(canvas, conn[1], indent + 1)
                return
            elif elem["type"] == "Loop":
                if elem["condition"]:
                    if elem["loop_type"] == "for":
                        code_lines.append(f"{indent_str}for {elem['condition']}:")
                    else:
                        code_lines.append(f"{indent_str}while {elem['condition']}:")
                    body_branches = sorted([conn for conn in canvas.connections if conn[0] == elem and conn[4] == "Body"], key=lambda c: c[6])
                    for conn in body_branches:
                        traverse(canvas, conn[1], indent + 1)
            elif elem["type"] == "Function":
                if elem["function_name"]:
                    params = elem["function_params"] or ""
                    decorator = f"{indent_str}@{elem['decorator']}\n" if elem["decorator"] else ""
                    lambda_str = f"{indent_str}{elem['function_name']} = lambda {params}: " if elem["is_lambda"] else f"{indent_str}def {elem['function_name']}({params}):"
                    code_lines.append(decorator + lambda_str)
                    if elem["subflowchart"]:
                        for sub_elem in sorted(elem["subflowchart"].elements, key=lambda e: e["y"]):
                            traverse(elem["subflowchart"], sub_elem, indent + 1)
                    else:
                        code_lines.append(f"{indent_str}    pass")
            elif elem["type"] == "Class":
                if elem["class_name"]:
                    parent = f"({elem['parent_class']})" if elem["parent_class"] else ""
                    code_lines.append(f"{indent_str}class {elem['class_name']}{parent}:")
                    if elem["attributes"]:
                        for attr, value in elem["attributes"].items():
                            code_lines.append(f"{indent_str}    {attr} = {value}")
                    if elem["methods"]:
                        for method in elem["methods"]:
                            code_lines.append(f"{indent_str}    def {method['name']}({method['params']}):")
                            if method.get("subflowchart"):
                                for sub_elem in sorted(method["subflowchart"].elements, key=lambda e: e["y"]):
                                    traverse(method["subflowchart"], sub_elem, indent + 2)
                            else:
                                code_lines.append(f"{indent_str}        pass")
            elif elem["type"] == "Start/End" and elem["return_value"]:
                code_lines.append(f"{indent_str}return {elem['return_value']}")
            elif elem["type"] == "Comment":
                if elem["code"]:
                    code_lines.append(f"{indent_str}# {elem['code']}")

            call_connections = sorted([conn for conn in canvas.connections if conn[0] == elem and conn[4] == "Call"], key=lambda c: c[6])
            for conn in call_connections:
                target = conn[1]
                params = conn[5] or ""
                if target["type"] == "Function":
                    code_lines.append(f"{indent_str}{target['function_name']}({params})")
                elif target["type"] == "Class":
                    if "." in params:
                        obj, method = params.split(".", 1)
                        code_lines.append(f"{indent_str}{obj}.{method}")

            if elem["type"] not in ["Decision", "Loop"]:
                next_elements = sorted([conn for conn in canvas.connections if conn[0] == elem and conn[4] == "Body"], key=lambda c: c[6])
                for conn in next_elements:
                    traverse(canvas, conn[1], indent)

        for lib in self.libraries:
            code_lines.insert(0, f"import {lib}")
        for mod_name, _ in self.custom_modules:
            code_lines.insert(0, f"import {mod_name}")
        for name, value in self.variables.items():
            code_lines.append(f"{name} = {repr(value)}")

        if self.main_canvas.elements:
            traverse(self.main_canvas, self.main_canvas.elements[0])

        self.code_text.insert("1.0", "\n".join(code_lines))

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

if __name__ == "__main__":
    root = tk.Tk()
    app = FlowchartToCodeGUI(root)
    try:
        root.mainloop()
    except Exception as e:
        messagebox.showerror("錯誤", f"應用程式異常：{str(e)}")
        sys.exit(1)
