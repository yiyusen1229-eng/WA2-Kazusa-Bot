# -*- coding: utf-8 -*-
"""素材热重载（hotreload.py）的自测（#20，不联网、不开界面）。

跑法：
    cd program
    build_env/venv/Scripts/python.exe tools/test_hotreload.py

验的是：
  1. 第一次 tick 只记基线，不算「变了」
  2. 文件变了：第一个 tick 只挂起，等签名稳定一个 SETTLE 才真正触发（避免拷到一半）
  3. 触发时：gen +1、kinds 正确、所有勾子都被调用
  4. 关掉（enabled=False）时什么都不做
  5. 某个勾子抛错：别的勾子照跑，错误记进 state()，不把巡检线程弄死
  6. 角色目录变了 → kinds 里是 character（切角色后自动跟着走）
  7. start/stop 线程生命周期；state() 字段齐全
"""
import json
import os
import sys
import tempfile
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROGRAM, "src"))

_TMP = tempfile.mkdtemp(prefix="wa2_hotreload_test_")
os.environ["WA2_USER_DIR"] = _TMP
os.environ["WA2_CACHE_DIR"] = os.path.join(_TMP, "cache")
os.environ["WA2_HOTRELOAD_S"] = "60"          # 线程不用真跑那么勤

import characters  # noqa: E402
import hotreload   # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:200]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def main():
    assets = os.path.join(_TMP, "assets")
    os.makedirs(os.path.join(assets, "cg"), exist_ok=True)
    cid = "和纱"
    char = os.path.join(_TMP, "characters", cid)
    os.makedirs(os.path.join(char, "portrait"), exist_ok=True)
    with open(os.path.join(_TMP, "characters", "active.json"), "w", encoding="utf-8") as f:
        json.dump({"id": cid}, f, ensure_ascii=False)

    called = []
    hotreload.reset()
    hotreload.watch(assets, char)
    hotreload.set_hooks({
        "one": lambda kinds: called.append(("one", list(kinds))),
        "two": lambda kinds: called.append(("two", list(kinds))),
    })

    # ---------------- 1 基线
    t0 = 1000.0
    check("第一次 tick 不算「变了」", hotreload.tick(now=t0) is False)
    check("第一次 tick 不调勾子", called == [], called)

    # ---------------- 2/3 变了 → 等稳定 → 触发
    time.sleep(0.01)
    with open(os.path.join(assets, "cg", "a.png"), "wb") as f:
        f.write(b"x" * 100)
    check("刚变：只挂起不触发", hotreload.tick(now=t0 + 1) is False)
    check("刚变：还没调勾子", called == [], called)
    check("稳定一个 SETTLE 之后触发", hotreload.tick(now=t0 + 1 + hotreload.SETTLE + 0.01) is True)
    check("勾子被调了（两个都调）", [c[0] for c in called] == ["one", "two"], called)
    check("kinds 里有 assets", called and called[0][1] == ["assets"], called)
    st = hotreload.state()
    check("gen 变成 1", st["gen"] == 1, st["gen"])
    check("last_kinds 记录正确", st["last_kinds"] == ["assets"], st["last_kinds"])
    check("没有错误", st["errors"] == [], st["errors"])
    check("state 字段齐全",
          set(st) >= {"ok", "enabled", "gen", "interval", "settle", "last_at",
                      "last_kinds", "errors", "ms", "watching", "running"}, sorted(st))

    # 再变一次：内容不同 → 再来一轮
    time.sleep(0.01)
    with open(os.path.join(assets, "cg", "a.png"), "wb") as f:
        f.write(b"y" * 200)
    hotreload.tick(now=t0 + 3)
    check("第二次变化也会触发", hotreload.tick(now=t0 + 3 + hotreload.SETTLE + 0.01) is True)
    check("gen 变成 2", hotreload.state()["gen"] == 2, hotreload.state()["gen"])

    # 没变化时不重复触发
    check("没变化 → 不触发", hotreload.tick(now=t0 + 10) is False)

    # ---------------- 4 关掉
    called.clear()
    hotreload.set_enabled(False)
    time.sleep(0.01)
    with open(os.path.join(assets, "cg", "a.png"), "wb") as f:
        f.write(b"z" * 300)
    check("关掉之后 tick 直接返回 False", hotreload.tick(now=t0 + 20) is False)
    check("关掉之后不调勾子", called == [], called)
    hotreload.set_enabled(True)
    hotreload.reset()
    hotreload.watch(assets, char)
    hotreload.tick(now=t0 + 21)                 # 重记基线

    # ---------------- 5 勾子失败
    boom = []

    def bad(kinds):
        boom.append(kinds)
        raise RuntimeError("模拟加载失败")

    called.clear()
    hotreload.set_hooks({"bad": bad, "good": lambda kinds: called.append(("good", list(kinds)))})
    time.sleep(0.01)
    with open(os.path.join(assets, "cg", "b.png"), "wb") as f:
        f.write(b"1" * 50)
    hotreload.tick(now=t0 + 30)
    check("失败的那次也算触发", hotreload.tick(now=t0 + 30 + hotreload.SETTLE + 0.01) is True)
    check("坏勾子被调了", len(boom) == 1, boom)
    check("好勾子照跑", [c[0] for c in called] == ["good"], called)
    st = hotreload.state()
    check("错误被记进 state", any("模拟加载失败" in x for x in st["errors"]), st["errors"])
    check("巡检线程不受影响（还能继续 tick）", isinstance(hotreload.tick(now=t0 + 40), bool))

    # ---------------- 6 角色目录
    hotreload.reset()
    hotreload.watch(assets, char)
    hotreload.set_hooks({"one": lambda kinds: called.append(("one", list(kinds)))})
    called.clear()
    hotreload.tick(now=t0 + 50)
    time.sleep(0.01)
    with open(os.path.join(char, "portrait", "x.png"), "wb") as f:
        f.write(b"p" * 10)
    hotreload.tick(now=t0 + 51)
    hotreload.tick(now=t0 + 51 + hotreload.SETTLE + 0.01)
    check("角色目录变了 → kinds 是 character", called and called[-1][1] == ["character"], called)

    # ---------------- 6.5 运行时数据不参与签名（2026-11-05「素材已更新」狂弹的根因）
    hotreload.reset()
    hotreload.watch(assets, char)
    os.makedirs(os.path.join(char, "sessions"), exist_ok=True)
    os.makedirs(os.path.join(char, "memory"), exist_ok=True)
    hotreload.tick(now=t0 + 60)
    before_gen = hotreload.state()["gen"]
    for rel in (("sessions", "auto.json"), ("sessions", "2.json"), ("memory", "standing.json")):
        p = os.path.join(char, *rel)
        with open(p, "a", encoding="utf-8") as f:
            f.write("{}")
    hotreload.tick(now=t0 + 61)
    hotreload.tick(now=t0 + 61 + hotreload.SETTLE + 0.01)
    check("写自动存档 / 关系摘要 → 不算素材变了", hotreload.state()["gen"] == before_gen,
          hotreload.state()["gen"])
    with open(os.path.join(char, "portrait", "y.png"), "wb") as f:
        f.write(b"q" * 10)
    hotreload.tick(now=t0 + 62)
    hotreload.tick(now=t0 + 62 + hotreload.SETTLE + 0.01)
    check("写立绘 → 仍然算素材变了", hotreload.state()["gen"] > before_gen,
          hotreload.state()["gen"])
    check("跳过名单里有 sessions / cache", {"sessions", "cache"} <= set(hotreload.SKIP_DIRS),
          sorted(hotreload.SKIP_DIRS))

    # ---------------- 7 线程
    hotreload.set_enabled(True)
    check("start() 返回 True", hotreload.start() is True)
    check("线程在跑", hotreload.state()["running"] is True)
    check("重复 start 不会起第二个", hotreload.start() is False)
    check("stop() 之后 running=False", hotreload.stop() is True and
          hotreload.state()["running"] is False)
    hotreload.set_enabled(False)
    check("关掉之后 start() 不起线程", hotreload.start() is False)

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), " / ".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
