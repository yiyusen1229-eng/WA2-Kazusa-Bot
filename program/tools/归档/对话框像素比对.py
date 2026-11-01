# -*- coding: utf-8 -*-
"""像素级比对: 游戏 vs 我们 的对话框丝带与文字位置"""
from PIL import Image

GAME = r"C:\Users\asus\.dsh\attachments\v1\objects\33\336fe9980d5eade8dc47e18f57f987bd529f3efd1b4c300e80dde4a35439ead2"
OURS = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\work\dlg_v5.png"


def load(p):
    return Image.open(p).convert("RGB").resize((1280, 720), Image.LANCZOS)


def cyan_band(im):
    """返回丝带可见带 (top, bottom)"""
    px = im.load()
    rows = []
    for y in range(400, 720):
        n = sum(1 for x in range(200, 1100, 6)
                if px[x, y][2] > 120 and px[x, y][2] > px[x, y][0] + 30)
        rows.append((y, n))
    ys = [y for y, n in rows if n > 30]
    return (min(ys), max(ys)) if ys else None


def text_boxes(im, y0, y1):
    """在给定纵向区间内找白色文字块, 返回 [(x0,y0,x1,y1), ...]"""
    px = im.load()
    pts = []
    for y in range(y0, y1):
        for x in range(120, 900):
            r, g, b = px[x, y]
            if r > 205 and g > 205 and b > 205 and max(r, g, b) - min(r, g, b) < 45:
                pts.append((x, y))
    if not pts:
        return []
    # 按行聚类
    ys = sorted(set(y for _, y in pts))
    groups, cur = [], [ys[0]]
    for y in ys[1:]:
        if y - cur[-1] <= 6:
            cur.append(y)
        else:
            groups.append(cur)
            cur = [y]
    groups.append(cur)
    out = []
    for g in groups:
        sel = [(x, y) for x, y in pts if y in g]
        out.append((min(x for x, _ in sel), min(g), max(x for x, _ in sel), max(g)))
    return out


for name, path in (("游戏", GAME), ("我们", OURS)):
    im = load(path)
    band = cyan_band(im)
    print("=== %s ===" % name)
    print("  丝带可见带 y: %s" % (band,))
    if band:
        boxes = text_boxes(im, max(0, band[0] - 30), min(719, band[1]))
        for i, b in enumerate(boxes[:3]):
            print("  文字块%d: x %d..%d  y %d..%d" % (i + 1, b[0], b[2], b[1], b[3]))
