# -*- coding: utf-8 -*-
"""验证: 游戏字模图是否按 JIS(Shift-JIS) 顺序排列

方法: 取几个 JIS 编码确定的汉字(亜/阿/哀/愛), 用日文字体渲染后
在图集里找最像的格子, 看格子坐标是否符合 JIS 行/列。
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
DIR = os.path.join(BASE, r"game_pak\font_pak")

ATLASES = {
    "80px本体(明朝)": ("杮懱80.tga", r"C:\Windows\Fonts\msmincho.ttc"),
    "80px袋(黑体)": ("戃塭80.tga", r"C:\Windows\Fonts\msgothic.ttc"),
}
TESTS = ["亜", "阿", "哀", "愛", "悪"]

for label, (fname, jpfont) in ATLASES.items():
    p = os.path.join(DIR, fname)
    if not os.path.exists(p):
        print("缺文件:", p)
        continue
    im = Image.open(p).convert("RGBA")
    alpha = np.array(im.split()[3]) > 110
    H, W = alpha.shape
    print("=== %s  %dx%d ===" % (label, W, H))
    # 推断格子尺寸: 试 32/40/48, 看哪种能让格子边界落在空白列上
    for cell in (32, 40, 48, 64):
        if W % cell or H % cell:
            continue
        cols, rows = W // cell, H // cell
        # 统计每格是否有内容
        filled = 0
        for r in range(rows):
            for c in range(cols):
                if alpha[r * cell:(r + 1) * cell, c * cell:(c + 1) * cell].sum() > 20:
                    filled += 1
        print("  格子 %2d -> %d x %d = %5d 格, 有内容 %5d" % (cell, cols, rows, cols * rows, filled))
    print("  (下一步用 %s 逐字定位)" % os.path.basename(jpfont))
