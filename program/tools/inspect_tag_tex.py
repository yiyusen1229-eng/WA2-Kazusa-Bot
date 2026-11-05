# -*- coding: utf-8 -*-
"""从 sys_00110.tga 里把「小白牌」标签抠出来（选项条左边那个）。

sys_00110 是 480x112 的一小条 UI 图（截图里红圈圈出的就是它）。
先原图放大 + 标尺网格，人工定好格子再裁；裁完存 ui/choice/tag.png。
"""
import os

from PIL import Image

PROG = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\program"
SRC = os.path.join(os.path.dirname(PROG), "other", "dev", "game_pak", "gh", "gcn_unpack",
                   "sys_00110.tga")
OUT = os.path.join(PROG, "work_scratch", "sys_00110_x8.png")

im = Image.open(SRC).convert("RGBA")
bg = Image.new("RGBA", im.size, (24, 24, 24, 255))
bg.alpha_composite(im)
big = bg.convert("RGB").resize((im.size[0] * 8, im.size[1] * 8), Image.NEAREST)

# 画 10px（原图）一格的红色网格，方便读坐标
px = big.load()
step = 10 * 8
for x in range(0, big.size[0], step):
    for y in range(big.size[1]):
        px[x, y] = (255, 60, 60)
for y in range(0, big.size[1], step):
    for x in range(big.size[0]):
        px[x, y] = (255, 60, 60)

big.save(OUT)
print("预览:", OUT, big.size)
