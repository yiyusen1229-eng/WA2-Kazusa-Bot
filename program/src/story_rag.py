# -*- coding: utf-8 -*-
"""剧本检索 (BM25 + 倒排索引, 纯 Python)
用 array 存倒排表, 内存占用比"每篇存词表"低一个数量级
"""
import array
import json
import math
import os
import re

CJK = re.compile(r"[\u4e00-\u9fff]")
WORD = re.compile(r"[a-zA-Z]{2,}")
STOP = set("的了是我你他她它在和与就都也很还又而但如果不没要会能可以这个那个什么怎么为什么吗呢吧啊呀哦嗯")


def tokenize(text):
    toks = []
    chars = [c for c in text if CJK.match(c)]
    for i in range(len(chars) - 1):
        a, b = chars[i], chars[i + 1]
        if a in STOP and b in STOP:
            continue
        toks.append(a + b)
    toks.extend(WORD.findall(text.lower()))
    return toks


class StoryIndex:
    def __init__(self, path):
        self.docs = json.load(open(path, encoding="utf-8"))
        self.vocab = {}
        self.post = []          # token_id -> array('I') of doc ids (重复即 tf)
        self.dl = array.array("I")
        for i, d in enumerate(self.docs):
            toks = tokenize(d["text"])
            self.dl.append(len(toks) or 1)
            for t in toks:
                tid = self.vocab.get(t)
                if tid is None:
                    tid = len(self.post)
                    self.vocab[t] = tid
                    self.post.append(array.array("I"))
                self.post[tid].append(i)
        self.N = len(self.docs)
        self.avgdl = sum(self.dl) / max(1, self.N)
        self._idf = {}

    def _idf_of(self, tid):
        v = self._idf.get(tid)
        if v is None:
            df = len(self.post[tid])
            v = math.log(1 + (self.N - df + 0.5) / (df + 0.5))
            self._idf[tid] = v
        return v

    def _hit_terms(self, doc_id, q):
        """该文档命中了几个「有信息量」的查询词（常见字不算）"""
        n = 0
        for t in q:
            tid = self.vocab.get(t)
            if tid is None:
                continue
            if self._idf_of(tid) < 3.0:     # 你好/我/你 这类高频字直接忽略
                continue
            if doc_id in self.post[tid]:
                n += 1
        return n

    def search(self, query, k=2, min_score=5.0):
        CHITCHAT = ('你好', '您好', '早安', '晚安', '天气', '吃了吗', '在吗', '在不在',
                    '嗨', '早上好', '中午好', '拜拜', '再见')
        if any(w in (query or '') for w in CHITCHAT):
            return []
        q = tokenize(query)
        if not q:
            return []
        scores = {}
        for t in q:
            tid = self.vocab.get(t)
            if tid is None:
                continue
            idf = self._idf_of(tid)
            arr = self.post[tid]
            # 统计每个文档里该词出现次数
            last, cnt = -1, 0
            for doc_id in list(arr) + [-1]:
                if doc_id == last:
                    cnt += 1
                    continue
                if last >= 0 and cnt:
                    dl = self.dl[last] or 1
                    s = idf * (cnt * 2.2) / (cnt + 1.2 * (0.25 + 0.75 * dl / self.avgdl))
                    scores[last] = scores.get(last, 0.0) + s
                last, cnt = doc_id, 1
        # 只保留「至少命中 2 个查询词」且分数够高的文档
        need = 2 if len(q) >= 2 else 1
        MIN_HIT_TERMS = need
        top = [(i, sc) for i, sc in sorted(scores.items(), key=lambda x: -x[1])
               if self._hit_terms(i, q) >= MIN_HIT_TERMS][:k]
        out = []
        for i, s in top:
            if s < min_score:
                break
            out.append({"score": round(s, 2), "src": self.docs[i].get("src", ""),
                        "text": self.docs[i]["text"]})
        return out


_CACHE = {}


def get_index(path=None):
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "story_index.json")
    if path not in _CACHE:
        if not os.path.exists(path):
            return None
        _CACHE[path] = StoryIndex(path)
    return _CACHE[path]


def memory_context(query, k=2, max_chars=900):
    idx = get_index()
    if idx is None:
        return ""
    hits = idx.search(query, k=k)
    if not hits:
        return ""
    parts, used = [], 0
    for h in hits:
        t = h["text"].strip()
        if used + len(t) > max_chars:
            t = t[:max(200, max_chars - used)]
        parts.append(t)
        used += len(t)
        if used >= max_chars:
            break
    return "\n---\n".join(parts)
