# -*- coding: utf-8 -*-
"""验证 80px 字模图的顺序与字体

假设: 3000 格 = JIS X 0208 一级汉字集合, 按 Shift-JIS 码位升序排列。
检验: 按 SJIS 顺序解码字符, 用日文字体渲染, 与图集格子逐个比 IoU。
   - 如果平均 IoU 很高 -> 顺序假设成立, 而且能确定是哪款日文字体
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
DIR = os.path.join(BASE, r"game_pak\font_pak")
CELL = 64

FONTS = {
    "MS Gothic": r"C:\Windows\Fonts\msgothic.ttc",
    "MS Mincho": r"C:\Windows\Fonts\msmincho.ttc",
    "Yu Gothic": r"C:\Windows\Fonts\YuGothR.ttc",
    "Meiryo": r"C:\Windows\Fonts\meiryo.ttc",
}


def sjis_chars():
    """按 Shift-JIS 码位升序取 JIS 一级汉字区(0x889F-0x9872)及假名符号"""
    out = []
    for hi in range(0x81, 0xA0):
        for lo in range(0x40, 0xFD):
            if lo == 0x7F:
                continue
            try:
                ch = bytes([hi, lo]).decode("shift_jis")
            except Exception:
                continue
            out.append(ch)
    return out


chars = sjis_chars()
print("SJIS 可用字符数:", len(chars))


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
    for k in range(rows * cols):
        r, c = divmod(k, cols)
        v = norm((alpha[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL] > 110).astype(np.float32))
        cells.append(v)
    cell_mat = np.stack([c for c in cells if c is not None])
    print("\n=== %s: %d 格 ===" % (atlas_name, len(cell_mat)))

    # 只取前 300 个格子做验证(快)
    N = min(300, len(cell_mat), len(chars))
    for fname, fpath in FONTS.items():
        if not os.path.exists(fpath):
            continue
        f = ImageFont.truetype(fpath, 56)
        vecs = []
        for ch in chars[:N]:
            im = Image.new("L", (CELL, CELL), 0)
            d = ImageDraw.Draw(im)
            d.text((2, 2), ch, font=f, fill=255)
            v = norm((np.array(im) > 110).astype(np.float32))
            if v is not None:
                vecs.append(v)
        vecs = [v for v in vecs if v is not None]
        if len(vecs) < N: N2 = len(vecs)
        else: N2 = N
        cm = np.stack(vecs[:N2])
        inter = (cell_mat[:N2] * cm).sum(1)
        union = cell_mat[:N2].sum(1) + cm.sum(1) - inter
        iou = inter / np.maximum(union, 1)
        print("  %-10s 前 %d 格平均 IoU %.3f   >0.8 占比 %.0f%%"
              % (fname, N2, iou.mean(), 100 * (iou > 0.8).mean()))
