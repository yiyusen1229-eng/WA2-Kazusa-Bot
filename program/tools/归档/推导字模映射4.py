# -*- coding: utf-8 -*-
"""字模映射 v4: 按反编译确认的「列优先、每列 20 个」顺序重做保序对齐

d3d9.dll 的绘制代码:
    x = 32 * (code / 20)
    y = 32 * (code % 20)
=> 图集第 k 个字形的像素位置 = (col=k/20, row=k%20) * 32, 即「列优先」。
之前按行优先排序去做对齐, 顺序错了, 现在修正。
"""
import json

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.optimize import linear_sum_assignment

ATLAS = r"E:\Games\GALGAMES\WHITE ALBUM 2\subfont.tga"
ATLAS = r"E:\Games\GALGAMES\WHITE ALBUM2\subfont.tga"
FONT = r"C:\Windows\Fonts\msyhbd.ttc"
OUT = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\app\assets\字体映射表.json"
CELL = 32
INNER = 26
PER_COL = 20


def norm(img):
    bb = img.getbbox()
    if not bb:
        return None
    c = img.crop(bb)
    w, h = c.size
    s = INNER / max(w, h)
    c = c.resize((max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)
    out = Image.new("L", (CELL, CELL), 0)
    out.paste(c, ((CELL - c.width) // 2, (CELL - c.height) // 2))
    return (np.array(out) > 110).astype(np.float32).ravel()


alpha = Image.open(ATLAS).convert("RGBA").split()[3]
W, H = alpha.size
cols, rows = W // CELL, H // CELL
print("图集 %dx%d -> %d 列 x %d 行" % (W, H, cols, rows))

# 列优先索引
cells = []
for k in range(cols * rows):
    col, r = divmod(k, PER_COL)
    if col >= cols:
        break
    v = norm(alpha.crop((col * CELL, r * CELL, (col + 1) * CELL, (r + 1) * CELL)))
    if v is not None:
        cells.append((k, v))
print("非空字形:", len(cells))
cell_idx = np.array([k for k, _ in cells])
cell_mat = np.stack([v for _, v in cells])

# 候选: 常用汉字 + 标点, 按 Unicode 升序
cand, keep = [], []
f = ImageFont.truetype(FONT, 32)
for cp in range(0x20, 0x9FFF):
    ch = chr(cp)
    if ch.isspace():
        continue
    img = Image.new("L", (CELL, CELL), 0)
    d = ImageDraw.Draw(img)
    try:
        bb = f.getbbox(ch)
    except Exception:
        continue
    if not bb:
        continue
    y = (CELL - (bb[3] - bb[1])) // 2 - bb[1]
    d.text((0, y), ch, font=f, fill=255)
    v = norm(img)
    if v is None:
        continue
    keep.append(ch)
    cand.append(v)
cand_mat = np.stack(cand)
print("候选字符:", len(keep))

inter = cell_mat @ cand_mat.T
union = cell_mat.sum(1)[:, None] + cand_mat.sum(1)[None, :] - inter
iou = (inter / np.maximum(union, 1)).astype(np.float32)
print("IoU 矩阵:", iou.shape)

for th in (0.45, 0.55, 0.65):
    cost = np.where(iou > th, -iou, 1.0)
    ri, ci = linear_sum_assignment(cost)
    mapping = {}
    for r, c in zip(ri, ci):
        s = float(iou[r, c])
        if s < th:
            continue
        mapping[str(cell_idx[r])] = {"ch": keep[c], "iou": round(s, 3)}
    rev = {}
    for cid, v in mapping.items():
        rev.setdefault(v["ch"], []).append(cid)
    dup = sum(1 for v in rev.values() if len(v) > 1)
    av = [v["iou"] for v in mapping.values()]
    print("  阈值 %.2f: 映射 %d 格, 不同字 %d, 重复 %d, 平均 IoU %.3f"
          % (th, len(mapping), len(rev), dup, np.mean(av) if av else 0))

# 用最优阈值保存
cost = np.where(iou > 0.5, -iou, 1.0)
ri, ci = linear_sum_assignment(cost)
mapping = {}
for r, c in zip(ri, ci):
    s = float(iou[r, c])
    if s < 0.5:
        continue
    mapping[str(cell_idx[r])] = {"ch": keep[c], "iou": round(s, 3)}
json.dump({"cell": mapping, "count": len(mapping), "order": "column-major", "per_col": PER_COL},
          open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
print("已保存:", OUT, len(mapping), "格")
