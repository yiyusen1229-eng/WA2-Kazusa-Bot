# -*- coding: utf-8 -*-
"""清理所有历史字体规则, 只保留一处统一定义

删掉:
  game450.css / screens.css 里的
    @font-face DroidSansFallback
    html, body, input, button... { font-family: DroidSansFallback }
    #msgText, #namePlate { font-family: MS Gothic }

保留:
  html, body 上的基础字体
  以及 unifont.css 里唯一的全程序规则
"""
import re

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\ui2"

BLOCK_DROID = re.compile(
    r"/\*\s*=+\s*统一使用汉化版字体 Droid Sans Fallback\s*=+\s*\*/\s*"
    r"@font-face\s*\{[^}]*\}\s*"
    r"html,\s*body,\s*input,\s*button,\s*textarea,\s*canvas,\s*div,\s*span,\s*b,\s*small,\s*em\s*\{[^}]*\}\s*",
    re.S)

BLOCK_MSG = re.compile(
    r"/\*\s*=+\s*对话文字字体[^*]*\*/\s*"
    r"#msgText,\s*#namePlate\s*\{[^}]*\}\s*",
    re.S)

for fn in ("game450.css", "screens.css"):
    p = BASE + "\\" + fn
    s = open(p, encoding="utf-8").read()
    n0 = len(s)
    s2 = BLOCK_DROID.sub("", s)
    removed_droid = (len(s) - len(s2)) > 0
    s = s2
    if fn == "game450.css":
        s2 = BLOCK_MSG.sub("", s)
        removed_msg = (len(s) - len(s2)) > 0
        s = s2
    else:
        removed_msg = False
    open(p, "w", encoding="utf-8").write(s)
    print("%-14s 删掉 Droid 规则: %s" % (fn, "是" if removed_droid else "无"))
    if fn == "game450.css":
        print("%-14s 删掉 MS Gothic 规则: %s" % ("", "是" if removed_msg else "无"))

# 检查还有没有残留
for fn in ("game450.css", "screens.css"):
    p = BASE + "\\" + fn
    s = open(p, encoding="utf-8").read()
    bad = []
    for kw in ("DroidSansFallback", "MS Gothic", "MS PGothic"):
        if kw in s:
            bad.append(kw)
    print("%-14s 残留: %s" % (fn, bad if bad else "无"))
