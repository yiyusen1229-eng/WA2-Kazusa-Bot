# -*- coding: utf-8 -*-
"""人设 / 世界书（一个功能一个文件）

数据位置（旧版本放在根目录的也认，按顺序回落）：

    persona/base.txt            共用底色（身份 / 性格 / 说话 / 关系 / 不知道）
    persona/stage1~4.txt        当前关系阶段（只注入命中那一份，省 token）
    persona/persona_core.txt    旧的一整份（没有 base/stage 时兜底）
    persona/persona.txt         中文兜底版
    worldbook/worldbook.json    世界书（关键词触发，最多 4 条 / 1200 字）

阶段由 `persona_stage.py` 从最近对话判断，不调用模型；读档时重置。

特别模式导入的提示词 / 世界书在**当前角色文件夹**里（characters/<角色>/prompt|worldbook/），
优先级更高（由 char_res 读），这里只管"程序自带的那一份"。

日志：main 启动时用 `set_logger()` 把它的 `log()` 注入进来，避免循环 import。
"""
import json
import os

import char_res
import characters
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

# 世界书默认值（worldbook.json 里没写这几项时用它；#12 集中在这里，表见 参数与指标.md）
WB_DEFAULT_DEPTH = 3        # 只看最近几条消息做关键词匹配
WB_DEFAULT_ENTRIES = 3      # 每轮最多注入几条
WB_DEFAULT_CHARS = 1200     # 每轮最多注入多少字

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


def prompt_dir():
    """人设目录：当前角色文件夹的 prompt/（里面有东西就用它），否则程序自带的 persona/

    两种情况都支持：base.txt + stageN.txt（分关系阶段），或整份的 persona_core/persona.txt。
    """
    try:
        d = os.path.join(characters.active_dir(), "prompt")
    except Exception:
        d = ""
    if d and os.path.isdir(d):
        for name in ("base.txt", "persona_core.txt", "persona.txt", "stage1.txt"):
            if os.path.isfile(os.path.join(d, name)):
                return d
    return PERSONA_DIR


def worldbook_file():
    """世界书文件：当前角色文件夹里的优先，没有再用程序自带的"""
    try:
        d = os.path.join(characters.active_dir(), "worldbook", "worldbook.json")
        if os.path.isfile(d):
            return d
    except Exception:
        pass
    return _first_existing(WORLDBOOK_FILE, LEGACY_WORLDBOOK_FILE)


