# -*- coding: utf-8 -*-
"""1. 修训练面板题头被裁切
2. 重新生成统计(训练样本/人设长度/平均长度/数据来源)
"""
import json
import os

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"

# ---------- 1. CSS: 题头不再被卡片边框裁掉 ----------
cp = BASE + r"\ui2\screens.css"
c = open(cp, encoding="utf-8").read()
if "/* 题头防裁切 */" not in c:
    c += '''

/* 题头防裁切 */
.trCard { padding: 3px 6px 5px 6px !important; }
.trH {
  margin-top: 0 !important;
  padding-top: 1px !important;
  line-height: 1.35 !important;
  overflow: visible !important;
}
.trCol.left .trCard { padding-top: 2px !important; }
'''
    open(cp, "w", encoding="utf-8").write(c)
    print("screens.css: 题头防裁切")

# ---------- 2. train.js: 权重标题改成「数据来源」, 兼容新键名 ----------
jp = BASE + r"\ui2\train.js"
j = open(jp, encoding="utf-8").read()
j = j.replace('const order = ["CODA", "IC", "NOVEL", "CC", "OTHER"];',
              'const order = ["主剧本", "人物资料", "小说", "其它", "CODA", "IC", "NOVEL", "CC", "OTHER"];')
open(jp, "w", encoding="utf-8").write(j)
print("train.js: 数据来源键名已扩展")

hp = BASE + r"\ui2\index.html"
h = open(hp, encoding="utf-8").read()
if "素材权重" in h:
    h = h.replace("素材权重", "数据来源")
    open(hp, "w", encoding="utf-8").write(h)
    print("index.html: 标题改为「数据来源」")

# ---------- 3. 重新生成 stats.json ----------
data = BASE + r"\train\data"
train = [json.loads(l) for l in open(os.path.join(data, "train.jsonl"), encoding="utf-8") if l.strip()]
val = [json.loads(l) for l in open(os.path.join(data, "val.jsonl"), encoding="utf-8") if l.strip()]

persona = open(os.path.join(BASE, r"app\persona_core.txt"), encoding="utf-8").read().strip()

u_len, a_len = [], []
for m in train[:4000]:
    msgs = m["messages"]
    us = [x["content"] for x in msgs if x["role"] == "user"]
    as_ = [x["content"] for x in msgs if x["role"] == "assistant"]
    if us:
        u_len.append(sum(len(x) for x in us) / len(us))
    if as_:
        a_len.append(len(as_[-1]))

stats = {
    "train": len(train),
    "val": len(val),
    "persona_len": len(persona),
    "avg_user_len": round(sum(u_len) / max(1, len(u_len)), 1),
    "avg_assistant_len": round(sum(a_len) / max(1, len(a_len)), 1),
    "by_route_weighted": {"主剧本": len(train)},
    "note": "v6: 多轮经历窗口 + <thinking> 推理链, 按场景切分",
}
out = os.path.join(data, "stats.json")
json.dump(stats, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("stats.json 已重写:", json.dumps(stats, ensure_ascii=False))
