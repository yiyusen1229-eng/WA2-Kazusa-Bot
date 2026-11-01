# -*- coding: utf-8 -*-
"""从游戏截图里抠出单字, 到 fon.pak 的字模图里找对应格子

如果能在图集里找到高匹配, 说明对话文字就是用这张图集画的,
那么直接贴图集就能做到像素级一致(不涉及任何系统字体)。
"""
import os

import numpy as np
from PIL import Image
from scipy import ndimage

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
GAME = r"C:\Users\asus\.dsh\attachments\v1\objects\32\32f773796aa3666f6aa89394f9dbb8d116c5550ddcaab66abe40bf04887bb8e2"
ATLAS = os.path.join(BASE, r"game_pak\fresh_font\戃塭80.tga")
CELL = 32

# 1) 抠游戏里的字
g = Image.open(GAME).convert("RGB")
a = np.array(g).astype(np.int16)
mx, mn = a.max(2), a.min(2)
white = (mx > 200) & ((mx - mn) < 50)
# 只保留第二行文字(求求你…)
band = white[1030:1090, 380:1450]
lab, n = ndimage.label(band)
boxes = []
for i in range(1, n + 1):
    ys, xs = np.where(lab == i)
    if len(ys) < 100:
        continue
    boxes.append((xs.min(), ys.min(), xs.max(), ys.max(), len(ys)))
boxes.sort(key=lambda b: b[0])
print("第二行连通块 %d 个:" % len(boxes))
for b in boxes[:14]:
    print("   x %4d..%4d  y %3d..%3d  h=%2d w=%2d 面积 %d"
          % (b[0], b[2], b[1], b[3], b[3] - b[1] + 1, b[2] - b[0] + 1, b[4]))


def norm(mask, cell=CELL, inner=None):
    ys, xs = np.where(mask)
    if len(ys) == 0:
        return None
    c = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = c.shape
    s = (cell - 4) / max(w, h)
    im = Image.fromarray((c * 255).astype(np.uint8)).resize(
        (max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)
    out = np.zeros((cell, cell), np.float32)
    oy, ox = (cell - im.height) // 2, (cell - im.width) // 2
    out[oy:oy + im.height, ox:ox + im.width] = np.array(im) / 255.0
    return (out > 0.43).astype(np.float32).ravel()


# 2) 载入图集
alpha = np.array(Image.open(ATLAS).convert("RGBA").split()[3])
rows, cols = alpha.shape[0] // CELL, alpha.shape[1] // CELL
vecs, ids, imgs = [], [], []
for k in range(rows * cols):
    r, c = divmod(k, cols)
    raw = (alpha[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL] > 110).astype(np.float32)
    if raw.sum() < 15:
        continue
    v = norm(raw)
    if v is None:
        continue
    vecs.append(v)
    ids.append(k)
    imgs.append(raw)
mat = np.stack(vecs)
ids = np.array(ids)
print("图集字形 %d 个" % len(ids))

# 3) 逐个游戏字去图集里找
print("\n游戏字 -> 图集最佳格子:")
for b in boxes[:12]:
    x0, y0, x1, y1, area = b
    sub = band[y0:y1 + 1, x0:x1 + 1]
    if sub.shape[0] < 20 or sub.shape[1] < 20:
        continue
    v = norm(sub)
    if v is None:
        continue
    inter = (mat * v).sum(1)
    union = mat.sum(1) + v.sum() - inter
    iou = inter / np.maximum(union, 1)
    j = int(iou.argmax())
    print("   (%3d,%3d) %2dx%-2d -> 格 %5d  IoU %.3f" % (x0, y0, sub.shape[1], sub.shape[0], ids[j], iou[j]))
