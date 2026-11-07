# -*- coding: utf-8 -*-
"""H 目录素材普查：数量、时长、实词分、连续短句分组。

    cd program && .\\build_env\\venv\\Scripts\\python.exe tools\\refs_survey.py H
"""
import io
import os
import sys
import wave

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROGRAM, "src"))
os.environ.setdefault("WA2_USER_DIR", os.path.join(PROGRAM, "build_env"))

import tts_client as TC  # noqa: E402

VOICE = os.path.join(PROGRAM, "build_env", "characters", "和纱", "voice")


def dur(path):
    try:
        with wave.open(path, "rb") as w:
            return w.getnframes() / float(w.getframerate())
    except Exception:
        return -1


def num_of(base):
    """ka0317 -> 317；取不到返回 None"""
    tail = "".join(ch for ch in base if ch.isdigit())
    return int(tail) if tail else None


def survey(folder):
    d = os.path.join(VOICE, folder)
    rows = []
    for f in sorted(os.listdir(d)):
        if not f.lower().endswith(".wav"):
            continue
        base = os.path.splitext(f)[0]
        tp = os.path.join(d, base + ".txt")
        txt = ""
        if os.path.exists(tp):
            try:
                txt = io.open(tp, encoding="utf-8").read().strip()
            except Exception:
                txt = ""
        rows.append({"base": base, "wav": os.path.join(d, f), "txt": txt,
                     "dur": dur(os.path.join(d, f)),
                     "w": TC._ref_wordiness(txt) if txt else 0.0,
                     "n": num_of(base)})
    return rows


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else "H"
    rows = survey(folder)
    has = [r for r in rows if r["txt"]]
    print("=== %s 目录 ===" % folder)
    print("  wav %d 条 | 有文本 %d | 实词分≥0.5 %d | 时长<3s %d | 3~10s %d | >10s %d"
          % (len(rows), len(has), sum(1 for r in has if r["w"] >= 0.5),
             sum(1 for r in rows if 0 <= r["dur"] < 3),
             sum(1 for r in rows if 3 <= r["dur"] <= 10),
             sum(1 for r in rows if r["dur"] > 10)))

    # 短句：时长 <3s 或 实词分 <0.5
    shorts = sorted([r for r in rows if r["dur"] < 3 or r["w"] < 0.5 or not r["txt"]],
                    key=lambda r: (r["n"] is None, r["n"] or 0))
    print("\n=== 短/弱片段 %d 条，按编号 === " % len(shorts))
    for r in shorts[:60]:
        print("  %-10s n=%-5s %4.1fs 实词%.2f  %s"
              % (r["base"], r["n"], r["dur"], r["w"], r["txt"][:24]))

    # 连续编号分组
    nums = [r["n"] for r in shorts if r["n"] is not None]
    groups, cur = [], []
    for r in sorted([x for x in shorts if x["n"] is not None], key=lambda x: x["n"]):
        if cur and r["n"] == cur[-1]["n"] + 1:
            cur.append(r)
        else:
            if len(cur) >= 2:
                groups.append(cur)
            cur = [r]
    if len(cur) >= 2:
        groups.append(cur)

    print("\n=== 可拼接的「连续编号」短句组 %d 组 ===" % len(groups))
    for g in groups:
        total = sum(x["dur"] for x in g)
        text = "、".join((x["txt"] or "") for x in g)
        print("  %s ~ %s（%d 条，共 %.1fs，合并后实词分 %.2f）"
              % (g[0]["base"], g[-1]["base"], len(g), total, TC._ref_wordiness(text)))
        print("      %s" % text[:70])
    return 0


if __name__ == "__main__":
    sys.exit(main())
