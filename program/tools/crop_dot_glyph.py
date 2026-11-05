# -*- coding: utf-8 -*-
"""路由用的小图处理：从 sys_00019 图集裁出「.」字形（选项条要用「1.」「2.」）。

图集是 140x16 一排，14 格 x 10px：0-9 / / : . 以及一个空位。
已有 d0~d9.png、dt_slash.png、dt_colon.png 在 ui/save/ 下，这里只补 dot.png。
先按格子裁，按「不透明像素的包围盒」判断哪一格是点。
"""
import os

from PIL import Image

PROG = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\program"
ATLAS = os.path.join(os.path.dirname(PROG), "other", "dev", "game_pak", "gh", "gcn_unpack",
                     "sys_00019.tga")
OUT_DIRS = [os.path.join(PROG, "res", "assets", "ui", "save"),
            os.path.join(PROG, "res", "assets", "ui", "choice")]

CELL = 10
atlas = Image.open(ATLAS).convert("RGBA")
w, h = atlas.size
n = w // CELL
print("图集 %dx%d，%d 格" % (w, h, n))
for i in range(n):
    cell = atlas.crop((i * CELL, 0, (i + 1) * CELL, h))
    a = cell.split()[3]
    box = a.getbbox()
    px = sum(1 for v in a.getdata() if v > 40)
    print("  格%2d bbox=%s 不透明像素=%d" % (i, box, px))
