# -*- coding: utf-8 -*-
"""给每条参考音频打分：合成两句测试句 → ASR 回读 → 算平均 CER。

为什么这么做：随机抽参考会让质量时好时坏（用户说「偶尔有些实词说不出来」）。
实测发现不同参考的 CER 差别很大，所以干脆逐条打分，把念不清的排到最后。

    other\\dev\\train\\venv\\Scripts\\python.exe program\\tools\\ref_cer_rank.py H
"""
import io
import json
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

SENTENCES = [
    "あぁ…ちょっと、指、なら、いいけど…っ、そこは、だめ…",
    "んっ…そこ、やだ…っ、でも、もっと、して…",
]


def cer(ref, hyp):
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
    folder = sys.argv[1] if len(sys.argv) > 1 else "H"
    voice = os.path.join(PROGRAM, "build_env", "characters", "和纱", "voice", folder)
    side = os.path.join(voice, "_refaudio.json")
    info = {}
    if os.path.isfile(side):
        for r in json.loads(io.open(side, encoding="utf-8").read()):
            info[r["wav"]] = r
    m = WhisperModel("large-v3", device="cpu", compute_type="int8")
    TC._ready = True

    cands = []
    for f, r in sorted(info.items()):
        if r.get("ratio", 0) < 0.5 or not (3.5 <= r.get("dur", 0) <= 7.5):
            continue
        tp = os.path.join(voice, os.path.splitext(f)[0] + ".txt")
        txt = io.open(tp, encoding="utf-8").read().strip() if os.path.isfile(tp) else ""
        if not txt or TC._looks_like_moan(txt):
            continue
        cands.append((f, txt))
    print("候选参考 %d 条" % len(cands))

    scores = {}
    for f, txt in cands:
        wav = os.path.join(voice, f)
        cers = []
        for s in SENTENCES:
            TC._TTS_CACHE_DIR = tempfile.mkdtemp(prefix="wa2_rank_")
            TC._ref_cache = {folder.lower(): [(wav, txt)], folder: [(wav, txt)]}
            TC._refs_sig = TC._char_voice_sig()
            data = TC.synthesize(s, "ja", emo=folder)
            if not data:
                cers.append(1.0)
                continue
            p = os.path.join(tempfile.mkdtemp(), "o.wav")
            io.open(p, "wb").write(data)
            segs, _ = m.transcribe(p, language="ja", beam_size=1, vad_filter=False,
                                   condition_on_previous_text=False)
            hyp = "".join(x.text for x in segs).strip()
            cers.append(cer(s, hyp))
        avg = sum(cers) / len(cers)
        scores[f] = round(avg, 3)
        print("  %-12s CER %.2f  (%.2f/%.2f)  %s"
              % (f, avg, cers[0], cers[1], txt[:20]), flush=True)
        io.open(os.path.join(voice, "_refcer.json"), "w", encoding="utf-8", newline="\n").write(
            json.dumps(scores, ensure_ascii=False, indent=1))
    print("\n已写", os.path.join(voice, "_refcer.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
