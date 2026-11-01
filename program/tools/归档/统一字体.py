# -*- coding: utf-8 -*-
"""统一字体: 全部改成对话框同款「微软雅黑」, 并删除无用的 wa2.ttf

对话框文字是 GDI 用「微软雅黑」渲染的, 所以界面文字统一成同一字体。
wa2.ttf (2.94MB) 只被 html/body 默认字体引用, 换成微软雅黑后即可删除。
"""
import glob
import os
import re
import time

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
FONT = '"Microsoft YaHei", "微软雅黑", "PingFang SC", sans-serif'

changed = 0
for f in glob.glob(os.path.join(BASE, r"ui2\*.css")):
    s = open(f, encoding="utf-8").read()
    orig = s

    # 1) 删掉引用 wa2.ttf 的 @font-face
    s = re.sub(r'@font-face\s*\{[^}]*wa2\.ttf[^}]*\}\s*', "", s)

    # 2) 所有具体字体声明, 统一成微软雅黑(保留 inherit)
    def repl(m):
        v = m.group(1).strip()
        if v == "inherit":
            return m.group(0)
        return "font-family: %s;" % FONT

    s = re.sub(r"font-family\s*:\s*([^;}\n]+);", repl, s)

    if s != orig:
        open(f, "w", encoding="utf-8").write(s)
        changed += 1
        print("已统一字体:", os.path.basename(f))

print("共修改 %d 个 CSS" % changed)

# 3) 删除 wa2.ttf
ttf = os.path.join(BASE, r"ui2\assets\wa2.ttf")
if os.path.exists(ttf):
    os.remove(ttf)
    print("已删除 assets/wa2.ttf (2.94 MB)")

# 4) 版本号
hp = os.path.join(BASE, r"ui2\index.html")
h = open(hp, encoding="utf-8").read()
tag = time.strftime("%H%M%S")
h = re.sub(r"(game\.css|game450\.css|screens\.css)(\?v=[0-9a-z]+)?",
           lambda m: "%s?v=%s" % (m.group(1), tag), h)
open(hp, "w", encoding="utf-8").write(h)
print("版本:", tag)
