# -*- coding: utf-8 -*-
"""记忆书查看 / 删除的自测（不联网、不开界面）。

跑法：
    cd program
    build_env/venv/Scripts/python.exe tools/test_memory_view.py

验的是：
  1. view() 把运行时条目按 kind 翻成中文标签，常驻记忆书一起带出来
  2. delete() 删掉指定条目并落盘；删完索引重新编号
  3. 越界 / 非法索引有明确报错，且不会把别的条目删掉
  4. 没有条目时给「还没有自动摘要」的提示
"""
import json
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROGRAM, "src"))

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


def main():
    tmp = tempfile.mkdtemp(prefix="wa2_memview_")
    os.environ["WA2_USER_DIR"] = tmp
    os.environ["WA2_CACHE_DIR"] = os.path.join(tmp, "cache")
    os.environ.pop("WA2_SESS_DIR", None)

    # 造一个角色 + 常驻记忆书
    write(os.path.join(tmp, "characters", "active.json"), '{"id": "A"}')
    write(os.path.join(tmp, "characters", "A", "name.txt"), "甲")
    write(os.path.join(tmp, "characters", "A", "memory", "standing.txt"), "她喜欢冬天。")

    import memory      # noqa: E402
    import api_memory  # noqa: E402

    print("== 1. 空记忆书 ==")
    v = api_memory.view()
    check("view ok", v.get("ok") is True, v)
    check("没有条目", v.get("count") == 0, v)
    check("有提示语", "自动摘要" in (v.get("hint") or ""), v.get("hint"))
    check("常驻记忆书读到了", "她喜欢冬天" in (v.get("standing") or {}).get("text", ""), v.get("standing"))
    check("常驻字数对得上", (v.get("standing") or {}).get("chars") == 6, v.get("standing"))

    print("== 2. 有条目 ==")
    memory.runtime_set(entries=[
        {"text": "她讨厌被人迟到", "kind": "preference", "from": [0, 4]},
        {"text": "上周一起去了咖啡厅", "kind": "event", "from": [4, 9]},
        {"text": "关系已经确认", "kind": "progress", "from": [9, 12]},
    ], covered=12, turns=3)
    v = api_memory.view()
    check("三条都在", v.get("count") == 3, v.get("count"))
    labels = [e["label"] for e in v["entries"]]
    check("标签翻成中文", labels == ["偏好", "事件", "进度"], labels)
    check("covered 带出来", v.get("covered") == 12, v.get("covered"))
    check("没有提示语了", not (v.get("hint") or ""), v.get("hint"))

    print("== 3. 删除 ==")
    r = api_memory.delete(1)
    check("删成功", r.get("ok") is True, r)
    check("剩两条", r.get("left") == 2, r)
    check("返回被删的文本", r.get("text") == "上周一起去了咖啡厅", r.get("text"))
    v = api_memory.view()
    texts = [e["text"] for e in v["entries"]]
    check("删的是第 1 条", texts == ["她讨厌被人迟到", "关系已经确认"], texts)
    check("索引重新编号", [e["i"] for e in v["entries"]] == [0, 1], v["entries"])

    print("== 4. 落盘 ==")
    saved = json.load(open(os.path.join(tmp, "cache", "memory_runtime.json"), encoding="utf-8"))
    check("文件里也少了一条", len(saved.get("entries") or []) == 2, saved.get("entries"))

    print("== 5. 非法索引 ==")
    check("越界报错", api_memory.delete(99).get("ok") is False)
    check("负数报错", api_memory.delete(-1).get("ok") is False)
    check("非数字报错", api_memory.delete("x").get("ok") is False)
    check("None 报错", api_memory.delete(None).get("ok") is False)
    v = api_memory.view()
    check("没误删", v.get("count") == 2, v.get("count"))

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), ", ".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
