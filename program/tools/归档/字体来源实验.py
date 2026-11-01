# -*- coding: utf-8 -*-
"""实验: 临时改名 fon.pak, 启动游戏截图, 看中文还在不在, 然后立刻改回"""
import ctypes
import os
import shutil
import subprocess
import time
from ctypes import wintypes

from PIL import ImageGrab

G = r"E:\Games\GALGAMES\WHITE ALBUM2"
PAK = os.path.join(G, "fon.pak")
BAK = os.path.join(G, "fon.pak.bak")
EXE = os.path.join(G, "WA2_chs.exe")
OUT_DIR = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\work"

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.FindWindowW.restype = wintypes.HWND
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.EnumWindows.argtypes = [ctypes.c_void_p, wintypes.LPARAM]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wintypes.HWND]

proc = None
try:
    if os.path.exists(PAK):
        if os.path.exists(BAK):
            os.remove(BAK)
        os.rename(PAK, BAK)
        print("已改名: fon.pak -> fon.pak.bak")

    proc = subprocess.Popen([EXE], cwd=G)
    print("已启动游戏, 等待窗口…")
    time.sleep(10)

    hwnd = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, l):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(h, buf, 256)
        if "WHITE ALBUM" in buf.value.upper() and user32.IsWindowVisible(h):
            hwnd.append((h, buf.value))
        return True

    user32.EnumWindows(cb, 0)
    print("找到窗口:", hwnd[:3])
    if hwnd:
        h = hwnd[0][0]
        user32.SetWindowPos(h, wintypes.HWND(-1), 0, 0, 0, 0, 0x0001 | 0x0002)
        time.sleep(2)
        r = wintypes.RECT()
        user32.GetWindowRect(h, ctypes.byref(r))
        print("窗口区域:", r.left, r.top, r.right, r.bottom)
        img = ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom))
        fp = os.path.join(OUT_DIR, "无fon_标题界面.png")
        img.save(fp)
        print("已截图:", fp, img.size)
finally:
    if proc:
        proc.terminate()
        time.sleep(1)
    if os.path.exists(BAK):
        if os.path.exists(PAK):
            os.remove(PAK)
        os.rename(BAK, PAK)
        print("已恢复: fon.pak.bak -> fon.pak")
    print("现况:", "fon.pak 存在" if os.path.exists(PAK) else "异常!")
