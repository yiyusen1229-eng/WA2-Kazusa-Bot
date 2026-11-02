# -*- coding: utf-8 -*-
"""关系阶段判断：只读最近对话 + 本地缓存，**不调用模型**。

为什么不用模型判断：那要额外一次调用（或把四个阶段都塞给模型），
比直接注入四个阶段还贵；这里用关键词 + 单调递进，够用且免费。

阶段：
    1 还没敞开   2 开始松动   3 完全敞开（表白之后）   4 婚后 / 同居

规则：
    · 只扫最近 40 条消息（用户说的是中文，命中中文关键词）
    · 阶段只升不降；但如果消息数明显变少（新游戏 / 读档），就重新判断
    · 状态存在 cache/persona_stage.json，不污染存档
"""
import json
import os

import memory

STATE_FILE = os.path.join(memory.CACHE_DIR, "persona_stage.json")
SCAN = 40

# 越往后越亲密；命中就取最靠后的阶段
MARKERS = (
    (4, ("结婚", "婚礼", "婚后", "同居", "老婆", "老公", "住在一起",
         "搬到", "戒指", "领证", "蜜月")),
    (3, ("表白", "告白", "喜欢你", "我爱你", "爱你", "交往",
         "女朋友", "男朋友", "亲我", "吻我", "做我的")),
    (2, ("想你", "别走", "陪我", "抱抱", "撒娇", "吃醋")),
)


def _load():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return int(d.get("stage") or 1), int(d.get("seen") or 0)
    except Exception:
        return 0, 0


def _save(stage, seen):
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"stage": int(stage), "seen": int(seen)}, f)
    except Exception:
        pass


def detect(messages):
    """只看文本，返回命中的最高阶段；没命中返回 0"""
    text = "\n".join((m.get("content") or "") for m in messages[-SCAN:])
    if not text:
        return 0
    for stage, keys in MARKERS:
        if any(k in text for k in keys):
            return stage
    return 0


def current(messages):
    """当前阶段（1~4）。会顺带把阶段记到缓存，供下一次参考。"""
    saved, seen = _load()
    n = len(messages or [])
    det = detect(messages or [])
    if n < seen:                     # 历史变短：新游戏 / 换了档
        stage = det or 1
    else:
        stage = max(saved or 1, det or 1)
    if stage != saved or n != seen:
        _save(stage, n)
    return stage


def reset():
    """读档 / 新游戏时调一下：下一次按新的历史重新判断"""
    try:
        os.remove(STATE_FILE)
    except OSError:
        pass
