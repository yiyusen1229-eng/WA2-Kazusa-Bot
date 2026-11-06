# -*- coding: utf-8 -*-
"""模型接入抽象层（#24）：一个入口，三种 provider，一套错误与降级。

    from llm import generate, LLMError
    r = generate(payload, cfg, timeout=90, fallback_cfg=local_cfg)
    r.text / r.usage / r.model / r.degraded / r.reason

为什么要有这一层：调用点原来在 `api_chat._chat` 里直接 urllib，错误处理是两段
`except: self._json({"error": ...})` —— 「没余额」和「网线掉了」对用户都是同一句话，
而这两种情况该做的事完全不同（充值 vs 检查 Ollama）。

## provider

`provider_of(base_url)` 从 URL 认：本机 11434 → `ollama`；`/v1/chat/completions` 兼容
→ `openai`；其它 → `custom`（仍然按 OpenAI 形状发，认不出不影响能用）。

## 错误分类（`LLMError.kind`）

| kind | 触发 | 可重试 | 默认降级 |
|---|---|---|---|
| `auth` | 401 / 403 | 否 | 回落本地模型 |
| `balance` | 402 / body 里有 insufficient / 余额 | 否 | 回落本地模型 |
| `rate` | 429 | 是（1 次） | 还不行就回落 |
| `server` | 5xx | 是（1 次） | 还不行就回落 |
| `offline` | 超时 / 连不上 | 是（1 次） | 回落本地模型 |
| `bad_response` | 200 但没 choices / JSON 坏 | 是（1 次） | 还不行就报错 |

`degraded=True` 时调用方要告诉用户「这次用的是本地模型」——静默降级会让人以为
云端模型突然变笨了。

## 预算

`budget_note(cost)` 累加当天花费到 `cache/usage_daily.json`，`budget_status()`
给出今天花了多少、阈值多少、有没有超。阈值来自 `params.BUDGET_DAILY`（默认 0 = 不提醒）。
"""
import json
import os
import time
import urllib.error
import urllib.request

# 每天花费提醒阈值（元）。0 = 不提醒；超过 80% 提醒一次，超过 100% 再提醒一次
BUDGET_DAILY = 0.0

CHAT_PATH = "/v1/chat/completions"
OLLAMA_PORT = ":11434"


class LLMError(Exception):
    """统一错误：调用方只需要看 kind 和 user_message"""

    def __init__(self, kind, message, user_message="", retryable=False, status=0):
        Exception.__init__(self, message)
        self.kind = kind
        self.detail = message
        self.user_message = user_message or message
        self.retryable = retryable
        self.status = status

    def __str__(self):
        return "%s: %s" % (self.kind, self.detail)


class Result(object):
    def __init__(self, text, usage=None, model="", provider="", ms=0,
                 degraded=False, reason="", attempts=1):
        self.text = text
        self.usage = usage or {}
        self.model = model
        self.provider = provider
        self.ms = int(ms)
        self.degraded = degraded
        self.reason = reason
        self.attempts = attempts

    def as_dict(self):
        return {"text": self.text, "usage": self.usage, "model": self.model,
                "provider": self.provider, "ms": self.ms,
                "degraded": self.degraded, "reason": self.reason,
                "attempts": self.attempts}


# ------------------------------------------------------------------ provider
def provider_of(base_url):
    u = (base_url or "").lower()
    if OLLAMA_PORT in u or "ollama" in u:
        return "ollama"
    if "/v1" in u or "openai" in u or "api." in u:
        return "openai"
    return "custom"


def endpoint(base_url):
    """拼出 chat 接口地址（已经带 /v1 的不重复加）"""
    b = (base_url or "").rstrip("/")
    if b.endswith("/v1/chat/completions"):
        return b
    if b.endswith("/v1"):
        return b + "/chat/completions"
    return b + CHAT_PATH


