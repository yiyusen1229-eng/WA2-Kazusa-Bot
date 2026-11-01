# -*- coding: utf-8 -*-
"""把世界书草稿压缩成知识条目, 并合并进 worldbook.json
用法: python summarize_entries.py [--cpu]
"""
import json
import os
import re
import sys
import time
import urllib.request

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
DRAFTS = os.path.join(BASE, "work", "worldbook_drafts.json")
WB = os.path.join(BASE, "app", "worldbook.json")
OLLAMA = "http://127.0.0.1:11434/api/chat"

SYS = ("你在整理一部视觉小说的设定资料。把给你的剧本片段，整理成一条客观的设定笔记。"
       "只写片段里确实出现的事实：人物关系、发生过什么、结果如何。"
       "不要写对白，不要写'他说'，用陈述句。不超过 320 字。不知道的不要补。")


def summarize(model, name, raw, cpu=False):
    prompt = "主题：%s\n\n剧本片段：\n%s\n\n请整理成一条设定笔记。" % (name, raw[:2200])
    opts = {"temperature": 0.3, "num_predict": 420, "num_ctx": 4096}
    if cpu:
        opts["num_gpu"] = 0
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": SYS},
                     {"role": "user", "content": prompt}],
        "stream": False,
        "options": opts,
    }, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(OLLAMA, data=body,
                                 headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=900) as r:
        t = json.loads(r.read().decode("utf-8"))["message"]["content"].strip()
    t = re.sub(r"\s*\n\s*", "\n", t).strip()
    return t


def main():
    args = sys.argv[1:]
    cpu = "--cpu" in args
    model = "qwen2.5:7b-instruct" if cpu else "kazusa14b"

    drafts = json.load(open(DRAFTS, encoding="utf-8"))
    wb = json.load(open(WB, encoding="utf-8"))
    existing = {e["name"] for e in wb["entries"]}

    out = []
    for i, d in enumerate(drafts, 1):
        if d["name"] in existing:
            print("[%d/%d] 跳过(已存在) %s" % (i, len(drafts), d["name"]), flush=True)
            continue
        t0 = time.time()
        try:
            note = summarize(model, d["name"], d["raw"], cpu=cpu)
        except Exception as e:
            print("[%d/%d] 失败 %s: %s" % (i, len(drafts), d["name"], e), flush=True)
            continue
        out.append({
            "name": d["name"],
            "keywords": d["keywords"],
            "content": note,
            "priority": 80,
            "case_sensitive": False,
        })
        print("[%d/%d] %s  %d 字  %.0f 秒" % (i, len(drafts), d["name"], len(note), time.time() - t0), flush=True)

    if not out:
        print("没有新条目")
        return

    wb["entries"].extend(out)
    json.dump(wb, open(WB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("\n已写入 %s, 新增 %d 条, 总计 %d 条" % (WB, len(out), len(wb["entries"])))


if __name__ == "__main__":
    main()
