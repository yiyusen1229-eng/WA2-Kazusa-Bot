# -*- coding: utf-8 -*-
"""合成参数自测：短句整句合成、长句才切分、H 的采样参数收紧。

不真的调模型：把 tts_client._post 换成假的，抓它发出去的查询串。
    cd program && .\\build_env\\venv\\Scripts\\python.exe tools\\test_tts_params.py
"""
import os
import sys
import urllib.parse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))
# 角色目录指到部署目录，否则 refs 为空、synthesize 会提前返回
os.environ.setdefault("WA2_USER_DIR", os.path.join(os.path.dirname(HERE), "build_env"))

import tts_client as TC  # noqa: E402

# 缓存目录指到临时目录，否则同文本会直接命中缓存、根本发不出请求
import tempfile
TC._TTS_CACHE_DIR = tempfile.mkdtemp(prefix="wa2_ttsp_")

FAILS = []
CAPTURED = {}


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:220]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def fake_post(path, timeout=30):
    CAPTURED["q"] = dict(urllib.parse.parse_qs(path.split("?", 1)[1]))
    return b"RIFF" + b"0" * 100


def main():
    TC._ready = True
    TC._post = fake_post
    TC._ensure_char_model = lambda: True
    TC._ref_cache = {"h": [("/tmp/x.wav", "いいからそのまま")],
                     "calm": [("/tmp/y.wav", "最初から言ってる。別に、嫌じゃないって")]}

    print("[1] 短句整句合成（40 字以内不切分）")
    TC.synthesize("その、ゆび、つよく、しすぎ…っ、いたい、のに…っ", "ja", emo="H")
    q = CAPTURED.get("q") or {}
    check("短句用 cut0", (q.get("text_split_method") or [""])[0] == "cut0", q.get("text_split_method"))
    check("短句确实发了请求", bool(q))

    print("[2] 长句才切分")
    long_text = "まって、まだ、はなす、の、いや…っ、" * 3
    CAPTURED.clear()
    TC.synthesize(long_text, "ja", emo="H")
    q = CAPTURED.get("q") or {}
    check("长句用 cut5", (q.get("text_split_method") or [""])[0] == "cut5",
          (len(long_text), q.get("text_split_method")))

    print("[3] H 的采样参数收紧（减少吞字）")
    prm = TC.EMOTION_PARAMS["H"]
    check("temperature ≤ 0.75", prm["temperature"] <= 0.75, prm)
    check("top_k ≤ 6", prm["top_k"] <= 6, prm)
    check("top_p ≤ 0.93", prm["top_p"] <= 0.93, prm)

    print("[4] 请求里带上了参考音频与文本")
    CAPTURED.clear()
    TC.synthesize("はぁ…っ、あ、ん…っ", "ja", emo="H")
    q = CAPTURED.get("q") or {}
    check("有 ref_audio_path", bool(q.get("ref_audio_path")), q)
    check("有 prompt_text", bool(q.get("prompt_text")), q)
    check("prompt_lang 是 ja", (q.get("prompt_lang") or [""])[0] == "ja", q.get("prompt_lang"))

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), "、".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
