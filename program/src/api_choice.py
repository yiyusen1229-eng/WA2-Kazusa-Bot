# -*- coding: utf-8 -*-
"""选择分支：让对话模型根据当前对话给出 2~5 个玩家可选行动（galgame 那种分歧）。

    POST /api/choice {"count": 2, "messages": [{"role","content"}, ...]}
      → {"ok": true, "options": ["放开手", "把脸背过去"], "count": 2}

为什么单独一个接口、而不是塞进 /api/chat：
  · 选项要「短、可点」，和正文回复是两种输出，混在一起容易把选项写进台词里；
  · 生成选项时不带人设大提示，只给最近几轮对话 —— 省 token，也不让模型开始演她。
"""
import json
import re
import urllib.request

import applog

MAX_COUNT = 5
MIN_COUNT = 2
KEEP_MSGS = 8              # 只看最近 8 条，够判断语境
MAX_TOKENS = 400
TIMEOUT_S = 25

PROMPT = (
    "你是 galgame（视觉小说）的编剧。根据下面这段对话，给出 {n} 个玩家此刻可以做的选择，"
    "要能明显把故事带向不同方向。\n"
    "要求：\n"
    "1. 每行一个，只写选项本身（第一人称的动作或一句短台词），不要编号、不要解释；\n"
    "2. 每个 4~14 个汉字，像游戏里的选项那样短；\n"
    "3. 不要写成她的台词，写「玩家（北原春希）会做的事」；\n"
    "4. 风格要和上下文一致（亲密 / 日常 / 争执），不要突然转成别的气氛。\n"
    "只输出 {n} 行。"
)

# 行首可能带的编号/项目符号：1. 1、 1) - ・ ①
_BULLET = re.compile(r"^\s*(?:[0-9１-５]+[\.、\)．:：]|[-–—・*·]+|[①-⑤])\s*")
_QUOTES = "「」『』\"'“”‘’"


def clean_option(s):
    """把一行收拾成纯选项文本"""
    t = (s or "").strip()
    t = _BULLET.sub("", t).strip()
    t = t.strip(_QUOTES).strip()
    t = re.sub(r"\s+", " ", t)
    return t


def parse_options(text, count=MIN_COUNT):
    """模型输出 → 选项列表（去编号、去空行、去重复、截到 count 个）"""
    n = max(MIN_COUNT, min(MAX_COUNT, int(count or MIN_COUNT)))
    out, seen = [], set()
    for line in (text or "").split("\n"):
        t = clean_option(line)
        if not t or len(t) < 2 or len(t) > 30:
            continue
        k = t.replace("…", "").replace("。", "")
        if k in seen:
            continue
        seen.add(k)
        out.append(t)
        if len(out) >= n:
            break
    return out


def _cloud_cfg():
    """复用主程序的云端配置（和翻译层同一套 key/base/model）"""
    try:
        import main
        cfg = main.cloud_cfg() or {}
    except Exception:
        cfg = {}
    return {"key": cfg.get("api_key") or cfg.get("key") or "",
            "base": (cfg.get("base_url") or cfg.get("base") or "").rstrip("/"),
            "model": cfg.get("model") or ""}


def _recent(messages):
    """压成「角色：内容」的几行，只要正文"""
    rows = []
    for m in (messages or [])[-KEEP_MSGS:]:
        if not isinstance(m, dict):
            continue
        role = "玩家" if m.get("role") == "user" else "和纱"
        txt = (m.get("content") or "").strip()
        if not txt:
            continue
        rows.append("%s：%s" % (role, txt[:200]))
    return "\n".join(rows)


def generate(messages, count=MIN_COUNT):
    """调云端模型生成选项；失败返回 ([], 错误)"""
    n = max(MIN_COUNT, min(MAX_COUNT, int(count or MIN_COUNT)))
    cfg = _cloud_cfg()
    if not (cfg["key"] and cfg["base"] and cfg["model"]):
        return [], "没配云端模型"
    ctx = _recent(messages)
    if not ctx:
        return [], "没有可参考的对话"
    payload = {
        "model": cfg["model"],
        "messages": [{"role": "system", "content": PROMPT.format(n=n)},
                     {"role": "user", "content": ctx}],
        "stream": False,
        "max_tokens": MAX_TOKENS,
        "reasoning_effort": "none",
    }
    try:
        rq = urllib.request.Request(
            cfg["base"] + "/v1/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + cfg["key"]})
        with urllib.request.urlopen(rq, timeout=TIMEOUT_S) as r:
            d = json.loads(r.read().decode("utf-8"))
        raw = ((d["choices"][0].get("message") or {}).get("content") or "").strip()
    except Exception as e:
        applog.log("选择分支：模型调用失败 %s" % e, "WARN")
        return [], str(e)[:80]
    opts = parse_options(raw, n)
    if len(opts) < MIN_COUNT:
        return [], "模型没给出够多的选项"
    return opts, ""


class ChoiceApi:
    """见 main.Handler。"""

    def _choice(self):
        try:
            body = self._body()
        except Exception as e:
            return self._json({"ok": False, "error": "bad body: %s" % e}, 400)
        if not isinstance(body, dict):
            return self._json({"ok": False, "error": "bad body"}, 400)
        try:
            count = int(body.get("count") or MIN_COUNT)
        except Exception:
            count = MIN_COUNT
        opts, err = generate(body.get("messages") or [], count)
        if err:
            return self._json({"ok": False, "error": err, "options": []})
        return self._json({"ok": True, "options": opts, "count": len(opts)})
