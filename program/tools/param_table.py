# -*- coding: utf-8 -*-
"""生成「参数与指标」表（#12）。

规则：**这张表由工具生成，不要手改**；改了常量就重跑。

    python tools/param_table.py            # 打印
    python tools/param_table.py --write    # 写入 other/docs/参数与指标.md
    python tools/param_table.py --check    # 与已提交的表对比，不一致退出码 1

数据源是 `program/src/params.py` 的 PARAMS（只读取当前生效值，不改行为）。
"""
import argparse
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # program/
SRC = os.path.join(ROOT, "src")
OUT = os.path.join(ROOT, "..", "other", "docs", "参数与指标.md")

sys.path.insert(0, SRC)

import params  # noqa: E402

GROUP_NOTES = {
    "记忆": "表里是 `memory.DEFAULTS`；`memory.json` 会覆盖（特别模式滑条改的就是它），"
            "本机实际生效值看调试面板「记忆」行。",
    "人设/世界书": "表里是 `persona_ctx` 的默认值；`worldbook.json` 里写了 scan_depth / "
                   "max_entries / max_chars 就以它为准。",
    "对话": "few-shot 条数来自本地 `fewshot.json`（不属于常量，不进表）。",
}


def _range_text(rng):
    if not isinstance(rng, tuple) or len(rng) != 2:
        return "—"
    return "%s ~ %s" % (rng[0], rng[1])


def _derived():
    """派生指标：不是常量，但改上面的参数会直接动到它们。

    只用**仓库里的常量**算（不读 memory.json / worldbook.json / fewshot.json 这类本地数据），
    否则 `--check` 换台机器就失败。本机实际生效值去调试面板看。
    """
    rows = []
    try:
        import memory
        d = memory.DEFAULTS
        ctx = int(d["cloud_ctx"])
        rows.append(("记忆：触发阈值", str(int(ctx * d["trigger_ratio"])) + " token",
                     "cloud_ctx × trigger_ratio（DEFAULTS）", "超过就切「记忆书模式」，不再全量发"))
        rows.append(("记忆：最近段上限", str(int(ctx * d["recent_ratio"])) + " token",
                     "cloud_ctx × recent_ratio", "压缩后保留多少原话"))
        rows.append(("记忆：条目上限", str(int(ctx * d["entries_ratio"])) + " token",
                     "cloud_ctx × entries_ratio", "注入的旧事最多占多少"))
        rows.append(("记忆：本地触发阈值", str(int(int(d["local_ctx"]) * d["trigger_ratio"])) + " token",
                     "local_ctx × trigger_ratio", "本地模型更早压缩（上下文小）"))
    except Exception as e:
        rows.append(("记忆：派生值", "?", "计算失败", str(e)[:60]))
    try:
        import char_res
        rows.append(("人设：三档字数上限",
                     "%d / %d / %d" % (char_res.MAX_PROMPT_CHARS, char_res.MAX_WORLDBOOK_CHARS,
                                       char_res.MAX_MEMORY_CHARS),
                     "char_res.py 常量", "人设 / 世界书补充 / 常驻记忆书（超出被截）"))
    except Exception:
        pass
    try:
        import audio_gain
        rows.append(("语音：响度目标", "%.1f LUFS" % audio_gain.TARGET_LUFS, "audio_gain.TARGET_LUFS",
                     "峰值上限 %.1f dBFS，增益 %+.0f ~ %+.0f dB"
                     % (audio_gain.PEAK_CEIL_DB, audio_gain.MIN_GAIN_DB, audio_gain.MAX_GAIN_DB)))
    except Exception:
        pass
    try:
        import diag
        rows.append(("调试面板：保留轮数", str(diag.KEEP) + " 轮", "diag.KEEP",
                     "面板只看最近几轮，再多放不下"))
    except Exception:
        pass
    return rows


def render():
    rows = params.rows()
    ok, errs = params.check()
    out = ["# 参数与指标", "",
           "> 由 `program/tools/param_table.py --write` 生成，**不要手改**。"
           "改了代码里的常量就重跑，表会跟着变。",
           "> 用法：按分组找参数 → 看「影响面 / 修改风险」→ 按「怎么调」那一列去改 → 按「验收方式」验一遍。",
           "> 每个参数在 `program/tools/test_params.py` 里至少有一条断言（区间 + 语义）；"
           "自检结果：" + ("全部在区间内" if ok else "**%d 项越界**" % len(errs)),
           "> 表里的「当前值」是**代码里的值**（含 `WA2_STAGE_EVERY` 这类环境变量覆盖）；"
           "`memory.json` / `worldbook.json` / `fewshot.json` 属于本地数据，不进表——"
           "本机实际生效值看调试面板或 `/api/debug/state`。",
           ""]
    for g in params.groups():
        part = [r for r in rows if r["group"] == g]
        if not part:
            continue
        out += ["## " + g, ""]
        if GROUP_NOTES.get(g):
            out += ["> " + GROUP_NOTES[g], ""]
        out += ["| 参数 | 当前值 | 可调范围 | 影响面 | 修改风险 | 怎么调 | 验收方式 |",
                "|---|---|---|---|---|---|---|"]
        for r in part:
            out.append("| `%s` %s | %s%s | %s | %s | %s | %s | %s |" % (
                r["key"], r["label"], r["value_text"],
                (" " + r["unit"]) if r["unit"] and r["value_text"] != "?" else "",
                _range_text(r["range"]), r["impact"], r["risk"], r["where"], r["verify"]))
        out.append("")
    out += ["## 派生指标（改上面的参数会动到这些）", "",
            "| 指标 | 现在 | 由什么决定 | 含义 |", "|---|---|---|---|"]
    for name, now, by, meaning in _derived():
        out.append("| %s | %s | %s | %s |" % (name, now, by, meaning))
    out += ["", "## 怎么现场看", "",
            "1. 开着调试面板（标题栏「调试」或 Ctrl+Shift+D）发一句话：",
            "   面板第一行起就是「这一轮提示词分段 / token 估算 / 场景 / 缓存命中」。",
            "2. 更细的整包：`GET /api/debug/state`（只读，只回数字和标签）。",
            "3. 改完常量跑一遍：`python tools/test_params.py` + `python tools/param_table.py --check`。",
            ""]
    if not ok:
        out += ["## 越界告警", ""] + ["- " + e for e in errs] + [""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    text = render()
    if a.write:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        print("已写入 %s（%d 个参数）" % (OUT, len(params.PARAMS)))
    elif a.check:
        old = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        if old != text:
            print("参数表过期：跑 python tools/param_table.py --write")
            return 1
        print("参数表是最新的")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
