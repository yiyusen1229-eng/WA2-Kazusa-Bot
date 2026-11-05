# -*- coding: utf-8 -*-
"""运行状态标记的自测（不联网、不开界面）。

跑法：
    cd program
    build_env/venv/Scripts/python.exe tools/test_runstate.py

验的是：
  1. 第一次启动：没有"上次"记录，不算异常退出
  2. 启动后标记落盘；再启动一次能认出"上次没正常退出"
  3. 正常退出删标记，下次启动不再报异常
  4. 崩溃日志能写出来，内容里有异常文本
  5. 有自动存档时，崩溃现场会复制一份
  6. state() 如实反映 dirty_exit / has_autosave
  7. install_hooks 真的挂上了 sys.excepthook
"""
import json
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROGRAM, "src"))

import runstate  # noqa: E402
import sessions  # noqa: E402

FAILS = []
TMP = tempfile.mkdtemp(prefix="wa2_run_test_")

# 把标记/崩溃日志都指到临时目录，别污染真实 logs/
runstate._dir = lambda: TMP
sessions.SESS_DIR = os.path.join(TMP, "sessions")
os.makedirs(sessions.SESS_DIR, exist_ok=True)


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:300]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def main():
    marker = os.path.join(TMP, "run_state.json")

    # 1. 第一次启动
    prev = runstate.begin("test", "0.0.1")
    check("第一次启动没有上次记录", prev is None, prev)
    check("标记已落盘", os.path.exists(marker))
    st = runstate.state()
    check("第一次不算异常退出", st["dirty_exit"] is False, st)
    check("没有自动存档", st["has_autosave"] is False, st)

    # 2. 模拟"崩了"：不调 end，直接再启动
    prev = runstate.begin("test", "0.0.1")
    check("第二次启动认出异常退出", prev is not None, prev)
    check("带上次的启动时间", bool(prev.get("started_at")), prev)
    check("state 报 dirty_exit", runstate.state()["dirty_exit"] is True, runstate.state())

    # 3. 正常退出
    runstate.end()
    check("正常退出删掉标记", not os.path.exists(marker))
    prev = runstate.begin("test", "0.0.1")
    check("正常退出后不再报异常", prev is None, prev)
    check("state 恢复干净", runstate.state()["dirty_exit"] is False, runstate.state())

    # 4. 崩溃日志
    p = runstate.crash_log("Traceback (most recent call last):\n  boom\nValueError: 炸了")
    check("崩溃日志写出来了", os.path.exists(p), p)
    body = open(p, encoding="utf-8").read()
    check("日志里有异常文本", "ValueError: 炸了" in body, body[:120])
    check("日志文件名带 crash_", os.path.basename(p).startswith("crash_"), p)

    # 5. 有自动存档时复制一份
    sessions.session_save({"slot": "auto", "messages": [{"role": "user", "content": "存一下"}]})
    check("state 看到自动存档", runstate.state()["has_autosave"] is True, runstate.state())
    p2 = runstate.crash_log("second")
    base = os.path.basename(p2)[:-4]
    copy = os.path.join(TMP, base + "_auto.json")
    check("崩溃现场复制了自动存档", os.path.exists(copy), copy)
    if os.path.exists(copy):
        d = json.load(open(copy, encoding="utf-8"))
        check("复制件内容对", (d.get("messages") or [{}])[0].get("content") == "存一下", d.get("messages"))

    # 6. 挂钩子
    old = sys.excepthook
    runstate.install_hooks()
    check("sys.excepthook 被替换", sys.excepthook is not old, sys.excepthook)
    sys.excepthook = old

    # 收尾：正常退出，别留标记
    runstate.end()

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), " / ".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
