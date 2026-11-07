# -*- coding: utf-8 -*-
"""标签贯通自测：提示词词表里的每个情绪，语音/立绘/BGM 三处都要认，不能有静默回落。

    cd program && .\\build_env\\venv\\Scripts\\python.exe tools\\test_emotion_wiring.py
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
SRC = os.path.join(PROGRAM, "src")
sys.path.insert(0, SRC)
os.environ.setdefault("WA2_USER_DIR", os.path.join(PROGRAM, "build_env"))

import tts_client as TC  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:260]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def read(p):
    return io.open(os.path.join(SRC, p), encoding="utf-8").read()


def vocab_from_prompt():
    """从 api_chat 的提示词里抠出「只能从这些里选：…」那段的中文标签"""
    t = read("api_chat.py")
    i = t.find("只能从这些里选")
    assert i > 0, "提示词里找不到词表"
    seg = t[i:i + 420]
    # 拼起来的字符串可能跨行，先把 """ 和换行去掉
    words = re.findall(r"[\u4e00-\u9fffA-Za-z]+", seg)
    # 只要逗号分隔那一段里的
    head = seg.split("怎么挑：")[0]
    cand = [w for w in re.findall(r"[^\s，。、]+", head.replace("只能从这些里选：", ""))]
    out = []
    for c in cand:
        c = c.strip("。\"'")
        if not c or c.startswith("("):
            continue
        if re.match(r"^[A-Za-z]+$", c) or re.search(r"[\u4e00-\u9fff]", c) or c == "H":
            out.append(c)
    # calm(平静) 这种写法：真正能输出的标签是括号前的部分
    def _base(x):
        return x.split("(")[0].strip() if "(" in x else x
    return [_base(x) for x in out if _base(x)]


def main():
    print("[1] 提示词词表")
    vocab = vocab_from_prompt()
    print("    解析到:", vocab)
    for tag in ("紧张", "激动", "委屈巴巴", "自怨自艾", "故作轻松", "气喘吁吁", "H", "沉重"):
        check("提示词包含 %s" % tag, tag in vocab, vocab)

    print("[2] 语音：每个标签都能映射到参考音频分组")
    for tag in vocab:
        groups = TC.REF_GROUPS.get(tag) or TC.REF_GROUPS.get(TC.EMOTION_ALIAS.get(tag, tag))
        check("%s 有 REF_GROUPS 映射" % tag, bool(groups), groups)
        check("%s 有 EMOTION_PARAMS 调参" % tag,
              tag in TC.EMOTION_PARAMS or TC.EMOTION_ALIAS.get(tag, tag) in TC.EMOTION_PARAMS,
              tag)

    print("[3] 每个参考音频文件夹都能被某个标签选到")
    TC._REFS_OVERRIDE = ""
    refs = TC.load_refs()
    reachable = set()
    for v in TC.REF_GROUPS.values():
        reachable.update(v)
    folders = [d for d in os.listdir(TC.refs_dir())
               if os.path.isdir(os.path.join(TC.refs_dir(), d))
               and any(f.lower().endswith(".wav")
                       for f in os.listdir(os.path.join(TC.refs_dir(), d)))]
    missing = [d for d in folders if d not in reachable and d.lower() not in
               {x.lower() for x in reachable}]
    check("没有孤立的音频文件夹", not missing, missing)
    print("    文件夹 %d 个，可达 %d 个" % (len(folders), len(set(folders) - set(missing))))

    print("[4] 立绘与 BGM 也认这些标签")
    sprite = read(os.path.join("ui", "wt-sprite.js"))
    mood = read(os.path.join("ui", "wt-mood.js"))
    for tag in vocab:
        check("立绘认 %s" % tag, ('"%s"' % tag) in sprite or ("%s:" % tag) in sprite, tag)
        check("BGM 认 %s" % tag, ('"%s"' % tag) in mood or ("%s:" % tag) in mood, tag)

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), "、".join(FAILS)))
        return 1
    print("全部通过（词表 %d 个标签全部贯通）" % len(vocab))
    return 0


if __name__ == "__main__":
    sys.exit(main())
