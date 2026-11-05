# -*- coding: utf-8 -*-
"""选择分支的素材：从原版两张图里切出来（本地素材，不入库）。

源文件：`other/dev/game_pak/gh/gcn_unpack/`
  · sys_00200.tga（784×216）—— 选项条贴图，竖排三段：
        段1 = 常态（顶部高光 + 条身 + 两端雪花）
        段2 = 悬停高亮
        段3 = 只剩两端雪花（本工具不用，雪花已含在段1/段2 里）
  · sys_00011.tga（408×288）—— 菜单图集，里面有一块**小白牌**（约 (218,63)~(236,96)）

产物（`program/res/assets/ui/choice/`）：
  bar_off.png   段1（784×72）
  bar_on.png    段2（784×72）
  tag.png       小白牌（抠掉图集深蓝底）

为什么整段用 + CSS 三段拉伸：原版条子 490×22 舞台像素 = 22.3:1，素材 784×72 = 10.9:1，
比例对不上，说明原版是「左右端保持比例、中间拉长」的三段画法（否则雪花会被压扁）。
CSS 用 border-image slice 96 实现。

用法：
    python program/tools/make_choice_assets.py
"""
import os

from PIL import Image

PROG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GCN = os.path.join(os.path.dirname(PROG), "other", "dev", "game_pak", "gh", "gcn_unpack")
OUT = os.path.join(PROG, "res", "assets", "ui", "choice")

TAG_BOX = (212, 58, 242, 98)
TAG_LUM_MIN = 95


def _save(im, name):
    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, name)
    im.save(dst)
    print("%-12s %-9s -> %s" % (name, "%dx%d" % im.size, dst))


def main():
    bar = Image.open(os.path.join(GCN, "sys_00200.tga")).convert("RGBA")
    w, h = bar.size
    seg = h // 3
    _save(bar.crop((0, 0, w, seg)), "bar_off.png")
    _save(bar.crop((0, seg, w, seg * 2)), "bar_on.png")

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
