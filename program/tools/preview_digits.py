# -*- coding: utf-8 -*-
"""把数字图集垫黑底放大，看清格子（原图是半透明白字，直接看几乎看不见）。"""
import os

from PIL import Image

PROG = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\program"


def preview(src, dst, scale=8, bg=(0, 0, 0, 255)):
    im = Image.open(src).convert("RGBA")
    canvas = Image.new("RGBA", im.size, bg)
    canvas.alpha_composite(im)
    rgb = canvas.convert("RGB")
    # 拉伸对比度，白字在黑底上更清楚
    rgb = rgb.point(lambda v: min(255, int(v * 1.6)))
    big = rgb.resize((im.size[0] * scale, im.size[1] * scale), Image.NEAREST)
    big.save(dst)
    print("%s %s -> %s %s" % (os.path.basename(src), im.size, os.path.basename(dst), big.size))


preview(os.path.join(PROG, "res", "assets", "ui", "save", "digits.png"),
        os.path.join(PROG, "work_scratch", "digits_black.png"))
preview(os.path.join(os.path.dirname(PROG), "other", "dev", "game_pak", "gh", "gcn_unpack",
                     "sys_00019.tga"),
        os.path.join(PROG, "work_scratch", "atlas_black.png"), scale=6)
