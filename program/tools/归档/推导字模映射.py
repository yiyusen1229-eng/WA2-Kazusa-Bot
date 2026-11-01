# -*- coding: utf-8 -*-
"""自动推导 subfont.tga 的 字符→格子 映射

原理:
  图集里的字形是 微软雅黑 Bold 32px 渲染的位图。
  把 GB2312 全部汉字用同一字体同一字号渲染成掩码,
  与 890 个格子逐一算 IoU, 取最相似的字符作为该格子的身份。
用训练环境(含 numpy)跑, 890x6763 的矩阵运算很快。
"""
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ATLAS = r"E:\Games\GALGAMES\WHITE ALBUM2\subfont.tga"
FONT = r"C:\Windows\Fonts\msyhbd.ttc"
OUT = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\app\assets\字体映射表.json"
CELL = 32


def gb2312_chars():
    """按 GB2312 编码顺序取所有汉字与符号"""
    out = []
    for hi in range(0xA1, 0xF8):
        for lo in range(0xA1, 0xFF):
            try:
                ch = bytes([hi, lo]).decode("gb2312")
            except Exception:
                continue
            out.append(ch)
    return out


chars = gb2312_chars()
print("GB2312 字符数:", len(chars))

im = Image.open(ATLAS).convert("RGBA")
alpha = im.split()[3]
cols = alpha.width // CELL
rows = alpha.height // CELL

cells = []
for r in range(rows):
    for c in range(cols):
        cell = alpha.crop((c * CELL, r * CELL, (c + 1) * CELL, (r + 1) * CELL))
        arr = (np.array(cell) > 110).astype(np.uint8).ravel()
        if arr.sum() > 6:
            cells.append((r * cols + c, arr))
print("有效格子:", len(cells))

cell_idx = np.array([i for i, _ in cells])
cell_mat = np.stack([a for _, a in cells]).astype(np.float32)   # (N, 1024)

# 渲染候选字
cand = []
keep = []
for ch in chars:
    img = Image.new("L", (CELL, CELL), 0)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, 32)
    bb = f.getbbox(ch)
    if not bb:
        continue
    y = (CELL - (bb[3] - bb[1])) // 2 - bb[1]
    d.text((0, y), ch, font=f, fill=255)
    a = (np.array(img) > 110).astype(np.uint8).ravel()
    if a.sum() < 6:
        continue
    keep.append(ch)
    cand.append(a)
cand_mat = np.stack(cand).astype(np.float32)
print("候选字符:", len(keep))

# IoU 矩阵
inter = cell_mat @ cand_mat.T
sum_cell = cell_mat.sum(1)[:, None]
sum_cand = cand_mat.sum(1)[None, :]
union = sum_cell + sum_cand - inter
iou = inter / np.maximum(union, 1)

best = iou.argmax(1)
score = iou.max(1)

mapping = {}
low = 0
for k, cid in enumerate(cell_idx):
    s = float(score[k])
    if s < 0.35:
        low += 1
        continue
    mapping[str(cid)] = {"ch": keep[int(best[k])], "iou": round(s, 3)}

print("映射成功 %d 格, 置信度低(跳过) %d 格" % (len(mapping), low))
print("平均 IoU: %.3f" % np.mean([v["iou"] for v in mapping.values()]))

# 检查重复: 同一个字被映射到多个格子
rev = {}
for cid, v in mapping.items():
    rev.setdefault(v["ch"], []).append(cid)
dup = {k: v for k, v in rev.items() if len(v) > 1}
print("重复映射的字:", len(dup))

json.dump({"cell": mapping, "count": len(mapping)},
          open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
print("已保存:", OUT)
