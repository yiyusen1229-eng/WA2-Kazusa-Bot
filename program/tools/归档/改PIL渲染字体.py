# -*- coding: utf-8 -*-
"""让对话框文字用 TrueType 文件渲染(PIL), 绕开 GDI 无法注册的字体

背景:
  汉化版用的 Droid Sans Fallback 字体, GDI 的 AddFontResourceEx/AddFontMemResourceEx
  都拒绝加载(返回 0), 但 FreeType(PIL) 可以正常读取。
  所以 measure / render_block 改成优先用 PIL 渲染, GDI 只作兜底。
"""
import re

P = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\app\gdi_text.py"
s = open(P, encoding="utf-8").read()

# ---------- 1. 增加 PIL 字体缓存 ----------
if "_pil_font" not in s:
    s = s.replace(
        "def _make_dc(w, h):",
        '''_PIL_FONT_CACHE = {}


def _pil_font(size, want_file=True):
    """按字号取 PIL 字体对象; 没有字体文件时返回 None"""
    if not (want_file and os.path.exists(_FONT_FILE)):
        return None
    key = int(size)
    if key not in _PIL_FONT_CACHE:
        try:
            from PIL import ImageFont
            _PIL_FONT_CACHE[key] = ImageFont.truetype(_FONT_FILE, key)
        except Exception:
            _PIL_FONT_CACHE[key] = None
    return _PIL_FONT_CACHE[key]


def _make_dc(w, h):''',
        1,
    )
    print("已加 PIL 字体缓存")

# ---------- 2. measure 优先走 PIL ----------
old_measure = '''def measure(text, size=None, face=None):
    size = size or SIZE
    face = face or FACE
    hdc, bmp = _make_dc(8, 8)'''
new_measure = '''def measure(text, size=None, face=None):
    size = size or SIZE
    face = face or FACE
    ft = _pil_font(size)
    if ft is not None:
        try:
            box = ft.getbbox(text or "国")
            w = max(1, box[2] - box[0])
            h = max(1, box[3] - box[1])
            return w, int(size * 1.05)
        except Exception:
            pass
    hdc, bmp = _make_dc(8, 8)'''
if old_measure in s:
    s = s.replace(old_measure, new_measure, 1)
    print("measure 已改为 PIL 优先")

# ---------- 3. render_block 优先走 PIL ----------
old_draw = '''    hdc, bmp = _make_dc(W, H)
    font = gdi32.CreateFontW(-size, 0, 0, 0, 400, 0, 0, 0,
                             GB2312_CHARSET, OUT_TT_ONLY_PRECIS, 0,
                             ANTIALIASED_QUALITY, 0, face)
    old = gdi32.SelectObject(hdc, font)
    gdi32.SetBkMode(hdc, TRANSPARENT)
    gdi32.SetTextColor(hdc, color[0] | (color[1] << 8) | (color[2] << 16))

    for i, ln in enumerate(lines):
        y = pad + outline_w + i * line_pitch
        for ex in range(embolden + 1):
            for ey in range(embolden + 1):
                gdi32.TextOutW(hdc, pad + outline_w + ex, int(y) + ey, ln, len(ln))

    raw = _read_pixels(hdc, bmp, W, H)
    gdi32.SelectObject(hdc, old)
    gdi32.DeleteObject(font)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(hdc)

    base = Image.frombuffer("RGBA", (W, H), raw, "raw", "BGRA", 0, 1)'''

new_draw = '''    ft = _pil_font(size)
    if ft is not None:
        base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        from PIL import ImageDraw
        dr = ImageDraw.Draw(base)
        for i, ln in enumerate(lines):
            y = pad + outline_w + i * line_pitch
            for ex in range(embolden + 1):
                for ey in range(embolden + 1):
                    dr.text((pad + outline_w + ex, y + ey), ln, font=ft,
                            fill=(color[0], color[1], color[2], 255))
    else:
        hdc, bmp = _make_dc(W, H)
        font = gdi32.CreateFontW(-size, 0, 0, 0, 400, 0, 0, 0,
                                 GB2312_CHARSET, OUT_TT_ONLY_PRECIS, 0,
                                 ANTIALIASED_QUALITY, 0, face)
        old = gdi32.SelectObject(hdc, font)
        gdi32.SetBkMode(hdc, TRANSPARENT)
        gdi32.SetTextColor(hdc, color[0] | (color[1] << 8) | (color[2] << 16))
        for i, ln in enumerate(lines):
            y = pad + outline_w + i * line_pitch
            for ex in range(embolden + 1):
                for ey in range(embolden + 1):
                    gdi32.TextOutW(hdc, pad + outline_w + ex, int(y) + ey, ln, len(ln))
        raw = _read_pixels(hdc, bmp, W, H)
        gdi32.SelectObject(hdc, old)
        gdi32.DeleteObject(font)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(hdc)
        base = Image.frombuffer("RGBA", (W, H), raw, "raw", "BGRA", 0, 1)'''

if old_draw in s:
    s = s.replace(old_draw, new_draw, 1)
    print("render_block 已改为 PIL 优先")
else:
    print("!! render_block 片段未匹配")

open(P, "w", encoding="utf-8").write(s)
import ast
ast.parse(s)
print("语法 OK")
