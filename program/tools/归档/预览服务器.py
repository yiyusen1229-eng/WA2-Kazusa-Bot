# -*- coding: utf-8 -*-
"""只服务 ui2 的预览服务器, 用来在浏览器里确认字体效果"""
import os
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

UI = r"E:/IDM下载目录/DSH工作产生文件/WA2-Kazusa-Bot/app/ui2"
PORT = 8903


class H(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=UI, **kw)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a):
        pass

    def translate_path(self, path):
        # 把 /game/xxx 映射到 UI 目录
        p = path.split("?", 1)[0]
        if p.startswith("/game/"):
            p = p[len("/game/"):] or "index.html"
        p = p.lstrip("/")
        return os.path.join(UI, p.replace("/", os.sep))


srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
print("预览地址: http://127.0.0.1:%d/game/index.html" % PORT, flush=True)
srv.serve_forever()
