# -*- coding: utf-8 -*-
"""把 sys_00110 的按钮底板切成三段（左帽 / 中间 / 右帽），给九宫格用。

为什么要烘：原图 480x112，上下有透明留白；直接拿去做 border-image，
四角会带上透明边、中间 fill 又被压得很薄。先裁掉留白、等比缩到目标高度，
左右帽保持原样、只横向拉伸中间段，就不会变形也不会露白。

用法：
    python tools/bake_char_bar.py            # 默认高 30，左右帽各 14
    python tools/bake_char_bar.py --height 34 --cap 16
"""
import argparse
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "res", "assets", "ui", "sys_00110.png")
OUT_DIR = os.path.join(ROOT, "res", "assets", "ui", "text")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--height", type=int, default=30, help="成品高度（px）")
    ap.add_argument("--cap", type=int, default=14, help="左右帽宽度（px）")
    args = ap.parse_args()

    im = Image.open(SRC).convert("RGBA")
    bbox = im.getbbox()          # 去掉四周透明留白
    im = im.crop(bbox)
    w, h = im.size
    nw = max(1, round(w * args.height / h))
    im = im.resize((nw, args.height), Image.LANCZOS)
    cap = min(args.cap, nw // 3)
    left = im.crop((0, 0, cap, args.height))
    right = im.crop((nw - cap, 0, nw, args.height))
    mid = im.crop((cap, 0, nw - cap, args.height))
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, part in (("sp_bar_left.png", left), ("sp_bar_mid.png", mid), ("sp_bar_right.png", right)):
        p = os.path.join(OUT_DIR, name)
        part.save(p)
        print("%-18s %s  %s" % (name, part.size, p))
    print("裁切后原图：%dx%d → 缩放 %dx%d，左右帽 %d px" % (w, h, nw, args.height, cap))


if __name__ == "__main__":
    main()
