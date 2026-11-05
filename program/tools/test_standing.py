# -*- coding: utf-8 -*-
"""常驻记忆书两段化（standing.py）的自测（#3，不联网、不开界面）。

跑法：
    cd program
    build_env/venv/Scripts/python.exe tools/test_standing.py

验的是：
  1. 没有 standing.json → 回落老的 memory/*.txt（注入行为不变）
  2. 第一次刷新：fixed 从 memory/*.txt 抄一份，关系摘要写进去，带阶段 / 时间
  3. **fixed 是用户的**：程序再刷多少次也不改它
  4. 每个阶段最多刷一次：note() 同阶段返回 False，换阶段才 True
  5. note() 不阻塞：模型慢慢返回，note() 立刻返回
  6. 刷新失败（模型抛错 / 返回空）→ 保留旧版，不写坏文件
  7. 模型输出会被收拾成 3~6 行、每行 ≤80 字、总共 ≤600 字
  8. 坏 json → 回落到老文本，不炸；没有 LLM → 什么都不做
"""
import json
import os
import sys
import tempfile
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROGRAM, "src"))

_TMP = tempfile.mkdtemp(prefix="wa2_standing_test_")
os.environ["WA2_USER_DIR"] = _TMP
os.environ["WA2_CACHE_DIR"] = os.path.join(_TMP, "cache")
os.environ["WA2_SESS_DIR"] = os.path.join(_TMP, "sessions")

import characters  # noqa: E402
import standing    # noqa: E402

FAILS = []
FIXED_TEXT = "固定设定：和纱是钢琴专业的，性格冷，习惯用「」说话。"


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:200]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def make_char():
    root = os.path.join(_TMP, "characters")
    cid = "和纱"
    d = os.path.join(root, cid)
    os.makedirs(os.path.join(d, "memory"), exist_ok=True)
    with open(os.path.join(root, "active.json"), "w", encoding="utf-8") as f:
        json.dump({"id": cid}, f, ensure_ascii=False)
    with open(os.path.join(d, "name.txt"), "w", encoding="utf-8") as f:
        f.write(cid)
    with open(os.path.join(d, "memory", "记忆书.txt"), "w", encoding="utf-8") as f:
        f.write(FIXED_TEXT)
    return d


def msgs(n=6):
    out = []
    for i in range(n):
        out.append({"role": "user", "content": "第 %d 句：今天也一起练琴吧" % i})
        out.append({"role": "assistant", "content": "「嗯……好。」"})
    return out


