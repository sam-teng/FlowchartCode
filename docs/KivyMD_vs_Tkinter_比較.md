# KivyMD 與 Tkinter 版本比較

本文件針對「流程圖轉程式碼工具」評估以 KivyMD 重寫 GUI 的可行性與成本，
作為未來技術選型參考。本階段僅做文件比較，不實作 KivyMD 原型。

## 1. 本專案需求盤點

| 需求 | 說明 |
|---|---|
| 流程圖 Canvas 編輯 | 拖曳節點、繪製連線、右鍵選單、hit-test |
| 逐步執行動畫 | 高亮元素/連線、可調速度、非阻塞 |
| 程式碼編輯與輸出 | 多行文字框、自動補全、即時驗證提示 |
| 模組/外部函式整合 | 匯入模組、函式瀏覽器、pip 搜尋安裝 |
| 安全政策 | 黑/白名單驗證與執行期沙箱 |
| 桌面部署 | Windows exe（PyInstaller），離線可用 |
| 擴充性 | extensions/ 外掛、同步元素、快速鍵設定 |

## 2. 框架簡介

- **Tkinter**：Python 標準庫 GUI，Windows 自帶 Tcl/Tk 8.6。本專案現行版本
  （`flowchart_gui/`）即以 Tkinter + ttk 實作，`tk.Canvas` 提供場景圖式繪圖。
- **KivyMD**：建構於 Kivy 之上的 Material Design 元件庫（目前為 2.x，
  需 Kivy >= 2.3）。以 KV 語言描述版面，GPU（OpenGL）渲染，支援桌面與行動平台。

## 3. 逐項對比

| 面向 | Tkinter（現行） | KivyMD | 評語 |
|---|---|---|---|
| 視覺風格 | 系統原生（ttk），樸素 | Material Design 3，現代美觀 | KivyMD 明顯較美 |
| Canvas 圖形 | `tk.Canvas` 場景圖，coords/itemconfig 原地更新 | Kivy `Canvas` 指令 + Widget 物件模型 | 兩者皆可；Tk 對本工具的節點圖更直接 |
| 拖曳/互動 | 事件綁定成熟、文件多 | 觸控導向，桌面滑鼠操作需調校 | Tk 桌面滑鼠體驗較自然 |
| 文字編輯 | `tk.Text` 內建、穩定 | 無內建多行編輯器，需 `TextInput` 自刻（補全/行號都要自己做） | 本工具重度依賴文字框 → Tk 佔優 |
| 鍵盤輸入 | 系統 IME（中文輸入）正常 | 桌面 IME 偶有焦點/輸入法問題 | Tk 較穩 |
| 動畫 | `root.after` 佇列（本專案已採用） | Clock 佇列，動畫能力更強 | 平手 |
| 啟動時間 | 快（<0.5s 常見） | 較慢（載入 GL 與 kv） | 工具型應用 Tk 佔優 |
| 打包體積 | PyInstaller 約 10–20MB | Kivy+KivyMD+SDL 約 50–100MB+ | Tk 佔優 |
| 行動平台 | 無 | Android/iOS 原生支援 | 需要行動版時 KivyMD 佔優 |
| 學習曲線 | 低（文件龐大、範例多） | 中（KV 語言、屬性系統、生命週期） | Tk 佔優 |
| 社群與維護 | 穩定但保守演進 | 活躍、持續改版 | 各有優勢 |
| 與核心邏輯耦合 | **零耦合**（本次重構後 `flowchart_core/` 不含任何 GUI import） | 同樣可只換 GUI 層 | 分層已為兩者鋪路 |

## 4. 對本專案的移植成本估算

本次重構已將所有業務邏輯集中於 `flowchart_core/`：
模型、驗證、政策、碼產生、執行器、序列化、補全、診斷、PyPI 用戶端。
若改用 KivyMD，需重寫的僅 `flowchart_gui/`：

| 模組 | Tk 實作 | KivyMD 對應工作 | 工作量 |
|---|---|---|---|
| canvas_view | tk.Canvas + coords | Kivy Canvas 指令或自訂 Widget 群組；需自刻箭頭/hit-test | 高 |
| dialogs | tk 對話框 | MDDialog / 自訂 Screen；文字欄位改 TextInput | 中 |
| autocomplete | Listbox 彈窗 | 自訂浮層 + RV 清單 | 中 |
| app | PanedWindow/Menu | MDToolbar + Drawer + 自訂版面 | 中 |
| 執行/診斷/政策 等 | **共用 flowchart_core** | **不需改動** | 無 |

粗估：熟悉 Kivy 的前提下，GUI 層重寫約 2–4 週；加上文字編輯補全調校與
打包測試，約 1–2 個月。風險集中於 TextInput 的 IME 與補全體驗。

## 5. 結論與建議

**建議續用 Tkinter 作為桌面版 GUI**，理由：

1. 本工具定位為桌面流程圖 IDE：Canvas 節點編輯 + 大量文字輸入 + 執行動畫，
   Tkinter 的 `Canvas` + `Text` 正是此類工具的強項。
2. 現行版本已完成核心/GUI 分層、非阻塞動畫、黑/白名單、外掛擴充，
   續用 Tk 的維護成本最低，既有 exe 發行流程不變。
3. KivyMD 的優勢（美觀、行動版）在此場景收益有限，而文字編輯與 IME
   是明確的風險點。

**轉向 KivyMD 的觸發條件**（任一成立再評估原型）：

- 需要 Android/iOS 版本（Kivy 為 Python 生態少數成熟選項）；
- 產品定位轉為「對外展示的現代化 App」，視覺規格要求 Material Design；
- 需要 GPU 等級的大量圖形特效（縮放/平移流暢度需求超過 Canvas 能力）。

屆時可依第 4 節清單僅重寫 `flowchart_gui/`，`flowchart_core/`
（含同步元素擴充點、政策、執行計畫）原封不動複用。

## 6. 參考

- KivyMD 專案：<https://github.com/kivymd/KivyMD>
- Kivy 官方：<https://kivy.org/>
- Python GUI 選型（2026）：<https://www.pythonguis.com/faq/which-python-gui-library/>
