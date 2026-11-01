# -*- coding: utf-8 -*-
"""sys_07020 三态按钮: 用「黄色文字」定位并抹除, 再切成三态"""
import os

from PIL import Image

SRC = r"E:\IDM下载目录\解包\cg\cg\sys_07020.tga"
BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
OUT = os.path.join(BASE, r"ui2\assets\ui\btn_3state.png")

im = Image.open(SRC).convert("RGBA")
W, H = im.size
FH = H // 3
print("素材 %dx%d, 每帧高 %d" % (W, H, FH))

canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

for i in range(3):
    fr = im.crop((0, i * FH, W, (i + 1) * FH)).copy()
    px = fr.load()
    # 找黄色文字像素 (原按钮的字是黄色)
    ys, xs = [], []
    for y in range(8, FH - 8):
        for x in range(28, W - 24):
            r, g, b, a = px[x, y]
            if a > 120 and r > 180 and g > 150 and b < 130 and (r - b) > 70:
                ys.append(y)
                xs.append(x)
    if not ys:
        # 兜底: 用较亮的白字
        for y in range(8, FH - 8):
            for x in range(28, W - 24):
                r, g, b, a = px[x, y]
                if a > 120 and r > 215 and g > 215 and b > 215:
                    ys.append(y)
                    xs.append(x)
    if not ys:
        print("第 %d 帧: 没找到文字" % (i + 1))
        canvas.alpha_composite(fr, (0, i * FH))
        continue

    y0, y1 = min(ys), max(ys)
    x0, x1 = min(xs), max(xs)
    print("第 %d 帧: 文字 x %d..%d  y %d..%d" % (i + 1, x0, x1, y0, y1))

    # 固定文字框: 上下行线性插值填充, 三帧统一
    bx0, bx1 = 48, 112
    by0, by1 = 8, 32
    top_y, bot_y = by0 - 1, by1 + 1
    for y in range(by0, by1 + 1):
        t = (y - top_y) / float(bot_y - top_y)
        for x in range(bx0, bx1 + 1):
            r1, g1, b1, a1 = px[x, top_y]
            r2, g2, b2, a2 = px[x, bot_y]
            px[x, y] = (int(r1 + (r2 - r1) * t), int(g1 + (g2 - g1) * t),
                        int(b1 + (b2 - b1) * t), int(a1 + (a2 - a1) * t))
    print("  已按插值抹除文字")

    canvas.alpha_composite(fr, (0, i * FH))

canvas.save(OUT)
print("已生成:", OUT, canvas.size)
