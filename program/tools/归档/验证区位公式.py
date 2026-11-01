# -*- coding: utf-8 -*-
"""验证 GB2312 区位公式: 格子号 = (区-1)*94 + (位-1)

把算出来的格子抠出来, 和该字的正常字形并排, 一眼就能看出对不对。
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
ATLAS = os.path.join(BASE, r"work\fnt_only\戃塭80.tga")
CELL = 32
COLS = 100
TESTS = "吧这开始游戏你"


def gb2312_index(ch):
    b = ch.encode("gbk")
    qu, wei = b[0] - 0xA0, b[1] - 0xA0
    return (qu - 1) * 94 + (wei - 1), qu, wei


alpha = np.array(Image.open(ATLAS).convert("RGBA").split()[3])
rows = alpha.shape[0] // CELL


def cell_img(k):
    if k < 0 or k >= rows * COLS:
        return None
    r, c = divmod(k, COLS)
    return alpha[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL]


f = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 30)
tiles = []
for ch in TESTS:
    idx, qu, wei = gb2312_index(ch)
    got = cell_img(idx)
    # 该字的正常渲染
    ref = Image.new("L", (CELL, CELL), 0)
    d = ImageDraw.Draw(ref)
    d.text((0, 0), ch, font=f, fill=255)
    row = Image.new("L", (CELL * 3, CELL), 0)
    row.paste(Image.fromarray((got * 255).astype(np.uint8)) if got is not None else Image.new("L", (CELL, CELL), 0), (0, 0))
    row.paste(ref, (CELL, 0))
    # 邻近几个格子做参考
    for i, off in enumerate((1, 2)):
        g2 = cell_img(idx + off)
        if g2 is not None:
            row.paste(Image.fromarray((g2 * 255).astype(np.uint8)), (CELL * (2 + i), 0))
    tiles.append((ch, idx, qu, wei, row))
    print("  %s  GBK %s  区%2d 位%2d  格子 %5d" % (ch, ch.encode('gbk').hex(), qu, wei, idx))

W = CELL * 3
H = CELL * len(tiles) * 2 + 10
sheet = Image.new("L", (W * 3, CELL * len(tiles) * 2), 0)
for i, (ch, idx, qu, wei, row) in enumerate(tiles):
    sheet.paste(row.resize((W * 2, CELL * 2), Image.NEAREST), (0, i * CELL * 2))
sheet.save(os.path.join(BASE, "work", "区位验证.png"))
print("已存 区位验证.png  (每行: 算出的格子 | 该字正常字形 | 相邻格子+1 | 相邻格子+2)")