def headers(cfg):
    h = {"Content-Type": "application/json"}
    if (cfg or {}).get("api_key"):
        h["Authorization"] = "Bearer " + cfg["api_key"]
    return h


# ------------------------------------------------------------------ 错误分类
_BALANCE_HINTS = ("insufficient", "balance", "quota", "余额", "欠费", "credit")


def classify_status(code, body=""):
    b = (body or "").lower()
    if code in (401, 403):
        return LLMError("auth", "HTTP %s" % code, "密钥不对或没有权限（设置里换一个 key）",
                        False, code)
    if code == 402 or any(k in b for k in _BALANCE_HINTS):
        return LLMError("balance", "HTTP %s %s" % (code, b[:120]),
                        "账户余额不足（充值，或先切到本地模型）", False, code)
    if code == 429:
        return LLMError("rate", "HTTP 429", "请求太频繁，被限流了", True, code)
    if 500 <= code < 600:
        return LLMError("server", "HTTP %s" % code, "模型服务出错（HTTP %s）" % code, True, code)
    return LLMError("http", "HTTP %s %s" % (code, b[:120]),
                    "模型服务返回 HTTP %s" % code, False, code)


def classify_exc(e):
    if isinstance(e, LLMError):
        return e
    if isinstance(e, urllib.error.HTTPError):
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            body = ""
        return classify_status(e.code, body)
    if isinstance(e, (TimeoutError,)):
        return LLMError("offline", "timeout", "模型没在超时时间内回话（网络慢或服务卡了）", True)
    if isinstance(e, urllib.error.URLError):
        return LLMError("offline", str(e.reason), "连不上模型服务（检查网络 / Ollama 有没有启动）",
                        True)
    return LLMError("unknown", str(e), "调用模型失败：%s" % e, False)


def _extract(d, require_text=True):
    """从响应里取正文：兼容 OpenAI 形状和 Ollama 原生形状"""
    if not isinstance(d, dict):
        raise LLMError("bad_response", "响应不是 JSON 对象", "模型返回的东西看不懂（不是 JSON）", True)
    ch = d.get("choices")
    if isinstance(ch, list) and ch:
        m = ch[0].get("message") or {}
        txt = m.get("content")
        if txt is None:
            txt = (m.get("text") or "")
        if isinstance(txt, list):      # 少数兼容实现把 content 做成片段数组
            txt = "".join((p.get("text") or "") for p in txt if isinstance(p, dict))
        return _finish(txt, d, require_text)
    msg = d.get("message")
    if isinstance(msg, dict) and "content" in msg:
        return _finish(msg.get("content"), d, require_text)
    raise LLMError("bad_response", "没有 choices/message", "模型返回里没有正文", True)


def _finish(txt, d, require_text):
    txt = (txt or "").strip()
    if require_text and not txt:
        # 空正文当成功是最坑的一种「假成功」：实测推理型模型把预算全花在思考上时
        # 会返回 content 为空（reasoning_content 有内容），调用方以为拿到了回复，
        # 于是写出空摘要 / 界面上一个字都不出。
        raise LLMError("bad_response", "content 为空（可能被思考吃掉了预算）",
                       "模型没返回正文（可能把预算花在思考上了，换个模型或调大 max_tokens）", True)
    return txt, d.get("usage") or {}


