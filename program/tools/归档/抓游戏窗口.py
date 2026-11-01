# -*- coding: utf-8 -*-
"""用 PrintWindow 抓 DirectDraw 窗口内容"""
import ctypes
import os
import subprocess
import time
from ctypes import wintypes

from PIL import Image

G = r"E:\Games\GALGAMES\WHITE ALBUM2"
EXE = os.path.join(G, "WA2_chs.exe")
OUT = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\work\普窗口.png"

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
user32.FindWindowW.restype = wintypes.HWND
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, ctypes.c_uint]
user32.GetWindowDC.restype = wintypes.HDC
user32.GetWindowDC.argtypes = [wintypes.HWND]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                            ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]


class BIH(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


p = subprocess.Popen([EXE], cwd=G)
try:
    time.sleep(12)
    h = user32.FindWindowW(None, "WHITE ALBUM2")
    print("窗口:", h)
    if not h:
        raise SystemExit("没找到窗口")
    r = wintypes.RECT()
    user32.GetWindowRect(h, ctypes.byref(r))
    w, hh = r.right - r.left, r.bottom - r.top
    print("尺寸:", w, hh)
    wdc = user32.GetWindowDC(h)
    mdc = gdi32.CreateCompatibleDC(wdc)
    bmp = gdi32.CreateCompatibleBitmap(wdc, w, hh)
    gdi32.SelectObject(mdc, bmp)
    ok = user32.PrintWindow(h, mdc, 2)   # PW_RENDERFULLCONTENT
    print("PrintWindow 返回:", ok)
    bi = BIH()
    bi.biSize = ctypes.sizeof(BIH)
    bi.biWidth = w
    bi.biHeight = -hh
    bi.biPlanes = 1
    bi.biBitCount = 32
    buf = ctypes.create_string_buffer(w * hh * 4)
    gdi32.GetDIBits(mdc, bmp, 0, hh, buf, ctypes.byref(bi), 0)
    img = Image.frombuffer("RGBA", (w, hh), buf.raw, "raw", "BGRA", 0, 1)
    img.convert("RGB").save(OUT)
    print("已保存:", OUT, " 亮度:", img.convert("L").getextrema())
finally:
    p.terminate()
