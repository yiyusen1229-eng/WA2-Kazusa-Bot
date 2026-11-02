# -*- coding: utf-8 -*-
"""人设 / 世界书（一个功能一个文件）

数据位置（旧版本放在根目录的也认，按顺序回落）：

    persona/base.txt            共用底色（身份 / 性格 / 说话 / 关系 / 不知道）
    persona/stage1~4.txt        当前关系阶段（只注入命中那一份，省 token）
    persona/persona_core.txt    旧的一整份（没有 base/stage 时兜底）
    persona/persona.txt         中文兜底版
    worldbook/worldbook.json    世界书（关键词触发，最多 4 条 / 1200 字）

阶段由 `persona_stage.py` 从最近对话判断，不调用模型；读档时重置。

特别模式导入的 `char/prompt`、`char/worldbook` 优先级更高（由 char_res 读），
这里只管"程序自带的那一份"。

日志：main 启动时用 `set_logger()` 把它的 `log()` 注入进来，避免循环 import。
"""
import json
import os

import char_res
import persona_stage

BASE = os.path.dirname(os.path.abspath(__file__))
PERSONA_DIR = os.path.join(BASE, "persona")
WORLDBOOK_DIR = os.path.join(BASE, "worldbook")
PERSONA_FILE = os.path.join(PERSONA_DIR, "persona.txt")
PERSONA_CORE_FILE = os.path.join(PERSONA_DIR, "persona_core.txt")
PERSONA_BASE_FILE = os.path.join(PERSONA_DIR, "base.txt")
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
        # 人设拆成 base + stageN；「查看文件」打开共用那份，阶段文件在同一个文件夹里
        "prompt": _first_existing(PERSONA_BASE_FILE, PERSONA_CORE_FILE,
                                  LEGACY_PERSONA_CORE_FILE,
                                  PERSONA_FILE, LEGACY_PERSONA_FILE),
        "worldbook": _first_existing(WORLDBOOK_FILE, LEGACY_WORLDBOOK_FILE),
    }


_PERSONA_SRC = {"v": ""}


def _note_persona_src(name):
    """人设来源变了才记一行日志，免得每条消息刷屏"""
    if _PERSONA_SRC["v"] != name:
        _PERSONA_SRC["v"] = name
        _log("人设来源: %s" % name)


def _read(path):
    try:
        return open(path, encoding="utf-8").read().strip()
    except Exception:
        return ""


def persona_text(messages=None):
    """人设：特别模式导入的提示词最优先（char/prompt/）。

    没有导入时用 `persona/base.txt` + 当前阶段那一份（`stage1~4.txt`），
    阶段由 persona_stage 从最近对话判断——只注入命中的那一份，省 token。
    没有拆分文件时，回落到旧的一整份 persona_core / persona.txt。
    """
    try:
        imported = char_res.prompt_text()
    except Exception as e:
        _log("读取导入提示词失败: %s" % e)
        imported = ""
    if imported:
        _note_persona_src("char/prompt")
        return imported

    base = _read(PERSONA_BASE_FILE)
    if base:
        try:
            stage = persona_stage.current(messages or [])
        except Exception as e:
            _log("关系阶段判断失败（按 1 处理）: %s" % e)
            stage = 1
        stage_txt = _read(os.path.join(PERSONA_DIR, "stage%d.txt" % stage))
        if stage_txt:
            _note_persona_src("persona/base+stage%d" % stage)
            return base + "\n\n" + stage_txt
        _note_persona_src("persona/base")
        return base

    # 旧的一整份（兼容没拆分的安装）
    for f in (PERSONA_CORE_FILE, LEGACY_PERSONA_CORE_FILE,
              PERSONA_FILE, LEGACY_PERSONA_FILE):
        t = _read(f)
        if t:
            _note_persona_src(os.path.basename(f))
            return t
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
