# -*- coding: utf-8 -*-
"""游戏字幕 vs 补丁配方渲染, 同倍放大对照"""
import os

from PIL import Image, ImageDraw, ImageFont

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
SHOT = os.path.join(BASE, "work", "剧情实测", "02_第10句.png")
TXT = "终于，还是下起来了。"
FS, ST = 28, 2
OCC = FS + 2 * ST

g = Image.open(SHOT).convert("RGB")
crop = g.crop((330, 660, 712, 704))
crop3 = crop.resize((crop.width * 3, crop.height * 3), Image.LANCZOS)
crop3.save(os.path.join(BASE, "work", "游戏字幕行3x.png"))
print("游戏字幕:", crop.size, "->", crop3.size)

lib = Image.new("RGBA", (OCC * len(TXT), OCC), (0, 0, 0, 0))
d = ImageDraw.Draw(lib)
f = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", FS)
for i, ch in enumerate(TXT):
    d.text((ST + OCC * i, ST - 2), ch, "white", f, stroke_width=ST, stroke_fill="black")
bg = Image.new("RGBA", lib.size, (30, 80, 120, 255))
bg.alpha_composite(lib)
ref = bg.convert("RGB")
ref3 = ref.resize((ref.width * 3, ref.height * 3), Image.LANCZOS)
ref3.save(os.path.join(BASE, "work", "配方渲染3x.png"))
print("配方渲染:", ref.size, "->", ref3.size)
