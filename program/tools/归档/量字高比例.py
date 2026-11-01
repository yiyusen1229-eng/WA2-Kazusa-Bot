# -*- coding: utf-8 -*-
"""量两张截图里字幕的字高, 算出我们还需要放大多少"""
import numpy as np
from PIL import Image
from scipy import ndimage

GAME = r"C:\Users\asus\.dsh\attachments\v1\objects\33\336fe9980d5eade8dc47e18f57f987bd529f3efd1b4c300e80dde4a35439ead2"
OURS = r"C:\Users\asus\.dsh\attachments\v1\objects\33\33cca83e1e2e249e10acfc6568508fe952ef5bd8b4117a618139921c5a40d29b"


def measure(path, label, yr=(0.70, 0.95)):
    im = Image.open(path).convert("RGB")
    a = np.array(im).astype(np.int16)
    mx, mn = a.max(2), a.min(2)
    white = (mx > 210) & ((mx - mn) < 45)
    white[:int(im.height * yr[0])] = False
    white[int(im.height * yr[1]):] = False
    lab, n = ndimage.label(white)
    hs = []
    for i in range(1, n + 1):
        ys, xs = np.where(lab == i)
        if len(ys) < 30:
            continue
        h = ys.max() - ys.min() + 1
        w = xs.max() - xs.min() + 1
        if 0.4 < w / h < 2.2 and h > 8:
            hs.append(h)
    hs = np.array(hs)
    print("%s  图 %s  样本 %d  字高中位 %.1f  均值 %.1f" % (
        label, im.size, len(hs), np.median(hs) if len(hs) else 0,
        hs.mean() if len(hs) else 0))
    return float(np.median(hs)) if len(hs) else 0


g = measure(GAME, "游戏")
o = measure(OURS, "我们")
if g and o:
    print("\n比例: 游戏/我们 = %.2f" % (g / o))
    print("→ 我们的字需要放大 %.2f 倍" % (g / o))
