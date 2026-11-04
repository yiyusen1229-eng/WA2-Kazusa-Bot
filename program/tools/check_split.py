# -*- coding: utf-8 -*-
"""拆分后静态审计：同名覆盖、丢语句、引用未定义、重复语句、漏搬函数。

    python tools/check_split.py            # 只看报告
    python tools/check_split.py --strict   # 有发现就返回码 1（提交前用）

对照基线：6f4955c（拆分前最后一次提交）。
"""
import argparse
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI = os.path.join(ROOT, "src", "ui")
PRE = "6f4955c"
SPLIT_FILES = ("game.js", "opt.js", "special.js")
MODULE_RE = re.compile(r"^(wt-|opt-widgets|opt-model|sp-)")

BUILTIN = set("""window document console JSON Math Date Object Array String Number Boolean
Promise setTimeout setInterval clearInterval clearTimeout fetch encodeURIComponent
decodeURIComponent parseInt parseFloat isNaN isFinite alert confirm requestAnimationFrame
localStorage sessionStorage navigator location screen Image Audio FileReader Blob URL
XMLHttpRequest Event CustomEvent RegExp Error TypeError AbortController
undefined null true false this function return if else for while do switch case break
continue var let const new typeof instanceof in of try catch finally throw delete void
yield await async class extends super import export default arguments $ WA2 setTimeout""".split())


def read(path):
    return open(path, encoding="utf-8", errors="replace").read()


def strip_code(src):
    """去掉注释与字符串，避免把文案/属性名当成标识符。"""
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    src = re.sub(r"(?m)//[^\n]*$", " ", src)
    src = re.sub(r"'(?:[^'\\]|\\.)*'", "''", src)
    src = re.sub(r'"(?:[^"\\]|\\.)*"', '""', src)
    src = re.sub(r"`(?:[^`\\]|\\.)*`", "``", src)
    return src


def defs(src):
    fns = set(re.findall(r"(?m)^\s*(?:async\s+)?function\s+(\w+)\s*\(", src))
    wins = set(re.findall(r"window\.(\w+)\s*=", src))
    return fns, wins


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    files = {f: read(os.path.join(UI, f)) for f in sorted(os.listdir(UI)) if f.endswith(".js")}
    mods = {f: s for f, s in files.items() if MODULE_RE.match(f)}
    problems = 0

    # 1. 同名全局定义
    print("== 1. 同名全局定义（可能互相覆盖）")
    owner = {}
    for f, s in files.items():
        _fns, wins = defs(strip_code(s))
        for w in wins:
            owner.setdefault(w, []).append(f)
    for k, v in sorted(owner.items()):
        if len(v) < 2 or k == "WA2":
            continue
        print("   ! window.%-22s <- %s" % (k, ", ".join(v)))
        problems += 1
    if problems == 0:
        print("   无")

    # 2. 拆分前有、现在没有的 window 赋值
    print("\n== 2. 拆分前有、现在没有的 window 赋值")
    have = set()
    for s in files.values():
        have |= {ln.strip() for ln in s.splitlines() if re.match(r"^\s*window\.\w+\s*=", ln)}
    for old in SPLIT_FILES:
        src = subprocess.run(["git", "-C", ROOT, "show", "%s:program/src/ui/%s" % (PRE, old)],
                             capture_output=True).stdout.decode("utf-8")
        want = {ln.strip() for ln in src.splitlines()
                if re.match(r"^\s*window\.\w+\s*=", ln) and ln.count("{") == ln.count("}")}
        missing = sorted(w for w in want if w not in have)
        for m in missing:
            print("   ! %-12s 缺: %s" % (old, m[:70]))
            problems += 1
        if not missing:
            print("   %-12s 无缺失" % old)

    # 3. 模块里用到、但全项目都没定义的标识符
    print("\n== 3. 模块里用到、但全项目都没定义的标识符")
    all_defs = set()
    for s in files.values():
        fns, wins = defs(strip_code(s))
        all_defs |= fns | wins | set(re.findall(r"(?:var|let|const)\s+(\w+)\s*=", s))
    for f, raw in mods.items():
        s = strip_code(raw)
        local = set(re.findall(r"(?:function|var|let|const)\s+(\w+)", s))
        for p in re.findall(r"function\s*\w*\s*\(([^)]*)\)", s):
            local |= {x.strip().split("=")[0].strip() for x in p.split(",") if x.strip()}
        used = set(re.findall(r"(?<![\w.$])([A-Za-z_$][\w$]*)\s*(?![:\w$])", s))
        unknown = sorted(n for n in used - local - BUILTIN - all_defs if not n.isupper())
        if unknown:
            print("   ! %-16s %s" % (f, ", ".join(unknown[:12])))
            problems += len(unknown)

    # 4. 重复语句
    print("\n== 4. 重复语句（连续两行完全相同）")
    for f, raw in mods.items():
        lines = [ln.strip() for ln in raw.splitlines()]
        for i in range(1, len(lines)):
            if lines[i] and lines[i] == lines[i - 1] and len(lines[i]) > 20 \
                    and not lines[i].startswith(("}", "{", "//", "*", "/*")):
                print("   ! %-16s L%d %s" % (f, i + 1, lines[i][:70]))
                problems += 1

    # 5. 漏搬函数
    print("\n== 5. 拆分前有、现在找不到的函数")
    have_fn = set()
    for s in files.values():
        have_fn |= set(re.findall(r"(?m)^\s*(?:async\s+)?function\s+(\w+)\s*\(", s))
    for old in SPLIT_FILES:
        src = subprocess.run(["git", "-C", ROOT, "show", "%s:program/src/ui/%s" % (PRE, old)],
                             capture_output=True).stdout.decode("utf-8")
        want = set(re.findall(r"(?m)^\s*(?:async\s+)?function\s+(\w+)\s*\(", src))
        missing = sorted(want - have_fn)
        print("   %-12s %s" % (old, ("缺: " + ", ".join(missing)) if missing else "函数齐全"))
        problems += len(missing)

    print("\n合计发现 %d 处" % problems)
    return 1 if (a.strict and problems) else 0


if __name__ == "__main__":
    sys.exit(main())
