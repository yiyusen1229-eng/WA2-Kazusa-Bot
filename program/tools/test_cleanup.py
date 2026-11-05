# -*- coding: utf-8 -*-
"""数据清理入口（#17）自测：概览体积 / 清缓存 / 导出脱敏 / 删角色。

跑法：
    cd program
    build_env/venv/Scripts/python.exe tools/test_cleanup.py

全部走临时目录（`tempfile.mkdtemp`，TEMP 已被 run_smoke 指到 work_scratch/tmp），
不碰真实日志、真实角色、真实缓存。重点验三件事：

1. **只删该删的**：正在写的那份日志不删、存档和角色内容一个字节都不动；
2. **导出必须脱敏**：zip 里不能出现 `sk-` 原文；
3. **删角色要二次确认**：confirm 不对 / 是当前角色 / id 带 `..`，三种都拒绝。
"""
import json
import os
import shutil
import sys
import tempfile
import time
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROGRAM, "src"))

import api_cleanup as C

FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:300]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def build_tree(base):
    """造一套假的数据目录，返回各路径"""
    d = {}
    d["logs"] = os.path.join(base, "logs")
    d["cache"] = os.path.join(base, "cache")
    d["text"] = os.path.join(base, "textcache")
    d["tts"] = os.path.join(base, "ttscache")
    d["scratch"] = os.path.join(base, "work_scratch")
    d["chars"] = os.path.join(base, "characters")

    today = time.strftime("%Y%m%d")
    write(os.path.join(d["logs"], "app-%s.log" % today), "今天的日志" * 10)
    write(os.path.join(d["logs"], "app-20200101.log"), "旧日志" * 20)
    write(os.path.join(d["logs"], "app-20200102.log"), "旧日志2" * 20)
    write(os.path.join(d["logs"], "perf-2020-01-01.csv"), "a,b\n1,2\n")
    write(os.path.join(d["logs"], "crash_20200101_000000.log"), "boom" * 30)
    write(os.path.join(d["logs"], "asset_report.json"), '{"ok": true}')

    write(os.path.join(d["cache"], "memory_runtime.json"), "{}")
    write(os.path.join(d["cache"], "persona_stage.json"), '{"stage": 2}')
    write(os.path.join(d["cache"], "prices.json"), "{}")
    write(os.path.join(d["cache"], "keep_me.txt"), "不是缓存")

    write(os.path.join(d["text"], "abc.png"), "x" * 100)
    write(os.path.join(d["tts"], "a.wav"), "y" * 200)
    write(os.path.join(d["scratch"], "tmp", "junk.txt"), "z" * 50)
    write(os.path.join(d["scratch"], "keep.log"), "留着的")

    # 两个角色：一个当前用，一个可删
    c = os.path.join(d["chars"], "和纱")
    write(os.path.join(c, "name.txt"), "和纱")
    write(os.path.join(c, "prompt", "base.txt"), "你是和纱，key=sk-abcdef123456")
    write(os.path.join(c, "prompt", "base.txt.bak"), "旧版")
    write(os.path.join(c, "worldbook", "worldbook.json"), '{"entries": []}')
    write(os.path.join(c, "memory", "记忆书.txt"), "她记得的事")
    write(os.path.join(c, "sessions", "1.json"), '{"turns": 3}')
    write(os.path.join(c, "portrait", "x.png"), "P" * 500)

    other = os.path.join(d["chars"], "新角色")
    write(os.path.join(other, "name.txt"), "雪菜")
    write(os.path.join(other, "prompt", "base.txt"), "你是雪菜")
    write(os.path.join(other, "sessions", "2.json"), '{"turns": 1}')
    write(os.path.join(d["cache"], "新角色", "tts.wav"), "T" * 80)
    return d


