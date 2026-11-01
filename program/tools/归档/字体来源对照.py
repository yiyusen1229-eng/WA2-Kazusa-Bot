# -*- coding: utf-8 -*-
"""对照实验: 有 fon.pak / 无 fon.pak, 各启动一次并多次截图"""
import ctypes
import os
import subprocess
import time
from ctypes import wintypes

from PIL import ImageGrab

G = r"E:\Games\GALGAMES\WHITE ALBUM2"
PAK = os.path.join(G, "fon.pak")
BAK = os.path.join(G, "fon.pak.bak")
EXE = os.path.join(G, "WA2_chs.exe")
OUT = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\work"

user32 = ctypes.WinDLL("user32", use_last_error=True)
user32.FindWindowW.restype = wintypes.HWND
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]


def run(label, rename_pak):
    print("\n=== %s ===" % label)
    if rename_pak and os.path.exists(PAK):
        if os.path.exists(BAK):
            os.remove(BAK)
        os.rename(PAK, BAK)
        print("  fon.pak 已改名")
    p = None
    try:
        p = subprocess.Popen([EXE], cwd=G)
        for wait in (8, 6, 6):
            time.sleep(wait)
            if p.poll() is not None:
                print("  进程已退出, 返回码 %s (崩溃)" % p.returncode)
                break
            h = user32.FindWindowW(None, "WHITE ALBUM2")
            if not h:
                print("  窗口还没出现")
                continue
            user32.SetWindowPos(h, wintypes.HWND(-1), 0, 0, 0, 0, 0x0001 | 0x0002)
            time.sleep(1)
            r = wintypes.RECT()
            user32.GetWindowRect(h, ctypes.byref(r))
            if r.right - r.left < 100:
                print("  窗口尺寸异常")
                continue
            img = ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom))
            fp = os.path.join(OUT, "%s_%dx%d.png" % (label, img.width, img.height))
            img.save(fp)
            # 判断是否全黑
            ex = img.convert("L").getextrema()
            print("  截图 %s  亮度范围 %s" % (os.path.basename(fp), ex))
            break
    finally:
        if p and p.poll() is None:
            p.terminate()
            time.sleep(1)
        if rename_pak and os.path.exists(BAK):
            if os.path.exists(PAK):
                os.remove(PAK)
            os.rename(BAK, PAK)
            print("  fon.pak 已恢复")


run("有fon", False)
run("无fon", True)
print("\n最终:", "fon.pak 存在" if os.path.exists(PAK) else "异常!")
