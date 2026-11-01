# -*- coding: utf-8 -*-
"""分析 GitHub 仓库里的 fon.pak: 看它里面是不是中文字模"""
import os
import struct

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
PAK = os.path.join(BASE, r"work\gh_fon.pak")
OUT = os.path.join(BASE, r"work\gh_fon")
os.makedirs(OUT, exist_ok=True)

d = open(PAK, "rb").read()
magic, a, b, cnt = struct.unpack_from("<4sIII", d, 0)
print("magic=%r 条目数=%d 大小 %.2f MB" % (magic, cnt, len(d) / 1048576))

ents = []
for i in range(cnt):
    off = 16 + i * 44
    if off + 44 > len(d):
        break
    name = d[off + 4:off + 36].split(b"\x00")[0]
    foff, fsz = struct.unpack_from("<II", d, off + 36)
    try:
        nm = name.decode("shift-jis")
    except Exception:
        nm = name.decode("latin1", "ignore")
    ents.append((nm, foff, fsz))
    print("  [%2d] %-20s 偏移 %9d 大小 %9d" % (i, nm, foff, fsz))

# 导出 TGA 并找简体字
CELL = 32
TARGETS = "吧这话这瞧"


def norm(mask, cell=CELL):
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


for nm, foff, fsz in ents:
    if not nm.lower().endswith(".tga") or fsz < 1000:
        continue
    fp = os.path.join(OUT, nm)
    open(fp, "wb").write(d[foff:foff + fsz])
    try:
        im = Image.open(fp)
        alpha = np.array(im.convert("RGBA").split()[3])
    except Exception as e:
        print("  打不开 %s: %s" % (nm, e))
        continue
    rows, cols = alpha.shape[0] // CELL, alpha.shape[1] // CELL
    print("\n%s  %dx%d -> %d 格" % (nm, im.width, im.height, rows * cols))
    vecs, ids = [], []
    for k in range(rows * cols):
        r, c = divmod(k, cols)
        m = (alpha[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL] > 110).astype(np.float32)
        if m.sum() < 15:
            continue
        v = norm(m)
        if v is None:
            continue
        vecs.append(v)
        ids.append((r, c))
    if not vecs:
        continue
    mat = np.stack(vecs)
    f = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 30)
    for ch in "吧这":
        im2 = Image.new("L", (CELL, CELL), 0)
        dd = ImageDraw.Draw(im2)
        dd.text((0, 0), ch, font=f, fill=255)
        v = norm((np.array(im2) > 110).astype(np.float32))
        if v is None:
            continue
        inter = (mat * v).sum(1)
        union = mat.sum(1) + v.sum() - inter
        iou = inter / np.maximum(union, 1)
        j = int(iou.argmax())
        print("    字「%s」最佳 IoU %.3f  格子(行%d,列%d)" % (ch, iou[j], ids[j][0], ids[j][1]))
