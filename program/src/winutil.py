# -*- coding: utf-8 -*-
"""Win32 窗口小工具：取窗口句柄、user32 句柄。

从 main.py 拆出来，避免单文件越滚越大。
"""
import ctypes
import os


def _win_hwnd():
    """取主窗口句柄：优先 pywebview 的原生对象，兜底 FindWindow"""
    w = globals().get("_WINDOW")
    try:
        h = int(w.native.Handle)
        if h:
            return h
    except Exception:
        pass
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.WinDLL("user32", use_last_error=True)
        u.FindWindowW.restype = wintypes.HWND
        u.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        return int(u.FindWindowW(None, WINDOW_TITLE) or 0)
    except Exception:
        return 0

def _user32():
    import ctypes
    from ctypes import wintypes
    u = ctypes.WinDLL("user32", use_last_error=True)
    u.IsZoomed.argtypes = [wintypes.HWND]
    u.IsZoomed.restype = wintypes.BOOL
    u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    u.ShowWindow.restype = wintypes.BOOL
    u.ReleaseCapture.argtypes = []
    u.ReleaseCapture.restype = wintypes.BOOL
    u.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    u.PostMessageW.restype = wintypes.BOOL
    u.SetForegroundWindow.argtypes = [wintypes.HWND]
    u.SetForegroundWindow.restype = wintypes.BOOL
    return u

def _quiet_act(path):
    """这些动作每秒几十次，别写请求日志（日志 IO 是拖动迟滞的主因之一）"""
    try:
        from urllib.parse import urlparse, parse_qs
        q = parse_qs(urlparse(path).query)
        action = qs(q, ("action", "act")).strip()
        return action in ("movepos", "rect", "state")
    except Exception:
        return False
