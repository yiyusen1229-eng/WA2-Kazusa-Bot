# -*- coding: utf-8 -*-
"""验证假设: 图集 890 格 = 剧本里出现频率最高的 890 个字, 按 Unicode 排序

检验方法:
  取语料里出现最多的 890 个不同字符, 按码位排序,
  与图集格子逐一算 IoU。如果假设成立, 平均 IoU 应显著高于随机/错误排序。
  同时和「按 GB2312 排序」「按频率排序」做对照。
"""
import collections
import json

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ATLAS = r"E:\Games\GALGAMES\WHITE ALBUM 2\subfont.tga"
ATLAS = r"E:\Games\GALGAMES\WHITE ALBUM2\subfont.tga"
FONT = r"C:\Windows\Fonts\msyhbd.ttc"
CORPUS = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\dataset\L2_scene.jsonl"
CELL = 32
INNER = 26


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
cols = alpha.width // CELL
cell_vecs = []
for r in range(alpha.height // CELL):
    for c in range(cols):
        v = norm(alpha.crop((c * CELL, r * CELL, (c + 1) * CELL, (r + 1) * CELL)))
        if v is not None:
            cell_vecs.append(v)
cell_mat = np.stack(cell_vecs)
print("格子:", len(cell_mat))

cnt = collections.Counter()
for line in open(CORPUS, encoding="utf-8"):
    d = json.loads(line)
    for t in (d.get("context", ""), d.get("response", "")):
        for ch in t:
            if ch.strip():
                cnt[ch] += 1
print("语料不同字符:", len(cnt))

f = ImageFont.truetype(FONT, 32)


def cand_vec(ch):
    img = Image.new("L", (CELL, CELL), 0)
    d = ImageDraw.Draw(img)
    try:
        bb = f.getbbox(ch)
    except Exception:
        return None
    if not bb:
        return None
    y = (CELL - (bb[3] - bb[1])) // 2 - bb[1]
    d.text((0, y), ch, font=f, fill=255)
    return norm(img)


def score_order(chars, label):
    chars = chars[:len(cell_mat)]
    vecs, keep = [], []
    for ch in chars:
        v = cand_vec(ch)
        if v is not None:
            vecs.append(v)
            keep.append(ch)
    if len(vecs) < len(cell_mat):
        vecs += [np.zeros(CELL * CELL, np.float32)] * (len(cell_mat) - len(vecs))
    cm = np.stack(vecs[:len(cell_mat)])
    inter = (cell_mat * cm).sum(1)
    union = cell_mat.sum(1) + cm.sum(1) - inter
    iou = inter / np.maximum(union, 1)
    print("  %-22s 平均 IoU %.3f   >0.6 的比例 %.0f%%"
          % (label, iou.mean(), 100 * (iou > 0.6).mean()))
    return iou, keep


top = [ch for ch, _ in cnt.most_common(890)]
print("\n对比不同排序假设:")
score_order(sorted(top), "高频890按Unicode")
score_order(top, "按频率排序")
score_order(sorted(list(cnt.keys()))[:890], "全语料按Unicode取前890")
