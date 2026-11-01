# -*- coding: utf-8 -*-
"""对比游戏自带字模 与 汉化补丁字模 的同一字，看是不是一套字体

做法: 拿「白」「雪」「私」三个日中通用字,
      在两张图集里各自用模板匹配找到对应格子, 并排存图。
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

GAME_ATLAS = [
    (r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\game_pak\fresh_font\杮懱80.tga", "游戏·明朝32px"),
    (r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\game_pak\fresh_font\戃塭80.tga", "游戏·哥特32px"),
]
PATCH_ATLAS = (r"E:\Games\GALGAMES\WHITE ALBUM2\subfont.tga", "汉化补丁")
OUT = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\work\字体对照.png"

CHARS = ["白", "雪", "私"]
CELL = 32


def render_template(ch, font_path, size, stroke=0):
    im = Image.new("L", (CELL, CELL), 0)
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(font_path, size)
    d.text((2, 0), ch, fill=255, font=f,
           stroke_width=stroke, stroke_fill=255 if stroke else None)
    return np.array(im, dtype=np.float32)


def best_cell(atlas_arr, tmpl, cells_x, cells_y):
    best = (-1, 0, 0)
    t = tmpl - tmpl.mean()
    tn = np.sqrt((t ** 2).sum()) + 1e-6
    for j in range(cells_y):
        for i in range(cells_x):
            c = atlas_arr[j * CELL:(j + 1) * CELL, i * CELL:(i + 1) * CELL].astype(np.float32)
            if c.max() < 20:
                continue
            cc = c - c.mean()
            den = np.sqrt((cc ** 2).sum()) + 1e-6
            score = float((t * cc).sum() / (tn * den))
            if score > best[0]:
                best = (score, i, j)
    return best


def load_atlas(path):
    im = Image.open(path).convert("L")
    return np.array(im)


rows = []
for ch in CHARS:
    row = [("字符", None)]
    # 游戏图集
    for path, name in GAME_ATLAS:
        arr = load_atlas(path)
        cy, cx = arr.shape[0] // CELL, arr.shape[1] // CELL
        best = (-1, 0, 0)
        for fp, sz in ((r"C:/Windows/Fonts/msgothic.ttc", 30),
                       (r"C:/Windows/Fonts/msmincho.ttc", 30),
                       (r"C:/Windows/Fonts/msyh.ttc", 30)):
            try:
                tm = render_template(ch, fp, sz)
            except Exception:
                continue
            b = best_cell(arr, tm, cx, cy)
            if b[0] > best[0]:
                best = b
        score, i, j = best
        crop = Image.fromarray(arr[j * CELL:(j + 1) * CELL, i * CELL:(i + 1) * CELL])
        row.append((name, crop, score))
    # 补丁图集
    path, name = PATCH_ATLAS
    im = Image.open(path).convert("RGBA")
    a = np.array(im.split()[3])
    cy, cx = a.shape[0] // CELL, a.shape[1] // CELL
    tm = render_template(ch, r"C:/Windows/Fonts/msyh.ttc", 28, stroke=2)
    score, i, j = best_cell(a, tm, cx, cy)
    crop = Image.fromarray(a[j * CELL:(j + 1) * CELL, i * CELL:(i + 1) * CELL])
    row.append((name, crop, score))
    rows.append(row)

# 排版
S = 4
W = 200 + 3 * (CELL * S + 30)
H = 60 + len(rows) * (CELL * S + 40)
canvas = Image.new("RGB", (W, H), (16, 24, 32))
d = ImageDraw.Draw(canvas)
font_lbl = ImageFont.truetype(r"C:/Windows/Fonts/msyh.ttc", 16)
d.text((10, 14), "字符", fill=(200, 220, 240), font=font_lbl)
for k in range(3):
    lbl = rows[0][k + 1][0]
    d.text((200 + k * (CELL * S + 30), 14), lbl, fill=(200, 220, 240), font=font_lbl)

for r, row in enumerate(rows):
    y = 60 + r * (CELL * S + 40)
    d.text((10, y + 40), row[0][0], fill=(255, 255, 255),
           font=ImageFont.truetype(r"C:/Windows/Fonts/msyh.ttc", 22))
    for k in range(1, 4):
        name, crop, score = row[k]
        im2 = crop.resize((CELL * S, CELL * S), Image.NEAREST).convert("RGB")
        canvas.paste(im2, (200 + (k - 1) * (CELL * S + 30), y))
        d.text((200 + (k - 1) * (CELL * S + 30), y + CELL * S + 4),
               "相似度 %.2f" % score, fill=(150, 190, 220), font=font_lbl)

canvas.save(OUT)
print("已保存:", OUT)
for row in rows:
    print("  %s: %s" % (row[0][0], "  ".join("%s=%.2f" % (c[0], c[2]) for c in row[1:])))
