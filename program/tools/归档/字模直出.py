# -*- coding: utf-8 -*-
"""直接用游戏字模图渲染一句话, 看能不能复刻游戏里的字形

思路: 对每个字, 在图集里找最像的格子, 直接贴那块位图。
     这就是游戏本身的画法(贴 32x32 位图), 不涉及任何系统字体。
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

DIR = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\game_pak\fresh_font"
OUT = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\work\字模直出.png"
CELL = 32
COLS = 100
TEXT = "「求求你，撤回前言吧…」"
FONTS = [r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc",
         r"C:\Windows\Fonts\msgothic.ttc"]


def norm_mask(m):
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


def load_atlas(name):
    alpha = np.array(Image.open(os.path.join(DIR, name)).convert("RGBA").split()[3])
    rows = alpha.shape[0] // CELL
    vecs, ids, imgs = [], [], []
    for k in range(rows * COLS):
        r, c = divmod(k, COLS)
        raw = (alpha[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL] > 110).astype(np.float32)
        if raw.sum() < 15:
            continue
        v = norm_mask(raw)
        if v is None:
            continue
        vecs.append(v)
        ids.append(k)
        imgs.append(raw)
    return np.stack(vecs), np.array(ids), imgs


mat, ids, imgs = load_atlas("戃塭80.tga")
print("图集字形:", len(ids))

# 每个字找最佳格子
picks = []
for ch in TEXT:
    best = (0.0, -1)
    for fp in FONTS:
        for size in (28, 30, 32):
            f = ImageFont.truetype(fp, size)
            im = Image.new("L", (CELL, CELL), 0)
            d = ImageDraw.Draw(im)
            d.text((0, 0), ch, font=f, fill=255)
            v = norm_mask((np.array(im) > 110).astype(np.float32))
            if v is None:
                continue
            inter = (mat * v).sum(1)
            union = mat.sum(1) + v.sum() - inter
            iou = inter / np.maximum(union, 1)
            j = int(iou.argmax())
            if iou[j] > best[0]:
                best = (float(iou[j]), j)
    picks.append((ch, best[1], best[0]))
    print("  %s -> 格 %s (IoU %.2f)" % (ch, ids[best[1]] if best[1] >= 0 else "无", best[0]))

# 拼图
W = CELL * len(TEXT)
canvas = Image.new("RGBA", (W, CELL), (0, 0, 0, 0))
for i, (ch, j, s) in enumerate(picks):
    if j < 0:
        continue
    raw = imgs[j]
    mask = Image.fromarray((raw * 255).astype(np.uint8)).convert("L")
    layer = Image.new("RGBA", (CELL, CELL), (255, 255, 255, 0))
    layer.putalpha(mask)
    canvas.alpha_composite(layer, (i * CELL, 0))
bg = Image.new("RGBA", canvas.size, (20, 60, 100, 255))
bg.alpha_composite(canvas)
bg.convert("RGB").resize((W * 2, CELL * 2), Image.LANCZOS).save(OUT)
print("已存:", OUT)
