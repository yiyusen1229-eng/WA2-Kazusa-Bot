# -*- coding: utf-8 -*-
"""对话框第四轮: 用游戏原图 + 遮罩消除硬边, 尺寸对齐实测"""
import re
import time

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"

css_add = '''

/* ===== 对话框第四轮: 位置/尺寸按游戏实测, 填充层加柔和遮罩 ===== */
#msgWrap {
  left: 50% !important; right: auto !important;
  transform: translateX(-50%) !important;
  width: 780px !important;
  height: 154px !important;
  bottom: 19px !important;
  padding: 0 !important;
}
/* 只保留丝带层做背景 */
#msgBox {
  background-image: url("assets/ui/msgbox_ribbon.png") !important;
  background-size: 100% 100% !important;
  background-repeat: no-repeat !important;
  filter: none !important;
  opacity: 1 !important;
}
/* 填充层(渐变+水印)放成伪元素, 用椭圆遮罩消掉矩形硬边 */
#msgBox::before {
  content: "";
  position: absolute; inset: 0;
  background: url("assets/ui/msgbox_fill.png") 0 0 / 100% 100% no-repeat;
  -webkit-mask-image: radial-gradient(ellipse 62% 78% at 50% 52%, #000 62%, transparent 88%);
  mask-image: radial-gradient(ellipse 62% 78% at 50% 52%, #000 62%, transparent 88%);
  pointer-events: none;
  z-index: 0;
}
#namePlate, #msgText { z-index: 1; }
/* 名字/正文位置 */
#namePlate {
  left: 17% !important; top: 8% !important;
  font-size: 11.5px !important;
}
#msgText {
  left: 19% !important; right: 12% !important;
  top: 32% !important;
  font-size: 15.5px !important;
  line-height: 1.5 !important;
}
'''

cp = BASE + r"\ui2\game450.css"
c = open(cp, encoding="utf-8").read()
if "对话框第四轮" not in c:
    open(cp, "a", encoding="utf-8").write(css_add)
    print("game450.css: 第四轮样式已加")

hp = BASE + r"\ui2\index.html"
h = open(hp, encoding="utf-8").read()
tag = time.strftime("%H%M%S")
h = re.sub(r"(game450\.css)(\?v=[0-9a-z]+)?", lambda m: "%s?v=%s" % (m.group(1), tag), h)
open(hp, "w", encoding="utf-8").write(h)
print("版本:", tag)
