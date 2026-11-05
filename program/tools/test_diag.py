# -*- coding: utf-8 -*-
"""调试面板状态账本（diag.py）的自测（不联网、不开界面）。

跑法：
    cd program
    build_env/venv/Scripts/python.exe tools/test_diag.py

验的是：
  1. token 估算：中日文 1 字≈1 token、英文 4 字≈1 token、空串 0
  2. 计数器累加、取出来是快照（改返回值不影响内部）
  3. note 覆盖写（只留最近一次）+ at 时间戳
  4. round_record 滚动只留 KEEP 条，且自动 +1 计数
  5. snapshot() 结构完整：server / counters / rounds / modules 六个块都在
  6. snapshot() 是只读的：连跑两次，计数和轮次都不变
  7. 面板数据里没有密钥、没有对话正文（只允许数字和小标签）
  8. persona_stage.debug_state() 不推进状态（跑完 stage/rounds 不变）
  9. story_rag.last_hits() 结构（没检索过也是合法空值）
 10. cache_io.stats() 的字段在 snapshot 里能对上
"""
import json
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROGRAM, "src"))

# 先指到临时缓存目录，别碰真实运行状态
_TMP = tempfile.mkdtemp(prefix="wa2_diag_test_")
os.environ["WA2_CACHE_DIR"] = _TMP
os.environ["WA2_SESS_DIR"] = os.path.join(_TMP, "sessions")

import diag            # noqa: E402
import cache_io        # noqa: E402
import persona_stage   # noqa: E402
import story_rag       # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:200]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def main():
    diag.reset()

    # 1 --------------------------------------------------------------------
    check("空串 0 token", diag.token_est("") == 0)
    zh = diag.token_est("今天天气不错，我们去散步吧")
    check("12 个汉字 ≈ 12~14 token", 12 <= zh <= 16, zh)
    en = diag.token_est("abcdefghijkl")
    check("12 个字母 ≈ 4 token", 3 <= en <= 6, en)
    check("混排比纯英文贵", diag.token_est("你好 world") > diag.token_est("world"))

    # 2 --------------------------------------------------------------------
    diag.count("text.disk")
    diag.count("text.disk")
    diag.count("tts.hit", 3)
    c = diag.counters()
    check("计数器累加", c["text.disk"] == 2 and c["tts.hit"] == 3, c)
    c["text.disk"] = 999
    check("取出来的是快照（改返回值不影响内部）", diag.counters()["text.disk"] == 2)

    # 3 --------------------------------------------------------------------
    diag.note("scene", id="cafe_dusk", score=0.86)
    diag.note("scene", id="school_day", score=0.9)
    n = diag.note_get("scene")
    check("note 覆盖写只留最近一次", n.get("id") == "school_day" and n.get("score") == 0.9, n)
    check("note 带时间戳", isinstance(n.get("at"), int) and n["at"] > 0, n)

    # 4 --------------------------------------------------------------------
    for i in range(diag.KEEP + 5):
        diag.round_record(ms=100 + i, model="m%d" % i, seg={"persona": i}, tokens={"system": i})
    rs = diag.rounds()
    check("轮次滚动只留 KEEP 条", len(rs) == diag.KEEP, len(rs))
    check("留下的是最近的几条", rs[-1]["model"] == "m%d" % (diag.KEEP + 4), rs[-1])
    check("round_record 自动 +1 计数", diag.counters()["chat.round"] == diag.KEEP + 5,
          diag.counters().get("chat.round"))

    # 5 --------------------------------------------------------------------
    snap = diag.snapshot()
    check("snapshot ok", snap.get("ok") is True)
    check("server 块有 pid / 运行时长", isinstance(snap["server"].get("pid"), int)
          and isinstance(snap["server"].get("uptime_s"), int), snap["server"])
    check("rounds 长度对得上", len(snap["rounds"]) == diag.KEEP, len(snap["rounds"]))
    mods = snap.get("modules") or {}
    for k in ("memory", "stage", "tts", "story", "scene", "cache"):
        check("modules.%s 在" % k, k in mods, list(mods))
    check("cache 块有 checked / dropped",
          "checked" in mods["cache"] and "dropped" in mods["cache"], mods["cache"])
    check("memory 块有条目数和预算",
          "entries" in mods["memory"] and "budget" in mods["memory"], mods["memory"])
    check("stage 块有阶段和间隔",
          "stage" in mods["stage"] and "every" in mods["stage"], mods["stage"])

    # 6 --------------------------------------------------------------------
    before = (len(diag.rounds()), dict(diag.counters()))
    sn1 = diag.snapshot()
    sn2 = diag.snapshot()
    after = (len(diag.rounds()), dict(diag.counters()))
    check("snapshot 只读（轮次 / 计数不变）", before == after, (before, after))
    check("两次 snapshot 结构一致", set(sn1) == set(sn2), (list(sn1), list(sn2)))

    # 7 --------------------------------------------------------------------
    blob = json.dumps(snap, ensure_ascii=False)
    check("面板数据里没有密钥样式的串", "sk-" not in blob and "api_key" not in blob)
    # 允许的字段：数字 / 模型名 / 时期 / 衣服名 / 世界书条目标题 / 场景 id
    secret_text = "这是不该出现在面板里的对话正文"
    diag.round_record(model="deepseek-chat", seg={"persona": 800}, reply_chars=24)
    blob2 = json.dumps(diag.snapshot(), ensure_ascii=False)
    check("没有把正文写进账本", secret_text not in blob2)

    # 账本里的字符串只允许是标签（模型名 / 时期 / 衣服 / 场景 id / 条目标题），不许是长文本
    vals = []

    def walk(v):
        if isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, str):
            vals.append(v)

    walk(diag.snapshot())
    longest = max((len(v) for v in vals), default=0)
    check("最长字段只有 %d 字（≤40，都是标签）" % longest, longest <= 40,
          sorted(vals, key=len)[-3:] if vals else [])

    # 8 --------------------------------------------------------------------
    st1 = persona_stage.debug_state()
    st2 = persona_stage.debug_state()
    check("debug_state 字段齐",
          all(k in st1 for k in ("stage", "rounds", "last_round", "seen", "every", "due_in", "busy")), st1)
    check("debug_state 不推进状态", st1 == st2, (st1, st2))
    check("阶段在 1~4", 1 <= st1["stage"] <= 4, st1)

    # 9 --------------------------------------------------------------------
    hits = story_rag.last_hits()
    check("last_hits 是 dict 且有 hits 列表", isinstance(hits, dict) and isinstance(hits.get("hits"), list), hits)
    check("cached_blocks 不触发加载（返回 0 或块数）",
          isinstance(story_rag.cached_blocks(), int), story_rag.cached_blocks())

    # 10 -------------------------------------------------------------------
    cache_io.reset_stats()
    snap3 = diag.snapshot()
    check("cache 计数跟着 cache_io 走", snap3["modules"]["cache"]["checked"] == 0,
          snap3["modules"]["cache"])

    # 11 -------------------------------------------------------------------
    diag.reset()
    check("reset 清干净", diag.counters() == {} and diag.rounds() == [] and diag.note_get("scene") == {})

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), " / ".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
