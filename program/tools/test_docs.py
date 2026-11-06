# -*- coding: utf-8 -*-
"""文档自测：架构文档 / 交接文档里的相对链接必须真的存在，且索引页列到了每份叶子。

为什么值得测：文档改个文件名、「不要动.md」换个位置，链接就悄悄烂掉；
而 AI 和新会话恰恰靠这些链接找入口，烂了自己不会报错。

    cd program && .\\build_env\\venv\\Scripts\\python.exe tools\\test_docs.py
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DOCS = os.path.join(REPO, "other", "docs")
FAILS = []

# 必须存在、且要被别处引用的文档
MUST = [
    os.path.join(DOCS, "不要动.md"),
    os.path.join(DOCS, "架构", "00b_数据流.md"),
]

SCAN = [
    os.path.join(REPO, "AGENTS.md"),
    os.path.join(REPO, "README.md"),
    os.path.join(DOCS, "不要动.md"),
    os.path.join(DOCS, "交接速览.md"),
    os.path.join(DOCS, "架构", "00_总览.md"),
    os.path.join(DOCS, "架构", "00b_数据流.md"),
]

LINK = re.compile(r"\]\((\.\.?/[^)#\s]+|[0-9A-Za-z_\-]+\.md)(#[^)]*)?\)")


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:220]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def main():
    print("[1] 新文档在不在")
    for p in MUST:
        check("存在：" + os.path.relpath(p, REPO), os.path.isfile(p), p)

    print("[2] 被入口文档引用（否则没人找得到）")
    agents = io.open(os.path.join(REPO, "AGENTS.md"), encoding="utf-8").read()
    overview = io.open(os.path.join(DOCS, "架构", "00_总览.md"), encoding="utf-8").read()
    check("AGENTS.md 指向不要动.md", "不要动.md" in agents)
    check("AGENTS.md 指向数据流", "00b_数据流" in agents or "数据流" in agents)
    check("00_总览 链接数据流", "00b_数据流" in overview)
    check("00_总览 链接不要动", "不要动" in overview)

    print("[3] 文档里的相对链接都能打开")
    bad = []
    for p in SCAN:
        if not os.path.isfile(p):
            bad.append("缺文件 " + os.path.relpath(p, REPO))
            continue
        t = io.open(p, encoding="utf-8").read()
        for m in LINK.finditer(t):
            rel = m.group(1)
            target = os.path.normpath(os.path.join(os.path.dirname(p), rel))
            if not os.path.exists(target):
                bad.append("%s -> %s" % (os.path.relpath(p, REPO), rel))
    check("没有断链", not bad, bad[:8])

    print("[4] 架构叶子文档都被 00_总览 列到")
    leaf_dir = os.path.join(DOCS, "架构")
    # 00_总览 是索引自己，不用登记自己
    leaves = [f for f in os.listdir(leaf_dir)
              if f.endswith(".md") and f[0].isdigit() and not f.startswith("00_")]
    missing = [f for f in leaves if f not in overview]
    check("每份叶子都出现在总览里", not missing, missing)

    print("[5] 不要动.md 每条都带「正确改法」")
    nd = io.open(os.path.join(DOCS, "不要动.md"), encoding="utf-8").read()
    heads = re.findall(r"(?m)^## (\d+)\..*$", nd)
    fixes = nd.count("**正确改法**")
    effects = nd.count("**动了会怎样**")
    check("有条目", len(heads) >= 10, len(heads))
    check("每条都有「动了会怎样」", effects == len(heads), (effects, len(heads)))
    check("每条都有「正确改法」", fixes == len(heads), (fixes, len(heads)))

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), "、".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
