# -*- coding: utf-8 -*-
"""#23 自测：聊天导出（脱敏 / 只导她的话 / 两种格式）+ 首次自检清单。

    cd program && .\\build_env\\venv\\Scripts\\python.exe tools\\test_export.py
"""
import io
import json
import os
import shutil
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROGRAM, "src"))

TMP = tempfile.mkdtemp(prefix="wa2_export_")
os.environ["WA2_USER_DIR"] = TMP
os.environ.pop("WA2_SESS_DIR", None)

import characters  # noqa: E402
import sessions  # noqa: E402
import api_export  # noqa: E402
import firstrun  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:220]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def seed_char():
    cid = None
    try:
        r = characters.create("小雪")
        cid = (r or {}).get("id") if isinstance(r, dict) else r
    except Exception:
        cid = None
    root = characters.root()
    os.makedirs(root, exist_ok=True)
    if not cid:
        cid = "小雪"
        d = os.path.join(root, cid)
        os.makedirs(os.path.join(d, "prompt"), exist_ok=True)
        os.makedirs(os.path.join(d, "sessions"), exist_ok=True)
        with io.open(os.path.join(d, "name.txt"), "w", encoding="utf-8") as f:
            f.write("小雪")
        with io.open(os.path.join(d, "prompt", "base.txt"), "w", encoding="utf-8") as f:
            f.write("你是小雪。")
    characters.switch(cid)
    # 不管 create() 有没有铺模板，测试都要一个「能跑」的角色：
    d = os.path.join(characters.root(), cid)
    os.makedirs(os.path.join(d, "prompt"), exist_ok=True)
    os.makedirs(os.path.join(d, "sessions"), exist_ok=True)
    base = os.path.join(d, "prompt", "base.txt")
    if not os.path.isfile(base) or os.path.getsize(base) == 0:
        with io.open(base, "w", encoding="utf-8") as f:
            f.write("你是小雪。")
    # sessions.py 的目录是模块级常量（WA2_SESS_DIR 在 import 时就定了），
    # 测试里直接改到临时角色目录，别碰到真实存档
    sessions.SESS_DIR = os.path.join(d, "sessions")
    return cid


def write_save(cid, slot, messages):
    d = os.path.join(characters.root(), cid, "sessions")
    os.makedirs(d, exist_ok=True)
    payload = {"schema_version": 1, "messages": messages,
               "meta": {"bg": "cg_001", "outfit": "校服"}}
    with io.open(os.path.join(d, "%s.json" % slot), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)


def main():
    print("[1] 脱敏：密钥与本机路径")
    raw_key = "sk-abcdefghijklmnopqrstuvwxyz123456"
    s, n = api_export.clean("我的 key 是 %s 别乱传" % raw_key, True)
    check("密钥被抹掉", raw_key not in s, s)
    check("记了一处脱敏", n >= 1, n)
    s2, n2 = api_export.clean(r"存档在 E:\游戏\存档\1.json 里", True)
    check("盘符路径被抹掉", "E:\\" not in s2 and "游戏" not in s2, s2)
    check("路径脱敏也计数", n2 >= 1, n2)
    s3, n3 = api_export.clean(r"E:\游戏\x.json", False)
    check("关掉脱敏就原样保留", s3 == r"E:\游戏\x.json" and n3 == 0, (s3, n3))

    print("[2] 渲染：Markdown / 纯文本 / 只导她的话")
    msgs = [
        {"role": "user", "content": "晚上好"},
        {"role": "assistant", "zh": "……嗯。", "emo": "毒舌"},
        {"role": "user", "content": "今天很冷"},
        {"role": "assistant", "zh": "关我什么事。", "emo": "calm"},
        {"role": "assistant", "zh": "（把热水放在你手边）", "emo": "soft"},
    ]
    md, st = api_export.render(msgs, "md", True)
    check("标题带角色名", md.startswith("# "), md[:30])
    check("有导出时间与句数", "导出于" in md and "共 5 句" in md, md[:200])
    check("统计对上", st["lines"] == 5 and st["her"] == 3 and st["mine"] == 2, st)
    check("她的台词带情绪标签", "（毒舌）" in md, md)
    check("你的台词用「你」开头", "**你**：晚上好" in md, md)

    md2, st2 = api_export.render(msgs, "md", True, only_reply=True)
    check("只导她的话：句数变 3", st2["lines"] == 3 and st2["mine"] == 0, st2)
    check("只导她的话：没有「你」", "**你**" not in md2, md2)

    txt, st3 = api_export.render(msgs, "txt", True)
    check("纯文本没有 ** 标记", "**" not in txt, txt[:60])
    check("纯文本也有她的话", "关我什么事" in txt)

    print("[3] 端到端：从存档导出")
    cid = seed_char()
    write_save(cid, "1", msgs)
    r = api_export.export(slot="1", fmt="md", do_redact=True, preview=True)
    check("预览成功", r.get("ok"), r)
    check("预览带统计", r.get("lines") == 5 and r.get("chars", 0) > 0, r)
    check("预览不含全文（截断标记）", r.get("preview") and len(r["preview"]) <= 800, len(r.get("preview") or ""))
    r2 = api_export.export(slot="1", fmt="md", do_redact=True)
    check("全文导出成功", r2.get("ok") and "关我什么事" in r2.get("text", ""), r2.get("filename"))
    check("文件名带角色与日期", r2.get("filename", "").endswith(".md") and "小雪" in r2["filename"],
          r2.get("filename"))
    check("空档报错不抛异常", api_export.export(slot="99").get("ok") is False)

    print("[4] 首次自检清单")
    st4 = firstrun.state()
    keys = [i["key"] for i in st4.get("items") or []]
    check("五项都在", keys == ["model", "character", "voice", "assets", "save"], keys)
    check("有 ready / all_ok", "ready" in st4 and "all_ok" in st4, list(st4))
    check("audio/素材是可选项",
          all(i["optional"] for i in st4["items"] if i["key"] in ("voice", "assets", "save")),
          [(i["key"], i["optional"]) for i in st4["items"]])
    check("角色项认得当前角色",
          [i for i in st4["items"] if i["key"] == "character"][0]["ok"] is True,
          [i for i in st4["items"] if i["key"] == "character"])
    check("每项都有标题与说明",
          all(i.get("title") and i.get("detail") is not None for i in st4["items"]))

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), "、".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
