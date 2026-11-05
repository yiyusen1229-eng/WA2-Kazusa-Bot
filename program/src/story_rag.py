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

# 只有「像在问剧情」的话才去检索原作文本：闲聊不该被塞一段剧本。
# 想扩展就在这儿加词（这些词本身都是剧情锚点或回忆的说法）。
STORY_HINTS = ('记得', '以前', '当时', '那时', '后来', '最后', '结局', 'END',
               '故事', '剧情', '发生', '说过', '当年', '回忆', '线里', '那条线',
               '学园祭', '文化祭', '演出', '事故', '车祸', '音乐室', '毕业',
               '温泉', '车站', '音乐会', '告白', '分手', '结婚', '去世', '生病')


# 情境（和 build_index_v3.py 里那套一致；改了要两边一起改，自测会比对数量级）
SIT_RX = {
    "亲密": r"裸|乳|胸|舌|喘|湿|插入|绝顶|爱抚|性器|下腹|湿透|进去了|做了|抱着|抱紧|吻|睡衣|床上",
    "调情": r"挑逗|勾引|调情|暧昧|撩|脸红|心跳|耳语|低语|靠过来|撒娇|凑近|想你了",
    "崩坏": r"哭|泪|呜咽|吼|喊叫|泣|崩溃|对不起|原谅",
    "拌嘴": r"笨蛋|毒舌|顶嘴|吵架|不耐烦|哼|烦人|吵死",
    "校园": r"学园祭|演出|同好会|舞台|放学|教室|社团",
    "工作": r"开樱|编辑部|采访|杂志|加班|会议|工作",
    "离别": r"告白|分手|离开|机场|毕业|再见|别走",
}
_SIT_COMPILED = {k: re.compile(v) for k, v in SIT_RX.items()}


def situation_of(text, loose=False):
    """这句话大概是什么情境（可多个）。命中数够门槛才算，宁缺不滥。

    `loose=True` 给「用户这句话」用：用户一句话很短，门槛必须放低，
    否则「学园祭演出那天」这种明显提示也会被判成没情境（实测就是这样）。
    就算放宽也只是**加分**，不会把不对的片段硬塞进来。
    """
    hits = []
    for name, rx in _SIT_COMPILED.items():
        n = len(rx.findall(text or ""))
        need = 1 if loose else (2 if name in ("亲密", "调情", "崩坏") else 3)
        if n >= need:
            hits.append(name)
    return hits[:3]


