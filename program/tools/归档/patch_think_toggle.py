# -*- coding: utf-8 -*-
"""加「显示思考」开关
1. main.py: 从回复里抽出 <thinking>, 分别返回 reply / thinking
2. index.html: 输入栏加按钮, 气泡内加思考面板
3. game.js: 保存状态 + 渲染 + 记忆开关
4. game450.css: 样式
"""
import re

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"

# ---------- 1. main.py ----------
mp = BASE + r"\app\main.py"
s = open(mp, encoding="utf-8").read()

if "def split_thinking" not in s:
    s = s.replace(
        "def persona_text():",
        '''def split_thinking(text):
    """把 <thinking>…</thinking> 从回复里拆出来"""
    import re as _re
    m = _re.search(r"<thinking>(.*?)</thinking>", text or "", _re.S)
    if not m:
        return (text or "").strip(), ""
    inner = m.group(1).strip()
    rest = _re.sub(r"<thinking>.*?</thinking>", "", text, flags=_re.S).strip()
    return rest, inner


def persona_text():''',
        1,
    )
    open(mp, "w", encoding="utf-8").write(s)
    print("main.py: 已加 split_thinking")

s = open(mp, encoding="utf-8").read()
# 在返回回复处拆出 thinking
if '"thinking"' not in s:
    s = s.replace(
        '            return self._json(200, {"reply": reply, "model": model})',
        '''            reply_clean, think = split_thinking(reply)
            return self._json(200, {"reply": reply_clean, "thinking": think, "model": model})''',
        1,
    )
    if '"thinking"' not in s:
        # 兜底: 找其它返回形式
        s = re.sub(
            r'return self\._json\(200, \{"reply": ([^}]+?)\}\)',
            r'''_rc, _th = split_thinking(\1)
            return self._json(200, {"reply": _rc, "thinking": _th})''',
            s,
            count=1,
        )
    open(mp, "w", encoding="utf-8").write(s)
    print("main.py: 返回里已拆 thinking")

import ast
ast.parse(open(mp, encoding="utf-8").read())
print("main.py 语法 OK")

# ---------- 2. index.html ----------
ip = BASE + r"\ui2\index.html"
h = open(ip, encoding="utf-8").read()

if "thinkBtn" not in h:
    h = h.replace(
        '<button id="sendBtn">发送</button>',
        '<button id="thinkBtn" title="显示/隐藏 和纱的内心想法">思考：关</button>\n    <button id="sendBtn">发送</button>',
        1,
    )
    h = h.replace(
        '<div id="msgText"></div>',
        '<div id="thinkBox" class="hidden"></div>\n      <div id="msgText"></div>',
        1,
    )
    open(ip, "w", encoding="utf-8").write(h)
    print("index.html: 已加按钮与思考面板")

# ---------- 3. game.js ----------
gp = BASE + r"\ui2\game.js"
g = open(gp, encoding="utf-8").read()

if "wa2_show_think" not in g:
    g = g.replace(
        '  const reply = (d.reply || "").trim();',
        '''  const reply = (d.reply || "").trim();
  window.__lastThinking = (d.thinking || "").trim();
  renderThinking();''',
        1,
    )
    g += '''

/* ---------- 思考显示开关 ---------- */
function thinkOn() {
  return localStorage.getItem("wa2_show_think") === "1";
}

function renderThinking() {
  const box = $("thinkBox");
  const btn = $("thinkBtn");
  const on = thinkOn();
  if (btn) btn.textContent = on ? "思考：开" : "思考：关";
  if (!box) return;
  const t = window.__lastThinking || "";
  if (on && t) {
    box.textContent = "（" + t + "）";
    box.classList.remove("hidden");
  } else {
    box.textContent = "";
    box.classList.add("hidden");
  }
}

document.addEventListener("DOMContentLoaded", function () {
  const btn = $("thinkBtn");
  if (btn) {
    btn.addEventListener("click", function () {
      localStorage.setItem("wa2_show_think", thinkOn() ? "0" : "1");
      renderThinking();
    });
  }
  renderThinking();
});
'''
    open(gp, "w", encoding="utf-8").write(g)
    print("game.js: 已加开关逻辑")

# ---------- 4. CSS ----------
cp = BASE + r"\ui2\game450.css"
c = open(cp, encoding="utf-8").read()
if "thinkBox" not in c:
    c += '''

/* 思考面板 */
#thinkBox {
  position: absolute; left: 13%; right: 9%; top: 6%;
  font-size: 11px; line-height: 1.45; color: #9fd8f5;
  font-style: italic; pointer-events: none;
  text-shadow: 0 1px 2px rgba(0,10,24,.9);
  opacity: .92;
}
#thinkBox.hidden { display: none; }
#thinkBtn {
  font-family: "Microsoft YaHei", sans-serif; font-size: 13px;
  padding: 0 12px; height: 34px; margin-left: 8px;
  color: #eaf7ff; cursor: pointer;
  background: rgba(20,90,140,.75);
  border: 1px solid rgba(150,230,255,.55); border-radius: 3px;
}
#thinkBtn:hover { background: rgba(40,130,190,.85); }
'''
    open(cp, "w", encoding="utf-8").write(c)
    print("game450.css: 已加样式")

print("完成")
