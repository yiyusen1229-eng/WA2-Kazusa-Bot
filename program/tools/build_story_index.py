# -*- coding: utf-8 -*-
"""把 98 个剧本文件(日中对照)抽取成中文场景块, 建立检索索引"""
import glob
import json
import os
import re

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
SRC = os.path.join(BASE, "game_pak", "gh", "scripts")
OUT = os.path.join(BASE, "app", "story_index.json")

CHUNK_CHARS = 700


def parse_file(path):
    """返回 [(speaker, line), ...] 只保留中文译文"""
    out = []
    try:
        raw = open(path, encoding="utf-8", errors="ignore").read()
    except Exception:
        return out
    # 逐行: 原文：xxx / 译文：xxx
    pending_speaker = None
    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("译文："):
            txt = line[3:].strip()
            txt = txt.replace("\\n", " ")
            if not txt:
                continue
            if txt.startswith("「") or txt.startswith("『"):
                out.append((pending_speaker or "", txt))
            else:
                # 说话人名(如「朋」) 或 场景词
                if len(txt) <= 8 and not re.search(r"[。！？…]", txt):
                    pending_speaker = txt
                else:
                    out.append(("", txt))
    return out


def main():
    files = sorted(glob.glob(os.path.join(SRC, "*.txt")))
    print("剧本文件:", len(files))

    chunks = []
    for path in files:
        name = os.path.splitext(os.path.basename(path))[0]
        lines = parse_file(path)
        if not lines:
            continue
        buf = []
        size = 0
        for spk, txt in lines:
            piece = ("%s：%s" % (spk, txt)) if spk else txt
            buf.append(piece)
            size += len(piece)
            if size >= CHUNK_CHARS:
                chunks.append({"src": name, "text": "\n".join(buf)})
                # 重叠 150 字, 避免切断上下文
                tail = "\n".join(buf)[-150:]
                buf = [tail]
                size = len(tail)
        if size > 100:
            chunks.append({"src": name, "text": "\n".join(buf)})

    print("场景块:", len(chunks))
    total = sum(len(c["text"]) for c in chunks)
    print("中文总量: %.1f 万字" % (total / 10000))

    json.dump(chunks, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print("索引已写入:", OUT, "%.1f MB" % (os.path.getsize(OUT) / 1048576))

    print("\n样例块:")
    for c in chunks[:2]:
        print("---", c["src"])
        print(c["text"][:200])


if __name__ == "__main__":
    main()
