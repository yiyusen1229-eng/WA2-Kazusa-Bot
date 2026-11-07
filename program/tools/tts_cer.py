# -*- coding: utf-8 -*-
"""TTS 可懂度自测：合成 → 用 ASR 转写回来 → 和原文比错字率（CER）。

这是唯一能客观衡量「念没念出实词」的办法（我听不了音频）：
CER 低 = 字念出来了；CER 高 = 念成一团气声。

    other\\dev\\train\\venv\\Scripts\\python.exe program\\tools\\tts_cer.py
"""
import io
import os
import sys
import tempfile
import wave

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROGRAM, "src"))
os.environ.setdefault("WA2_USER_DIR", os.path.join(PROGRAM, "build_env"))

import tts_client as TC  # noqa: E402

TEXT = "あぁ…ちょっと、指、なら、いいけど…っ、そこは、だめ…"


def cer(ref, hyp):
    """按字符算编辑距离 / 参考长度（日文不分词，字符级最稳）"""
    r, h = list(ref), list(hyp)
    if not r:
        return 0.0
    dp = list(range(len(h) + 1))
    for i, rc in enumerate(r, 1):
        prev, dp[0] = dp[0], i
        for j, hc in enumerate(h, 1):
            cur = dp[j]
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + (rc != hc))
            prev = cur
    return dp[len(h)] / len(r)


def main():
    from faster_whisper import WhisperModel
    m = WhisperModel("large-v3", device="cpu", compute_type="int8")
    TC._ready = True
    print("原文:", TEXT)
    print("%-6s %-6s %6s %6s  %s" % ("情绪", "时长", "CER", "识别", "ASR 转写"))
    for emo in ("calm", "H"):
        TC._TTS_CACHE_DIR = tempfile.mkdtemp(prefix="wa2_cer_")
        data = TC.synthesize(TEXT, "ja", emo=emo)
        if not data:
            print("%-6s 合成失败" % emo)
            continue
        with wave.open(io.BytesIO(data), "rb") as w:
            dur = w.getnframes() / float(w.getframerate())
        tmp = os.path.join(tempfile.mkdtemp(), "o.wav")
        io.open(tmp, "wb").write(data)
        segs, _ = m.transcribe(tmp, language="ja", beam_size=1, vad_filter=False,
                               condition_on_previous_text=False)
        hyp = "".join(s.text for s in segs).strip()
        print("%-6s %-6.1f %6.2f %6s  %s" % (emo, dur, cer(TEXT, hyp),
                                             "差" if cer(TEXT, hyp) > 0.5 else "好", hyp[:40]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
