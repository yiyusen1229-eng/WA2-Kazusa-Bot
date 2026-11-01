# -*- coding: utf-8 -*-
"""特别模式用图：把竖版滚动条精灵转成横向滑条。

sys_00030.png 是解包出来的滚动条精灵（96x640），三列各有用途：
    第 1 列 x 3..28   常态轨道
    第 2 列 x 35..60  悬停态轨道（更亮的描边）
    第 3 列 x 65..92  亮色按钮 + 滑块（pill）
每列纵向：y 0..47 上箭头按钮 / 50..589 轨道 / 592..639 下箭头按钮。

设置界面的百分比滑条是横着放的，所以这里把「轨道」「滑块」各转 90°，
存成独立 PNG 给 CSS 用（素材不在仓库里，换机器要重跑这个脚本）。

用法：
    python tools/make_special_ui.py
"""
import os
import sys

from PIL import Image, ImageDraw

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "res", "assets", "ui", "sys_00030.png")
OUT = os.path.join(BASE, "res", "assets", "ui", "special")

# (名字, 左, 上, 右, 下) —— 右下不含
SLICES = [
    ("slider_track",      3,  50, 29, 590),
    ("slider_track_hover", 35, 50, 61, 590),
]

# 滑块：原素材是一条长药丸（86x28），按用户要求做成小圆角方块。
# 颜色直接从药丸上取，保证和轨道是同一套配色。
KNOB_SRC = (65, 49, 93, 135)
KNOB_SIZE = 19
KNOB_RADIUS = 4


def _make_knob(pill):
    color = pill.getpixel((pill.width // 3, pill.height // 2))
    edge = (min(255, color[0] + 50), min(255, color[1] + 50), min(255, color[2] + 50), 255)
    im = Image.new("RGBA", (KNOB_SIZE, KNOB_SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, KNOB_SIZE - 1, KNOB_SIZE - 1],
                        radius=KNOB_RADIUS, fill=color, outline=edge, width=1)
    return im

# 恢复默认设置的按钮：sys_03030.png 是 208x72（3 帧 x 24 高），
# 左边写着 "DEFAULT"，只要右边的按钮本体（x 66..208），三帧原样保留。
RESET_SRC = os.path.join(BASE, "res", "assets", "ui", "sys_03030.png")
RESET_CROP = (66, 0, 208, 72)


def main():
    if not os.path.exists(SRC):
        sys.exit("找不到 %s（先用 tools/check_assets.py 确认素材）" % SRC)
    im = Image.open(SRC).convert("RGBA")
    os.makedirs(OUT, exist_ok=True)
    for name, l, t, r, b in SLICES:
        piece = im.crop((l, t, r, b)).rotate(90, expand=True)
        path = os.path.join(OUT, name + ".png")
        piece.save(path)
        print("%-20s %dx%d -> %s" % (name, piece.width, piece.height, path))

    knob = _make_knob(im.crop(KNOB_SRC).rotate(90, expand=True))
    path = os.path.join(OUT, "slider_knob.png")
    knob.save(path)
    print("%-20s %dx%d -> %s" % ("slider_knob", knob.width, knob.height, path))

    if os.path.exists(RESET_SRC):
        btn = Image.open(RESET_SRC).convert("RGBA").crop(RESET_CROP)
        path = os.path.join(OUT, "reset_btn.png")
        btn.save(path)
        print("%-20s %dx%d -> %s" % ("reset_btn", btn.width, btn.height, path))
    else:
        print("跳过 reset_btn：找不到 %s" % RESET_SRC)


if __name__ == "__main__":
    main()
