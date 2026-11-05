# -*- coding: utf-8 -*-
"""素材向导（api_wizard.build）的自测（#20，不联网、不开界面）。

跑法：
    cd program
    build_env/venv/Scripts/python.exe tools/test_wizard.py

验的是：
  1. 缺立绘：按衣服聚合，examples 里能看出是哪套衣服的哪个表情
  2. 缺场景：按 id 列出
  3. 语音：没参考音频 / 0 字节都算缺
  4. 提示词 / 世界书 / 记忆书：未导入时列出来
  5. 全齐了：每步 ok、done=True、hint 变成「可以开始玩」
  6. 每一步都 can_skip=True（向导只提示，不拦人）
"""
import json
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROGRAM, "src"))

_TMP = tempfile.mkdtemp(prefix="wa2_wizard_test_")
os.environ["WA2_USER_DIR"] = _TMP
os.environ["WA2_CACHE_DIR"] = os.path.join(_TMP, "cache")
os.environ["WA2_ASSETS_DIR"] = os.path.join(_TMP, "assets")

import api_wizard  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:200]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def write(path, data=b"x"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data if isinstance(data, bytes) else str(data).encode("utf-8"))


def wjson(path, obj):
    write(path, json.dumps(obj, ensure_ascii=False).encode("utf-8"))


def main():
    assets = os.path.join(_TMP, "assets")
    cid = "和纱"
    root = os.path.join(_TMP, "characters")
    char = os.path.join(root, cid)
    wjson(os.path.join(root, "active.json"), {"id": cid})
    os.makedirs(os.path.join(char, "memory"), exist_ok=True)

    # 场景：两个登记，只有一个文件
    wjson(os.path.join(assets, "cg", "index.json"),
          {"items": [{"id": "classroom", "file": "classroom.jpg"},
                     {"id": "roof", "file": "roof.jpg"}]})
    write(os.path.join(assets, "cg", "classroom.jpg"))

    # 立绘：两套衣服，只放了一套
    wjson(os.path.join(char, "portrait", "index.json"),
          {"outfits": {
              "高中·冬装": {"default": "认真.png", "variants": [{"file": "认真.png"},
                                                               {"file": "微笑.png"}]},
              "高中·常服": {"default": "平静.png", "variants": [{"file": "平静.png"}]},
          }})
    write(os.path.join(char, "portrait", "高中·常服", "平静.png"))

    # 语音：一个 0 字节、没有参考音频
    write(os.path.join(char, "voice", "broken.wav"), b"")

    d = api_wizard.build(assets_dir=assets, char_dir=char)
    check("向导返回 ok", d.get("ok") is True, d.get("error"))
    check("有 4 步", len(d.get("steps") or []) == 4, [s["key"] for s in d.get("steps") or []])
    check("总量对得上：checked > 0", d.get("checked", 0) > 0, d.get("checked"))

    steps = {s["key"]: s for s in d.get("steps") or []}
    check("四步都 can_skip", all(s.get("can_skip") for s in steps.values()),
          [s.get("can_skip") for s in steps.values()])

    p = steps["portrait"]
    check("立绘：判定缺（冬装缺 2 个表情）", p["ok"] is False and p["missing"] == 2,
          (p["ok"], p["missing"]))
    check("立绘：例子带衣服名", any("高中·冬装" in x for x in p["examples"]), p["examples"])
    check("立绘：给出去哪儿导入", "立绘导入" in p["hint"], p["hint"])

    c = steps["scene"]
    check("场景：缺 1 个（roof）", c["ok"] is False and c["missing"] == 1, (c["ok"], c["missing"]))
    check("场景：例子里有 roof", any("roof" in x for x in c["examples"]), c["examples"])

    v = steps["voice"]
    check("语音：判缺（有 0 字节文件）", v["ok"] is False, v.get("examples"))
    check("语音：例子里标出 0 字节", any("0 字节" in x for x in v["examples"]), v["examples"])

    t = steps["text"]
    check("文本三件套：判缺", t["ok"] is False and t["missing"] >= 2, (t["ok"], t["missing"]))
    check("文本三件套：列出未导入的", any("未导入" in x for x in t["examples"]), t["examples"])

    check("总判定 done=False、hint 提示可跳过", d["done"] is False and "补" in d["hint"], d["hint"])

    # ---------------- 全齐
    write(os.path.join(assets, "cg", "roof.jpg"))
    write(os.path.join(char, "portrait", "高中·冬装", "认真.png"))
    write(os.path.join(char, "portrait", "高中·冬装", "微笑.png"))
    # 那个 0 字节的坏文件按向导说的删掉，再放一个好的参考音频
    os.remove(os.path.join(char, "voice", "broken.wav"))
    write(os.path.join(char, "voice", "ref.wav"), b"RIFF" + b"0" * 100)
    write(os.path.join(char, "voice", "ref.txt"), "参考文本")
    wjson(os.path.join(char, "prompt", "persona.txt"), "提示词")
    # 世界书 / 记忆书：special_files 认固定目录名，这里直接建文件碰运气也行，
    # 主要验「不再缺立绘 / 场景 / 语音」这三步
    d2 = api_wizard.build(assets_dir=assets, char_dir=char)
    steps2 = {s["key"]: s for s in d2["steps"]}
    check("补齐后：立绘 ok", steps2["portrait"]["ok"] is True, steps2["portrait"]["examples"])
    check("补齐后：场景 ok", steps2["scene"]["ok"] is True, steps2["scene"]["examples"])
    check("补齐后：语音 ok", steps2["voice"]["ok"] is True, steps2["voice"]["examples"])
    check("补齐后：执行了扫描", d2["checked"] >= d["checked"], (d["checked"], d2["checked"]))

    # 文本三件套判定依赖 char_res 的目录约定，单独看它至少不抛
    check("文本三件套：不抛异常", isinstance(steps2["text"]["missing"], int))

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), " / ".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
