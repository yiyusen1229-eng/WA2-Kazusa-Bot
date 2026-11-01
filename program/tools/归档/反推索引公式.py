# -*- coding: utf-8 -*-
"""定位若干个字在 80px 图集里的实际格子号, 反推 字符码→格子 的公式"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

DIR = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\game_pak\fresh_font"
CELL = 32
COLS = 100

PROBE = "あいうえおかきくけこアイウエオ亜唖娃阿哀愛挨A B C 1 2 3 あ"
PROBE = "あかさたな亜唖娃阿哀愛挨一丁三上下不"
FONTS = [r"C:\Windows\Fonts\msgothic.ttc", r"C:\Windows\Fonts\msmincho.ttc",
         r"C:\Windows\Fonts\msyhbd.ttc"]


def norm(m):
    ys, xs = np.where(m > 0)
    if len(ys) == 0:
        return None
    c = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = c.shape
    s = (CELL - 5) / max(w, h)
    im = Image.fromarray((c * 255).astype(np.uint8)).resize(
        (max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)
    out = np.zeros((CELL, CELL), np.float32)
    oy, ox = (CELL - im.height) // 2, (CELL - im.width) // 2
    out[oy:oy + im.height, ox:ox + im.width] = np.array(im) / 255.0
    return (out > 0.43).astype(np.float32).ravel()


alpha = np.array(Image.open(os.path.join(DIR, "戃塭80.tga")).convert("RGBA").split()[3])
rows = alpha.shape[0] // CELL
cells = []
for k in range(rows * COLS):
    r, c = divmod(k, COLS)
    m = (alpha[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL] > 110).astype(np.float32)
    if m.sum() < 15:
        cells.append(None)
        continue
    cells.append(norm(m))
valid = [(k, v) for k, v in enumerate(cells) if v is not None]
ids = np.array([k for k, _ in valid])
mat = np.stack([v for _, v in valid])
print("图集有效格 %d / %d" % (len(valid), len(cells)))

for ch in PROBE:
    best = (0, -1)
    for fp in FONTS:
        for size in (28, 30, 32):
            f = ImageFont.truetype(fp, size)
            im = Image.new("L", (CELL, CELL), 0)
            d = ImageDraw.Draw(im)
            d.text((0, 0), ch, font=f, fill=255)
            v = norm((np.array(im) > 110).astype(np.float32))
            if v is None:
                continue
            inter = (mat * v).sum(1)
            union = mat.sum(1) + v.sum() - inter
            iou = inter / np.maximum(union, 1)
            j = int(iou.argmax())
            if iou[j] > best[0]:
                best = (float(iou[j]), int(ids[j]))
    # 反推: 若图集按 SJIS 码序, 该字应在哪
    try:
        sj = ch.encode("shift_jis")
        if len(sj) == 1:
            pred = sj[0] - 0x20
        else:
            pred = 95 + (sj[0] - 0x81) * 188 + (sj[1] - 0x40)
    except Exception:
        pred = -1
    print("  %s  ->  格子 %4d (IoU %.2f)   SJIS预测 %4d" % (ch, best[1], best[0], pred))
