# -*- coding: utf-8 -*-
"WindowApi 的 mixin：从 main.py 拆出，方法体未改动。"

import applog


class WindowApi:
    """见 main.Handler；从 main 注入运行时全局。"""

    def _window_ctl(self):
        import main
        from main import (WINDOWED_SIZE, WINDOW_TITLE, _dpi_scale, _screen_size, _user32, _win_hwnd, qs)
        """无边框窗口的关闭 / 最小化 / 最大化（走 HTTP，避免依赖 js_api）"""
        from urllib.parse import urlparse, parse_qs
        try:
            q = parse_qs(urlparse(self.path).query)
            action = qs(q, ("action", "act")).strip()
            w = main._WINDOW
            try:
                applog.log("窗口控制: action=%s window=%s" % (action, "有" if w else "无"), "WIN")
            except Exception:
                pass
            if w is None:
                return self._json({"ok": False, "error": "窗口未就绪"})
            if action == "close":
                w.destroy()
            elif action == "min":
                w.minimize()
            elif action == "max":
                try:
                    w.maximize()
                except Exception:
                    w.toggle_fullscreen()
            elif action == "move":
                import ctypes
                from ctypes import wintypes
                u = ctypes.WinDLL("user32", use_last_error=True)
                u.FindWindowW.restype = wintypes.HWND
                u.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
                u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
                u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                           ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
                dx = int(q.get("dx", ["0"])[0]); dy = int(q.get("dy", ["0"])[0])
                hw = u.FindWindowW(None, WINDOW_TITLE)
                r = wintypes.RECT(); u.GetWindowRect(hw, ctypes.byref(r))
                u.SetWindowPos(hw, None, r.left + dx, r.top + dy, 0, 0, 0x0001 | 0x0004)
            elif action == "dragbegin":
                try:
                    _api_ref = main._API
                    if _api_ref is not None:
                        return self._json(_api_ref.drag_begin())
                except Exception as e:
                    return self._json({"ok": False, "error": str(e)})
                return self._json({"ok": False})
            elif action == "togglemax":
                u = _user32()
                hw = _win_hwnd()
                if hw:
                    maxed = bool(u.IsZoomed(hw))
                    u.ShowWindow(hw, 9 if maxed else 3)      # SW_RESTORE / SW_MAXIMIZE
                    return self._json({"ok": True, "maxed": bool(u.IsZoomed(hw))})
                # 拿不到 hwnd 时退回 pywebview（和最小化/关闭同一条路）
                try:
                    if getattr(w, "_wa2_maxed", False):
                        w.restore(); w._wa2_maxed = False
                    else:
                        w.maximize(); w._wa2_maxed = True
                    return self._json({"ok": True, "maxed": w._wa2_maxed})
                except Exception as e:
                    return self._json({"ok": False, "error": str(e)})
            elif action == "togglefull":
                # 浏览器 Fullscreen API 在无边框 WebView2 上会让窗口变成
                # “铺满屏幕但点不动”的透明层，所以改走 pywebview 自己的全屏开关
                try:
                    w.toggle_fullscreen()
                    w._wa2_full = not bool(getattr(w, "_wa2_full", False))
                    return self._json({"ok": True, "fullscreen": w._wa2_full})
                except Exception as e:
                    try:
                        w.maximize()
                        return self._json({"ok": True, "fallback": "maximize"})
                    except Exception:
                        return self._json({"ok": False, "error": str(e)})
            elif action == "fullscreen":
                # OPTION 1 的「窗口模式 / 全屏模式」：按目标状态切，不是盲目 toggle。
                # 退出全屏时必须回到一个**明显小于全屏**的窗口 —— 不然在 4K/高 DPI 上
                # 全屏与"最大化"看起来一样大（用户实测反馈过）。
                want = qs(q, ("on",), "1")
                target = (want != "0")
                try:
                    cur = bool(getattr(w, "_wa2_full", False))
                    if target != cur:
                        w.toggle_fullscreen()
                    w._wa2_full = target
                    if not target:
                        try:
                            w.restore()                      # 先解除最大化
                        except Exception:
                            pass
                        try:
                            w.resize(*WINDOWED_SIZE)
                        except Exception:
                            pass
                        try:
                            # move() 收的是 DIP，GetSystemMetrics 给的是物理像素，先换算
                            sw, sh = _screen_size()
                            dp = _dpi_scale()
                            if sw and sh and dp > 0:
                                w.move(int((sw / dp - WINDOWED_SIZE[0]) / 2),
                                       int((sh / dp - WINDOWED_SIZE[1]) / 2))
                        except Exception:
                            pass
                    return self._json({"ok": True, "fullscreen": target})
                except Exception as e:
                    # 全屏 API 不可用时退回最大化，至少不是"点了没反应"
                    try:
                        w.maximize()
                        w._wa2_full = target
                        return self._json({"ok": True, "fullscreen": target, "fallback": "maximize"})
                    except Exception:
                        return self._json({"ok": False, "error": str(e)})
            elif action == "state":
                u = _user32()
                hw = _win_hwnd()
                return self._json({"ok": bool(hw), "maxed": bool(u.IsZoomed(hw)) if hw else False,
                                   "fullscreen": bool(getattr(w, "_wa2_full", False))})
            elif action == "resize":
                try:
                    nw = int(q.get("w", ["0"])[0])
                    nh = int(q.get("h", ["0"])[0])
                except Exception:
                    return self._json({"ok": False, "error": "bad size"})
                if nw < 640 or nh < 360:
                    return self._json({"ok": False, "error": "too small"})
                w = main._WINDOW
                try:
                    w.resize(nw, nh)
                    return self._json({"ok": True, "w": nw, "h": nh})
                except Exception as e:
                    return self._json({"ok": False, "error": str(e)})
            elif action == "restore":
                try:
                    w.restore()
                except Exception:
                    w.toggle_fullscreen()
            return self._json({"ok": True, "action": action})
        except Exception as e:
            return self._json({"ok": False, "error": str(e)})
