# -*- coding: utf-8 -*-
"""界面像素测量（measure_ui.py）的自测（#14，不联网、不开界面）。

跑法：
    cd program
    build_env/venv/Scripts/python.exe tools/test_measure_ui.py

用 Pillow 画「已知答案」的合成图来验检测器：
  1. 1600×900 原图（缩放 0.5）：行距 60 舞台px、第一个峰 76.8、槽位宽 395、宽高比 6.583
  2. 800×450 预览图：整体 +2px → compare 的偏移应该是 +2，且「只有平移没有形变」
  3. 放大 2% 的预览图 → 周期比 / 宽比 ≈ 1.02，并且报「被拉伸」
  4. verify：带黑边的截图先裁黑边再量，数字不变
  5. 非 16:9 → 给警告；一条线都没有 → compare 返回失败而不是抛
"""
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from PIL import Image, ImageDraw  # noqa: E402

import measure_ui as M  # noqa: E402

FAILS = []
TMP = tempfile.mkdtemp(prefix="wa2_measure_test_")

BG = 40
SLOT = 90
LINE = 240

# 舞台坐标下的「标准答案」
STAGE_FIRST = 76.8
STAGE_PITCH = 60.0
STAGE_W_SLOT = 395.0
ASSET = (1896, 288)


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:200]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def draw_scene(w, h, shift=0.0, scale=1.0, pad=0, line=True):
    """画一张「存档界面」示意图：5 条亮线 + 5 个槽位框。

    shift/scale 是**舞台坐标**下的偏移和缩放；内部按 w/800 换算成图像像素。
    pad>0 时四周留黑边（用来测 verify 的裁黑边）。
    """
    img = Image.new("L", (w + pad * 2, h + pad * 2), 0)
    d = ImageDraw.Draw(img)
    d.rectangle([pad, pad, pad + w - 1, pad + h - 1], fill=BG)
    k = w / 800.0

    def X(v):
        return pad + v * k

    def Y(v):
        return pad + v * k

    for i in range(5):
        y = (STAGE_FIRST + i * STAGE_PITCH) * scale + shift
        top = Y(y)
        if line and 0 <= top < h:
            # 真实截图上的白线是 2~4px 粗的（1px 的线会被平滑抹掉，不能拿来测）
            lw = max(2, int(round(2 * k)))
            d.line([X(20), top, X(420), top], fill=LINE, width=lw)
        # 槽位框：从这条线往下半个行距到下一行
        y0 = top + 2
        y1 = Y((STAGE_FIRST + i * STAGE_PITCH + STAGE_PITCH * 0.85) * scale + shift)
        x0 = X(5.4 * scale)
        x1 = X((5.4 * scale) + STAGE_W_SLOT * scale)
        if y1 > y0 and x1 > x0:
            d.rectangle([x0, y0, x1, y1], fill=SLOT)
    return img


