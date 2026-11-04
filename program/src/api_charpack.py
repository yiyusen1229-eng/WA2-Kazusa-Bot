# -*- coding: utf-8 -*-
"""/api/charpack/* 的实现：角色包导出 / 导入

和 api_char.py 一个套路 —— 只是 Handler 的一个 mixin，路由在 main.py 的 do_POST 里。

两个接口都会**弹系统窗口**（选目录 / 选文件），所以是阻塞式 HTTP 请求：
窗口开着的时候前端那个 fetch 就一直等着，关掉才返回。取消返回
{"ok": false, "cancelled": true}，前端按「已取消」提示，不当成错误。
"""

import char_pack


class CharPackApi:
    """见 main.Handler。"""

    def _charpack_export(self):
        """POST /api/charpack/export  {"id": "和纱"} → 选目录 → 打包 zip"""
        try:
            body = self._body()
        except Exception as e:
            return self._json({"ok": False, "error": "bad body: %s" % e}, 400)
        cid = ((body or {}).get("id") or "").strip()
        try:
            return self._json(char_pack.export_with_dialog(cid))
        except Exception as e:
            return self._json({"ok": False, "error": "导出失败：%s" % e})

    def _charpack_import(self):
        """POST /api/charpack/import  → 选 zip → 解成新角色（不自动切换）"""
        try:
            return self._json(char_pack.import_with_dialog())
        except Exception as e:
            return self._json({"ok": False, "error": "导入失败：%s" % e})
