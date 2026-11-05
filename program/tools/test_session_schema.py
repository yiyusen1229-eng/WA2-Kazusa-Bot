# -*- coding: utf-8 -*-
"""存档 schema 版本化的自测（不联网、不开界面）。

跑法：
    cd program
    build_env/venv/Scripts/python.exe tools/test_session_schema.py

验的是：
  1. 新存档带 schema_version
  2. 存取往返不丢内容
  3. 老档（没有版本号）→ 迁移到当前版本，原档留 .v0.bak，文件被写回
  4. 比程序新的存档 → 拒绝读取（save_too_new），且文件一个字节都不动
  5. 坏档（不是 JSON / messages 不是数组）→ corrupt，不抛异常
  6. 列表里标出 incompatible
  7. 缩略图照旧能取
"""
import json
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROGRAM, "src"))

SESS_DIR = tempfile.mkdtemp(prefix="wa2_sess_test_")
os.environ["WA2_SESS_DIR"] = SESS_DIR

import sessions  # noqa: E402  （必须在设好 WA2_SESS_DIR 之后导入）

FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:300]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def path_of(slot):
    return os.path.join(SESS_DIR, slot + ".json")


def write_raw(slot, text):
    with open(path_of(slot), "w", encoding="utf-8") as f:
        f.write(text)


def read_raw(slot):
    with open(path_of(slot), encoding="utf-8") as f:
        return f.read()


def main():
    print("SESS_DIR =", SESS_DIR)

    # 1. 新存档带版本号
    r = sessions.session_save({"slot": "auto", "messages": [
        {"role": "user", "content": "こんばんは"},
        {"role": "assistant", "content": "…うん", "zh": "……嗯"},
    ], "meta": {"bg": "classroom"}})
    check("保存成功", r.get("ok") is True, r)
    check("返回带 schema_version", r.get("schema_version") == sessions.SCHEMA_VERSION, r)
    raw = json.loads(read_raw("auto"))
    check("文件里有 schema_version", raw.get("schema_version") == sessions.SCHEMA_VERSION, raw.get("schema_version"))
    check("没有残留 .tmp", not os.path.exists(path_of("auto") + ".tmp"))

    # 2. 往返
    d = sessions.session_load("auto")
    check("读档成功", d.get("ok") is True, d)
    check("消息条数一致", len(d.get("messages") or []) == 2, len(d.get("messages") or []))
    check("内容不丢", (d["messages"][1].get("zh") == "……嗯"), d.get("messages"))
    check("meta 不丢", (d.get("meta") or {}).get("bg") == "classroom", d.get("meta"))
    check("当前版本不触发迁移", "migrated_from" not in d, d.get("migrated_from"))

    # 3. 老档（没有版本号）
    old = {"slot": "old", "saved_at": "2026-01-01 00:00:00",
           "messages": [{"role": "user", "content": "老存档"}], "meta": {}}
    write_raw("old", json.dumps(old, ensure_ascii=False))
    d = sessions.session_load("old")
    check("老档能读", d.get("ok") is True, d)
    check("标出迁移来源 v0", d.get("migrated_from") == 0, d.get("migrated_from"))
    check("迁移后消息还在", (d.get("messages") or [{}])[0].get("content") == "老存档", d.get("messages"))
    check("原档备份存在", os.path.exists(path_of("old") + ".v0.bak"))
    raw = json.loads(read_raw("old"))
    check("迁移结果写回文件", raw.get("schema_version") == sessions.SCHEMA_VERSION, raw.get("schema_version"))
    d2 = sessions.session_load("old")
    check("第二次读不再迁移", "migrated_from" not in d2, d2.get("migrated_from"))

    # 4. 比程序新的存档
    future = {"schema_version": sessions.SCHEMA_VERSION + 5, "slot": "future",
              "messages": [{"role": "user", "content": "未来"}], "meta": {}}
    write_raw("future", json.dumps(future, ensure_ascii=False))
    before = read_raw("future")
    d = sessions.session_load("future")
    check("未来版本被拒绝", d.get("ok") is False and d.get("error") == "save_too_new", d)
    check("拒绝时带上版本信息", d.get("schema_version") == sessions.SCHEMA_VERSION + 5, d)
    check("拒绝时不改文件", read_raw("future") == before)

    # 5. 坏档
    write_raw("broken", "{not json")
    d = sessions.session_load("broken")
    check("坏 JSON → corrupt", d.get("ok") is False and d.get("error") == "corrupt", d)

    write_raw("badmsgs", json.dumps({"schema_version": 1, "messages": "oops"}, ensure_ascii=False))
    d = sessions.session_load("badmsgs")
    check("messages 不是数组 → corrupt", d.get("ok") is False and d.get("error") == "corrupt", d)

    write_raw("baditem", json.dumps({"schema_version": 1, "messages": ["x"]}, ensure_ascii=False))
    d = sessions.session_load("baditem")
    check("消息不是对象 → corrupt", d.get("ok") is False and d.get("error") == "corrupt", d)

    d = sessions.session_load("nope")
    check("不存在的槽位有明确报错", d.get("ok") is False and "no such slot" in str(d.get("error")), d)

    # 6. 列表
    lst = sessions.session_list()
    check("列表成功", lst.get("ok") is True, lst)
    by = {x["slot"]: x for x in lst.get("slots", [])}
    check("列表带 schema_version", by.get("auto", {}).get("schema_version") == sessions.SCHEMA_VERSION, by.get("auto"))
    check("未来版本标 incompatible", by.get("future", {}).get("incompatible") is True, by.get("future"))
    check("当前版本不标 incompatible", by.get("auto", {}).get("incompatible") is False, by.get("auto"))
    check("坏档不进列表", "broken" not in by and "badmsgs" not in by, list(by))

    # 7. 缩略图
    thumb = "data:image/jpeg;base64," + __import__("base64").b64encode(b"\xff\xd8\xff\xd9").decode()
    sessions.session_save({"slot": "thumb", "messages": [{"role": "user", "content": "x"}],
                           "meta": {"thumb": thumb}})
    data = sessions.session_thumb("thumb")
    check("缩略图能取", data == b"\xff\xd8\xff\xd9", data)
    check("没缩略图返回 None", sessions.session_thumb("auto") is None)

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), " / ".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
