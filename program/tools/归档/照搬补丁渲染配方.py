# -*- coding: utf-8 -*-
"""把我们的文字渲染改成与补丁 sub_compiler.py 完全相同的配方

补丁的做法(Python/PIL):
    font = ImageFont.truetype(ttf, 28)
    draw.text((2, 0), 字, 'white', font, stroke_width=2, stroke_fill='black')
即: 白色填充 + 2px 黑色描边, 无模糊、无提纯、无 MaxFilter 膨胀。

我们按显示尺寸等比放大: 字号 48 -> 描边 48*2/28 ≈ 3.4 -> 3
"""
import re

P = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\app\gdi_text.py"
s = open(P, encoding="utf-8").read()

# 1) 参数: 字体/字号/描边
s = re.sub(r'_FONT_FILE = r"[^"]*"', '_FONT_FILE = r"C:/Windows/Fonts/msyhbd.ttc"', s, count=1)
s = re.sub(r"^SIZE = \d+", "SIZE = 48", s, count=1, flags=re.M)
s = re.sub(r"^OUTLINE_W = \d+", "OUTLINE_W = 3", s, count=1, flags=re.M)
s = re.sub(r"^BODY_BLUR = [\d.]+", "BODY_BLUR = 0.0", s, count=1, flags=re.M)
s = re.sub(r"^EDGE_BLUR = [\d.]+", "EDGE_BLUR = 0.0", s, count=1, flags=re.M)
s = re.sub(r"^WHITE_BOOST = [\d.]+", "WHITE_BOOST = 0.0", s, count=1, flags=re.M)

# 2) 绘制改为一笔带描边的 draw.text（和补丁一样）
old = '''        dr = ImageDraw.Draw(base)
        for i, ln in enumerate(lines):
            y = pad + outline_w + i * line_pitch
            x = pad + outline_w
            for fp, seg in split_runs(ln):
                f_seg = _pil_font(size, fp)
                for ex in range(embolden + 1):
                    for ey in range(embolden + 1):
                        dr.text((x + ex, y + ey), seg, font=f_seg,
                                fill=(color[0], color[1], color[2], 255))
                if f_seg is not None:
                    x += f_seg.getlength(seg)'''

new = '''        dr = ImageDraw.Draw(base)
        sw = max(0, int(round(size * 2.0 / 28.0)))   # 与补丁同比例: 28px 配 2px 描边
        for i, ln in enumerate(lines):
            y = pad + outline_w + i * line_pitch
            x = pad + outline_w
            for fp, seg in split_runs(ln):
                f_seg = _pil_font(size, fp)
                dr.text((x, y), seg, font=f_seg,
                        fill=(color[0], color[1], color[2], 255),
                        stroke_width=sw, stroke_fill=(0, 0, 0, 255))
                if f_seg is not None:
                    x += f_seg.getlength(seg)'''

if old in s:
    s = s.replace(old, new, 1)
    print("绘制方式已改为「白字+黑描边」")
else:
    print("!! 未匹配绘制段, 需要人工改")

# 3) 去掉后处理里的描边/模糊/提纯(补丁没这些)
s = s.replace("    if outline_w > 0:", "    if False and outline_w > 0:", 1)
s = s.replace("    if BODY_BLUR:", "    if False and BODY_BLUR:", 1)
s = s.replace("    if WHITE_BOOST > 0:", "    if False and WHITE_BOOST > 0:", 1)

open(P, "w", encoding="utf-8").write(s)

import ast
ast.parse(s)
print("语法 OK")