def read(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main():
    d = make_char()
    p = standing.path()
    check("standing.json 落在角色 memory/ 下", p.startswith(d) and p.endswith("standing.json"), p)

    # 1) 没有文件 → 回落老文本
    check("没有 standing.json：load 返回 None", standing.load() is None)
    old_text = standing.text()
    check("没有 standing.json：text() 回落 memory/*.txt", FIXED_TEXT in old_text, old_text[:60])
    st0 = standing.status()
    check("status 说还没有两段化", st0["exists"] is False and "hint" in st0, st0)

    # 2) 第一次刷新
    calls = []

    def fake_llm(prompt):
        calls.append(prompt)
        return "- 刚开始一起练琴\n- 她还是嘴硬\n- 约好了下次再合奏"

    standing.set_llm(fake_llm)
    got = standing.build(msgs(), 2)
    check("build 写出 standing.json", got is not None and os.path.isfile(p), got)
    saved = read(p)
    check("fixed 从 memory/*.txt 抄过来了", FIXED_TEXT in saved.get("fixed", ""), saved.get("fixed", "")[:40])
    check("关系摘要写进去了", "- 刚开始一起练琴" in saved.get("relation_summary", ""), saved)
    check("记了阶段", saved.get("stage") == 2, saved.get("stage"))
    check("记了更新时间", bool(saved.get("updated_at")), saved.get("updated_at"))
    check("记了对话条数", saved.get("source_msgs") == len(msgs()), saved.get("source_msgs"))
    check("没有留下 .tmp", not os.path.exists(p + ".tmp"))
    check("prompt 里带了阶段和对话", "当前关系阶段：2" in calls[-1] and "练琴" in calls[-1], calls[-1][:80])
    two = standing.text()
    check("text() 现在有两段", FIXED_TEXT in two and "【我们之间现在的进展" in two, two[:80])

    # 3) fixed 是用户的
    saved["fixed"] = "用户自己改过的固定设定"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(saved, f, ensure_ascii=False)
    standing.build(msgs(), 3)
    again = read(p)
    check("再刷一次也不改用户的 fixed", again.get("fixed") == "用户自己改过的固定设定", again.get("fixed"))
    check("阶段跟着更新", again.get("stage") == 3, again.get("stage"))

    # 4) 每个阶段最多一次
    check("同阶段不再刷新", standing.note(3, msgs()) is False)
    before = read(p)
    hit = standing.note(4, msgs())
    check("换阶段会刷新", hit is True, hit)
    standing.wait()
    after = read(p)
    check("换阶段后文件真的更新了", after.get("stage") == 4, after.get("stage"))
    check("刷新确实动了内容", after.get("updated_at") >= before.get("updated_at"),
          (before.get("updated_at"), after.get("updated_at")))

    # 5) note() 不阻塞
    def slow_llm(prompt):
        time.sleep(0.4)
        return "- 慢慢来"

    standing.set_llm(slow_llm)
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "fixed": "x", "relation_summary": "", "stage": 1,
                   "updated_at": "", "source_msgs": 0}, f, ensure_ascii=False)
    t0 = time.time()
    hit = standing.note(2, msgs())
    dt = time.time() - t0
    check("note() 立刻返回（不等模型）", hit is True and dt < 0.2, (hit, round(dt, 3)))
    check("后台还在跑", standing.wait(3) is True)

    # 6) 失败保留旧版
    old = read(p)
    old_summary = old.get("relation_summary")

    def boom(prompt):
        raise TimeoutError("模拟超时")

    standing.set_llm(boom)
    check("模型抛错：build 返回 None", standing.build(msgs(), 5) is None)
    check("模型抛错：旧文件没被写坏", read(p) == old, read(p).get("relation_summary"))

    standing.set_llm(lambda prompt: "")
    check("模型返回空：build 返回 None", standing.build(msgs(), 6) is None)
    check("模型返回空：旧文件没变", read(p).get("relation_summary") == old_summary)

    # 7) 输出收拾
    standing.set_llm(lambda prompt: "\n".join([
        "- 第一行" + "长" * 100,
        "· 第二行",
        "* 第三行",
        "第四行没有前缀",
        "- 第五行", "- 第六行", "- 第七行", "- 第八行",
    ]))
    cleaned = standing.build(msgs(), 7)
    check("清理后最多 6 行", cleaned and len(cleaned["relation_summary"].splitlines()) <= 6,
          (cleaned or {}).get("relation_summary"))
    lines = (cleaned or {}).get("relation_summary", "").splitlines()
    check("每行都有 - 前缀", all(l.startswith("- ") for l in lines), lines)
    check("每行 ≤80 字", all(len(l) <= 82 for l in lines), [len(l) for l in lines])
    check("总长 ≤600", len((cleaned or {}).get("relation_summary", "")) <= 600,
          len((cleaned or {}).get("relation_summary", "")))
    check("超长行被截断", any(len(l) < 110 for l in lines) and len(lines) >= 5, lines[:2])

    # 阶段 1 不生成；失败后同阶段冷却
    os.remove(p)
    standing.set_llm(fake_llm)
    standing._TRY.update({"stage": 0, "at": 0.0, "ok": False})
    check("阶段 1 且没有文件：不生成", standing.note(1, msgs()) is False)
    check("确实没写文件", not os.path.isfile(p))
    check("到阶段 2 才生成", standing.note(2, msgs()) is True)
    standing.wait()
    check("阶段 2 生成成功", os.path.isfile(p) and read(p).get("stage") == 2)

    os.remove(p)
    standing.set_llm(boom)
    standing._TRY.update({"stage": 0, "at": 0.0, "ok": False})
    check("失败也会触发一次", standing.note(3, msgs()) is True)
    standing.wait()
    check("失败后同阶段不再立刻重试（冷却）", standing.note(3, msgs()) is False)
    check("换阶段不受冷却影响", standing.note(4, msgs()) is True)
    standing.wait()

    # 8) 坏 json / 没有 LLM
    with open(p, "w", encoding="utf-8") as f:
        f.write("{ 这不是 json")
    check("坏 json：load 返回 None", standing.load() is None)
    check("坏 json：text() 回落老文本", FIXED_TEXT in standing.text())
    check("坏 json：status 说没有两段化", standing.status()["exists"] is False)

    standing.set_llm(None)
    check("没有 LLM：note 返回 False", standing.note(9, msgs()) is False)
    check("没有 LLM：build 返回 None", standing.build(msgs(), 9) is None)

    # 没有 active.json 时 characters 会自动建一个默认角色（不是崩溃，也不是空路径）
    os.remove(os.path.join(_TMP, "characters", "active.json"))
    check("没有当前角色：会自动建默认角色（不是空路径）", bool(standing.path()), standing.path())
    check("自动建出来的角色：load/text/status 都不炸",
          standing.load() is None and isinstance(standing.text(), str)
          and standing.status()["exists"] is False)

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), " / ".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
