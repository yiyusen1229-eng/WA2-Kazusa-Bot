# -*- coding: utf-8 -*-
"""剧情检索（story_rag）的自测（不联网、不开界面）。

跑法：
    cd program
    build_env/venv/Scripts/python.exe tools/test_story_rag.py

验的是：
  1. 分词：汉字二元组、停用字对跳过、英文单词
  2. df 按文档去重：同一个词在一篇里出现 20 次也只是一篇（以前会 idf 变负数）
  3. 意图门槛：闲聊（今天好冷 / 你好 / 我饿了）一条不取；带剧情锚点才检索
  4. 严格档：两个罕见词命中
  5. 退档：整句都是常见词时也能命中（「学园祭的演出」这类以前是 0 命中）
  6. 排序与 k 上限、分数下限
  7. memory_context 的 max_chars 截断 + 只看账（last_hits 不含正文）
"""
import json
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROGRAM, "src"))

import story_rag as S  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:200]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


FILLER = "甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥天地玄黄宇宙洪荒日月盈昃辰宿列张"


def make_docs(n=200):
    docs = []
    for i in range(n):
        # 每篇用固定的填充字（二元组高度重复 → idf 很低），保证不含目标词
        body = (FILLER * 8)[:200]
        docs.append({"src": "填充%d" % i, "text": body})
    docs[0] = {"src": "11/2 星期二", "text": "〔学园祭的演出〕\n礼堂里坐满了人，演出非常成功。"}
    docs[1] = {"src": "2/14 星期四", "text": "〔雪菜的车祸〕\n那天的车祸在冬天，所幸并无大碍。"}
    docs[2] = {"src": "11/1 星期四", "text": "〔第二音乐室〕\n第二音乐室的门锁着，钢琴还在。"}
    # 一篇里重复很多次，但仍只是一篇（测 df 去重）
    docs[3] = {"src": "重复", "text": "车祸" * 20 + FILLER}
    return docs


def main():
    tmp = tempfile.mkdtemp(prefix="story_rag_test_")
    path = os.path.join(tmp, "index.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(make_docs(), f, ensure_ascii=False)
    idx = S.StoryIndex(path)

    # 1) 分词
    toks = S.tokenize("学园祭的演出")
    check("汉字切成二元组", toks[:2] == ["学园", "园祭"], toks)
    check("英文单词也进词表", "hi" in S.tokenize("hi 你好"), S.tokenize("hi 你好"))
    check("两个停用字组成的二元组被跳过", "的了" not in S.tokenize("的了"), S.tokenize("的了"))

    # 2) df 去重 / idf 不为负
    tid = idx.vocab["车祸"]
    df = sum(1 for did in idx.post[tid] if did != -1) and len(set(idx.post[tid]))
    check("重复词仍只算一篇（df 去重）", df <= 3, df)
    check("idf 不会变负数", idx._idf_of(tid) > 0, idx._idf_of(tid))
    common = idx.vocab.get("甲乙") or idx.vocab.get("乙丙")
    check("高频填充词的 idf 很低", idx._idf_of(common) < 1.0, idx._idf_of(common))

    # 3) 意图门槛
    for q in ("今天好冷", "你好", "我饿了", "周末做什么", "你弹钢琴吗"):
        check("闲聊不检索：%s" % q, idx.search(q) == [], idx.search(q))

    # 4) 严格档：带剧情锚点 + 罕见词
    hits = idx.search("雪菜的车祸是什么时候")
    check("剧情问句能命中", len(hits) >= 1, hits)
    check("命中的是车祸那篇", hits and "车祸" in hits[0]["text"], hits[0]["text"][:40] if hits else "")
    check("出处带章节", hits and hits[0]["src"] == "2/14 星期四", hits[0]["src"] if hits else "")

    # 5) 退档：整句常见词
    hits2 = idx.search("回忆一下学园祭的演出")
    check("常见词组成的剧情问句也能命中（退档）", len(hits2) >= 1, hits2)
    check("命中的是学园祭那篇", hits2 and "学园祭" in hits2[0]["text"],
          hits2[0]["text"][:30] if hits2 else "")

    # 6) k 上限 / 无关词
    check("k=1 只回一条", len(idx.search("学园祭的演出", k=1)) <= 1)
    check("没有命中词时返回空", idx.search("记得那件事吗") == [])

    # 7) memory_context：截断 + 只看账
    old = S.get_index
    try:
        S.get_index = lambda path=None: idx
        text = S.memory_context("学园祭的演出", k=2, max_chars=120)
        check("max_chars 生效（不超上限太多）", 0 < len(text) <= 400, len(text))
        st = S.last_hits()
        check("last_hits 有 hits/chars/at", set(st) == {"hits", "chars", "at"}, list(st))
        check("last_hits 不含正文", all("text" not in h for h in st["hits"]), st["hits"][:1])
        check("last_hits 记了出处", st["hits"] and st["hits"][0]["src"], st["hits"][:1])
    finally:
        S.get_index = old

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), " / ".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
