# -*- coding: utf-8 -*-
"""自己开游戏, 点开始, 推进几句剧情, 抓图看显示的是中文还是日文"""
import ctypes
import os
import subprocess
import time
from ctypes import wintypes

from PIL import Image

G = r"E:\Games\GALGAMES\WHITE ALBUM2"
EXE = os.path.join(G, "WA2_chs.exe")
OUT = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\work"

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
user32.FindWindowW.restype = wintypes.HWND
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, ctypes.c_uint]
user32.GetWindowDC.restype = wintypes.HDC
user32.GetWindowDC.argtypes = [wintypes.HWND]
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_ulonglong]
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


def shot(h, tag):
    r = wintypes.RECT()
    user32.GetWindowRect(h, ctypes.byref(r))
    w, hh = r.right - r.left, r.bottom - r.top
    wdc = user32.GetWindowDC(h)
    mdc = gdi32.CreateCompatibleDC(wdc)
    bmp = gdi32.CreateCompatibleBitmap(wdc, w, hh)
    gdi32.SelectObject(mdc, bmp)
    user32.PrintWindow(h, mdc, 2)
    bi = BIH()
    bi.biSize = ctypes.sizeof(BIH)
    bi.biWidth = w
    bi.biHeight = -hh
    bi.biPlanes = 1
    bi.biBitCount = 32
    buf = ctypes.create_string_buffer(w * hh * 4)
    gdi32.GetDIBits(mdc, bmp, 0, hh, buf, ctypes.byref(bi), 0)
    img = Image.frombuffer("RGBA", (w, hh), buf.raw, "raw", "BGRA", 0, 1).convert("RGB")
    fp = os.path.join(OUT, "剧情_%s.png" % tag)
    img.save(fp)
    print("  截图 %s %s 亮度 %s" % (os.path.basename(fp), img.size, img.convert("L").getextrema()))
    return img


def click(x, y):
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.1)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.06)
    user32.mouse_event(0x0004, 0, 0, 0, 0)


p = subprocess.Popen([EXE], cwd=G)
time.sleep(14)
h = user32.FindWindowW(None, "WHITE ALBUM2")
print("窗口:", h)
if not h:
    p.terminate()
    raise SystemExit("没窗口")
r = wintypes.RECT()
user32.GetWindowRect(h, ctypes.byref(r))
print("窗口区域:", r.left, r.top, r.right, r.bottom)
shot(h, "1_标题")

# 点「开始游戏」: 菜单在窗口中央偏下, 第一项约 y=52%
cx = r.left + (r.right - r.left) * 0.5
cy = r.top + (r.bottom - r.top) * 0.52
print("点击 开始游戏 (%.0f, %.0f)" % (cx, cy))
click(cx, cy)
time.sleep(4)
shot(h, "2_进入后")

# 连续点击推进剧情
for i in range(6):
    click(r.left + 300, r.top + 300)
    time.sleep(2.2)
shot(h, "3_剧情")
p.terminate()
print("完成")
