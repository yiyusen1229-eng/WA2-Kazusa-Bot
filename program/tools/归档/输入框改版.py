# -*- coding: utf-8 -*-
"""输入框改版: 直接用 sys_00110 原图(480x112), 不裁切不拼接
位置移到右侧空白区, 尺寸放大到接近原生
"""
import os
import re
import time

from PIL import Image

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"

# 1) 素材直接当输入框
src = Image.open(r"E:\IDM下载目录\解包\cg\cg\sys_00110.tga").convert("RGBA")
src.save(os.path.join(BASE, r"ui2\assets\input_frame.png"))
print("input_frame.png = sys_00110 原图", src.size)

# 2) CSS 定位
css = '''

/* ===== 输入框第十一版: 原图直用, 移到右下 ===== */
#inputBar {
  left: 512px !important;
  top: 208px !important;
  bottom: auto !important;
  width: 280px !important;
  height: 65px !important;
  opacity: 1 !important;
  align-items: flex-start !important;
}
#inputFrame { width: 100% !important; height: 100% !important; opacity: .92 !important; }
#input {
  font-size: 11px !important;
  padding: 0 14px 0 26px !important;
  height: 100% !important;
}
#thinkBtn, #sendBtn {
  position: absolute !important;
  bottom: -22px;
  height: 20px !important;
  font-size: 7.6px !important;
  padding: 0 9px !important;
}
#thinkBtn { right: 62px !important; margin: 0 !important; }
#sendBtn  { right: 0 !important; }
'''
cp = os.path.join(BASE, r"ui2\game450.css")
c = open(cp, encoding="utf-8").read()
if "输入框第十一版" not in c:
    open(cp, "a", encoding="utf-8").write(css)
    print("game450.css: 第十一版已加")

hp = os.path.join(BASE, r"ui2\index.html")
h = open(hp, encoding="utf-8").read()
tag = time.strftime("%H%M%S")
h = re.sub(r"(game450\.css)(\?v=[0-9a-z]+)?", lambda m: "%s?v=%s" % (m.group(1), tag), h)
open(hp, "w", encoding="utf-8").write(h)
print("版本:", tag)
