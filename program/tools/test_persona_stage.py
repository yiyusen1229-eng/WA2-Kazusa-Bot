# -*- coding: utf-8 -*-
"""关系阶段：云端分类 + 封顶 + 兜底的自测（不联网）"""
import os
import sys
import tempfile
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))
import persona_stage as P  # noqa: E402

FAILS = []
CALLS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def rounds(n, extra=""):
    """n 轮 = n 对 user/assistant"""
    out = []
    for i in range(n):
        out.append({"role": "user", "content": "第%d句，今天也聊聊吧" % i})
        out.append({"role": "assistant", "content": "「…嗯」"})
    if extra:
        out.append({"role": "user", "content": extra})
    return out


def fake_llm(system, user):
    CALLS.append(user)
    return "3"


def main():
    tmp = tempfile.mkdtemp(prefix="wa2_stage_")
    P.STATE_FILE = os.path.join(tmp, "persona_stage.json")
    P.set_llm(fake_llm)

    print("[1] 本地只认明确的 4")
    check("普通对话不误判", P.detect_local(rounds(3)) == 0)
    check("结婚 → 4", P.detect_local(rounds(1, "我们结婚吧")) == 4)

    print("\n[2] 云端每 40 轮判一次")
    P.reset()
    CALLS.clear()
    msgs = rounds(40)
    check("先返回旧阶段 1", P.current(msgs) == 1)
    if P._LAST["thread"]:
        P._LAST["thread"].join(timeout=5)
    check("云端判出 3", P.current(msgs) == 3, P._load())
    check("确实调了一次", len(CALLS) == 1, len(CALLS))

    print("\n[3] 只升不降 + 40 轮后再判")
    P.set_llm(lambda s, u: (CALLS.append(u), "2")[1])
    msgs2 = msgs + rounds(40)
    before = len(CALLS)
    P.current(msgs2)
    if P._LAST["thread"]:
        P._LAST["thread"].join(timeout=5)
    check("又调了一次", len(CALLS) == before + 1, len(CALLS))
    check("低标签不降级", P.current(msgs2) == 3, P._load())

    print("\n[4] 到 4 封顶，不再调用")
    P.set_llm(lambda s, u: (CALLS.append(u), "4")[1])
    msgs3 = msgs2 + rounds(40)
    P.current(msgs3)
    if P._LAST["thread"]:
        P._LAST["thread"].join(timeout=5)
    check("升到 4", P.current(msgs3) == 4, P._load())
    n = len(CALLS)
    P.current(msgs3 + rounds(40))
    check("到顶后不再调用", len(CALLS) == n, "%d -> %d" % (n, len(CALLS)))

    print("\n[5] 明确的 4 不用等云端")
    P.reset()
    n = len(CALLS)
    check("结婚直接 4", P.current(rounds(1, "我们结婚吧")) == 4)
    check("没有调用云端", len(CALLS) == n)

    print("\n[6] 云端失败 → 保持原阶段")
    P.reset()
    def boom(s, u):
        CALLS.append(u)
        raise RuntimeError("掉线")
    P.set_llm(boom)
    P.current(rounds(40))
    if P._LAST["thread"]:
        P._LAST["thread"].join(timeout=5)
    check("失败不崩、保持 1", P.current(rounds(40)) == 1, P._load())

    print("\n" + ("全部通过" if not FAILS else "失败 %d 项：%s" % (len(FAILS), "、".join(FAILS))))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
