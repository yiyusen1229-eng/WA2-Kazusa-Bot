# -*- coding: utf-8 -*-
"""用 GDI(微软雅黑 Bold 30px) 渲染字形, 精确匹配 subfont.tga 的字模"""
import ctypes
from ctypes import wintypes

import numpy as np
from PIL import Image

ATLAS = r"E:\Games\GALGAMES\WHITE ALBUM2\subfont.tga"
CELL = 32

gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


gdi32.CreateFontW.restype = wintypes.HANDLE
gdi32.CreateFontW.argtypes = [ctypes.c_int] * 5 + [wintypes.DWORD] * 8 + [wintypes.LPCWSTR]
gdi32.TextOutW.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.LPCWSTR, ctypes.c_int]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                            ctypes.c_void_p, ctypes.POINTER(BITMAPINFO), wintypes.UINT]
gdi32.PatBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                         ctypes.c_int, wintypes.DWORD]
gdi32.SetTextColor.argtypes = [wintypes.HDC, wintypes.DWORD]
gdi32.SetBkMode.argtypes = [wintypes.HDC, ctypes.c_int]
user32.GetDC.restype = wintypes.HDC
user32.GetDC.argtypes = [wintypes.HWND]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteObject.restype = wintypes.BOOL
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.DeleteDC.restype = wintypes.BOOL
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]


def gdi_glyph(ch, size=30, weight=700, face="Microsoft YaHei"):
    hdc = user32.GetDC(None)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, CELL, CELL)
    gdi32.SelectObject(mem, bmp)
    gdi32.PatBlt(mem, 0, 0, CELL, CELL, 0x00000042)
    font = gdi32.CreateFontW(-size, 0, 0, 0, weight, 0, 0, 0, 134, 0, 0, 4, 0, face)
    old = gdi32.SelectObject(mem, font)
    gdi32.SetBkMode(mem, 1)
    gdi32.SetTextColor(mem, 0x00FFFFFF)
    gdi32.TextOutW(mem, 0, 0, ch, 1)

    bi = BITMAPINFO()
    bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.bmiHeader.biWidth = CELL
    bi.bmiHeader.biHeight = -CELL
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    bi.bmiHeader.biCompression = 0
    buf = ctypes.create_string_buffer(CELL * CELL * 4)
    gdi32.GetDIBits(mem, bmp, 0, CELL, buf, ctypes.byref(bi), 0)

    gdi32.SelectObject(mem, old)
    gdi32.DeleteObject(font)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(None, hdc)

    arr = np.frombuffer(buf.raw, dtype=np.uint8).reshape(CELL, CELL, 4)
    gray = arr[:, :, :3].max(axis=2)
    return (gray > 110).astype(np.float32)


def norm(m):
    ys, xs = np.where(m > 0)
    if len(ys) == 0:
        return None
    crop = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = crop.shape
    s = 26.0 / max(w, h)
    img = Image.fromarray((crop * 255).astype(np.uint8)).resize(
        (max(1, int(w * s)), max(1, int(h * s))), Image.LANCZOS)
    out = np.zeros((CELL, CELL), np.float32)
    oy, ox = (CELL - img.height) // 2, (CELL - img.width) // 2
    out[oy:oy + img.height, ox:ox + img.width] = np.array(img) / 255.0
    return (out > 0.43).astype(np.float32).ravel()


a, b = gdi_glyph("求"), gdi_glyph("吧")
print("渲染自检: 两字不同 ->", not np.array_equal(a, b), " 墨迹", int(a.sum()), int(b.sum()))

alpha = np.array(Image.open(ATLAS).convert("RGBA").split()[3])
rows = alpha.shape[0] // CELL
cells, ids = [], []
for k in range(rows * 20):
    r, c = divmod(k, 20)
    m = (alpha[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL] > 110).astype(np.float32)
    v = norm(m)
    if v is not None:
        ids.append(k)
        cells.append(v)
cell_mat = np.stack(cells)
print("格子:", len(ids))

for ch in "求你撤前言吧和纱有事":
    best = (0.0, -1, 0)
    for size in (29, 30, 31):
        v = norm(gdi_glyph(ch, size))
        if v is None:
            continue
        inter = (cell_mat * v).sum(1)
        union = cell_mat.sum(1) + v.sum() - inter
        iou = inter / np.maximum(union, 1)
        j = int(iou.argmax())
        if iou[j] > best[0]:
            best = (float(iou[j]), ids[j], size)
    print("  %s -> IoU %.3f  格子 %d  (字号 %d)" % (ch, best[0], best[1], best[2]))
