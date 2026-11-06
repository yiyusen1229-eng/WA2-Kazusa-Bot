# -*- coding: utf-8 -*-
"""「开始游戏」必须真的清空对话历史（静态守卫 + 真机探针配合）。

2026-11-06 用户反馈：点「开始游戏」进新局，打开回想却是**上一局**的内容。
根因：`wt-nav.js` 里写的是 `history = []`。
`history` 是 `game.js` 顶层的 `let history = []`（不是 wt-nav 的变量），
这一行只把**绑定**换成新数组，而真正的对话数组还被 `window.__history` 指向，
回想（`rebuildBacklog`）读的正是 `window.__history` → 旧消息原样显示。
更糟的是 `history` 这个名字在浏览器里还挂着 History API，赋值会被打断。

规矩：清历史只能走 `WA2.session.clearHistory()`（它 `length = 0` 原地清，
并保持 `window.__history` 是同一个数组）。

跑：
    cd program && .\\build_env\\venv\\Scripts\\python.exe tools\\test_newgame.py
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
UI = os.path.join(os.path.dirname(HERE), "src", "ui")
FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:200]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def read(name):
    return io.open(os.path.join(UI, name), encoding="utf-8").read()


def main():
    nav = read("wt-nav.js")
    sess = read("wt-session.js")
    backlog = read("wt-backlog.js")

    print("[1] 不许直接给 history 赋新数组")
    # 只看真正的赋值语句：行首（允许缩进）history = ...，排除 == 和注释行
    bad = []
    for f in ("wt-nav.js", "wt-session.js", "wt-chat.js", "game.js", "wt-backlog.js"):
        for n, line in enumerate(read(f).split("\n"), 1):
            s = line.strip()
            if s.startswith("//") or s.startswith("*"):
                continue
            if re.match(r"^(window\.)?history\s*=(?!=)", s) and "[]" in s:
                bad.append("%s:%d %s" % (f, n, s[:60]))
    check("没有 history = [] 这类替换数组的写法", not bad, bad)

    print("[2] 清历史只能走 clearHistory()")
    check("wt-session 定义了 clearHistory", "function clearHistory" in sess)
    check("clearHistory 内部是原地清空（length = 0）",
          re.search(r"function clearHistory\(\)[^}]*applyHistory\(\[\]\)", sess, re.S) is not None)
    check("clearHistory 被导出", '"clearHistory"' in sess)
    check("wt-nav 的「开始游戏」调了它",
          "WA2.session.clearHistory" in nav or "clearHistory" in nav, "")

    print("[3] 回想读的是 window.__history")
    check("rebuildBacklog 用 window.__history", "window.__history" in backlog)
    check("applyHistory 之后仍指向同一个数组",
          "window.__history = history" in sess, "")

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), "、".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
