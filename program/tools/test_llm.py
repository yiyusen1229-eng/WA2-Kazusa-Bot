# -*- coding: utf-8 -*-
"""模型接入层自测（#24）：provider / 错误分类 / 重试 / 降级 / 预算。

网络全挡掉：把 llm.post 换成一个按剧本返回的假函数，不连任何服务。

    cd program && .\\build_env\\venv\\Scripts\\python.exe tools\\test_llm.py
"""
import io
import json
import os
import shutil
import sys
import tempfile
import urllib.error

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))

TMP = tempfile.mkdtemp(prefix="wa2_llm_")
os.environ["WA2_CACHE_DIR"] = TMP

import llm  # noqa: E402

FAILS = []
CALLS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:220]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def http_error(code, body=""):
    import email.utils
    import urllib.request

    class _H(urllib.error.HTTPError):
        def __init__(self, code, body):
            urllib.error.HTTPError.__init__(self, "http://x", code, "err",
                                            email.utils.formatdate().encode() and {}, None)
            self._body = body.encode("utf-8")

        def read(self, *a):
            return self._body

    return _H(code, body)


class Script(object):
    """按顺序吐出预置结果；元素是 dict（成功）或 Exception（失败）"""

    def __init__(self, *steps):
        self.steps = list(steps)

    def __call__(self, url, payload, cfg, timeout=90):
        CALLS.append({"url": url, "model": payload.get("model"),
                      "key": cfg.get("api_key"), "think": "thinking" in payload})
        if not self.steps:
            raise AssertionError("剧本用完了")
        s = self.steps.pop(0)
        if isinstance(s, Exception):
            raise s
        return s


def ok(text="「嗯。」", usage=None):
    return {"choices": [{"message": {"content": text}}], "usage": usage or {"total_tokens": 42}}


CFG = {"api_key": "sk-test-key-123", "base_url": "https://api.example.com", "model": "m1"}
LOCAL = {"api_key": "", "base_url": "http://127.0.0.1:11434", "model": "qwen3:1.7b"}


