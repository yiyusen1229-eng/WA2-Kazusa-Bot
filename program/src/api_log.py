# -*- coding: utf-8 -*-
"""日志相关接口（#15）。

    GET /api/log/dump            写一份线程栈快照（卡死时用，在 main.py 里）
    GET /api/log/bundle?turns=N  生成诊断包 zip（默认不含对话；N>0 时附最近 N 轮）

包里的内容、脱敏规则见 `logpack.py` 的模块注释。
"""
import logpack


class LogApi:
    """见 main.Handler。"""

    def _log_bundle(self):
        from main import qs
        from urllib.parse import urlparse, parse_qs
        try:
            q = parse_qs(urlparse(self.path).query)
            turns = int(qs(q, ("turns", "n"), "0") or 0)
        except Exception:
            turns = 0
        turns = max(0, min(200, turns))
        try:
            res = logpack.bundle(include_turns=turns)
        except Exception as e:
            return self._json({"ok": False, "error": str(e)}, 500)
        return self._json(res)
