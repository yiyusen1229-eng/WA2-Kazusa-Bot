# -*- coding: utf-8 -*-
"""按钮改用「边框贴图 + 透明内部」: 彻底避开中间去字, 不会有模糊块

做法:
  sys_07020 三帧, 只保留外圈边框(含雪花边缘), 把中间内部区域 alpha 清零,
  再用 CSS border-image 画边框, 内部用半透明纯色填充。
"""
import os
import re
import time

from PIL import Image

SRC = r"E:\IDM下载目录\解包\cg\cg\sys_07020.tga"
BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
OUT = os.path.join(BASE, r"ui2\assets\ui\btn_frame.png")

im = Image.open(SRC).convert("RGBA")
W, H = im.size
FH = H // 3
canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))

# 内部清空范围(留出边框宽度)
IX0, IX1 = 16, W - 16
IY0, IY1 = 7, FH - 7

for i in range(3):
    fr = im.crop((0, i * FH, W, (i + 1) * FH)).copy()
    px = fr.load()
    for y in range(IY0, IY1):
        for x in range(IX0, IX1):
            r, g, b, a = px[x, y]
            px[x, y] = (r, g, b, 0)
    canvas.alpha_composite(fr, (0, i * FH))

canvas.save(OUT)
print("已生成边框贴图:", OUT, canvas.size)

css = '''

/* ===== 按钮: 边框贴图 + 透明内部(无模糊块) ===== */
#thinkBtn, #sendBtn {
  background-image: url("assets/ui/btn_frame.png") !important;
  background-size: 100% 300% !important;
  background-repeat: no-repeat !important;
  background-position: 0 0 !important;
  background-color: rgba(26,104,146,.55) !important;
  border: 0 !important;
  border-radius: 0 !important;
  appearance: none !important;
  -webkit-appearance: none !important;
  box-shadow: none !important;
  color: #f2fbff !important;
  text-shadow: 0 1px 2px rgba(0,18,36,.95) !important;
  width: 82px !important;
}
#thinkBtn:active, #sendBtn:active { background-position: 0 50% !important; }
#thinkBtn.released, #sendBtn.released { background-position: 0 100% !important; }
'''
cp = os.path.join(BASE, r"ui2\game450.css")
c = open(cp, encoding="utf-8").read()
if "边框贴图 + 透明内部" not in c:
    open(cp, "a", encoding="utf-8").write(css)
    print("game450.css: 边框贴图样式已加")

hp = os.path.join(BASE, r"ui2\index.html")
h = open(hp, encoding="utf-8").read()
tag = time.strftime("%H%M%S")
h = re.sub(r"(game450\.css)(\?v=[0-9a-z]+)?", lambda m: "%s?v=%s" % (m.group(1), tag), h)
open(hp, "w", encoding="utf-8").write(h)
print("版本:", tag)
