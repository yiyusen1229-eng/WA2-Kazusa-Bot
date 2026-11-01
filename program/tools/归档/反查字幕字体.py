# -*- coding: utf-8 -*-
"""用 sub_compiler.py 的完全相同配方, 反查补丁用的是哪款字体

配方:
  FONT_SIZE=28, stroke_width=2, stroke_fill='black', fill='white'
  绘制位置 (2 + 32*(i%20), 2 + 32*(i//20) - 2)
  画布 640 x (32*行数)
用同样的代码渲染候选字, 与 subfont.tga 的格子比, 正确字体应当几乎完全重合。
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
ATLAS = r"E:\Games\GALGAMES\WHITE ALBUM2\subfont.tga"
FONT_SIZE = 28
FONT_STROKE = 2
OCC = FONT_SIZE + 2 * FONT_STROKE   # 32
PER_LINE = 20

CANDS = [
    ("微软雅黑", r"C:\Windows\Fonts\msyh.ttc"),
    ("微软雅黑 Bold", r"C:\Windows\Fonts\msyhbd.ttc"),
    ("微软雅黑 Light", r"C:\Windows\Fonts\msyhl.ttc"),
    ("黑体 SimHei", r"C:\Windows\Fonts\simhei.ttf"),
    ("宋体 SimSun", r"C:\Windows\Fonts\simsun.ttc"),
    ("等线 DengXian", r"C:\Windows\Fonts\Deng.ttf"),
    ("MS Gothic", r"C:\Windows\Fonts\msgothic.ttc"),
]

atlas = np.array(Image.open(ATLAS).convert("RGBA"))
H, W = atlas.shape[:2]
rows, cols = H // OCC, W // PER_LINE
print("字库 %dx%d -> %d 行 x %d 列 = %d 格" % (W, H, rows, cols, rows * cols))

# 取若干非空格子作为样本
samples = []
for k in range(rows * cols):
    r, c = divmod(k, PER_LINE)
    cell = atlas[r*OCC:(r+1)*OCC, c*OCC:(c+1)*OCC]
    if (cell[:, :, 3] > 60).sum() > 200:
        samples.append((k, cell))
print("有内容的格子:", len(samples))

TEST = "求撤回前言吧和有事"


def render_cell(ch, font_path):
    lib = Image.new("RGBA", (OCC, OCC), (0, 0, 0, 0))
    d = ImageDraw.Draw(lib)
    f = ImageFont.truetype(font_path, FONT_SIZE)
    d.text((FONT_STROKE, FONT_STROKE - 2), ch, "white", f,
           stroke_width=FONT_STROKE, stroke_fill="black")
    return np.array(lib)


for name, path in CANDS:
    if not os.path.exists(path):
        continue
    best_list = []
    for ch in TEST:
        ref = render_cell(ch, path)
        ref_a = ref[:, :, 3] > 60
        best = (0, -1)
        for k, cell in samples:
            a = cell[:, :, 3] > 60
            inter = np.logical_and(ref_a, a).sum()
            union = np.logical_or(ref_a, a).sum()
            iou = inter / union if union else 0
            if iou > best[0]:
                best = (iou, k)
        best_list.append((ch, round(best[0], 3), best[1]))
    avg = np.mean([b[1] for b in best_list])
    print("  %-14s 平均 %.3f   %s" % (name, avg, best_list))
