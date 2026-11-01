# -*- coding: utf-8 -*-
"""对话框第五轮: 去掉遮罩迷雾, 改用加法混合(screen)
sys_00001 的暗部是纯黑, 加法混合下自然不显示 -> 不会出现矩形硬边, 也不会糊一团雾
"""
import re
import time

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"

css_add = '''

/* ===== 对话框第五轮: 加法混合, 不要遮罩 ===== */
#msgBox::before {
  -webkit-mask-image: none !important;
  mask-image: none !important;
  mix-blend-mode: screen !important;
  opacity: .9 !important;
  background: url("assets/ui/msgbox_fill.png") 0 0 / 100% 100% no-repeat !important;
}
/* 丝带层也用 screen, 让亮线叠加而不是盖住 */
#msgBox {
  background-image: url("assets/ui/msgbox_ribbon.png") !important;
  background-blend-mode: screen !important;
}
'''

cp = BASE + r"\ui2\game450.css"
c = open(cp, encoding="utf-8").read()
if "对话框第五轮" not in c:
    open(cp, "a", encoding="utf-8").write(css_add)
    print("game450.css: 第五轮(加法混合)已加")

hp = BASE + r"\ui2\index.html"
h = open(hp, encoding="utf-8").read()
tag = time.strftime("%H%M%S")
h = re.sub(r"(game450\.css)(\?v=[0-9a-z]+)?", lambda m: "%s?v=%s" % (m.group(1), tag), h)
open(hp, "w", encoding="utf-8").write(h)
print("版本:", tag)
