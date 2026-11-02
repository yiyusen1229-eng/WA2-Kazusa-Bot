# -*- coding: utf-8 -*-
"""人设 / 世界书（一个功能一个文件）

数据位置（旧版本放在根目录的也认，按顺序回落）：

    persona/persona_core.txt    每轮注入的精简人设（优先，和训练分布一致）
    persona/persona.txt         完整人设
    worldbook/worldbook.json    世界书（关键词触发，最多 4 条 / 1200 字）

特别模式导入的 `char/prompt`、`char/worldbook` 优先级更高（由 char_res 读），
这里只管"程序自带的那一份"。

日志：main 启动时用 `set_logger()` 把它的 `log()` 注入进来，避免循环 import。
"""
import json
import os

import char_res

BASE = os.path.dirname(os.path.abspath(__file__))
PERSONA_DIR = os.path.join(BASE, "persona")
WORLDBOOK_DIR = os.path.join(BASE, "worldbook")
PERSONA_FILE = os.path.join(PERSONA_DIR, "persona.txt")
PERSONA_CORE_FILE = os.path.join(PERSONA_DIR, "persona_core.txt")
WORLDBOOK_FILE = os.path.join(WORLDBOOK_DIR, "worldbook.json")
# 旧版本在根目录的副本（回落用，不再写入）
LEGACY_PERSONA_FILE = os.path.join(BASE, "persona.txt")
LEGACY_PERSONA_CORE_FILE = os.path.join(BASE, "persona_core.txt")
LEGACY_WORLDBOOK_FILE = os.path.join(BASE, "worldbook.json")

_LOG = None


def set_logger(fn):
    """main 启动时注入日志函数（避免 import main 造成循环依赖）"""
    global _LOG
    _LOG = fn


def _log(msg):
    if _LOG:
        try:
            _LOG(msg)
        except Exception:
            pass


def _first_existing(*paths):
    """按顺序找第一个存在的文件；都不存在就返回第一个（让调用方的 open 报错可控）"""
    for p in paths:
        if p and os.path.exists(p):
            return p
    return paths[0] if paths else ""


def default_paths():
    """程序默认读的（没导入时）人设 / 世界书路径，给「查看文件」和 status 用"""
    return {
        "prompt": _first_existing(PERSONA_CORE_FILE, LEGACY_PERSONA_CORE_FILE,
                                  PERSONA_FILE, LEGACY_PERSONA_FILE),
        "worldbook": _first_existing(WORLDBOOK_FILE, LEGACY_WORLDBOOK_FILE),
    }


_PERSONA_SRC = {"v": ""}


def _note_persona_src(name):
    """人设来源变了才记一行日志，免得每条消息刷屏"""
    if _PERSONA_SRC["v"] != name:
        _PERSONA_SRC["v"] = name
        _log("人设来源: %s" % name)


def persona_text():
    """人设：特别模式导入的提示词最优先（char/prompt/），其次精简人设 persona_core，
    最后才是完整版 persona.txt —— 导入的东西删掉会自动回落，不破坏原文件。"""
    try:
        imported = char_res.prompt_text()
    except Exception as e:
        _log("读取导入提示词失败: %s" % e)
        imported = ""
    if imported:
        _note_persona_src("char/prompt")
        return imported
    # 优先用训练时一致的精简人设(persona_core), 保证训练/推理分布一致
    for f in (PERSONA_CORE_FILE, LEGACY_PERSONA_CORE_FILE,
              PERSONA_FILE, LEGACY_PERSONA_FILE):
        try:
            t = open(f, encoding="utf-8").read().strip()
            if t:
                _note_persona_src(os.path.basename(f))
                return t
        except Exception:
            continue
    _note_persona_src("内置默认")
    return "你是示例角色，说话简短，只用简体中文。"


def load_worldbook():
    """世界书：特别模式导入的 json 优先（char/worldbook/），没有再用 worldbook/ 里的
    worldbook.json（旧安装还在根目录的也认）。char_res 按 mtime 缓存，导入后立刻生效。"""
    try:
        wb = char_res.worldbook()
        if wb:
            return wb
    except Exception as e:
        _log("读取导入世界书失败: %s" % e)
    for f in (WORLDBOOK_FILE, LEGACY_WORLDBOOK_FILE):
        try:
            return json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
    return {"entries": []}


def worldbook_context(messages, depth=None, max_entries=None, max_chars=None):
    """按关键词匹配注入世界书（每轮重读，导入的新世界书立刻生效）"""
    wb = load_worldbook()
    depth = depth or wb.get("scan_depth", 3)
    max_entries = max_entries or wb.get("max_entries", 3)
    max_chars = max_chars or wb.get("max_chars", 1200)
    recent = " ".join((m.get("content") or "") for m in messages[-depth:])
    hits = []
    for e in wb.get("entries", []):
        cs = e.get("case_sensitive", False)
        hay = recent if cs else recent.lower()
        for kw in e.get("keywords", []):
            k = kw if cs else kw.lower()
            if k and k in hay:
                hits.append(e)
                break
    hits.sort(key=lambda e: -e.get("priority", 0))
    hits = hits[:max_entries]
    if not hits:
        return "", []
    parts, names, total = [], [], 0
    for e in hits:
        c = e.get("content", "").strip()
        if not c:
            continue
        if total + len(c) > max_chars:
            break
        parts.append("【%s】\n%s" % (e.get("name", ""), c))
        names.append(e.get("name", ""))
        total += len(c)
    return "\n\n".join(parts), names
