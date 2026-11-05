# -*- coding: utf-8 -*-
"""把「选择分支」要用的原版素材转成 PNG（本地素材，不入库）。

来源：`other/dev/game_pak/gh/gcn_unpack/`

| 源 | 产物 | 说明 |
|---|---|---|
| `sys_00200.tga`（784×216） | `ui/choice/bar.png` | 竖排三段：常态 / 悬停高亮 / 按下；条身中间透明，蓝色渐变由 CSS 铺 |
| `sys_00110.tga`（480×112） | `ui/choice/plate.png` | 带雪花暗纹的蓝板，叠在渐变之上做纹理 |
| `sys_00011.tga`（408×288） | `ui/choice/tag.png` | 菜单图集里那块**小白牌**（截图红圈处，约 (218,63)~(236,96)），按亮度抠掉深蓝底 |

数字沿用 `ui/save/d1..d9.png`（sys_00019 图集烤的），「.」由 CSS 画；两端雪花用 `snowflake_right.png`。

用法：
    python program/tools/make_choice_assets.py
"""
import os

from PIL import Image

PROG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GCN = os.path.join(os.path.dirname(PROG), "other", "dev", "game_pak", "gh", "gcn_unpack")
OUT = os.path.join(PROG, "res", "assets", "ui", "choice")

TAG_BOX = (210, 55, 246, 100)      # 小白牌在图集里的位置（留余量，后面按 alpha 收紧）
TAG_LUM_MIN = 95                   # 低于这个亮度当背景抠掉（图集那块是深蓝）


def _save(im, name):
    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, name)
    im.save(dst)
    print("%-10s %-10s -> %s" % (name, "%dx%d" % im.size, os.path.basename(dst)))


def main():
    _save(Image.open(os.path.join(GCN, "sys_00200.tga")).convert("RGBA"), "bar.png")
    _save(Image.open(os.path.join(GCN, "sys_00110.tga")).convert("RGBA"), "plate.png")

    atlas = Image.open(os.path.join(GCN, "sys_00011.tga")).convert("RGBA")
    tag = atlas.crop(TAG_BOX)
    px = tag.load()
    w, h = tag.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a and (0.299 * r + 0.587 * g + 0.114 * b) < TAG_LUM_MIN:
                px[x, y] = (r, g, b, 0)
    bbox = tag.split()[3].getbbox()
    if bbox:
        tag = tag.crop(bbox)
    _save(tag, "tag.png")


if __name__ == "__main__":
    main()
