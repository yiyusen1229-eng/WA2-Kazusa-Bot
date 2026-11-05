# -*- coding: utf-8 -*-
"""演出 / 切片规则配置（perfcfg.py）的自测（#19，不联网、不开界面）。

跑法：
    cd program
    build_env/venv/Scripts/python.exe tools/test_perfcfg.py

验的是：
  1. 没有配置文件 → 默认值，而且**默认值必须等于现有代码里的常量**（不然「什么都没配」也会改行为）
  2. 正常覆盖：fade_ms / 两张映射表 / 五个切片预算都生效
  3. 逐字段校验：超范围夹边界、类型不对用默认、不认识的键忽略，全部给 warning
  4. 整份 JSON 坏了 / 顶层不是对象 → 全默认 + warning，不炸
  5. 映射表：非 dict、坏条目、超长键、超条数都被挡掉
  6. 没有当前角色 / 换角色 → 不炸，读的是对的那份
  7. 缓存：文件改了能立刻读到
"""
import json
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROGRAM, "src"))

_TMP = tempfile.mkdtemp(prefix="wa2_perfcfg_test_")
os.environ["WA2_USER_DIR"] = _TMP
os.environ["WA2_CACHE_DIR"] = os.path.join(_TMP, "cache")
os.environ["WA2_SESS_DIR"] = os.path.join(_TMP, "sessions")

import api_chat      # noqa: E402
import characters    # noqa: E402
import perfcfg       # noqa: E402
import persona_ctx   # noqa: E402

FAILS = []
CUR = {"id": "和纱"}


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:200]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def char_dir(cid=None):
    cid = cid or CUR["id"]
    d = os.path.join(_TMP, "characters", cid)
    os.makedirs(os.path.join(d, "memory"), exist_ok=True)
    root = os.path.join(_TMP, "characters")
    with open(os.path.join(root, "active.json"), "w", encoding="utf-8") as f:
        json.dump({"id": cid}, f, ensure_ascii=False)
    return d


def write(d, name, obj):
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8") as f:
        if isinstance(obj, str):
            f.write(obj)
        else:
            json.dump(obj, f, ensure_ascii=False)
    return p


def fresh(d):
    perfcfg.clear_cache()
    return d


