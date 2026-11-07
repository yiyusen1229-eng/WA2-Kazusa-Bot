# -*- coding: utf-8 -*-
"""给「只有呼吸/拟声、没有台词」的参考音频补呼吸型文本。

为什么这么做：H 场景的台词本身大量是拟声（「あ…うっ…はぁ…」），
参考音频也是拟声时，两者是**匹配**的；问题只在于 prompt_text 不能为空——
GPT-SoVITS 要靠它切语义 token，空文本等于丢掉了韵律条件。

做法：不用人工编词，按**音频里的实际气口**生成：
  1. 算 50ms 帧的 RMS 包络；
  2. 以高分位数为基准取阈值，找出连续的发声段（气口）；
  3. 每个气口写一个拟声词（短气口用「はぁ」，长的用「あ」），用「…」连接。

这样文本的音节数与气口数一一对应，既不编造台词，也能让韵律条件对上。
"""
import io
import os
import struct
import sys
import wave

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_HERE = os.path.dirname(os.path.abspath(__file__))
H = os.path.join(os.path.dirname(_HERE), "build_env", "characters", "和纱", "voice", "H")
FRAME = 0.05          # 50ms 一帧
MIN_SEG = 0.18        # 气口最短 0.18s
MERGE_GAP = 0.25      # 间隔小于 0.25s 的合并成一个气口


def rms_envelope(path):
    with wave.open(path, "rb") as w:
        sr = w.getframerate()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if sw != 2:
        raise ValueError("只处理 16bit wav: %s" % path)
    n = len(raw) // 2
    vals = struct.unpack("<%dh" % n, raw[:n * 2])
    if ch > 1:
        vals = vals[::ch]
    step = max(1, int(sr * FRAME))
    env = []
    for i in range(0, len(vals) - step, step):
        chunk = vals[i:i + step]
        s = 0
        for v in chunk:
            s += v * v
        env.append((s / len(chunk)) ** 0.5)
    return env, len(env) * FRAME


def segments(path):
    env, dur = rms_envelope(path)
    if not env:
        return [], 0.0
    srt = sorted(env)
    p95 = srt[int(len(srt) * 0.95)] or 1
    thr = max(p95 * 0.18, 120.0)          # 阈值：相对峰值，且不低到抓噪声
    segs, cur = [], None
    for i, e in enumerate(env):
        if e >= thr:
            if cur is None:
                cur = [i, i]
            else:
                cur[1] = i
        else:
            if cur is not None:
                segs.append(cur)
                cur = None
    if cur is not None:
        segs.append(cur)
    # 合并过近的气口
    merged = []
    for s in segs:
        if merged and (s[0] - merged[-1][1]) * FRAME < MERGE_GAP:
            merged[-1][1] = s[1]
        else:
            merged.append(list(s))
    # 过滤太短的
    out = [(a * FRAME, (b - a + 1) * FRAME) for a, b in merged
           if (b - a + 1) * FRAME >= MIN_SEG]
    return out, dur


def text_from_segments(segs):
    parts = []
    for _, length in segs:
        parts.append("はぁ" if length <= 0.9 else "あ")
    if not parts:
        return ""
    return "…".join(parts)


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]
    todo = args or [os.path.splitext(f)[0] for f in sorted(os.listdir(H))
                            if f.lower().endswith(".wav")
                            and not os.path.exists(os.path.join(H, os.path.splitext(f)[0] + ".txt"))]
    print("待处理 %d 条" % len(todo))
    for base in todo:
        wav = os.path.join(H, base + ".wav")
        if not os.path.isfile(wav):
            print("  缺文件:", base)
            continue
        segs, dur = segments(wav)
        txt = text_from_segments(segs)
        if not txt:
            # 一个气口都没抓到：退回一个最朴素的，总比空文本好
            txt = "はぁ…"
        if not dry:
            io.open(os.path.join(H, base + ".txt"), "w", encoding="utf-8",
                    newline="\n").write(txt + "\n")
        print("  %-8s %5.1fs  气口 %2d 个  %s" % (base, dur, len(segs), txt[:56]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
