# -*- coding: utf-8 -*-
"""参数扫描: 找出与游戏最接近的 描边宽度 + 高斯模糊

对齐的统计量(尺度无关):
  白芯平均亮度     游戏 228
  描边平均亮度     游戏 140
  暗像素/白芯 比例 游戏 4.11   (反映描边粗细)
"""
import itertools
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage

sys.path.insert(0, r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\app")

FONT = r"C:/Windows/Fonts/msyh.ttc"
FS = 28
TXT = "……有事？"
TARGET_WHITE = 228.0
TARGET_RING = 140.0
TARGET_RATIO = 4.11


def stats(im):
    a = np.array(im.convert("RGB")).astype(np.float32)
    g = a.mean(2)
    mx, mn = a.max(2), a.min(2)
    sat = mx - mn
    white = (g > 200) & (sat < 40)
    if white.sum() < 50:
        return None
    dil = ndimage.binary_dilation(white, iterations=2)
    ring = dil & ~white
    dark = (g < 90) & (sat < 60)
    return dict(
        white=float(a[white].mean()),
        ring=float(g[ring].mean()) if ring.sum() else 0.0,
        ratio=float(dark.sum()) / max(1, int(white.sum())),
        wn=int(white.sum()),
    )


def render(stroke, blur, stroke_color=(0, 0, 0)):
    tile = 32 + 4
    lib = Image.new("RGBA", (tile, tile), (0, 0, 0, 0))
    d = ImageDraw.Draw(lib)
    f = ImageFont.truetype(FONT, FS)
    d.text((2 + 2, 2), TXT[0], "white", f,
           stroke_width=stroke, stroke_fill=stroke_color + (255,))
    # 只用一个字做统计, 避免排版差异
    out = lib
    off = 2
    W = FS * len(TXT) + 8
    canvas = Image.new("RGBA", (W, tile), (0, 0, 0, 0))
    x = 0
    for ch in TXT:
        tmp = Image.new("RGBA", (tile, tile), (0, 0, 0, 0))
        dd = ImageDraw.Draw(tmp)
        dd.text((4, 2), ch, "white", f, stroke_width=stroke, stroke_fill=stroke_color + (255,))
        canvas.alpha_composite(tmp, (x, 0))
        x += FS
    if blur > 0:
        canvas = canvas.filter(ImageFilter.GaussianBlur(blur))
    bg = Image.new("RGBA", canvas.size, (40, 90, 130, 255))
    bg.alpha_composite(canvas)
    return bg.convert("RGB")


print("目标: 白 %.0f | 描边 %.0f | 比例 %.2f\n" % (TARGET_WHITE, TARGET_RING, TARGET_RATIO))
rows = []
for stroke, blur in itertools.product((1, 2), (0.0, 0.3, 0.5, 0.7, 0.9)):
    im = render(stroke, blur)
    s = stats(im)
    if not s:
        continue
    err = (abs(s["white"] - TARGET_WHITE) / TARGET_WHITE
           + abs(s["ring"] - TARGET_RING) / TARGET_RING
           + abs(s["ratio"] - TARGET_RATIO) / TARGET_RATIO)
    rows.append((err, stroke, blur, s))
    print("  描边%d 模糊%.1f -> 白 %.0f 描边 %.0f 比例 %.2f   误差 %.3f"
          % (stroke, blur, s["white"], s["ring"], s["ratio"], err))

rows.sort()
print("\n最接近的组合:")
for err, stroke, blur, s in rows[:3]:
    print("  描边 %d + 模糊 %.1f  (误差 %.3f)" % (stroke, blur, err))
