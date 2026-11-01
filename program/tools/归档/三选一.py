# -*- coding: utf-8 -*-
"""把游戏原图和三个候选按「屏幕实际显示比例」并排, 让人一眼挑"""
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\app")
import gdi_text

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
GAME = r"C:\Users\asus\.dsh\attachments\v1\objects\32\32f773796aa3666f6aa89394f9dbb8d116c5550ddcaab66abe40bf04887bb8e2"

# 游戏截图统一到 1280 宽(和我们窗口一致), 裁出「求求你，撤回前言吧…」那一行
g = Image.open(GAME).convert("RGB")
g = g.resize((1280, int(g.height * 1280 / g.width)), Image.LANCZOS)
import numpy as np
a = np.array(g).astype(np.int16)
mx, mn = a.max(2), a.min(2)
m = (mx > 215) & ((mx - mn) < 45)
m[:int(g.height * 0.742)] = False
m[int(g.height * 0.792):] = False
m[:, :int(g.width * 0.12)] = False
m[:, int(g.width * 0.86):] = False
ys, xs = np.where(m)
gcrop = g.crop((max(0, xs.min() - 6), max(0, ys.min() - 8),
                min(g.width, xs.max() + 6), ys.max() + 10))
print("游戏行(1280宽下):", gcrop.size)
print("  字高约:", ys.max() - ys.min(), "px")

# 三个候选: 都按程序里的显示比例 0.5 缩放(0.3125 * 1.6)
CANDS = [
    ("A 雅黑常规 56", "C:/Windows/Fonts/msyh.ttc", 56),
    ("B 雅黑常规 64", "C:/Windows/Fonts/msyh.ttc", 64),
    ("C 雅黑Bold 56", "C:/Windows/Fonts/msyhbd.ttc", 56),
]
TEXT = "「求求你，撤回前言吧…"
tiles = [("游戏原图", gcrop, gcrop.height)]
for label, fp, size in CANDS:
    gdi_text._FONT_FILE = fp
    gdi_text._PIL_FONT_CACHE.clear()
    png, w, h = gdi_text.render_block(TEXT, maxw=1200, size=size)
    import io
    im = Image.open(io.BytesIO(png)).convert("RGBA")
    # 按程序实际显示比例缩放
    disp_w = int(im.width * 0.5)
    disp_h = int(im.height * 0.5)
    im2 = im.resize((disp_w, disp_h), Image.LANCZOS)
    bg = Image.new("RGBA", im2.size, (20, 60, 100, 255))
    bg.alpha_composite(im2)
    tiles.append((label, bg.convert("RGB"), disp_h))
    print("%s 显示尺寸 %dx%d" % (label, disp_w, disp_h))

W = max(t[1].width for t in tiles) + 16
H = sum(t[2] + 30 for t in tiles) + 12
sheet = Image.new("RGB", (W, H), (12, 18, 26))
d = ImageDraw.Draw(sheet)
f = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 20)
y = 6
for label, im, hh in tiles:
    d.text((8, y), label, fill=(150, 235, 255), font=f)
    y += 26
    sheet.paste(im, (8, y))
    y += hh + 6
sheet.save(BASE + r"\work\三选一.png")
print("已存 三选一.png", sheet.size)