def default_paths():
    """当前实际读的人设 / 世界书路径（给「查看文件」和 status 用）

    自包含之后这两份都在角色文件夹里；角色文件夹是空的才回落到程序自带的。
    """
    pd = prompt_dir()
    return {
        # 人设拆成 base + stageN；「查看文件」打开共用那份，阶段文件在同一个文件夹里
        "prompt": _first_existing(
            os.path.join(pd, "base.txt"),
            os.path.join(pd, "persona_core.txt"),
            os.path.join(pd, "persona.txt"),
            PERSONA_BASE_FILE, PERSONA_CORE_FILE, LEGACY_PERSONA_CORE_FILE,
            PERSONA_FILE, LEGACY_PERSONA_FILE,
        ),
        "worldbook": worldbook_file(),
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


PERIOD_LABELS = {
    "ic": "IC（高中篇）",
    "cc": "CC（大学/出道篇）",
    "coda": "CODA（成年篇）",
}


def period_of(outfit=""):
    """按当前衣服名判断时期；认不出来按 IC（新游戏默认校服）"""
    s = (outfit or "").strip()
    low = s.lower()
    if low in PERIOD_LABELS:
        return low
    if s.startswith("CC") or low.startswith("cc"):
        return "cc"
    if (s.startswith("coda") or low.startswith("coda") or s.startswith("CODA")
            or s.startswith("婚后") or s.startswith("睡衣") or s.startswith("礼服")):
        return "coda"
    if s.startswith(("高中", "舞台", "学园祭", "浴衣", "和服", "打工")):
        return "ic"
    # 兜底：只拿到编号时（前端通常发衣服名，不会走到这里）
    if s in ("013", "014", "016", "017"):
        return "cc"
    return "ic"


def _period_overlay(period):
    """时期补丁：persona_ic.txt / persona_cc.txt / persona_coda.txt"""
    p = (period or "").strip().lower()
    if p not in PERIOD_LABELS:
        return ""
    pd = prompt_dir()
    for name in ("persona_%s.txt" % p, "persona_core_%s.txt" % p):
        t = _read(os.path.join(pd, name))
        if t:
            return t
    return ""


def persona_text(messages=None, period=None):
    """人设：特别模式导入的提示词最优先（当前角色文件夹的 prompt/）。

    否则用角色文件夹里的 `base.txt` + 当前阶段那一份（`stage1~4.txt`）——
    角色文件夹是空的才回落到程序自带的 persona/。阶段由 persona_stage 从最近对话判断，
    只注入命中的那一份，省 token。没有拆分文件时，用整份的 persona_core / persona.txt。

    period 给 ic / cc / coda 时，会在人设最后追加 `persona_<period>.txt` 的时期补丁；
    补丁里写明「最高优先级」，用来覆盖基础人设里不属于当前时期的身份/时间。
    """
    base = ""
    try:
        imported = char_res.prompt_text()
    except Exception as e:
        _log("读取导入提示词失败: %s" % e)
        imported = ""
    if imported:
        _note_persona_src("角色文件夹的提示词")
        base = imported
    else:
        for d in (prompt_dir(), PERSONA_DIR):
            b = _read(os.path.join(d, "base.txt"))
            if not b:
                continue
            try:
                stage = persona_stage.current(messages or [])
            except Exception as e:
                _log("关系阶段判断失败（按 1 处理）: %s" % e)
                stage = 1
            stage_txt = _read(os.path.join(d, "stage%d.txt" % stage))
            if stage_txt:
                _note_persona_src("%s/base+stage%d" % (os.path.basename(os.path.dirname(d)), stage))
                base = b + "\n\n" + stage_txt
            else:
                _note_persona_src("%s/base" % os.path.basename(os.path.dirname(d)))
                base = b
            break

        if not base:
            # 整份的（兼容没拆分的安装 / 只放了一份提示词的角色）
            pd = prompt_dir()
            for f in (os.path.join(pd, "persona_core.txt"), os.path.join(pd, "persona.txt"),
                      PERSONA_CORE_FILE, LEGACY_PERSONA_CORE_FILE,
                      PERSONA_FILE, LEGACY_PERSONA_FILE):
                t = _read(f)
                if t:
                    _note_persona_src(os.path.basename(f))
                    base = t
                    break
        if not base:
            _note_persona_src("内置默认")
            base = "你是示例角色，说话简短，只用简体中文。"

    # 说话风格摘句（可选）：prompt/style.txt。从原作按情境摘出来的句子，
    # 只学语气不照抄；有就拼在阶段之后，没有就当不存在。
    try:
        _style = _read(os.path.join(prompt_dir(), "style.txt"))
    except Exception:
        _style = ""
    if _style and _style not in base:
        _note_persona_src("%s + 风格摘句" % _PERSONA_SRC["v"])
        base = base + "\n\n" + _style

    p = (period or "").strip().lower()
    ov = _period_overlay(p)
    if ov:
        _note_persona_src("%s + 时期:%s" % (_PERSONA_SRC["v"], p))
        base = base + "\n\n" + ov
    return base


def loads_tolerant(raw):
    """宽容地解析 JSON：允许末尾有多余内容。

    手工编辑 worldbook.json 很容易在最后多一行（实测多了一个「xx」），
    严格的 json.load 会抛 Extra data —— 原来的写法是 except 后静默回落，
    结果**整本世界书一条都不注入**，而且没有任何报错。
    这里改成：先严格解析；失败就用 raw_decode 吃掉第一个完整值，剩下的当垃圾记日志。
    """
    try:
        return json.loads(raw)
    except Exception:
        pass
    try:
        d, end = json.JSONDecoder().raw_decode(raw.lstrip())
        junk = raw.lstrip()[end:].strip()
        if junk:
            _log("JSON 末尾有多余内容（%d 字符，已忽略）：%r" % (len(junk), junk[:24]))
        return d
    except Exception as e:
        _log("JSON 解析失败：%s" % e)
        raise


def load_worldbook():
    """世界书：当前角色文件夹的 worldbook/ 优先，没有再用程序自带的 worldbook/
    （旧安装还在根目录的也认）。char_res 按 mtime 缓存，导入后立刻生效。"""
    try:
        wb = char_res.worldbook()
        if wb:
            return wb
    except Exception as e:
        _log("读取导入世界书失败: %s" % e)
    for f in (worldbook_file(), WORLDBOOK_FILE, LEGACY_WORLDBOOK_FILE):
        try:
            with open(f, encoding="utf-8") as fh:
                return loads_tolerant(fh.read())
        except Exception:
            continue
    return {"entries": []}


def worldbook_context(messages, depth=None, max_entries=None, max_chars=None, period=None):
    """按关键词匹配注入世界书（每轮重读，导入的新世界书立刻生效）

    period=ic/cc/coda 时，只注入通用条目和当前时期的条目；
    条目的 period 字段可以是 ic / cc / coda / all。
    """
    wb = load_worldbook()
    depth = depth or wb.get("scan_depth", WB_DEFAULT_DEPTH)
    max_entries = max_entries or wb.get("max_entries", WB_DEFAULT_ENTRIES)
    max_chars = max_chars or wb.get("max_chars", WB_DEFAULT_CHARS)
    recent = " ".join((m.get("content") or "") for m in messages[-depth:])
    p = (period or "").strip().lower() or None
    hits = []
    for e in wb.get("entries", []):
        ep = (e.get("period") or "").strip().lower()
        if ep and ep != "all" and p and ep != p:
            continue
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
