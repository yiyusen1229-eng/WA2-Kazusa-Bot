# -*- coding: utf-8 -*-
"""验证 JIS 区点顺序: 第 k 格 = JIS 一级第 k 个字"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
DIR = os.path.join(BASE, r"game_pak\font_pak")
CELL = 64

FONTS = {
    "MS Gothic": r"C:\Windows\Fonts\msgothic.ttc",
    "MS Mincho": r"C:\Windows\Fonts\msmincho.ttc",
    "Meiryo": r"C:\Windows\Fonts\meiryo.ttc",
}


def jis_level1():
    """JIS X 0208 一级: 区 16-47, 每区 94 字, 起点 0x3021"""
    out = []
    for ku in range(16, 48):
        for ten in range(1, 95):
            b1 = ku + 0xA0
            b2 = ten + 0xA0
            try:
                ch = bytes([b1, b2]).decode("euc_jp")
            except Exception:
                continue
            out.append(ch)
    return out


chars = jis_level1()
print("JIS 一级字数:", len(chars), " 前 10:", "".join(chars[:10]))


def norm(m):
    ys, xs = np.where(m > 0)
    if len(ys) == 0:
        return None
    crop = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = crop.shape
    s = 56.0 / max(w, h)
    im = Image.fromarray((crop * 255).astype(np.uint8)).resize(
        (max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)
    out = np.zeros((CELL, CELL), np.float32)
    oy, ox = (CELL - im.height) // 2, (CELL - im.width) // 2
    out[oy:oy + im.height, ox:ox + im.width] = np.array(im) / 255.0
    return (out > 0.43).astype(np.float32).ravel()


for atlas_name in ("戃塭80.tga", "杮懱80.tga"):
    p = os.path.join(DIR, atlas_name)
    if not os.path.exists(p):
        continue
    alpha = np.array(Image.open(p).convert("RGBA").split()[3])
    rows, cols = alpha.shape[0] // CELL, alpha.shape[1] // CELL
    cells = []
    for k in range(min(60, rows * cols)):
        r, c = divmod(k, cols)
        v = norm((alpha[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL] > 110).astype(np.float32))
        cells.append(v)
    print("\n=== %s 前 %d 格 ===" % (atlas_name, len(cells)))
    for fname, fpath in FONTS.items():
        if not os.path.exists(fpath):
            continue
        f = ImageFont.truetype(fpath, 56)
        ious = []
        for k, cell in enumerate(cells):
            if cell is None or k >= len(chars):
                continue
            im = Image.new("L", (CELL, CELL), 0)
            d = ImageDraw.Draw(im)
            d.text((2, 2), chars[k], font=f, fill=255)
            v = norm((np.array(im) > 110).astype(np.float32))
            if v is None:
                continue
            inter = (cell * v).sum()
            union = cell.sum() + v.sum() - inter
            ious.append(inter / max(union, 1))
        if ious:
            print("  %-10s 平均 IoU %.3f  (前 5 格: %s)"
                  % (fname, float(np.mean(ious)), [round(x, 2) for x in ious[:5]]))
