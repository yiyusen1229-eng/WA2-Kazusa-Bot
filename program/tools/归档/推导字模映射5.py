# -*- coding: utf-8 -*-
"""字模映射 v5: 候选集限定为「剧本实际用到的字」, 按码位排序做保序对齐

依据:
  * 图集按行优先填充, 每行 20 个 (640/32)
  * 第一行是标点, 第二行起字符的 Unicode 码位严格递增 (世4E16<业4E1A<东4E1C…)
  => 图集顺序 = 某批字符按码位升序排列
  * 候选集用剧本里出现过的字(3169 个), 而不是全部 4 万汉字, 大幅降低歧义
"""
import collections
import json

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ATLAS = r"E:\Games\GALGAMES\WHITE ALBUM2\subfont.tga"
FONT = r"C:\Windows\Fonts\msyhbd.ttc"
CORPUS = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\dataset\L2_scene.jsonl"
OUT = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\app\assets\字体映射表.json"
CELL = 32
INNER = 26
COLS = 20


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
rows = alpha.height // CELL
cells, ids = [], []
for k in range(rows * COLS):
    r, c = divmod(k, COLS)
    v = norm(alpha.crop((c * CELL, r * CELL, (c + 1) * CELL, (r + 1) * CELL)))
    if v is not None:
        ids.append(k)
        cells.append(v)
cell_mat = np.stack(cells)
print("字形格:", len(ids))

# 候选: 剧本用字, 按码位升序
used = set()
for line in open(CORPUS, encoding="utf-8"):
    d = json.loads(line)
    for t in (d.get("context", ""), d.get("response", "")):
        used.update(ch for ch in t if not ch.isspace())
cand_chars = sorted(used)
print("剧本用字:", len(cand_chars))

f = ImageFont.truetype(FONT, 32)
cand, keep = [], []
for ch in cand_chars:
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

inter = cell_mat @ cand_mat.T
union = cell_mat.sum(1)[:, None] + cand_mat.sum(1)[None, :] - inter
iou = (inter / np.maximum(union, 1)).astype(np.float32)
print("IoU 矩阵:", iou.shape)

N, M = iou.shape
NEG = -1e9
dp = np.full((N + 1, M + 1), NEG)
dp[0, :] = 0.0
for i in range(1, N + 1):
    run = np.maximum.accumulate(dp[i - 1])
    dp[i, 1:] = run[:-1] + iou[i - 1]

best_j = int(np.argmax(dp[N]))
score = dp[N, best_j]
print("最优总分 %.1f (平均 %.3f)" % (score, score / N))

assign = []
j = best_j
for i in range(N, 0, -1):
    while j > 0 and abs(dp[i, j] - (dp[i - 1, j - 1] + iou[i - 1, j - 1])) > 1e-6:
        j -= 1
    if j == 0:
        break
    assign.append((i - 1, j - 1))
    j -= 1
assign.reverse()

mapping = {}
pairs = []
for ci, cj in assign:
    mapping[str(ids[ci])] = {"ch": keep[cj], "iou": round(float(iou[ci, cj]), 3)}
    pairs.append((ids[ci], keep[cj], float(iou[ci, cj])))

rev = {v["ch"]: v["iou"] for v in mapping.values()}
print("映射格数:", len(mapping), " 不同字:", len(rev))
for ch in "求你撤前言吧和纱有事":
    print("   %s -> %s" % (ch, "有" if ch in rev else "无"))

json.dump({"cell": mapping, "count": len(mapping), "order": "row-major-20", "per_row": COLS},
          open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
print("已保存:", OUT)
