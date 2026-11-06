# -*- coding: utf-8 -*-
"""关键参数登记表（#12）。

为什么要有这张表：数字原来散在 `memory.DEFAULTS`、`persona_stage.EVERY`、
`special_cfg`、`pricing`、`audio_gain`、`wt-fade.js` 里，改一个不知道会影响什么。
这里把「改哪些数字会动到什么」集中登记成一张**只读**表，由
`tools/param_table.py --write` 生成 `other/docs/参数与指标.md`（`--check` 保证表不过期）。

这张表**不改变任何行为**：`get` 是取当前值的只读函数（含环境变量 / 配置文件叠加后的
生效值）。要改参数还是去改原来的地方（表里的「怎么调」列写了在哪改）。

对外：
    PARAMS      登记项（每项见 `P()` 的字段）
    rows()      展开成行（当前值已解出来、格式化成字符串）
    get(key)    取单个参数的当前值
    check()     结构自检 → (ok, errors)
    groups()    分组顺序
"""
import importlib
import os
import re

GROUPS = ["对话", "记忆", "人设/世界书", "关系阶段", "角色资源",
          "语音", "缓存", "演出", "存档/包/日志"]

_MODS = {}


def _m(name):
    """懒加载模块：登记表本身可以被任何进程 import，不拽重依赖"""
    if name not in _MODS:
        _MODS[name] = importlib.import_module(name)
    return _MODS[name]


def _main_attr(name, default=None):
    try:
        return getattr(_m("main"), name, default)
    except Exception:
        return default


_JS_CACHE = {}


def _js_num(fname, name, default=None):
    """从前端文件里读一个数字常量（`DEF_MS = 240;` 这种）"""
    key = (fname, name)
    if key in _JS_CACHE:
        return _JS_CACHE[key]
    val = default
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", fname)
        with open(path, encoding="utf-8") as f:
            src = f.read()
        m = re.search(r"\b" + re.escape(name) + r"\s*=\s*([0-9.]+)", src)
        if m:
            val = float(m.group(1))
            if val.is_integer():
                val = int(val)
    except Exception:
        pass
    _JS_CACHE[key] = val
    return val


def _wb(key, default):
    """世界书里实际生效的值（没写就用 persona_ctx 的默认）—— 表里不用它，
    因为 worldbook.json 是本地数据，写进文档会让 `--check` 换机就失败。"""
    try:
        return _m("persona_ctx").load_worldbook().get(key, default)
    except Exception:
        return default


def P(key, group, label, get, unit, rng, where, impact, risk, verify):
    return {"key": key, "group": group, "label": label, "get": get, "unit": unit,
            "range": rng, "where": where, "impact": impact, "risk": risk, "verify": verify}


