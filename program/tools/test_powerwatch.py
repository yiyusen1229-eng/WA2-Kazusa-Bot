# -*- coding: utf-8 -*-
"""powerwatch（睡眠唤醒检测）的自测：喂假墙钟，不睡觉、不联网。

    cd program && .\\build_env\\venv\\Scripts\\python.exe tools\\test_powerwatch.py
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, __file__.rsplit("tools", 1)[0] + "src")

import powerwatch  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:200]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def main():
    powerwatch.reset()

    print("[1] 正常节奏不触发")
    check("第一轮只记基线", powerwatch.tick(1000.0) is False)
    check("+5 秒不算唤醒", powerwatch.tick(1005.0) is False)
    check("+19 秒（还没到阈值）不算", powerwatch.tick(1024.0) is False)
    check("gen 还是 0", powerwatch.gen() == 0, powerwatch.gen())

    print("[2] 跳一大截 = 刚唤醒")
    check("+600 秒触发", powerwatch.tick(1624.0) is True)
    check("gen 变 1", powerwatch.gen() == 1, powerwatch.gen())
    st = powerwatch.state()
    check("last_gap 记到 600", st.get("last_gap") == 600.0, st.get("last_gap"))
    check("记下了时间点", bool(st.get("at")), st.get("at"))
    check("字段齐全", set(st) >= {"gen", "last_gap", "at", "interval", "jump_s", "running"},
          sorted(st))

    print("[3] 连续两次唤醒")
    check("再跳一次也触发", powerwatch.tick(3000.0) is True)
    check("gen 变 2", powerwatch.gen() == 2, powerwatch.gen())
    check("紧接着的 +5 秒不再触发", powerwatch.tick(3005.0) is False)
    check("gen 仍是 2", powerwatch.gen() == 2, powerwatch.gen())

    print("[4] 阈值就是 JUMP_S")
    powerwatch.reset()
    powerwatch.tick(10.0)
    check("差 19.9 秒不触发", powerwatch.tick(10.0 + powerwatch.JUMP_S - 0.1) is False)
    powerwatch.reset()
    powerwatch.tick(10.0)
    check("差 20.0 秒触发", powerwatch.tick(10.0 + powerwatch.JUMP_S) is True)

    print("[5] 线程能起停")
    check("start() 返回 True", powerwatch.start() is True)
    import time
    time.sleep(0.2)
    check("running=True", powerwatch.state().get("running") is True)
    check("重复 start 不会起第二个", powerwatch.start() is False)
    check("stop() 之后 running=False", powerwatch.stop() is True
          and powerwatch.state().get("running") is False)

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), "、".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
