# -*- coding: utf-8 -*-
"""选择分支的素材：从原版两张图里切出来（本地素材，不入库）。

源文件：`other/dev/game_pak/gh/gcn_unpack/`
  · sys_00200.tga（784×216）—— 选项条贴图，竖排三段，**每段 784×72**：
        段1 = 常态（顶部高光 + 条身 + 两端渐隐）
        段2 = 悬停高亮（同位置、更亮更实）
        段3 = 只有两端雪花（叠在段1/段2 上面的一层）
  · sys_00011.tga（408×288）—— 菜单图集，里面有一块**小白牌**（带蓝色别针，
        实测 alpha 盒 x 219..236 / y 64..96 = 18×33）

产物（`program/res/assets/ui/choice/`）：
  bar_off.png   段1  784×72
  bar_on.png    段2  784×72
  snow.png      段3  784×72（两端雪花，和条子同一个 784×72 画布）
  tag.png       小白牌 18×33（按 alpha 裁到最小）

为什么不再拆 snow_l / snow_r：
  段3 和条子是同尺寸同原点的画布，整张叠上去，雪花的位置就是原版位置，
  不用自己算端头偏移（上一版拆开单独摆，位置只能靠估）。

用法：
    python program/tools/make_choice_assets.py
"""
import os

from PIL import Image

PROG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GCN = os.path.join(os.path.dirname(PROG), "other", "dev", "game_pak", "gh", "gcn_unpack")
OUT = os.path.join(PROG, "res", "assets", "ui", "choice")

# 图集里小白牌的 alpha 盒（手工定位后写死；改素材才需要动）
TAG_BOX = (219, 64, 237, 97)


def _save(im, name):
    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, name)
    im.save(dst)
    print("%-12s %-9s -> %s" % (name, "%dx%d" % im.size, dst))


def main():
    bar = Image.open(os.path.join(GCN, "sys_00200.tga")).convert("RGBA")
    w, h = bar.size
    seg = h // 3
    for i, name in enumerate(("bar_off.png", "bar_on.png", "snow.png")):
        _save(bar.crop((0, seg * i, w, seg * (i + 1))), name)

    atlas = Image.open(os.path.join(GCN, "sys_00011.tga")).convert("RGBA")
    tag = atlas.crop(TAG_BOX)
    bbox = tag.split()[3].getbbox()
    if bbox:
        tag = tag.crop(bbox)
    _save(tag, "tag.png")

    # 上一版留下的拆件：雪花已经并进 snow.png，删掉免得下次又有人用
    for old in ("snow_l.png", "snow_r.png"):
        p = os.path.join(OUT, old)
        if os.path.exists(p):
            os.remove(p)
            print("删掉旧拆件 %s" % p)


if __name__ == "__main__":
    main()
