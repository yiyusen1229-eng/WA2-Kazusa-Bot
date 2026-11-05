# -*- coding: utf-8 -*-
"""/api/hotreload：素材热重载的状态与开关（#20）。

    GET  /api/hotreload          → {ok, enabled, gen, last_at, last_kinds, errors, ...}
    POST /api/hotreload {"on":0} → 关掉（想省点磁盘 stat 的时候）

前端 `wt-hotreload.js` 每几秒问一次 `gen`：变了说明素材文件被动过，就重拉立绘索引、重画当前画面。
"""

import hotreload


class HotReloadApi:
    """见 main.Handler。"""

    def _hotreload_get(self):
        try:
            return self._json(hotreload.state())
        except Exception as e:
            return self._json({"ok": False, "error": "读热重载状态失败：%s" % e})

    def _hotreload_post(self):
        try:
            body = self._body()
        except Exception as e:
            return self._json({"ok": False, "error": "bad body: %s" % e}, 400)
        on = bool((body or {}).get("on", True))
        hotreload.set_enabled(on)
        if on:
            hotreload.start()
        else:
            hotreload.stop()
        st = hotreload.state()
        st["note"] = "素材热重载已打开" if on else "素材热重载已关闭（重启后按环境变量决定）"
        return self._json(st)
