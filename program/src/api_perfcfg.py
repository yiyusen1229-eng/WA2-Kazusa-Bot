# -*- coding: utf-8 -*-
"""/api/performance：每角色的演出 / 切片规则（#19）。

只读接口：把 `characters/<角色>/performance.json` 与 `persona_slices.json`
（缺了就是默认值）连同 warning 一起交给前端。前端在启动和切角色后各拉一次。
"""

import perfcfg


class PerfCfgApi:
    """见 main.Handler。"""

    def _performance_get(self):
        """GET /api/performance"""
        try:
            return self._json(perfcfg.detail())
        except Exception as e:
            return self._json({"ok": False, "error": "读演出配置失败：%s" % e})
