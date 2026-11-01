# -*- coding: utf-8 -*-
"""逐字字体回退: 日文字体优先, 缺字回退中文字体

依据反编译结论: 游戏用日文字模图(Gothic/Mincho)画所有汉字,
所以字形应当是日文风格; 日文没有的简体字才回退中文。
"""
import os
import re

P = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\app\gdi_text.py"
s = open(P, encoding="utf-8").read()

if "FALLBACK_FONT" in s:
    print("已存在回退逻辑")
else:
    # 1) 配置: 主字体(日文) + 回退字体(中文)
    s = s.replace(
        "_FONT_FILE = r\"C:/Windows/Fonts/msyhbd.ttc\"",
        "_FONT_FILE = r\"C:/Windows/Fonts/msgothic.ttc\"\n"
        "# 日文字体缺简体字时, 逐字回退到这个字体\n"
        "FALLBACK_FONT = r\"C:/Windows/Fonts/msyhbd.ttc\"",
        1,
    )
    print("已配置主/回退字体")

    # 2) 载入 cmap 判断某字是否被主字体覆盖
    helper = '''

_CMAP = None
_FALLBACK_CMAP = None


def _load_cmaps():
    global _CMAP, _FALLBACK_CMAP
    if _CMAP is not None:
        return
    try:
        from fontTools.ttLib import TTFont
    except Exception:
        _CMAP = set()
        _FALLBACK_CMAP = set()
        return
    def cmap_of(path):
        try:
            if path.lower().endswith((".ttc", ".otc")):
                f = TTFont(path, fontNumber=0, lazy=True)
            else:
                f = TTFont(path, lazy=True)
            s = set()
            for t in f["cmap"].tables:
                s.update(t.cmap.keys())
            f.close()
            return s
        except Exception:
            return set()
    _CMAP = cmap_of(_FONT_FILE)
    _FALLBACK_CMAP = cmap_of(FALLBACK_FONT)


def font_for_char(ch):
    """返回该字应使用的字体文件"""
    _load_cmaps()
    if not _CMAP:
        return _FONT_FILE
    if ord(ch) in _CMAP:
        return _FONT_FILE
    if _FALLBACK_CMAP and ord(ch) in _FALLBACK_CMAP:
        return FALLBACK_FONT
    return _FONT_FILE


def split_runs(text):
    """把一行按所用字体切成若干段: [(字体, 子串), ...]"""
    runs = []
    for ch in text:
        fp = font_for_char(ch)
        if runs and runs[-1][0] == fp:
            runs[-1][1].append(ch)
        else:
            runs.append([fp, [ch]])
    return [(fp, "".join(cs)) for fp, cs in runs]

'''
    # 插到 _pil_font 之前
    idx = s.index("def _pil_font")
    s = s[:idx] + helper + s[idx:]
    print("已加入字体回退函数")

    # 3) 绘制时按段换字体
    old_draw = '''        dr = ImageDraw.Draw(base)
        for i, ln in enumerate(lines):
            y = pad + outline_w + i * line_pitch
            for ex in range(embolden + 1):
                for ey in range(embolden + 1):
                    dr.text((pad + outline_w + ex, y + ey), ln, font=ft,
                            fill=(color[0], color[1], color[2], 255))'''
    new_draw = '''        dr = ImageDraw.Draw(base)
        for i, ln in enumerate(lines):
            y = pad + outline_w + i * line_pitch
            x = pad + outline_w
            for fp, seg in split_runs(ln):
                f_seg = _pil_font(size, fp)
                for ex in range(embolden + 1):
                    for ey in range(embolden + 1):
                        dr.text((x + ex, y + ey), seg, font=f_seg,
                                fill=(color[0], color[1], color[2], 255))
                if f_seg is not None:
                    x += f_seg.getlength(seg)'''
    if old_draw in s:
        s = s.replace(old_draw, new_draw, 1)
        print("已改为逐段绘制")
    else:
        print("!! 绘制段未匹配")

    # 4) _pil_font 支持指定字体
    s = s.replace("def _pil_font(size):", "def _pil_font(size, path=None):", 1)
    s = s.replace('    key = size\n', '    key = (size, path or _FONT_FILE)\n', 1)
    if "key = (size, path or _FONT_FILE)" not in s:
        # 尝试另一种缓存写法
        m = re.search(r"def _pil_font\(size, path=None\):\n(.*?)\n\n", s, re.S)
        print("_pil_font 缓存写法需人工确认")
    open(P, "w", encoding="utf-8").write(s)
    print("已写入")

import ast
ast.parse(open(P, encoding="utf-8").read())
print("语法 OK")
