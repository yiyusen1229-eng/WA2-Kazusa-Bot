# -*- coding: utf-8 -*-
"""修复: 训练数据卡片被误隐藏 + 学习率显示真实值"""
P = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\ui2\train.js"
s = open(P, encoding="utf-8").read()

old = '''    const w = s.by_route_weighted || {};
  const wRow = $("dRoutes");
  if (wRow && Object.keys(w).length === 0) {
    const row = wRow.closest(".mrow") || wRow.parentElement;
    if (row) row.style.display = "none";
  }
    const box = $("dRoutes");
    if (box) {
      const order = ["CODA", "IC", "NOVEL", "CC", "OTHER"];
      box.innerHTML = order.filter(k => w[k] != null)
        .map(k => '<span>' + k + " " + w[k] + '</span>').join(" ");
    }'''

new = '''    // 素材权重: 没有数据时只把这一小节写成"—", 绝不隐藏整张卡
    const w = s.by_route_weighted || {};
    const box = $("dRoutes");
    if (box) {
      const order = ["CODA", "IC", "NOVEL", "CC", "OTHER"];
      const parts = order.filter(k => w[k] != null)
        .map(k => '<span>' + k + " " + w[k] + '</span>');
      box.innerHTML = parts.length ? parts.join(" ") : "<span>—</span>";
    }'''

assert old in s, "未匹配权重隐藏片段"
s = s.replace(old, new, 1)

# 学习率: 显示配置里的真实值
s = s.replace('set("mLr", c.lr != null ? "1e-4" : "—");',
              'set("mLr", c.lr != null ? Number(c.lr).toExponential(2) : "—");')

open(P, "w", encoding="utf-8").write(s)
print("train.js 已修")
import ast
print("OK")
