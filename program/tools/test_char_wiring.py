# -*- coding: utf-8 -*-
"""资源接线的端到端自测：起一个假模型服务 + 真后端，看 system 里到底塞了什么。

跑法：
    cd program
    build_env/venv/Scripts/python.exe tools/test_char_wiring.py

为什么这么测：只读代码看不出「导入的提示词有没有真的替换人设」。这里把
`/api/chat` 的 base_url 指到本地假模型，假模型把收到的 system prompt 原样记账，
测试再断言里面有没有导入的内容。不花钱、不联网。

测试用 WA2_USER_DIR 把 char/ 指到临时目录，不碰运行时真正的导入文件。
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
ENV = os.path.join(PROGRAM, "build_env")
PY = os.path.join(ENV, "venv", "Scripts", "python.exe")
ASSETS = os.path.join(PROGRAM, "res", "assets")

FAILS = []
CAPTURED = {}


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name + (("  " + str(extra)[:200]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class FakeModel(BaseHTTPRequestHandler):
    """假模型：记下收到的 messages，回一句中文（免得走日语翻译）"""

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            body = {}
        CAPTURED["messages"] = body.get("messages") or []
        out = {"choices": [{"message": {"content": "「嗯。」"}}], "usage": {}}
        data = json.dumps(out, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def get_json(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def post_json(url, obj, timeout=60):
    req = urllib.request.Request(url, data=json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def post_bytes(url, data, timeout=20):
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/octet-stream"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def wait_up(url, seconds=20):
    t0 = time.time()
    while time.time() - t0 < seconds:
        try:
            get_json(url, timeout=2)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def sync_backend():
    """把 src/*.py 同步到 build_env（和 run_dev.py 一样），否则测的是旧代码"""
    src = os.path.join(PROGRAM, "src")
    for f in os.listdir(src):
        if f.endswith(".py"):
            shutil.copy2(os.path.join(src, f), os.path.join(ENV, f))


def main():
    sync_backend()
    fake_port = free_port()
    fake = ThreadingHTTPServer(("127.0.0.1", fake_port), FakeModel)
    threading.Thread(target=fake.serve_forever, daemon=True).start()

    tmp = tempfile.mkdtemp(prefix="wa2_wiring_")
    port = free_port()
    env = os.environ.copy()
    env["WA2_USER_DIR"] = tmp
    env["WA2_ASSETS_DIR"] = ASSETS
    env["WA2_NO_MODELS"] = "1"          # 不拉起语音/翻译进程
    proc = subprocess.Popen([PY, "main.py", "--serve-only", "--port", str(port)],
                            cwd=ENV, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = "http://127.0.0.1:%d" % port
    try:
        check("后端起来了", wait_up(base + "/api/ping"))
        if FAILS:
            return 1

        def chat():
            CAPTURED.clear()
            d = post_json(base + "/api/chat", {
                "messages": [{"role": "user", "content": "你好"}],
                "base_url": "http://127.0.0.1:%d/v1" % fake_port,
                "model": "deepseek-flash",
            })
            sys_msg = ""
            for m in CAPTURED.get("messages") or []:
                if m.get("role") == "system":
                    sys_msg = m.get("content") or ""
                    break
            return d, sys_msg

        print("[1] 没导入：人设还是 persona_core")
        d, sys0 = chat()
        check("对话能跑通", (d or {}).get("reply"), repr(d)[:300])
        check("system 是原人设", "冬马和纱" in sys0, sys0[:200])
        st0 = get_json(base + "/api/special/status")["files"]
        check("status：没有导入文件", st0.get("prompt") is None, repr(st0))

        print("\n[2] 导入提示词 → system 换成它")
        persona = "测试提示词：你现在的名字叫测试和纱，说话必须带「测试」两个字。"
        r = post_bytes(base + "/api/special/upload?kind=prompt&name=" +
                       urllib.parse.quote("测试提示词.txt"), persona.encode("utf-8"))
        check("上传成功", r.get("ok"), repr(r))
        d, sys1 = chat()
        check("system 里有导入的提示词", persona in sys1, sys1[:300])
        check("原人设被替换掉了", "你是冬马和纱，钢琴家" not in sys1, sys1[:300])

        print("\n[3] 导入记忆书 + 文本世界书 → 每轮都带上")
        mem = "测试记忆：我们约好周日去海边，你欠我一顿饭。"
        wbt = "测试世界书：这座城市的车站叫峰城站，冬天会下雪。"
        post_bytes(base + "/api/special/upload?kind=memory&name=" +
                   urllib.parse.quote("旧事.txt"), mem.encode("utf-8"))
        post_bytes(base + "/api/special/upload?kind=worldbook&name=" +
                   urllib.parse.quote("设定.md"), wbt.encode("utf-8"))
        d, sys2 = chat()
        check("记忆书进了 system", mem in sys2, sys2[-400:])
        check("世界书文本进了 system", wbt in sys2, sys2[-400:])
        check("记忆书和世界书分开写", "你记得的旧事" in sys2 and "设定补充" in sys2, sys2[-600:])

        print("\n[4] status 能看到生效的是哪份")
        st = get_json(base + "/api/special/status")["files"]
        check("prompt 文件", (st.get("prompt") or {}).get("file") == "测试提示词.txt", repr(st))
        check("memory 文件", (st.get("memory") or {}).get("file") == "旧事.txt", repr(st))
        check("worldbook 文件", (st.get("worldbook") or {}).get("file") == "设定.md", repr(st))
        check("人设字数对得上", st.get("prompt_chars") == len(persona), repr(st))

        print("\n[5] 删掉导入 → 回落到原人设")
        for kind, name in (("prompt", "测试提示词.txt"), ("memory", "旧事.txt"), ("worldbook", "设定.md")):
            sub = {"prompt": "prompt", "memory": "memory", "worldbook": "worldbook"}[kind]
            os.remove(os.path.join(tmp, "char", sub, name))
        d, sys3 = chat()
        check("回落成功", "冬马和纱" in sys3 and "测试提示词" not in sys3, sys3[:200])
        check("记忆书也没了", "测试记忆" not in sys3)
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        try:
            fake.shutdown()
        except Exception:
            pass
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + ("全部通过" if not FAILS else "失败 %d 项：%s" % (len(FAILS), "、".join(FAILS))))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
