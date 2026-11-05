# -*- coding: utf-8 -*-
"""把「选择分支」要用的原版素材转成 PNG（本地素材，不入库）。

来源：`other/dev/game_pak/gh/gcn_unpack/`

| 源 | 产物 | 用法 |
|---|---|---|
| `sys_00200.tga`（784×216） | `ui/choice/bar_top.png`（段1） | 常态：条子顶部那一道高光（CSS 里只取顶部 8px） |
| 同上 | `ui/choice/bar_top_on.png`（段2） | 悬停：换这条更亮的高光 |
| 同上 | `ui/choice/bar_snow.png`（段3） | 两端雪花（原图左右各一朵，中间透明） |
| `sys_00110.tga`（480×112） | `ui/choice/plate.png` | 带雪花暗纹的蓝板（备选纹理，未在 CSS 里启用） |
| `sys_00011.tga`（408×288） | `ui/choice/tag.png` | 菜单图集里那块**小白牌**（约 (218,63)~(236,96)），按亮度 <95 抠掉深蓝底 |

**条身填充不来自贴图**：游戏里是顶点色染的，所以 CSS 用深蓝渐变画底，
上面叠「顶部高光 + 两端雪花」。数字沿用 `ui/save/d1..d9.png`，「.」由 CSS 画。

用法：
    python program/tools/make_choice_assets.py
"""
import os

from PIL import Image

PROG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GCN = os.path.join(os.path.dirname(PROG), "other", "dev", "game_pak", "gh", "gcn_unpack")
OUT = os.path.join(PROG, "res", "assets", "ui", "choice")
TAG_BOX = (210, 55, 246, 100)
TAG_LUM_MIN = 95


def _save(im, name):
    os.makedirs(OUT, exist_ok=True)
    im.save(os.path.join(OUT, name))
    print("%-14s %dx%d" % (name, im.size[0], im.size[1]))


def main():
    bar = Image.open(os.path.join(GCN, "sys_00200.tga")).convert("RGBA")
    w, h = bar.size
    seg = h // 3
    _save(bar.crop((0, 0, w, seg)), "bar_top.png")
    _save(bar.crop((0, seg, w, seg * 2)), "bar_top_on.png")
    _save(bar.crop((0, seg * 2, w, seg * 3)), "bar_snow.png")
    _save(Image.open(os.path.join(GCN, "sys_00110.tga")).convert("RGBA"), "plate.png")

    atlas = Image.open(os.path.join(GCN, "sys_00011.tga")).convert("RGBA")
    tag = atlas.crop(TAG_BOX)
    px = tag.load()
    tw, th = tag.size
    for y in range(th):
        for x in range(tw):
            r, g, b, a = px[x, y]
            if a and (0.299 * r + 0.587 * g + 0.114 * b) < TAG_LUM_MIN:
                px[x, y] = (r, g, b, 0)
    bbox = tag.split()[3].getbbox()
    if bbox:
        tag = tag.crop(bbox)
    _save(tag, "tag.png")


if __name__ == "__main__":
    main()
