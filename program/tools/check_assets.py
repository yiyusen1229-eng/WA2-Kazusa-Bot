# -*- coding: utf-8 -*-
"""素材自检：告诉你缺什么、放哪里、怎么拿

用法：
    python tools/check_assets.py
    python tools/check_assets.py --json      # 机器可读

退出码：
    0  全部就绪
    1  有缺失
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (相对路径, 类型, 是否必需, 获取方式)
ITEMS = [
    # ---- 界面素材 ----
    ("ui2/assets/sprites/index.json", "file", True,
     "游戏解包：立绘索引（随立绘一起产出）"),
    ("ui2/assets/sprites", "dir", True,
     "游戏解包：278 张立绘 PNG，放 ui2/assets/sprites/<服装>/"),
    ("ui2/assets/ui", "dir", True,
     "游戏解包 + 汉化补丁：UI 图集切图（对话框、按钮、箭头）"),
    ("ui2/assets/menu", "dir", True,
     "游戏解包：主菜单五项的两态图"),
    ("ui2/assets/tb", "dir", True,
     "游戏解包：工具栏按钮"),
    ("ui2/assets/tb2", "dir", True,
     "游戏解包：工具栏按钮（第二套）"),
    ("ui2/assets/title.png", "file", True,
     "游戏解包：标题画面背景"),
    ("ui2/assets/ui_logo.png", "file", True,
     "游戏解包：WHITE ALBUM 2 标志"),
    ("ui2/assets/bgm_calm.ogg", "file", False,
     "游戏解包：BGM（缺了没声音，但程序能跑）"),
    ("ui2/assets/snd", "dir", False,
     "游戏解包：音效与 BGM"),

    # ---- 字体 ----
    ("app/assets/subfont.tga", "file", True,
     "汉化补丁：891 字形图集（gcn.pak 解包得到）"),
    ("app/assets/subfont_charset.json", "file", True,
     "汉化补丁：字形映射表"),
    ("app/assets/字体映射表.json", "file", True,
     "汉化补丁：全角/半角与异体字映射"),

    # ---- 剧本索引 ----
    ("app/story_index.json", "file", False,
     "本地构建：python tools/build_story_index.py（需要剧本）"),

    # ---- 配置 ----
    ("最新版/config.json", "file", False,
     "复制 config.example.json 再填自己的 API key"),

    # ---- 模型（只有想跑本地对话才需要）----
    ("train/models/Qwen2.5-14B-Instruct", "dir", False,
     "python tools/setup_assets.py --model 14b"),
    ("tts/GPT-SoVITS", "dir", False,
     "python tools/setup_assets.py --tts"),
    ("tts/models/Hy-MT2-1.8B-Q4_K_M.gguf", "file", False,
     "自行下载 Hy-MT2-1.8B 的 GGUF 量化版"),

    # ---- 语音语料（只有想重训 TTS 才需要）----
    ("语音训练集", "dir", False,
     "游戏解包：和纱语音 + 标注清单"),
]


def check():
    rows = []
    for rel, kind, required, hint in ITEMS:
        path = os.path.join(ROOT, rel)
        if kind == "dir":
            ok = os.path.isdir(path) and bool(os.listdir(path)) if os.path.isdir(path) else False
        else:
            ok = os.path.isfile(path)
        rows.append({
            "path": rel,
            "kind": kind,
            "required": required,
            "present": ok,
            "hint": hint,
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    rows = check()
    missing_req = [r for r in rows if r["required"] and not r["present"]]
    missing_opt = [r for r in rows if not r["required"] and not r["present"]]
    ok = [r for r in rows if r["present"]]

    if args.json:
        print(json.dumps({
            "ready": not missing_req,
            "ok": rows,
            "missing_required": missing_req,
            "missing_optional": missing_opt,
        }, ensure_ascii=False, indent=2))
        return 0 if not missing_req else 1

    print("=" * 72)
    print(" 素材自检  (根目录: %s)" % ROOT)
    print("=" * 72)

    print("\n[已就绪] %d 项" % len(ok))
    for r in ok:
        print("  ✓ %s" % r["path"])

    if missing_req:
        print("\n[缺少 · 必需] %d 项 —— 不补齐程序起不来" % len(missing_req))
        for r in missing_req:
            print("  ✗ %s" % r["path"])
            print("      获取方式：%s" % r["hint"])

    if missing_opt:
        print("\n[缺少 · 可选] %d 项 —— 缺了仍能跑，但对应功能不可用" % len(missing_opt))
        for r in missing_opt:
            print("  ○ %s" % r["path"])
            print("      获取方式：%s" % r["hint"])

    print("\n" + "-" * 72)
    if missing_req:
        print(" 结论：还不能运行。缺 %d 项必需素材，见 docs/本地素材获取指南.md" % len(missing_req))
        return 1
    print(" 结论：必需素材齐全，可以运行。")
    if missing_opt:
        print("       另有 %d 项可选素材缺失（语音、翻译、本地模型会不可用）" % len(missing_opt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
