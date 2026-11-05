# -*- coding: utf-8 -*-
"""素材导入向导（#20）：把「缺什么」按步骤摆出来，每一步都能跳过。

    GET /api/assets/wizard            → 读启动时那份 asset_report.json（快）
    GET /api/assets/wizard?refresh=1  → 现扫一遍再回（半天没动素材时用）

返回的 `steps` 是给界面直接画的：

    {"key": "portrait", "title": "立绘", "ok": false, "missing": 3,
     "examples": ["高中·冬装/生气.png", ...], "hint": "特别模式 → 立绘导入"}

不替用户做导入动作：导入面板已经有了，向导只负责「告诉你缺什么、从哪进」。
"""

import os
import time

import assets_report
import char_res
import characters


def _report_path():
    try:
        import applog
        return os.path.join(applog._log_dir(), "asset_report.json")
    except Exception:
        return ""


def _group_missing(report, kind):
    """按 outfit / id 聚合，给界面一行一行的例子"""
    out = {}
    for it in (report.get("missing") or []):
        if (it or {}).get("kind") != kind:
            continue
        key = it.get("outfit") or it.get("id") or "?"
        rel = it.get("file") or ""
        out.setdefault(key, []).append(rel)
    return out


def build(assets_dir="", char_dir="", report=None, limit=8):
    """返回给前端的向导数据；`report` 传了就不重扫"""
    assets_dir = assets_dir or os.environ.get("WA2_ASSETS_DIR") or ""
    char_dir = char_dir or characters.active_dir()
    if report is None:
        try:
            report = assets_report.build(assets_dir, char_dir)
        except Exception as e:
            return {"ok": False, "error": "素材自检失败：%s" % e, "steps": []}

    missing = report.get("missing") or []
    zero = report.get("zero") or []

    # 1) 立绘
    pm = _group_missing(report, "portrait")
    p_examples = []
    for outfit in sorted(pm):
        for f in pm[outfit][:3]:
            p_examples.append("%s/%s" % (outfit, f))
    p_ok = not pm

    # 2) 场景背景
    cm = _group_missing(report, "cg")
    c_examples = ["%s（%s）" % (cid, (cm[cid] or [""])[0]) for cid in sorted(cm)]
    c_ok = not cm

    # 3) 语音
    z_voice = [z.get("file") for z in zero if (z or {}).get("kind") == "voice"]
    try:
        refs = char_res.voice_refs() or []
    except Exception:
        refs = []
    v_ok = bool(refs) and not z_voice
    v_examples = []
    if not refs:
        v_examples.append("还没导入参考音频")
    for f in z_voice[:3]:
        v_examples.append("%s（0 字节）" % f)

    # 4) 提示词 / 世界书 / 记忆书
    try:
        st = char_res.status() or {}
    except Exception:
        st = {}
    t_missing = []
    for key, label in (("prompt", "提示词"), ("worldbook", "世界书"), ("memory", "记忆书")):
        if not ((st.get(key) or {}).get("file")):
            t_missing.append(label)
    t_examples = ["未导入：%s" % "、".join(t_missing)] if t_missing else []

    steps = [
        {"key": "portrait", "title": "立绘（表情 / 衣服）", "ok": p_ok,
         "missing": sum(len(v) for v in pm.values()),
         "examples": p_examples[:limit],
         "hint": "特别模式 → 立绘导入；缺的表情可以先跳过，缺图时用旧图顶着",
         "action": "portrait", "can_skip": True},
        {"key": "scene", "title": "场景背景", "ok": c_ok,
         "missing": len(cm), "examples": c_examples[:limit],
         "hint": "特别模式 → 场景 / CG 导入；缺的场景会被自动跳过",
         "action": "scene", "can_skip": True},
        {"key": "voice", "title": "语音（参考音频）", "ok": v_ok,
         "missing": len(z_voice) + (0 if refs else 1),
         "examples": v_examples[:limit],
         "hint": "特别模式 → 语音导入；没有参考音频时只显示文字",
         "action": "voice", "can_skip": True},
        {"key": "text", "title": "提示词 / 世界书 / 记忆书", "ok": not t_missing,
         "missing": len(t_missing), "examples": t_examples,
         "hint": "特别模式 → 提示词 / 世界书 / 记忆书导入",
         "action": "text", "can_skip": True},
    ]
    bad = [s for s in steps if not s["ok"]]
    return {
        "ok": True,
        "at": report.get("at") or "",
        "checked": report.get("checked") or 0,
        "bytes": report.get("bytes") or 0,
        "missing_total": len(missing),
        "zero_total": len(zero),
        "steps": steps,
        "done": not bad,
        "hint": ("素材齐了，可以开始玩" if not bad
                 else "%d 步有缺项，可以先去玩、以后在「特别模式」里补" % len(bad)),
        "assets_dir": assets_dir,
        "char_dir": char_dir,
    }


def cached_build(assets_dir="", char_dir="", refresh=False):
    """读启动时那份报告；refresh=True 或报告不存在时才现扫"""
    if not refresh:
        p = _report_path()
        if p and os.path.isfile(p):
            try:
                import json
                with open(p, encoding="utf-8") as f:
                    rep = json.load(f)
                if isinstance(rep, dict):
                    return build(assets_dir, char_dir, report=rep)
            except Exception:
                pass
    return build(assets_dir, char_dir)


class WizardApi:
    """见 main.Handler。"""

    def _wizard_get(self):
        try:
            from main import qs
            refresh = (qs(self.path, "refresh") or "").strip() not in ("", "0", "false")
        except Exception:
            refresh = False
        try:
            assets_dir = os.environ.get("WA2_ASSETS_DIR") or ""
            try:
                from main import ASSETS_DIR as _AD
                assets_dir = _AD or assets_dir
            except Exception:
                pass
            return self._json(cached_build(assets_dir=assets_dir, refresh=refresh))
        except Exception as e:
            return self._json({"ok": False, "error": "素材向导失败：%s" % e, "steps": []})
