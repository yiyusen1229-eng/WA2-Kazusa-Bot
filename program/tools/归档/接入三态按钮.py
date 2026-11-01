# -*- coding: utf-8 -*-
"""思考/发送 按钮换成 sys_07020 三态皮肤
常态 = 第1帧, 按下 = 第2帧, 松开一瞬 = 第3帧
"""
import os
import re
import time

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"

css = '''

/* ===== 按钮三态皮肤 (sys_07020) ===== */
#thinkBtn, #sendBtn {
  background-image: url("assets/ui/btn_3state.png") !important;
  background-size: 100% 300% !important;
  background-repeat: no-repeat !important;
  background-position: 0 0 !important;
  border: none !important;
  border-radius: 0 !important;
  background-color: transparent !important;
  color: #eaf7ff !important;
  text-shadow: 0 1px 2px rgba(0,15,30,.9) !important;
  width: 66px !important;
}
#thinkBtn:active, #sendBtn:active {
  background-position: 0 33.333% !important;
}
#thinkBtn.released, #sendBtn.released {
  background-position: 0 66.666% !important;
}
'''
cp = os.path.join(BASE, r"ui2\game450.css")
c = open(cp, encoding="utf-8").read()
if "按钮三态皮肤" not in c:
    open(cp, "a", encoding="utf-8").write(css)
    print("game450.css: 三态按钮样式已加")

# JS: 松开时闪现第三帧
jp = os.path.join(BASE, r"ui2\game.js")
j = open(jp, encoding="utf-8").read()
if "released" not in j:
    j += '''

/* ---------- 按钮三态: 松开时闪现第三帧 ---------- */
document.addEventListener("DOMContentLoaded", function () {
  ["thinkBtn", "sendBtn"].forEach(function (id) {
    const b = document.getElementById(id);
    if (!b) return;
    b.addEventListener("pointerup", function () {
      b.classList.add("released");
      setTimeout(function () { b.classList.remove("released"); }, 130);
    });
  });
});
'''
    open(jp, "w", encoding="utf-8").write(j)
    print("game.js: 松开状态已加")

hp = os.path.join(BASE, r"ui2\index.html")
h = open(hp, encoding="utf-8").read()
tag = time.strftime("%H%M%S")
h = re.sub(r"(game450\.css|game\.js)(\?v=[0-9a-z]+)?", lambda m: "%s?v=%s" % (m.group(1), tag), h)
open(hp, "w", encoding="utf-8").write(h)
print("版本:", tag)
