# -*- coding: utf-8 -*-
"""三态按钮: 重新去字(按行取两侧均色, 保留纵向渐变), 并修按钮间距"""
import os
import re
import time

from PIL import Image

SRC = r"E:\IDM下载目录\解包\cg\cg\sys_07020.tga"
BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
OUT = os.path.join(BASE, r"ui2\assets\ui\btn_3state.png")

im = Image.open(SRC).convert("RGBA")
W, H = im.size
FH = H // 3
canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

BX0, BX1 = 46, 114      # 文字所在横向范围
for i in range(3):
    fr = im.crop((0, i * FH, W, (i + 1) * FH)).copy()
    px = fr.load()
    for y in range(6, FH - 6):
        # 取左右两侧(无字)做均色
        samp = []
        for x in list(range(20, BX0 - 6)) + list(range(BX1 + 6, W - 20)):
            r, g, b, a = px[x, y]
            if a > 60:
                samp.append((r, g, b, a))
        if not samp:
            continue
        ar = sum(s[0] for s in samp) // len(samp)
        ag = sum(s[1] for s in samp) // len(samp)
        ab = sum(s[2] for s in samp) // len(samp)
        aa = sum(s[3] for s in samp) // len(samp)
        for x in range(BX0, BX1 + 1):
            px[x, y] = (ar, ag, ab, aa)
    canvas.alpha_composite(fr, (0, i * FH))

canvas.save(OUT)
print("已重新去字:", OUT)

# --- 按钮间距 + 去掉原生样式 ---
css = '''

/* ===== 按钮: 分开间距, 去掉原生外观 ===== */
#thinkBtn, #sendBtn {
  appearance: none !important;
  -webkit-appearance: none !important;
  background-color: transparent !important;
  border: 0 !important;
  outline: 0 !important;
  width: 82px !important;
}
#thinkBtn { right: 94px !important; }
#sendBtn  { right: 0 !important; }
'''
cp = os.path.join(BASE, r"ui2\game450.css")
c = open(cp, encoding="utf-8").read()
if "按钮: 分开间距" not in c:
    open(cp, "a", encoding="utf-8").write(css)
    print("game450.css: 间距与外观已修")

hp = os.path.join(BASE, r"ui2\index.html")
h = open(hp, encoding="utf-8").read()
tag = time.strftime("%H%M%S")
h = re.sub(r"(game450\.css)(\?v=[0-9a-z]+)?", lambda m: "%s?v=%s" % (m.group(1), tag), h)
open(hp, "w", encoding="utf-8").write(h)
print("版本:", tag)
