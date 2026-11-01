# -*- coding: utf-8 -*-
"""训练面板增强
1. 图表加坐标轴说明(横轴=步数, 纵轴=loss) + 刻度
2. 图表下方空白处放「实时训练预览」: 当前在学哪一条样本
3. 训练脚本把样本写进 progress.json
"""
import re

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"

# ================= 1. 训练脚本: 写 preview =================
tp = BASE + r"\train\train_qlora.py"
s = open(tp, encoding="utf-8").read()

if "PREVIEW_POOL" not in s:
    # 在 dataset map 之后建立预览池
    s = s.replace(
        '    prog.log("  有效训练样本 %d" % len(ds))',
        '''    prog.log("  有效训练样本 %d" % len(ds))
    # 预览池: 抽 40 条, 供界面展示"模型此刻在学什么"
    PREVIEW_POOL = []
    try:
        import random as _rnd
        _n = min(40, len(ds))
        _idx = _rnd.Random(7).sample(range(len(ds)), _n)
        for _i in _idx:
            _row = ds[_i]
            _lab = _row["labels"]
            _ids = _row["input_ids"]
            # 找到第一个非 -100 的位置(= 回答起点)
            _st = 0
            for _k, _v in enumerate(_lab):
                if _v != -100:
                    _st = _k
                    break
            _prompt = tok.decode(_ids[:_st], skip_special_tokens=True)
            _ans = tok.decode(_ids[_st:], skip_special_tokens=True)
            _prompt = re.sub(r"<\\|[^|]*\\|>", "", _prompt).strip()[-260:]
            _ans = re.sub(r"<\\|[^|]*\\|>", "", _ans).strip()[:260]
            PREVIEW_POOL.append({"prompt": _prompt, "answer": _ans})
    except Exception as _e:
        prog.log("  预览池跳过: %s" % _e)''',
        1,
    )

    # 回调里写入 preview
    s = s.replace(
        "            if state.global_step != prog.step:",
        '''            try:
                if PREVIEW_POOL:
                    _pv = PREVIEW_POOL[int(state.global_step) % len(PREVIEW_POOL)]
                    prog.extra["preview"] = {
                        "step": int(state.global_step),
                        "prompt": _pv["prompt"],
                        "answer": _pv["answer"],
                        "loss": prog.loss,
                        "eval_loss": prog.extra.get("eval_loss"),
                    }
            except Exception:
                pass
            if state.global_step != prog.step:''',
        1,
    )
    open(tp, "w", encoding="utf-8").write(s)
    print("train_qlora.py: 已加 preview 池")

# Prog 需要 extra 字段
s = open(tp, encoding="utf-8").read()
if "self.extra" not in s:
    s = s.replace("self.logs = []", "self.logs = []\n        self.extra = {}", 1)
    s = s.replace("d.update(kw)", "d.update(self.extra)\n        d.update(kw)", 1)
    # eval_loss 记录
    s = s.replace('prog.log("eval_loss %.4f" % float(logs["eval_loss"]))',
                  'prog.extra["eval_loss"] = round(float(logs["eval_loss"]), 4)\n                prog.log("eval_loss %.4f" % float(logs["eval_loss"]))', 1)
    open(tp, "w", encoding="utf-8").write(s)
    print("train_qlora.py: Prog 已支持 extra")

import ast
ast.parse(open(tp, encoding="utf-8").read())
print("train_qlora.py 语法 OK")

# ================= 2. 后端透传 =================
mp = BASE + r"\app\main.py"
s = open(mp, encoding="utf-8").read()
if '"preview"' not in s:
    s = s.replace('"meta", "gpu_mem", "updated_at"):',
                  '"meta", "gpu_mem", "updated_at", "preview", "eval_loss"):', 1)
    open(mp, "w", encoding="utf-8").write(s)
    print("main.py: 已透传 preview / eval_loss")
ast.parse(open(mp, encoding="utf-8").read())
print("main.py 语法 OK")