def main():
    real_post = llm.post

    print("[1] provider 识别与地址拼接")
    check("11434 → ollama", llm.provider_of("http://127.0.0.1:11434") == "ollama")
    check("api.xxx → openai", llm.provider_of("https://api.deepseek.com") == "openai")
    check("/v1 → openai", llm.provider_of("http://192.168.1.9:8000/v1") == "openai")
    check("其它 → custom", llm.provider_of("http://my-box:9999") == "custom")
    check("拼 /v1/chat/completions", llm.endpoint("https://a.com") == "https://a.com/v1/chat/completions")
    check("已经带 /v1 不重复", llm.endpoint("https://a.com/v1") == "https://a.com/v1/chat/completions")
    check("完整的原样返回", llm.endpoint("https://a.com/v1/chat/completions")
          == "https://a.com/v1/chat/completions")
    check("有 key 才有 Authorization", "Authorization" in llm.headers(CFG)
          and "Authorization" not in llm.headers(LOCAL))

    print("[2] 成功路径")
    llm.post = Script(ok("「今天也冷。」", {"total_tokens": 77, "prompt_tokens": 50,
                                          "completion_tokens": 27}))
    r = llm.generate({"model": "m1", "messages": []}, CFG, timeout=5, sleep=lambda s: None)
    check("拿到正文", r.text == "「今天也冷。」", r.text)
    check("usage 透传", r.usage.get("total_tokens") == 77, r.usage)
    check("没降级", r.degraded is False and r.reason == "", (r.degraded, r.reason))
    check("provider 记下来了", r.provider == "openai", r.provider)

    print("[3] 错误分类")
    check("401 → auth", llm.classify_status(401).kind == "auth")
    check("403 → auth", llm.classify_status(403).kind == "auth")
    check("402 → balance", llm.classify_status(402).kind == "balance")
    check("body 提 insufficient → balance",
          llm.classify_status(400, '{"error":"Insufficient Balance"}').kind == "balance")
    check("429 → rate 且可重试",
          llm.classify_status(429).kind == "rate" and llm.classify_status(429).retryable)
    check("503 → server 且可重试", llm.classify_status(503).kind == "server"
          and llm.classify_status(503).retryable)
    check("timeout → offline 且可重试",
          llm.classify_exc(TimeoutError("x")).kind == "offline"
          and llm.classify_exc(TimeoutError("x")).retryable)
    check("URLError → offline",
          llm.classify_exc(urllib.error.URLError("no route")).kind == "offline")
    check("HTTPError 会读 body 分类",
          llm.classify_exc(http_error(402, "insufficient balance")).kind == "balance")
    check("用户话术不是英文堆栈",
          "余额" in llm.classify_status(402).user_message,
          llm.classify_status(402).user_message)

    print("[4] 重试一次：可重试的错误会再试")
    CALLS[:] = []
    llm.post = Script(http_error(503), ok("第二次成了"))
    r = llm.generate({"model": "m1"}, CFG, timeout=5, sleep=lambda s: None)
    check("第二次成功", r.text == "第二次成了", r.text)
    check("确实发了两次", len(CALLS) == 2, len(CALLS))
    check("attempts 记 2", r.attempts == 2, r.attempts)

    print("[5] 不可重试的错误不浪费时间")
    CALLS[:] = []
    llm.post = Script(http_error(401))
    try:
        llm.generate({"model": "m1"}, CFG, timeout=5, sleep=lambda s: None)
        check("401 应该抛错", False)
    except llm.LLMError as e:
        check("401 → auth", e.kind == "auth", e.kind)
    check("只发了一次", len(CALLS) == 1, len(CALLS))

    print("[6] 降级到本地模型")
    CALLS[:] = []
    llm.post = Script(http_error(401), ok("本地模型说的话", {"total_tokens": 9}))
    r = llm.generate({"model": "m1", "thinking": {"type": "disabled"}}, CFG, timeout=5,
                     fallback_cfg=LOCAL, sleep=lambda s: None)
    check("拿到本地模型的回复", r.text == "本地模型说的话", r.text)
    check("标记降级了", r.degraded is True, r.degraded)
    check("降级原因记下来", r.reason == "auth", r.reason)
    check("用的是本地模型名", r.model == LOCAL["model"], r.model)
    check("第二次请求打到 ollama", "11434" in CALLS[-1]["url"], CALLS[-1]["url"])
    check("降级时摘掉 thinking/reasoning_effort", CALLS[-1]["think"] is False, CALLS[-1])

    print("[7] 降级也失败：错误要说清两头")
    llm.post = Script(http_error(401), urllib.error.URLError("refused"))
    try:
        llm.generate({"model": "m1"}, CFG, timeout=5, fallback_cfg=LOCAL, sleep=lambda s: None)
        check("应该抛错", False)
    except llm.LLMError as e:
        check("话术里同时有云端和本地",
              "余额" in e.user_message or "密钥" in e.user_message, e.user_message)
        check("提到本地也没成", "本地" in e.user_message, e.user_message)

    print("[8] 坏响应")
    llm.post = Script({"nope": 1}, {"nope": 1})
    try:
        llm.generate({"model": "m1"}, CFG, timeout=5, sleep=lambda s: None)
        check("坏响应应该抛错", False)
    except llm.LLMError as e:
        check("→ bad_response", e.kind == "bad_response", e.kind)
    # 空正文不能当成功：推理型模型把预算花在思考上时 content 会是空的，
    # 调用方会据此写出空摘要、界面上一个字都没有 —— 必须报错让人知道
    llm.post = Script({"choices": [{"message": {"content": None}}], "usage": {}},
                      {"choices": [{"message": {"content": None}}], "usage": {}})
    try:
        llm.generate({"model": "m1"}, CFG, timeout=5, sleep=lambda s: None)
        check("空正文应该抛错", False)
    except llm.LLMError as e:
        check("空正文 → bad_response", e.kind == "bad_response", e.kind)
        check("话术提到 max_tokens/思考", "max_tokens" in e.user_message
              or "思考" in e.user_message, e.user_message)
    llm.post = Script({"choices": [{"message": {"content": "  \n "}}], "usage": {}},
                      {"choices": [{"message": {"content": "  \n "}}], "usage": {}})
    try:
        llm.generate({"model": "m1"}, CFG, timeout=5, sleep=lambda s: None)
        check("纯空白也应该抛错", False)
    except llm.LLMError as e:
        check("纯空白 → bad_response", e.kind == "bad_response", e.kind)

    print("[9a] 本地走原生接口：带上 num_ctx")
    np = llm.native_payload({"model": "m", "max_tokens": 300,
                             "messages": [{"role": "user", "content": "hi"}]})
    check("options.num_ctx 有值且 >= 8192",
          int(np.get("options", {}).get("num_ctx", 0)) >= 8192, np.get("options"))
    check("max_tokens → num_predict", np["options"].get("num_predict") == 300,
          np["options"])
    check("本地不要思考", np.get("think") is False, np.get("think"))
    check("原生请求不带 stream", np.get("stream") is False)
    check("原生用量口径换算",
          llm._native_usage({"prompt_eval_count": 10, "eval_count": 5})
          == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
    print("[9] Ollama 原生形状也认")
    llm.post = Script({"message": {"content": "「原生 ok」"}, "usage": {"total_tokens": 5}})
    r = llm.generate({"model": "q"}, LOCAL, timeout=5, sleep=lambda s: None)
    check("Ollama message.content", r.text == "「原生 ok」", r.text)
    check("provider=ollama", r.provider == "ollama", r.provider)

    print("[10] 预算：累加 / 80% 提醒 / 超额 / 换天归零")
    os.environ["WA2_BUDGET_DAILY"] = "1.0"
    st = llm.budget_status()
    check("初始 0", st["cost"] == 0 and st["limit"] == 1.0, st)
    check("没到 80% 不提醒", llm.budget_warning(st) == "", llm.budget_warning(st))
    st = llm.budget_note(0.5)
    check("累加到 0.5", abs(st["cost"] - 0.5) < 1e-6, st)
    check("50% 还不提醒", llm.budget_warning(st) == "", llm.budget_warning(st))
    st = llm.budget_note(0.35)
    check("85% 提醒", "85%" in llm.budget_warning(st) or "已花" in llm.budget_warning(st),
          llm.budget_warning(st))
    st = llm.budget_note(0.3)
    check("超 100% 说超预算", "超过预算" in llm.budget_warning(st), llm.budget_warning(st))
    check("over 标记", st["over"] is True, st)
    # 换天：把文件里的日期改成昨天
    p = llm._budget_path()
    d = json.load(io.open(p, encoding="utf-8"))
    d["date"] = "2000-01-01"
    json.dump(d, io.open(p, "w", encoding="utf-8"))
    st2 = llm.budget_status()
    check("换天就归零", st2["cost"] == 0, st2)
    os.environ.pop("WA2_BUDGET_DAILY", None)
    st3 = llm.budget_status()
    check("没设预算就不提醒", llm.budget_warning(st3) == "", llm.budget_warning(st3))

    llm.post = real_post
    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), "、".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
