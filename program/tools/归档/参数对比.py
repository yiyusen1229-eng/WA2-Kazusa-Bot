# -*- coding: utf-8 -*-
"""1:1 对比: 游戏原字 vs 我们不同参数的渲染"""
import io
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
GAME = r"C:\Users\asus\.dsh\attachments\v1\objects\a5\a5db8fdca460689fc0a7bfea2f5860e369eb8ab77025b2b3ece6cfd0084cfbec"
TEXT = "求求你，撤回前言吧"

sys.path.insert(0, os.path.join(BASE, "app"))

img = Image.open(GAME).convert("RGB")
a = np.array(img).astype(np.int16)
mx = a.max(axis=2)
mn = a.min(axis=2)
white = (mx > 195) & ((mx - mn) < 50)
rowsum = white.sum(axis=1)
rows = [y for y in range(img.height) if rowsum[y] > 25]
groups, cur = [], [rows[0]]
for y in rows[1:]:
    if y - cur[-1] <= 4:
        cur.append(y)
    else:
        groups.append(cur)
        cur = [y]
groups.append(cur)
groups = [g for g in groups if len(g) > 10]
g = groups[1] if len(groups) > 1 else groups[0]
y0, y1 = g[0], g[-1] + 1
cols = np.where(white[y0:y1].sum(axis=0) > 1)[0]
x0, x1 = cols.min(), cols.max() + 1
gcrop = img.crop((max(0, x0 - 6), max(0, y0 - 8), x1 + 6, y1 + 8))
print("游戏字行: %dx%d" % gcrop.size)

# 我们的渲染: 用 gdi_text, 调不同参数
import gdi_text

VARIANTS = [
    ("雅黑粗 描边2", "msyhbd.ttc", 2, 1.0, 0.30, 1.0),
    ("雅黑粗 描边1", "msyhbd.ttc", 1, 0.6, 0.25, 1.0),
    ("雅黑常规 描边1", "msyh.ttc", 1, 0.6, 0.25, 1.0),
    ("雅黑常规 描边2", "msyh.ttc", 2, 1.0, 0.30, 1.0),
]

rows_out = [("游戏原图", gcrop)]

for label, fontfile, ow, bodyblur, boost, edge in VARIANTS:
    gdi_text._FONT_FILE = "C:/Windows/Fonts/" + fontfile
    gdi_text._PIL_FONT_CACHE.clear()
    gdi_text.OUTLINE_W = ow
    gdi_text.BODY_BLUR = bodyblur
    gdi_text.EDGE_BLUR = edge
    gdi_text.WHITE_BOOST = boost
    png, w, h = gdi_text.render_block(TEXT, maxw=1200, size=30)
    im = Image.open(io.BytesIO(png)).convert("RGBA")
    bg = Image.new("RGBA", im.size, (20, 60, 100, 255))
    bg.alpha_composite(im)
    rows_out.append((label, bg.convert("RGB")))

W = max(r[1].width for r in rows_out) + 20
H = sum(r[1].height + 34 for r in rows_out) + 10
sheet = Image.new("RGB", (W, H), (12, 18, 26))
d = ImageDraw.Draw(sheet)
f = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)
y = 5
for label, im in rows_out:
    d.text((8, y), label, fill=(150, 230, 255), font=f)
    y += 24
    sheet.paste(im, (8, y))
    y += im.height + 10
sheet.save(os.path.join(BASE, r"work\参数对比.png"))
print("已生成 参数对比.png", sheet.size)
