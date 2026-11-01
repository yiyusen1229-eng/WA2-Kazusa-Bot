# -*- coding: utf-8 -*-
"""用 sys_00110 做输入框: 切成 左/中/右, 中段平铺拉长到原输入框长宽比
原输入框: 46% 宽 (368 舞台px) x 17.1 舞台px  -> 长宽比约 21.5
"""
import os

from PIL import Image

SRC = r"E:\IDM下载目录\解包\cg\cg\sys_00110.tga"
BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
OUT = os.path.join(BASE, r"ui2\assets\input_frame.png")

TARGET_RATIO = 252.0 / 22.0   # 252x22 舞台px -> 11.45
H = 88                            # 输出高度

im = Image.open(SRC).convert("RGBA")
W, A_H = im.size
print("素材:", W, A_H)

# 逐列算灰度标准差, 找雪花最少的区间(在右侧 45%~90%)
g = im.convert("L")
cols = []
for x in range(W):
    px = [g.getpixel((x, y)) for y in range(0, A_H, 4)]
    m = sum(px) / len(px)
    var = sum((v - m) ** 2 for v in px) / len(px)
    cols.append(var)

lo, hi = int(W * 0.45), int(W * 0.92)
best = None
span = 70
for x in range(lo, hi - span):
    s = sum(cols[x:x + span])
    if best is None or s < best[1]:
        best = (x, s)
mid_a = best[0]
mid_b = mid_a + span
print("中段选取 x %d..%d (雪花干扰最低)" % (mid_a, mid_b))

left = im.crop((0, 0, mid_a, A_H))
mid = im.crop((mid_a, 0, mid_b, A_H))
right = im.crop((mid_b, 0, W, A_H))

scale = H / A_H
left = left.resize((max(1, round(left.width * scale)), H), Image.LANCZOS)
mid = mid.resize((max(1, round(mid.width * scale)), H), Image.LANCZOS)
right = right.resize((max(1, round(right.width * scale)), H), Image.LANCZOS)

target_w = round(H * TARGET_RATIO)
rest = target_w - left.width - right.width
strip = Image.new("RGBA", (rest, H), (0, 0, 0, 0))
x = 0
while x < rest:
    strip.alpha_composite(mid, (x, 0))
    x += mid.width

canvas = Image.new("RGBA", (target_w, H), (0, 0, 0, 0))
canvas.alpha_composite(left, (0, 0))
canvas.alpha_composite(strip, (left.width, 0))
canvas.alpha_composite(right, (target_w - right.width, 0))
canvas.save(OUT)
print("已生成 %s  %dx%d  比例 %.2f (目标 %.2f)"
      % (OUT, canvas.width, canvas.height, canvas.width / canvas.height, TARGET_RATIO))