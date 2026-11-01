# -*- coding: utf-8 -*-
"""验证: 字模图按「字符编码升序」排列, 从 0x20 开始

从预览看: 第 0 格是空格, 接着 ! " # $ % & ' ( ) * + , - . / 0-9 : ; < = > ? @ A-Z ...
所以 index = 字符在「所有可编码字符按码位升序」里的位次。

验证: 取若干 index 已知的字符, 用日文字体渲染后与对应格子比 IoU。
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
DIR = os.path.join(BASE, r"game_pak\font_pak")
CELL = 32
COLS = 100

FONTS = {
    "MS Gothic": r"C:\Windows\Fonts\msgothic.ttc",
    "MS Mincho": r"C:\Windows\Fonts\msmincho.ttc",
    "Meiryo": r"C:\Windows\Fonts\meiryo.ttc",
}


def code_order_chars():
    """0x20 起, 单字节 ASCII -> 双字节 SJIS 全表, 按码位升序"""
    out = []
    for b in range(0x20, 0x7F):
        out.append(chr(b))
    for hi in range(0x81, 0xFD):
        for lo in range(0x40, 0xFD):
            if lo == 0x7F:
                continue
            try:
                out.append(bytes([hi, lo]).decode("shift_jis"))
            except Exception:
                pass
    return out


chars = code_order_chars()
print("编码序字符数:", len(chars))
print("前 20:", "".join(c if c.isprintable() else "_" for c in chars[:20]))

# 检查几个已知位次
probe = {}
for i, ch in enumerate(chars[:4000]):
    if ch in "Aあ亜" and ch not in probe:
        probe[ch] = i
print("位次:", probe)


def norm(m, cell=CELL):
    ys, xs = np.where(m > 0)
    if len(ys) == 0:
        return None
    crop = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = crop.shape
    s = (cell - 6) / max(w, h)
    im = Image.fromarray((crop * 255).astype(np.uint8)).resize(
        (max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)
    out = np.zeros((cell, cell), np.float32)
    oy, ox = (cell - im.height) // 2, (cell - im.width) // 2
    out[oy:oy + im.height, ox:ox + im.width] = np.array(im) / 255.0
    return (out > 0.43).astype(np.float32).ravel()


for atlas_name in ("戃塭80.tga", "杮懱80.tga"):
    p = os.path.join(DIR, atlas_name)
    alpha = np.array(Image.open(p).convert("RGBA").split()[3])
    print("\n=== %s %dx%d ===" % (atlas_name, alpha.shape[1], alpha.shape[0]))
    for fname, fpath in FONTS.items():
        if not os.path.exists(fpath):
            continue
        f = ImageFont.truetype(fpath, 30)
        ious = []
        for idx in (33, 34, 66, 97, 150, 200, 260, 300, 350, 400):
            if idx >= len(chars):
                continue
            r, c = divmod(idx, COLS)
            if (r + 1) * CELL > alpha.shape[0]:
                break
            cell = norm((alpha[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL] > 110).astype(np.float32))
            if cell is None:
                continue
            im = Image.new("L", (CELL, CELL), 0)
            d = ImageDraw.Draw(im)
            d.text((1, 0), chars[idx], font=f, fill=255)
            v = norm((np.array(im) > 110).astype(np.float32))
            if v is None:
                continue
            inter = (cell * v).sum()
            union = cell.sum() + v.sum() - inter
            ious.append((chars[idx], round(float(inter / max(union, 1)), 3)))
        print("  %-10s %s" % (fname, ious))
