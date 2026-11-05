# -*- coding: utf-8 -*-
"""measure_choice.py 的自测：用「已知答案」的合成图验检测器。

为什么合成而不是拿原版截图：原版截图的背景是花的人物 CG，读数会被背景带跑，
不能当标尺。这里用纯深色背景 + 真素材合成一张 800×450，答案是写死的：
  第 1 条 quad 上沿 148、第 2 条 200、行距 52、左端 155、宽 490、高 45。
检测器应该能读回：上沿 148+7.2 / 200+7.2（7.2 = 贴图 50% 不透明处离帧顶）、行距 52。

素材不在（干净 clone）就直接跳过：这两个 png 是本地素材，不入库。

    python tools/test_measure_choice.py
"""
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PROG = os.path.dirname(HERE)
ASSETS = os.path.join(PROG, "res", "assets", "ui", "choice")
OUT = os.path.join(PROG, "work_scratch")
INSET = 11.5 * 0.625          # 贴图 50% 不透明行 → 舞台 px
BAR_X, BAR_W, BAR_H = 155, 490, 45
ROW0, PITCH = 148, 52

FAIL = []


def ok(cond, msg):
    print(("  √ " if cond else "  × ") + msg)
    if not cond:
        FAIL.append(msg)


def _bar(name):
    p = os.path.join(ASSETS, name)
    if not os.path.isfile(p):
        return None
    return Image.open(p).convert("RGBA").resize((BAR_W, BAR_H), Image.LANCZOS)


def build(path):
    """第 1 条用段1（常态）、第 2 条用段2（悬停，几乎不透明）——
    两条都是「贴图自己的 alpha 坡」，50% 交叉点有确定答案，能当标尺。"""
    off, on = _bar("bar_off.png"), _bar("bar_on.png")
    if off is None:
        return False
    canvas = Image.new("RGBA", (800, 450), (18, 28, 42, 255))
    canvas.alpha_composite(off, (BAR_X, ROW0))
    canvas.alpha_composite(on if on is not None else off, (BAR_X, ROW0 + PITCH))
    canvas.convert("RGB").save(path)
    return True


def main():
    if not os.path.isfile(os.path.join(ASSETS, "bar_off.png")):
        print("跳过：没有 res/assets/ui/choice/bar_off.png（本地素材，不入库）")
        return 0
    os.makedirs(OUT, exist_ok=True)
    shot = os.path.join(OUT, "test_measure_choice.png")
    if not build(shot):
        print("跳过：素材读不出来")
        return 0

    sys.path.insert(0, HERE)
    import measure_choice as M

    print("合成图（答案：上沿 148/200、行距 52、左端 155、宽 490、高 45）")
    res = M.measure(shot)
    bands = res["bands"]
    ok(len(bands) == 2, "找到 2 条（实得 %d）" % len(bands))
    if len(bands) < 2:
        print("失败：条数不对，后面跳过")
        return 1

    top1, bot1, _ = bands[0]
    top2, bot2, _ = bands[1]
    ok(abs(top1 - (ROW0 + INSET)) <= 2.0,
       "第 1 条上沿 %.1f ≈ %.1f" % (top1, ROW0 + INSET))
    ok(abs(top2 - (ROW0 + PITCH + INSET)) <= 2.0,
       "第 2 条上沿 %.1f ≈ %.1f" % (top2, ROW0 + PITCH + INSET))
    ok(abs(res["pitch"] - PITCH) <= 2.0, "行距 %.1f ≈ %d" % (res["pitch"], PITCH))
    ok(res.get("strong") is bands[1], "最亮那条认成第 2 条（加法高亮）")
    ok(res.get("left") is not None and abs(res["left"] - (BAR_X + 20.3)) <= 4.0,
       "左端 50%% 点 %.1f ≈ %.1f" % (res["left"] or -1, BAR_X + 20.3))
    ok(abs((bot1 - top1) - 24.0) <= 3.0, "第 1 条厚度 %.1f ≈ 24（贴图可见高）" % (bot1 - top1))

    # 只有一条时：行距给 None，不许瞎报
    one = res["bands"][0]
    ok(one is not None and len(bands) == 2, "bands 结构正常")

    # 空白图：不许硬给数字
    blank = Image.new("RGB", (800, 450), (18, 28, 42))
    blank.save(shot)
    r2 = M.measure(shot)
    ok(not r2["bands"], "纯色图不报条子（实得 %d 条）" % len(r2["bands"]))

    print()
    if FAIL:
        print("FAIL %d 项" % len(FAIL))
        return 1
    print("PASS 全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
