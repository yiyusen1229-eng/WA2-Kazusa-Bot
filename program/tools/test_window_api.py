# -*- coding: utf-8 -*-
"""窗口接口「归属」自测（不联网、不起窗口）。

跑法：
    cd program
    build_env/venv/Scripts/python.exe tools/test_window_api.py

为什么要它：2026-11-05 用户报「全屏失效了」。真因不在全屏代码里，而是
`python main.py` 起的时候真身模块叫 `__main__`，`api_window.py` 里的
`import main` 把 main.py **又执行了一遍**，拿到一份没有 `_WINDOW` 的空壳，
于是每个窗口请求都回 `{"ok": false, "error": "module 'main' has no attribute
'_WINDOW'"}`——HTTP 200、日志干净、界面毫无反应。标题栏按钮还有 pywebview
桥接兜底，所以「关闭 / 最小化」照常，只有**只有 HTTP 一条路**的全屏 / 最大化死掉。

这类「静默失效」靠跑一遍接口是查不出来的（返回码永远是 200），所以这里钉三条：
  1. main.py 顶部必须把 "main" 指到真身（__main__）；
  2. api_window.py 取窗口必须经 winutil._main_module()，不许直接 `import main`；
  3. _main_module() 在「__main__ 有窗口 + main 空壳」时，必须挑到有窗口的那份。
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
SRC = os.path.join(PROGRAM, "src")
sys.path.insert(0, SRC)

FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:300]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def read(name):
    with open(os.path.join(SRC, name), encoding="utf-8") as f:
        return f.read()


def main():
    main_src = read("main.py")
    win_src = read("api_window.py")

    # 1. 别名：main.py 顶层把 "main" 指到 __main__（脚本模式下真身）
    alias = re.search(
        r'if\s+__name__\s*==\s*["\']__main__["\']\s*:\s*\n\s*sys\.modules\.setdefault\(\s*["\']main["\']\s*,',
        main_src)
    check("main.py 顶部把 \"main\" 别名指到 __main__", bool(alias),
          "找不到 sys.modules.setdefault(\"main\", sys.modules[\"__main__\"])")

    # 2. api_window.py 不许再直连 main 的窗口对象
    check("api_window.py 不再 `import main`", not re.search(r"^\s*import main\s*$", win_src, re.M))
    check("api_window.py 不再直接摸 main._WINDOW", "main._WINDOW" not in win_src)
    check("api_window.py 不再直接摸 main._API", "main._API" not in win_src)
    check("api_window.py 经 winutil._main_module() 取真身", "_main_module" in win_src)

    # 3. 解析器本身：有窗口的那份才是真身
    import types
    import winutil

    saved = {k: sys.modules.get(k) for k in ("main", "__main__")}
    try:
        real = types.ModuleType("__main__")
        real._WINDOW = object()          # 真身：窗口挂在这里
        shell = types.ModuleType("main")  # 空壳：import main 再执行一遍得到的
        sys.modules["__main__"] = real
        sys.modules["main"] = shell
        check("_main_module() 挑到有窗口的那份", winutil._main_module() is real)

        # 真身还没窗口时也不能崩：退回任意一份可用的，交给调用方判空
        real2 = types.ModuleType("__main__")
        sys.modules["__main__"] = real2
        got = winutil._main_module()
        check("真身没窗口时退回而不是抛异常", got in (real2, shell), got)
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v

    # 4. 其它 mixin 的 `from main import` 都在函数里（顶层快照会拿到空壳/半成品）
    top = []
    for fn in sorted(f for f in os.listdir(SRC) if f.startswith("api_") and f.endswith(".py")):
        for i, line in enumerate(read(fn).splitlines(), 1):
            if re.match(r"^(import main|from main import)", line):
                top.append("%s:%d" % (fn, i))
    check("api_*.py 顶层没有 import main（都在函数内）", not top, " / ".join(top[:5]))

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), " / ".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
