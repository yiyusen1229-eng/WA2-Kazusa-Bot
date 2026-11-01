# -*- coding: utf-8 -*-
"""把游戏那一行和候选字体做「红绿叠加」, 形状差异一眼可见"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

GAME = r"C:\Users\asus\.dsh\attachments\v1\objects\a5\a5db8fdca460689fc0a7bfea2f5860e369eb8ab77025b2b3ece6cfd0084cfbec"
BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
TEXT = "然的话，这次我可是真的要"

CANDS = [
    ("微软雅黑 Bold", r"C:\Windows\Fonts\msyhbd.ttc"),
    ("微软雅黑", r"C:\Windows\Fonts\msyh.ttc"),
    ("Droid", os.path.join(BASE, r"app\assets\DroidSansFallback.ttf")),
    ("SimHei", r"C:\Windows\Fonts\simhei.ttf"),
]

img = Image.open(GAME).convert("RGB")
crop = img.crop((0, 60, 795, 175))          # 第一行文字
a = np.array(crop).astype(np.int16)
mx = a.max(axis=2)
mn = a.min(axis=2)
white = ((mx > 190) & ((mx - mn) < 50)).astype(np.uint8)

ys, xs = np.where(white)
y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
ref = white[y0:y1, x0:x1]
print("游戏字行:", ref.shape, " 墨迹", int(ref.sum()))

TW = 1000
def fit(mask):
    im = Image.fromarray((mask * 255).astype(np.uint8))
    h = max(1, int(im.height * TW / im.width))
    return np.array(im.resize((TW, h), Image.LANCZOS)) > 100

ref_f = fit(ref)
print("归一后:", ref_f.shape)


def render(path, size=64):
    im = Image.new("L", (2000, 140), 0)
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(path, size)
    d.text((10, 10), TEXT, font=f, fill=255)
    m = np.array(im) > 100
    ys, xs = np.where(m)
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


outs = []
for name, path in CANDS:
    if not os.path.exists(path):
        continue
    cand = fit(render(path))
    h = min(ref_f.shape[0], cand.shape[0])
    r = ref_f[:h]
    c = cand[:h]
    w = min(r.shape[1], c.shape[1])
    rgb = np.zeros((h, w, 3), np.uint8)
    rgb[:, :, 0] = r[:, :w] * 255     # 红 = 游戏
    rgb[:, :, 1] = c[:, :w] * 255     # 绿 = 候选
    im = Image.fromarray(rgb)
    canvas = Image.new("RGB", (TW + 310, max(h, 120) + 30), (10, 14, 20))
    d2 = ImageDraw.Draw(canvas)
    d2.text((8, 4), name, fill=(255, 255, 255),
            font=ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 22))
    canvas.paste(im, (150, 20))
    outs.append(canvas)

total_h = sum(c.height + 8 for c in outs)
sheet = Image.new("RGB", (TW + 310, total_h + 10), (10, 14, 20))
y = 5
for c in outs:
    sheet.paste(c, (0, y))
    y += c.height + 8
sheet.save(os.path.join(BASE, r"work\字体叠加对比.png"))
print("已生成 字体叠加对比.png  红=游戏 绿=候选 黄=重合")
