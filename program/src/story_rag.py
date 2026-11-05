# -*- coding: utf-8 -*-
"""剧本检索 (BM25 + 倒排索引, 纯 Python)
用 array 存倒排表, 内存占用比"每篇存词表"低一个数量级
"""
import array
import gzip
import json
import math
import os
import re
import threading
import time

import cache_io

# 最近一次检索的只看账（调试面板用：出处 / 分数 / 字数，不含正文）
_LAST = {"hits": [], "chars": 0, "at": 0}

CJK = re.compile(r"[\u4e00-\u9fff]")
WORD = re.compile(r"[a-zA-Z]{2,}")
STOP = set("的了是我你他她它在和与就都也很还又而但如果不没要会能可以这个那个什么怎么为什么吗呢吧啊呀哦嗯")


def _load_docs(path):
    """读取剧本索引：优先 .json.gz（体积约为 json 的 1/6，启动更快）

    坏索引（0 字节 / 半截 gz）当没有：cache_io 会删掉它，调用方按"没索引"处理。
    """
    if path.endswith(".gz"):
        return cache_io.read_gz_json(path) or []
    return cache_io.read_json(path) or []



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
        self.docs = _load_docs(path)
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
_BUILD_LOCK = threading.Lock()

GLOBAL_INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "story_index.json")


def _char_dir():
    """当前角色的文件夹（没有就空串）"""
    try:
        import characters
        return characters.active_dir() or ""
    except Exception:
        return ""


def _char_cfg():
    """角色自己的剧情检索配置：characters/<角色>/story.json

        没有这个文件      → 沿用旧行为（用全局索引）
        {"enabled": false} → 这个角色不做剧情检索
        {"index": "xx.gz"} → 用角色文件夹里的这份索引（相对角色文件夹）
    """
    d = _char_dir()
    if not d:
        return {}
    p = os.path.join(d, "story.json")
    try:
        with open(p, encoding="utf-8") as f:
            v = json.load(f)
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def enabled():
    """这个角色要不要做剧情检索（新角色默认关，避免捞到别人的剧情）"""
    return _char_cfg().get("enabled", True) is not False


def active_index():
    """当前角色实际用的索引文件：角色自带优先，否则全局那份（和纱的）"""
    d = _char_dir()
    if d:
        cfg = _char_cfg()
        rel = (cfg.get("index") or "").strip()
        if rel:
            p = rel if os.path.isabs(rel) else os.path.join(d, rel)
            if os.path.exists(p):
                return p
            if os.path.exists(p + ".gz"):
                return p + ".gz"
        own = os.path.join(d, "story_index.json.gz")
        if os.path.exists(own):
            return own
    return GLOBAL_INDEX


def get_index(path=None):
    if path is None:
        path = active_index()
    # 有 .gz 就用 .gz
    gz = path + ".gz"
    if os.path.exists(gz):
        path = gz
    if path in _CACHE:
        return _CACHE[path]
    if not os.path.exists(path):
        return None
    # 第一次建索引要读 12MB 并分词，可能被多个请求同时触发 —— 加锁只建一次
    with _BUILD_LOCK:
        if path not in _CACHE:
            _CACHE[path] = StoryIndex(path)
    return _CACHE[path]


def preload():
    """启动时后台预热（main.py 调用），别让第一句相关的话等 1 秒多"""
    try:
        if not enabled():
            return False
        return get_index() is not None
    except Exception:
        return False


def memory_context(query, k=2, max_chars=900):
    idx = get_index()
    if idx is None:
        _LAST.update({"hits": [], "chars": 0, "at": int(time.time())})
        return ""
    hits = idx.search(query, k=k)
    if not hits:
        _LAST.update({"hits": [], "chars": 0, "at": int(time.time())})
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
    # 调试面板（#13）：只留出处 / 分数 / 字数，不返回正文
    _LAST.update({
        "hits": [{"src": str(h.get("src") or "")[:20], "score": h.get("score"),
                  "chars": len(h.get("text") or "")} for h in hits],
        "chars": used,
        "at": int(time.time()),
    })
    return "\n---\n".join(parts)


def last_hits():
    """最近一次检索的只看账（面板 / 自测用；不含正文）"""
    return dict(_LAST)


def cached_blocks():
    """已经加载进内存的索引有多少块；没加载返回 0（**不触发加载**，面板轮询不能拖 1 秒）"""
    try:
        for idx in list(_CACHE.values()):
            return len(getattr(idx, "docs", []) or [])
    except Exception:
        pass
    return 0
