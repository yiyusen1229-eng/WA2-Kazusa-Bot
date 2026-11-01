# -*- coding: utf-8 -*-
"""把游戏对话那一行和各候选字体渲染的同一句并排放, 直接看字形"""
import os

from PIL import Image, ImageDraw, ImageFont

GAME = r"C:\Users\asus\.dsh\attachments\v1\objects\a5\a5db8fdca460689fc0a7bfea2f5860e369eb8ab77025b2b3ece6cfd0084cfbec"
BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
TEXT = "求求你，撤回前言吧…"

CANDS = [
    ("微软雅黑 Bold", r"C:\Windows\Fonts\msyhbd.ttc"),
    ("微软雅黑", r"C:\Windows\Fonts\msyh.ttc"),
    ("Droid Sans Fallback", os.path.join(BASE, r"app\assets\DroidSansFallback.ttf")),
    ("SimHei 黑体", r"C:\Windows\Fonts\simhei.ttf"),
    ("等线 DengXian", r"C:\Windows\Fonts\Deng.ttf"),
]

img = Image.open(GAME).convert("RGB")
# 第二行文字大概在 y 190..245, 横向 60..700 (原图 795x340)
crop = img.crop((55, 186, 720, 248))
scale = 2
crop = crop.resize((crop.width * scale, crop.height * scale), Image.LANCZOS)

ROWH = 100
out = Image.new("RGB", (crop.width + 20, ROWH * (len(CANDS) + 2)), (16, 30, 44))
d = ImageDraw.Draw(out)
f_label = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 20)

y = 8
d.text((10, y), "游戏原图", fill=(120, 255, 160), font=f_label)
y += 26
out.paste(crop, (10, y))
y += crop.height + 10

for name, path in CANDS:
    if not os.path.exists(path):
        continue
    d.text((10, y), name, fill=(255, 220, 120), font=f_label)
    y += 26
    # 渲染到和游戏字差不多高(游戏字高约 40px * 2 = 80)
    tile = Image.new("RGB", (crop.width, ROWH - 30), (16, 30, 44))
    td = ImageDraw.Draw(tile)
    font = ImageFont.truetype(path, 64)
    td.text((20, 0), TEXT, font=font, fill=(255, 255, 255))
    out.paste(tile, (10, y))
    y += ROWH - 30

out.save(os.path.join(BASE, r"work\字体并排对比.png"))
print("已生成 字体并排对比.png  尺寸", out.size)
