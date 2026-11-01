# -*- coding: utf-8 -*-
"""用游戏对话截图当基准, 判断对话文字到底用的哪款字体

之前用 subfont.tga(字幕字模) 当基准得出"微软雅黑 Bold", 可能选错了对象:
对话文字是游戏引擎画的, 补丁带的 default.ttf(Droid Sans Fallback) 很可能才是它用的字体。
这里直接拿游戏截图里的字幕行, 和各种候选字体做 IoU 比对。
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

GAME = r"C:\Users\asus\.dsh\attachments\v1\objects\a5\a5db8fdca460689fc0a7bfea2f5860e369eb8ab77025b2b3ece6cfd0084cfbec"
BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
TEXT = "求求你，撤回前言吧"

CANDS = [
    ("微软雅黑 Bold", r"C:\Windows\Fonts\msyhbd.ttc"),
    ("微软雅黑", r"C:\Windows\Fonts\msyh.ttc"),
    ("Droid Sans Fallback", os.path.join(BASE, r"app\assets\DroidSansFallback.ttf")),
    ("SimHei 黑体", r"C:\Windows\Fonts\simhei.ttf"),
    ("等线 DengXian", r"C:\Windows\Fonts\Deng.ttf"),
    ("思源/Noto", r"C:\Windows\Fonts\NotoSansSC-Regular.otf"),
]

img = Image.open(GAME).convert("RGB")
W, H = img.size
print("游戏截图:", W, H)

# 找白色文字所在行(取中下部)
a = np.array(img).astype(np.int16)
mx = a.max(axis=2)
mn = a.min(axis=2)
white = (mx > 200) & ((mx - mn) < 45)
rowsum = white.sum(axis=1)
# 取文字行: 行内有较多白像素
rows = [y for y in range(H // 3, H) if rowsum[y] > 40]
if not rows:
    raise SystemExit("没找到文字行")
# 找连续段, 取最长的一段
groups, cur = [], [rows[0]]
for y in rows[1:]:
    if y - cur[-1] <= 3:
        cur.append(y)
    else:
        groups.append(cur)
        cur = [y]
groups.append(cur)
groups.sort(key=len, reverse=True)
g = groups[0]
y0, y1 = g[0], g[-1] + 1
cols = np.where(white[y0:y1].sum(axis=0) > 0)[0]
x0, x1 = cols.min(), cols.max() + 1
print("文字行区域: x %d..%d  y %d..%d (%dx%d)" % (x0, x1, y0, y1, x1 - x0, y1 - y0))

crop = img.crop((x0, y0, x1, y1))
crop.resize(((x1 - x0) * 2, (y1 - y0) * 2), Image.LANCZOS).save(os.path.join(BASE, r"work\游戏文字行.png"))

ref_mask = white[y0:y1, x0:x1]


def norm_mask(m, size=32, inner=30):
    ys, xs = np.where(m)
    if len(ys) == 0:
        return None
    c = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    im = Image.fromarray((c * 255).astype(np.uint8))
    h, w = im.height, im.width
    s = inner / max(w, h)
    im = im.resize((max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)
    out = Image.new("L", (size * 8, size * 2), 0)
    return np.array(im.resize((inner, inner), Image.LANCZOS)) > 100


ref = norm_mask(ref_mask)
if ref is None:
    raise SystemExit("参考掩码为空")
print("参考掩码:", ref.shape, " 墨迹", int(ref.sum()))

for name, path in CANDS:
    if not os.path.exists(path):
        print("  跳过(缺字体):", name)
        continue
    best = (0, 0)
    for size in range(24, 34):
        for dy in range(-2, 3):
            img2 = Image.new("L", (600, 60), 0)
            d = ImageDraw.Draw(img2)
            f = ImageFont.truetype(path, size)
            d.text((4, 6 + dy), TEXT, font=f, fill=255)
            m = np.array(img2) > 100
            cand = norm_mask(m)
            if cand is None:
                continue
            inter = np.logical_and(ref, cand).sum()
            union = np.logical_or(ref, cand).sum()
            iou = inter / union if union else 0
            if iou > best[0]:
                best = (iou, size)
    print("  %-22s 最佳 IoU %.3f  (字号 %d)" % (name, best[0], best[1]))
