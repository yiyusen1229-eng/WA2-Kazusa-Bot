# -*- coding: utf-8 -*-
"""常驻记忆书两段化 + 随关系阶段低频刷新（#3）。

以前：`memory/*.txt` 是静态文本，每轮原样注入。长期对话之后会和对话记忆书「语义漂移」——
设定里还写着「刚认识」，记忆条目里已经住一起了，模型两边都能看到，容易精神分裂。

现在：角色文件夹里多一份 `memory/standing.json`：

    {"version": 1,
     "fixed": "固定设定（用户写的，程序不改）",
     "relation_summary": "关系摘要（阶段切换时刷新，几行短句）",
     "stage": 3, "updated_at": "2026-11-05 15:20:00", "source_msgs": 88}

规矩：
  · **fixed 是用户的**：文件不存在时从 `memory/*.txt` 抄一份，之后程序绝不改写它。
  · `relation_summary` 只在**关系阶段变化**时刷新，且**每个阶段最多一次**（stage 记在文件里）；
    阶段 1（刚认识）不生成——那时候没有「进展」可写。
  · 刷新在后台线程里跑；失败保留旧版并记 WARN、**同一阶段冷却半小时**再试；绝不阻塞对话。
  · 文件不存在 / 坏了 → 回落到老的 `char_res.memory_text()`（注入内容和以前完全一样）。

对外：
    load()                   → dict | None（有效就返回；坏了返回 None）
    text(fallback=None)      → 注入用的一段文本（fixed + 关系摘要，没文件就回落老文本）
    note(stage, messages)    → 阶段变了才在后台刷一次；返回是否触发
    build(messages, stage)   → 同步刷一次（自测 / 手动）
    status()                 → 面板 / `/api/memory` 用：有没有文件、阶段、更新时间
    set_llm(fn)              → 注入 (prompt) -> 文本
"""
import json
import os
import threading
import time

import applog
import characters

VERSION = 1
MAX_SUMMARY_CHARS = 600          # 摘要总长上限（每轮都进去，别写长）
MAX_LINE_CHARS = 80              # 单行上限
MAX_LINES = 6                    # 最多几行
MAX_INPUT_CHARS = 3000           # 送给模型的对话上限（从后往前截）
MIN_STAGE = 2                    # 阶段 1（刚认识）没什么可总结的，等关系动过再生成
RETRY_COOLDOWN_S = 1800          # 同一阶段失败过就等半小时再试，别每轮都打模型

PROMPT = """你只做一件事：用 3~6 行短句，写清楚「两人关系现在到哪一步」。
要求：
- 每行以「- 」开头，一行一件事，不要空行、不要标题、不要解释、不要引号。
- 写已经发生的事、现在的称呼和态度、还没解决的疙瘩。
- 不要编造没发生过的事；拿不准就写得更轻。
当前关系阶段：%d（1=刚认识，2=开始亲近，3=确认关系，4=婚后/同居）。

对话记录：
%s"""

_LOCK = threading.Lock()
_BUSY = threading.Lock()
_LLM = None
_WARNED = set()
_TRY = {"stage": 0, "at": 0.0, "ok": False}   # 最近一次尝试（失败后冷却，别每轮都打模型）


def set_llm(fn):
    """注入 (prompt) -> 文本 的模型调用；main 启动时设置"""
    global _LLM
    _LLM = fn


def _dir():
    d = characters.active_dir()
    return os.path.join(d, "memory") if d else ""


def path():
    d = _dir()
    return os.path.join(d, "standing.json") if d else ""


def _warn_once(key, msg):
    if key in _WARNED:
        return
    _WARNED.add(key)
    try:
        applog.log(msg, "WARN")
    except Exception:
        pass


def load():
    """读 standing.json；没有或坏了都返回 None（坏的那份不删，留着人工看）"""
    p = path()
    if not p or not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
    except Exception as e:
        _warn_once("bad", "常驻记忆书：standing.json 读不了（回落到 memory/*.txt）：%s" % e)
        return None
    if not isinstance(d, dict):
        _warn_once("shape", "常驻记忆书：standing.json 结构不对（回落到 memory/*.txt）")
        return None
    return {
        "version": int(d.get("version") or 0),
        "fixed": str(d.get("fixed") or ""),
        "relation_summary": str(d.get("relation_summary") or ""),
        "stage": int(d.get("stage") or 0),
        "updated_at": str(d.get("updated_at") or ""),
        "source_msgs": int(d.get("source_msgs") or 0),
    }


def text(fallback=None):
    """注入用的一段文本：fixed + 关系摘要；没有 standing.json 就回落老文本"""
    d = load()
    if d:
        parts = []
        fixed = (d.get("fixed") or "").strip()
        rel = (d.get("relation_summary") or "").strip()
        if fixed:
            parts.append(fixed)
        if rel:
            parts.append("【我们之间现在的进展（摘要，不是原文）】\n" + rel)
        if parts:
            return "\n\n".join(parts)
    if fallback is not None:
        return fallback
    try:
        import char_res
        return char_res.memory_text() or ""
    except Exception:
        return ""


