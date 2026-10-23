"""流程圖轉程式碼工具 — 入口

核心邏輯位於 flowchart_core/（不依賴 tkinter），
GUI 位於 flowchart_gui/。執行本檔即可啟動視窗介面。
"""
import sys


def _main() -> int:
    try:
        from flowchart_gui.app import main
    except ImportError as exc:
        print(f"無法載入 GUI 模組：{exc}", file=sys.stderr)
        print("請確認 flowchart_core/ 與 flowchart_gui/ 資料夾位於本檔同層。", file=sys.stderr)
        return 1
    return main()


if __name__ == "__main__":
    sys.exit(_main())
