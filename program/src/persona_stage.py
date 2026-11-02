# -*- coding: utf-8 -*-
"""关系阶段：云端每 N 轮判断一次，到顶（4）就停。

设计（2026-11-02 按用户要求改）：
    · 不再用本地关键词做日常判断（不准）
    · 每 40 轮对话（一轮 = 一问一答）把最近一段发给云端，只回一个 1~4 的标签
    · 分类在后台线程里跑，不拖慢聊天；结果下一轮生效
    · 只升不降；到 4（婚后 / 同居）就封顶，不再调用
    · 本地关键词只做两件事：命中"结婚/同居"这类明确的 4 直接封顶；
      云端失败时兜底
    · 频率可用 WA2_STAGE_EVERY 环境变量改（默认 40 轮）

状态存在 cache/persona_stage.json，不写存档。
"""
import json
import os
import re
import threading

import memory

STATE_FILE = os.path.join(memory.CACHE_DIR, "persona_stage.json")
EVERY = max(5, int(os.environ.get("WA2_STAGE_EVERY", "40") or 40))
SCAN_CHARS = 6000          # 发给云端的对话上限（从后往前截）
TAIL_ROUNDS = 40           # 每次最多带最近 40 轮

RUBRIC = """你只判断对话里两人关系的进展，只输出一个数字：
1 = 关系初期（双方还在试探，没有明确表示）
2 = 关系升温（有来有往，开始明显亲近）
3 = 关系确认（已经明确表明心意 / 确认关系）
4 = 婚后或同居
只输出 1、2、3、4 中的一个，不要解释，不要标点。"""

MARKERS_4 = ("结婚", "婚礼", "婚后", "同居", "老婆", "老公", "住在一起",
             "搬到", "戒指", "领证", "蜜月")

_LOG = None
_LLM = None
_BUSY = threading.Lock()
_LAST = {"thread": None}


def set_logger(fn):
    global _LOG
    _LOG = fn


def set_llm(fn):
    """注入一个 (system, user) -> 文本 的云端调用；main 启动时设置"""
    global _LLM
    _LLM = fn


def _log(msg):
    if _LOG:
        try:
            _LOG(msg)
        except Exception:
            pass


def _load():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return {
            "stage": int(d.get("stage") or 1),
            "seen": int(d.get("seen") or 0),
            "rounds": int(d.get("rounds") or 0),
            "last_round": int(d.get("last_round") or 0),
        }
    except Exception:
        return {"stage": 1, "seen": 0, "rounds": 0, "last_round": 0}


def _save(st):
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(st, f)
    except Exception:
        pass


def _rounds(messages):
    return sum(1 for m in (messages or []) if m.get("role") == "assistant")


def _transcript(messages):
    """最近 TAIL_ROUNDS 轮的文本，从后往前截到 SCAN_CHARS"""
    lines = []
    for m in (messages or [])[-(TAIL_ROUNDS * 2):]:
        role = "对方" if m.get("role") == "user" else "她"
        lines.append("%s：%s" % (role, (m.get("content") or "").strip()))
    text = "\n".join(lines)
    return text[-SCAN_CHARS:]


def detect_local(messages):
    """只认明确的 4（结婚/同居），其它阶段交给云端"""
    text = "\n".join((m.get("content") or "") for m in (messages or [])[-80:])
    return 4 if any(k in text for k in MARKERS_4) else 0


def _parse_tag(text):
    m = re.search(r"[1-4]", text or "")
    return int(m.group(0)) if m else 0


def classify_now(messages):
    """同步跑一次分类（自测 / 后台线程用）"""
    st = _load()
    if st["stage"] >= 4:
        return 4
    local = detect_local(messages)
    if local >= 4:
        st.update(stage=4, rounds=_rounds(messages), seen=len(messages))
        _save(st)
        return 4
    if not _LLM:
        st.update(seen=len(messages), rounds=_rounds(messages),
                  last_round=_rounds(messages))
        _save(st)
        return st["stage"]
    try:
        out = _LLM(RUBRIC, _transcript(messages))
        tag = _parse_tag(out)
    except Exception as e:
        _log("人设阶段：云端判断失败（保留 %d）: %s" % (st["stage"], e))
        st.update(seen=len(messages), rounds=_rounds(messages),
                  last_round=_rounds(messages))
        _save(st)
        return st["stage"]
    if not tag:
        st.update(seen=len(messages), rounds=_rounds(messages),
                  last_round=_rounds(messages))
        _save(st)
        return st["stage"]
    new = max(st["stage"], tag)
    st.update(stage=new, rounds=_rounds(messages), seen=len(messages),
              last_round=_rounds(messages))
    _save(st)
    if new != st["stage"]:
        _log("人设阶段：→ %d" % new)
    return new


def _classify_async(messages):
    if not _BUSY.acquire(blocking=False):
        return
    try:
        classify_now(messages)
    finally:
        _BUSY.release()


def current(messages):
    """当前阶段（1~4）。到 4 直接返回；够 40 轮就在后台判一次。"""
    messages = messages or []
    st = _load()
    n = len(messages)
    rounds = _rounds(messages)
    if n < st["seen"]:                 # 历史变短：新游戏 / 换档
        st = {"stage": 1, "seen": 0, "rounds": rounds, "last_round": 0}
        _save(st)
    if st["stage"] >= 4:
        return 4
    # 明确的 4：不用等云端
    if detect_local(messages) >= 4:
        st.update(stage=4, seen=n, rounds=rounds)
        _save(st)
        return 4
    # 够轮数就后台判；第一次也按 40 轮来（读档时如果已经够 40 轮会立刻判）
    due = rounds - st["last_round"] >= EVERY
    if due and not _BUSY.locked():
        t = threading.Thread(target=_classify_async, args=(list(messages),), daemon=True)
        _LAST["thread"] = t
        t.start()
    return st["stage"]


def reset():
    """读档 / 新游戏：清掉状态，下一次按新历史重新判"""
    try:
        os.remove(STATE_FILE)
    except OSError:
        pass
