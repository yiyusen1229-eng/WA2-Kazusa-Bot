# -*- coding: utf-8 -*-
"""对话框对齐游戏原图(第三轮)
- 尺寸改回素材原始比例 1248:208 -> 780x130, 消除纵向拉伸
- 名字/正文右移到游戏里的位置
- 提亮、加饱和, 贴近游戏观感
"""
import re
import time

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"

css_add = '''

/* ===== 对话框对齐游戏原图 (第三轮) ===== */
#msgWrap {
  left: 50% !important; right: auto !important;
  transform: translateX(-50%) !important;
  width: 780px !important;
  height: 130px !important;
  bottom: 34px !important;
  padding: 0 !important;
}
#msgBox {
  opacity: 1 !important;
  filter: brightness(1.12) saturate(1.15) contrast(1.03) !important;
}
#namePlate {
  left: 17% !important; top: 6% !important;
  font-size: 11.5px !important;
}
#msgText {
  left: 19% !important; right: 12% !important;
  top: 30% !important;
  font-size: 15.5px !important;
  line-height: 1.5 !important;
}
'''

cp = BASE + r"\ui2\game450.css"
c = open(cp, encoding="utf-8").read()
if "对话框对齐游戏原图 (第三轮)" not in c:
    open(cp, "a", encoding="utf-8").write(css_add)
    print("game450.css: 已加第三轮对齐样式")

hp = BASE + r"\ui2\index.html"
h = open(hp, encoding="utf-8").read()
tag = time.strftime("%H%M%S")
h = re.sub(r"(game450\.css)(\?v=[0-9a-z]+)?", lambda m: "%s?v=%s" % (m.group(1), tag), h)
open(hp, "w", encoding="utf-8").write(h)
print("index.html 版本:", tag)
