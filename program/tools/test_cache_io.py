# -*- coding: utf-8 -*-
"""缓存读取守卫的自测（不联网、不开界面）。

跑法：
    cd program
    build_env/venv/Scripts/python.exe tools/test_cache_io.py

验的是：
  1. 不存在的文件 → None，不算坏
  2. 0 字节文件 → 删掉 + None
  3. 坏 JSON → 删掉 + 返回默认值
  4. 正常 JSON → 原样读出，文件保留
  5. 半截 PNG（没有 IEND）→ 删掉
  6. 完整 PNG → 原样读出
  7. 坏 .json.gz → 删掉
  8. stats 记到 checked / dropped
"""
import gzip
import json
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROGRAM, "src"))

import cache_io  # noqa: E402

FAILS = []
TMP = tempfile.mkdtemp(prefix="wa2_cacheio_test_")

PNG_OK = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32 + b"IEND\xaeB`\x82"


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:200]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def put(name, data):
    p = os.path.join(TMP, name)
    with open(p, "wb") as f:
        f.write(data)
    return p


def main():
    cache_io.reset_stats()

    p = os.path.join(TMP, "nope.json")
    check("不存在的文件返回 None", cache_io.read_json(p) is None)
    check("不存在的文件不算 dropped", cache_io.stats()["dropped"] == 0, cache_io.stats())

    p = put("empty.json", b"")
    check("0 字节返回 None", cache_io.read_json(p) is None)
    check("0 字节文件被删掉", not os.path.exists(p))

    p = put("bad.json", b"{oops")
    check("坏 JSON 返回默认值", cache_io.read_json(p, {"d": 1}) == {"d": 1})
    check("坏 JSON 文件被删掉", not os.path.exists(p))

    p = put("ok.json", json.dumps({"a": 1}).encode("utf-8"))
    check("正常 JSON 读出来", cache_io.read_json(p) == {"a": 1})
    check("正常 JSON 文件保留", os.path.exists(p))

    p = put("ok.json.gz", gzip.compress(json.dumps([1, 2]).encode("utf-8")))
    check("正常 gz 读出来", cache_io.read_gz_json(p) == [1, 2])
    p = put("bad.json.gz", b"not gzip")
    check("坏 gz 返回默认值", cache_io.read_gz_json(p, []) == [])
    check("坏 gz 文件被删掉", not os.path.exists(p))

    p = put("half.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 40)
    check("半截 PNG 返回 None", cache_io.read_image(p) is None)
    check("半截 PNG 被删掉", not os.path.exists(p))

    p = put("full.png", PNG_OK)
    check("完整 PNG 读出来", cache_io.read_image(p) == PNG_OK)
    check("完整 PNG 文件保留", os.path.exists(p))

    p = put("notpng.bin", b"hello world" * 10)
    check("不是 PNG 返回 None", cache_io.read_image(p) is None)
    check("不是 PNG 被删掉", not os.path.exists(p))

    st = cache_io.stats()
    check("stats 有 checked", st["checked"] > 0, st)
    check("stats 记了 dropped", st["dropped"] == 5, st)

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), " / ".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
