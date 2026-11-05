# -*- coding: utf-8 -*-
"""更新检查 / 一键更新 / 打开链接（从 main.py 拆出的 mixin）。

- GET  /api/update         查 GitHub 上的 version.json，判断有没有比本机新的版本
- POST /api/update/apply   一键更新：git 仓库走 fetch+reset，zip 安装走整份快照下载
- GET  /api/update/status  一键更新的进度（前端轮询）
- GET  /api/open_url?url=  用系统浏览器打开链接（只允许 http/https）
"""

import json
import os
import urllib.request
import webbrowser

import version as _ver
import updater


class UpdateApi:
    """见 main.Handler。"""

    def _update_check(self):
        """查远端版本；拿不到就当“无更新”，绝不影响启动。"""
        info = {
            "ok": True,
            "current": _ver.VERSION,
            "latest": _ver.VERSION,
            "newer": False,
            "url": _ver.PATCH_URL,
            "notes": "",
        }
        try:
            st = updater.detect()
            info["auto"] = bool(st.get("can_auto"))
            info["mode"] = st.get("mode") or ""
        except Exception as e:
            info["auto"] = False
            info["mode"] = ""
            info["auto_error"] = str(e)[:120]
        url = os.environ.get("WA2_UPDATE_URL") or _ver.RAW_VERSION_URL
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "WA2-Kazusa-Bot"})
            with urllib.request.urlopen(req, timeout=6) as r:
                d = json.loads(r.read().decode("utf-8"))
            latest = str(d.get("version") or "").strip()
            if latest:
                info["latest"] = latest
                info["newer"] = _ver.ver_key(latest) > _ver.ver_key(_ver.VERSION)
                info["url"] = d.get("url") or _ver.PATCH_URL
                info["notes"] = str(d.get("notes") or "")[:200]
        except Exception as e:
            info["ok"] = False
            info["error"] = "%s: %s" % (type(e).__name__, e)
        return self._json(info)

    def _update_apply(self):
        """一键更新：后台跑，前端用 /api/update/status 轮询。"""
        try:
            st = updater.detect()
            if not st.get("can_auto"):
                return self._json({"ok": False,
                                   "error": st.get("git_detail") or "无法自动更新"})
            p = updater.apply()
            return self._json({"ok": True, "started": True,
                               "mode": st.get("mode"), "progress": p})
        except Exception as e:
            return self._json({"ok": False, "error": "%s: %s" % (type(e).__name__, e)})

    def _update_status(self):
        return self._json({"ok": True, "progress": updater.progress()})

    def _open_url(self):
        """用系统默认浏览器打开（只放行 http/https，避免被当成执行器）。"""
        from urllib.parse import urlparse, parse_qs
        import main

        q = parse_qs(urlparse(self.path).query)
        url = (main.qs(q, ("url",)) or "").strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            return self._json({"ok": False, "error": "只允许 http/https"})
        try:
            webbrowser.open(url)
            return self._json({"ok": True, "url": url})
        except Exception as e:
            return self._json({"ok": False, "error": str(e)})
