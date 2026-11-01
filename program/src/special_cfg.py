# -*- coding: utf-8 -*-
"""特别模式 → 存读档设置：读写 memory.json

memory.py 的参数本来就可以用 `memory.json` 覆盖（见 memory.cfg()），
这里只负责那四个能在界面上调的：
    cloud_ctx      模型上下文大小（token）
    trigger_ratio  触发记忆书打包的阈值
    recent_ratio   读档时最多保留的原文比例
    entries_ratio  记忆条目上限比例

文件不存在时按当前值生成一份，所以"默认配置"就是 memory.DEFAULTS。
写入走临时文件 + 原子替换，避免写一半留下坏 JSON。
"""
import json
import os

import memory
import special_files

# 上下文滑条的上限：memory.DEFAULTS 里云端那一档，界面按百分比显示
CTX_MAX = 32000

DEFAULT_NAME = "和纱"
NAME_FILE = os.path.join(special_files.CHAR_DIR, "name.txt")

KEYS = ("cloud_ctx", "trigger_ratio", "recent_ratio", "entries_ratio")

# 滑条能到的最小值：0 会让记忆书彻底不工作，留一点余量
MIN_CTX = 1000
MIN_RATIO = 0.01


def defaults():
    return {k: memory.DEFAULTS[k] for k in KEYS}


def current():
    """当前生效的值（已叠加 memory.json 的覆盖）"""
    c = memory.cfg()
    return {k: c[k] for k in KEYS}


def ensure():
    """没有配置文件就生成一份默认的；返回是否新建"""
    if os.path.exists(memory.CFG_FILE):
        return False
    return _write(current())


def save(payload):
    """合并保存：只覆盖传进来的字段，文件里别的键保持不动"""
    if not isinstance(payload, dict):
        return {"ok": False, "error": "bad body"}
    try:
        patch = _clean(payload)
    except (TypeError, ValueError) as e:
        return {"ok": False, "error": "参数不对: %s" % e}
    if not patch:
        return {"ok": False, "error": "没有可保存的字段"}

    data = {}
    try:
        with open(memory.CFG_FILE, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict):
            data = d
    except Exception:
        pass
    data.update(patch)
    if not _write(data):
        return {"ok": False, "error": "写入失败"}
    return {"ok": True, "cfg": current()}


def _clean(payload):
    out = {}
    if "cloud_ctx" in payload:
        out["cloud_ctx"] = int(max(MIN_CTX, min(CTX_MAX, float(payload["cloud_ctx"]))))
    for k in ("trigger_ratio", "recent_ratio", "entries_ratio"):
        if k in payload:
            v = float(payload[k])
            out[k] = round(max(MIN_RATIO, min(1.0, v)), 4)
    return out


def _write(data):
    try:
        tmp = memory.CFG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, memory.CFG_FILE)
        return True
    except Exception:
        return False


# ------------------------------------------------------------------ 角色名
def get_name():
    """对话框左上角显示的名字：char/name.txt，没有就用默认的「和纱」"""
    try:
        with open(NAME_FILE, encoding="utf-8") as f:
            name = f.read().strip()
        if name:
            return name
    except Exception:
        pass
    return DEFAULT_NAME


def set_name(name):
    name = (name or "").strip()
    if not name:
        return {"ok": False, "error": "名字不能为空"}
    if len(name) > 12:
        return {"ok": False, "error": "名字最长 12 个字"}
    try:
        os.makedirs(os.path.dirname(NAME_FILE), exist_ok=True)
        tmp = NAME_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(name)
        os.replace(tmp, NAME_FILE)
    except Exception as e:
        return {"ok": False, "error": "写入失败: %s" % e}
    return {"ok": True, "name": name}