def status():
    """给面板 / 接口看的：有没有两段化、当前阶段、上次更新时间"""
    d = load()
    p = path()
    out = {"file": p, "exists": bool(d), "two_part": bool(d),
           "stage": (d or {}).get("stage", 0),
           "updated_at": (d or {}).get("updated_at", ""),
           "fixed_chars": len(((d or {}).get("fixed") or "").strip()),
           "summary_chars": len(((d or {}).get("relation_summary") or "").strip())}
    if not d:
        out["hint"] = "还没有 standing.json；关系阶段第一次变化时会自动生成（fixed 从 memory/*.txt 抄一份）"
    return out


# ------------------------------------------------------------------ 摘要

def _clean(raw):
    """把模型输出收拾成 3~6 行、每行 ≤80 字、总共 ≤600 字"""
    lines = []
    for line in (raw or "").splitlines():
        t = line.strip().strip("`")
        for pre in ("- ", "-", "· ", "·", "* ", "*", "• "):
            if t.startswith(pre):
                t = t[len(pre):].strip()
                break
        t = t.strip().strip("「」\"'“”")
        if not t:
            continue
        if len(t) > MAX_LINE_CHARS:
            t = t[:MAX_LINE_CHARS]
        lines.append(t)
        if len(lines) >= MAX_LINES:
            break
    out = "\n".join("- " + t for t in lines)
    if len(out) > MAX_SUMMARY_CHARS:
        out = out[:MAX_SUMMARY_CHARS].rstrip()
    return out


def _transcript(messages):
    lines = []
    for m in (messages or [])[-60:]:
        role = "对方" if (m or {}).get("role") == "user" else "她"
        lines.append("%s：%s" % (role, ((m or {}).get("content") or "").strip()))
    text = "\n".join(lines)
    return text[-MAX_INPUT_CHARS:]


def build(messages, stage, fixed=None):
    """同步刷一次（自测 / 手动）。返回新的 dict；失败返回 None（旧文件不动）。"""
    if not _LLM:
        return None
    p = path()
    if not p:
        return None
    old = load() or {}
    if fixed is None:
        fixed = old.get("fixed") or ""
        if not fixed:
            try:
                import char_res
                fixed = (char_res.memory_text() or "").strip()
            except Exception:
                fixed = ""
    try:
        raw = _LLM(PROMPT % (int(stage), _transcript(messages)))
    except Exception as e:
        _warn_once("llm", "常驻记忆书：关系摘要刷新失败（保留旧版）：%s" % e)
        return None
    summary = _clean(raw)
    if not summary:
        _warn_once("empty", "常驻记忆书：模型没给出可用的关系摘要（保留旧版）")
        return None
    now = {"version": VERSION, "fixed": fixed, "relation_summary": summary,
           "stage": int(stage), "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "source_msgs": len(messages or [])}
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(now, f, ensure_ascii=False, indent=1)
        os.replace(tmp, p)
    except Exception as e:
        _warn_once("write", "常驻记忆书：写 standing.json 失败（保留旧版）：%s" % e)
        return None
    try:
        applog.log("常驻记忆书：阶段 %d 的关系摘要已更新（%d 字）"
                   % (int(stage), len(summary)), "MEM")
    except Exception:
        pass
    return now


def _refresh(messages, stage):
    if not _BUSY.acquire(blocking=False):
        return
    try:
        _TRY["stage"] = stage
        _TRY["at"] = time.time()
        _TRY["ok"] = build(messages, stage) is not None
    finally:
        _BUSY.release()


def note(stage, messages):
    """关系阶段变了 → 后台刷一次（每个阶段最多一次）。返回是否触发。

    · 阶段 1（刚认识）不生成：那时候没有「进展」可写。
    · 同一阶段失败过一次就冷却半小时，避免每轮都打模型。
    """
    if not _LLM:
        return False
    try:
        stage = int(stage or 1)
    except Exception:
        stage = 1
    cur = load()
    if cur and int(cur.get("stage") or 0) == stage:
        return False                       # 这个阶段已经刷过
    if not cur and stage < MIN_STAGE:
        return False                       # 还没有 file，而且关系还没动过
    if (_TRY["stage"] == stage and not _TRY["ok"]
            and time.time() - _TRY["at"] < RETRY_COOLDOWN_S):
        return False                       # 这个阶段刚失败过，等冷却
    if _BUSY.locked():
        return False                       # 上一次还在跑，不排队
    t = threading.Thread(target=_refresh, args=(list(messages or []), stage),
                         name="standing-refresh", daemon=True)
    t.start()
    return True


def wait(seconds=5.0):
    """自测用：等后台刷新线程结束"""
    t0 = time.time()
    while _BUSY.locked() and time.time() - t0 < seconds:
        time.sleep(0.02)
    # 线程刚起来还没拿到锁的情况
    time.sleep(0.05)
    return not _BUSY.locked()
