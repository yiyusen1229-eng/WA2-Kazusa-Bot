# -*- coding: utf-8 -*-
"""把「选择分支」要用的原版素材转成 PNG（本地素材，不入库）。

来源：`other/dev/game_pak/gh/gcn_unpack/`（游戏解包目录）
  · sys_00200.tga（784×216）→ res/assets/ui/choice/bar.png
      三段竖排：常态 / 悬停高亮 / 按下。**中间是透明的**，蓝色渐变由 choice.css 铺。
  · 数字：不需要重新烤，直接复用 res/assets/ui/save/d1..d9.png（来自 sys_00019 图集）
  · 两端雪花：复用 res/assets/snowflake_right.png
  · 小标签：sys_00011 是菜单图集（Q.SAVE / ON·OFF / No Data），里面没有单独的标签图，
      所以标签由 choice.css 用 CSS 画（白牌 + 小孔 + 轻微旋转）

用法：
    python program/tools/make_choice_assets.py
"""
import os

from PIL import Image

PROG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GCN = os.path.join(os.path.dirname(PROG), "other", "dev", "game_pak", "gh", "gcn_unpack")
OUT = os.path.join(PROG, "res", "assets", "ui", "choice")

SRC = os.path.join(GCN, "sys_00200.tga")


def main():
    os.makedirs(OUT, exist_ok=True)
    im = Image.open(SRC).convert("RGBA")
    dst = os.path.join(OUT, "bar.png")
    im.save(dst)
    print("%s %s -> %s（%d 字节）" % (os.path.basename(SRC), im.size, dst, os.path.getsize(dst)))
    print("提示：三段竖排（每段 %d px）；中间的蓝色渐变在 choice.css 里铺，不要只贴这张图。"
          % (im.size[1] // 3))


if __name__ == "__main__":
    main()
