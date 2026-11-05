# -*- coding: utf-8 -*-
"""后端脚本语法自测（不联网、不起服务）。

跑法：
    cd program
    build_env/venv/Scripts/python.exe tools/test_py_syntax.py

为什么要它：`node tools/test_ui_syntax.js` 管前端，Python 这一侧以前没有任何
「整份文件能不能解析」的守卫——一次编辑把两行挤成一行（注释/return 后面接了 if），
只有等 main.py 起服务时才会炸。这里用 `compile()` 把 src/ 下每个 .py 过一遍，
不 import、不执行，纯解析。
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
SRC = os.path.join(PROGRAM, "src")

FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:300]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def main():
    files = sorted(f for f in os.listdir(SRC) if f.endswith(".py"))
    for fn in files:
        path = os.path.join(SRC, fn)
        try:
            with open(path, encoding="utf-8") as f:
                src = f.read()
        except Exception as e:
            check(fn + " 能读", False, e)
            continue
        try:
            compile(src, fn, "exec")
            check(fn, True)
        except SyntaxError as e:
            check(fn, False, "第 %s 行：%s" % (e.lineno, e.msg))
            print("       " + (e.text or "").rstrip())
    print()
    print("  检查了 %d 个文件" % len(files))
    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), " / ".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
