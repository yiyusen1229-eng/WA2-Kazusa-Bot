# -*- coding: utf-8 -*-
"""立绘索引的自测：没写 index.json 的老角色包要能照目录扫出来。

为什么单独测：2026-11-06 用户反馈「立绘基本没换过」。查下来是角色包里
`portrait/` 有 14 套衣服目录、但**没有 index.json**，`sprite_index()` 返回空，
前端每套衣服都查不到，只能永远退回同一张默认图。
修法是扫目录兜底，这个测试盯着它别再退回去。

跑：
    cd program && .\\build_env\\venv\\Scripts\\python.exe tools\\test_sprite_scan.py
"""
import json
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROGRAM, "src"))

_TMP = tempfile.mkdtemp(prefix="wa2_sprite_scan_")
os.environ["WA2_USER_DIR"] = _TMP
import characters  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:200]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def touch(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"\x89PNGfake")


def main():
    assets = os.path.join(_TMP, "assets")
    os.makedirs(os.path.join(assets, "sprites"), exist_ok=True)   # 自带索引也没有
    char = os.path.join(_TMP, "characters", "测试")
    os.makedirs(os.path.join(char, "portrait"), exist_ok=True)
    with open(os.path.join(_TMP, "characters", "active.json"), "w", encoding="utf-8") as f:
        json.dump({"id": "测试"}, f, ensure_ascii=False)

    # 老角色包：只有「衣服/表情.png」，没有 index.json
    for emo in ("认真", "微笑", "生气", "冷淡", "惊讶", "害羞", "难过"):
        touch(os.path.join(char, "portrait", "常服", emo + ".png"))
    touch(os.path.join(char, "portrait", "礼服", "认真.png"))
    touch(os.path.join(char, "portrait", "礼服", "微笑.png"))
    # 干扰项：非图片文件、空目录
    touch(os.path.join(char, "portrait", "常服", "说明.txt"))
    os.makedirs(os.path.join(char, "portrait", "空目录"), exist_ok=True)

    print("[1] 没有 index.json：照目录扫")
    idx = characters.sprite_index(os.path.join(assets, "sprites"))
    of = idx.get("outfits") or {}
    check("扫出两套衣服", sorted(of) == ["常服", "礼服"], sorted(of))
    check("空目录不算一套", "空目录" not in of, sorted(of))
    emo = (of.get("常服") or {}).get("emotions") or {}
    check("表情名 = 文件名", emo.get("生气") == "生气.png", emo)
    check("非图片文件没混进来", "说明" not in emo, list(emo))
    check("默认脸用「认真」", (of.get("常服") or {}).get("default") == "认真.png",
          (of.get("常服") or {}).get("default"))
    check("label 就是衣服名", (of.get("常服") or {}).get("label") == "常服")

    print("[2] 写了 index.json：文件优先，不扫目录")
    own = os.path.join(char, "portrait", "index.json")
    with open(own, "w", encoding="utf-8") as f:
        json.dump({"outfits": {"自定义": {"code": "027", "label": "自定义",
                                          "default": "认真.png",
                                          "emotions": {"angry": "生气.png"}}}},
                  f, ensure_ascii=False)
    idx2 = characters.sprite_index(os.path.join(assets, "sprites"))
    of2 = idx2.get("outfits") or {}
    check("以 index.json 为准", sorted(of2) == ["自定义"], sorted(of2))
    check("文件里的 emotions 保留", (of2["自定义"].get("emotions") or {}).get("angry") == "生气.png")
    check("code 保留", of2["自定义"].get("code") == "027")

    print("[3] 自带索引 + 角色索引合并（角色优先）")
    with open(os.path.join(assets, "sprites", "index.json"), "w", encoding="utf-8") as f:
        json.dump({"outfits": {"常服": {"code": "027", "label": "常服",
                                        "default": "认真.png",
                                        "emotions": {"serious": "认真.png"}},
                               "自带专用": {"code": "099", "default": "x.png"}}},
                  f, ensure_ascii=False)
    idx3 = characters.sprite_index(os.path.join(assets, "sprites"))
    of3 = idx3.get("outfits") or {}
    check("同 code 合成一条（用角色那份的名字）", "自定义" in of3 and "常服" not in of3, sorted(of3))
    check("自带独有的那套仍在", "自带专用" in of3, sorted(of3))
    check("表情映射两边叠起来", (of3["自定义"].get("emotions") or {}).get("angry") == "生气.png"
          and (of3["自定义"].get("emotions") or {}).get("serious") == "认真.png",
          of3["自定义"].get("emotions"))
    check("合并后 code 还是 027", of3["自定义"].get("code") == "027")

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), "、".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
