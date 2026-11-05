# -*- coding: utf-8 -*-
"""每角色的「演出 / 切片」规则配置（#19）。

两个文件都放在角色文件夹里，缺了就用默认值（默认值 = 现在代码里的硬编码值，行为不变）：

    characters/<角色>/performance.json      前端演出：淡化时长、情绪→表情、场景→衣服
    characters/<角色>/persona_slices.json   后端切片：原作检索块数 / 世界书条数与字数 / 常驻记忆上限

校验（逐字段，不整份丢弃）：
  · 数字超出范围 → **夹到边界**并给一条 warning
  · 类型不对 / 空串 → 该字段用默认值 + warning
  · 不认识的键 → 忽略 + warning（避免用户以为写了个新开关）
  · 整份 JSON 坏了 → 全用默认 + warning（不崩、不阻塞对话）
  · 文件不存在 → 默认值，**不算错误**（大多数角色都没有这两个文件）

对外：
    DEFAULTS_PERF / DEFAULTS_SLICES / RANGES
    performance()         → dict（给前端：淡化时长 / 两张映射表）
    slices()              → dict（给后方：检索与世界书预算）
    load()                → (performance, slices, warnings, files)
    detail()              → 给 /api/performance 的完整包
    clear_cache()         → 自测用
"""
import json
import os

import applog
import characters

PERF_NAME = "performance.json"
SLICES_NAME = "persona_slices.json"

# 默认值：必须和现在的硬编码值一致（不然「什么都没配」也会改行为）
DEFAULTS_PERF = {
    "fade_ms": 240,              # ui/wt-fade.js 的 DEF_MS
    "mood_to_emotion": {},       # 空 = 用 wt-sprite.js 内置的 MOOD_TO_EMO
    "outfit_by_scene": {},       # 空 = 用 wt-sprite.js 内置的 OUTFIT_BY_SCENE
}

DEFAULTS_SLICES = {
    "story_k": 2,                # api_chat.STORY_K
    "story_max_chars": 900,      # api_chat.STORY_MAX_CHARS
    "worldbook_entries": 3,      # persona_ctx.WB_DEFAULT_ENTRIES
    "worldbook_chars": 1200,     # persona_ctx.WB_DEFAULT_CHARS
    "memory_max_chars": 1500,    # char_res.MAX_MEMORY_CHARS
}

RANGES = {
    "fade_ms": (200, 300),
    "story_k": (0, 5),
    "story_max_chars": (0, 3000),
    "worldbook_entries": (0, 8),
    "worldbook_chars": (0, 4000),
    "memory_max_chars": (0, 4000),
}

MAX_MAP_ITEMS = 40
MAX_MAP_KEY = 30

_CACHE = {}
_WARNED = set()


def _dir():
    return characters.active_dir()


def paths():
    d = _dir()
    if not d:
        return {"performance": "", "slices": ""}
    return {"performance": os.path.join(d, PERF_NAME),
            "slices": os.path.join(d, SLICES_NAME)}


def _read_json(path):
    """返回 (dict | None, error | None)；文件不存在返回 (None, None)

    用 utf-8-sig 读：用户可能拿记事本 / PowerShell 5.1 存出带 BOM 的 UTF-8，
    带 BOM 时 `json.load` 会直接报「读不了」，看起来像文件坏了。
    """
    if not path or not os.path.isfile(path):
        return None, None
    try:
        with open(path, encoding="utf-8-sig") as f:
            d = json.load(f)
    except Exception as e:
        return None, "读不了：%s" % e
    if not isinstance(d, dict):
        return None, "顶层必须是一个对象"
    return d, None


def _clamp(name, v, default, warn, where):
    lo, hi = RANGES[name]
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        warn("%s：%s 要数字，给的是 %r，用默认 %s" % (where, name, v, default))
        return default
    iv = int(v)
    if iv < lo or iv > hi:
        warn("%s：%s=%s 超出 %d~%d，夹到边界" % (where, name, v, lo, hi))
        return lo if iv < lo else hi
    return iv


def _map(v, name, where, warn):
    """情绪/场景映射：只认「短字符串 → 短字符串」，坏条目单独丢掉"""
    if v is None:
        return {}
    if not isinstance(v, dict):
        warn("%s：%s 要一个对象，给的是 %s，忽略" % (where, name, type(v).__name__))
        return {}
    out = {}
    for k, val in v.items():
        if len(out) >= MAX_MAP_ITEMS:
            warn("%s：%s 超过 %d 条，多的忽略" % (where, name, MAX_MAP_ITEMS))
            break
        if not isinstance(k, str) or not isinstance(val, str) or not k or not val:
            warn("%s：%s 里有一项不是字符串（%r → %r），跳过" % (where, name, k, val))
            continue
        if len(k) > MAX_MAP_KEY or len(val) > MAX_MAP_KEY:
            warn("%s：%s 里 %r 太长（>%d），跳过" % (where, name, k, MAX_MAP_KEY))
            continue
        out[k] = val
    return out


def _load_uncached(warn):
    files = paths()
    perf = dict(DEFAULTS_PERF)
    slices = dict(DEFAULTS_SLICES)

    raw, err = _read_json(files["performance"])
    if err:
        warn("%s：%s，整份用默认" % (PERF_NAME, err))
    elif raw:
        known = set(DEFAULTS_PERF)
        for k in raw:
            if k not in known:
                warn("%s：不认识的字段 %r（已忽略）" % (PERF_NAME, k))
        if "fade_ms" in raw:
            perf["fade_ms"] = _clamp("fade_ms", raw["fade_ms"], DEFAULTS_PERF["fade_ms"],
                                     warn, PERF_NAME)
        for m in ("mood_to_emotion", "outfit_by_scene"):
            if m in raw:
                perf[m] = _map(raw[m], m, PERF_NAME, warn)

    raw, err = _read_json(files["slices"])
    if err:
        warn("%s：%s，整份用默认" % (SLICES_NAME, err))
    elif raw:
        known = set(DEFAULTS_SLICES)
        for k in raw:
            if k not in known:
                warn("%s：不认识的字段 %r（已忽略）" % (SLICES_NAME, k))
        for k in DEFAULTS_SLICES:
            if k in raw:
                slices[k] = _clamp(k, raw[k], DEFAULTS_SLICES[k], warn, SLICES_NAME)

    return perf, slices, files


def load():
    """→ (performance, slices, warnings, files)

    每次都重读两份小 JSON（1KB 上下，微秒级）：用户改完文件不用重启也立刻生效。
    只对 warning 做了去重（同一个问题只记一条日志），不缓存结果。
    """
    files = paths()
    warns = []

    def warn(msg):
        warns.append(msg)
        if msg not in _WARNED:
            _WARNED.add(msg)
            try:
                applog.log("演出/切片配置：" + msg, "WARN")
            except Exception:
                pass

    perf, slices, files = _load_uncached(warn)
    return perf, slices, warns, files


def performance():
    return load()[0]


def slices():
    return load()[1]


def detail():
    perf, sl, warns, files = load()
    return {"ok": True, "performance": perf, "slices": sl, "warnings": warns,
            "files": {"performance": files["performance"], "slices": files["slices"]}}


def clear_cache():
    """自测用：清掉 warning 去重记录（结果本来就不缓存，改文件立刻生效）"""
    _CACHE.clear()
    _WARNED.clear()