def main():
    a_path = os.path.join(TMP, "original_1600.png")
    draw_scene(1600, 900).save(a_path)

    info = M.detect(a_path, asset=ASSET)
    check("原图：识别出 5 条线", len(info["peaks"]) == 5, info["peaks"])
    check("原图：行距 60 舞台px（±0.5）", abs(info["pitch_stage"] - STAGE_PITCH) <= 0.5,
          info["pitch_stage"])
    check("原图：第一个峰 76.8（±1）", abs(info["first_stage"] - STAGE_FIRST) <= 1.0,
          info["first_stage"])
    check("原图：槽位宽 395（±2）", info["width_stage"] and abs(info["width_stage"] - STAGE_W_SLOT) <= 2,
          info["width_stage"])
    check("原图：宽高比 ≈ 素材（差 <1%）",
          info["ratio"] is not None and info["ratio_error"] < 0.01,
          (info["ratio"], info.get("asset_ratio"), info.get("ratio_error")))

    # 2) 整体 +2px
    b_path = os.path.join(TMP, "preview_shift2.png")
    draw_scene(800, 450, shift=2.0).save(b_path)
    res = M.compare(a_path, b_path, asset=ASSET, out=lambda *_: None)
    check("compare：偏移 +2.0（±0.5）", res.get("offset_px") is not None and
          abs(res["offset_px"] - 2.0) <= 0.5, res.get("offset_px"))
    check("compare：周期比 ≈ 1", res.get("pitch_ratio") and
          abs(res["pitch_ratio"] - 1) <= 0.01, res.get("pitch_ratio"))
    check("compare：宽比 ≈ 1", res.get("width_ratio") and
          abs(res["width_ratio"] - 1) <= 0.01, res.get("width_ratio"))
    check("compare：判定「只有平移」", res.get("ok") is True, res.get("problems"))

    # 3) 放大 2%（模拟元素被拉伸）
    c_path = os.path.join(TMP, "preview_scale102.png")
    draw_scene(800, 450, shift=0.0, scale=1.02).save(c_path)
    res2 = M.compare(a_path, c_path, asset=ASSET, out=lambda *_: None)
    check("放大 2%：周期比 ≈ 1.02（±0.01）",
          res2.get("pitch_ratio") and abs(res2["pitch_ratio"] - 1.02) <= 0.01,
          res2.get("pitch_ratio"))
    check("放大 2%：宽比 ≈ 1.02（±0.02）",
          res2.get("width_ratio") and abs(res2["width_ratio"] - 1.02) <= 0.02,
          res2.get("width_ratio"))
    check("放大 2%：报出问题（不是「只有平移」）",
          res2.get("ok") is False and res2.get("problems"), res2.get("problems"))

    # 4) verify：带 30px 黑边的 800×450 截图
    d_path = os.path.join(TMP, "shot_with_border.png")
    draw_scene(800, 450, pad=30).save(d_path)
    v = M.verify(d_path, out=lambda *_: None)
    check("verify：裁出了黑边", v.get("cropped") is not None, v.get("cropped"))
    check("verify：裁完仍是 5 条线", len(v["peaks"]) == 5, v["peaks"])
    check("verify：行距仍是 60（±1）", abs(v["pitch_stage"] - STAGE_PITCH) <= 1.0, v["pitch_stage"])
    check("verify：第一个峰仍是 76.8（±2）", abs(v["first_stage"] - STAGE_FIRST) <= 2.0, v["first_stage"])

    # 5) 非 16:9 警告 / 空图不炸
    e_path = os.path.join(TMP, "not169.png")
    draw_scene(800, 400).save(e_path)
    ie = M.detect(e_path)
    check("非 16:9：给警告", any("16:9" in w for w in ie["warnings"]), ie["warnings"])

    blank = os.path.join(TMP, "blank.png")
    Image.new("L", (800, 450), 20).save(blank)
    ib = M.detect(blank)
    check("空白图：找不到峰也不抛", ib["peaks"] == [] and ib["pitch_stage"] == 0, ib["peaks"])
    res3 = M.compare(blank, blank, out=lambda *_: None)
    check("两张空白比：返回失败而不是抛", res3.get("ok") is False and res3.get("problems"),
          res3.get("problems"))

    # 噪声图：不能假装量到了
    noise = os.path.join(TMP, "noise.png")
    im = Image.new("L", (800, 450), 30)
    px = im.load()
    import random
    random.seed(7)
    for y in range(450):
        for x in range(0, 800, 3):
            px[x, y] = random.randint(20, 200)
    im.save(noise)
    noise_info = M.detect(noise)
    check("噪声图：自信度低（不会假装量到行距）", noise_info.get("confident") is False,
          (noise_info.get("confident"), noise_info.get("pitch_hits")))
    check("噪声图：给出提示", any("没找到稳定的行距" in w for w in noise_info["warnings"]),
          noise_info["warnings"])

    # 正常图：自信度应该是高的
    check("正常图：自信", M.detect(a_path)["confident"] is True)

    # 6) CLI 的素材尺寸解析
    check("--asset 解析 1896x288", M._asset("1896x288") == (1896, 288))
    check("--asset 支持 *", M._asset("1896*288") == (1896, 288))
    check("--asset 空值返回 None", M._asset("") is None)

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), " / ".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
