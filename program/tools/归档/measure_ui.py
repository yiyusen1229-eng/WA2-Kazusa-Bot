# -*- coding: utf-8 -*-
"""从游戏原截图测量 UI 元素几何, 换算到 800x450 舞台坐标"""
import sys
from PIL import Image


def load(p):
    return Image.open(p).convert("RGB")


def find_panel(src, out_prefix):
    im = load(src)
    W, H = im.size
    px = im.load()
    # 找青色边框像素 (R低 G高 B高)
    def is_cyan(c):
        r, g, b = c
        return g > 140 and b > 160 and r < 140 and (g + b) > 340

    cols = [0] * W
    rows = [0] * H
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            if is_cyan(px[x, y]):
                cols[x] += 1
                rows[y] += 1
    xs = [x for x in range(W) if cols[x] > 3]
    ys = [y for y in range(H) if rows[y] > 3]
    if not xs or not ys:
        print("未找到边框")
        return
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    print("%s  图像 %dx%d" % (out_prefix, W, H))
    print("  青色边框范围: x %d..%d  y %d..%d" % (x0, x1, y0, y1))
    # 换算到 800x450
    sx = 800.0 / W
    sy = 450.0 / H
    print("  舞台坐标(800x450): x %.1f..%.1f  y %.1f..%.1f  (宽 %.1f 高 %.1f)"
          % (x0 * sx, x1 * sx, y0 * sy, y1 * sy, (x1 - x0) * sx, (y1 - y0) * sy))

    # 扫描水平分隔线(行的上下边界): 统计每行青色像素数, 找峰值
    peaks = [(y, rows[y]) for y in range(y0, y1 + 1) if rows[y] > W * 0.25]
    if peaks:
        print("  长横线(行分隔) y:", [p[0] for p in peaks][:14])


if __name__ == "__main__":
    for p in sys.argv[1:]:
        find_panel(p, p.split("\\")[-1][:8])
