from FlowchartCodeV2 import FlowchartToCodeGUI
class NmapFlowchartApp(FlowchartToCodeGUI):
    def __init__(self, root):
        super().__init__(root)
        self.root.title("Nmap Flowchart Editor (python-nmap 0.7.1)")
        self.nm = nmap.PortScanner()  # 初始化 python-nmap
        self.libraries.append("nmap")  # 自動匯入 nmap 模組
        self.nmap_tools = [
            "TCP SYN Scan", "TCP Connect Scan", "UDP Scan",
            "Service Version", "OS Detection", "Fast Scan", "Full Port Scan"
        ]

    def create_widgets(self):
        paned_window = PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.Frame(paned_window, width=200)
        paned_window.add(left_frame, minsize=200)

        canvas_frame = ttk.Frame(paned_window)
        paned_window.add(canvas_frame, minsize=600)

        right_frame = ttk.Frame(paned_window, width=300)
        paned_window.add(right_frame, minsize=300)

        # 元素選擇
        ttk.Label(left_frame, text="Nmap 功能：").pack(pady=5)
        self.element_var = tk.StringVar(value="TCP SYN Scan")
        ttk.OptionMenu(left_frame, self.element_var, "TCP SYN Scan", *self.nmap_tools).pack(pady=5)
        ttk.Button(left_frame, text="新增 Nmap 元素", command=lambda: self.add_element(self.main_canvas)).pack(pady=5)

        # 目標輸入框
        ttk.Label(left_frame, text="Target (IP/Host):").pack(pady=5)
        self.target_entry = ttk.Entry(left_frame, width=20)
        self.target_entry.pack(pady=5)
        self.variables["target"] = "'scanme.nmap.org'"  # 預設目標
        self.defined_variables.add("target")

        # 連線類型
        ttk.Label(left_frame, text="連線類型：").pack(pady=5)
        self.connection_var = tk.StringVar(value="Body")
        ttk.OptionMenu(left_frame, self.connection_var, "Body", "Body", "Exit").pack(pady=5)

        # 其他功能按鈕
        ttk.Button(left_frame, text="匯入模組", command=self.import_library).pack(pady=5)
        ttk.Button(left_frame, text="變數管理", command=self.manage_variables).pack(pady=5)
        ttk.Button(left_frame, text="儲存流程圖", command=self.save_flowchart).pack(pady=5)
        ttk.Button(left_frame, text="載入流程圖", command=self.load_flowchart).pack(pady=5)
        ttk.Button(left_frame, text="清除畫布", command=self.clear_canvas).pack(pady=5)
        ttk.Button(left_frame, text="使用說明", command=self.show_help).pack(pady=5)
        ttk.Button(left_frame, text="上一步", command=self.undo).pack(pady=5)
        ttk.Button(left_frame, text="下一步", command=self.redo).pack(pady=5)

        # 主畫布
        self.main_canvas = FlowchartCanvas(canvas_frame, "Nmap 流程圖")
        self.bind_canvas_events(self.main_canvas)

        # 程式碼與輸出區域
        code_frame = ttk.Frame(right_frame)
        code_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        ttk.Label(code_frame, text="程式碼：").pack()
        self.code_text = Text(code_frame, height=15, width=40)
        self.code_text.pack(fill=tk.BOTH, expand=True)
        ttk.Button(code_frame, text="產生程式碼", command=self.generate_code).pack(pady=5)
        ttk.Button(code_frame, text="執行掃描", command=self.run_code).pack(pady=5)

        output_frame = ttk.Frame(right_frame)
        output_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        ttk.Label(output_frame, text="掃描結果：").pack()
        self.output_text = Text(output_frame, height=10, width=40, state="disabled")
        self.output_text.pack(fill=tk.BOTH, expand=True)

        self.animation_speed_var = tk.StringVar(value="正常")
        ttk.Label(right_frame, text="動畫速度：").pack(pady=5)
        ttk.OptionMenu(right_frame, self.animation_speed_var, "正常", "慢", "正常", "快").pack(pady=5)

    def edit_element(self, element, canvas):
        edit_dialog = tk.Toplevel(self.root)
        edit_dialog.title(f"編輯 {element['type']} 元素")
        edit_dialog.geometry("400x300")

        ttk.Label(edit_dialog, text="Nmap 參數（如 -p 80,443 或 -T4）：").pack(pady=5)
        args_text = ttk.Entry(edit_dialog)
        args_text.insert(0, element["nmap_args"] or "")
        args_text.pack(pady=5)

        def save_changes():
            try:
                element["nmap_args"] = args_text.get().strip()
                self.update_element_coords(element, canvas)
                label_text = self.get_label_text(element)
                canvas.canvas.itemconfig(element["label_id"], text=label_text[:20] + "..." if len(label_text) > 20 else label_text)
                edit_dialog.destroy()
            except Exception as e:
                messagebox.showerror("錯誤", f"儲存失敗：{str(e)}")

        ttk.Button(edit_dialog, text="儲存", command=save_changes).pack(pady=5)
        ttk.Button(edit_dialog, text="取消", command=edit_dialog.destroy).pack(pady=5)
        edit_dialog.protocol("WM_DELETE_WINDOW", edit_dialog.destroy)

    def get_label_text(self, element):
        if element["type"] in self.nmap_tools:
            args = element["nmap_args"] or ""
            return f"{element['type']} {args}"
        return super().get_label_text(element)

    def generate_code(self):
        self.code_text.delete("1.0", tk.END)
        code_lines = ["import nmap", "nm = nmap.PortScanner()", "target = target"]
        visited_elements = set()

        def traverse(canvas, elem, indent=0):
            if elem["id"] in visited_elements:
                return
            visited_elements.add(elem["id"])

            indent_str = "    " * indent
            if elem["type"] in self.nmap_tools:
                args = elem["nmap_args"] or ""
                nmap_cmd = f"nm.scan(target, arguments='{self.get_nmap_args(elem['type'])} {args}')"
                code_lines.append(f"{indent_str}{nmap_cmd}")

            next_elements = sorted([conn for conn in canvas.connections if conn[0] == elem and conn[4] == "Body"], key=lambda c: c[6])
            for conn in next_elements:
                traverse(canvas, conn[1], indent)

        if self.main_canvas.elements:
            traverse(self.main_canvas, self.main_canvas.elements[0])
        self.code_text.insert("1.0", "\n".join(code_lines))

    def get_nmap_args(self, tool):
        if tool == "TCP SYN Scan":
            return "-sS"
        elif tool == "TCP Connect Scan":
            return "-sT"
        elif tool == "UDP Scan":
            return "-sU"
        elif tool == "Service Version":
            return "-sV"
        elif tool == "OS Detection":
            return "-O"
        elif tool == "Fast Scan":
            return "-F"
        elif tool == "Full Port Scan":
            return "-p-"
        return ""

    def run_code(self):
        self.output_text.config(state="normal")
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert("1.0", "執行掃描中...\n")
        self.output_text.config(state="disabled")
        self.root.update()

        target = self.target_entry.get().strip() or eval(self.variables["target"])
        if not target:
            messagebox.showerror("錯誤", "請輸入目標 IP 或主機名")
            return

        self.execution_globals = {"nmap": nmap, "target": target}
        for name in dir(builtins):
            self.execution_globals[name] = getattr(builtins, name)

        visited_elements = set()
        visited_connections = set()
        highlight_duration, error_duration = self.get_animation_duration()

        def execute_scan(canvas, elem):
            if elem["id"] in visited_elements:
                return
            visited_elements.add(elem["id"])

            if elem["type"] in self.nmap_tools:
                canvas.highlight_element(elem, duration=highlight_duration)
                args = f"{self.get_nmap_args(elem['type'])} {elem['nmap_args'] or ''}".strip()
                try:
                    self.nm.scan(hosts=target, arguments=args)
                    self.output_text.config(state="normal")
                    for host in self.nm.all_hosts():
                        self.output_text.insert(tk.END, f"Host: {host} ({self.nm[host].hostname()})\n")
                        self.output_text.insert(tk.END, f"State: {self.nm[host].state()}\n")
                        for proto in self.nm[host].all_protocols():
                            ports = self.nm[host][proto].keys()
                            for port in sorted(ports):
                                state = self.nm[host][proto][port]['state']
                                service = self.nm[host][proto][port].get('name', 'unknown')
                                self.output_text.insert(tk.END, f"Port: {port}/{proto} State: {state} Service: {service}\n")
                        if 'osclass' in self.nm[host]:
                            for osclass in self.nm[host]['osclass']:
                                self.output_text.insert(tk.END, f"OS: {osclass['osfamily']} {osclass['osgen']}\n")
                        self.output_text.insert(tk.END, "-" * 50 + "\n")
                    with open("nmap_scan_result.txt", "a") as f:
                        f.write(self.nm.get_nmap_last_output() + "\n" + "-" * 50 + "\n")
                    self.output_text.config(state="disabled")
                except Exception as e:
                    canvas.highlight_error(elem, duration=error_duration)
                    self.output_text.config(state="normal")
                    self.output_text.insert(tk.END, f"錯誤執行 {elem['type']} {args}: {str(e)}\n")
                    self.output_text.config(state="disabled")
                    return

            next_elements = sorted([conn for conn in canvas.connections if conn[0] == elem and conn[4] == "Body"], key=lambda c: c[6])
            for conn in next_elements:
                if conn not in visited_connections:
                    canvas.highlight_connection(conn, duration=highlight_duration)
                    visited_connections.add(conn)
                execute_scan(canvas, conn[1])

        if self.main_canvas.elements:
            execute_scan(self.main_canvas, self.main_canvas.elements[0])
        else:
            self.output_text.config(state="normal")
            self.output_text.delete("1.0", tk.END)
            self.output_text.insert("1.0", "錯誤：無掃描任務可執行\n")
            self.output_text.config(state="disabled")

    def show_help(self):
        help_window = tk.Toplevel(self.root)
        help_window.title("使用說明")
        help_window.geometry("600x400")

        help_text = tk.Text(help_window, wrap="word", font=("Arial", 10))
        help_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        help_content = """
Nmap 流程圖編輯器使用說明（基於 python-nmap 0.7.1）：

1. **新增 Nmap 元素**：
   - 從左側選擇 Nmap 功能（如 TCP SYN Scan、Service Version），點擊「新增 Nmap 元素」。
   - 右鍵元素可編輯參數（如 -p 80,443）或刪除。

2. **設定目標**：
   - 在「Target」輸入框輸入 IP 或主機名（如 scanme.nmap.org）。
   - 目標自動儲存為變數 target，可在「變數管理」中編輯。

3. **連線元素**：
   - 選擇連線類型（Body 或 Exit），左鍵拖曳在元素間建立連線。
   - Body 表示順序執行，Exit 用於條件分支（目前簡化為順序）。
   - 右鍵連線可編輯優先級或刪除。

4. **儲存與載入**：
   - 點擊「儲存流程圖」，選擇 .json 或 .pickle 格式。
   - 點擊「載入流程圖」，選擇現有檔案。
   - 注意：載入 .pickle 檔案可能有安全風險。

5. **執行掃描**：
   - 點擊「產生程式碼」生成 Nmap 掃描腳本。
   - 點擊「執行掃描」運行，結果顯示於輸出視窗並儲存至 nmap_scan_result.txt。
   - 動畫高亮顯示掃描流程，速度可調（慢、正常、快）。

6. **變數管理**：
   - 點擊「變數管理」，新增或編輯目標等變數。
   - 預設目標為 'scanme.nmap.org'。

7. **注意事項**：
   - 需安裝 python-nmap==0.7.1 和 Nmap 可執行檔。
   - 某些掃描（如 UDP 或 OS Detection）需 root 權限。
   - 掃描目標需合法且有授權，避免違反網路安全法規。
        """
        help_text.insert("1.0", help_content)
        help_text.config(state="disabled")
        ttk.Button(help_window, text="關閉", command=help_window.destroy).pack(pady=5)
        help_window.protocol("WM_DELETE_WINDOW", help_window.destroy)

if __name__ == "__main__":
    root = tk.Tk()
    app = NmapFlowchartApp(root)
    try:
        root.mainloop()
    except Exception as e:
        messagebox.showerror("錯誤", f"應用程式異常：{str(e)}")
        sys.exit(1)
