# -*- coding: utf-8 -*-
"""启动 exe, 找到窗口, 点进游戏, 截图对话区"""
import ctypes
import subprocess
import time
from ctypes import wintypes

from PIL import ImageGrab

EXE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\最新版\和纱_字体修复版.exe"
OUT = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\work\实机截图.png"
TITLE = "WHITE ALBUM 2"

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.FindWindowW.restype = wintypes.HWND
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                               wintypes.DWORD, ctypes.c_ulonglong]

subprocess.Popen([EXE])
time.sleep(12)

hwnd = None
for _ in range(20):
    hwnd = user32.FindWindowW(None, TITLE)
    if hwnd:
        break
    # 标题带程序名时用模糊匹配
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, l):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(h, buf, 256)
        if "WHITE ALBUM" in buf.value and user32.IsWindowVisible(h):
            found.append(h)
        return True

    user32.EnumWindows(cb, 0)
    if found:
        hwnd = found[0]
        break
    time.sleep(1)

if not hwnd:
    print("找不到窗口")
    raise SystemExit(1)

rect = wintypes.RECT()
user32.GetWindowRect(hwnd, ctypes.byref(rect))
print("窗口:", rect.left, rect.top, rect.right, rect.bottom)
user32.ShowWindow(hwnd, 9)
user32.SetWindowPos(hwnd, wintypes.HWND(-1), 0, 0, 0, 0, 0x0001 | 0x0002)  # 置顶
user32.SetForegroundWindow(hwnd)
time.sleep(1.8)

rect = wintypes.RECT()
user32.GetWindowRect(hwnd, ctypes.byref(rect))
w = rect.right - rect.left
h = rect.bottom - rect.top
print("尺寸:", w, h)


def click(x, y):
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.15)
    user32.mouse_event(0x0002, 0, 0, 0, 0)   # LEFTDOWN
    time.sleep(0.08)
    user32.mouse_event(0x0004, 0, 0, 0, 0)   # LEFTUP
    time.sleep(0.8)


# 点开始游戏(菜单第一项, 约在窗口高度 50% 处)
click(rect.left + w * 0.5, rect.top + h * 0.50)
time.sleep(2.5)
img = ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom))
img.save(OUT)
print("已截图:", OUT, img.size)
