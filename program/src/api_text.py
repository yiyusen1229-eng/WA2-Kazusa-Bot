# -*- coding: utf-8 -*-
"TextApi 的 mixin：从 main.py 拆出，方法体未改动。"

import os

import cache_io
import diag


class TextApi:
    """见 main.Handler；从 main 注入运行时全局。"""

    def _text_img(self):
        from main import (GLIB, _RENDER_LOCK, _TEXT_CACHE, _TEXT_CACHE_MAX, _text_disk_path, qs)
        """把文字渲染成 PNG（和对话框走同一套字模流程）

        参数（正式名 / 兼容旧名）：
            text            / t            要渲染的文字
            plain           / p            1 = 无描边、无边距
            max_width       / w            单行最大像素宽
            chars_per_line  / per_line     单行最多几个全角字（不传用默认 20）
            size            / s            兼容旧参数的兜底字号（仅 GLIB 回退用）
            embolden        / e            兼容旧参数的加粗（仅 GLIB 回退用）
            color           / c            染色，RRGGBB
            tight           /              1 = 半角字符（数字/字母/符号）走紧凑步进
        """
        from urllib.parse import urlparse, parse_qs
        try:
            q = parse_qs(urlparse(self.path).query)
            text = qs(q, ("text", "t")).strip()
            plain = qs(q, ("plain", "p"), "0") == "1"
            try:
                max_width = int(qs(q, ("max_width", "w"), "1200"))
            except ValueError:
                max_width = 1200
            try:
                chars_per_line = int(qs(q, ("chars_per_line", "per_line"), "0")) or None
            except ValueError:
                chars_per_line = None
            color = qs(q, ("color", "c")).strip().lstrip("#") or None
            tight = qs(q, ("tight",), "0") == "1"
            size = int(qs(q, ("size", "s"), "56") or 56)
            embolden = int(qs(q, ("embolden", "e"), "0") or 0)
            if not text:
                text = " "
            _key = (text, plain, max_width, chars_per_line, color, tight)
            _disk = _text_disk_path(_key)
            _TEXT_DISK = _disk
            if os.path.exists(_disk):
                # 坏缓存（0 字节 / 半截）当没有：cache_io 会删掉它，下面重新渲染
                data = cache_io.read_image(_disk)
                if data:
                    diag.count("text.disk")
                    self.send_response(200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "public, max-age=86400")
                    self.end_headers()
                    self.wfile.write(data)
                    return
            if _key in _TEXT_CACHE:
                data = _TEXT_CACHE[_key]
                diag.count("text.mem")
            else:
                diag.count("text.render")
                try:
                    import io as _io
                    import sub_render
                    with _RENDER_LOCK:
                        img = sub_render.render_block(
                            text, maxw=max_width, stroke=not plain,
                            margin=(None if not plain else 0), per_line=chars_per_line,
                            color=color, tight=tight)
                        _buf = _io.BytesIO()
                        img.save(_buf, "PNG")
                        data = _buf.getvalue()
                        # 缓存上限：超过 400 条就丢掉最早的，避免内存一直涨
                        if len(_TEXT_CACHE) >= 400:
                            try:
                                _TEXT_CACHE.pop(next(iter(_TEXT_CACHE)))
                            except Exception:
                                _TEXT_CACHE.clear()
                except Exception:
                    if not GLIB:
                        raise
                    data = GLIB.render_cached(text, maxw=max_width, size=size, embolden=embolden)
                if len(_TEXT_CACHE) < _TEXT_CACHE_MAX:
                    _TEXT_CACHE[_key] = data
                try:
                    if not os.path.exists(_disk):
                        with open(_disk, "wb") as _f:
                            _f.write(data)
                except Exception:
                    pass
        except Exception as e:
            import traceback
            try:
                open(os.path.join(os.environ.get("TEMP", "."), "wa2_text_error.log"), "a", encoding="utf-8").write(
                    traceback.format_exc() + "\n----\n")
            except Exception:
                pass
            return self._json({"error": str(e)}, 500)
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
