# -*- coding: utf-8 -*-
"""素材自检：告诉你缺什么、该放到哪

用法：
    python tools/check_assets.py
    python tools/check_assets.py --json      # 机器可读

退出码：
    0  必需素材齐全
    1  有必需素材缺失

说明：仓库不含任何游戏素材 / 模型权重。这里只检查"该在的位置有没有东西"，
     素材由使用者按自己的合法来源准备。
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # program/
SRC = os.path.join(ROOT, "src")
RES = os.path.join(ROOT, "res", "assets")
ENV = os.path.join(ROOT, "build_env")

# (路径, 类型, 是否必需, 说明)
ITEMS = [
    # ---- 界面素材（res/assets，开发时由 WA2_ASSETS_DIR 指过来）----
    ("res/assets/ui", "dir", True, "界面图集：对话框、按钮、页签、存档界面件"),
    ("res/assets/menu", "dir", True, "主菜单五项的两态图"),
    ("res/assets/tb", "dir", True, "工具栏按钮"),
    ("res/assets/tb2", "dir", True, "工具栏按钮（第二套）"),
    ("res/assets/sprites", "dir", True, "立绘（assets/sprites/<衣服>/ 由特别模式导入）"),
    ("res/assets/title.png", "file", True, "标题画面背景"),
    ("res/assets/ui_logo.png", "file", True, "WHITE ALBUM 2 标志"),
    ("res/assets/cg", "dir", False, "场景背景 CG（tools/import_cg.py 生成）"),
    ("res/assets/snd", "dir", False, "音效与 BGM"),

    # ---- 字模（运行时目录 build_env/assets，打包时随 --add-data assets 一起带走）----
    ("build_env/assets/subfont.tga", "file", True, "891 字形图集（界面所有文字都靠它）"),
    ("build_env/assets/subfont_charset.json", "file", True, "字形映射表"),

    # ---- 人设 / 世界书 / 检索索引 ----
    ("src/persona/base.txt", "file", True, "人设共用底色"),
    ("src/persona/stage1.txt", "file", True, "关系阶段 1（关系初期）"),
    ("src/persona/stage2.txt", "file", True, "关系阶段 2（关系升温）"),
    ("src/persona/stage3.txt", "file", True, "关系阶段 3（关系确认）"),
    ("src/persona/stage4.txt", "file", True, "关系阶段 4（婚后 / 同居）"),
    ("src/worldbook/worldbook.json", "file", True, "世界书（关键词触发）"),
    ("src/story_index.json.gz", "file", False, "剧情检索索引（tools/build_story_index_v2.py 生成）"),

    # ---- 运行时可选项 ----
    ("build_env/config.json", "file", False, "云端 API 配置（复制 config.example.json 再填 key）"),
    ("build_env/characters", "dir", False, "总角色资源文件夹（每个角色一个子文件夹）"),
    ("other/dev/tts/GPT-SoVITS", "dir", False, "本地语音依赖（没有就只有文字）"),
    ("other/dev/dataset/L2_scene.jsonl", "file", False, "剧本场景（重建检索索引用）"),
]


def _abs(rel):
    if rel.startswith("res/"):
        return os.path.join(ROOT, *rel.split("/"))
    if rel.startswith("build_env/"):
        return os.path.join(ROOT, *rel.split("/"))
    if rel.startswith("src/"):
        return os.path.join(ROOT, *rel.split("/"))
    return os.path.join(os.path.dirname(ROOT), *rel.split("/"))   # other/dev/...


def check():
    rows = []
    for rel, kind, required, hint in ITEMS:
        path = _abs(rel)
        if kind == "dir":
            ok = os.path.isdir(path) and bool(os.listdir(path))
        else:
            ok = os.path.isfile(path)
        rows.append({"path": rel, "kind": kind, "required": required,
                     "present": ok, "hint": hint})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()
    rows = check()
    missing_req = [r for r in rows if r["required"] and not r["present"]]
    missing_opt = [r for r in rows if not r["required"] and not r["present"]]

    if args.json:
        print(json.dumps({"ready": not missing_req, "items": rows,
                          "missing_required": missing_req,
                          "missing_optional": missing_opt},
                         ensure_ascii=False, indent=2))
        return 0 if not missing_req else 1

    ok = [r for r in rows if r["present"]]
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
            print("      %s" % r["hint"])
    if missing_opt:
        print("\n[缺少 · 可选] %d 项 —— 缺了仍能跑，只是对应功能不可用" % len(missing_opt))
        for r in missing_opt:
            print("  ○ %s" % r["path"])
            print("      %s" % r["hint"])
    print("\n" + "-" * 72)
    print(" 结论：必需素材齐全，可以运行。" if not missing_req
          else " 结论：还不能运行，缺 %d 项必需素材。" % len(missing_req))
    return 0 if not missing_req else 1


if __name__ == "__main__":
    sys.exit(main())
