import tkinter as tk
from tkinter import ttk, messagebox, Text, PanedWindow, filedialog
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
        try:
            self.root = tk.Tk()
            self.root.title("流程圖轉程式碼工具")
            self.root.geometry("800x400")
            self.root.state('zoomed')
        except Exception as e:
            messagebox.showerror("錯誤", f"初始化失敗：{str(e)}")
            sys.exit(1)

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
            "字典推導式": {k: v**2 for k, v in dict.items()}",
            "裝飾器": "@decorator\ndef func(): pass",
            "上下文管理器": "with open('file.txt') as f:\n    data = f.read()"
        }

        self.create_widgets()

    def create_widgets(self):
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

        self.style = ttk.Style()
        self.style.configure("TFrame", background="#ECEFF4")
        self.style.configure("TButton", padding=6)
        self.style.configure("TLabelFrame", background="#ffffff")

    def bind_canvas_events(self, canvas):
        try:
            canvas.canvas.bind("<Button-1>", lambda e: self.handle_canvas_click(e, canvas))
            canvas.canvas.bind("<B1-Motion>", lambda e: self.handle_canvas_drag(e, canvas))
            canvas.canvas.bind("<Button-2>", lambda e: self.show_context_menu(e, canvas))  # macOS
            canvas.canvas.bind("<Button-3>", lambda e: self.show_context_menu(e, canvas))  # Windows/Linux
        except Exception as e:
            messagebox.showerror("錯誤", f"綁定事件失敗：{str(e)}")

    def show_context_menu(self, event, canvas):
        try:
            context_menu = tk.Menu(self.root, tearoff=0)
            element = None
            for elem in canvas.elements:
                x, y = elem["x"], elem["y"]
                if abs(x - event.x) < 20 and abs(y - event.y) < 20:
                    element = elem
                    break
            if element:
                if element["type"] not in ["Start/End"]:
                    context_menu.add_command(label="編輯", command=lambda: self.edit_element(element, canvas))
                context_menu.add_command(label="刪除", command=lambda: self.delete_element(element, canvas))
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
            messagebox.showerror("錯誤", f"無法創建編輯視窗：{str(e)}}")
            return

        ttk.Label(edit_dialog, text="程式碼/條件：").pack(pady=2)
        code_text = tk.Text(edit_dialog, height=5, width=40)
        code_text.pack(pady=5)

        # 填充現有屬性
        if element["type"] in ["Process", "Input"]: "Output"]:
            code_text.insert("1.0", element["code"] or "")
        elif element["type"] == "Decision":
            code_text.insert("1.0", element["condition"] or "")
        elif element["type"] == "Loop":
            code_text.insert("1.0", element["condition"] or "")
            loop_type_var = tk.StringVar(value=element["loop_type"] or "for")
            ttk.Radiobuttonedit_dialog, text="For 迴圈", value="for", variable=loop_type_var).pack(pady=1)
            ttk.Radiobutton(edit_dialog, text="While 迴圈", value="while", variable=loop_type_var).pack(pady=1)
        elif element["type"] == "Function":
            code_text.insert("1.0", element["function_name"] or "")
            param_text = ttk.Entry(edit_dialog)
            param_text.insert(0, element["function_params"] or "")
            ttk.Label(edit_dialog, text="參數：").pack(pady=2)
            param_text.pack(pady=2)
            lambda_var = tk.BooleanVar(value=valueelement.get("is_lambda", False))
            ttk.Checkbutton(edit_buttonedit_dialog, text="Lambda 函式", variable=lambda_var).pack(pady=2)
        elif element["type"] == "Class":
            code_text.insert("1.0", element["class_name"] or "")
            parent_text = ttk.Label(edit_dialog, text="父類別：").pack(pady=2)
            parent_entry = ttk.Entry(parent_text)
            parent_text.pack(pady=2)
            entry.insert(0, element["parent_class"] or "")
            parent_text.pack(pady=5)
            ttk.Label(edit_dialog, text="屬性（JSON）：").pack(pady=2)
            attr_text = tk.Text(edit_dialog, height=3, width=40)
            attr_text.pack(pady=2)
            attr_text.insert("1.0", json.dumps(element["attributes"] or {}, indent=2))
            attr_text.pack(pady=5)

        # 語法糖模板
        ttk.Label(edit_dialog, text="語法糖模板：").pack(pady=5)
        template_var = tk.StringVar(value="無")
        template_menu = ttk.OptionMenu(edit_dialog, template_var, "無", *self.syntax_sugar_templates.keys())
        template_menu.pack(pady=2)

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
                else:
                    pass
                except Exception as e:
                    messagebox.showerror("錯誤", f"套用模板失敗：{str(e)}")

        ttk.Button(edit_dialog, text="套用模板", command=apply_template).pack(pady=2)

        def save_changes():
            try:
                code = code_text.get("1.0", tk.END).strip()
                if element["type"] in ["Process", "Input"]: "Output"]:
                    valid, error_msg = self.validate_code(code, is_condition=False, element=elem, canvas=canvas)
                    if not valid:
                        messagebox.showerror("錯誤", error_msg)
                        return
                    element["code"] = code
                    if element["type"] == "Process":
                        self.update_defined_variables(code)
                elif element["type"] == "Decision":
                    valid, error_msg = self.validate_code(code, is_condition=True, element=elem, canvas=canvas)
                    if not valid:
                        messagebox.showerror("錯誤", error_msg)
                        return
                    element["condition"] = code
                elif element["type"] == "Loop":
                    valid, error_msg = self.validate_code(code, is_condition=True, element=elem, canvas=canvas))
                    if not valid:
                        messagebox.showerror("錯誤", error_msg)
                        return
                    element["condition"] = code
                    element["loop_type"] = loop_type_var.get()
                elif element["type"] == "Function":
                    if not code or not re.match(r'^[a-zA-Z_]\w*', code):
                        messagebox.showerror("錯誤", "函式名稱必須為有效 Python 標識符")
                        return
                    element["function_name"] = code
                    element["function_params"] = param_text.get().strip()
                    element["is_lambda"] = lambda_var.get()
                    if element["function_name"]:
                        param_count = len([p for p in element["function_params"].split(",") if p.strip()])
                        self.function_signatures[element["function_name"]] = param_count
                elif element["type"] == "Class":
                    if not code or not re.match(r'^[a-zA-Z_]\w*', code):
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
                    self.class_signatures[self.class_signatures[element["class_name"]] = {
                        "attributes": element["attributes"],
                        "methods": {m["name"]: len([p for p in m["params"].split(",") if p.strip()]) for m in element.get("methods", [])}
                    ]

                self.update_element_coords(element, canvas)
                try:
                    label_text = self.get_label_text(element)
                    canvas.canvas.itemconfig(element["label_id"].get(), text=label_text[:20] + "..." if len(label_text) > 20 else label_text)
                except Exception as e:
                    messagebox.showerror("錯誤", f"更新標籤失敗：{str(e)}")
                    return
                edit_dialog.destroy()

            except Exception as e:
                messagebox.showerror("錯誤", f"儲存失敗：{str(e)}")

        ttk.Button(edit_dialog, text="儲存" command, command=save_changes).pack(pady=2)
        ttk.Button(edit_dialog, text="取消", command="edit_dialog.destroy, command=edit_dialog.destroy).pack(pady=2)

        edit_dialog.protocol("WM_DELETE_WINDOW", edit_dialog.destroy)

    # ... 其他方法（update_defined_variables、validate_code、run_code 等保持先前修正版本） ...

if __name__ == "__main__":
    root = tk.Tk()
    app = FlowchartToCodeGUI(root)
    try:
        root.mainloop()
    except Exception as e:
        messagebox.showerror("錯誤", f"應用程式異常：{str(e)}")
        sys.exit(1)