def _load_docs(path):
    """读取剧本索引：优先 .json.gz（体积约为 json 的 1/6，启动更快）

    两种格式都认：老版是 `[{src, text}]`，v3 是 `{"v": 3, "blocks": [...]}`
    （v3 每块多带 period / route / tags / title）。
    坏索引（0 字节 / 半截 gz）当没有：cache_io 会删掉它，调用方按"没索引"处理。
    """
    if path.endswith(".gz"):
        data = cache_io.read_gz_json(path) or []
    else:
        data = cache_io.read_json(path) or []
    if isinstance(data, dict):
        return data.get("blocks") or []
    return data



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
            # post[tid] 里每个文档出现几次就存几次（tf），所以 df 要去重后再算，
            # 否则「雪菜」这种高频词会出现 df > N、idf 变负数。
            # 倒排表按 doc id 升序追加，数「分组个数」即可，比 set() 快也不占内存。
            df, last = 0, -1
            for did in self.post[tid]:
                if did != last:
                    df += 1
                    last = did
            v = math.log(1 + (self.N - df + 0.5) / (df + 0.5))
            self._idf[tid] = v
        return v

    def _hit_terms(self, doc_id, q, min_idf=3.0):
        """该文档命中了几个「有信息量」的查询词（常见字不算；min_idf 可放宽）"""
        n = 0
        for t in q:
            tid = self.vocab.get(t)
            if tid is None:
                continue
            if self._idf_of(tid) < min_idf:     # 你好/我/你 这类高频字直接忽略
                continue
            if doc_id in self.post[tid]:
                n += 1
        return n

    def search(self, query, k=2, min_score=5.0, period=None, tags=None):
        CHITCHAT = ('你好', '您好', '早安', '晚安', '天气', '吃了吗', '在吗', '在不在',
                    '嗨', '早上好', '中午好', '拜拜', '再见')
        if any(w in (query or '') for w in CHITCHAT):
            return []
        # 闲聊不检索：只有提到「过去 / 结局 / 具体场景」才去翻剧本，
        # 否则每句「今天好冷」都会被塞 900 字原作片段。
        if not any(h in (query or '') for h in STORY_HINTS):
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
        # 时期 / 情境加权：同一句话，优先取「同样时期」和「同样情境」的片段。
        # （H 场景与调情短篇的语感完全不同；现在是 coda 就别拿 IC 的教室段子。）
        # 做法：先给命中的块加权（保证它们排在前面），再按分数排；没有命中的退回原顺序。
        prefer_ids = set()
        if period or tags:
            want_tags = set(tags or [])
            for i, sc in list(scores.items()):
                d = self.docs[i]
                mult = 1.0
                hit_period = bool(period) and d.get("period") == period
                hit_tag = bool(want_tags) and bool(want_tags & set(d.get("tags") or []))
                if hit_period:
                    mult *= 1.3
                if hit_tag:
                    mult *= 1.5
                if hit_period or hit_tag:
                    prefer_ids.add(i)
                if mult != 1.0:
                    scores[i] = sc * mult
        # 只保留「至少命中 2 个查询词」且分数够高的文档
        need = 2 if len(q) >= 2 else 1
        ok = [(i, sc) for i, sc in scores.items() if self._hit_terms(i, q, 3.0) >= need]
        if not ok:
            # 退一步：整句都是常见字（「学园祭的演出」「雪菜的车祸」）时，
            # 上面那道 idf≥3 的门会一条都不给过。放宽到 1 个词、idf≥1.2，宁可多给一点
            # 也别让「问剧情」变成空手（调用方只有拿到内容才注入）。
            ok = [(i, sc) for i, sc in scores.items() if self._hit_terms(i, q, 1.2) >= 1]
            min_score = min_score * 0.7
        if prefer_ids:
            # 同情境/同时期的优先占位，剩下的按分数补
            ok.sort(key=lambda x: (0 if x[0] in prefer_ids else 1, -x[1]))
        else:
            ok.sort(key=lambda x: -x[1])
        top = ok[:k]
        out = []
        for i, s in top:
            if s < min_score:
                break
            d = self.docs[i]
            out.append({"score": round(s, 2), "src": d.get("src", ""),
                        "text": d["text"], "period": d.get("period", ""),
                        "tags": d.get("tags") or []})
        return out


_CACHE = {}
_BUILD_LOCK = threading.Lock()

GLOBAL_INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "story_index.json")
# v3：同一份剧本、每块多带 period / route / tags（有就用它，没有回落 v2）
GLOBAL_INDEX_V3 = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "story_index_v3.json.gz")


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
    if os.path.exists(GLOBAL_INDEX_V3):
        return GLOBAL_INDEX_V3
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


def memory_context(query, k=2, max_chars=900, period=None, tags=None):
    idx = get_index()
    if idx is None:
        _LAST.update({"hits": [], "chars": 0, "at": int(time.time())})
        return ""
    hits = idx.search(query, k=k, period=period, tags=tags)
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
    # 调试面板（#13）：只留出处 / 分数 / 字数 / 时期与情境标签，不返回正文
    _LAST.update({
        "hits": [{"src": str(h.get("src") or "")[:20], "score": h.get("score"),
                  "chars": len(h.get("text") or ""),
                  "period": h.get("period") or "",
                  "tags": h.get("tags") or []} for h in hits],
        "want_period": period or "",
        "want_tags": list(tags or []),
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
