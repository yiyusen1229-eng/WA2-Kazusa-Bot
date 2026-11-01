# -*- coding: utf-8 -*-
"""字体定案: 微软雅黑 Bold

依据: 用 subfont.tga(汉化中文字模图集)第 2 行 20 个字形与候选字体做掩码 IoU 比对
  微软雅黑 Bold   0.596  ← 最像
  SimHei          0.474
  Droid Sans Fallback 0.415
  微软雅黑 Regular 0.386
  宋体            0.300
所以程序里所有文字改成 微软雅黑 Bold。
"""
import os
import re
import time

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"

# ---------- 1. gdi_text: 用系统 msyhbd.ttc ----------
gp = os.path.join(BASE, r"app\gdi_text.py")
s = open(gp, encoding="utf-8").read()

s = re.sub(
    r'_FONT_FILE = os\.path\.join\([^)]*\)',
    lambda m: '_FONT_FILE = r"C:/Windows/Fonts/msyhbd.ttc"',
    s, count=1)
if "_FONT_FILE = r\"C:\\Windows\\Fonts\\msyhbd.ttc\"" not in s:
    s = s.replace(
        '# ---- 字体: 私有加载汉化版用的 Droid Sans Fallback ----',
        '# ---- 字体: 汉化字模由 微软雅黑 Bold 生成(字形 IoU 比对 0.596) ----')
open(gp, "w", encoding="utf-8").write(s)
print("gdi_text.py: 字体文件 -> msyhbd.ttc")

import ast
ast.parse(open(gp, encoding="utf-8").read())

# ---------- 2. CSS ----------
css_add = '''

/* ===== 字体定案: 微软雅黑 Bold(与汉化字模一致) ===== */
html, body, input, button, textarea, div, span, b, small, em, .kv, .lbl, .val {
  font-family: "Microsoft YaHei", "微软雅黑", sans-serif !important;
  font-weight: 700 !important;
}
/* 数值/日志用常规粗细, 避免糊成一团 */
.pvMeta, .log, #log, .pinfo, .axisX, .axisY { font-weight: 400 !important; }
'''
changed = 0
for f in ("game.css", "game450.css", "screens.css"):
    fp = os.path.join(BASE, "ui2", f)
    if not os.path.exists(fp):
        continue
    c = open(fp, encoding="utf-8").read()
    if "字体定案" not in c:
        open(fp, "a", encoding="utf-8").write(css_add)
        changed += 1
print("CSS 已加字体定案:", changed)

hp = os.path.join(BASE, r"ui2\index.html")
h = open(hp, encoding="utf-8").read()
tag = time.strftime("%H%M%S")
h = re.sub(r"(game\.css|game450\.css|screens\.css)(\?v=[0-9a-z]+)?",
           lambda m: "%s?v=%s" % (m.group(1), tag), h)
open(hp, "w", encoding="utf-8").write(h)
print("版本:", tag)

print("msyhbd.ttc 存在:", os.path.exists(r"C:\Windows\Fonts\msyhbd.ttc"))
