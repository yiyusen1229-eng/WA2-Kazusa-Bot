# -*- coding: utf-8 -*-
"""决定性实验: 改名 fon.pak 后抓游戏标题界面, 看中文菜单还在不在"""
import ctypes
import os
import subprocess
import time
from ctypes import wintypes

from PIL import Image

G = r"E:\Games\GALGAMES\WHITE ALBUM2"
PAK = os.path.join(G, "fon.pak")
BAK = os.path.join(G, "fon.pak.bak")
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


def capture(tag):
    h = user32.FindWindowW(None, "WHITE ALBUM2")
    if not h:
        print("  没窗口")
        return None
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
    fp = os.path.join(OUT, "实验_%s.png" % tag)
    img.save(fp)
    print("  已存 %s  尺寸 %s  亮度 %s" % (os.path.basename(fp), img.size, img.convert("L").getextrema()))
    return img


print("=== 正常(fon.pak 存在) ===")
p = subprocess.Popen([EXE], cwd=G)
time.sleep(13)
capture("有fon")
p.terminate()
time.sleep(2)

print("\n=== 改名 fon.pak ===")
if os.path.exists(PAK):
    if os.path.exists(BAK):
        os.remove(BAK)
    os.rename(PAK, BAK)
    print("  已改名")
try:
    p = subprocess.Popen([EXE], cwd=G)
    time.sleep(13)
    capture("无fon")
    p.terminate()
    time.sleep(2)
finally:
    if os.path.exists(BAK):
        if os.path.exists(PAK):
            os.remove(PAK)
        os.rename(BAK, PAK)
        print("  fon.pak 已恢复")
print("最终:", "OK" if os.path.exists(PAK) else "错误")
