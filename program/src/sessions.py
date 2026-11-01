# -*- coding: utf-8 -*-
"""存档读写：sessions/<slot>.json

从 main.py 拆出来的独立模块，对外只有四个函数：
    session_save(data)   存
    session_load(slot)   读
    session_list()       列表（不含缩略图本体）
    session_thumb(slot)  缩略图 JPEG 字节
"""
import base64
import json
import os
import time

SESS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sessions")


def _sess_path(slot):
    """槽位号 → 文件路径（只保留安全字符，避免路径穿越）"""
    safe = "".join(c for c in str(slot or "auto") if c.isalnum() or c in "-_")[:32]
    return os.path.join(SESS_DIR, (safe or "auto") + ".json")


def session_save(data):
    try:
        slot = data.get("slot") or "auto"
        payload = {
            "slot": slot,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            # 日记必须完整：这里**不裁剪**，回想界面翻的就是这份
            "messages": data.get("messages") or [],
            "meta": data.get("meta") or {},
        }
        # 记忆书（可选）：有就原样存，没有就不写 —— 旧档照样能读
        mem = data.get("memory")
        if isinstance(mem, dict):
            payload["memory"] = mem
        os.makedirs(SESS_DIR, exist_ok=True)
        path = _sess_path(slot)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)          # 原子替换，写一半断电不会毁掉旧档
        _SESS_CACHE.pop(os.path.basename(path), None)
        return {"ok": True, "slot": slot, "count": len(payload["messages"]),
                "saved_at": payload["saved_at"]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def session_patch_memory(slot, mem, expect_saved_at=None):
    """只更新某个存档的 memory 字段（后台生成摘要后写回）。

    如果期间玩家又存过一次档（saved_at 变了），就放弃这次写回 ——
    宁可少一次记忆，也不能把新存档的内容覆盖成旧的。
    """
    try:
        path = _sess_path(slot)
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        if expect_saved_at and d.get("saved_at") != expect_saved_at:
            return False
        d["memory"] = mem
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
        _SESS_CACHE.pop(os.path.basename(path), None)
        return True
    except Exception:
        return False


def session_load(slot="auto"):
    try:
        path = _sess_path(slot)
        if not os.path.exists(path):
            return {"ok": False, "error": "no such slot"}
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return dict(ok=True, **d)
    except Exception as e:
        return {"ok": False, "error": str(e)}


_SESS_CACHE = {}      # 文件名 -> (mtime, 摘要)：避免每次开界面都把上百个存档全解析一遍


def _session_brief(path, fname):
    """读一个存档，只取槽位要显示的那点信息（不含缩略图本体）"""
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return None
    hit = _SESS_CACHE.get(fname)
    if hit and hit[0] == mt:
        return hit[1]
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        msgs = d.get("messages") or []
        preview = ""
        for m in reversed(msgs):
            if m.get("role") == "assistant":
                t = (m.get("zh") or m.get("content") or "").strip()
                if t:
                    preview = t
                    break
        meta = d.get("meta") or {}
        rec = {"slot": d.get("slot"), "saved_at": d.get("saved_at"),
               "count": len(msgs), "preview": preview[:60],
               "bg": meta.get("bg", ""),
               # 缩略图不塞进列表：只报有没有，本体走 /api/session/thumb
               "thumb": bool(meta.get("thumb"))}
        _SESS_CACHE[fname] = (mt, rec)
        return rec
    except Exception:
        return None


def session_list():
    try:
        os.makedirs(SESS_DIR, exist_ok=True)
        out = []
        for f in sorted(os.listdir(SESS_DIR)):
            if not f.endswith(".json"):
                continue
            rec = _session_brief(os.path.join(SESS_DIR, f), f)
            if rec:
                out.append(rec)
        return {"ok": True, "slots": out}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def session_thumb(slot):
    """槽位缩略图（JPEG 字节）；没有就返回 None"""
    try:
        path = _sess_path(slot)
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        t = (d.get("meta") or {}).get("thumb") or ""
        if not t.startswith("data:image"):
            return None
        return base64.b64decode(t.split(",", 1)[1])
    except Exception:
        return None
