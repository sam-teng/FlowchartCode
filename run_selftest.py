"""無 GUI 自測：python run_selftest.py"""
from __future__ import annotations

import ast
import os
import sys
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)


def expect(cond: bool, message: str, failures: list) -> None:
    if cond:
        print(f"  [OK] {message}")
    else:
        print(f"  [FAIL] {message}")
        failures.append(message)


def build_sample_flowchart(fc_module):
    ElementType = fc_module.ElementType
    Element = fc_module.Element
    Connection = fc_module.Connection
    Flowchart = fc_module.Flowchart

    fc = Flowchart()
    start = fc.add_element(Element(type=ElementType.START_END, x=100, y=40))
    init = fc.add_element(Element(type=ElementType.PROCESS, x=100, y=120,
                                  code="total = 0"))
    loop = fc.add_element(Element(type=ElementType.LOOP, x=100, y=200,
                                  condition="i in range(4)", loop_type="for"))
    add = fc.add_element(Element(type=ElementType.PROCESS, x=100, y=280,
                                 code="total += i"))
    out_loop = fc.add_element(Element(type=ElementType.OUTPUT, x=100, y=360,
                                      code="total"))
    decide = fc.add_element(Element(type=ElementType.DECISION, x=100, y=440,
                                    condition="total > 3"))
    big = fc.add_element(Element(type=ElementType.OUTPUT, x=40, y=520, code="'big'"))
    small = fc.add_element(Element(type=ElementType.OUTPUT, x=200, y=520,
                                   code="'small'"))
    greet = fc.add_element(Element(type=ElementType.FUNCTION, x=320, y=120,
                                   function_name="greet", function_params="name"))
    greet_body = fc.add_element(Element(type=ElementType.OUTPUT, x=320, y=200,
                                        code="'hi ' + name"))
    greet.subflowchart = Flowchart()
    greet.subflowchart.add_element(greet_body)
    ev_set = fc.add_element(Element(type=ElementType.SYNC_EVENT, x=420, y=280,
                                    options={"event_name": "done_evt", "action": "set"}))
    call_greet = fc.add_element(Element(type=ElementType.PROCESS, x=100, y=600,
                                        code="msg = 'world'"))
    end = fc.add_element(Element(type=ElementType.START_END, x=100, y=680))

    links = [
        (start, init, "Body", ""),
        (init, loop, "Body", ""),
        (loop, add, "Body", ""),
        (loop, out_loop, "Exit", ""),
        (out_loop, decide, "Body", ""),
        (decide, big, "Body", ""),
        (decide, small, "Exit", ""),
        (big, call_greet, "Body", ""),
        (small, call_greet, "Body", ""),
        (call_greet, greet, "Call", "'world'"),
        (call_greet, ev_set, "Body", ""),
        (ev_set, end, "Body", ""),
    ]
    for source, target, ctype, params in links:
        ok, message = fc.add_connection(
            Connection(source.id, target.id, ctype, params, 0)
        )
        if not ok:
            raise RuntimeError(message)
    return fc


