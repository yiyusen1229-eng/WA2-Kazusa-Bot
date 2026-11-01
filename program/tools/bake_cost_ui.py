# -*- coding: utf-8 -*-
"""烤「花费」那一栏的字模：固定文案 + 0~9 单字。

为什么不走 /api/text：
    字模渲染器是给中文设计的固定网格（每个字 28px 步进），
    拉丁字母和数字会被撑得很开（token 变成 t o k e n）。
    这里改用 PIL 直接排版 —— 一个词一次画完，字符间距是字体自己的度量。

做法：
    所有小图都画在**同高画布**上、共用同一条基线，只横向裁掉空白。
    这样前端把每张都设成同一个高度，字就是对得齐的。

用法：
    python tools/bake_cost_ui.py
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "res", "assets", "ui", "text")

FONT_PATH = r"C:/Windows/Fonts/msyh.ttc"
SIZE = 28
STROKE = 2
CANVAS_H = 40          # 统一高度（含上伸部/下伸部），前端按同一高度显示
BASELINE = 30
PAD = 4
FILL = (255, 255, 255, 255)
STROKE_COLOR = (0, 0, 0, 255)

ITEMS = {
    "cost_now":   "本条对话",
    "cost_cum":   "累计",
    "cost_token": "token",
    "cost_spend": "花费",
    "cost_sep":   "·",
    "cost_yen":   "¥",
    "cost_dot":   ".",
}
for _d in range(10):
    ITEMS["cost_d%d" % _d] = str(_d)


def bake(text, font):
    canvas = Image.new("RGBA", (900, CANVAS_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    # anchor="ls"：左下角 = 基线左下，保证所有小图共用一条基线
    d.text((PAD, BASELINE), text, font=font, fill=FILL,
           stroke_width=STROKE, stroke_fill=STROKE_COLOR, anchor="ls")
    bb = canvas.split()[3].getbbox()
    if not bb:
        return canvas
    # 只横向裁紧，纵向保留整块画布（对齐用）
    left = max(0, bb[0] - 1)
    right = min(canvas.width, bb[2] + 1)
    return canvas.crop((left, 0, right, CANVAS_H))


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not os.path.exists(FONT_PATH):
        print("找不到字体:", FONT_PATH)
        return 1
    font = ImageFont.truetype(FONT_PATH, SIZE)
    os.makedirs(OUT, exist_ok=True)
    for key, text in ITEMS.items():
        img = bake(text, font)
        img.save(os.path.join(OUT, key + ".png"))
        print("%-12s %-8r %dx%d" % (key, text, img.width, img.height))
    print("\n共 %d 张 → %s" % (len(ITEMS), OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
