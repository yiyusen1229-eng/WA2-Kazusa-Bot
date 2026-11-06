# -*- coding: utf-8 -*-
"""Win32 窗口小工具：取窗口句柄、user32 句柄。

从 main.py 拆出来，避免单文件越滚越大。
"""
import ctypes
import os


def _main_module():
    """取“主程序模块”。

    直接跑 `python main.py` 时，主模块在 sys.modules 里的名字是 "__main__"，
    不是 "main" —— 所以两个都要查，否则拆出来的模块取不到 main 的全局变量。
    """
    import sys
    for name in ("main", "__main__"):
        m = sys.modules.get(name)
        if m is not None and getattr(m, "_WINDOW", None) is not None:
            return m
    for name in ("main", "__main__"):
        m = sys.modules.get(name)
        if m is not None:
            return m
    return None


def _win_hwnd():
    """取主窗口句柄：优先 pywebview 的原生对象，兜底 FindWindow"""
    # _WINDOW 挂在主模块上（可能是 __main__），必须跨模块取，否则句柄恒为 0
    _m = _main_module()
    w = getattr(_m, "_WINDOW", None) if _m is not None else None
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
        _m2 = _main_module()
        _title = getattr(_m2, "WINDOW_TITLE", "") if _m2 is not None else ""
        return int(u.FindWindowW(None, _title) or 0)
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


# ======================================================================
# 桌面行为（#18）：置顶 / 透明 / 多显示器（点击穿透做过又删了）
# 全部用 user32 的本机 API，不引第三方库（pystray / keyboard 都没装，
# 加了会让打包多两套依赖和一个全局键盘钩子，风险不值当）。
# ======================================================================
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
LWA_ALPHA = 0x00000002


def _u32():
    """带齐这些动作要用的签名（user32 默认按 int 传参，句柄会被截断）"""
    import ctypes
    from ctypes import wintypes
    u = ctypes.WinDLL("user32", use_last_error=True)
    u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                               ctypes.c_int, ctypes.c_int, wintypes.UINT]
    u.SetWindowPos.restype = wintypes.BOOL
    u.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    u.GetWindowLongW.restype = ctypes.c_long
    u.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
    u.SetWindowLongW.restype = ctypes.c_long
    u.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.COLORREF,
                                             ctypes.c_ubyte, wintypes.DWORD]
    u.SetLayeredWindowAttributes.restype = wintypes.BOOL
    u.GetLayeredWindowAttributes.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD),
                                             ctypes.POINTER(ctypes.c_ubyte),
                                             ctypes.POINTER(wintypes.DWORD)]
    u.GetLayeredWindowAttributes.restype = wintypes.BOOL
    u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    u.GetWindowRect.restype = wintypes.BOOL
    u.MoveWindow.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int,
                             ctypes.c_int, ctypes.c_int, wintypes.BOOL]
    u.MoveWindow.restype = wintypes.BOOL
    return u


