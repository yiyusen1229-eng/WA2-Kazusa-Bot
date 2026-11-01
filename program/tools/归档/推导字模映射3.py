# -*- coding: utf-8 -*-
"""字模映射 v3: 利用「图集按 Unicode 升序排列」这一性质, 做保序对齐

既然格子按码位升序, 字符也必须按码位升序匹配 —— 这是一个单调对齐问题:
  在候选字符序列(按码位排序)中, 找出与 890 个格子一一对应、且保持顺序的子序列,
  使总 IoU 最大。用动态规划解, 结果比匈牙利(可乱序)准确得多。
"""
import json

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ATLAS = r"E:\Games\GALGAMES\WHITE ALBUM2\subfont.tga"
FONT = r"C:\Windows\Fonts\msyhbd.ttc"
OUT = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\app\assets\字体映射表.json"
CELL = 32
INNER = 26


def norm_mask(img):
    bb = img.getbbox()
    if not bb:
        return None
    crop = img.crop(bb)
    w, h = crop.size
    s = INNER / max(w, h)
    crop = crop.resize((max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)
    out = Image.new("L", (CELL, CELL), 0)
    out.paste(crop, ((CELL - crop.width) // 2, (CELL - crop.height) // 2))
    return (np.array(out) > 110).astype(np.float32).ravel()


def all_chars():
    """候选字符: 常用汉字 + 标点/符号, 按 Unicode 升序"""
    out = []
    for cp in range(0x20, 0x9FFF):
        try:
            ch = chr(cp)
        except Exception:
            continue
        if ch.isspace():
            continue
        out.append(ch)
    return out


chars = all_chars()
print("候选字符:", len(chars))

alpha = Image.open(ATLAS).convert("RGBA").split()[3]
cols = alpha.width // CELL
rows = alpha.height // CELL
cell_ids, cell_vecs = [], []
for r in range(rows):
    for c in range(cols):
        v = norm_mask(alpha.crop((c * CELL, r * CELL, (c + 1) * CELL, (r + 1) * CELL)))
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
    try:
        bb = f.getbbox(ch)
    except Exception:
        continue
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
print("有效候选:", len(keep))

inter = cell_mat @ cand_mat.T
union = cell_mat.sum(1)[:, None] + cand_mat.sum(1)[None, :] - inter
iou = (inter / np.maximum(union, 1)).astype(np.float32)
# 只保留高相似度区域, 其余给负分(不参与匹配)
score = np.where(iou > 0.40, iou, -1.0)

N, M = score.shape
print("DP 矩阵 %d x %d" % (N, M))
NEG = -1e9
dp = np.full((N + 1, M + 1), NEG, dtype=np.float64)
dp[0, :] = 0.0
for i in range(1, N + 1):
    prev = dp[i - 1]
    run = np.maximum.accumulate(prev)
    dp[i, 1:] = run[:-1] + score[i - 1]

best_end = int(np.argmax(dp[N]))
print("最优终点列:", best_end, " 总分 %.1f" % dp[N, best_end])

# 回溯
assign = []
j = best_end
for i in range(N, 0, -1):
    # 找到使 dp 成立的 j-1
    while j > 0 and abs(dp[i, j] - (dp[i - 1, j - 1] + score[i - 1, j - 1])) > 1e-6:
        j -= 1
    if j == 0:
        break
    assign.append((i - 1, j - 1))
    j -= 1
assign.reverse()
print("对齐上 %d 个" % len(assign))

mapping = {}
for ci, cj in assign:
    mapping[str(cell_ids[ci])] = {"ch": keep[cj], "iou": round(float(iou[ci, cj]), 3)}
rev = {}
for cid, v in mapping.items():
    rev.setdefault(v["ch"], []).append(cid)
print("不同字:", len(rev), " 重复:", sum(1 for v in rev.values() if len(v) > 1))
av = [v["iou"] for v in mapping.values()]
print("平均 IoU %.3f, 最低 %.3f" % (np.mean(av), np.min(av)))

json.dump({"cell": mapping, "count": len(mapping), "order": "unicode"},
          open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
print("已保存:", OUT)