def main():
    base = tempfile.mkdtemp(prefix="wa2_cleanup_")
    d = build_tree(base)
    kw = dict(log_dir=d["logs"], cache_dir=d["cache"], text_cache=d["text"],
              tts_cache=d["tts"], scratch_dir=d["scratch"],
              root=d["chars"], chars=["和纱", "新角色"])

    # ---------- 概览
    ov = C.overview(**kw)
    check("概览 ok", ov.get("ok") is True)
    items = {it["key"]: it for it in ov["items"]}
    check("概览列出 8 个清理项", len(ov["items"]) == 8, len(ov["items"]))
    check("概览项顺序与 KINDS 一致",
          [it["key"] for it in ov["items"]] == [k for k, _l, _n in C.KINDS])
    check("历史日志算了两份旧日志", items["logs"]["files"] == 3, items["logs"]["files"])
    check("性能采样体积对", items["perf"]["bytes"] == os.path.getsize(
        os.path.join(d["logs"], "perf-2020-01-01.csv")))
    check("崩溃现场 1 份", items["crash"]["files"] == 1)
    check("素材报告 1 份", items["asset_report"]["files"] == 1)
    check("运行时缓存只算那三份", items["runtime"]["files"] == 3,
          items["runtime"]["files"])
    check("字模缓存 100 字节", items["text_cache"]["bytes"] == 100)
    check("语音缓存 200 字节", items["tts_cache"]["bytes"] == 200)
    check("临时目录算全部内容", items["scratch"]["bytes"] == 59, items["scratch"]["bytes"])

    ch = {c["id"]: c for c in ov["characters"]}
    check("概览两个角色", len(ov["characters"]) == 2)
    check("角色显示名读 name.txt", ch["新角色"]["name"] == "雪菜", ch["新角色"]["name"])
    check("角色体积含立绘", ch["和纱"]["bytes"] > 500)
    check("存档体积单独算", ch["和纱"]["sessions_bytes"] > 0)
    check("总量 = 缓存 + 角色", ov["total_bytes"] == ov["cache_bytes"] + ov["characters_bytes"])

    # ---------- 清缓存：日志（保留今天那份）
    r = C.clean(["logs"], **{k: v for k, v in kw.items() if k in
                             ("log_dir", "cache_dir", "text_cache", "tts_cache", "scratch_dir")})
    got = r["cleaned"][0]
    today = time.strftime("%Y%m%d")
    check("清了 2 份旧日志", got["removed"] == 2, got["removed"])
    check("今天那份还在", os.path.exists(os.path.join(d["logs"], "app-%s.log" % today)))
    check("skipped 说明今天那份在写",
          any("正在写" in s for s in got["skipped"]), got["skipped"])

    # ---------- 清缓存：perf / crash / asset_report
    r = C.clean(["perf", "crash", "asset_report"], log_dir=d["logs"])
    total = sum(x["removed"] for x in r["cleaned"])
    check("perf+crash+report 共删 3 个文件", total == 3, total)
    check("perf csv 没了", not os.path.exists(os.path.join(d["logs"], "perf-2020-01-01.csv")))
    check("crash 没了", not os.path.exists(
        os.path.join(d["logs"], "crash_20200101_000000.log")))
    check("asset_report 没了", not os.path.exists(
        os.path.join(d["logs"], "asset_report.json")))

    # ---------- 清缓存：runtime 只删三个 json
    r = C.clean(["runtime"], cache_dir=d["cache"])
    check("runtime 删了 3 个", r["cleaned"][0]["removed"] == 3, r["cleaned"][0]["removed"])
    check("cache 里别的文件留着", os.path.exists(os.path.join(d["cache"], "keep_me.txt")))
    check("cache 下的角色缓存没被顺手删", os.path.isdir(os.path.join(d["cache"], "新角色")))

    # ---------- 清缓存：字模 / 语音 / 临时目录
    r = C.clean(["text_cache", "tts_cache", "scratch"], text_cache=d["text"],
                tts_cache=d["tts"], scratch_dir=d["scratch"])
    check("字模缓存目录没了", not os.path.isdir(d["text"]))
    check("语音缓存目录没了", not os.path.isdir(d["tts"]))
    check("临时目录里 tmp 没了", not os.path.isdir(os.path.join(d["scratch"], "tmp")))
    check("临时目录本身还在", os.path.isdir(d["scratch"]))
    check("临时目录里的散文件也清了", not os.path.exists(os.path.join(d["scratch"], "keep.log")))
    check("释放字节 = 100+200+59", r["freed_bytes"] == 359, r["freed_bytes"])

    # ---------- 不认识的 key
    r = C.clean(["不存在的东西"], log_dir=d["logs"])
    check("未知 key 记在 unknown 里", r["unknown"] == ["不存在的东西"], r["unknown"])
    check("未知 key 不算失败", r.get("ok") is True)

    # ---------- 导出：默认不含对话 + 脱敏
    out = os.path.join(base, "out")
    e = C.export(turns=0, out_dir=out, root=d["chars"], chars=["和纱", "新角色"],
                 log_dir=d["logs"])
    check("导出回 ok", e.get("ok") is True, e.get("error"))
    check("zip 落盘了", os.path.exists(e.get("path") or ""))
    with zipfile.ZipFile(e["path"]) as zf:
        names = zf.namelist()
        blob = "\n".join(zf.read(n).decode("utf-8", "replace") for n in names
                         if n.endswith((".json", ".txt")))
        man1 = json.loads(zf.read("manifest.json").decode("utf-8"))
    check("有 manifest.json", "manifest.json" in names)
    check("有 README.txt", "README.txt" in names)
    check("带了人设 / 世界书 / 记忆书",
          "characters/和纱/prompt/base.txt" in names and
          "characters/和纱/worldbook/worldbook.json" in names and
          "characters/和纱/memory/记忆书.txt" in names, names[:6])
    check("跳过 .bak", not any(n.endswith(".bak") for n in names))
    check("不带素材（立绘不进 zip）", not any(n.endswith(".png") for n in names))
    check("默认不带对话存档", not any("/sessions/" in n for n in names))
    check("脱敏：zip 里没有 sk- 原文", "sk-abcdef123456" not in blob)
    check("manifest 标明不含对话", man1.get("include_dialogue") is False,
          man1.get("include_dialogue"))
    check("manifest 有角色清单", [c["id"] for c in man1.get("characters") or []]
          == ["和纱", "新角色"], man1.get("characters"))

    # ---------- 导出：含对话
    e2 = C.export(turns=20, out_dir=out, root=d["chars"], chars=["和纱"],
                  log_dir=d["logs"])
    with zipfile.ZipFile(e2["path"]) as zf2:
        names2 = zf2.namelist()
        man = json.loads(zf2.read("manifest.json").decode("utf-8"))
    check("带对话时包含 sessions", any("/sessions/" in n for n in names2), names2[:6])
    check("manifest 标明含对话", man.get("include_dialogue") is True, man.get("include_dialogue"))

    # ---------- 删角色：三种拒绝
    r = C.remove_character("新角色", "写错了", root=d["chars"], cache_dir=d["cache"],
                           active="和纱")
    check("confirm 不对被拒", r.get("ok") is False and "确认名不对" in r.get("error", ""),
          r.get("error"))
    r = C.remove_character("和纱", "和纱", root=d["chars"], cache_dir=d["cache"], active="和纱")
    check("当前角色不能删", r.get("ok") is False and "正在用" in r.get("error", ""), r.get("error"))
    r = C.remove_character("../偷", "x", root=d["chars"], cache_dir=d["cache"], active="和纱")
    check("id 带 .. 被拒", r.get("ok") is False, r.get("error"))
    r = C.remove_character("不存在的角色", "不存在的角色", root=d["chars"], cache_dir=d["cache"],
                           active="和纱")
    check("不存在的角色被拒", r.get("ok") is False and "没有这个角色" in r.get("error", ""),
          r.get("error"))

    # ---------- 删角色：成功路径
    sessions_before = os.path.getsize(os.path.join(d["chars"], "新角色", "sessions", "2.json"))
    r = C.remove_character("新角色", "雪菜", root=d["chars"], cache_dir=d["cache"], active="和纱")
    check("按角色名确认后能删", r.get("ok") is True, r.get("error"))
    check("原目录没了", not os.path.isdir(os.path.join(d["chars"], "新角色")))
    moved = r.get("moved_to") or ""
    check("挪进 characters/_deleted/", "_deleted" in moved and os.path.isdir(moved), moved)
    check("挪走的是整个文件夹（存档也在）",
          os.path.exists(os.path.join(moved, "sessions", "2.json")))
    check("存档字节没变", os.path.getsize(os.path.join(moved, "sessions", "2.json")) == sessions_before)
    check("cache/<角色>/ 被清掉", not os.path.isdir(os.path.join(d["cache"], "新角色")))
    check("另一个角色没动", os.path.isdir(os.path.join(d["chars"], "和纱")))
    check("返回可读的撤回提示", "撤回" in (r.get("note") or ""))

    shutil.rmtree(base, ignore_errors=True)
    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), " / ".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
