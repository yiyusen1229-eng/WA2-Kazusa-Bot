# -*- coding: utf-8 -*-
"""把游戏原始 TGA/BMP 转成 PNG, 并生成联系表(contact sheet)方便识别"""
import os
import sys
from PIL import Image

SRC = r"E:\IDM下载目录\解包\cg\cg"
OUT = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\ui2\assets\ui"
WORK = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\work"


def convert(names):
    os.makedirs(OUT, exist_ok=True)
    done = []
    for n in names:
        src = os.path.join(SRC, n)
        if not os.path.exists(src):
            print("缺少", n)
            continue
        try:
            im = Image.open(src).convert("RGBA")
            dst = os.path.join(OUT, os.path.splitext(n)[0].lower() + ".png")
            im.save(dst)
            done.append((n, im.size, dst))
        except Exception as e:
            print("失败", n, e)
    return done


def sheet(names, out_name, cols=4, cell=260):
    tiles = []
    for n in names:
        src = os.path.join(SRC, n)
        if not os.path.exists(src):
            continue
        im = Image.open(src).convert("RGBA")
        bg = Image.new("RGBA", im.size, (10, 30, 48, 255))
        bg.alpha_composite(im)
        im = bg.convert("RGB")
        im.thumbnail((cell, cell))
        tiles.append((n, im))
    if not tiles:
        return
    from PIL import ImageDraw, ImageFont
    rows = (len(tiles) + cols - 1) // cols
    W = cols * (cell + 8) + 8
    H = rows * (cell + 26) + 8
    out = Image.new("RGB", (W, H), (18, 22, 28))
    d = ImageDraw.Draw(out)
    f = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 12)
    for i, (n, im) in enumerate(tiles):
        r, c = divmod(i, cols)
        x = 8 + c * (cell + 8)
        y = 8 + r * (cell + 26)
        out.paste(im, (x, y + 16))
        d.text((x, y), n, fill=(180, 230, 255), font=f)
    p = os.path.join(WORK, out_name)
    out.save(p)
    print("联系表:", p, out.size)


if __name__ == "__main__":
    group = sys.argv[1] if len(sys.argv) > 1 else "sys"
    files = sorted(f for f in os.listdir(SRC) if f.lower().startswith(group))
    convert(files)
    sheet(files[:24], "sheet_%s.png" % group, cols=4, cell=300)
