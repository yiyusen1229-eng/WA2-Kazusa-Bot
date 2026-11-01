# -*- coding: utf-8 -*-
"""量出游戏字幕的白色到底是哪个色号的 RGB"""
import numpy as np
from PIL import Image

GAME = r"C:\Users\asus\.dsh\attachments\v1\objects\42\42eef33234786ecd044d24852f2a9a0821ff7cf41d0168d4c40b70b66c782da8"
OURS = r"C:\Users\asus\.dsh\attachments\v1\objects\c6\c63f24e48d9a6590d558acd49c66c8e52a621efe523addbe2be21a4341196097"


def core_color(path, label, top_frac=0.25):
    im = Image.open(path).convert("RGB")
    a = np.array(im).astype(np.float32)
    g = a.mean(2)
    mx, mn = a.max(2), a.min(2)
    sat = mx - mn
    # 白芯: 亮且低饱和
    m = (g > 195) & (sat < 30)
    if m.sum() < 50:
        print("%s: 白芯太少" % label)
        return
    vals = a[m]
    # 取最亮的那部分(白芯核心), 排除边缘半透明像素
    lum = vals.mean(1)
    thr = np.quantile(lum, 1 - top_frac)
    core = vals[lum >= thr]
    r, gg, b = core[:, 0].mean(), core[:, 1].mean(), core[:, 2].mean()
    print("\n=== %s ===" % label)
    print("  白芯像素 %d, 其中核心 %d" % (m.sum(), len(core)))
    print("  核心 RGB = (%.0f, %.0f, %.0f)   #%02X%02X%02X" % (r, gg, b, int(r), int(gg), int(b)))
    print("  亮度 %.0f   色偏 R-B = %+.0f, G-B = %+.0f" % ((r + gg + b) / 3, r - b, gg - b))
    # 描边
    from scipy import ndimage
    dil = ndimage.binary_dilation(m, iterations=3) & ~m
    if dil.sum():
        d = a[dil]
        print("  描边 RGB = (%.0f, %.0f, %.0f)  亮度 %.0f" % (d[:, 0].mean(), d[:, 1].mean(), d[:, 2].mean(), d.mean()))


core_color(GAME, "游戏")
core_color(OURS, "我们")
