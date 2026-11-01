# -*- coding: utf-8 -*-
"""三态按钮去字(第四版): 用左侧一条干净竖条横向拉伸覆盖文字区, 边缘羽化

比均色自然: 竖条本身带雪花纹理和纵向渐变, 拉伸后仍是渐变色带而不是平块。
"""
import os

from PIL import Image

SRC = r"E:\IDM下载目录\解包\cg\cg\sys_07020.tga"
BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
OUT = os.path.join(BASE, r"ui2\assets\ui\btn_3state.png")

im = Image.open(SRC).convert("RGBA")
W, H = im.size
FH = H // 3
canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

X0, X1 = 46, 114          # 文字区
S0, S1 = 20, 42           # 干净取样竖条
FEATHER = 9

for i in range(3):
    fr = im.crop((0, i * FH, W, (i + 1) * FH)).copy()
    px = fr.load()
    strip_w = S1 - S0
    mid_w = X1 - X0 + 1
    for k in range(mid_w):
        x = X0 + k
        sx = S0 + int(round(k / float(mid_w - 1) * (strip_w - 1)))
        edge = min(k + 1, mid_w - k)
        t = min(1.0, edge / float(FEATHER))
        for y in range(FH):
            r1, g1, b1, a1 = px[sx, y]
            r0, g0, b0, a0 = px[x, y]
            px[x, y] = (int(r0 + (r1 - r0) * t), int(g0 + (g1 - g0) * t),
                        int(b0 + (b1 - b0) * t), int(a0 + (a1 - a0) * t))
    canvas.alpha_composite(fr, (0, i * FH))

canvas.save(OUT)
print("已生成:", OUT)
