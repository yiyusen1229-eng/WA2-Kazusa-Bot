# -*- coding: utf-8 -*-
"""用游戏截图里抠出的真实字形, 去 14pt 字模图里找格子

这是最可靠的比对: 查询图来自游戏自己, 渲染方式一致。
"""
import os

import numpy as np
from PIL import Image
from scipy import ndimage

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
SHOT = os.path.join(BASE, r"work\普窗口.png")
ATLAS = os.path.join(BASE, r"work\fnt_only\14pt戃.tga")
CELL = 32

im = Image.open(SHOT).convert("RGB")
c = im.crop((680, 415, 850, 480))
a = np.array(c).astype(np.int16)
mx, mn = a.max(2), a.min(2)
m = (mx > 185) & ((mx - mn) < 70)

# 按列投影找出 4 个字的水平范围
colsum = m.sum(0)
runs = []
inrun = False
for x, v in enumerate(colsum):
    if v > 0 and not inrun:
        s = x
        inrun = True
    elif v == 0 and inrun:
        if x - s >= 14:
            runs.append((s, x))
        inrun = False
if inrun:
    runs.append((s, len(colsum)))
print("检测到字的列范围:", runs)

alpha = np.array(Image.open(ATLAS).convert("RGBA").split()[3])
rows, cols = alpha.shape[0] // CELL, alpha.shape[1] // CELL
cells, ids = [], []
for k in range(rows * cols):
    r, cc = divmod(k, cols)
    mm = (alpha[r*CELL:(r+1)*CELL, cc*CELL:(cc+1)*CELL] > 110).astype(np.float32)
    if mm.sum() < 20:
        continue
    cells.append(mm)
    ids.append(k)
mat = np.stack([x.ravel() for x in cells])
print("字模 %d 格" % len(ids))


def norm(mask):
    ys, xs = np.where(mask)
    if len(ys) == 0:
        return None
    crop = mask[ys.min():ys.max()+1, xs.min():xs.max()+1].astype(np.float32)
    h, w = crop.shape
    s = (CELL - 4) / max(w, h)
    img = Image.fromarray((crop*255).astype(np.uint8)).resize(
        (max(1, int(w*s)), max(1, int(h*s))), Image.LANCZOS)
    out = np.zeros((CELL, CELL), np.float32)
    oy, ox = (CELL-img.height)//2, (CELL-img.width)//2
    out[oy:oy+img.height, ox:ox+img.width] = np.array(img)/255.0
    return (out > 0.43).astype(np.float32).ravel()


CHARS = "开始游戏"
for i, (x0, x1) in enumerate(runs[:4]):
    sub = m[:, x0:x1]
    ys = np.where(sub.sum(1) > 0)[0]
    if len(ys) == 0:
        continue
    sub = sub[ys.min():ys.max()+1]
    v = norm(sub)
    if v is None:
        continue
    inter = (mat * v).sum(1)
    union = mat.sum(1) + v.sum() - inter
    iou = inter / np.maximum(union, 1)
    order = np.argsort(-iou)[:3]
    ch = CHARS[i] if i < len(CHARS) else "?"
    print("  「%s」 %dx%d  最佳: %s" % (
        ch, sub.shape[1], sub.shape[0],
        "  ".join("格%d IoU%.3f" % (ids[j], iou[j]) for j in order)))
