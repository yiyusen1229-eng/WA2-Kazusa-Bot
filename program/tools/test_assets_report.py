# -*- coding: utf-8 -*-
"""素材自检报告的自测（不联网、不开界面）。

跑法：
    cd program
    build_env/venv/Scripts/python.exe tools/test_assets_report.py

验的是：
  1. 背景索引里列的文件缺失 → 进 missing
  2. 背景文件 0 字节 → 进 zero
  3. 立绘索引里列的默认图 / 表情图缺失 → 进 missing
  4. 参考语音 0 字节 → 进 zero
  5. 全齐时 ok=True，summary 报「都正常」
  6. write() 原子落盘、不留 .tmp
"""
import json
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROGRAM, "src"))

import assets_report  # noqa: E402

FAILS = []
TMP = tempfile.mkdtemp(prefix="wa2_assets_test_")
ASSETS = os.path.join(TMP, "assets")
CHAR = os.path.join(TMP, "char")
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32 + b"IEND\xaeB`\x82"


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:220]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def put(path, data=PNG):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def main():
    # 背景：1 好 1 空 1 缺
    os.makedirs(os.path.join(ASSETS, "cg"), exist_ok=True)
    put(os.path.join(ASSETS, "cg", "好背景.webp"), PNG)
    put(os.path.join(ASSETS, "cg", "空背景.webp"), b"")
    with open(os.path.join(ASSETS, "cg", "index.json"), "w", encoding="utf-8") as f:
        json.dump({"items": [
            {"id": "好背景", "file": "好背景.webp"},
            {"id": "空背景", "file": "空背景.webp"},
            {"id": "缺背景", "file": "缺背景.webp"},
        ]}, f, ensure_ascii=False)

    # 角色：立绘 1 好 1 缺；语音 1 好 1 空
    pdir = os.path.join(CHAR, "portrait")
    put(os.path.join(pdir, "校服", "认真.png"), PNG)
    with open(os.path.join(pdir, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"height": 900, "outfits": {
            "校服": {"default": "认真.png",
                     "variants": [
                         {"variant": "101", "file": "认真.png", "emotion": "serious"},
                         {"variant": "102", "file": "缺表情.png", "emotion": "sad"},
                     ]}
        }}, f, ensure_ascii=False)
    put(os.path.join(CHAR, "voice", "ref.wav"), b"RIFF" * 10)
    put(os.path.join(CHAR, "voice", "empty.wav"), b"")

    r = assets_report.build(ASSETS, CHAR)
    missing = [(m["kind"], m.get("file")) for m in r["missing"]]
    zero = [(z["kind"], z.get("file")) for z in r["zero"]]

    check("背景缺失进 missing", ("cg", "缺背景.webp") in missing, missing)
    check("背景 0 字节进 zero", ("cg", "空背景.webp") in zero, zero)
    check("立绘缺失进 missing", ("portrait", "缺表情.png") in missing, missing)
    check("语音 0 字节进 zero",
          any(z[0] == "voice" and "empty.wav" in str(z[1]) for z in zero), zero)
    check("有缺失时 ok=False", r["ok"] is False, r["ok"])
    check("统计了文件数", r["checked"] >= 6, r["checked"])
    check("统计了体积", r["bytes"] > 0, r["bytes"])
    check("summary 报缺失", "缺" in assets_report.summary(r), assets_report.summary(r))

    # 全齐
    put(os.path.join(ASSETS, "cg", "空背景.webp"), PNG)
    put(os.path.join(ASSETS, "cg", "缺背景.webp"), PNG)
    put(os.path.join(pdir, "校服", "缺表情.png"), PNG)
    put(os.path.join(CHAR, "voice", "empty.wav"), b"RIFF" * 10)
    r2 = assets_report.build(ASSETS, CHAR)
    check("全齐时 ok=True", r2["ok"] is True, (r2["missing"], r2["zero"]))
    check("summary 报都正常", "都正常" in assets_report.summary(r2),
          assets_report.summary(r2))

    # 落盘
    out = os.path.join(TMP, "logs", "asset_report.json")
    p = assets_report.write(out, r2)
    check("报告写出来了", bool(p) and os.path.exists(out), p)
    check("不留 .tmp", not os.path.exists(out + ".tmp"))
    d = json.load(open(out, encoding="utf-8"))
    check("报告内容可解析", d.get("checked") == r2["checked"], d.get("checked"))

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), " / ".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
