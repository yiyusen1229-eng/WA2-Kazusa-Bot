# -*- coding: utf-8 -*-
"""量化纵向拉伸: 比对右侧大雪花的长宽比"""
from PIL import Image

GAME = r"C:\Users\asus\.dsh\attachments\v1\objects\33\336fe9980d5eade8dc47e18f57f987bd529f3efd1b4c300e80dde4a35439ead2"
OURS = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\work\dlg_final10.png"


def snowflake_bbox(im, x0, x1, y0, y1):
    px = im.load()
    pts = []
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b = px[x, y]
            # 雪花是接近纯白的亮像素
            if r > 190 and g > 225 and b > 240:
                pts.append((x, y))
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


for name, path in (("游戏", GAME), ("我们", OURS)):
    im = Image.open(path).convert("RGB").resize((1280, 720), Image.LANCZOS)
    bb = snowflake_bbox(im, 980, 1160, 480, 700)
    if bb:
        w = bb[2] - bb[0] + 1
        h = bb[3] - bb[1] + 1
        print("%s 右雪花: x %d..%d  y %d..%d   宽 %d 高 %d  长宽比 %.3f"
              % (name, bb[0], bb[2], bb[1], bb[3], w, h, h / w))
    else:
        print("%s: 未找到雪花" % name)
