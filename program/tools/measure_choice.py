# -*- coding: utf-8 -*-
"""在「选项条所在的窗口」里量：亮青蓝上/下沿 + 左右端。

窗口默认 y 150..250（800×450 舞台），x 150..720 —— 原版那张网格图上读出来的。
用法：python tools/measure_choice.py 原版.png [渲染.png]
"""
import os
import sys

from PIL import Image

STAGE_W, STAGE_H = 800, 450
WIN = (150, 150, 720, 250)      # x0, y0, x1, y1
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def stage(path):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    im = im.resize((STAGE_W, int(round(h * STAGE_W / float(w)))), Image.LANCZOS)
    if im.size[1] > STAGE_H:
        t = (im.size[1] - STAGE_H) // 2
        im = im.crop((0, t, STAGE_W, t + STAGE_H))
    elif im.size[1] < STAGE_H:
        c = Image.new("RGB", (STAGE_W, STAGE_H), (0, 0, 0))
        c.paste(im, (0, 0))
        im = c
    return im


def cyan(p):
    r, g, b = p
    return b > 170 and g > 150 and r < 200


def band_rows(px, x0, x1, y0, y1, min_frac=0.5):
    """返回 [(top, bottom, left, right)]"""
    need = int((x1 - x0) * min_frac)
    rows = []
    for y in range(y0, y1):
        n = sum(1 for x in range(x0, x1) if cyan(px[x, y]))
        rows.append((y, n >= need))
    bands, cur = [], None
    for y, on in rows:
        if on and cur is None:
            cur = y
        elif not on and cur is not None:
            if y - cur >= 3:
                bands.append((cur, y - 1))
            cur = None
    if cur is not None and y1 - cur >= 3:
        bands.append((cur, y1 - 1))
    out = []
    for t, b in bands:
        xs = [x for y in range(t, b + 1) for x in range(x0, x1) if cyan(px[x, y])]
        if xs:
            out.append((t, b, min(xs), max(xs)))
    return out


def report(label, path):
    im = stage(path)
    px = im.load()
    x0, y0, x1, y1 = WIN
    bs = band_rows(px, x0, x1, y0, y1)
    print("\n== %s == %s" % (label, os.path.basename(path)))
    for i, (t, b, l, r) in enumerate(bs):
        print("  条%d: top=%d bottom=%d 高=%d 左=%d 右=%d 宽=%d"
              % (i + 1, t, b, b - t + 1, l, r, r - l + 1))
    if len(bs) >= 2:
        print("  行距=%d 缝=%d" % (bs[1][0] - bs[0][0], bs[1][0] - bs[0][1] - 1))
    return bs


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    a = report("原版", sys.argv[1])
    if len(sys.argv) >= 3:
        b = report("渲染", sys.argv[2])
        if a and b:
            print("\n== 差值（渲染 − 原版）==")
            print("  高 %+d 宽 %+d top %+d 左 %+d"
                  % (b[0][1] - b[0][0] - (a[0][1] - a[0][0]), b[0][3] - b[0][2] - (a[0][3] - a[0][2]),
                     b[0][0] - a[0][0], b[0][2] - a[0][2]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
