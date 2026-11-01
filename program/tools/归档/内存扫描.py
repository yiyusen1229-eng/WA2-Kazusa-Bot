# -*- coding: utf-8 -*-
"""读游戏进程内存, 找屏幕上的中文句子, 确认编码与字形来源"""
import ctypes
import os
import struct
import time
from ctypes import wintypes

G = r"E:\Games\GALGAMES\WHITE ALBUM2"
EXE = os.path.join(G, "WA2_chs.exe")

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

k32.OpenProcess.restype = wintypes.HANDLE
k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
k32.VirtualQueryEx.argtypes = [wintypes.HANDLE, wintypes.LPCVOID,
                               ctypes.POINTER(ctypes.c_char * 48), ctypes.c_size_t]
k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.CloseHandle.argtypes = [wintypes.HANDLE]
user32.FindWindowW.restype = wintypes.HWND
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]


def scan(pid, patterns, max_scan=1500 * 1024 * 1024):
    h = k32.OpenProcess(0x0010 | 0x0400, False, pid)   # VM_READ | QUERY_INFO
    if not h:
        print("  打不开进程")
        return {}
    results = {k: [] for k in patterns}
    addr = 0
    total = 0
    mbi = (ctypes.c_char * 48)()
    MEM_COMMIT = 0x1000
    while addr < 0x7FFFFFFF and total < max_scan:
        got = k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), 48)
        if not got:
            break
        base, = struct.unpack_from("<Q", mbi, 0)
        size, = struct.unpack_from("<Q", mbi, 24)
        state, = struct.unpack_from("<I", mbi, 32)
        protect, = struct.unpack_from("<I", mbi, 36)
        if size == 0:
            break
        if state == MEM_COMMIT and protect not in (0x01, 0x00):
            buf = ctypes.create_string_buffer(size)
            n = ctypes.c_size_t(0)
            if k32.ReadProcessMemory(h, ctypes.c_void_p(base), buf, size, ctypes.byref(n)):
                data = buf.raw[:n.value]
                total += len(data)
                for name, pat in patterns.items():
                    start = 0
                    while True:
                        i = data.find(pat, start)
                        if i < 0:
                            break
                        if len(results[name]) < 5:
                            results[name].append(base + i)
                        start = i + 1
        addr = base + size
    k32.CloseHandle(h)
    print("  扫描 %.0f MB" % (total / 1048576))
    return results


import subprocess
p = subprocess.Popen([EXE], cwd=G)
time.sleep(15)
h = user32.FindWindowW(None, "WHITE ALBUM2")
if not h:
    p.terminate()
    raise SystemExit("没窗口")
print("游戏进程 PID:", p.pid)

import ctypes
from ctypes import wintypes as wt
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.mouse_event.argtypes = [wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, ctypes.c_ulonglong]


def click(x, y, wait=1.6):
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.1)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.06)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(wait)


# 进入剧情
click(768, 432, 3)     # 开始游戏
click(768, 720, 5)     # Initial Start
for _ in range(6):
    click(768, 432, 2.2)

patterns = {
    "GBK 终于": "终于".encode("gbk"),
    "GBK 起来": "起来".encode("gbk"),
    "SJIS 終": "終".encode("shift_jis"),
    "UTF16 终于": "终于".encode("utf-16-le"),
}
print("扫描内存…")
res = scan(p.pid, patterns)
for k, v in res.items():
    print("  %-12s 命中 %d 处: %s" % (k, len(v), [hex(x) for x in v[:3]]))
p.terminate()
