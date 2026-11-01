# -*- coding: utf-8 -*-
"""用完整剧本(L2_scene, 366 万汉字)重建检索索引"""
import json
import os
import sys

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
SRC = os.path.join(BASE, "dataset", "L2_scene.jsonl")
OUT = os.path.join(BASE, "app", "story_index.json")

CHUNK = 1200   # 每块字符数


def main():
    scenes = []
    with open(SRC, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            ctx = (d.get("context") or "").strip()
            resp = (d.get("response") or "").strip()
            ch = (d.get("chapter") or "").strip()
            if not ctx:
                continue
            scenes.append((ch, ctx, resp))

    print("场景:", len(scenes))

    chunks = []
    for chapter, ctx, resp in scenes:
        full = ctx + ("\n" + resp if resp else "")
        # 长场景切成多块
        start = 0
        while start < len(full):
            piece = full[start:start + CHUNK]
            if len(piece) >= 200:
                chunks.append({
                    "src": chapter or "本篇",
                    "text": piece,
                })
            start += CHUNK - 100   # 轻微重叠

    # 去重(相同文本)
    seen, uniq = set(), []
    for c in chunks:
        key = c["text"][:200]
        if key in seen:
            continue
        seen.add(key)
        uniq.append(c)

    total = sum(len(c["text"]) for c in uniq)
    print("索引块:", len(uniq), " 汉字总量: %.1f 万" % (total / 10000))

    json.dump(uniq, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print("已写入 %s  %.1f MB" % (OUT, os.path.getsize(OUT) / 1048576))


if __name__ == "__main__":
    main()
