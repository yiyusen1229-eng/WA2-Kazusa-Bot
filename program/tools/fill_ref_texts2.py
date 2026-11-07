# -*- coding: utf-8 -*-
"""补参考音频文本：来源扩展为「训练清单(.list) + 标注结果.json」。

清单格式：path|speaker|lang|text（GPT-SoVITS 训练清单），覆盖比标注结果全得多。
规则仍与现有 .txt 一致：用清单里的原文，去掉首尾「」，内部换行直接拼接，不覆盖已有文件。
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
VOICE = os.path.join(PROGRAM, "build_env", "characters", "和纱", "voice")
SET = os.path.join(os.path.dirname(PROGRAM), "other", "dev", "语音训练集")


def clean(text):
    s = (text or "").replace("\r", "").strip()
    if s.startswith("「"):
        s = s[1:]
    if s.endswith("」"):
        s = s[:-1]
    return s.replace("\n", "").strip()


def load_sources():
    out = {}
    # 训练清单（3 份，后者不覆盖前者的已有值）
    for fn in ("gpt_sovits.list", "gpt_sovits_全量.list", "GPT-SoVITS清单.list"):
        p = os.path.join(SET, fn)
        if not os.path.isfile(p):
            continue
        for line in io.open(p, encoding="utf-8", errors="replace").read().splitlines():
            parts = line.split("|")
            if len(parts) < 4:
                continue
            base = os.path.splitext(os.path.basename(parts[0]))[0].lower()
            t = clean("|".join(parts[3:]))
            if base and t:
                out.setdefault(base, t)
    # 标注结果（有 text 用 text，否则 asr）
    p = os.path.join(SET, "标注结果.json")
    if os.path.isfile(p):
        for e in json.loads(io.open(p, encoding="utf-8").read()):
            base = os.path.splitext((e.get("wav") or "").lower())[0]
            t = clean(e.get("text") or "") or (e.get("asr") or "").strip()
            if base and t:
                out.setdefault(base, t)
    return out


def main():
    src = load_sources()
    print("可用文本来源: %d 条" % len(src))
    made = have = none = 0
    for d in sorted(os.listdir(VOICE)):
        pdir = os.path.join(VOICE, d)
        if not os.path.isdir(pdir):
            continue
        for f in sorted(os.listdir(pdir)):
            if not f.lower().endswith(".wav"):
                continue
            base = os.path.splitext(f)[0]
            tp = os.path.join(pdir, base + ".txt")
            if os.path.exists(tp):
                have += 1
                continue
            t = src.get(base.lower())
            if not t:
                none += 1
                continue
            io.open(tp, "w", encoding="utf-8", newline="\n").write(t + "\n")
            made += 1
    print("补了 %d 条，已有 %d 条，没有来源的 %d 条" % (made, have, none))
    return 0


if __name__ == "__main__":
    sys.exit(main())
