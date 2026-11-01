# -*- coding: utf-8 -*-
"""严格对比: 游戏实际字幕 vs 用补丁配方渲染的同一条字幕

1. 从游戏截图里裁出字幕行
2. 用 sub_compiler.py 的配方(28px + stroke 2)渲染同一句话
3. 两者归一化到相同字高, 并排 + 叠加
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
SHOT = os.path.join(BASE, r"work\剧情实测\02_第10句.png")
TXT = "终于，还是下起来了。"
FS, ST, OCC, PER = 28, 2, 32, 20


def patch_render(text, font_path, size=FS, stroke=ST):
    occ = size + 2 * stroke
    lib = Image.new("RGBA", (occ * len(text), occ), (0, 0, 0, 0))
    d = ImageDraw.Draw(lib)
    f = ImageFont.truetype(font_path, size)
    for i, ch in enumerate(text):
        d.text((stroke + occ * i, stroke - 2), ch, "white", f,
               stroke_width=stroke, stroke_fill="black")
    return lib


# 1) 游戏截图里的字幕行
g = Image.open(SHOT).convert("RGB")
a = np.array(g).astype(np.int16)
mx, mn = a.max(2), a.min(2)
m = (mx > 205) & ((mx - mn) < 45)
m[:int(g.height * 0.72)] = False
ys, xs = np.where(m)
gcrop = g.crop((xs.min() - 8, ys.min() - 8, xs.max() + 9, ys.max() + 9))
print("游戏字幕行:", gcrop.size)

# 2) 补丁配方渲染
ref = patch_render(TXT, r"C:\Windows\Fonts\msyhbd.ttc")
print("补丁配方渲染:", ref.size)

# 3) 归一到同一高度后比较笔画
def to_height(im, h=80):
    return im.resize((int(im.width * h / im.height), h), Image.LANCZOS)


g2 = to_height(gcrop)
r2 = to_height(ref.convert("RGB"))
print("归一后 游戏 %s / 渲染 %s" % (g2.size, r2.size))

W = max(g2.width, r2.width) + 12
sheet = Image.new("RGB", (W, 80 * 2 + 40), (10, 14, 20))
sheet.paste(g2, (6, 6))
sheet.paste(r2, (6, 100))
sheet.save(os.path.join(BASE, "work", "严格对比.png"))

# 4) 笔画粗细量化: 白芯像素占比
def white_ratio(im):
    a = np.array(im.convert("RGB")).astype(np.int16)
    mx, mn = a.max(2), a.min(2)
    w = (mx > 225) & ((mx - mn) < 30)
    ys, xs = np.where(w)
    if len(ys) == 0:
        return 0
    box = (ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1)
    return w.sum() / box

print("白芯密度  游戏 %.4f   渲染 %.4f" % (white_ratio(g2), white_ratio(r2)))
print("已存 严格对比.png")
