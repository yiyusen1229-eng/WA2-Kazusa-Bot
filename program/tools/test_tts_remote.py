# -*- coding: utf-8 -*-
"""语音服务放在另一台机器上（手机连家里 PC）——端点解析 / 远程探活 / 不误启动。

    cd program && .\\build_env\\venv\\Scripts\\python.exe tools\\test_tts_remote.py
"""
import http.server
import os
import socket
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))

import tts_client as TC  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:200]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


class _Quiet(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html>ok</html>")

    def log_message(self, *a):
        pass


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main():
    old_url = TC.URL

    print("[1] 端点解析跟着 URL 走")
    TC.URL = "http://127.0.0.1:9880"
    check("本地：endpoint 解析正确", TC.endpoint() == ("127.0.0.1", 9880), TC.endpoint())
    check("本地：is_remote 为假", TC.is_remote() is False)
    TC.URL = "http://100.101.102.103:9880"
    check("远程：endpoint 解析正确", TC.endpoint() == ("100.101.102.103", 9880), TC.endpoint())
    check("远程：is_remote 为真", TC.is_remote() is True)
    TC.URL = "http://192.168.1.5"          # 不带端口
    check("不带端口时回落到默认 9880", TC.endpoint() == ("192.168.1.5", 9880), TC.endpoint())
    TC.URL = "https://tts.example.com:8443"
    check("https + 自定义端口", TC.endpoint() == ("tts.example.com", 8443), TC.endpoint())

    print("[2] 监听地址：默认只听本机，可用环境变量放开")
    os.environ.pop("WA2_TTS_BIND", None)
    check("默认是 127.0.0.1", TC.bind_host() == "127.0.0.1", TC.bind_host())
    os.environ["WA2_TTS_BIND"] = "0.0.0.0"
    check("WA2_TTS_BIND 生效", TC.bind_host() == "0.0.0.0", TC.bind_host())
    os.environ.pop("WA2_TTS_BIND", None)

    print("[3] 远程模式：HTTP 探活、不 spawn 本地进程")
    port = free_port()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), _Quiet)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        TC.URL = "http://192.168.1.5:%d" % port   # 故意写个假 host：探活应该打得通本机这个端口吗？
        # 说明：host 是假的，所以探活必须失败 —— 这正是「探活真的按 URL 走」的证明
        check("假 host 探活失败（说明没再摸 127.0.0.1:9880）", TC._http_ok(timeout=1.0) is False)

        TC.URL = "http://127.0.0.1:%d" % port
        check("真实端口探活成功", TC._http_ok(timeout=1.5) is True)
        TC.URL = "http://localhost:%d" % port
        check("localhost 也算本地", TC.is_remote() is False)
        check("localhost 能探到", TC._http_ok(timeout=1.5) is True)

        print("[4] 远程可用性只看那头通不通（本机没权重也算可用）")
        TC.URL = "http://127.0.0.1:%d" % port
        _proc_before = TC._proc
        ok = TC.start()
        check("start() 复用已有服务成功", ok is True, ok)
        check("没有启动子进程", TC._proc is _proc_before, (TC._proc, _proc_before))
    finally:
        # shutdown() 只停循环，监听套接字还开着（端口仍可 connect），必须 server_close
        srv.shutdown()
        srv.server_close()

    print("[5] 服务关了之后老实报不可达")
    TC.URL = "http://127.0.0.1:%d" % port
    check("端口关了 → _http_ok 假", TC._http_ok(timeout=0.8) is False)

    TC.URL = old_url
    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), "、".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
