# -*- coding: utf-8 -*-
"""读取游戏截图与我们的截图, 量化比较白芯亮度、描边深度、描边粗细"""
import numpy as np
from PIL import Image

GAME = r"C:\Users\asus\.dsh\attachments\v1\objects\42\42eef33234786ecd044d24852f2a9a0821ff7cf41d0168d4c40b70b66c782da8"
OURS = r"C:\Users\asus\.dsh\attachments\v1\objects\55\5520a626b274610dd088b517b1c26027c079527d3c12b7685241f045b457b409"


def analyze(path, label, thresh_white=200):
    im = Image.open(path).convert("RGB")
    a = np.array(im).astype(np.float32)
    g = a.mean(2)
    mx = a.max(2)
    mn = a.min(2)
    sat = mx - mn
    white = (g > thresh_white) & (sat < 40)
    if white.sum() < 100:
        print("  %s: 白字太少" % label)
        return
    ys, xs = np.where(white)
    bx = (xs.min(), ys.min(), xs.max(), ys.max())
    print("\n=== %s  图 %s ===" % (label, im.size))
    print("  文字外接框: %s" % (bx,))
    print("  白芯像素数: %d" % int(white.sum()))
    # 白芯亮度
    core = a[white]
    print("  白芯亮度   均值 %.1f  中位 %.1f  最高 %.1f" % (core.mean(), np.median(core), core.max()))
    # 描边: 紧贴白芯的暗像素
    from scipy import ndimage
    dil = ndimage.binary_dilation(white, iterations=2)
    ring = dil & ~white
    ring_vals = g[ring]
    if len(ring_vals):
        print("  描边亮度   均值 %.1f  中位 %.1f  最低 %.1f" % (
            ring_vals.mean(), np.median(ring_vals), ring_vals.min()))
    # 描边宽度: 从白芯向外, 暗像素连续几圈
    dark = (g < 90) & (sat < 60)
    # 用白芯数量/周长估算描边厚度
    per = ndimage.binary_erosion(dil).sum() - white.sum()
    print("  白芯外形周长约: %d" % int(per))
    if per > 0:
        print("  描边暗像素数 / 周长 = %.2f" % (dark.sum() / per))
    print("  整体暗像素(描边)数: %d, 平均亮度 %.1f" % (int(dark.sum()), g[dark].mean() if dark.sum() else 0))


analyze(GAME, "游戏")
analyze(OURS, "我们")
