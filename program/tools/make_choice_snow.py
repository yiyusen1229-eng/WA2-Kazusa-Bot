# -*- coding: utf-8 -*-
"""再从 sys_00200 段3 里切出左右两朵雪花（原图两端各一朵，中间透明）。

产物：snow_l.png / snow_r.png（各自裁到 alpha 包围盒，保持原始比例）
"""
import os

from PIL import Image

PROG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GCN = os.path.join(os.path.dirname(PROG), "other", "dev", "game_pak", "gh", "gcn_unpack")
OUT = os.path.join(PROG, "res", "assets", "ui", "choice")


def alpha_box(im):
    b = im.split()[3].getbbox()
    return im.crop(b) if b else im


def main():
    bar = Image.open(os.path.join(GCN, "sys_00200.tga")).convert("RGBA")
    w, h = bar.size
    seg = h // 3
    snow = bar.crop((0, seg * 2, w, seg * 3))
    mid = w // 2
    left = alpha_box(snow.crop((0, 0, mid, seg)))
    right = alpha_box(snow.crop((mid, 0, w, seg)))
    left.save(os.path.join(OUT, "snow_l.png"))
    right.save(os.path.join(OUT, "snow_r.png"))
    print("snow_l.png %dx%d / snow_r.png %dx%d" %
          (left.size[0], left.size[1], right.size[0], right.size[1]))


if __name__ == "__main__":
    main()
