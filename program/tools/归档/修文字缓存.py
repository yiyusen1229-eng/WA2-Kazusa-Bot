# -*- coding: utf-8 -*-
"""修复文字缓存: 缓存键里必须包含字体文件与全部渲染参数

原来 key = md5(RENDER_VER|text|maxw|size|embolden)
RENDER_VER 写死 25, 换字体不会改键 -> 永远命中旧图(所以四个版本字一模一样)。
"""
import os
import re
import shutil

P = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\app\gdi_text.py"
s = open(P, encoding="utf-8").read()

old = s[s.index("def render_cached"):]
old_fn = old[:old.index("return open(fp")]

new_head = '''def render_cached(text, maxw=1200, size=None, embolden=0, outline_w=None):
    # 缓存键必须包含所有影响像素的参数, 尤其是字体文件
    try:
        _fsig = "%s|%d" % (_FONT_FILE, int(os.path.getmtime(_FONT_FILE)))
    except Exception:
        _fsig = str(_FONT_FILE)
    key = hashlib.md5((
        "%s|%s|%d|%d|%d|%d|%s|%d|%.2f|%.2f|%.2f|%d|%d" % (
            _fsig, text, maxw, size or SIZE, embolden,
            OUTLINE_W if outline_w is None else outline_w,
            str(EMULATE_BITMAP), BITMAP_SIZE,
            BODY_BLUR, EDGE_BLUR, WHITE_BOOST, SIZE, PAD)
    ).encode("utf-8")).hexdigest()
    os.makedirs(CACHE_DIR, exist_ok=True)
    fp = os.path.join(CACHE_DIR, key + ".png")
    if os.path.exists(fp):
        return '''

s = s.replace(old_fn, new_head, 1)
open(P, "w", encoding="utf-8").write(s)

import ast
ast.parse(s)
print("缓存键已重写, 语法 OK")
print([l for l in s.split("\n") if "hashlib.md5" in l][:2])
