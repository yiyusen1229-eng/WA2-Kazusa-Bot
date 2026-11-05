# -*- coding: utf-8 -*-
"""用完整剧本重建剧情检索索引（story_rag 用）

源：`other/dev/dataset/L2_scene.jsonl`
    每行一个场景：{scene_id, chapter, context, response}
出：`program/src/story_index.json.gz`
    story_rag.get_index() 优先读 .gz（体积约为 json 的 1/14，启动更快）

用法：
    python tools/build_story_index_v2.py                 # 默认源
    python tools/build_story_index_v2.py --src <文件>    # 换源
    python tools/build_story_index_v2.py --chunk 1200    # 每块字符数

索引结构：[{src: 章节, text: 剧本片段}]，story_rag 按 BM25 检索。
"""
import argparse
import gzip
import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DEFAULT = os.path.join(os.path.dirname(ROOT), "other", "dev", "dataset", "L2_scene.jsonl")
OUT_DEFAULT = os.path.join(ROOT, "src", "story_index.json.gz")
OVERLAP = 100          # 相邻块重叠的字数，避免一句话被切断后检索不到


def _heading(chapter, ctx):
    """给每块加一行「标题行」，让 BM25 能按场景名/日期召回

    剧本里有的场景第一行就是标题（「轻音乐同好会再结成（上）」），有的直接是台词；
    台词行带引号或冒号，排除掉。都没有就退回章节日期。
    """
    first = (ctx or "").strip().split("\n", 1)[0].strip()
    if 0 < len(first) <= 30 and "「" not in first and "『" not in first and "：" not in first:
        return first
    return (chapter or "").strip() or "本篇"


def build(src, out, chunk):
    scenes = []
    with open(src, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            ctx = (d.get("context") or "").strip()
            resp = (d.get("response") or "").strip()
            if not ctx:
                continue
            scenes.append(((d.get("chapter") or "").strip(), ctx, resp))
    print("场景: %d" % len(scenes))

    chunks, seen = [], set()
    for chapter, ctx, resp in scenes:
        full = ctx + ("\n" + resp if resp else "")
        head = _heading(chapter, ctx)
        start = 0
        while start < len(full):
            piece = full[start:start + chunk]
            if len(piece) >= 200:
                key = piece[:200]
                if key not in seen:            # 相同开头的块去重
                    seen.add(key)
                    chunks.append({"src": chapter or "本篇",
                                   "text": "〔%s〕\n%s" % (head, piece)})
            start += chunk - OVERLAP

    total = sum(len(c["text"]) for c in chunks)
    print("索引块: %d  汉字总量: %.1f 万" % (len(chunks), total / 10000))

    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + ".tmp"
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False)
    os.replace(tmp, out)
    print("已写入 %s  %.1f MB" % (out, os.path.getsize(out) / 1048576))

    # 旧的未压缩索引（12MB）没必要留着：运行时优先读 .gz
    plain = out[:-3] if out.endswith(".gz") else ""
    if plain and os.path.exists(plain):
        os.remove(plain)
        print("已删除旧的无压缩索引 %s" % plain)


def main():
    ap = argparse.ArgumentParser(description="重建剧情检索索引")
    ap.add_argument("--src", default=SRC_DEFAULT)
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--chunk", type=int, default=1200, help="每块字符数")
    a = ap.parse_args()
    if not os.path.exists(a.src):
        print("找不到剧本：%s" % a.src)
        return 2
    t0 = time.time()
    build(a.src, a.out, max(200, a.chunk))
    print("耗时 %.1f 秒" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
