# -*- coding: utf-8 -*-
"""价格：从官网价格页抓当前单价，抓不到就用内置的兜底表。

为什么要抓：单价会变（官方调价、新模型），写死在代码里迟早过期。
抓不到也不能影响主流程 —— 一律退回 BUILTIN，绝不让聊天因为查价失败而报错。

计费口径（DeepSeek）：
    输入分「缓存命中 / 未命中」两档，输出一档；
    高峰时段（UTC 周一~周五 01:00-04:00、06:00-10:00）单价翻倍，
    其余时段（含周末、中国法定节假日）是半价。
    注：中国法定节假日这里没有判断，只按周末算 —— 影响很小（会按高峰价算）。
"""
import datetime
import json
import os
import re
import time
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE, "cache")
CACHE_FILE = os.path.join(CACHE_DIR, "prices.json")
PRICE_URL = "https://api-docs.deepseek.com/quick_start/pricing"
TTL = 6 * 3600          # 6 小时内不重复抓

# 2026-11 官方页面上的数字（美元 / 1M token），抓不到就用这份
BUILTIN = {
    "deepseek-flash": {
        "hit":  {"peak": 0.006, "off": 0.003},
        "miss": {"peak": 0.3,   "off": 0.15},
        "out":  {"peak": 1.2,   "off": 0.6},
    },
    "deepseek-v4-pro": {
        "hit":  {"peak": 0.044, "off": 0.022},
        "miss": {"peak": 1.32,  "off": 0.66},
        "out":  {"peak": 3.96,  "off": 1.98},
    },
}

_MEM = {"t": 0, "table": None, "source": ""}


def _num(s):
    m = re.search(r"\d+(?:\.\d+)?", s.replace(",", ""))
    return float(m.group()) if m else None


def _cells(html):
    """按出现顺序取出所有单元格的纯文本"""
    out = []
    for m in re.finditer(r"<td[^>]*>(.*?)</td>", html, re.S):
        txt = re.sub(r"<[^>]+>", "", m.group(1))
        txt = txt.replace("&amp;", "&").replace("\u200b", "")
        out.append(re.sub(r"\s+", " ", txt).strip())
    return out


def _parse(html):
    """把价格表解析成 {model: {...}}；解析不出来返回 None"""
    cells = _cells(html)
    models = []
    for i, c in enumerate(cells):
        if c.upper() == "MODEL":
            for c2 in cells[i + 1: i + 4]:
                n = re.sub(r"\(\d+\)", "", c2).strip()
                if n and " " not in n and n.lower().startswith("deepseek"):
                    models.append(n)
            break
    if not models:
        return None
    return _parse_simple(cells, models)


def _parse_simple(cells, models):
    """状态机版本（上面那个只负责找模型名）"""
    table = {m: {"hit": {}, "miss": {}, "out": {}} for m in models}
    idx = 0
    n = len(cells)
    kind = None      # hit / miss / out
    while idx < n:
        c = cells[idx]
        u = c.upper()
        if u.startswith("1M INPUT TOKENS"):
            # 官方页把 (CACHE HIT)/(CACHE MISS) 写在同一个单元格里
            kind = "hit" if "CACHE HIT" in u else "miss"
            idx += 1
            continue
        if u.startswith("1M OUTPUT TOKENS"):
            kind = "out"
            idx += 1
            continue
        if u in ("OFF-PEAK", "PEAK"):
            phase = "off" if u == "OFF-PEAK" else "peak"
            # 后面连续 len(models) 个 $ 价格
            got = 0
            j = idx + 1
            while j < n and got < len(models):
                v = cells[j]
                if v.startswith("$"):
                    num = _num(v)
                    if num is not None and kind:
                        table[models[got]][kind][phase] = num
                    got += 1
                elif v.upper() in ("OFF-PEAK", "PEAK") or v.upper().startswith("1M "):
                    break
                j += 1
            idx = j
            continue
        idx += 1
    # 校验：三个价格都得有
    for m in models:
        for k in ("hit", "miss", "out"):
            if len(table[m][k]) != 2:
                return None
    return table


def _load_cache():
    try:
        with open(CACHE_FILE, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and d.get("table"):
            return d
    except Exception:
        pass
    return None


def _save_cache(table):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp = CACHE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"t": time.time(), "table": table}, f, ensure_ascii=False, indent=1)
        os.replace(tmp, CACHE_FILE)
    except Exception:
        pass


def table(force=False):
    """返回 (价格表, 来源)。来源：official / cache / builtin"""
    now = time.time()
    if not force and _MEM["table"] and now - _MEM["t"] < TTL:
        return _MEM["table"], _MEM["source"]
    c = _load_cache()
    if not force and c and now - c.get("t", 0) < TTL:
        _MEM.update({"t": c["t"], "table": c["table"], "source": "cache"})
        return c["table"], "cache"
    try:
        req = urllib.request.Request(PRICE_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode("utf-8", "replace")
        t = _parse(html)
        if t:
            _save_cache(t)
            _MEM.update({"t": now, "table": t, "source": "official"})
            return t, "official"
    except Exception:
        pass
    # 抓不到：用旧缓存，再不行用内置
    if c and c.get("table"):
        _MEM.update({"t": c.get("t", 0), "table": c["table"], "source": "cache"})
        return c["table"], "cache"
    _MEM.update({"t": now, "table": BUILTIN, "source": "builtin"})
    return BUILTIN, "builtin"


def prices_for(model):
    t, src = table()
    name = (model or "").strip()
    if name in t:
        return t[name], src
    # 名字对不上（比如换了别名）：退回第一个模型的价格，别让统计崩
    first = next(iter(t.values())) if t else BUILTIN["deepseek-flash"]
    return first, src


def is_peak(now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if now.weekday() >= 5:          # 周六日全时段半价
        return False
    h = now.hour + now.minute / 60.0
    return (1 <= h < 4) or (6 <= h < 10)


def cost(model, usage):
    """按官方口径算一次调用的美元花费；usage 用 API 返回的 usage 字段"""
    if not usage:
        return 0.0
    p, _src = prices_for(model)
    key = "peak" if is_peak() else "off"
    hit = int(usage.get("prompt_cache_hit_tokens") or 0)
    prompt = int(usage.get("prompt_tokens") or 0)
    miss = usage.get("prompt_cache_miss_tokens")
    miss = int(miss) if miss is not None else max(0, prompt - hit)
    out = int(usage.get("completion_tokens") or 0)
    return (hit / 1e6 * p["hit"][key] +
            miss / 1e6 * p["miss"][key] +
            out / 1e6 * p["out"][key])
