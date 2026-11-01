# -*- coding: utf-8 -*-
"""用你修好的 JPG 补到 sys_07020 原图上(只覆盖中间有字那一块)

JPG 和 TGA 都是 160x120 三帧, 坐标一一对应。
把 JPG 中间干净区域贴回 TGA, 边缘做羽化, 保留 TGA 原来的 alpha 和外框。
"""
import os
import re
import time

from PIL import Image, ImageFilter

JPG = r"C:\Users\asus\.dsh\attachments\v1\objects\44\440f58727a8eb4993f433c0eb2ccd6e4e5197bb26de6d71e2ca9f71e02692bbc"
TGA = r"E:\IDM下载目录\解包\cg\cg\sys_07020.tga"
BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
OUT = os.path.join(BASE, r"ui2\assets\ui\btn_3state.png")

jpg = Image.open(JPG).convert("RGB")
tga = Image.open(TGA).convert("RGBA")
print("JPG:", jpg.size, " TGA:", tga.size)
assert jpg.size == tga.size, "尺寸不一致"

out = tga.copy()
FH = tga.height // 3

# 每帧中间有字的矩形(略大一点, 覆盖干净)
X0, X1 = 40, 120
Y0, Y1 = 5, 35

for i in range(3):
    by = i * FH
    patch = jpg.crop((X0, by + Y0, X1, by + Y1))
    # 羽化蒙版: 边缘 4px 渐变, 避免接缝
    mask = Image.new("L", patch.size, 255)
    md = mask.load()
    w, h = patch.size
    for y in range(h):
        for x in range(w):
            d = min(x, w - 1 - x, y, h - 1 - y)
            md[x, y] = min(255, int(d / 4.0 * 255))
    mask = mask.filter(ImageFilter.GaussianBlur(1.2))
    out.paste(patch, (X0, by + Y0), mask)

out.save(OUT)
print("已生成:", OUT)

css = '''

/* ===== 按钮: 用修好的完整三帧贴图 ===== */
#thinkBtn, #sendBtn {
  background-image: url("assets/ui/btn_3state.png") !important;
  background-size: 100% 300% !important;
  background-repeat: no-repeat !important;
  background-position: 0 0 !important;
  background-color: transparent !important;
  border: 0 !important;
  border-radius: 0 !important;
  appearance: none !important;
  -webkit-appearance: none !important;
  box-shadow: none !important;
  color: #f4fcff !important;
  text-shadow: 0 1px 2px rgba(0,18,36,.95) !important;
  width: 82px !important;
}
#thinkBtn:active, #sendBtn:active { background-position: 0 50% !important; }
#thinkBtn.released, #sendBtn.released { background-position: 0 100% !important; }
'''
cp = os.path.join(BASE, r"ui2\game450.css")
c = open(cp, encoding="utf-8").read()
if "用修好的完整三帧贴图" not in c:
    open(cp, "a", encoding="utf-8").write(css)
    print("game450.css: 完整三帧样式已加")

hp = os.path.join(BASE, r"ui2\index.html")
h = open(hp, encoding="utf-8").read()
tag = time.strftime("%H%M%S")
h = re.sub(r"(game450\.css)(\?v=[0-9a-z]+)?", lambda m: "%s?v=%s" % (m.group(1), tag), h)
open(hp, "w", encoding="utf-8").write(h)
print("版本:", tag)
