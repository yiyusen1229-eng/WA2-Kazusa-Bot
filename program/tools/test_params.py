# -*- coding: utf-8 -*-
"""关键参数表的自测（#12，不联网、不开界面）。

跑法：
    cd program
    build_env/venv/Scripts/python.exe tools/test_params.py

验的是：
  1. 登记表结构自检（键唯一 / 字段齐全 / 取值落在声明区间）
  2. 每组参数的**语义**断言（不只是"有个数"，而是关系和推导对得上）
  3. 后端常量确实来自这几个模块（没有第二份影子常量）
  4. 前端常量（wt-fade 的 200/240/300）和登记表一致
  5. `other/docs/参数与指标.md` 和 `params.py` 没脱节（等价于 param_table --check）
"""
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
SRC = os.path.join(PROGRAM, "src")
sys.path.insert(0, SRC)
sys.path.insert(0, HERE)

# 别碰真实运行状态
os.environ["WA2_CACHE_DIR"] = tempfile.mkdtemp(prefix="wa2_params_test_")

import params  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:220]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def main():
    rows = params.rows()
    by = {r["key"]: r for r in rows}

    # 1 --------------------------------------------------------------------
    ok, errs = params.check()
    check("登记表结构自检通过", ok, errs)
    check("至少登记了 30 个参数（现在 %d）" % len(rows), len(rows) >= 30, len(rows))
    check("每个分组都有参数", all(any(r["group"] == g for r in rows) for g in params.groups()),
          [g for g in params.groups() if not any(r["group"] == g for r in rows)])
    check("没有取不到值的参数", all(r["value"] is not None for r in rows),
          [r["key"] for r in rows if r["value"] is None])

    # 2 / 3 ----------------------------------------------------------------
    import api_chat
    import memory
    import special_cfg

    check("回复上限：本地 < 云端",
          api_chat.MAX_TOKENS_LOCAL < api_chat.MAX_TOKENS_CLOUD,
          (api_chat.MAX_TOKENS_LOCAL, api_chat.MAX_TOKENS_CLOUD))
    check("登记表里的 token 上限就是 api_chat 的常量",
          by["chat.max_tokens_cloud"]["value"] == api_chat.MAX_TOKENS_CLOUD
          and by["chat.max_tokens_local"]["value"] == api_chat.MAX_TOKENS_LOCAL)
    check("超时 ≥ 30 秒", api_chat.CHAT_TIMEOUT_S >= 30, api_chat.CHAT_TIMEOUT_S)
    check("原作检索参数有效", api_chat.STORY_K >= 0 and api_chat.STORY_MAX_CHARS > 0,
          (api_chat.STORY_K, api_chat.STORY_MAX_CHARS))

    # 记忆：budget 三档必须严格由三个比例 × 上下文推出来
    cfg = memory.cfg()
    trig, recent_b, entries_b = memory.budget(True)
    ctx = int(cfg["cloud_ctx"])
    check("budget 触发阈值 = 上下文 × trigger_ratio",
          trig == int(ctx * cfg["trigger_ratio"]), (trig, ctx, cfg["trigger_ratio"]))
    check("budget 最近段 = 上下文 × recent_ratio",
          recent_b == int(ctx * cfg["recent_ratio"]), (recent_b, recent_b))
    check("budget 条目 = 上下文 × entries_ratio",
          entries_b == int(ctx * cfg["entries_ratio"]), entries_b)
    check("比例顺序：trigger > recent > entries",
          cfg["trigger_ratio"] > cfg["recent_ratio"] > cfg["entries_ratio"], cfg)
    check("三档预算都不为 0", trig > 0 and recent_b > 0 and entries_b > 0,
          (trig, recent_b, entries_b))
    check("分块大小 < 云端上下文", cfg["chunk_tokens"] < cfg["cloud_ctx"],
          (cfg["chunk_tokens"], cfg["cloud_ctx"]))
    check("同步打包块数 ≤ 后台块数",
          cfg["sync_chunks"] <= max(1, cfg["async_chunks"]), cfg)
    check("条目上限 ≥ 4", cfg["max_entries"] >= 4, cfg["max_entries"])

    # special_cfg 的滑条上限必须跟 DEFAULTS 对齐，否则界面能调出越界值
    check("special_cfg.CTX_MAX == memory.DEFAULTS['cloud_ctx']",
          special_cfg.CTX_MAX == memory.DEFAULTS["cloud_ctx"],
          (special_cfg.CTX_MAX, memory.DEFAULTS["cloud_ctx"]))
    check("滑条最小值在合法区间",
          special_cfg.MIN_CTX < special_cfg.CTX_MAX and 0 < special_cfg.MIN_RATIO < 1,
          (special_cfg.MIN_CTX, special_cfg.MIN_RATIO))
    check("special_cfg.defaults() 就是 DEFAULTS 里那四项",
          special_cfg.defaults() == {k: memory.DEFAULTS[k] for k in special_cfg.KEYS})

    # 世界书：默认值常量还在 persona_ctx，表里读的是"生效值"
    import persona_ctx
    wb = persona_ctx.load_worldbook()
    check("世界书默认值常量都在 DEFAULTS 里可被覆盖",
          persona_ctx.WB_DEFAULT_DEPTH >= 1 and persona_ctx.WB_DEFAULT_ENTRIES >= 1
          and persona_ctx.WB_DEFAULT_CHARS >= 200,
          (persona_ctx.WB_DEFAULT_DEPTH, persona_ctx.WB_DEFAULT_ENTRIES,
           persona_ctx.WB_DEFAULT_CHARS))
    check("表里的世界书深度 = persona_ctx 的默认常量（不是本地数据）",
          by["worldbook.depth"]["value"] == persona_ctx.WB_DEFAULT_DEPTH,
          (by["worldbook.depth"]["value"], persona_ctx.WB_DEFAULT_DEPTH))
    check("本机 worldbook.json 的覆盖值也在合法区间",
          1 <= wb.get("scan_depth", persona_ctx.WB_DEFAULT_DEPTH) <= 40,
          wb.get("scan_depth"))

    # 角色资源：三档上限必须递增
    import char_res
    check("人设 ≥ 世界书 ≥ 常驻记忆书（三档上限递增）",
          char_res.MAX_PROMPT_CHARS > char_res.MAX_WORLDBOOK_CHARS > char_res.MAX_MEMORY_CHARS,
          (char_res.MAX_PROMPT_CHARS, char_res.MAX_WORLDBOOK_CHARS, char_res.MAX_MEMORY_CHARS))

    # 关系阶段
    import persona_stage
    st = persona_stage.debug_state()
    check("阶段间隔 ≥ 5 轮", persona_stage.EVERY >= 5, persona_stage.EVERY)
    check("debug_state 的 every 就是 EVERY", st.get("every") == persona_stage.EVERY, st)
    check("最多带最近轮数 ≥ 判断间隔",
          persona_stage.TAIL_ROUNDS >= persona_stage.EVERY,
          (persona_stage.TAIL_ROUNDS, persona_stage.EVERY))
    check("扫描字数不超过 20000", persona_stage.SCAN_CHARS <= 20000, persona_stage.SCAN_CHARS)
    check("本地封顶关键词至少 1 个", len(persona_stage.MARKERS_4) >= 1)
    check("阶段在 1~4", 1 <= st.get("stage", 1) <= 4, st)

    # 语音
    import tts_client
    import audio_gain
    check("TTS 端口和翻译端口不同",
          tts_client.PORT != tts_client.T_PORT, (tts_client.PORT, tts_client.T_PORT))
    check("等就绪的超时 ≥ 单句合成超时",
          tts_client.READY_TIMEOUT_S >= tts_client.SYNTH_TIMEOUT_S,
          (tts_client.READY_TIMEOUT_S, tts_client.SYNTH_TIMEOUT_S))
    check("增益上下限方向对：max>0>min",
          audio_gain.MAX_GAIN_DB > 0 > audio_gain.MIN_GAIN_DB,
          (audio_gain.MIN_GAIN_DB, audio_gain.MAX_GAIN_DB))
    check("峰值上限是负的（留余量）", audio_gain.PEAK_CEIL_DB < 0, audio_gain.PEAK_CEIL_DB)
    check("目标响度在 -30 ~ -8 之间", -30 <= audio_gain.TARGET_LUFS <= -8, audio_gain.TARGET_LUFS)
    check("情绪参数至少覆盖 neutral / calm / 毒舌",
          all(k in tts_client.EMOTION_PARAMS for k in ("neutral", "calm", "毒舌")),
          list(tts_client.EMOTION_PARAMS))
    check("每组情绪参数四个键齐全",
          all(set(v) >= {"speed_factor", "temperature", "top_k", "top_p"}
              for v in tts_client.EMOTION_PARAMS.values()))

    # 缓存 / 演出 / 存档 / 包 / 日志
    import diag, sessions, char_pack, applog, pricing
    check("字模淘汰阈值 ≤ 上限（实际生效的是 evict）",
          by["ui.text_cache_evict"]["value"] <= by["ui.text_cache_max"]["value"],
          (by["ui.text_cache_evict"]["value"], by["ui.text_cache_max"]["value"]))
    check("两个字模阈值都 > 0",
          by["ui.text_cache_evict"]["value"] > 0 and by["ui.text_cache_max"]["value"] > 0)
    check("面板保留轮数 ≥ 1", diag.KEEP >= 1, diag.KEEP)
    check("过渡时长 最小 < 默认 < 最大",
          by["ui.fade_ms_min"]["value"] < by["ui.fade_ms"]["value"] < by["ui.fade_ms_max"]["value"],
          [by["ui.fade_ms_min"]["value"], by["ui.fade_ms"]["value"], by["ui.fade_ms_max"]["value"]])
    check("过渡默认值在 200~300 之间",
          200 <= by["ui.fade_ms"]["value"] <= 300, by["ui.fade_ms"]["value"])
    check("存档 schema 版本 ≥ 1", sessions.SCHEMA_VERSION >= 1, sessions.SCHEMA_VERSION)
    check("角色包单文件上限 < 总量上限",
          char_pack.MAX_ENTRY < char_pack.MAX_TOTAL,
          (char_pack.MAX_ENTRY, char_pack.MAX_TOTAL))
    check("角色包条目上限 ≥ 100", char_pack.MAX_ENTRIES >= 100, char_pack.MAX_ENTRIES)
    check("慢请求阈值 > 0", applog._SLOW_REQUEST_MS > 0, applog._SLOW_REQUEST_MS)
    check("价格缓存时效 > 0", pricing.TTL > 0, pricing.TTL)

    # 4 --------------------------------------------------------------------
    # 前端常量：表里读的就是 wt-fade.js 里的字面量，夹取逻辑也要一致
    fade_js = os.path.join(SRC, "ui", "wt-fade.js")
    src = open(fade_js, encoding="utf-8").read()
    check("wt-fade.js 里有 DEF_MS/MIN_MS/MAX_MS",
          all(k in src for k in ("DEF_MS = 240", "MIN_MS = 200", "MAX_MS = 300")), src[:0])
    check("表里的三个值来自 JS 字面量",
          (by["ui.fade_ms"]["value"], by["ui.fade_ms_min"]["value"],
           by["ui.fade_ms_max"]["value"]) == (240, 200, 300),
          [by["ui.fade_ms"]["value"], by["ui.fade_ms_min"]["value"], by["ui.fade_ms_max"]["value"]])

    # 5 --------------------------------------------------------------------
    import param_table
    doc = os.path.join(PROGRAM, "..", "other", "docs", "参数与指标.md")
    check("参数表文档存在", os.path.isfile(doc))
    if os.path.isfile(doc):
        old = open(doc, encoding="utf-8").read()
        check("文档和 params.py 没脱节（等于 param_table --check）",
              old == param_table.render())
        missing = [r["key"] for r in rows if ("`%s`" % r["key"]) not in old]
        check("每个登记参数都在文档里出现", not missing, missing[:5])

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), " / ".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