# ================= 3. HTML: 预览块 =================
ip = BASE + r"\ui2\index.html"
h = open(ip, encoding="utf-8").read()
if "pvUser" not in h:
    h = h.replace(
        '<canvas id="chart"></canvas>',
        '''<div class="chartBox">
            <canvas id="chart"></canvas>
            <div class="axisY">loss</div>
            <div class="axisX">步数 →</div>
          </div>
          <div class="preview">
            <div class="pvH">实时训练预览<span id="pvStep"></span></div>
            <div class="pvRow"><b>前文</b><span id="pvUser">等待训练数据…</span></div>
            <div class="pvRow"><b>和纱</b><span id="pvAns">—</span></div>
            <div class="pvMeta"><span id="pvLoss">—</span><span id="pvEval">—</span><span id="pvSpeed">—</span></div>
          </div>''',
        1,
    )
    open(ip, "w", encoding="utf-8").write(h)
    print("index.html: 已加预览块与坐标轴标签")

# ================= 4. train.js: 轴标签 + 预览渲染 =================
jp = BASE + r"\ui2\train.js"
j = open(jp, encoding="utf-8").read()

if "axisY" not in j:
    j = j.replace(
        '''    g.fillText(mx.toFixed(2), 2, 7);
    g.fillText(mn.toFixed(2), 2, h - 2);''',
        '''    g.fillText(mx.toFixed(2), 2, 7);
    g.fillText(mn.toFixed(2), 2, h - 2);

    // 横轴刻度: 起止步数
    g.fillStyle = "rgba(150,220,250,.6)";
    g.fillText("step 0", w - 34, h - 2);''',
        1,
    )

if "pvUser" not in j:
    j = j.replace(
        "    drawChart(d.losses || []);",
        '''    drawChart(d.losses || []);
    // 实时训练预览
    const pv = d.preview || {};
    set("pvStep", pv.step != null ? "　第 " + pv.step + " 步" : "");
    set("pvUser", pv.prompt || "等待训练数据…");
    set("pvAns", pv.answer || "—");
    set("pvLoss", pv.loss != null ? "当前 loss " + Number(pv.loss).toFixed(4) : "");
    set("pvEval", pv.eval_loss != null ? "　验证 loss " + Number(pv.eval_loss).toFixed(4) : "");
    set("pvSpeed", d.speed ? "　" + (1000 / (d.speed || 1) / 1000).toFixed(1) + " 步/分" : "");''',
        1,
    )
    open(jp, "w", encoding="utf-8").write(j)
    print("train.js: 已加预览渲染")

# ================= 5. CSS =================
cp = BASE + r"\ui2\screens.css"
c = open(cp, encoding="utf-8").read()
if ".chartBox" not in c:
    c += '''

/* 训练图表: 坐标轴 + 预览区 */
.chartBox { position: relative; margin-top: 6px; }
.chartBox canvas { display: block; width: 100%; height: 130px; }
.axisY {
  position: absolute; left: 2px; top: -2px;
  font-size: 6.5px; color: rgba(150,220,250,.65);
  letter-spacing: .5px;
}
.axisX {
  position: absolute; right: 4px; bottom: -2px;
  font-size: 6.5px; color: rgba(150,220,250,.65);
}
.preview {
  margin-top: 8px; padding: 7px 9px;
  border: 1px solid rgba(110,200,255,.22);
  border-radius: 3px;
  background: rgba(4,20,34,.55);
  font-size: 7.2px; line-height: 1.55; color: #cfeeff;
}
.pvH {
  font-size: 7.6px; color: #8fe0ff; letter-spacing: .6px;
  margin-bottom: 4px;
}
.pvRow { display: flex; gap: 6px; margin: 3px 0; }
.pvRow b {
  flex: 0 0 auto; font-weight: normal;
  color: #7fd4ff; min-width: 24px;
}
.pvRow span {
  flex: 1 1 auto; color: #e6f7ff;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}
.pvMeta {
  margin-top: 4px; font-size: 6.8px;
  color: rgba(150,220,250,.7);
}
'''
    open(cp, "w", encoding="utf-8").write(c)
    print("screens.css: 已加样式")

print("完成")
