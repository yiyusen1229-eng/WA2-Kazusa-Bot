# -*- coding: utf-8 -*-
"""对齐工具: 在两张 1280x720 截图里找同一块图案, 给出位移差"""
import sys
from PIL import Image


def gray(im):
    return im.convert("L")


def crop_gray(im, box):
    return gray(im).crop(box)


def ssd_at(hay, needle, ox, oy):
    """粗糙 SSD: needle 放在 (ox,oy) 处"""
    hw, hh = hay.size
    nw, nh = needle.size
    if ox + nw > hw or oy + nh > hh or ox < 0 or oy < 0:
        return 1e18
    hp = hay.load()
    np_ = needle.load()
    s = 0
    step = 3
    for y in range(0, nh, step):
        for x in range(0, nw, step):
            d = hp[ox + x, oy + y] - np_[x, y]
            s += d * d
    return s


def find(hay_path, needle_img, search_box, step=4):
    hay = gray(Image.open(hay_path).resize((1280, 720), Image.LANCZOS))
    x0, y0, x1, y1 = search_box
    best = (1e18, None)
    for oy in range(y0, y1, step):
        for ox in range(x0, x1, step):
            s = ssd_at(hay, needle_img, ox, oy)
            if s < best[0]:
                best = (s, (ox, oy))
    return best[1], best[0]


if __name__ == "__main__":
    game = sys.argv[1]
    ours = sys.argv[2]
    asset = sys.argv[3]

    a = Image.open(asset).convert("RGBA")
    bg = Image.new("RGBA", a.size, (10, 30, 48, 255))
    bg.alpha_composite(a)
    a = bg.convert("RGB")

    # 取资产左上角一块(含 "画面设置 SCREEN SETTING")
    needle = crop_gray(a, (0, 0, 300, 40))
    print("模板: 资产 (0,0)-(300,40)")

    p1, s1 = find(game, needle, (0, 60, 700, 260), 4)
    p2, s2 = find(ours, needle, (0, 60, 700, 260), 4)
    print("游戏里匹配到:", p1, "ssd=%.0f" % s1)
    print("我们里匹配到:", p2, "ssd=%.0f" % s2)
    if p1 and p2:
        print("偏差(1280坐标): dx=%d dy=%d" % (p2[0] - p1[0], p2[1] - p1[1]))
        print("偏差(800x450舞台): dx=%.1f dy=%.1f" % ((p2[0] - p1[0]) / 1.6, (p2[1] - p1[1]) / 1.6))
