# -*- coding: utf-8 -*-
"""界面自测探针：用真实的 WebView2 打开界面，执行 JS，必要时截图。

为什么需要它：
  * `main.py --serve-only` 只验证后端，验证不了「JS 有没有真的跑起来」；
  * 浏览器手工点太慢，而且这台机器的自动化通道在界面动画下不稳定；
  * 这里直接开一个 WebView2 窗口（和正式程序同一个引擎），用 evaluate_js 驱动，
    配合 Win32 PrintWindow 截图，能看到「执行路径」和「画面」两方面的证据。

用法（先起后端服务）：
    python main.py --serve-only            # 另开一个终端，记下端口
    python tools/ui_probe.py --url http://127.0.0.1:8771/game/index.html \\
        --js setup.js --check check.js --wait 1200 --shot out.png

约定：
  * --js     打开页面后先执行（可以用来点按钮、改状态）
  * --wait   执行完 --js 后等多久（毫秒），给异步请求/动画留时间
  * --check  等待结束后再执行一次，通常用来读结果（打印在 "check" 里）
  * --shot   截图路径（PNG）
  * 两个 JS 文件都写 `return <可 JSON 化的值>`（或最后一个表达式），
    结果会原样打印出来。
"""
import argparse
import ctypes
import json
import os
import sys
import time
from ctypes import wintypes

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import webview  # noqa: E402
from PIL import Image  # noqa: E402

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


def find_window(title):
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        n = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(n + 2)
        user32.GetWindowTextW(hwnd, buf, n + 2)
        if title in buf.value:
            found.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return found[0] if found else 0


def grab(hwnd, path):
    """PrintWindow 抓整窗（含边框），存 PNG。"""
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    if w <= 0 or h <= 0:
        raise RuntimeError("bad window rect %sx%s" % (w, h))
    hdc = user32.GetWindowDC(hwnd)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    old = gdi32.SelectObject(mem, bmp)
    try:
        user32.PrintWindow(hwnd, mem, 2)          # PW_RENDERFULLCONTENT
        bi = BITMAPINFOHEADER()
        bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bi.biWidth, bi.biHeight = w, -h
        bi.biPlanes, bi.biBitCount = 1, 32
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bi), 0)
        img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1)
        img.convert("RGB").save(path)
    finally:
        gdi32.SelectObject(mem, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(hwnd, hdc)
    return w, h


def read_js(path):
    if not path:
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def main():
    ap = argparse.ArgumentParser(description="界面自测探针（真实 WebView2）")
    ap.add_argument("--url", required=True)
    ap.add_argument("--js", help="打开后执行一次的脚本")
    ap.add_argument("--check", help="等待结束后再执行一次的脚本（读结果用）")
    ap.add_argument("--wait", type=int, default=1000, help="两步之间的等待毫秒数")
    ap.add_argument("--shot", help="截图输出路径（PNG）")
    ap.add_argument("--title", default="WA2 Probe")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    args = ap.parse_args()

    out = {"url": args.url}

    def runner(window):
        try:
            for _ in range(80):
                time.sleep(0.25)
                try:
                    if window.evaluate_js("document.readyState") == "complete":
                        break
                except Exception:
                    pass
            time.sleep(1.0)                      # 让 DOMContentLoaded 之后的脚本跑完

            setup = read_js(args.js)
            if setup:
                out["setup"] = window.evaluate_js(setup)

            time.sleep(max(0, args.wait) / 1000.0)

            check = read_js(args.check)
            if check:
                out["check"] = window.evaluate_js(check)

            if args.shot:
                hwnd = find_window(args.title)
                if hwnd:
                    out["shot"] = grab(hwnd, args.shot)
                else:
                    out["error"] = "window not found for screenshot"
        except Exception as e:                    # noqa: BLE001
            out["error"] = "%s: %s" % (type(e).__name__, e)
        finally:
            try:
                window.destroy()
            except Exception:
                pass

    win = webview.create_window(args.title, args.url,
                                width=args.width, height=args.height)
    webview.start(runner, win, private_mode=True, debug=False)
    print(json.dumps(out, ensure_ascii=False, indent=1)[:12000])


if __name__ == "__main__":
    main()
