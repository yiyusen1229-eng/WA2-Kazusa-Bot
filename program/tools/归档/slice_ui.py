# -*- coding: utf-8 -*-
"""从游戏图集切出 UI 元件(存档槽、按钮、图标)"""
import os
from PIL import Image

SRC = r"E:\IDM下载目录\解包\cg\cg"
OUT = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\ui2\assets\ui"


def save(im, name):
    im.save(os.path.join(OUT, name))
    print("  ->", name, im.size)


def main():
    # 1) 存档槽 2x2 图集
    im = Image.open(os.path.join(SRC, "sys_01010.tga")).convert("RGBA")
    w, h = im.width // 2, im.height // 2
    tiles = {
        "slot_empty.png": (0, 0),   # 空槽(带 No Data 占位)
        "slot_normal.png": (1, 0),  # 有数据的槽(左侧留空)
        "slot_empty_sel.png": (0, 1),
        "slot_sel.png": (1, 1),     # 选中态
    }
    print("存档槽:")
    for name, (c, r) in tiles.items():
        save(im.crop((c * w, r * h, (c + 1) * w, (r + 1) * h)), name)

    # 2) 大圆角面板(详情卡)
    p = os.path.join(SRC, "sys_00100.tga")
    if os.path.exists(p):
        print("面板:")
        save(Image.open(p).convert("RGBA"), "panel.png")

    # 3) 工具栏图标 6列x3行
    p = os.path.join(SRC, "sys_00010.tga")
    if os.path.exists(p):
        ic = Image.open(p).convert("RGBA")
        cw, ch = ic.width // 6, ic.height // 3
        labels = {
            (5, 0): "icon_close.png",
            (2, 0): "icon_gear.png",
            (1, 0): "icon_save.png",
            (3, 0): "icon_load.png",
        }
        print("图标:")
        for (c, r), name in labels.items():
            save(ic.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch)), name)

    # 4) 按钮帧
    p = os.path.join(SRC, "sys_00101.tga")
    if os.path.exists(p):
        b = Image.open(p).convert("RGBA")
        bw, bh = b.width // 2, b.height // 3
        print("按钮:")
        save(b.crop((0, 0, bw, bh)), "btn_normal.png")
        save(b.crop((bw, 0, b.width, bh)), "btn_hover.png")


if __name__ == "__main__":
    main()
