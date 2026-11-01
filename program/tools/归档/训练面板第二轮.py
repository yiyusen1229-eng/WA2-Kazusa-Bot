# -*- coding: utf-8 -*-
"""训练面板第二轮修正
1. 左栏两块拉伸到底, 与右栏底部对齐
2. 图表加高 + 坐标轴标注加粗放大
3. 开始/继续/训练中 按钮状态机
4. 后端补充 can_resume 字段
"""
import json
import os
import re

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"

# ---------------- 1. main.py: can_resume ----------------
mp = BASE + r"\app\main.py"
s = open(mp, encoding="utf-8").read()

if '"can_resume"' not in s:
    # 在 train_status 组装 ckpts 之后补字段
    m = re.search(r"(    ckpts = \[\]\n    if os\.path\.isdir\(out\):\n(?:.*\n)*?)(    info\[)", s)
    if m:
        ins = '''    info["can_resume"] = len(ckpts) > 0
    info["last_ckpt"] = max((c[0] for c in ckpts), default=0)
'''
        s = s[:m.end(1)] + ins + s[m.end(1):]
        open(mp, "w", encoding="utf-8").write(s)
        print("main.py: 已加 can_resume / last_ckpt")
    else:
        print("main.py: 未匹配到 ckpts 段, 跳过")
import ast
ast.parse(open(mp, encoding="utf-8").read())

# ---------------- 2. CSS ----------------
cp = BASE + r"\ui2\screens.css"
c = open(cp, encoding="utf-8").read()
if "/* 第二轮修正 */" not in c:
    c += '''

/* 第二轮修正 */
/* 左栏两块等高拉伸, 底部与右栏对齐 */
.trCol.left { justify-content: stretch; }
.trCol.left .trCard { flex: 1 1 0 !important; min-height: 0; overflow: hidden; }
/* 图表加高, 填满卡片 */
.chartBox { flex: 1 1 auto; min-height: 190px; display: flex; flex-direction: column; }
.chartBox canvas { flex: 1 1 auto; height: 100% !important; min-height: 170px; }
/* 坐标轴标注: 放大 + 移到画布外侧 */
.axisY {
  position: absolute; left: -14px; top: 50%;
  transform: translateY(-50%) rotate(-90deg);
  font-size: 8px !important; color: rgba(160,225,250,.85) !important;
  letter-spacing: 1px;
}
.axisX {
  position: absolute; right: 2px; bottom: -13px;
  font-size: 8px !important; color: rgba(160,225,250,.85) !important;
}
/* 按钮禁用态 */
.trBtn.disabled { opacity: .42; pointer-events: none; filter: grayscale(.5); }
/* 题头更保险: 额外顶部留白 */
.trH { padding-top: 3px !important; }
.trCard { padding-top: 5px !important; }
'''
    open(cp, "w", encoding="utf-8").write(c)
    print("screens.css: 第二轮修正已加")

# ---------------- 3. train.js: 按钮状态 ----------------
jp = BASE + r"\ui2\train.js"
j = open(jp, encoding="utf-8").read()

if "trainStart" in j and "训 练 中" not in j:
    j = j.replace(
        "    drawChart(d.losses || []);",
        '''    drawChart(d.losses || []);
    // 开始/继续/训练中 按钮状态机
    (function () {
      const b = $("trainStart");
      if (!b) return;
      if (d.state === "running") {
        b.textContent = "训 练 中";
        b.classList.add("disabled");
      } else {
        b.classList.remove("disabled");
        b.textContent = d.can_resume ? "继 续 训 练" : "开 始 训 练";
      }
    })();''',
        1,
    )
    open(jp, "w", encoding="utf-8").write(j)
    print("train.js: 按钮状态机已加")
else:
    print("train.js: 跳过")

print("完成")