def set_topmost(hwnd, on=True):
    """窗口置顶（放在最上层，别的程序盖不住它）"""
    if not hwnd:
        return False
    try:
        u = _u32()
        after = HWND_TOPMOST if on else HWND_NOTOPMOST
        ok = u.SetWindowPos(int(hwnd), after, 0, 0, 0, 0,
                            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        return bool(ok)
    except Exception:
        return False


def is_topmost(hwnd):
    """读 exstyle 判断置顶位（WS_EX_TOPMOST = 0x8）"""
    if not hwnd:
        return False
    try:
        return bool(_u32().GetWindowLongW(int(hwnd), GWL_EXSTYLE) & 0x00000008)
    except Exception:
        return False


def set_alpha(hwnd, alpha=255):
    """整窗不透明度：0~255，255 或 None = 不透明（会顺手摘掉 LAYERED）。

    注意 `SetLayeredWindowAttributes` 要求窗口先有 WS_EX_LAYERED，
    所以这里先补样式再设 alpha；恢复 255 时把样式摘掉，让 WebView2 回到硬件合成。
    """
    if not hwnd:
        return False
    try:
        h = int(hwnd)
        u = _u32()
        ex = u.GetWindowLongW(h, GWL_EXSTYLE)
        a = 255 if alpha is None else max(0, min(255, int(alpha)))
        if a >= 255:
            u.SetWindowLongW(h, GWL_EXSTYLE, ex & ~WS_EX_LAYERED)
            return True
        if not (ex & WS_EX_LAYERED):
            u.SetWindowLongW(h, GWL_EXSTYLE, ex | WS_EX_LAYERED)
        return bool(u.SetLayeredWindowAttributes(h, 0, a, LWA_ALPHA))
    except Exception:
        return False


def get_alpha(hwnd):
    """读回当前不透明度；没开 layered 就是 255"""
    if not hwnd:
        return 255
    try:
        import ctypes
        from ctypes import wintypes
        u = _u32()
        h = int(hwnd)
        if not (u.GetWindowLongW(h, GWL_EXSTYLE) & WS_EX_LAYERED):
            return 255
        cr = wintypes.DWORD(0)
        al = ctypes.c_ubyte(0)
        fl = wintypes.DWORD(0)
        if u.GetLayeredWindowAttributes(h, ctypes.byref(cr), ctypes.byref(al), ctypes.byref(fl)):
            return int(al.value)
    except Exception:
        pass
    return 255


def get_rect(hwnd):
    """(left, top, width, height)；拿不到返回 None"""
    if not hwnd:
        return None
    try:
        import ctypes
        from ctypes import wintypes
        u = _u32()
        r = wintypes.RECT()
        if not u.GetWindowRect(int(hwnd), ctypes.byref(r)):
            return None
        return (int(r.left), int(r.top), int(r.right - r.left), int(r.bottom - r.top))
    except Exception:
        return None


def move_window(hwnd, x, y, w=None, h=None):
    """把窗口移到 (x, y)；w/h 不给就保持原尺寸"""
    if not hwnd:
        return False
    try:
        u = _u32()
        cur = get_rect(hwnd)
        if not cur:
            return False
        ww = cur[2] if w is None else int(w)
        hh = cur[3] if h is None else int(h)
        return bool(u.MoveWindow(int(hwnd), int(x), int(y), ww, hh, True))
    except Exception:
        return False


def monitor_workarea(x=None, y=None):
    """某个点所在显示器的工作区（不含任务栏）：(left, top, right, bottom)。

    点不给就用鼠标位置。多显示器时用它把窗口夹回可见区域，
    免得换屏幕后窗口落在已经拔掉的显示器上（重启就找不回来了）。
    """
    try:
        import ctypes
        from ctypes import wintypes
        u = _u32()
        u.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
        u.MonitorFromPoint.restype = wintypes.HANDLE
        u.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
        u.GetMonitorInfoW.restype = wintypes.BOOL

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD),
                        ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT),
                        ("dwFlags", wintypes.DWORD)]

        pt = wintypes.POINT(int(x if x is not None else 0), int(y if y is not None else 0))
        if x is None or y is None:
            u.GetCursorPos(ctypes.byref(pt))
        mon = u.MonitorFromPoint(pt, 2)      # MONITOR_DEFAULTTONEAREST
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if mon and u.GetMonitorInfoW(mon, ctypes.byref(mi)):
            return (int(mi.rcWork.left), int(mi.rcWork.top),
                    int(mi.rcWork.right), int(mi.rcWork.bottom))
    except Exception:
        pass
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.WinDLL("user32")
        return (0, 0, int(u.GetSystemMetrics(0)), int(u.GetSystemMetrics(1)))
    except Exception:
        return None


def clamp_to_workarea(x, y, w, h, area=None):
    """把窗口矩形夹进工作区：至少留一角可见（标题栏能拖回来）。"""
    try:
        L, T, R, B = area or monitor_workarea(x, y)
    except Exception:
        L, T, R, B = 0, 0, 1920, 1080
    w = max(200, int(w or 800))
    h = max(150, int(h or 450))
    x = int(x or 0)
    y = int(y or 0)
    if x > R - 120:
        x = R - 120
    if y > B - 60:
        y = B - 60
    if x + w < L + 120:
        x = L
    if y + h < T + 60:
        y = T
    if x + w > R:
        x = max(L, R - w)
    if y + h > B:
        y = max(T, B - h)
    return (int(x), int(y), int(w), int(h))
