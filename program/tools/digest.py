# -*- coding: utf-8 -*-
"""省 token 的读书工具：先看结构，再只读需要的那几行。

用法：
    python tools/digest.py --outline other/docs/新对话交接说明.md
    python tools/digest.py --head 40 README.md
    python tools/digest.py --slice 120-180 other/docs/新对话交接说明.md
    python tools/digest.py --patch other/docs/patches/xxx.patch
    python tools/digest.py --stat other/docs/新对话交接说明.md

--outline 输出标题行 + 行号，配合 --slice 就能只读某一节。
"""
import argparse
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def read_lines(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()


def cmd_outline(path):
    lines = read_lines(path)
    print("%s  %d 行 / %.1f KB" % (path, len(lines), os.path.getsize(path) / 1024))
    for i, ln in enumerate(lines, 1):
        if re.match(r"^#{1,4}\s", ln):
            print("%5d | %s" % (i, ln[:110]))
    if not any(re.match(r"^#{1,4}\s", ln) for ln in lines):
        print("（没有 Markdown 标题，用 --head / --slice 看）")


def cmd_head(path, n):
    for i, ln in enumerate(read_lines(path)[:n], 1):
        print("%5d | %s" % (i, ln))


def cmd_slice(path, a, b):
    lines = read_lines(path)
    for i in range(max(1, a), min(len(lines), b) + 1):
        print("%5d | %s" % (i, lines[i - 1]))


def cmd_patch(path):
    """只看补丁动了哪些文件、加减多少行，不看内容。"""
    text = open(path, encoding="utf-8", errors="replace").read()
    print("%s  %.1f KB" % (path, os.path.getsize(path) / 1024))
    blocks = re.split(r"^diff --git ", text, flags=re.M)[1:]
    print("%d 个文件：" % len(blocks))
    for b in blocks:
        head = b.splitlines()[0] if b.splitlines() else ""
        files = re.findall(r"a/(\S+) b/(\S+)", head)
        name = files[0][1] if files else head[:60]
        add = len(re.findall(r"^\+(?!\+\+)", b, flags=re.M))
        dele = len(re.findall(r"^-(?!--)", b, flags=re.M))
        print("  %-58s +%-4d -%d" % (name, add, dele))


def cmd_stat(path):
    lines = read_lines(path)
    print("%s\n  %d 行 / %.1f KB" % (path, len(lines), os.path.getsize(path) / 1024))


def main():
    ap = argparse.ArgumentParser(description="省 token 的文档摘要工具")
    ap.add_argument("path", help="文件路径")
    ap.add_argument("--outline", action="store_true", help="只列标题（默认）")
    ap.add_argument("--head", type=int, help="前 N 行")
    ap.add_argument("--slice", help="行范围，如 120-180")
    ap.add_argument("--patch", action="store_true", help="补丁只列文件与增删行数")
    ap.add_argument("--stat", action="store_true", help="只报大小")
    a = ap.parse_args()

    if not os.path.exists(a.path):
        print("找不到文件：%s" % a.path)
        return 2
    if a.patch:
        cmd_patch(a.path)
    elif a.head:
        cmd_head(a.path, a.head)
    elif a.slice:
        m = re.match(r"^(\d+)-(\d+)$", a.slice.strip())
        if not m:
            print("--slice 格式：120-180")
            return 2
        cmd_slice(a.path, int(m.group(1)), int(m.group(2)))
    elif a.stat:
        cmd_stat(a.path)
    else:
        cmd_outline(a.path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
