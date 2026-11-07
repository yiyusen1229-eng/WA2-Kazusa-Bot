# -*- coding: utf-8 -*-
"""把「太短、单独用不了」的参考音频按连续编号拼成一条。

为什么要拼：GPT-SoVITS 的参考音频最好 3~10 秒、内容是一句完整的话。
太短的片段（<3 秒，或文本不到 6 个字）单独当参考效果差；但如果编号是连续的
（ka0301、ka0302、ka0303），它们往往是同一段连着的台词，拼起来就够用了。

做法：
  · 识别候选：时长 < 最小值（默认 3.0s）或 文本字数 < 最小值（默认 6）；
  · 只把**编号连续**的相邻候选并成一组（中间缺号就断开）；
  · 音频拼接：中间补一小段静音（默认 0.25s），采样率/声道/位深必须一致；
  · 文本拼接：用「、」连接；
  · 输出 <首号>_<末号>.wav + 同名 .txt，**保留原文件**（不删）。
  · 合并后超过最大时长（默认 12s）的组跳过 —— 太长做参考反而不好。

    cd program && .\\build_env\\venv\\Scripts\\python.exe tools\\merge_short_refs.py H --dry-run
    cd program && .\\build_env\\venv\\Scripts\\python.exe tools\\merge_short_refs.py H --apply
"""
import io
import os
import struct
import sys
import wave

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
VOICE = os.path.join(PROGRAM, "build_env", "characters", "和纱", "voice")

MIN_DUR = 3.0        # 短于这个算"太短"
MIN_CHARS = 6        # 文本短于这个字也算"太短"
GAP_S = 0.25         # 拼接时的静音间隔
MAX_MERGED = 12.0    # 合并后超过这个时长就跳过


def num_of(base):
    tail = "".join(ch for ch in base if ch.isdigit())
    return int(tail) if tail else None


def read_wav(path):
    with wave.open(path, "rb") as w:
        return {"sr": w.getframerate(), "ch": w.getnchannels(),
                "sw": w.getsampwidth(), "data": w.readframes(w.getnframes())}


def dur_of(path):
    try:
        with wave.open(path, "rb") as w:
            return w.getnframes() / float(w.getframerate())
    except Exception:
        return -1.0


def main():
    args = [a for a in sys.argv[1:]]
    apply = "--apply" in args
    args = [a for a in args if not a.startswith("--")]
    folder = args[0] if args else "H"
    d = os.path.join(VOICE, folder)
    assert os.path.isdir(d), "目录不存在: %s" % d

    items = []
    for f in sorted(os.listdir(d)):
        if not f.lower().endswith(".wav"):
            continue
        base = os.path.splitext(f)[0]
        if "_" in base:          # 已经合并过的不再参与
            continue
        tp = os.path.join(d, base + ".txt")
        txt = ""
        if os.path.exists(tp):
            txt = io.open(tp, encoding="utf-8").read().strip()
        items.append({"base": base, "path": os.path.join(d, f), "txt": txt,
                      "dur": dur_of(os.path.join(d, f)), "n": num_of(base)})

    shorts = [x for x in items if x["n"] is not None
              and (x["dur"] < MIN_DUR or len(x["txt"]) < MIN_CHARS)]
    shorts.sort(key=lambda x: x["n"])

    groups, cur = [], []
    for x in shorts:
        if cur and x["n"] == cur[-1]["n"] + 1:
            cur.append(x)
        else:
            if len(cur) >= 2:
                groups.append(cur)
            cur = [x]
    if len(cur) >= 2:
        groups.append(cur)

    print("=== %s：短片段 %d 个，可拼接的连续组 %d 组 ===" % (folder, len(shorts), len(groups)))
    made = 0
    for g in groups:
        total = sum(x["dur"] for x in g) + GAP_S * (len(g) - 1)
        text = "、".join(x["txt"] for x in g if x["txt"])
        name = "%s_%s" % (g[0]["base"], g[-1]["base"])
        ok = total <= MAX_MERGED and text
        print("  %-24s %d 条 %5.1fs -> %.1fs  %s%s"
              % (name, len(g), sum(x["dur"] for x in g), total,
                 "可合并" if ok else "跳过（太长/无文本）", ""))
        print("      文本: %s" % text[:70])
        if not ok or not apply:
            continue
        # 拼接
        first = read_wav(g[0]["path"])
        sr, ch, sw = first["sr"], first["ch"], first["sw"]
        frames = []
        for i, x in enumerate(g):
            info = read_wav(x["path"])
            if (info["sr"], info["ch"], info["sw"]) != (sr, ch, sw):
                print("      参数不一致，跳过：%s" % x["base"])
                frames = None
                break
            frames.append(info["data"])
        if frames is None:
            continue
        gap = b"\x00" * int(sr * GAP_S) * ch * sw
        out_path = os.path.join(d, name + ".wav")
        with wave.open(out_path, "wb") as w:
            w.setnchannels(ch)
            w.setsampwidth(sw)
            w.setframerate(sr)
            for i, fr in enumerate(frames):
                if i:
                    w.writeframes(gap)
                w.writeframes(fr)
        io.open(os.path.join(d, name + ".txt"), "w", encoding="utf-8",
                newline="\n").write(text + "\n")
        made += 1

    print()
    print(("已合并 %d 组（原文件保留）" % made) if apply else "（--dry-run：没有写文件，加 --apply 才合并）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
