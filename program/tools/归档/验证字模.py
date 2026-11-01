# -*- coding: utf-8 -*-
"""验证 subfont.tga 是否是「微软雅黑 Bold 生成的位图字模」

做法:
  拿游戏截图里的字(求求你撤回前言吧), 用 微软雅黑 Bold 在 32px 渲染,
  逐个和 atlas 的 890 个格子比 IoU, 看能否找到高相似度格子。
  若相似度高 -> 图集就是这套字体, 可以用它直接拼字, 像素级还原。
"""
import os

from PIL import Image, ImageDraw, ImageFont

ATLAS = r"E:\Games\GALGAMES\WHITE ALBUM2\subfont.tga"
BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
FONT = r"C:\Windows\Fonts\msyhbd.ttc"
CELL = 32
TESTS = "求你撤回前言吧"

im = Image.open(ATLAS).convert("RGBA")
alpha = im.split()[3]

cells = []
for r in range(alpha.height // CELL):
    for c in range(alpha.width // CELL):
        cell = alpha.crop((c * CELL, r * CELL, (c + 1) * CELL, (r + 1) * CELL))
        if cell.getbbox():
            cells.append((r * (alpha.width // CELL) + c, cell))
print("有效字形:", len(cells))


def bits(img):
    p = img.load()
    w, h = img.size
    s = set()
    for y in range(h):
        for x in range(w):
            if p[x, y] > 110:
                s.add((x, y))
    return s


cell_bits = [(i, bits(c)) for i, c in cells]

for ch in TESTS:
    best = (0.0, -1)
    for size in (28, 29, 30, 31, 32):
        img = Image.new("L", (CELL, CELL), 0)
        d = ImageDraw.Draw(img)
        f = ImageFont.truetype(FONT, size)
        # 垂直居中
        bb = f.getbbox(ch)
        y_off = (CELL - (bb[3] - bb[1])) // 2 - bb[1]
        d.text((0, y_off), ch, font=f, fill=255)
        tb = bits(img)
        if not tb:
            continue
        for idx, cb in cell_bits:
            inter = len(tb & cb)
            union = len(tb | cb)
            if union and inter / union > best[0]:
                best = (inter / union, idx, size)
    print("  %s -> 最佳 IoU %.3f (格子 %d, 字号 %s)" % (ch, best[0], best[1], best[2] if len(best) > 2 else "-"))
