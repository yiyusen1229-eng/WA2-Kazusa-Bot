# -*- coding: utf-8 -*-
"""对话框第十轮: 消除纵向拉伸
素材 1248x208 (比例 6.0)。之前渲染成 780x154 舞台px = 1248x246 屏幕px,
纵向被拉长 1.185 倍 —— 雪花的形状就是这么变形的。
改为 780x130 (1248x208), 完全按素材原始比例。
名字/正文的百分比按新旧高度比 (154/130) 换算, 保持绝对位置不变。
"""
import re
import time

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"

css_add = '''

/* ===== 对话框第十轮: 按素材原始比例, 消除纵向拉伸 ===== */
#msgWrap {
  width: 780px !important;
  height: 130px !important;   /* 780 * 208/1248 = 130, 与素材 1:1 */
  bottom: 0px !important;
}
/* 绝对位置保持不变: 154/130 = 1.185 */
#namePlate {
  left: 21% !important;
  top: 11.4% !important;
  font-size: 11.5px !important;
}
#msgText {
  left: 26% !important;
  right: 10% !important;
  top: 36.5% !important;
  font-size: 15.5px !important;
  line-height: 1.5 !important;
}
'''

cp = BASE + r"\ui2\game450.css"
c = open(cp, encoding="utf-8").read()
if "对话框第十轮" not in c:
    open(cp, "a", encoding="utf-8").write(css_add)
    print("game450.css: 第十轮(去拉伸)已加")

hp = BASE + r"\ui2\index.html"
h = open(hp, encoding="utf-8").read()
tag = time.strftime("%H%M%S")
h = re.sub(r"(game450\.css)(\?v=[0-9a-z]+)?", lambda m: "%s?v=%s" % (m.group(1), tag), h)
open(hp, "w", encoding="utf-8").write(h)
print("版本:", tag)
