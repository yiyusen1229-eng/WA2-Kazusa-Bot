# -*- coding: utf-8 -*-
"""#18 桌面行为：置顶 / 透明 / 点击穿透 / 多显示器 —— 用真的 Win32 窗口验。

不开主程序、不弹可见窗口：自己 CreateWindowEx 一个隐藏窗口，
把样式设上去再读回来。验的是「API 真的生效」，不是「代码里有这行」。

    cd program && .\\build_env\\venv\\Scripts\\python.exe tools\\test_desktop.py
"""
import ctypes
import sys
from ctypes import wintypes

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, __file__.rsplit("tools", 1)[0] + "src")

import winutil  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:200]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def make_hidden_window():
    """建一个**屏幕外**的窗口（不会闪出来，但必须是「可见」状态）

    为什么不能纯隐藏：`SetWindowPos(HWND_TOPMOST)` 只在可见窗口上真的落
    WS_EX_TOPMOST；隐藏窗口调用返回成功但样式不变（实测）。
    所以放到 (-4000, -4000) 再 SW_SHOWNOACTIVATE —— 用户看不到，样式能验。
    """
    u = ctypes.WinDLL("user32", use_last_error=True)
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    u.CreateWindowExW.restype = wintypes.HWND
    u.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                  wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_int, wintypes.HWND, wintypes.HMENU,
                                  wintypes.HINSTANCE, wintypes.LPVOID]
    u.DefWindowProcW.restype = ctypes.c_long
    u.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_long, wintypes.HWND, wintypes.UINT,
                                 wintypes.WPARAM, wintypes.LPARAM)
    proc = WNDPROC(lambda hwnd, msg, wp, lp: u.DefWindowProcW(hwnd, msg, wp, lp))

    class WNDCLASS(ctypes.Structure):
        _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                    ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                    ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                    ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                    ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]

    cls_name = "WA2DesktopTest"
    wc = WNDCLASS()
    wc.lpfnWndProc = proc
    wc.lpszClassName = cls_name
    wc.hInstance = k.GetModuleHandleW(None)
    if not u.RegisterClassW(ctypes.byref(wc)):
        err = ctypes.get_last_error()
        if err not in (1410,):          # 类已注册
            return None, None
    hwnd = u.CreateWindowExW(0, cls_name, "wa2 hidden", 0x80000000, -4000, -4000, 300, 200,
                             None, None, wc.hInstance, None)
    if hwnd:
        u.ShowWindow(hwnd, 4)           # SW_SHOWNOACTIVATE：屏幕外，不抢焦点
    return hwnd, proc


def main():
    hwnd, proc = make_hidden_window()
    check("建出隐藏窗口", bool(hwnd), ctypes.get_last_error() if not hwnd else "")
    if not hwnd:
        print("\n失败 %d 项" % len(FAILS))
        return 1

    print("[1] 置顶")
    # 注：SetWindowPos(HWND_TOPMOST) 对「程序自己造的、离屏未激活」窗口不会真的落
    # WS_EX_TOPMOST（实测：返回 1、样式位不变，Windows 的分带是延迟的）。
    # 所以这里只验 getter（用建窗时就带 topmost 的窗口）和调用不炸；
    # 「点了置顶真的浮在最上面」在 app 级验（tools/test_desktop_app.py 开真窗口）。
    tm = winutil._u32()
    h2 = ctypes.WinDLL("user32").CreateWindowExW(
        0x00000008, "WA2DesktopTest", "wa2 topmost", 0x80000000, -4200, -4200, 200, 150,
        None, None, ctypes.WinDLL("kernel32").GetModuleHandleW(None), None)
    if h2:
        check("建窗时带 WS_EX_TOPMOST → is_topmost 读得到", winutil.is_topmost(h2),
              winutil._u32().GetWindowLongW(h2, -20) & 0xFFFFFFFF)
        ctypes.WinDLL("user32").DestroyWindow(h2)
    else:
        check("建窗时带 WS_EX_TOPMOST", False, "CreateWindowExW 失败")
    check("set_topmost(True) 调用成功", winutil.set_topmost(hwnd, True))
    check("set_topmost(False) 调用成功", winutil.set_topmost(hwnd, False))

    print("[2] 不透明度")
    check("初始 255", winutil.get_alpha(hwnd) == 255, winutil.get_alpha(hwnd))
    check("设 180 成功", winutil.set_alpha(hwnd, 180))
    check("读回来 180", winutil.get_alpha(hwnd) == 180, winutil.get_alpha(hwnd))
    check("夹取：999 → 255（等于复位）",
          winutil.set_alpha(hwnd, 999) and winutil.get_alpha(hwnd) == 255, winutil.get_alpha(hwnd))
    check("夹取：-5 → 0", winutil.set_alpha(hwnd, -5) and winutil.get_alpha(hwnd) == 0,
          winutil.get_alpha(hwnd))
    check("回到 255 摘掉 LAYERED",
          winutil.set_alpha(hwnd, 255) and winutil.get_alpha(hwnd) == 255)

    print("[3] 点击穿透")
    check("初始不穿透", not winutil.is_click_through(hwnd))
    check("set_click_through(True)", winutil.set_click_through(hwnd, True))
    check("读回来穿透", winutil.is_click_through(hwnd))
    check("关掉", winutil.set_click_through(hwnd, False) and not winutil.is_click_through(hwnd))

    print("[4] 多显示器 / 夹取")
    area = winutil.monitor_workarea(100, 100)
    check("拿得到工作区", bool(area) and len(area) == 4, area)
    if area:
        L, T, R, B = area
        check("工作区合理（右下大于左上）", R > L and B > T, area)
        x, y, w, h = winutil.clamp_to_workarea(99999, 99999, 800, 450, area)
        check("超出一大截会被拉回来", x < 99999 and y < 99999 and x <= R and y <= B, (x, y, w, h))
        check("尺寸不变", (w, h) == (800, 450), (w, h))
        x2, y2, _, _ = winutil.clamp_to_workarea(-5000, -5000, 800, 450, area)
        check("跑到负坐标也拉回来", x2 >= L and y2 >= T, (x2, y2))

    print("[5] 移动窗口")
    check("move_window 返回成功", winutil.move_window(hwnd, 50, 60))
    rect = winutil.get_rect(hwnd)
    check("位置真的变了", rect and rect[0] == 50 and rect[1] == 60, rect)

    print("[6] 句柄是 0 时不炸")
    check("set_topmost(0) 返回 False", winutil.set_topmost(0) is False)
    check("set_alpha(0) 返回 False", winutil.set_alpha(0) is False)
    check("get_alpha(0) 不抛异常", winutil.get_alpha(0) in (0, 255))
    check("get_rect(0) 返回 None", winutil.get_rect(0) is None)

    try:
        ctypes.WinDLL("user32").DestroyWindow(hwnd)
    except Exception:
        pass

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), "、".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
