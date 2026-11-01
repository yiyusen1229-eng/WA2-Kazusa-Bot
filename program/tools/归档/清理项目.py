# -*- coding: utf-8 -*-
"""清理废弃文件与实验代码

原则:
  · 只删可再生的产物（构建中间件、旧 exe、临时截图、实验解包）
  · 数据与训练产物一律保留（dataset / train / tts / 语音训练集）
  · 一次性实验脚本移到 tools/归档/，不直接删除
"""
import os
import shutil

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
BASE = os.path.abspath(BASE)


def size_of(path):
    if os.path.isfile(path):
        return os.path.getsize(path)
    t = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                t += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return t


def safe(path):
    ap = os.path.abspath(path)
    if not ap.startswith(BASE):
        raise SystemExit("拒绝操作: 不在项目目录内 -> %s" % ap)
    return ap


def remove(path, label=""):
    ap = safe(path)
    if not os.path.exists(ap):
        return 0, "已不存在"
    s = size_of(ap)
    try:
        if os.path.isdir(ap):
            shutil.rmtree(ap)
        else:
            os.remove(ap)
    except Exception as e:
        return 0, "失败: %s" % e
    return s, "已删除"


def main():
    total = 0
    log = []

    # --- 1. 构建中间件 ---
    for rel in (r"app\build", r"app\__pycache__", r"train\__pycache__", r"app\dist\__pycache__"):
        s, msg = remove(os.path.join(BASE, rel))
        total += s
        log.append(("构建产物", rel, s, msg))

    # --- 2. dist 里的旧 exe ---
    dist = os.path.join(BASE, "app", "dist")
    if os.path.isdir(dist):
        for f in os.listdir(dist):
            if f.startswith("旧版本_勿用_") and f.endswith(".exe"):
                s, msg = remove(os.path.join(dist, f))
                total += s
                log.append(("旧 exe", "dist/" + f, s, msg))

    # --- 3. 最新版里的旧版本 ---
    for f in ("和纱_恢复原版.exe", "和纱_字体修复版.exe"):
        s, msg = remove(os.path.join(BASE, "最新版", f))
        total += s
        log.append(("旧交付", "最新版/" + f, s, msg))

    # --- 4. 原生实验 exe（源码保留） ---
    s, msg = remove(os.path.join(BASE, "以后的版本_原生实验", "和纱_原生版.exe"))
    total += s
    log.append(("原生实验", "和纱_原生版.exe", s, msg))

    # --- 5. 旧 UI 目录 ---
    s, msg = remove(os.path.join(BASE, "ui"))
    total += s
    log.append(("旧界面", "ui/", s, msg))

    # --- 6. 备份文件 ---
    for rel in (r"app\ui2\game450.css.bak", r"app\ui2\screens.css.bak",
                r"ui2\game450.css.bak", r"ui2\screens.css.bak",
                r"ui2\assets\input_frame_旧.png", r"app\ui2\assets\input_frame_旧.png",
                r"train\progress.json.bak"):
        s, msg = remove(os.path.join(BASE, rel))
        total += s
        log.append(("备份", rel, s, msg))

    # --- 7. work 里的实验产物（保留 gh_sub / script_full / 日志） ---
    keep = {"gh_sub", "script_full"}
    work = os.path.join(BASE, "work")
    if os.path.isdir(work):
        for d in sorted(os.listdir(work)):
            full = os.path.join(work, d)
            if not os.path.isdir(full) or d in keep:
                continue
            s, msg = remove(full)
            total += s
            log.append(("实验目录", "work/" + d, s, msg))

        # work 根目录的临时图片/日志（保留标注日志）
        for f in sorted(os.listdir(work)):
            full = os.path.join(work, f)
            if not os.path.isfile(full):
                continue
            if f in ("标注日志.txt", "标注全量日志.txt", "打印.txt"):
                continue
            s, msg = remove(full)
            total += s
            log.append(("临时文件", "work/" + f, s, msg))

    # --- 8. 一次性实验脚本归档 ---
    tools = os.path.join(BASE, "tools")
    archive = os.path.join(tools, "归档")
    os.makedirs(archive, exist_ok=True)
    ACTIVE = {"语音分析.py", "语音筛选.py", "语音标注.py", "提取台词库.py",
              "评测对比.py", "读游戏窗口样式.py", "预览服务器2.py",
              "build_story_index.py", "build_story_index_v2.py",
              "build_worldbook_drafts.py"}
    moved = 0
    if os.path.isdir(tools):
        for f in sorted(os.listdir(tools)):
            full = os.path.join(tools, f)
            if not os.path.isfile(full) or not f.endswith(".py"):
                continue
            if f in ACTIVE:
                continue
            dst = os.path.join(archive, f)
            try:
                shutil.move(full, dst)
                moved += 1
            except Exception:
                pass

    # 汇总
    print("=" * 62)
    for cat, rel, s, msg in log:
        if s > 0 or msg != "已不存在":
            print("  %-8s %-46s %8.1f MB  %s" % (cat, rel[:46], s / 1048576, msg))
    print("=" * 62)
    print("释放空间: %.2f GB" % (total / 1073741824))
    print("归档脚本: %d 个 -> tools/归档/" % moved)


if __name__ == "__main__":
    main()
