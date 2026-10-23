"""GUI 煙霧測試：python run_gui_smoke.py（需圖形環境）"""
from __future__ import annotations

import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)


def main() -> int:
    import tkinter as tk

    try:
        from flowchart_gui.app import FlowchartApp
    except Exception as exc:
        print(f"SKIP: 無法載入 GUI：{exc}")
        return 0

    root = tk.Tk()
    try:
        app = FlowchartApp(root)
    except Exception as exc:
        print(f"FAIL: 建立 FlowchartApp 失敗：{exc}")
        import traceback
        traceback.print_exc()
        root.destroy()
        return 1

    from tkinter import messagebox, simpledialog
    _orig = (simpledialog.askstring, messagebox.showerror, messagebox.askyesno,
             messagebox.showinfo)
    simpledialog.askstring = lambda *a, **k: "0"
    messagebox.showerror = lambda *a, **k: None
    messagebox.askyesno = lambda *a, **k: True
    messagebox.showinfo = lambda *a, **k: None

    ok = True
    try:
        app._element_var.set("Process")
        app.add_element(app.view)
        app.add_element(app.view)
        app._element_var.set("Decision")
        app.add_element(app.view)
        flowchart = app.project.flowchart
        if len(flowchart.elements) < 3:
            print(f"FAIL: add_element 未建立足夠元素（{len(flowchart.elements)}）")
            ok = False
        else:
            from flowchart_core import Connection, ConnectionType
            a, b, c = flowchart.elements[0], flowchart.elements[1], flowchart.elements[2]

            app._select_element(a, app.view)
            if app.view._selected_id != a.id:
                print("FAIL: 選取高亮未設定")
                ok = False
            app._select_element(None, app.view)
            if app.view._selected_id is not None:
                print("FAIL: 選取高亮未清除")
                ok = False

            edge = app.view._edge_point(a, b.x, b.y)
            if abs(edge[0] - a.x) < 1 and abs(edge[1] - a.y) < 1 and a.x != b.x:
                print("FAIL: 邊界端點未偏移")
                ok = False

            app._connection_var.set(ConnectionType.BODY)
            app._conn_source = a
            app._complete_connection(a, b, app.view)
            if app._conn_source is not None:
                print("FAIL: 連線後 _conn_source 未清理")
                ok = False
            if len(flowchart.connections) != 1:
                print(f"FAIL: 連線未建立（{len(flowchart.connections)}）")
                ok = False

            before = len(flowchart.connections)
            app._conn_source = a
            app._complete_connection(a, b, app.view)
            if len(flowchart.connections) != before:
                print("FAIL: 重複連線未被拒絕")
                ok = False

            app._connection_var.set(ConnectionType.CALL)
            app._conn_source = a
            app._complete_connection(a, c, app.view)
            if any(cn.type == ConnectionType.CALL for cn in flowchart.connections):
                print("FAIL: Call→Process 未被拒絕")
                ok = False
            app._connection_var.set(ConnectionType.BODY)

            for mode in ("窄環", "連線埠", "兩次點擊", "右鍵拖曳"):
                app._on_connection_mode_changed(mode)
                if app.settings.connection_mode != mode:
                    print(f"FAIL: 模式切換 {mode} 未生效")
                    ok = False
                if mode == "連線埠" and not app.view._ports_visible:
                    print("FAIL: 連線埠模式未顯示連線埠")
                    ok = False
                if mode != "連線埠" and app.view._ports_visible:
                    print(f"FAIL: 模式 {mode} 不應顯示連線埠")
                    ok = False
            if app._mode() != "右鍵拖曳":
                print("FAIL: 當前模式非右鍵拖曳")
                ok = False
            app._on_connection_mode_changed("窄環")

            app._pending_conn_source = a
            app.stop_execution()
            if app._pending_conn_source is not None:
                print("FAIL: Esc 未取消兩次點擊來源")
                ok = False

            app._select_element(b, app.view)
            app.delete_connection(flowchart.connections[0], app.view)
            if len(flowchart.connections) != before - 1:
                print("FAIL: 刪除連線失敗")
                ok = False

            app._refresh_diagnostics()
            app.code_text.insert("1.0", "x = 1\nprint(x)\n")
            if "x = 1" not in app.code_text.get("1.0", "end"):
                print("FAIL: code_text 內容寫入失敗")
                ok = False
            app.generate_code()
            generated = app.code_text.get("1.0", "end")
            if "import threading" not in generated:
                print("FAIL: generate_code 未產生預期內容")
                ok = False

            root.geometry("1100x640")
            root.update()
            w1 = app.view.canvas.winfo_width()
            h1 = app.view.canvas.winfo_height()
            root.geometry("1270x710")
            root.update()
            w2 = app.view.canvas.winfo_width()
            h2 = app.view.canvas.winfo_height()
            if w1 <= 1 or h1 <= 1 or w2 <= w1 or h2 <= h1:
                print(f"FAIL: 畫布未隨視窗縮放（{w1}x{h1} → {w2}x{h2}）")
                ok = False
            cw = app.code_text.winfo_width()
            root.geometry("1200x680")
            root.update()
            if app.code_text.winfo_width() <= 0 or cw <= 0:
                print("FAIL: 程式碼區寬度異常")
                ok = False
            minsize = root.minsize()
            if minsize[0] <= 0 or minsize[1] <= 0:
                print(f"FAIL: 未設定最小視窗尺寸 {minsize}")
                ok = False

            work_paned = app.view.canvas.master.master
            pane0 = work_paned.nametowidget(work_paned.panes()[0])
            s0 = work_paned.sashpos(0)
            pw = pane0.winfo_width()
            work_paned.sashpos(0, s0 + 60)
            root.update()
            if pane0.winfo_width() == pw:
                print("FAIL: 水平分隔線調整未改變面板寬度")
                ok = False
            outer_paned = work_paned.master
            ds0 = outer_paned.sashpos(0)
            dh = app.diag_list.winfo_height()
            outer_paned.sashpos(0, ds0 - 50)
            root.update()
            if app.diag_list.winfo_height() == dh:
                print("FAIL: 垂直分隔線調整未改變診斷面板高度")
                ok = False
        root.update()
        root.update_idletasks()
    except Exception as exc:
        print(f"FAIL: GUI 操作例外：{exc}")
        import traceback
        traceback.print_exc()
        ok = False
    finally:
        simpledialog.askstring, messagebox.showerror, messagebox.askyesno, \
            messagebox.showinfo = _orig
        root.destroy()

    if ok:
        print("GUI smoke OK")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
