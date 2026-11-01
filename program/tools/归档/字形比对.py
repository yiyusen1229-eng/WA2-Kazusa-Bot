# -*- coding: utf-8 -*-
"""字形比对: 拿 subfont.tga 的整行字形, 和各候选字体渲染的同一行比 IoU

subfont.tga: 640x1440, 32x32 一格, 20 列 45 行, GB2312 一级汉字顺序
第 2 行 = 世业东丝丢两严个中丰临丹为主丽举久么义之
"""
import os

from PIL import Image, ImageDraw, ImageFont

ATLAS = r"E:\Games\GALGAMES\WHITE ALBUM2\subfont.tga"
BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
LINE = "世业东丝丢两严个中丰临丹为主丽举久么义之"

CANDS = [
    ("微软雅黑", r"C:\Windows\Fonts\msyh.ttc"),
    ("微软雅黑 Bold", r"C:\Windows\Fonts\msyhbd.ttc"),
    ("SimHei 黑体", r"C:\Windows\Fonts\simhei.ttf"),
    ("SimSun 宋体", r"C:\Windows\Fonts\simsun.ttc"),
    ("等线 DengXian", r"C:\Windows\Fonts\Deng.ttf"),
    ("Droid Sans Fallback", os.path.join(BASE, r"app\assets\DroidSansFallback.ttf")),
]

atlas = Image.open(ATLAS).convert("RGBA").split()[3]
ref = atlas.crop((0, 32, 640, 64))
rp = ref.load()


def mask_of(im, th=100):
    return im.point(lambda v: 255 if v > th else 0)


ref_m = mask_of(ref)
ref_p = ref_m.load()


def iou(img):
    p = img.load()
    inter = union = 0
    for y in range(32):
        for x in range(640):
            a = ref_p[x, y] > 128
            b = p[x, y] > 128
            if a and b:
                inter += 1
            if a or b:
                union += 1
    return inter / union if union else 0


rows = []
for name, path in CANDS:
    if not os.path.exists(path):
        continue
    best = (0, None)
    # 字号和基线都要试, 找最优
    for size in (28, 29, 30, 31, 32, 33, 34):
        for dy in (-3, -2, -1, 0, 1, 2, 3):
            img = Image.new("L", (640, 32), 0)
            d = ImageDraw.Draw(img)
            try:
                f = ImageFont.truetype(path, size)
            except Exception:
                break
            for i, ch in enumerate(LINE):
                d.text((i * 32, dy), ch, font=f, fill=255)
            score = iou(mask_of(img))
            if score > best[0]:
                best = (score, (size, dy))
    rows.append((best[0], name, best[1]))
    print("  %-22s IoU %.4f  参数 %s" % (name, best[0], best[1]))

rows.sort(reverse=True)
print("\n排名:")
for s, n, prm in rows:
    print("  %.4f  %-22s %s" % (s, n, prm))
