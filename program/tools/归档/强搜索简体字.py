# -*- coding: utf-8 -*-
"""在字模图里做「带抖动」的强搜索, 确认简体字到底在不在

之前的比对是固定尺寸对齐的, 位图字模和矢量渲染差半个像素就掉分。
这次对每个字: 5 种字体 x 4 种字号 x 9 个偏移, 取全图集最高分。
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
ATLAS = os.path.join(BASE, r"game_pak\fresh_font\戃塭80.tga")
CELL = 32
COLS = 100
CHARS = "吧这话你瞧"
FONTS = [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc",
         r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\msgothic.ttc",
         r"C:\Windows\Fonts\simsun.ttc"]

alpha = np.array(Image.open(ATLAS).convert("RGBA").split()[3])
rows = alpha.shape[0] // CELL
cells, ids = [], []
for k in range(rows * COLS):
    r, c = divmod(k, COLS)
    m = (alpha[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL] > 110)
    if m.sum() < 20:
        continue
    cells.append(m.astype(np.float32))
    ids.append(k)
mat = np.stack([c.ravel() for c in cells])
print("图集字形 %d 个" % len(ids))


def render(ch, fp, size, dx, dy):
    im = Image.new("L", (CELL * 2, CELL * 2), 0)
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(fp, size)
    d.text((CELL // 2 + dx, CELL // 2 + dy), ch, font=f, fill=255)
    a = np.array(im) > 110
    ys, xs = np.where(a)
    if len(ys) == 0:
        return None
    cy, cx = (ys.min() + ys.max()) // 2, (xs.min() + xs.max()) // 2
    y0, x0 = cy - CELL // 2, cx - CELL // 2
    if y0 < 0 or x0 < 0 or y0 + CELL > im.height or x0 + CELL > im.width:
        return None
    return a[y0:y0 + CELL, x0:x0 + CELL].astype(np.float32).ravel()


for ch in CHARS:
    best = (0.0, -1, None)
    for fp in FONTS:
        for size in (26, 28, 30, 32):
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    v = render(ch, fp, size, dx, dy)
                    if v is None or v.sum() < 20:
                        continue
                    inter = (mat * v).sum(1)
                    union = mat.sum(1) + v.sum() - inter
                    iou = inter / np.maximum(union, 1)
                    j = int(iou.argmax())
                    if iou[j] > best[0]:
                        best = (float(iou[j]), int(ids[j]), os.path.basename(fp))
    print("  「%s」 最高 IoU %.3f  格子 %s  (%s)" % (ch, best[0], best[1], best[2]))
