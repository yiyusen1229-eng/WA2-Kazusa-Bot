# -*- coding: utf-8 -*-
"""把选项条 / 小标签的原始素材转成 PNG，并放大预览数字图集（看清楚格子）。"""
import os

from PIL import Image

PROG = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\program"
GCN = os.path.join(os.path.dirname(PROG), "other", "dev", "game_pak", "gh", "gcn_unpack")
OUT = os.path.join(PROG, "res", "assets", "ui", "choice")
os.makedirs(OUT, exist_ok=True)

pairs = [
    ("sys_00011.tga", "tag.png"),
    ("sys_00200.tga", "bar.png"),
]
for src, dst in pairs:
    p = os.path.join(GCN, src)
    im = Image.open(p).convert("RGBA")
    im.save(os.path.join(OUT, dst))
    print("%-16s %s -> %s" % (src, im.size, dst))

# 数字图集：放大看清楚有哪些格子
atlas = Image.open(os.path.join(GCN, "sys_00019.tga")).convert("RGBA")
print("sys_00019:", atlas.size)
big = atlas.resize((atlas.size[0] * 4, atlas.size[1] * 4), Image.NEAREST)
big.save(os.path.join(PROG, "work_scratch", "atlas_00019.png"))
digits = Image.open(os.path.join(PROG, "res", "assets", "ui", "save", "digits.png")).convert("RGBA")
d_big = digits.resize((digits.size[0] * 8, digits.size[1] * 8), Image.NEAREST)
d_big.save(os.path.join(PROG, "work_scratch", "digits_x8.png"))
print("digits.png:", digits.size)
