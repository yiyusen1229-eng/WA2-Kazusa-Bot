# -*- coding: utf-8 -*-
"""记忆书机制的端到端自测：读档复制 → 缓存生效 → 存档快照 → 定时重打包。

跑法：
    cd program
    build_env/venv/Scripts/python.exe tools/test_memory_flow.py

为什么这么测：光看代码看不出「读档到底有没有把记忆书接上」「存档会不会每轮
偷偷再总结一遍」。这里起真后端 + 假模型：

  · 假模型把每次请求记账：聊天请求、总结请求分开数
  · /api/session/load 之后直接读 cache/memory_runtime.json，看有没有复制过去
  · 存档后对比 save.memory 和缓存，并断言「存档过程中没有发生总结调用」
  · 连发 6 轮，验证第 6 轮触发后台重打包（repack_turns = 6）

用 WA2_SESS_DIR / WA2_CACHE_DIR / WA2_USER_DIR 把运行时目录指到临时目录，
不碰真实存档和缓存。
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
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
ENV = os.path.join(PROGRAM, "build_env")
PY = os.path.join(ENV, "venv", "Scripts", "python.exe")
ASSETS = os.path.join(PROGRAM, "res", "assets")
sys.path.insert(0, os.path.join(PROGRAM, "src"))
import memory as M  # noqa: E402

FAILS = []
CHAT_CALLS = []
SUM_CALLS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:400]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class FakeModel(BaseHTTPRequestHandler):
    """聊天请求正常回一句；总结请求（system 是记忆整理器）回 JSON 条目"""

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            body = {}
        msgs = body.get("messages") or []
        sys_msg = msgs[0].get("content", "") if msgs and msgs[0].get("role") == "system" else ""
        if "对话记忆整理器" in sys_msg:
            SUM_CALLS.append(body)
            payload = {"entries": [
                {"text": "总结出的新条目 %d" % len(SUM_CALLS), "kind": "event"},
                {"text": "当前进展：还在测试", "kind": "progress"},
            ]}
            content = json.dumps(payload, ensure_ascii=False)
        else:
            CHAT_CALLS.append(body)
            content = "「嗯。」"
        out = {"choices": [{"message": {"content": content}}], "usage": {}}
        data = json.dumps(out, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def get_json(url, timeout=20):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def post_json(url, obj, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def wait_up(url, seconds=25):
    t0 = time.time()
    while time.time() - t0 < seconds:
        try:
            get_json(url, timeout=2)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def sync_backend():
    for f in os.listdir(os.path.join(PROGRAM, "src")):
        if f.endswith(".py"):
            shutil.copy2(os.path.join(PROGRAM, "src", f), os.path.join(ENV, f))


def main():
    sync_backend()
    fake_port = free_port()
    fake = ThreadingHTTPServer(("127.0.0.1", fake_port), FakeModel)
    threading.Thread(target=fake.serve_forever, daemon=True).start()

    tmp = tempfile.mkdtemp(prefix="wa2_memflow_")
    sess_dir = os.path.join(tmp, "sessions")
    cache_dir = os.path.join(tmp, "cache")
    user_dir = os.path.join(tmp, "user")
    os.makedirs(sess_dir, exist_ok=True)
    os.makedirs(cache_dir, exist_ok=True)
    os.makedirs(user_dir, exist_ok=True)

    port = free_port()
    env = os.environ.copy()
    env["WA2_SESS_DIR"] = sess_dir
    env["WA2_CACHE_DIR"] = cache_dir
    env["WA2_USER_DIR"] = user_dir
    env["WA2_ASSETS_DIR"] = ASSETS
    env["WA2_NO_MODELS"] = "1"
    env["WA2_MEM_URL"] = "http://127.0.0.1:%d/v1" % fake_port   # 总结也走假模型，别烧真 token
    proc = subprocess.Popen([PY, "main.py", "--serve-only", "--port", str(port)],
                            cwd=ENV, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = "http://127.0.0.1:%d" % port
    try:
        check("后端起来了", wait_up(base + "/api/ping"))
        if FAILS:
            return 1

        cfg = get_json(base + "/api/special/cfg")["cfg"]
        ctx = int(cfg["cloud_ctx"])
        trig = int(ctx * cfg["trigger_ratio"])
        recent_b = int(ctx * cfg["recent_ratio"])
        print("预算：ctx=%d 触发=%d 最近段=%d" % (ctx, trig, recent_b))

        # 造一段超过阈值的对话（每条 ~45 字）
        body_txt = "这是用来撑上下文的一句测试对话，长度大概四十五个字左右，反复出现。"
        n = int(trig / 45 * 1.3) + 40
        msgs = [{"role": "user" if i % 2 == 0 else "assistant",
                 "content": "第%d句：%s" % (i, body_txt)} for i in range(n)]
        total = M.est_messages(msgs)
        aligned = M.recent_start(msgs, recent_b, 0)
        covered = max(0, aligned - 4)
        print("构造：%d 条 / %d token（阈值 %d），最近段起点 %d，存档 covered=%d"
              % (n, total, trig, aligned, covered))
        check("历史确实超过阈值", total > trig, total)

        entry_a = {"text": "存档里的旧事：玩家说过喜欢冬天", "kind": "event"}
        entry_p = {"text": "当前进展：刚读完档", "kind": "progress"}
        save = {"slot": "m1", "saved_at": "2026-11-02 10:00:00",
                "messages": msgs, "meta": {},
                "memory": {"enabled": True, "generated_at": "2026-11-02 09:59:00",
                           "covered_upto": covered, "entries": [entry_a, entry_p]}}
        with open(os.path.join(sess_dir, "m1.json"), "w", encoding="utf-8") as f:
            json.dump(save, f, ensure_ascii=False)
        with open(os.path.join(sess_dir, "short.json"), "w", encoding="utf-8") as f:
            json.dump({"slot": "short", "saved_at": "2026-11-02 10:00:00",
                       "messages": msgs[:4], "meta": {}}, f, ensure_ascii=False)

        print("\n[1] 读档：存档记忆书 → 缓存（cache/memory_runtime.json）")
        d = get_json(base + "/api/session/load?slot=m1")
        check("读档成功", d.get("ok"), repr(d)[:200])
        check("前端拿不到 memory 字段", "memory" not in d, list(d.keys()))
        rt_path = os.path.join(cache_dir, "memory_runtime.json")
        check("缓存文件已生成", os.path.exists(rt_path), rt_path)
        rt = json.load(open(rt_path, encoding="utf-8"))
        check("条目复制进缓存", [e["text"] for e in rt["entries"]] == [entry_a["text"], entry_p["text"]],
              rt.get("entries"))
        check("covered / slot 一起复制", rt["covered"] == covered and rt["slot"] == "m1", rt)

        print("\n[2] 聊天：只发最近段 + 缓存里的记忆条目")
        d = post_json(base + "/api/chat", {
            "messages": msgs,
            "base_url": "http://127.0.0.1:%d/v1" % fake_port,
            "model": "deepseek-flash",
        })
        check("对话正常返回", (d or {}).get("reply"), repr(d)[:200])
        last = CHAT_CALLS[-1] if CHAT_CALLS else {}
        sent = last.get("messages") or []
        sys_msg = sent[0].get("content", "") if sent else ""
        check("system 里注入了缓存记忆", entry_a["text"] in sys_msg, sys_msg[-400:])
        check("进度条目也在", "当前进展" in sys_msg, sys_msg[-300:])
        check("只发最近一段（条数变少）", len(sent) - 1 < n, "%d vs %d" % (len(sent) - 1, n))
        # 注意：system 后面还跟着 fewshot（21 组），这里只数我们造的那段历史
        hist_sent = [m for m in sent[1:] if "这是用来撑上下文" in (m.get("content") or "")]
        check("没有把完整历史发出去", len(hist_sent) <= (n - covered) + 2,
              "%d vs %d" % (len(hist_sent), n - covered))

        print("\n[2b] 特别模式的「固定记忆」和自动记忆书是两套，能同时出现")
        mem_txt = "角色固定记忆：她是职业钢琴家，母亲也是钢琴家。"
        req = urllib.request.Request(
            base + "/api/special/upload?kind=memory&name=" +
            urllib.parse.quote("固定记忆.txt"),
            data=mem_txt.encode("utf-8"), method="POST",
            headers={"Content-Type": "application/octet-stream"})
        with urllib.request.urlopen(req, timeout=20) as rr:
            up = json.loads(rr.read().decode("utf-8"))
        check("固定记忆上传成功", up.get("ok"), up)
        post_json(base + "/api/chat", {
            "messages": msgs,
            "base_url": "http://127.0.0.1:%d/v1" % fake_port,
            "model": "deepseek-flash",
        })
        sent = (CHAT_CALLS[-1].get("messages") or [])
        sys_msg = sent[0].get("content", "") if sent else ""
        check("自动记忆书的条目在", entry_a["text"] in sys_msg, sys_msg[-500:])
        check("固定记忆书也在", mem_txt in sys_msg, sys_msg[-500:])
        check("两套的标题不同", "你记得的事" in sys_msg and "你记得的旧事" in sys_msg,
              sys_msg[-700:])

        print("\n[3] 存档：直接把缓存快照进去，不再跑总结")
        sum_before = len(SUM_CALLS)
        r = post_json(base + "/api/session/save", {"slot": "m2", "messages": msgs, "meta": {}})
        check("存档成功", r.get("ok"), repr(r))
        check("存档期间没有发生总结调用", len(SUM_CALLS) == sum_before,
              "%d → %d" % (sum_before, len(SUM_CALLS)))
        saved = json.load(open(os.path.join(sess_dir, "m2.json"), encoding="utf-8"))
        check("save.memory 存在", isinstance(saved.get("memory"), dict), saved.get("memory"))
        check("条目和缓存一致",
              [e["text"] for e in saved["memory"]["entries"]] == [entry_a["text"], entry_p["text"]],
              saved.get("memory"))
        check("covered 和缓存一致", saved["memory"]["covered_upto"] == covered,
              saved["memory"].get("covered_upto"))
        check("完整 messages 一条不少", len(saved["messages"]) == n, len(saved["messages"]))

        print("\n[4] 连发 6 轮：第 6 轮触发后台重打包")
        for i in range(6):
            post_json(base + "/api/chat", {
                "messages": msgs,
                "base_url": "http://127.0.0.1:%d/v1" % fake_port,
                "model": "deepseek-flash",
            })
        for _ in range(50):                       # 后台线程，等它跑完
            if len(SUM_CALLS) > sum_before:
                break
            time.sleep(0.2)
        check("第 6 轮触发了总结", len(SUM_CALLS) > sum_before,
              "sum_calls=%d (before %d)" % (len(SUM_CALLS), sum_before))
        rt2 = json.load(open(rt_path, encoding="utf-8"))
        check("重打包把 covered 推到最近段起点", rt2["covered"] == aligned,
              "%s vs %s" % (rt2["covered"], aligned))
        check("新条目并进缓存", any("总结出的新条目" in e["text"] for e in rt2["entries"]),
              rt2.get("entries"))

        print("\n[5] 读一个没有记忆书的档：缓存清空")
        get_json(base + "/api/session/load?slot=short")
        rt3 = json.load(open(rt_path, encoding="utf-8"))
        check("缓存被清空", rt3["entries"] == [] and rt3["covered"] == 0, rt3)
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
