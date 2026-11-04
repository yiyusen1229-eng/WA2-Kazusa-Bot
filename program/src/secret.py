# -*- coding: utf-8 -*-
"""密钥：环境变量优先 + 日志脱敏

为什么要这个：
  `config.json` 里的 `api_key` 是明文。自己用没事，但只要**分享配置、发诊断包、
  录屏、备份到网盘**，key 就跟着出去了。设一个环境变量就能完全不往文件里写。

读 key 的顺序（`main.cloud_cfg()` 里调用）：
    1. 环境变量 `WA2_API_KEY`
    2. 环境变量 `DEEPSEEK_API_KEY`
    3. `config.json` 里的 `api_key`

界面：key 来自环境变量时，`/api/modelcfg` 只返回掩码（`sk-****abcd`）+ `key_from_env`，
所以界面上永远看不到真 key；用户点了保存也不会把掩码写回文件（`main.model_cfg_save` 里挡着）。

日志：`applog.log()` 与 `main.log()` 写之前都过一遍 `redact()`，
把 `sk-...` / `Bearer ...` / `"api_key": "..."` 换成 `***`。对话正文本来就不写日志
（applog 只记请求路径），这里只管「长得像密钥」的东西。
"""
import os
import re

# 按顺序找：先认本项目自己的名字，再认 DeepSeek 官方的习惯名
ENV_KEYS = ("WA2_API_KEY", "DEEPSEEK_API_KEY")

MASK = "****"

# 只认「看起来像密钥」的形状，别把普通单词也抹了
_RE_SK = re.compile(r"\bsk-[A-Za-z0-9_\-]{6,}")
_RE_BEARER = re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.=]{8,}", re.I)
_RE_KV = re.compile(
    r"(\"?(?:api_key|access_token|secret_key|token)\"?\s*[:=]\s*\"?)([A-Za-z0-9_\-\.=]{12,})",
    re.I)


def env_key():
    """环境变量里的 key（没有就是空串）。文件里的那份不会被它覆盖写回。"""
    for name in ENV_KEYS:
        v = (os.environ.get(name) or "").strip()
        if v:
            return v
    return ""


def apply_env(cfg):
    """把环境变量里的 key 盖到配置 dict 上（不改原对象）。

    没有环境变量就原样返回——文件里那份照旧生效，不会被清空。
    """
    k = env_key()
    if not k:
        return cfg
    d = dict(cfg or {})
    d["api_key"] = k
    d["key_from_env"] = True
    return d


def mask(key):
    """给界面看的掩码：`sk-****abcd`（留前缀 3 位 + 末 4 位）"""
    k = (key or "").strip()
    if not k:
        return ""
    if len(k) <= 8:
        return MASK
    return k[:3] + MASK + k[-4:]


def is_masked(key):
    """这个值是不是已经打码了（掩码被当成真 key 写回文件是这里要防的事）"""
    k = key or ""
    return MASK in k or "\u2022" in k          # **** 或界面上的 ••••


def redact(text):
    """把文本里像密钥的部分替换掉；不是字符串就原样返回"""
    if text is None:
        return text
    try:
        s = str(text)
    except Exception:
        return text
    if not s:
        return s
    s = _RE_SK.sub(MASK, s)
    s = _RE_BEARER.sub(lambda m: m.group(1) + MASK, s)
    s = _RE_KV.sub(lambda m: m.group(1) + MASK, s)
    return s


def source():
    """当前 key 从哪儿来：`env` / `file` / ``（只给日志和排查用，不带 key 本身）"""
    if env_key():
        return "env"
    return "file"