def main() -> int:
    failures: list[str] = []

    print("== 1. 核心不依賴 tkinter ==")
    import flowchart_core
    expect("tkinter" not in sys.modules, "import flowchart_core 未載入 tkinter", failures)

    print("== 2. 擴充註冊（含 extensions/ 外掛）==")
    registry = flowchart_core.create_default_registry(os.path.join(BASE, "extensions"))
    names = [ext.meta.type_name for ext in registry.all_extensions()]
    expect("Thread/Task" in names and "SyncEvent" in names, "內建同步元素已註冊", failures)
    expect("QueuePush" in names and "QueuePop" in names, "範例外掛已載入", failures)
    expect(not registry.load_errors, f"外掛載入無錯誤 {registry.load_errors}", failures)

    print("== 3. 建立樣本流程圖並執行 ==")
    symbols = flowchart_core.SymbolTable()
    policy = flowchart_core.CodePolicy.standard()
    validator = flowchart_core.CodeValidator(symbols, policy)
    flowchart = build_sample_flowchart(flowchart_core)
    symbols.rebuild_from_flowchart(flowchart)
    plan = flowchart_core.compile_plan(flowchart, symbols, validator, registry)
    executor = flowchart_core.FlowchartExecutor(plan, policy)
    warnings = executor.prepare({}, [], [])
    events = list(executor.run())
    output = executor.output.getvalue()
    expect("6" in output, f"迴圈總和輸出 6（實際 {output!r}）", failures)
    expect("big" in output, f"Decision 真分支輸出 big（實際 {output!r}）", failures)
    expect("hi 'world'" in output or "hi world" in output,
           f"函式呼叫輸出 hi world（實際 {output!r}）", failures)
    errors = [e for e in events if e.kind == "error"]
    expect(not errors, f"執行無錯誤 {[e.message for e in errors]}", failures)

    print("== 4. 迴圈安全上限 ==")
    loop_fc = flowchart_core.Flowchart()
    wloop = loop_fc.add_element(flowchart_core.Element(
        type=flowchart_core.ElementType.LOOP, condition="True", loop_type="while"))
    wbody = loop_fc.add_element(flowchart_core.Element(
        type=flowchart_core.ElementType.PROCESS, code="pass"))
    loop_fc.add_connection(flowchart_core.Connection(wloop.id, wbody.id, "Body"))
    wplan = flowchart_core.compile_plan(loop_fc, symbols, validator, registry,
                                        loop_limit=25)
    wexec = flowchart_core.FlowchartExecutor(wplan, policy)
    wexec.prepare()
    wevents = list(wexec.run())
    expect(any(e.kind == "loop_limit" for e in wevents), "while 無限迴圈觸發上限保護", failures)

    print("== 5. 程式碼產生與語法檢查 ==")
    generator = flowchart_core.CodeGenerator(
        flowchart, symbols, registry, variables={"seed": 1}
    )
    code = generator.generate()
    try:
        ast.parse(code)
        expect(True, "產生的程式碼語法正確", failures)
    except SyntaxError as exc:
        expect(False, f"產生的程式碼語法錯誤：{exc}", failures)
    expect("def greet(name):" in code, "包含函式定義", failures)
    expect("threading" in code, "包含 threading 匯入", failures)

    print("== 6. 政策黑/白名單 ==")
    expect(policy.check_import("os")[0] is False, "標準政策封鎖 os", failures)
    expect(policy.check_import("math")[0] is True, "標準政策允許 math", failures)
    expect(policy.check_name("eval")[0] is False, "標準政策封鎖 eval", failures)
    violations = policy.check_code("import subprocess")
    expect(bool(violations), "程式碼檢查抓到 subprocess", failures)
    strict = flowchart_core.CodePolicy.strict()
    expect(strict.check_import("math")[0] is True, "嚴格白名單允許 math", failures)
    expect(strict.check_import("os")[0] is False, "嚴格白名單拒絕 os", failures)
    expect(strict.check_name("print")[0] is True, "嚴格白名單允許 print", failures)
    lenient = flowchart_core.CodePolicy.lenient()
    expect(lenient.check_import("math")[0] is True, "寬鬆允許 math", failures)
    expect(lenient.check_import("ctypes")[0] is False, "寬鬆仍封鎖 ctypes", failures)
    pexec = flowchart_core.FlowchartExecutor(plan, policy)
    pexec.prepare()
    blocked = policy.check_import("os")
    expect(blocked[0] is False, "executor 準備完成後政策仍有效", failures)

    print("== 7. 序列化往返與舊格式 ==")
    project = flowchart_core.Project(
        flowchart=flowchart, variables={"seed": "1"},
        libraries=["math"], custom_modules=[],
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "proj.json")
        flowchart_core.save_project(path, project)
        loaded = flowchart_core.load_project(path)
        expect(len(loaded.flowchart.elements) == len(flowchart.elements),
               "JSON 往返元素數一致", failures)
        expect(len(loaded.flowchart.connections) == len(flowchart.connections),
               "JSON 往返連線數一致", failures)
        expect(loaded.libraries == ["math"], "JSON 往返 libraries 一致", failures)
        thread_el = flowchart_core.Element(
            type=flowchart_core.ElementType.THREAD, code="pass",
            options={"start_delay": "1", "wait_event": "e1"},
        )
        expect(thread_el.to_dict()["options"].get("start_delay") == "1",
               "Thread options 序列化", failures)
        restored = flowchart_core.Element.from_dict(thread_el.to_dict())
        expect(restored.opt("wait_event") == "e1", "Thread options 還原", failures)
        legacy_path = os.path.join(BASE, "flowchartNew.json")
        if os.path.exists(legacy_path):
            legacy = flowchart_core.load_project(legacy_path)
            expect(len(legacy.flowchart.elements) > 0, "載入 flowchartNew.json", failures)
        old_path = os.path.join(BASE, "flowchart.json")
        if os.path.exists(old_path):
            old = flowchart_core.load_project(old_path)
            expect(len(old.flowchart.elements) > 0, "載入舊版 flowchart.json（main_canvas）", failures)

    print("== 8. 片段庫佔位符 ==")
    snippets = flowchart_core.SnippetLibrary()
    placeholders = snippets.parse_placeholders("for {i} in range({n}):")
    expect(placeholders == ["i", "n"], f"解析佔位符 {placeholders}", failures)
    rendered = snippets.render("for {i} in range({n}):", {"i": "idx", "n": "5"})
    expect(rendered == "for idx in range(5):", f"代換結果 {rendered!r}", failures)

    print("== 9. 補全提供者 ==")
    symbols2 = flowchart_core.SymbolTable()
    symbols2.defined_variables.add("total")
    symbols2.register_function("greet", "name")
    symbols2.libraries.append("math")
    provider = flowchart_core.CompletionProvider(symbols2, policy)
    items = provider.complete("tot")
    expect(any(i.label == "total" for i in items), "補全找到變數 total", failures)
    items = provider.complete("math.")
    expect(any(i.label == "sqrt" for i in items), "補全找到 math.sqrt", failures)
    found, signature, _doc = provider.describe_name("math.sqrt")
    expect(found and "(" in signature, f"describe math.sqrt → {signature}", failures)

    print("== 10. 診斷分析器 ==")
    diag_fc = flowchart_core.Flowchart()
    diag_fc.add_element(flowchart_core.Element(type=flowchart_core.ElementType.PROCESS,
                                               code="x = "))
    diag_fc.add_element(flowchart_core.Element(type=flowchart_core.ElementType.DECISION))
    diags = flowchart_core.analyze(diag_fc, symbols2, validator, registry)
    messages = " | ".join(d.message for d in diags)
    expect("缺少 Start/End" in messages, "診斷：缺少 Start/End", failures)
    expect("Decision 缺少條件" in messages, "診斷：Decision 缺少條件", failures)

    print("== 11. History 復原/重做 ==")
    history = flowchart_core.History()
    history.push({"v": 1})
    history.push({"v": 2})
    state = history.undo({"v": 3})
    expect(state == {"v": 2}, "undo 返回前一狀態", failures)
    state = history.redo()
    expect(state == {"v": 3}, "redo 返回下一狀態", failures)

    print("== 12. 快速鍵管理 ==")
    from flowchart_gui.shortcuts import ShortcutManager
    with tempfile.TemporaryDirectory() as tmp:
        mgr = ShortcutManager(os.path.join(tmp, "shortcuts.json"))
        expect(mgr.get("run") == "<F5>", "預設 F5 執行", failures)
        error = mgr.set("run", "<Control-z>")
        expect(error is not None, "快速鍵衝突偵測", failures)
        error = mgr.set("run", "<F6>")
        expect(error is None, "快速鍵可改綁", failures)
        mgr2 = ShortcutManager(os.path.join(tmp, "shortcuts.json"))
        expect(mgr2.get("run") == "<F6>", "快速鍵持久化", failures)

    print("== 13. 外部函式呼叫（math.sqrt）==")
    ext_fc = flowchart_core.Flowchart()
    s = ext_fc.add_element(flowchart_core.Element(type=flowchart_core.ElementType.START_END))
    ext = ext_fc.add_element(flowchart_core.Element(
        type=flowchart_core.ElementType.EXTERNAL, code="sqrt_val",
        options={"module": "math", "qualname": "sqrt"},
    ))
    ext_fc.add_connection(flowchart_core.Connection(s.id, ext.id, "Call", "9"))
    ext_plan = flowchart_core.compile_plan(ext_fc, symbols, validator, registry)
    ext_exec = flowchart_core.FlowchartExecutor(ext_plan, policy)
    ext_exec.prepare(libraries=["math"])
    list(ext_exec.run())
    expect("3.0" in ext_exec.output.getvalue(), "外部呼叫 math.sqrt(9) = 3.0", failures)

    print("== 14. Thread + Event 執行 ==")
    th_fc = flowchart_core.Flowchart()
    ev1 = th_fc.add_element(flowchart_core.Element(
        type=flowchart_core.ElementType.SYNC_EVENT,
        options={"event_name": "go", "action": "set"},
    ))
    th1 = th_fc.add_element(flowchart_core.Element(
        type=flowchart_core.ElementType.THREAD, code="print('thread ran')",
        options={"start_delay": "0"},
    ))
    th_fc.add_connection(flowchart_core.Connection(ev1.id, th1.id, "Body"))
    th_plan = flowchart_core.compile_plan(th_fc, symbols, validator, registry)
    th_exec = flowchart_core.FlowchartExecutor(th_plan, policy)
    th_exec.prepare()
    th_events = list(th_exec.run())
    import time as _time
    _time.sleep(0.15)
    expect(any(e.kind == "thread_started" for e in th_events), "產生 thread_started 事件", failures)
    expect("thread ran" in th_exec.output.getvalue(), "執行緒內容已執行", failures)

    print("== 15. 連線驗證目標類型規則 ==")
    proc = flowchart_core.Element(type=flowchart_core.ElementType.PROCESS, code="pass")
    func = flowchart_core.Element(type=flowchart_core.ElementType.FUNCTION,
                                  function_name="f")
    ext_el = flowchart_core.Element(type=flowchart_core.ElementType.EXTERNAL,
                                    options={"module": "math", "qualname": "sqrt"})
    r = validator.validate_connection("Call", "1", "0", proc)
    expect(not r.ok and "Call" in r.message, f"Call→Process 被拒：{r.message}", failures)
    r = validator.validate_connection("Call", "1", "0", func)
    expect(r.ok, f"Call→Function 允許：{r.message}", failures)
    r = validator.validate_connection("Call", "sqrt(4)", "0", ext_el)
    expect(r.ok, f"Call→External 允許：{r.message}", failures)
    r = validator.validate_connection("Body", "", "0", func)
    expect(not r.ok and "Body" in r.message, f"Body→Function 被拒：{r.message}", failures)
    r = validator.validate_connection("Exit", "", "0", ext_el)
    expect(not r.ok, f"Exit→External 被拒：{r.message}", failures)
    r = validator.validate_connection("Body", "", "0", proc)
    expect(r.ok, f"Body→Process 允許：{r.message}", failures)

    print("== 16. 連線方式設定 ==")
    from flowchart_gui.settings import CONNECTION_MODES, SettingsManager
    with tempfile.TemporaryDirectory() as tmp:
        spath = os.path.join(tmp, "settings.json")
        mgr = SettingsManager(spath)
        expect(mgr.connection_mode == "窄環", "預設連線方式為窄環", failures)
        expect(mgr.set_connection_mode("兩次點擊"), "切換連線方式", failures)
        mgr2 = SettingsManager(spath)
        expect(mgr2.connection_mode == "兩次點擊", "連線方式持久化", failures)
        expect(not mgr.set_connection_mode("不存在的模式"), "拒絕未知模式", failures)
        bad = os.path.join(tmp, "bad.json")
        with open(bad, "w", encoding="utf-8") as fh:
            fh.write("{ broken")
        expect(SettingsManager(bad).connection_mode == "窄環", "損壞設定檔回復預設", failures)
        expect(set(CONNECTION_MODES) >= {"窄環", "連線埠", "兩次點擊", "右鍵拖曳"},
               "四種連線模式皆已定義", failures)

    print()
    if failures:
        print(f"自測失敗 {len(failures)} 項：")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("全部自測通過。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
