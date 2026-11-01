# -*- coding: utf-8 -*-
"""像素级测量三件事:
  1. 字距（相邻字的中心间距 / 字宽）
  2. 「有」字的宽高比（判断是否被纵向压扁）
  3. 人名与正文的字高比
"""
import numpy as np
from PIL import Image
from scipy import ndimage

GAME = r"C:\Users\asus\.dsh\attachments\v1\objects\33\336fe9980d5eade8dc47e18f57f987bd529f3efd1b4c300e80dde4a35439ead2"
OURS = r"C:\Users\asus\.dsh\attachments\v1\objects\ca\cab17c1f460da73ce3bf77152563c3f7758390003ce554a3d82133570ffa30f5"


def glyphs(im, y0r, y1r, thresh=205, min_area=25):
    a = np.array(im.convert("RGB")).astype(np.int16)
    mx, mn = a.max(2), a.min(2)
    m = (mx > thresh) & ((mx - mn) < 45)
    m[:int(im.height * y0r)] = False
    m[int(im.height * y1r):] = False
    lab, n = ndimage.label(m)
    boxes = []
    for i in range(1, n + 1):
        ys, xs = np.where(lab == i)
        if len(ys) < min_area:
            continue
        boxes.append([xs.min(), ys.min(), xs.max(), ys.max()])
    # 按 x 合并重叠的碎块（同一个字可能被拆开）
    boxes.sort()
    merged = []
    for b in boxes:
        placed = False
        for m2 in merged:
            if not (b[0] > m2[2] + 2 or b[2] < m2[0] - 2):
                m2[0] = min(m2[0], b[0]); m2[1] = min(m2[1], b[1])
                m2[2] = max(m2[2], b[2]); m2[3] = max(m2[3], b[3])
                placed = True
                break
        if not placed:
            merged.append(b[:])
    return [b for b in merged if (b[2]-b[0]) > 4 and (b[3]-b[1]) > 4]


def report(im, label, body_r, name_r=None):
    g = glyphs(im, *body_r)
    if not g:
        print("%s 正文没测到" % label)
        return None
    hs = np.array([b[3]-b[1]+1 for b in g])
    ws = np.array([b[2]-b[0]+1 for b in g])
    cxs = np.array([(b[0]+b[2])/2 for b in g])
    gaps = np.diff(sorted(cxs))
    gaps = gaps[(gaps > 8) & (gaps < 80)]
    print("\n=== %s (%s) ===" % (label, im.size))
    print("  正文字形 %d 个" % len(g))
    print("  字高中位 %.1f   字宽中位 %.1f   宽高比 %.3f" % (np.median(hs), np.median(ws), np.median(ws)/np.median(hs)))
    if len(gaps):
        print("  字距(中心间距)中位 %.1f   字距/字宽 = %.3f" % (np.median(gaps), np.median(gaps)/np.median(ws)))
    # 最宽最方正的那个大概是"有"之类
    big = [b for b in g if (b[3]-b[1]+1) >= np.median(hs)*0.9]
    if big:
        bw = np.median([b[2]-b[0]+1 for b in big])
        bh = np.median([b[3]-b[1]+1 for b in big])
        print("  主体汉字(高>=中位) %d 个: 宽 %.1f 高 %.1f 宽高比 %.3f" % (len(big), bw, bh, bw/bh))
    if name_r:
        gn = glyphs(im, *name_r)
        if gn:
            hn = np.median([b[3]-b[1]+1 for b in gn])
            print("  人名 %d 字, 字高中位 %.1f   人名/正文 = %.3f" % (len(gn), hn, hn/np.median(hs)))
    return dict(h=np.median(hs), w=np.median(ws), pitch=np.median(gaps) if len(gaps) else 0)


g = Image.open(GAME).convert("RGB")
o = Image.open(OURS).convert("RGB")
rg = report(g, "游戏", (0.72, 0.80), (0.68, 0.72))
ro = report(o, "我们", (0.76, 0.84), (0.72, 0.76))

if rg and ro:
    print("\n===== 比例 =====")
    print("  字高 游戏/我们 = %.3f" % (rg["h"]/ro["h"]))
    print("  字宽 游戏/我们 = %.3f" % (rg["w"]/ro["w"]))
    print("  字距 游戏/我们 = %.3f" % (rg["pitch"]/ro["pitch"]) if ro["pitch"] else "")
    print("  游戏 字距/字宽 = %.3f   我们 %.3f" % (rg["pitch"]/rg["w"], ro["pitch"]/ro["w"]))
