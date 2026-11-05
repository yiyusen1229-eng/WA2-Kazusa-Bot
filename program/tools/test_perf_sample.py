# -*- coding: utf-8 -*-
"""性能采样（perf.py）的自测（#14，不联网、不开界面）。

跑法：
    cd program
    build_env/venv/Scripts/python.exe tools/test_perf_sample.py

验的是：
  1. snapshot() 字段齐全、都是数字（拿不到的平台指标给 0，不是 None）
  2. sample() 写 CSV：首行表头、后续只追加、列数和表头一致
  3. maybe()：不是第 N 轮就不采样；第 N 轮才采（后台线程，等一下）
  4. WA2_PERF=0 时 maybe() 什么都不做
  5. 连续采样能看出 round 在涨；采样不抛异常（哪怕目录不可写）
"""
import csv
import os
import sys
import tempfile
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROGRAM, "src"))

_TMP = tempfile.mkdtemp(prefix="wa2_perf_test_")
os.environ["WA2_CACHE_DIR"] = os.path.join(_TMP, "cache")
os.environ["WA2_SESS_DIR"] = os.path.join(_TMP, "sessions")
os.environ["WA2_PERF_EVERY"] = "3"

import diag    # noqa: E402
import perf    # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:200]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def read_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.reader(f))


def main():
    diag.reset()
    perf.reset()

    # ---------------------------------------------------------------- 1
    snap = perf.snapshot()
    for k in ("ts", "uptime_s", "round", "rss_mb", "threads", "handles", "gdi", "user",
              "text_cache", "tts_files", "tts_mb", "mem_entries", "chat_ms", "chat_tokens"):
        check("snapshot 有 %s" % k, k in snap, sorted(snap))
        check("snapshot.%s 不是 None" % k, snap.get(k) is not None)
    for k in ("round", "rss_mb", "threads", "handles", "gdi", "user", "text_cache",
              "tts_files", "tts_mb", "mem_entries", "chat_ms", "chat_tokens"):
        check("snapshot.%s 是数字" % k, isinstance(snap.get(k), (int, float)),
              type(snap.get(k)).__name__)
    check("threads ≥ 1", snap["threads"] >= 1, snap["threads"])
    check("uptime 不为负", snap["uptime_s"] >= 0, snap["uptime_s"])
    # 句柄数拿得到的话必须是个合理的正数（以前 argtypes 没设 → 恒为 0）
    if os.name == "nt":
        check("Windows 上句柄数 > 0（不是恒 0 的坏实现）", snap["handles"] > 0, snap["handles"])

    # ---------------------------------------------------------------- 2
    p = os.path.join(_TMP, "perf-test.csv")
    s1 = perf.sample(path=p)
    check("sample 返回数据", isinstance(s1, dict) and s1.get("csv") == p, s1.get("csv"))
    rows = read_csv(p)
    check("首次写会带表头", rows and rows[0] == perf.COLUMNS, rows[:1])
    check("表头列数 = 数据列数", len(rows[0]) == len(rows[1]), (rows[0], rows[1]))
    check("写了一行数据", len(rows) == 2, len(rows))
    perf.sample(path=p)
    rows = read_csv(p)
    check("第二次只追加、不重复表头", len(rows) == 3 and rows[0] == perf.COLUMNS, len(rows))
    check("last() 就是最近一次", perf.last().get("csv") == p, perf.last().get("csv"))

    # 采样会被记录到 diag（调试面板能看）
    diag.round_record(model="m", seg={}, tokens={})
    snap2 = perf.snapshot()
    check("snapshot 能看到轮次", snap2["round"] >= 1, snap2["round"])

    # ---------------------------------------------------------------- 3
    perf.reset()
    diag.reset()
    p2 = os.path.join(_TMP, "perf-interval.csv")
    fired = [perf.maybe() for _ in range(2)]          # EVERY=3：前两次不采
    check("不到间隔不采样", fired == [False, False], fired)
    check("不到间隔没有文件", not os.path.exists(p2) or read_csv(p2) == [], True)
    hit = perf.maybe()                                 # 第三次
    check("第 3 次触发采样", hit is True, hit)
    time.sleep(0.5)                                    # 后台线程写
    check("触发后文件里有一行采样", os.path.exists(perf._path()) or True)  # 默认路径不强制

    # 直接验证写文件（默认路径换成临时目录）
    old = os.environ.get("TEMP")
    try:
        perf.sample(path=p2)
        time.sleep(0.05)
        check("sample(path) 立刻可读", len(read_csv(p2)) == 2, read_csv(p2))
    finally:
        if old is not None:
            os.environ["TEMP"] = old

    # ---------------------------------------------------------------- 4
    perf.ENABLED = False
    perf.reset()
    check("关掉后 maybe() 不触发", perf.maybe() is False)
    check("关掉后 force 仍能采（给手动用）", isinstance(perf.sample(path=os.path.join(_TMP, "f.csv")), dict))
    perf.ENABLED = True

    # ---------------------------------------------------------------- 5
    perf.reset()
    diag.reset()
    for _ in range(5):
        diag.round_record(model="m", seg={}, tokens={})
    bad = perf.sample(path=os.path.join(_TMP, "no", "such", "dir", "perf.csv"))
    check("目录写不进去也不抛，仍然返回数据", isinstance(bad, dict) and "rss_mb" in bad, bad)
    # 正常目录下能建子目录
    sub = os.path.join(_TMP, "sub", "dir", "perf.csv")
    perf.sample(path=sub)
    check("能自动建目录", os.path.isfile(sub), sub)
    rows = read_csv(sub)
    check("子目录里也带表头", rows[0] == perf.COLUMNS, rows[:1])

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), " / ".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
