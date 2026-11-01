# -*- coding: utf-8 -*-
"""用游戏对话截图当基准, 判断对话文字用的哪款字体(v2: 整行等比归一)"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

GAME = r"C:\Users\asus\.dsh\attachments\v1\objects\a5\a5db8fdca460689fc0a7bfea2f5860e369eb8ab77025b2b3ece6cfd0084cfbec"
BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
TEXT = "求求你，撤回前言吧"
LW, LH = 600, 40

CANDS = [
    ("微软雅黑 Bold", r"C:\Windows\Fonts\msyhbd.ttc"),
    ("微软雅黑", r"C:\Windows\Fonts\msyh.ttc"),
    ("Droid Sans Fallback", os.path.join(BASE, r"app\assets\DroidSansFallback.ttf")),
    ("SimHei 黑体", r"C:\Windows\Fonts\simhei.ttf"),
    ("等线 DengXian", r"C:\Windows\Fonts\Deng.ttf"),
    ("宋体 SimSun", r"C:\Windows\Fonts\simsun.ttc"),
]


def line_norm(mask):
    """把整行掩码按外接框缩放到 LW x LH, 保持宽高比并居中"""
    ys, xs = np.where(mask)
    if len(ys) == 0:
        return None
    c = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    im = Image.fromarray((c * 255).astype(np.uint8))
    s = min(LW / im.width, LH / im.height)
    im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    out = Image.new("L", (LW, LH), 0)
    out.paste(im, ((LW - im.width) // 2, (LH - im.height) // 2))
    return np.array(out) > 100


img = Image.open(GAME).convert("RGB")
a = np.array(img).astype(np.int16)
mx = a.max(axis=2)
mn = a.min(axis=2)
white = (mx > 200) & ((mx - mn) < 45)

# 用第二个文字行(「求求你，撤回前言吧…」)
rowsum = white.sum(axis=1)
rows = [y for y in range(img.height) if rowsum[y] > 30]
groups, cur = [], [rows[0]]
for y in rows[1:]:
    if y - cur[-1] <= 4:
        cur.append(y)
    else:
        groups.append(cur)
        cur = [y]
groups.append(cur)
groups = [g for g in groups if len(g) > 12]
print("找到文字行:", [(g[0], g[-1]) for g in groups])
g = groups[1] if len(groups) > 1 else groups[0]
y0, y1 = g[0], g[-1] + 1
cols = np.where(white[y0:y1].sum(axis=0) > 0)[0]
x0, x1 = cols.min(), cols.max() + 1
print("选用行: x %d..%d y %d..%d (%dx%d)" % (x0, x1, y0, y1, x1 - x0, y1 - y0))

ref = line_norm(white[y0:y1, x0:x1])
print("参考掩码墨迹:", int(ref.sum()))
Image.fromarray((ref * 255).astype(np.uint8)).save(os.path.join(BASE, r"work\参考字行.png"))

results = []
for name, path in CANDS:
    if not os.path.exists(path):
        continue
    best = (0, 0)
    for size in range(22, 40):
        im2 = Image.new("L", (900, 80), 0)
        d = ImageDraw.Draw(im2)
        f = ImageFont.truetype(path, size)
        d.text((4, 6), TEXT, font=f, fill=255)
        m = np.array(im2) > 100
        cand = line_norm(m)
        if cand is None:
            continue
        inter = np.logical_and(ref, cand).sum()
        union = np.logical_or(ref, cand).sum()
        iou = inter / union if union else 0
        if iou > best[0]:
            best = (iou, size)
    results.append((best[0], name, best[1]))
    print("  %-22s IoU %.3f  (字号 %d)" % (name, best[0], best[1]))

results.sort(reverse=True)
print("\n最像:", results[0][1] if results else "无")