PARAMS = [
    # ---------------- 对话 ----------------
    P("chat.max_tokens_cloud", "对话", "云端回复上限", lambda: _m("api_chat").MAX_TOKENS_CLOUD,
      "token", (64, 4096), "api_chat.py 常量",
      "太小：话没说完就被截断；太大：偶发长篇，演出变慢也变贵", "低",
      "test_params 断言 >0；手动：发一句看回复是否被截"),
    P("chat.max_tokens_local", "对话", "本地模型回复上限", lambda: _m("api_chat").MAX_TOKENS_LOCAL,
      "token", (64, 2048), "api_chat.py 常量",
      "本地小模型上下文小，调大容易把上下文吃满", "低", "test_params 断言小于云端那档"),
    P("chat.timeout_s", "对话", "等云端回复超时", lambda: _m("api_chat").CHAT_TIMEOUT_S,
      "秒", (30, 600), "api_chat.py 常量",
      "太小：慢模型正常回复也会被判失败；太大：真断线时要等到超时", "低",
      "test_params 断言 ≥30；手动：断网后发一句，看多久报错"),
    P("llm.budget_daily", "对话", "每天花费提醒阈值", lambda: _m("llm").BUDGET_DAILY,
      "元", (0, 100), "llm.py 常量（环境变量 WA2_BUDGET_DAILY 可临时覆盖）",
      "0 = 不提醒；到 80% 提醒一次、超过 100% 再提醒一次（只在对话回复里带一句话）", "低",
      "test_llm 断言阈值语义；手动：设成 0.01 聊两句看提示"),
    P("chat.story_k", "对话", "原作检索注入块数", lambda: _m("api_chat").STORY_K,
      "块", (0, 6), "api_chat.py 常量（角色 persona_slices.json 的 story_k 可覆盖）",
      "调大：更像原作但每轮更贵，且容易盖过当前语境", "中",
      "test_params 断言 ≥0；面板「检索」行看命中块数"),
    P("chat.story_max_chars", "对话", "原作检索最多字数", lambda: _m("api_chat").STORY_MAX_CHARS,
      "字", (0, 4000), "api_chat.py 常量（persona_slices.json 的 story_max_chars 可覆盖）",
      "调大：挤占人设/世界书预算", "中", "面板「提示词」行的「原作」段字数"),

    # ---------------- 记忆 ----------------
    P("memory.cloud_ctx", "记忆", "云端上下文窗口", lambda: _m("memory").DEFAULTS["cloud_ctx"],
      "token", (4000, 128000), "memory.json / 特别模式滑条",
      "决定什么时候切「记忆书模式」；调小会更早压缩，历史细节丢得快", "中",
      "special_cfg.CTX_MAX 必须等于它（test_params 断言）；面板「记忆」行"),
    P("memory.local_ctx", "记忆", "本地上下文窗口", lambda: _m("memory").DEFAULTS["local_ctx"],
      "token", (1024, 32768), "memory.json",
      "本地模型实际能吃多少；填大了会发送超长请求", "中", "test_params 断言 < cloud_ctx"),
    P("memory.trigger_ratio", "记忆", "触发记忆书的阈值比例",
      lambda: _m("memory").DEFAULTS["trigger_ratio"], "比例", (0.1, 1.0), "memory.json / 特别模式滑条",
      "越小越早开始压缩，省 token 但更容易丢细节", "中",
      "test_params 断言 budget 随它线性变化"),
    P("memory.recent_ratio", "记忆", "压缩后保留原文的比例",
      lambda: _m("memory").DEFAULTS["recent_ratio"], "比例", (0.05, 0.9), "memory.json / 滑条",
      "调大：留更多原话，条目份额被挤；调小：条目变多", "中", "test_params 断言 recent < trigger"),
    P("memory.entries_ratio", "记忆", "记忆条目占上下文比例",
      lambda: _m("memory").DEFAULTS["entries_ratio"], "比例", (0.01, 0.5), "memory.json / 滑条",
      "调大：注入更多旧事，可能压过当前话题", "中", "test_params 断言 entries < recent"),
    P("memory.max_entries", "记忆", "条目数上限", lambda: _m("memory").DEFAULTS["max_entries"],
      "条", (4, 200), "memory.json", "合并时超过就丢最旧的", "低", "面板「记忆」行的条目数 / 上限"),
    P("memory.repack_turns", "记忆", "每几轮重新打包", lambda: _m("memory").DEFAULTS["repack_turns"],
      "轮", (0, 40), "memory.json", "0 = 不后台重打包；太小会频繁调模型", "中",
      "test_params 断言 ≥0；日志里「记忆书：重新打包」"),
    P("memory.max_new_entries", "记忆", "一次打包最多产出条目",
      lambda: _m("memory").DEFAULTS["max_new_entries"], "条", (1, 40), "memory.json",
      "调大：一次压缩更细，但合并压力大", "低", "test_memory 系列自测"),
    P("memory.chunk_tokens", "记忆", "打包分块大小", lambda: _m("memory").DEFAULTS["chunk_tokens"],
      "token", (500, 16000), "memory.json",
      "长历史按这个切成几块总结；太大一块可能超模型上下文", "中",
      "test_params 断言 < cloud_ctx"),
    P("memory.sync_chunks", "记忆", "聊天时同步打包块数",
      lambda: _m("memory").DEFAULTS["sync_chunks"], "块", (0, 4), "memory.json",
      "调大：这一轮会明显变慢（在回复前做）", "高", "手动：超阈值后发一句，看「本轮」耗时"),
    P("memory.async_chunks", "记忆", "后台打包块数", lambda: _m("memory").DEFAULTS["async_chunks"],
      "块", (0, 20), "memory.json", "后台做，不影响回复；调大可能和对话抢模型", "低",
      "日志「记忆书：后台打包」"),

    # ---------------- 人设/世界书 ----------------
    P("worldbook.depth", "人设/世界书", "关键词扫描最近几条消息",
      lambda: _m("persona_ctx").WB_DEFAULT_DEPTH, "条", (1, 40),
      "persona_ctx.py 常量（worldbook.json 的 scan_depth 可覆盖）",
      "越大越容易误命中；越小越容易漏", "中", "面板「提示词」行的世界书字数"),
    P("worldbook.max_entries", "人设/世界书", "每轮最多注入几条",
      lambda: _m("persona_ctx").WB_DEFAULT_ENTRIES, "条", (1, 20),
      "persona_ctx.py 常量（worldbook.json / persona_slices.json 可覆盖）",
      "调大：设定更全，但挤占原文和条目预算", "中",
      "面板「提示词」行的「世界书(n条)」"),
    P("worldbook.max_chars", "人设/世界书", "每轮最多注入字数",
      lambda: _m("persona_ctx").WB_DEFAULT_CHARS, "字", (200, 8000),
      "persona_ctx.py 常量（worldbook.json / persona_slices.json 可覆盖）",
      "调大同上；和 entries 是双重闸", "中", "面板「提示词」行的世界书字数"),
    P("persona.max_prompt_chars", "人设/世界书", "人设正文上限",
      lambda: _m("char_res").MAX_PROMPT_CHARS, "字", (1000, 60000), "char_res.py 常量",
      "截断保护：人设写太长会被砍", "低", "面板「提示词」行的「人设」字数"),
    P("persona.max_worldbook_chars", "人设/世界书", "世界书补充上限",
      lambda: _m("char_res").MAX_WORLDBOOK_CHARS, "字", (500, 20000), "char_res.py 常量",
      "同上", "低", "同上"),
    P("persona.max_memory_chars", "人设/世界书", "常驻记忆书上限",
      lambda: _m("char_res").MAX_MEMORY_CHARS, "字", (200, 10000),
      "char_res.py 常量（persona_slices.json 的 memory_max_chars 可再压一道）",
      "常驻记忆书每轮都进，写长了直接推高每轮成本", "中", "面板「提示词」行的「常驻」字数"),

    # ---------------- 关系阶段 ----------------
    P("stage.every", "关系阶段", "每几轮判一次", lambda: _m("persona_stage").EVERY,
      "轮", (5, 500), "环境变量 WA2_STAGE_EVERY（默认 40）",
      "调小：阶段升得快、云端调用多；调大：反应慢", "中",
      "面板「分类」行的「每 N 轮判一次 / 还差几轮」"),
    P("stage.scan_chars", "关系阶段", "判断时看多少字", lambda: _m("persona_stage").SCAN_CHARS,
      "字", (1000, 20000), "persona_stage.py 常量",
      "太长：把早期关系也塞进去，可能误判；太短：看不出进展", "中",
      "test_params 断言 < 20000"),
    P("stage.tail_rounds", "关系阶段", "最多带最近几轮", lambda: _m("persona_stage").TAIL_ROUNDS,
      "轮", (10, 120), "persona_stage.py 常量", "和上一次的 scan_chars 一起决定看多远", "低",
      "test_params 断言 ≥ every"),
    P("stage.local_markers", "关系阶段", "本地「直接到 4」关键词数",
      lambda: len(_m("persona_stage").MARKERS_4), "个", (1, 50), "persona_stage.py 的 MARKERS_4",
      "命中直接封顶 4，不再问云端；加词等于放宽封顶条件", "中",
      "test_params 断言 ≥1；手动：说「结婚」看阶段是否变 4"),

    # ---------------- 角色资源 ----------------
    P("charpack.max_total_mb", "角色资源", "角色包解压总量上限",
      lambda: round(_m("char_pack").MAX_TOTAL / 1024 / 1024), "MB", (64, 8192), "char_pack.py 常量",
      "防 zip 炸弹；调小会误拒大角色包", "低", "test_char_pack 自测（44 项）"),
    P("charpack.max_entry_mb", "角色资源", "角色包单文件上限",
      lambda: round(_m("char_pack").MAX_ENTRY / 1024 / 1024), "MB", (1, 2048), "char_pack.py 常量",
      "同上；立绘/语音单文件超过就被丢", "低", "test_char_pack 自测"),
    P("charpack.max_entries", "角色资源", "角色包条目数上限",
      lambda: _m("char_pack").MAX_ENTRIES, "条", (100, 100000), "char_pack.py 常量",
      "同上", "低", "test_char_pack 自测"),

    # ---------------- 语音 ----------------
    P("tts.port", "语音", "GPT-SoVITS 端口", lambda: _m("tts_client").PORT,
      "端口", (1024, 65535), "tts_client.py 常量 / config.json 的 voice 段",
      "和本机别的服务撞端口就起不来；改了要同步 config.json", "中",
      "手动：/api/voice/ok 返回 ready=true"),
    P("tts.translate_port", "语音", "翻译服务端口", lambda: _m("tts_client").T_PORT,
      "端口", (1024, 65535), "tts_client.py 常量",
      "和 tts.port 相同会互相抢", "中", "test_params 断言两个端口不同"),
    P("tts.ready_timeout_s", "语音", "等语音服务就绪", lambda: _m("tts_client").READY_TIMEOUT_S,
      "秒", (10, 600), "tts_client.py 常量",
      "第一次要加载模型，给少了第一句永远没声", "中", "手动：冷启动后第一句能否出声"),
    P("tts.synth_timeout_s", "语音", "单句合成超时", lambda: _m("tts_client").SYNTH_TIMEOUT_S,
      "秒", (5, 300), "tts_client.py 常量", "太短：长句被掐；太长：卡住时等很久", "低",
      "日志「TTS 合成: N 字节, 耗时 Xs」"),
    P("tts.target_lufs", "语音", "响度归一化目标", lambda: _m("audio_gain").TARGET_LUFS,
      "LUFS", (-30, -8), "audio_gain.py 的 TARGET_LUFS",
      "调到 -23 更接近广播，但游戏里会显小；-16 是一般网页音频的响度", "中",
      "test_audio_gain 断言 -20dBFS 正弦 → -20 LUFS、apply 后到目标；面板「语音」行"),
    P("tts.max_gain_db", "语音", "最大提升增益", lambda: _m("audio_gain").MAX_GAIN_DB,
      "dB", (0, 24), "audio_gain.py 常量", "太大：底噪跟着抬", "低", "test_audio_gain 断言夹在 ±12"),
    P("tts.min_gain_db", "语音", "最大衰减增益", lambda: _m("audio_gain").MIN_GAIN_DB,
      "dB", (-24, 0), "audio_gain.py 常量", "太负：本来正常的语音会被压得很小", "低",
      "test_audio_gain 的「增益夹在 ±12」"),
    P("tts.peak_ceiling_db", "语音", "推完峰值上限", lambda: _m("audio_gain").PEAK_CEIL_DB,
      "dBFS", (-6, 0), "audio_gain.py 常量", "0 会削波；-1 留一点余量", "低",
      "test_audio_gain 的「推完峰值不超过 -1dBFS」"),
    P("tts.emotion_params", "语音", "情绪合成参数组数",
      lambda: len(_m("tts_client").EMOTION_PARAMS), "组", (1, 40), "tts_client.py 的 EMOTION_PARAMS",
      "每种情绪一组 speed/temperature/top_k/top_p；加情绪要同步前端标签", "中",
      "手动：切情绪听音色是否变"),

    # ---------------- 缓存 ----------------
    P("ui.text_cache_max", "缓存", "字模内存缓存上限", lambda: _main_attr("_TEXT_CACHE_MAX", 0),
      "条", (50, 20000), "main.py 常量", "软上限：真正开始淘汰看下一行的 evict", "低",
      "面板「缓存」行的字模计数"),
    P("ui.text_cache_evict", "缓存", "字模淘汰阈值", lambda: _main_attr("_TEXT_CACHE_EVICT", 0),
      "条", (50, 2000), "main.py 常量",
      "**实际生效的上限就是它**（以前写死在 api_text 里的 400）", "中",
      "test_params 断言 ≤ text_cache_max；面板「缓存」行"),
    P("diag.keep", "缓存", "调试面板保留轮数", lambda: _m("diag").KEEP,
      "轮", (1, 50), "diag.py 常量", "多了面板放不下", "低", "test_diag 断言滚动只留 KEEP 条"),

    # ---------------- 演出 ----------------
    P("ui.fade_ms", "演出", "交叉淡化时长", lambda: _js_num("wt-fade.js", "DEF_MS", 0),
      "毫秒", (200, 300), "wt-fade.js 的 DEF_MS / prefs.xfadeMs",
      "太短像硬切，太长像卡顿；改的是默认值，用户可在 prefs 覆盖", "低",
      "test_fade 断言夹在 200~300；探针看 opacity 是否渐变"),
    P("ui.fade_ms_min", "演出", "过渡时长下限", lambda: _js_num("wt-fade.js", "MIN_MS", 0),
      "毫秒", (100, 400), "wt-fade.js 常量", "区间夹取用", "低", "test_fade 断言 clamp"),
    P("ui.fade_ms_max", "演出", "过渡时长上限", lambda: _js_num("wt-fade.js", "MAX_MS", 0),
      "毫秒", (150, 800), "wt-fade.js 常量", "区间夹取用", "低", "test_fade 断言 clamp"),

    # ---------------- 存档/包/日志 ----------------
    P("sessions.schema_version", "存档/包/日志", "存档 schema 版本",
      lambda: _m("sessions").SCHEMA_VERSION, "版本号", (1, 99), "sessions.py 常量",
      "改它必须写迁移，否则老存档读不了", "高", "test_session_schema 自测（29 项）"),
    P("log.slow_request_ms", "存档/包/日志", "慢请求告警阈值",
      lambda: _m("applog")._SLOW_REQUEST_MS, "毫秒", (200, 30000), "applog.py 常量",
      "太低会刷一堆 SLOW；太高看不到卡顿", "低",
      "手动：看 logs/app-*.log 里的 SLOW 行"),
    P("pricing.price_ttl_h", "存档/包/日志", "价格表缓存时效",
      lambda: round(_m("pricing").TTL / 3600), "小时", (1, 168), "pricing.py 的 TTL",
      "过期会去抓官方页面；抓不到用 BUILTIN", "低", "test_params 断言 >0"),
]


