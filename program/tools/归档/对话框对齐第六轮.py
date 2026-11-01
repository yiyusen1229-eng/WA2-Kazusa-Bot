# -*- coding: utf-8 -*-
"""对话框第六轮: 按叠加图测得的像素偏差修正
游戏 vs 我们(1280x720 坐标):
  名字  高 35px / 左 70px  → 舞台: 下 22 / 右 44
  正文  高 25px / 左 45px  → 舞台: 下 16 / 右 28
  整框  高 30px            → 舞台: 下移 19
"""
import re
import time

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"

css_add = '''

/* ===== 对话框第六轮: 按像素测量修正 ===== */
#msgWrap {
  bottom: 0px !important;
  height: 154px !important;
  width: 780px !important;
}
/* 名字: 22.5% / 21% */
#namePlate {
  left: 22.5% !important;
  top: 21% !important;
  font-size: 11.5px !important;
}
/* 正文: 26% / 41% */
#msgText {
  left: 26% !important;
  right: 10% !important;
  top: 41% !important;
  font-size: 15.5px !important;
  line-height: 1.5 !important;
}
'''

cp = BASE + r"\ui2\game450.css"
c = open(cp, encoding="utf-8").read()
if "对话框第六轮" not in c:
    open(cp, "a", encoding="utf-8").write(css_add)
    print("game450.css: 第六轮已加")

hp = BASE + r"\ui2\index.html"
h = open(hp, encoding="utf-8").read()
tag = time.strftime("%H%M%S")
h = re.sub(r"(game450\.css)(\?v=[0-9a-z]+)?", lambda m: "%s?v=%s" % (m.group(1), tag), h)
open(hp, "w", encoding="utf-8").write(h)
print("版本:", tag)
