# -*- coding: utf-8 -*-
"""/api/memory：记忆书查看 / 删除条目

记忆书分两半，界面上也分两块显示：

  · **常驻记忆书**（`characters/<角色>/memory/*.txt`）——角色设定，只读。
    要改就回「特别模式 → 记忆书 → 导入文件」，这里不碰文件。
  · **对话记忆书**（`memory.runtime()` 的 entries）——对话超阈值后自动压出来的短句。
    这里可以删：删掉的只是「这一轮不再注入」，存档里那份快照不动，下次读档会回来。

条目结构见 memory.py：`{"text": ..., "kind": "preference|event|progress", "from": [起, 止]}`
`from` 是它在对话里的覆盖区间，界面上只用来提示「这条概括了哪几句」。
"""

import memory
import char_res

KIND_LABEL = {"preference": "偏好", "event": "事件", "progress": "进度"}


def _entry(i, e):
    if not isinstance(e, dict):
        return None
    text = (e.get("text") or "").strip()
    if not text:
        return None
    kind = (e.get("kind") or "").strip()
    return {
        "i": i,
        "text": text,
        "kind": kind,
        "label": KIND_LABEL.get(kind, "其他"),
        "from": e.get("from") or [],
    }


def view():
    """给界面用的一份快照（只读，不改任何状态）"""
    r = memory.runtime()
    entries = []
    for i, e in enumerate(r.get("entries") or []):
        v = _entry(i, e)
        if v:
            entries.append(v)

    standing_text = ""
    standing_file = ""
    try:
        standing_text = (char_res.memory_text() or "").strip()
        st = (char_res.status() or {}).get("memory") or {}
        standing_file = st.get("file") or ""
    except Exception:
        pass

    hint = ""
    if not entries:
        hint = "还没有自动摘要。对话变长、超过阈值之后才会生成记忆条目；现在发给模型的还是原文。"

    return {
        "ok": True,
        "entries": entries,
        "count": len(entries),
        "covered": int(r.get("covered") or 0),
        "turns": int(r.get("turns") or 0),
        "updated_at": r.get("updated_at") or "",
        "hint": hint,
        "standing": {
            "file": standing_file,
            "chars": len(standing_text),
            "text": standing_text,
        },
    }


def delete(index):
    """删掉运行时记忆书里的第 index 条（只影响这一轮注入，不改存档）"""
    try:
        i = int(index)
    except Exception:
        return {"ok": False, "error": "索引不对"}
    r = memory.runtime()
    ents = list(r.get("entries") or [])
    if i < 0 or i >= len(ents):
        return {"ok": False, "error": "没有这一条（可能已经被删了）"}
    gone = ents.pop(i)
    memory.runtime_set(entries=ents)
    try:
        import applog
        applog.log("记忆书：删掉第 %d 条，剩 %d 条" % (i, len(ents)), "MEM")
    except Exception:
        pass
    return {"ok": True, "left": len(ents),
            "text": (gone or {}).get("text", "") if isinstance(gone, dict) else ""}


class MemoryApi:
    """见 main.Handler。"""

    def _memory_get(self):
        """GET /api/memory"""
        try:
            return self._json(view())
        except Exception as e:
            return self._json({"ok": False, "error": "读记忆书失败：%s" % e})

    def _memory_delete(self):
        """POST /api/memory/delete  {"index": 0}"""
        try:
            body = self._body()
        except Exception as e:
            return self._json({"ok": False, "error": "bad body: %s" % e}, 400)
        return self._json(delete((body or {}).get("index")))
