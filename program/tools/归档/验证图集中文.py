# -*- coding: utf-8 -*-
"""验证 14pt 图集里是否含简体中文专用字(吧/的/了/是/我/你)

如果汉化补丁替换了图集, 这些字必然存在且能高匹配。
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
DIR = os.path.join(BASE, r"game_pak\font_pak")
CELL = 32
TESTS = "吧的了是我你他这说"

FONTS = {
    "微软雅黑": r"C:\Windows\Fonts\msyh.ttc",
    "微软雅黑B": r"C:\Windows\Fonts\msyhbd.ttc",
    "宋体": r"C:\Windows\Fonts\simsun.ttc",
}


def norm(m):
    ys, xs = np.where(m > 0)
    if len(ys) == 0:
        return None
    crop = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = crop.shape
    s = (CELL - 4) / max(w, h)
    im = Image.fromarray((crop * 255).astype(np.uint8)).resize(
        (max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)
    out = np.zeros((CELL, CELL), np.float32)
    oy, ox = (CELL - im.height) // 2, (CELL - im.width) // 2
    out[oy:oy + im.height, ox:ox + im.width] = np.array(im) / 255.0
    return (out > 0.43).astype(np.float32).ravel()


for atlas_name in ("14pt杮懱.tga", "14pt戃.tga"):
    p = os.path.join(DIR, atlas_name)
    if not os.path.exists(p):
        print("缺:", p)
        continue
    alpha = np.array(Image.open(p).convert("RGBA").split()[3])
    rows, cols = alpha.shape[0] // CELL, alpha.shape[1] // CELL
    print("\n=== %s  %dx%d  -> %d 格 ===" % (atlas_name, alpha.shape[1], alpha.shape[0], rows * cols))
    cells = []
    for k in range(rows * cols):
        r, c = divmod(k, cols)
        m = alpha[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL]
        v = norm((m > 110).astype(np.float32))
        if v is not None:
            cells.append((k, v))
    mat = np.stack([v for _, v in cells])
    ids = [k for k, _ in cells]
    print("  非空 %d 格" % len(cells))
    for fname, fpath in FONTS.items():
        if not os.path.exists(fpath):
            continue
        for size in (28, 30, 32):
            f = ImageFont.truetype(fpath, size)
            res = []
            for ch in TESTS:
                im = Image.new("L", (CELL, CELL), 0)
                d = ImageDraw.Draw(im)
                d.text((0, 0), ch, font=f, fill=255)
                v = norm((np.array(im) > 110).astype(np.float32))
                if v is None:
                    continue
                inter = (mat * v).sum(1)
                union = mat.sum(1) + v.sum() - inter
                iou = inter / np.maximum(union, 1)
                j = int(iou.argmax())
                res.append("%s:%.2f@%d" % (ch, float(iou[j]), ids[j]))
            print("  %-10s %dpx  %s" % (fname, size, "  ".join(res)))
