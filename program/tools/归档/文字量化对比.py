# -*- coding: utf-8 -*-
"""量化对比: 游戏文字 vs 我们的文字

分别统计:
  1. 白色填充占比 (白芯像素 / 字形外接框面积)
  2. 描边占比     (暗色边缘像素 / 外接框面积)
  3. 平均笔画宽度 (对白芯做距离变换取平均, 或用 面积/周长 估算)
"""
import sys

import numpy as np
from PIL import Image

GAME = r"C:\Users\asus\.dsh\attachments\v1\objects\a5\a5db8fdca460689fc0a7bfea2f5860e369eb8ab77025b2b3ece6cfd0084cfbec"
OURS_VEC = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\work\字体三方对比.png"


def analyze(im, label, thresh_white=205, thresh_dark=110):
    a = np.array(im.convert("RGB")).astype(np.int16)
    mx = a.max(axis=2)
    mn = a.min(axis=2)
    white = (mx > thresh_white) & ((mx - mn) < 40)     # 近白且低饱和
    # 描边: 明显比周围暗且低饱和
    dark = (mx < thresh_dark) & ((mx - mn) < 60)
    ys, xs = np.where(white)
    if len(ys) == 0:
        print("  %s: 没找到白色文字" % label)
        return
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    box = (y1 - y0) * (x1 - x0)
    wcount = white[y0:y1, x0:x1].sum()
    dcount = dark[y0:y1, x0:x1].sum()
    # 平均笔画宽度估算: 白芯面积 / (白芯周长/2)
    from scipy import ndimage
    lab, n = ndimage.label(white[y0:y1, x0:x1])
    if n == 0:
        return
    sizes = ndimage.sum(white[y0:y1, x0:x1], lab, range(1, n + 1))
    big = sizes > 30
    # 形态学腐蚀, 看几轮后消失 -> 半宽
    m = white[y0:y1, x0:x1]
    half = 0
    cur = m.copy()
    while cur.any() and half < 20:
        cur = ndimage.binary_erosion(cur)
        half += 1
    print("  %-8s 外接框 %4dx%-4d  白芯占比 %5.1f%%  暗边占比 %5.1f%%  最大笔画半宽 %d"
          % (label, x1 - x0, y1 - y0, 100.0 * wcount / box, 100.0 * dcount / box, half))


print("=== 游戏原图 ===")
analyze(Image.open(GAME), "游戏")

print("=== 我们的对比图里两行 ===")
im = Image.open(OURS_VEC).convert("RGB")
h = im.height
# 三行: 游戏/矢量/位图, 大概各占 1/3
analyze(im.crop((0, int(h * 0.33), im.width, int(h * 0.66))), "矢量")
analyze(im.crop((0, int(h * 0.66), im.width, h)), "位图")
