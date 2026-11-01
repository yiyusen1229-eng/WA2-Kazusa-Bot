# -*- coding: utf-8 -*-
"""字模映射 v2: 按外接框居中归一 + 匈牙利算法一对一匹配

v1 用「每个格子取最高 IoU 的字符」会塌缩(888 格里只有 252 个不同字),
因为简单字形的掩码彼此太像。这次:
  1. 先把每个字形裁到外接框再缩放居中, 消除位移差异
  2. 用 scipy 的匈牙利算法做全局一对一分配, 保证不重复
"""
import json

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.optimize import linear_sum_assignment

ATLAS = r"E:\Games\GALGAMES\WHITE ALBUM2\subfont.tga"
FONT = r"C:\Windows\Fonts\msyhbd.ttc"
OUT = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\app\assets\字体映射表.json"
CELL = 32
INNER = 26          # 归一化到 26x26 再比


def norm_mask(arr_img):
    """裁外接框 -> 等比缩放到 INNER 见方 -> 居中放置"""
    bb = arr_img.getbbox()
    if not bb:
        return None
    crop = arr_img.crop(bb)
    w, h = crop.size
    s = INNER / max(w, h)
    crop = crop.resize((max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)
    out = Image.new("L", (CELL, CELL), 0)
    out.paste(crop, ((CELL - crop.width) // 2, (CELL - crop.height) // 2))
    return (np.array(out) > 110).astype(np.float32).ravel()


def gb2312_chars():
    out = []
    for hi in range(0xA1, 0xF8):
        for lo in range(0xA1, 0xFF):
            try:
                out.append(bytes([hi, lo]).decode("gb2312"))
            except Exception:
                pass
    return out


chars = gb2312_chars()
alpha = Image.open(ATLAS).convert("RGBA").split()[3]
cols = alpha.width // CELL
rows = alpha.height // CELL

cell_ids, cell_vecs = [], []
for r in range(rows):
    for c in range(cols):
        cell = alpha.crop((c * CELL, r * CELL, (c + 1) * CELL, (r + 1) * CELL))
        v = norm_mask(cell)
        if v is not None:
            cell_ids.append(r * cols + c)
            cell_vecs.append(v)
cell_mat = np.stack(cell_vecs)
print("格子:", len(cell_ids))

keep, cand_vecs = [], []
f = ImageFont.truetype(FONT, 32)
for ch in chars:
    img = Image.new("L", (CELL, CELL), 0)
    d = ImageDraw.Draw(img)
    bb = f.getbbox(ch)
    if not bb:
        continue
    y = (CELL - (bb[3] - bb[1])) // 2 - bb[1]
    d.text((0, y), ch, font=f, fill=255)
    v = norm_mask(img)
    if v is None:
        continue
    keep.append(ch)
    cand_vecs.append(v)
cand_mat = np.stack(cand_vecs)
print("候选:", len(keep))

inter = cell_mat @ cand_mat.T
union = cell_mat.sum(1)[:, None] + cand_mat.sum(1)[None, :] - inter
iou = inter / np.maximum(union, 1)

# 匈牙利: 最大化总 IoU -> 最小化 -iou
cost = -iou
ri, ci = linear_sum_assignment(cost)
print("分配对数:", len(ri))

mapping = {}
scores = []
for r, c in zip(ri, ci):
    s = float(iou[r, c])
    if s < 0.45:
        continue
    mapping[str(cell_ids[r])] = {"ch": keep[c], "iou": round(s, 3)}
    scores.append(s)

print("写入映射 %d 格, 平均 IoU %.3f, 最低 %.3f" % (len(mapping), np.mean(scores), np.min(scores)))
rev = {}
for cid, v in mapping.items():
    rev.setdefault(v["ch"], []).append(cid)
print("不同字符数:", len(rev), " 重复:", sum(1 for v in rev.values() if len(v) > 1))

json.dump({"cell": mapping, "count": len(mapping)},
          open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
print("已保存:", OUT)
