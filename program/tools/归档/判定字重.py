# -*- coding: utf-8 -*-
"""判定字幕到底用常规体还是粗体: 把候选渲染整行对齐到游戏字幕, 比重叠度"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
SHOT = os.path.join(BASE, "work", "剧情实测", "02_第10句.png")
TXT = "终于，还是下起来了。"
FS, ST = 28, 2
OCC = FS + 2 * ST

CANDS = [
    ("微软雅黑 常规", r"C:\Windows\Fonts\msyh.ttc"),
    ("微软雅黑 Bold", r"C:\Windows\Fonts\msyhbd.ttc"),
    ("微软雅黑 Light", r"C:\Windows\Fonts\msyhl.ttc"),
    ("等线", r"C:\Windows\Fonts\Deng.ttf"),
]

# 游戏字幕行 -> 二值白芯
g = Image.open(SHOT).convert("RGB")
crop = g.crop((330, 660, 712, 704))
a = np.array(crop).astype(np.int16)
mx, mn = a.max(2), a.min(2)
gw = (mx > 225) & ((mx - mn) < 30)
ys, xs = np.where(gw)
gcrop = crop.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
print("游戏字幕白芯外接框:", gcrop.size)


def white_mask(im):
    a = np.array(im.convert("RGB")).astype(np.int16)
    mx, mn = a.max(2), a.min(2)
    return (mx > 225) & ((mx - mn) < 30)


def render_line(path, stroke):
    lib = Image.new("RGBA", (OCC * len(TXT), OCC), (0, 0, 0, 0))
    d = ImageDraw.Draw(lib)
    f = ImageFont.truetype(path, FS)
    for i, ch in enumerate(TXT):
        d.text((stroke + OCC * i, stroke - 2), ch, "white", f,
               stroke_width=stroke, stroke_fill="black")
    bg = Image.new("RGBA", lib.size, (40, 90, 130, 255))
    bg.alpha_composite(lib)
    return bg.convert("RGB")


def to_h(im, h):
    return im.resize((max(1, int(im.width * h / im.height)), h), Image.LANCZOS)


H = gcrop.height
gmask = white_mask(to_h(gcrop, H))
for name, path in CANDS:
    for stroke in (0, 1, 2):
        r = render_line(path, stroke)
        m = white_mask(to_h(r, H))
        w = min(gmask.shape[1], m.shape[1])
        g2 = gmask[:, :w]
        m2 = m[:, :w]
        inter = np.logical_and(g2, m2).sum()
        union = np.logical_or(g2, m2).sum()
        iou = inter / union if union else 0
        # 白芯占比（衡量粗细）
        ratio_g = g2.sum() / max(1, g2.shape[0] * g2.shape[1])
        ratio_r = m2.sum() / max(1, m2.shape[0] * m2.shape[1])
        print("  %-12s 描边%d  IoU %.3f   白芯占比 游戏 %.3f / 渲染 %.3f  (行宽 %d vs %d)"
              % (name, stroke, iou, ratio_g, ratio_r, gmask.shape[1], m.shape[1]))