# ------------------------------------------------------------------ 调用
def post(url, payload, cfg, timeout=90):
    """真正发请求（测试里替换这个函数就能把网络挡在外面）"""
    rq = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                                headers=headers(cfg))
    with urllib.request.urlopen(rq, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def generate(payload, cfg, timeout=90, fallback_cfg=None, retry_pause=0.6, sleep=None):
    """发一次请求；可重试的错误重试一次，再不行按需回落本地模型。

    返回 Result；全部失败抛 LLMError（带用户能看懂的话）。
    """
    sleep = sleep or time.sleep
    cfg = dict(cfg or {})
    url = endpoint(cfg.get("base_url"))
    t0 = time.time()
    attempts = 0
    last = None
    for i in (1, 2):
        attempts = i
        try:
            d = post(url, payload, cfg, timeout)
            text, usage = _extract(d, require_text=True)
            return Result(text, usage, cfg.get("model") or "", provider_of(cfg.get("base_url")),
                          (time.time() - t0) * 1000, False, "", attempts)
        except Exception as e:
            err = classify_exc(e)
            last = err
            if not err.retryable or i == 2:
                break
            sleep(retry_pause)

    if last is None:
        last = LLMError("unknown", "没有尝试", "调用模型失败", False)

    # 降级：本地模型还活着就换过去（只对 auth/balance/offline 这类「换个人还能干」的错）
    if fallback_cfg and last.kind in ("auth", "balance", "offline", "rate", "server"):
        fcfg = dict(fallback_cfg)
        fpayload = dict(payload)
        fpayload["model"] = fcfg.get("model") or payload.get("model")
        fpayload.pop("thinking", None)
        fpayload.pop("reasoning_effort", None)
        try:
            d = post(endpoint(fcfg.get("base_url")), fpayload, fcfg, timeout)
            text, usage = _extract(d, require_text=True)
            return Result(text, usage, fcfg.get("model") or "", provider_of(fcfg.get("base_url")),
                          (time.time() - t0) * 1000, True, last.kind, attempts + 1)
        except Exception as e:
            other = classify_exc(e)
            last.user_message = "%s；本地模型也没成（%s）" % (last.user_message, other.user_message)
    raise last


# ------------------------------------------------------------------ 预算
def _budget_path():
    base = os.environ.get("WA2_CACHE_DIR") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "cache")
    return os.path.normpath(os.path.join(base, "usage_daily.json"))


def _today():
    return time.strftime("%Y-%m-%d")


def budget_status():
    """{date, cost, limit, ratio, over}"""
    try:
        with open(_budget_path(), encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {}
    day = _today()
    if d.get("date") != day:
        d = {"date": day, "cost": 0.0}
    limit = _limit()
    cost = float(d.get("cost") or 0)
    ratio = (cost / limit) if limit > 0 else 0.0
    return {"date": day, "cost": round(cost, 4), "limit": limit,
            "ratio": round(ratio, 3), "over": bool(limit > 0 and cost >= limit)}


def _limit():
    """当天预算上限（元）。环境变量 WA2_BUDGET_DAILY 可以临时覆盖（自测用）"""
    try:
        env = os.environ.get("WA2_BUDGET_DAILY")
        if env not in (None, ""):
            return float(env)
    except Exception:
        pass
    try:
        return float(BUDGET_DAILY or 0)
    except Exception:
        return 0.0


def budget_note(cost):
    """累加今天的花费；返回 budget_status()"""
    try:
        c = float(cost or 0)
    except Exception:
        c = 0.0
    if c <= 0:
        return budget_status()
    p = _budget_path()
    st = budget_status()
    st["cost"] = float(st["cost"]) + c
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"date": st["date"], "cost": round(st["cost"], 6)}, f)
        os.replace(tmp, p)
    except Exception:
        pass
    limit = st["limit"]
    return {"date": st["date"], "cost": round(st["cost"], 4), "limit": limit,
            "ratio": round((st["cost"] / limit) if limit > 0 else 0.0, 3),
            "over": bool(limit > 0 and st["cost"] >= limit)}


def budget_warning(st):
    """给前端一句话；没到 80% 返回空串"""
    if not st or not st.get("limit"):
        return ""
    r = st.get("ratio") or 0
    if st.get("over"):
        return "今天的模型花费已经超过预算（%.2f/%.2f 元），建议切本地模型" % (st["cost"], st["limit"])
    if r >= 0.8:
        return "今天已花 %.0f%% 预算（%.2f/%.2f 元）" % (r * 100, st["cost"], st["limit"])
    return ""
