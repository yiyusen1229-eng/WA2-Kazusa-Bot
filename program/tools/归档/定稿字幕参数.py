# -*- coding: utf-8 -*-
"""按像素比对结果定稿参数

扫描结论(与游戏截图的统计量对齐: 白芯228 / 描边140 / 暗白比4.11):
    描边宽度 3, 高斯模糊 0.8, 描边色 (60,60,60)  -> 误差最小
    -> 描边不再是死黑, 整体也保留游戏那种柔化后的"旧"感

同时在上下各留 4px 空白, 彻底避免截断。
"""
import re

P = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\app\sub_render.py"
s = open(P, encoding="utf-8").read()

# 参数区
s = s.replace("FONT_STROKE = 2", "FONT_STROKE = 3", 1)
s = s.replace('FONT_PATH = r"C:/Windows/Fonts/msyh.ttc"',
              'FONT_PATH = r"C:/Windows/Fonts/msyh.ttc"\n'
              'STROKE_COLOR = (60, 60, 60, 255)   # 不用纯黑, 实测游戏描边亮度约 140\n'
              'BLUR = 0.8                          # 模拟 D3D9 双线性放大的柔化\n'
              'PAD_V = 4                           # 上下留白', 1)

# 描边颜色
s = s.replace('stroke_width=FONT_STROKE, stroke_fill="black")',
              'stroke_width=FONT_STROKE, stroke_fill=STROKE_COLOR)', 1)

# 画布高度: 32 + 8
s = s.replace("    h = FONT_OCCUPATION + pad * 2\n",
              "    h = FONT_OCCUPATION + PAD_V * 2\n", 1)
# 贴图 y 偏移: 让字形上下都留 4px
s = s.replace("        canvas.alpha_composite(tile, (x - 4, -2))",
              "        canvas.alpha_composite(tile, (x - 4, PAD_V - 4))", 1)

# 行高
s = s.replace("    line_h = FONT_OCCUPATION + 4",
              "    line_h = FONT_OCCUPATION + PAD_V * 2", 1)

# 模糊值用常量
s = s.replace("out = out.filter(ImageFilter.GaussianBlur(0.5))",
              "out = out.filter(ImageFilter.GaussianBlur(BLUR))", 1)

open(P, "w", encoding="utf-8").write(s)

import ast
ast.parse(s)
print("已写入定稿参数")
for line in s.split("\n"):
    if any(line.startswith(k) for k in ("FONT_SIZE", "FONT_STROKE", "STROKE_COLOR", "BLUR", "PAD_V", "FONT_PATH")):
        print("   ", line)