def main():
    d = char_dir()

    # ---------------------------------------------------------------- 1 默认值
    fresh(d)
    p, s, w, files = perfcfg.load()
    check("没有配置文件：没有 warning", w == [], w)
    check("没有配置文件：三个演出默认值", p["fade_ms"] == 240 and p["mood_to_emotion"] == {}
          and p["outfit_by_scene"] == {}, p)
    check("没有配置文件：五个切片默认值",
          (s["story_k"], s["story_max_chars"], s["worldbook_entries"],
           s["worldbook_chars"], s["memory_max_chars"]) == (2, 900, 3, 1200, 1500), s)
    check("files 里给了两个路径", files["performance"].endswith("performance.json")
          and files["slices"].endswith("persona_slices.json"), files)

    # 默认值必须和代码常量一致（否则「没配」也会悄悄改行为）
    check("fade_ms 默认 = wt-fade 的 240", p["fade_ms"] == 240)
    check("story_k 默认 = api_chat.STORY_K", s["story_k"] == api_chat.STORY_K, api_chat.STORY_K)
    check("story_max_chars 默认 = api_chat.STORY_MAX_CHARS",
          s["story_max_chars"] == api_chat.STORY_MAX_CHARS)
    check("worldbook_entries 默认 = persona_ctx.WB_DEFAULT_ENTRIES",
          s["worldbook_entries"] == persona_ctx.WB_DEFAULT_ENTRIES)
    check("worldbook_chars 默认 = persona_ctx.WB_DEFAULT_CHARS",
          s["worldbook_chars"] == persona_ctx.WB_DEFAULT_CHARS)

    # ---------------------------------------------------------------- 2 正常覆盖
    write(d, "performance.json", {"fade_ms": 280,
                                  "mood_to_emotion": {"warm": "smile", "shy": "sad"},
                                  "outfit_by_scene": {"夜の学校": "冬季校服"}})
    write(d, "persona_slices.json", {"story_k": 3, "story_max_chars": 1000,
                                     "worldbook_entries": 4, "worldbook_chars": 1400,
                                     "memory_max_chars": 800})
    fresh(d)
    p, s, w, _ = perfcfg.load()
    check("fade_ms 覆盖生效", p["fade_ms"] == 280, p["fade_ms"])
    check("情绪映射覆盖生效", p["mood_to_emotion"].get("shy") == "sad", p["mood_to_emotion"])
    check("场景映射覆盖生效", p["outfit_by_scene"].get("夜の学校") == "冬季校服", p["outfit_by_scene"])
    check("切片覆盖生效", (s["story_k"], s["story_max_chars"], s["worldbook_entries"],
                          s["worldbook_chars"], s["memory_max_chars"]) == (3, 1000, 4, 1400, 800), s)
    check("正常配置没有 warning", w == [], w)
    check("detail() 结构齐全",
          set(perfcfg.detail()) >= {"ok", "performance", "slices", "warnings", "files"})

    # ---------------------------------------------------------------- 3 校验
    write(d, "performance.json", {"fade_ms": 9999, "不认识": 1})
    write(d, "persona_slices.json", {"story_k": -5, "worldbook_entries": 99, "story_max_chars": "很多"})
    fresh(d)
    p, s, w, _ = perfcfg.load()
    check("fade_ms 超上限夹到 300", p["fade_ms"] == 300, p["fade_ms"])
    check("story_k 负数夹到 0", s["story_k"] == 0, s["story_k"])
    check("worldbook_entries 超上限夹到 8", s["worldbook_entries"] == 8, s["worldbook_entries"])
    check("story_max_chars 给字符串 → 用默认 900", s["story_max_chars"] == 900, s["story_max_chars"])
    check("超范围有 warning", any("夹到边界" in x for x in w), w)
    check("类型不对有 warning", any("要数字" in x for x in w), w)
    check("不认识的键有 warning", any("不认识" in x for x in w), w)
    check("未知键不影响已知键", s["story_k"] == 0)

    write(d, "persona_slices.json", {"story_k": True, "memory_max_chars": 1200.7})
    fresh(d)
    _p, s, w, _ = perfcfg.load()
    check("bool 不算数字 → 用默认", s["story_k"] == 2, s["story_k"])
    check("小数会取整", s["memory_max_chars"] == 1200, s["memory_max_chars"])

    # ---------------------------------------------------------------- 4 整份坏掉
    write(d, "performance.json", "{ 这不是 json")
    fresh(d)
    p, _s, w, _ = perfcfg.load()
    check("坏 json：整份用默认", p["fade_ms"] == 240 and p["mood_to_emotion"] == {}, p)
    check("坏 json：给 warning", any("读不了" in x for x in w), w)

    write(d, "performance.json", "[1, 2, 3]")
    fresh(d)
    p, _s, w, _ = perfcfg.load()
    check("顶层不是对象：用默认", p["fade_ms"] == 240)
    check("顶层不是对象：给 warning", any("顶层必须是一个对象" in x for x in w), w)

    # ---------------------------------------------------------------- 5 映射表
    write(d, "performance.json", {
        "mood_to_emotion": "不是对象",
        "outfit_by_scene": {"好场景": "校服", "坏场景": 123, "": "空键",
                            ("x" * 40): "太长键"},
    })
    fresh(d)
    p, _s, w, _ = perfcfg.load()
    check("映射表不是对象 → 空表 + warning",
          p["mood_to_emotion"] == {} and any("要一个对象" in x for x in w), w)
    check("合法条目保留", p["outfit_by_scene"].get("好场景") == "校服", p["outfit_by_scene"])
    check("值不是字符串的条目丢掉", "坏场景" not in p["outfit_by_scene"])
    check("空键丢掉", "" not in p["outfit_by_scene"])
    check("超长键丢掉", not any(len(k) > 30 for k in p["outfit_by_scene"]))
    check("坏条目有 warning", any("跳过" in x for x in w), w)

    big = dict(("k%d" % i, "v%d" % i) for i in range(60))
    write(d, "performance.json", {"outfit_by_scene": big})
    fresh(d)
    p, _s, w, _ = perfcfg.load()
    check("超过 %d 条只留 %d" % (perfcfg.MAX_MAP_ITEMS, perfcfg.MAX_MAP_ITEMS),
          len(p["outfit_by_scene"]) == perfcfg.MAX_MAP_ITEMS, len(p["outfit_by_scene"]))
    check("超条数有 warning", any("超过" in x for x in w), w)

    # ---------------------------------------------------------------- 6 换角色
    d2 = char_dir("雪菜")
    write(d2, "persona_slices.json", {"story_k": 5})
    fresh(d2)
    _p, s2, _w, files2 = perfcfg.load()
    check("换角色读的是新角色的文件", s2["story_k"] == 5, s2["story_k"])
    check("路径跟着角色走", "雪菜" in files2["slices"], files2["slices"])
    # 旧角色没配 story_k 仍然是默认
    d1 = char_dir("和纱")
    fresh(d1)
    _p, s1, _w, _f = perfcfg.load()
    check("切回来又回到默认（和纱没配这条）", s1["story_k"] == 2, s1["story_k"])

    # ---------------------------------------------------------------- 7 缓存
    write(d1, "persona_slices.json", {"story_k": 1})
    fresh(d1)
    check("改文件后读到新值", perfcfg.slices()["story_k"] == 1)
    write(d1, "persona_slices.json", {"story_k": 4})
    check("不 clear_cache 也能读到（按 mtime 失效）", perfcfg.slices()["story_k"] == 4,
          perfcfg.slices()["story_k"])

    # 带 BOM 的 UTF-8（记事本 / PowerShell 5.1 存出来的样子）也要能读
    p_bom = os.path.join(d1, "performance.json")
    with open(p_bom, "wb") as f:
        f.write(b"\xef\xbb\xbf" + json.dumps({"fade_ms": 260}).encode("utf-8"))
    fresh(d1)
    p2, _s, w2, _f = perfcfg.load()
    check("带 BOM 的 JSON 也能读（不当成坏文件）", p2["fade_ms"] == 260, (p2["fade_ms"], w2))
    check("带 BOM 不产生 warning", not any("读不了" in x for x in w2), w2)

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), " / ".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
