# -*- coding: utf-8 -*-
"""首次启动自检（#23）：告诉用户「还差什么」，并指到该去的地方。

    GET /api/firstrun     → {ok, items:[...], all_ok, ready, checked_at}

不是拦路的向导：**只读检查**，不写配置、不改任何东西。前端拿到列表画成一屏，
每项给一个「去设置」的按钮；全绿或者用户点「跳过」就记一个 prefs 标记，下次不再弹。

检查项（顺序 = 新人上手的顺序）：

1. 模型服务   云端有 base_url + key，或者本地 Ollama 在跑
2. 角色       至少有一个角色，且当前角色的 prompt 不是空的
3. 语音       GPT-SoVITS 可不可用（可选，缺了只是没声音）
4. 素材       背景 / 立绘 有没有东西（可选，缺了只有黑底）
5. 存档       有没有档（可选，用来提示「可以接着玩」）
"""
import json
import os
import time
import urllib.request

import characters
import secret
import sessions


def _cfg_path():
    for p in (os.environ.get("WA2_CONFIG"),
              os.path.join(characters.user_dir(), "config.json")):
        if p and os.path.isfile(p):
            return p
    return ""


def _read_cfg():
    p = _cfg_path()
    if not p:
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _ollama_alive(url="http://127.0.0.1:11434/api/tags", timeout=0.8):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _item(key, title, ok, detail, fix="", optional=False):
    return {"key": key, "title": title, "ok": bool(ok), "detail": detail,
            "fix": fix, "optional": bool(optional)}


def checklist():
    items = []

    # 1 模型服务
    cfg = _read_cfg()
    base = (cfg.get("base_url") or "").strip()
    has_key = bool((cfg.get("api_key") or "").strip()) and not secret.is_masked(cfg.get("api_key"))
    cloud_ok = bool(base) and has_key
    local_ok = _ollama_alive()
    if cloud_ok and local_ok:
        detail = "云端已配置，本地 Ollama 也在跑"
    elif cloud_ok:
        detail = "云端已配置（%s）" % (base[:40] + ("…" if len(base) > 40 else ""))
    elif local_ok:
        detail = "没配云端，但本机 Ollama 在跑，可直接用本地模型"
    elif not _cfg_path():
        detail = "还没有 config.json（第一次运行会自动生成一份空白模板）"
    else:
        detail = "云端没填 key，本地 Ollama 也没响应"
    items.append(_item("model", "模型服务", cloud_ok or local_ok, detail, fix="opt"))

    # 2 角色
    try:
        chars = characters.list_characters() or []
    except Exception:
        chars = []
    cid = characters.active_id()
    cdir = characters.active_dir()
    prompt_ok = bool(cdir) and characters._has_prompt(os.path.join(cdir, "prompt"))
    detail = ("当前「%s」，共 %d 个角色" % (characters.display_name(cid), len(chars))) if chars \
        else "一个角色都没有"
    if chars and not prompt_ok:
        detail += "；但当前角色的 prompt/ 是空的"
    items.append(_item("character", "角色", bool(chars) and prompt_ok, detail, fix="special"))

    # 3 语音（可选）
    try:
        import tts_client
        tts_ok = bool(tts_client.available())
    except Exception:
        tts_ok = False
    items.append(_item("voice", "语音合成", tts_ok,
                       "GPU 合成可用" if tts_ok else "没检测到 GPT-SoVITS（不影响文字对话）",
                       fix="special", optional=True))

    # 4 素材（可选）
    try:
        import assets_report
        import scene_cg
        adir = getattr(scene_cg, "assets_dir", lambda: "")() or ""
        rep = assets_report.build(adir, cdir or "") if adir else {}
        checked = int(rep.get("checked") or 0)
        nbytes = int(rep.get("bytes") or 0)
        miss = len(rep.get("missing") or [])
        zero = len(rep.get("zero") or [])
        detail = ("检查 %d 个文件（%.1f MB）" % (checked, nbytes / 1048576.0)) if checked \
            else "素材目录里没找到要检查的文件"
        if miss:
            detail += "，缺 %d 个" % miss
        if zero:
            detail += "，空文件 %d 个" % zero
        mat_ok = checked > 0 and miss == 0
    except Exception as e:
        mat_ok = False
        detail = "读不到素材清单（%s）" % e
    items.append(_item("assets", "素材", mat_ok, detail, fix="asset", optional=True))

    # 5 存档（可选）
    try:
        lst = sessions.session_list() or []
    except Exception:
        lst = []
    items.append(_item("save", "存档", bool(lst),
                       "有 %d 个档，可以接着玩" % len(lst) if lst else "还没有存档",
                       fix="", optional=True))

    return items


def state():
    items = checklist()
    required = [i for i in items if not i["optional"]]
    return {
        "ok": True,
        "items": items,
        "all_ok": all(i["ok"] for i in items),
        "ready": all(i["ok"] for i in required),
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
