# -*- coding: utf-8 -*-
"""聊天导出（#23）：把一段对话导成 Markdown / 纯文本，默认脱敏。

    GET /api/export/chat?slot=auto&fmt=md&redact=1&only_reply=0          → 附件下载
    GET /api/export/chat?slot=auto&fmt=md&redact=1&preview=1             → 预览（JSON）

三条规矩（#23 边界）：

1. **默认脱敏**：密钥用 `secret.redact` 换成等长的掩码；盘符绝对路径换成 `<本机路径>`。
2. **分享前先预览**：`preview=1` 返回字数、条数、被脱敏的处数 + 前 800 字，
   前端把这段给用户看，确认了再下载。
3. **不写进存档目录**：导出只读存档、只产出文本，不改任何文件。

`slot=auto` 读自动存档；`slot=N` 读第 N 号档。带 `only_reply=1` 时只导她的台词
（想发截图/卡片时用，不用手删自己的话）。
"""
import io
import json
import os
import re
import time
from urllib.parse import parse_qs, quote, urlparse

import characters
import secret
import sessions

FMT_EXT = {"md": ".md", "txt": ".txt"}

# 盘符路径（C:\xxx、D:/yyy）——导出给别人的东西里不该出现本机目录结构
_RE_WINPATH = re.compile(r"[A-Za-z]:[\\/][^\s，。；、）)」』\"']{1,120}")
_RE_MASK = "***"


def _mask_path(m):
    return "<本机路径>"


def clean(text, do_redact=True):
    """按开关脱敏；返回 (处理后文本, 脱敏处数)"""
    if text is None:
        return "", 0
    s = str(text)
    if not do_redact:
        return s, 0
    n = 0
    before = s
    s = secret.redact(s) or ""
    if s != before:
        n += 1
    hits = _RE_WINPATH.findall(s)
    if hits:
        n += len(hits)
        s = _RE_WINPATH.sub(_RE_MASK, s)
    return s, n


def _msgs(slot):
    d = sessions.session_load(slot or "auto")
    if not d.get("ok"):
        return None, d.get("error") or "读取存档失败"
    return (d.get("messages") or []), ""


def render(messages, fmt="md", do_redact=True, only_reply=False, who=None):
    """把消息渲染成文本；返回 (文本, 统计)"""
    name = who or characters.display_name(characters.active_id()) or "她"
    lines = []
    n_both = n_her = n_mine = 0
    masked = 0
    if fmt == "md":
        lines.append("# %s · 对话记录" % name)
        lines.append("")
    else:
        lines.append("%s · 对话记录" % name)
    stamp = time.strftime("%Y-%m-%d %H:%M")
    for m in messages:
        role = m.get("role")
        body = (m.get("zh") or m.get("content") or "").strip()
        if not body:
            continue
        if role == "assistant":
            n_her += 1
        elif role == "user":
            if only_reply:
                continue          # 统计只算真正导出的行，不然「共 N 句」和正文对不上
            n_mine += 1
        else:
            continue
        n_both += 1
        body, k = clean(body, do_redact)
        masked += k
        emo = (m.get("emo") or "").strip()
        if fmt == "md":
            tag = "（%s）" % emo if (role == "assistant" and emo) else ""
            prefix = "**%s**%s：" % ("你" if role == "user" else name, tag)
            lines.append(prefix + body)
            lines.append("")
        else:
            lines.append(("你：" if role == "user" else name + "：") + body)
    if fmt == "md":
        lines.insert(2, "> 导出于 %s · 共 %d 句（她 %d 句%s）%s"
                     % (stamp, n_both, n_her,
                        "，你 %d 句" % n_mine if n_mine else "",
                        " · 已脱敏 %d 处" % masked if masked else ""))
        lines.insert(3, "")
    else:
        lines.insert(1, "导出于 %s · 共 %d 句" % (stamp, n_both))
        lines.insert(2, "")
    text = "\n".join(lines).rstrip() + "\n"
    return text, {"lines": n_both, "her": n_her, "mine": n_mine, "masked": masked,
                  "chars": len(text)}


def export(slot="auto", fmt="md", do_redact=True, only_reply=False, preview=False,
           preview_chars=800):
    messages, err = _msgs(slot)
    if messages is None:
        return {"ok": False, "error": err}
    if not messages:
        return {"ok": False, "error": "这段对话是空的（还没有内容可导出）"}
    fmt = "txt" if str(fmt).lower() in ("txt", "text") else "md"
    text, stat = render(messages, fmt, do_redact, only_reply)
    name = characters.display_name(characters.active_id()) or "对话"
    fname = "%s_%s%s" % (name, time.strftime("%Y%m%d_%H%M"), FMT_EXT[fmt])
    if preview:
        return dict(ok=True, preview=text[:preview_chars],
                    truncated=len(text) > preview_chars, filename=fname,
                    redacted=bool(do_redact), **stat)
    return dict(ok=True, filename=fname, text=text, redacted=bool(do_redact), **stat)


# ------------------------------------------------------------------ HTTP
def handle_get(server, q=None):
    """在 main 的路由里调用：自己写响应（可能是附件下载）

    ⚠️ 别指望调用方把 parse_qs 结果传进来：main.do_GET 里那个位置还没有 `q`
    （2026-11-06 实测 NameError，连接被掐断，浏览器只看到「下载失败」）。
    所以这里自己解析，`q` 只当作可选的覆盖。
    """
    if q is None:
        q = parse_qs(urlparse(getattr(server, "path", "") or "").query)
    fmt = (q.get("fmt", ["md"])[0] or "md").lower()
    slot = (q.get("slot", ["auto"])[0] or "auto").strip()
    redact_on = (q.get("redact", ["1"])[0] or "1").lower() not in ("0", "false", "off")
    only_reply = (q.get("only_reply", ["0"])[0] or "0").lower() not in ("0", "false", "off")
    preview = (q.get("preview", ["0"])[0] or "0").lower() not in ("0", "false", "off")
    r = export(slot=slot, fmt=fmt, do_redact=redact_on, only_reply=only_reply, preview=preview)
    if not r.get("ok"):
        return server._json(r)
    if preview:
        return server._json(r)
    body = r["text"].encode("utf-8-sig")      # 带 BOM：Windows 记事本打开不乱码
    server.send_response(200)
    server.send_header("Content-Type", "text/markdown; charset=utf-8"
                       if fmt != "txt" else "text/plain; charset=utf-8")
    server.send_header("Content-Disposition",
                       "attachment; filename=\"chat.%s\"; filename*=UTF-8''%s"
                       % (FMT_EXT.get(fmt, ".md").lstrip("."), quote(r["filename"])))
    server.send_header("Content-Length", str(len(body)))
    server.send_header("Cache-Control", "no-store")
    server.end_headers()
    server.wfile.write(body)
    return True