# ------------------------------------------------------------------ 取数 / 自检

def _fmt(v):
    if v is None:
        return "?"
    if isinstance(v, bool):
        return "开" if v else "关"
    if isinstance(v, float):
        return ("%g" % round(v, 4))
    return str(v)


def get(key):
    for p in PARAMS:
        if p["key"] == key:
            return p["get"]()
    raise KeyError(key)


def rows():
    out = []
    for p in PARAMS:
        try:
            val = p["get"]()
        except Exception:
            val = None
        out.append(dict(p, value=val, value_text=_fmt(val)))
    return out


def groups():
    return list(GROUPS)


def check():
    """结构自检：键唯一、字段齐全、能取到值、数值落在声明的区间内"""
    errs = []
    seen = set()
    for p in PARAMS:
        k = p["key"]
        if k in seen:
            errs.append("%s 重复登记" % k)
        seen.add(k)
        for f in ("key", "group", "label", "get", "unit", "range", "where", "impact", "risk", "verify"):
            if f not in p or (f != "range" and not p.get(f)):
                errs.append("%s 缺字段 %s" % (k, f))
        if p.get("group") not in GROUPS:
            errs.append("%s 的分组 %r 不在 GROUPS 里" % (k, p.get("group")))
        try:
            val = p["get"]()
        except Exception as e:
            errs.append("%s 取不到值：%s" % (k, e))
            continue
        rng = p.get("range")
        if isinstance(rng, tuple) and len(rng) == 2 and isinstance(val, (int, float)) and not isinstance(val, bool):
            lo, hi = rng
            if not (lo <= val <= hi):
                errs.append("%s 当前值 %s 不在声明区间 %s~%s" % (k, val, lo, hi))
    return (not errs), errs
