# -*- coding: utf-8 -*-
"""在两张图集里找同一个字的格子, 并排对照

用「人」「白」「今」三个两种语言都用的字。
对每个字, 用多种字体/字号渲染模板, 在所有非空格子里取最相似的一个。
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
GAME = [
    (BASE + r"\game_pak\fresh_font\杮懱80.tga", "游戏·明朝"),
    (BASE + r"\game_pak\fresh_font\戃塭80.tga", "游戏·哥特"),
]
PATCH = (r"E:\Games\GALGAMES\WHITE ALBUM2\subfont.tga", "汉化补丁")
OUT = BASE + r"\work\字体对照_看图.png"

CELL = 32
CHARS = ["人", "白", "今"]
FONTS = [r"C:/Windows/Fonts/msgothic.ttc", r"C:/Windows/Fonts/msmincho.ttc",
         r"C:/Windows/Fonts/msyh.ttc", r"C:/Windows/Fonts/simhei.ttf"]


def tmpl(ch, fp, size, stroke=0, dx=2, dy=2):
    im = Image.new("L", (CELL, CELL), 0)
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(fp, size)
    kw = dict(stroke_width=stroke, stroke_fill=255) if stroke else {}
    d.text((dx, dy), ch, fill=255, font=f, **kw)
    return np.array(im, dtype=np.float32)


def scan(arr):
    """返回所有非空格的 (i, j, 数组)"""
    h, w = arr.shape
    out = []
    for j in range(h // CELL):
        for i in range(w // CELL):
            c = arr[j * CELL:(j + 1) * CELL, i * CELL:(i + 1) * CELL]
            if (c > 40).sum() < 40:
                continue
            out.append((i, j, c.astype(np.float32)))
    return out


def match(cells, ch):
    best = (-9, None, None)
    for fp in FONTS:
        for size in (26, 28, 30, 32):
            for stroke in (0, 2):
                if stroke and "msyh" not in fp:
                    continue
                t = tmpl(ch, fp, size, stroke)
                if (t > 40).sum() < 30:
                    continue
                tn = np.sqrt(((t - t.mean()) ** 2).sum()) + 1e-6
                for i, j, c in cells:
                    cc = c - c.mean()
                    s = float(((t - t.mean()) * cc).sum() / (tn * (np.sqrt((cc ** 2).sum()) + 1e-6)))
                    if s > best[0]:
                        best = (s, (i, j), c.copy())
    return best


def load(path):
    im = Image.open(path)
    a = np.array(im.split()[3] if im.mode == "RGBA" else im.convert("L"))
    return a


rows = []
game_cells = [(n, scan(load(p))) for p, n in GAME]
patch_cells = [("补丁", scan(load(PATCH[0])))]
for ch in CHARS:
    r = [ch]
    for name, cells in game_cells:
        s, ij, crop = match(cells, ch)
        r.append((name, s, crop))
    for name, cells in patch_cells:
        s, ij, crop = match(cells, ch)
        r.append((name, s, crop))
    rows.append(r)

S = 5
cols = len(rows[0]) - 1
W = 120 + cols * (CELL * S + 24)
H = 70 + len(rows) * (CELL * S + 60)
cv = Image.new("RGB", (W, H), (12, 18, 26))
d = ImageDraw.Draw(cv)
fl = ImageFont.truetype(r"C:/Windows/Fonts/msyh.ttc", 15)
for k in range(cols):
    d.text((120 + k * (CELL * S + 24), 20), rows[0][k + 1][0], fill=(170, 210, 240), font=fl)
for r, row in enumerate(rows):
    y = 70 + r * (CELL * S + 60)
    d.text((16, y + 60), row[0], fill=(255, 255, 255),
           font=ImageFont.truetype(r"C:/Windows/Fonts/msyh.ttc", 30))
    for k in range(1, len(row)):
        name, s, crop = row[k]
        im2 = Image.fromarray(crop.astype(np.uint8)).resize((CELL * S, CELL * S), Image.NEAREST).convert("RGB")
        cv.paste(im2, (120 + (k - 1) * (CELL * S + 24), y))
        d.text((120 + (k - 1) * (CELL * S + 24), y + CELL * S + 6),
               "%.2f" % s, fill=(140, 180, 210), font=fl)

cv.save(OUT)
print("已保存:", OUT)
for row in rows:
    print("  %s: %s" % (row[0], "  ".join("%s=%.2f" % (c[0], c[1]) for c in row[1:])))
