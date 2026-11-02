# -*- coding: utf-8 -*-
"""关系阶段判断的自测（不调用模型）"""
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))
import persona_stage as P  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def main():
    tmp = tempfile.mkdtemp(prefix="wa2_stage_")
    P.STATE_FILE = os.path.join(tmp, "persona_stage.json")

    print("[1] 关键词")
    check("普通聊天 → 1", P.detect([{"content": "早上好"}]) == 0)
    check("想你 → 2", P.detect([{"content": "有点想你"}]) == 2)
    check("喜欢你 → 3", P.detect([{"content": "我喜欢你"}]) == 3)
    check("结婚 → 4", P.detect([{"content": "我们结婚吧"}]) == 4)
    check("多阶段取最高", P.detect([{"content": "想你，喜欢你，结婚吧"}]) == 4)

    print("\n[2] 单调递进 + 变小重置")
    P.reset()
    check("从 1 开始", P.current([{"content": "你好"}]) == 1)
    check("升到 2", P.current([{"content": "你好"}, {"content": "有点想你"}]) == 2)
    check("升到 3", P.current([{"content": "你好"}, {"content": "有点想你"},
                               {"content": "我喜欢你"}]) == 3)
    check("升到 4", P.current([{"content": "你好"}, {"content": "有点想你"},
                               {"content": "我喜欢你"}, {"content": "结婚吧"}]) == 4)
    check("关键词滚出最近段也不降",
          P.current([{"content": "你好"}, {"content": "有点想你"},
                     {"content": "我喜欢你"}, {"content": "结婚吧"},
                     {"content": "今天下雪了"}]) == 4)
    check("历史变短（新游戏）→ 回 1", P.current([{"content": "你好"}]) == 1)

    print("\n[3] 读档重置")
    P.current([{"content": "喜欢你"}])
    P.reset()
    check("重置后按新历史判", P.current([{"content": "随便聊聊"}]) == 1)

    print("\n" + ("全部通过" if not FAILS else "失败 %d 项：%s" % (len(FAILS), "、".join(FAILS))))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
