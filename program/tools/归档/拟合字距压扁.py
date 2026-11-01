# -*- coding: utf-8 -*-
"""二维拟合: 找到与游戏字幕最吻合的 横向(字距) 与 纵向(压扁) 比例

做法:
  1. 从游戏截图裁出「终于，还是下起来了。」这一行, 做二值化
  2. 用我们的渲染管线画同一句, 也二值化
  3. 把我们的图按 (sx, sy) 缩放后与游戏图比 IoU, 扫 sx/sy 找最优
  sx 反映字距(横向), sy 反映是否被压扁(纵向)
"""
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
SHOT = BASE + r"\work\剧情实测\02_第10句.png"
TXT = "终于，还是下起来了。"
FS, ST = 28, 2


def game_mask():
    im = Image.open(SHOT).convert("RGB")
    # 之前定位到的字幕行: x 330..712, y 660..704
    crop = im.crop((325, 655, 720, 710))
    a = np.array(crop).astype(np.int16)
    mx, mn = a.max(2), a.min(2)
    m = (mx > 200) & ((mx - mn) < 45)
    ys, xs = np.where(m)
    if len(ys) == 0:
        raise SystemExit("游戏字幕没找到")
    m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return m


def our_mask(text, advance=28, blur=0.7):
    n = len(text)
    w = advance * n + 40
    h = 80
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(r"C:/Windows/Fonts/msyh.ttc", FS)
    x = 20
    for ch in text:
        d.text((x, 12), ch, "white", f, stroke_width=ST, stroke_fill="black")
        x += advance
    if blur:
        img = img.filter(ImageFilter.GaussianBlur(blur))
    a = np.array(img.split()[3]) > 90
    ys, xs = np.where(a)
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def iou(m1, m2, sx, sy):
    h, w = m1.shape
    im = Image.fromarray((m2 * 255).astype(np.uint8))
    nw, nh = max(1, int(w * sx)), max(1, int(h * sy))
    im = im.resize((nw, nh), Image.LANCZOS)
    a2 = np.array(im) > 127
    H = max(h, nh)
    W = max(w, nw)
    A = np.zeros((H, W), bool)
    B = np.zeros((H, W), bool)
    A[:h, :w] = m1
    B[:nh, :nw] = a2
    inter = np.logical_and(A, B).sum()
    union = np.logical_or(A, B).sum()
    return inter / union if union else 0


gm = game_mask()
print("游戏字幕 mask:", gm.shape)
best = (0, 1, 1)
for advance in (26, 27, 28, 29, 30, 31):
    om = our_mask(TXT, advance=advance)
    for sy in (0.94, 0.96, 0.98, 1.0, 1.02):
        for sx in (0.94, 0.96, 0.98, 1.0, 1.02, 1.04):
            v = iou(gm, om, sx, sy)
            if v > best[0]:
                best = (v, advance, sy * sx)
        # 只打印每档 advance 的最优
    v2 = max(iou(gm, om, sx, sy) for sy in (0.94, 0.96, 0.98, 1.0, 1.02) for sx in (0.94, 0.96, 0.98, 1.0, 1.02, 1.04))
    print("  字距 %d -> 最优 IoU %.3f" % (advance, v2))

print("\n最优: IoU %.3f  字距=%d  (综合缩放 %.2f)" % best)
