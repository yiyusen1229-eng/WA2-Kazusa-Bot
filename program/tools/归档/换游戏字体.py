# -*- coding: utf-8 -*-
"""换成汉化补丁用的字体 Droid Sans Fallback

依据:
  游戏的 fnt.pak / fon.pak 解出来是 4 张位图字模图集(14pt/80px, 明朝/黑体),
  里面没有 TTF —— 游戏本身用位图字模绘制日文。
  汉化补丁目录里的 default.ttf 是 Droid Sans Fallback, 中文就是用它渲染的。
  所以程序里所有文字改用这个字体, 与汉化版观感一致。

做三件事:
  1. 字体文件放进 app\assets 并打进 exe
  2. GDI 渲染(对话框正文)改用这个字体, 私有加载不污染系统
  3. CSS 加 @font-face, 所有界面文字用它
"""
import os
import re
import shutil
import time

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
SRC_TTF = r"E:\IDM下载目录\解包\ziti\default (1).ttf"
DST_TTF = os.path.join(BASE, r"app\assets\DroidSansFallback.ttf")

os.makedirs(os.path.dirname(DST_TTF), exist_ok=True)
shutil.copy2(SRC_TTF, DST_TTF)
print("字体已复制:", DST_TTF, "%.2f MB" % (os.path.getsize(DST_TTF) / 1048576))

# 同时放到 ui2/assets 供网页 @font-face 用
ui_ttf = os.path.join(BASE, r"ui2\assets\DroidSansFallback.ttf")
shutil.copy2(SRC_TTF, ui_ttf)
print("网页字体:", ui_ttf)

# ---------- 1. GDI ----------
gp = os.path.join(BASE, r"app\gdi_text.py")
s = open(gp, encoding="utf-8").read()

if "AddFontResourceExW" not in s:
    s = s.replace(
        '# ---- 可调参数 ----\nFACE = "微软雅黑"',
        '''# ---- 字体: 私有加载汉化版用的 Droid Sans Fallback ----
FR_PRIVATE = 0x10
_FONT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "assets", "DroidSansFallback.ttf")
FACE = "微软雅黑"
try:
    if os.path.exists(_FONT_FILE):
        if gdi32.AddFontResourceExW(ctypes.c_wchar_p(_FONT_FILE), FR_PRIVATE, 0):
            FACE = "Droid Sans Fallback"
except Exception:
    pass

# ---- 可调参数 ----''',
        1,
    )
    # RENDER_VER 递增, 让旧缓存失效
    m = re.search(r"RENDER_VER\s*=\s*(\d+)", s)
    if m:
        s = s.replace(m.group(0), "RENDER_VER = %d" % (int(m.group(1)) + 1))
    open(gp, "w", encoding="utf-8").write(s)
    print("gdi_text.py: 已改用 Droid Sans Fallback")

import ast
ast.parse(open(gp, encoding="utf-8").read())
print("gdi_text.py 语法 OK")

# ---------- 2. CSS ----------
css_add = '''

/* ===== 统一使用汉化版字体 Droid Sans Fallback ===== */
@font-face {
  font-family: "DroidSansFallback";
  src: url("assets/DroidSansFallback.ttf") format("truetype");
  font-display: swap;
}
html, body, input, button, textarea, canvas, div, span, b, small, em {
  font-family: "DroidSansFallback", "Droid Sans Fallback", "Microsoft YaHei", sans-serif !important;
}
'''
changed = 0
for f in ("game.css", "game450.css", "screens.css"):
    fp = os.path.join(BASE, "ui2", f)
    if not os.path.exists(fp):
        continue
    c = open(fp, encoding="utf-8").read()
    if "DroidSansFallback" not in c:
        open(fp, "a", encoding="utf-8").write(css_add)
        changed += 1
print("CSS 已加 @font-face:", changed, "个文件")

hp = os.path.join(BASE, r"ui2\index.html")
h = open(hp, encoding="utf-8").read()
tag = time.strftime("%H%M%S")
h = re.sub(r"(game\.css|game450\.css|screens\.css)(\?v=[0-9a-z]+)?",
           lambda m: "%s?v=%s" % (m.group(1), tag), h)
open(hp, "w", encoding="utf-8").write(h)
print("版本:", tag)
