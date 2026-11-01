# -*- coding: utf-8 -*-
"""量化对比: 游戏对话文字 vs 我们现在的渲染 (同尺寸归一后比笔画粗细和大小)"""
import io
import os
import sys

import numpy as np
from PIL import Image

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
GAME = r"C:\Users\asus\.dsh\attachments\v1\objects\32\32f773796aa3666f6aa89394f9dbb8d116c5550ddcaab66abe40bf04887bb8e2"
OURS = r"C:\Users\asus\.dsh\attachments\v1\objects\c6\c604aa314580f9ed68e521b236fe0c0ca4a2ec18d108cb43b73dbcc51d01b7dc"


def text_mask(im, y0, y1, thresh=200):
    a = np.array(im.convert("RGB")).astype(np.int16)
    mx = a.max(axis=2)
    mn = a.min(axis=2)
    w = (mx > thresh) & ((mx - mn) < 45)
    w[:y0] = False
    w[y1:] = False
    ys, xs = np.where(w)
    if len(ys) == 0:
        return None, None
    return w[ys.min():ys.max() + 1, xs.min():xs.max() + 1], (xs.min(), ys.min(), xs.max(), ys.max())


def stroke_stats(mask, label):
    h, w = mask.shape
    ink = mask.sum()
    # 每字宽度估计: 按连通块
    from scipy import ndimage
    lab, n = ndimage.label(mask)
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    big = [s for s in sizes if s > 40]
    # 笔画半宽: 反复腐蚀
    cur = mask.copy()
    k = 0
    while cur.any() and k < 30:
        cur = ndimage.binary_erosion(cur)
        k += 1
    print("  %-10s 框 %3dx%-3d  墨量 %5d  占比 %4.1f%%  连通块 %d  最大连通块 %4.0f  笔画半宽 %d"
          % (label, w, h, ink, 100.0 * ink / (w * h), len(big),
             max(big) if big else 0, k))
    return ink, w, h, k


print("=== 游戏原图 ===")
g = Image.open(GAME)
print("  尺寸", g.size)
# 对话文字大约在画面下部 72%~82%
W, H = g.size
gm, box = text_mask(g, int(H * 0.70), int(H * 0.84))
if gm is not None:
    stroke_stats(gm, "游戏")
    Image.fromarray((gm * 255).astype(np.uint8)).save(os.path.join(BASE, r"work\对比_游戏.png"))

print("=== 我们的截图 ===")
o = Image.open(OURS)
print("  尺寸", o.size)
W2, H2 = o.size
om, box2 = text_mask(o, int(H2 * 0.70), int(H2 * 0.84))
if om is not None:
    stroke_stats(om, "我们")
    Image.fromarray((om * 255).astype(np.uint8)).save(os.path.join(BASE, r"work\对比_我们.png"))
