# -*- coding: utf-8 -*-
"""测量游戏 OPTION 截图的版面几何(换算到 1280x720)"""
import sys
from PIL import Image


def main(path):
    im = Image.open(path).convert("RGB")
    W, H = im.size
    sx, sy = 1280.0 / W, 720.0 / H
    px = im.load()

    def cyan(c):
        r, g, b = c
        return g > 130 and b > 150 and r < 150 and (g + b) > 320 and (b - r) > 40

    # 1) 每条横线上的青色像素数
    rows = []
    for y in range(H):
        n = sum(1 for x in range(0, W, 3) if cyan(px[x, y]))
        rows.append(n * 3)

    # 2) 找长横线
    lines = [(y, rows[y]) for y in range(H) if rows[y] > W * 0.35]
    groups = []
    for y, n in lines:
        if groups and y - groups[-1][-1][0] <= 3:
            groups[-1].append((y, n))
        else:
            groups.append([(y, n)])
    print("图像 %dx%d  横线组:" % (W, H))
    for g in groups:
        y0 = g[0][0]
        print("  y=%4d (720坐标系 %5.1f)  长度≈%d/%d" % (y0, y0 * sy, max(n for _, n in g), W))

    # 3) 面板左右边缘: 在中间高度扫描最左/最右的青色
    midy = int(H * 0.5)
    xs = [x for x in range(W) if cyan(px[x, midy])]
    if xs:
        print("中部 y=%d 的青色 x 范围: %d..%d (1280坐标系 %.1f..%.1f)"
              % (midy, min(xs), max(xs), min(xs) * sx, max(xs) * sx))

    # 4) 顶栏 / 底栏 高度: 找第一条和最后一条长横线
    if groups:
        first = groups[0][0][0]
        last = groups[-1][0][0]
        print("第一道长横线 y=%d (%.1f)   最后一道 y=%d (%.1f)"
              % (first, first * sy, last, last * sy))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        main(p)
        print()
