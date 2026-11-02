# -*- coding: utf-8 -*-
"""打包脚本：从 src/ + res/ 直接生成 exe，中间产物用完即删

结构约定（源码树里只有这两个文件夹）：
    src/    全部代码（前端 ui/ + Python 后端）
    res/    全部资源（界面图、音效、BGM、立绘…）
    ui2/    临时构建产物，打完包就删掉
"""
import io
import os
import re
import shutil
import subprocess
import sys
import time

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\program"
SRC = os.path.join(BASE, "src")
RES = os.path.join(BASE, "res")
APP = os.path.join(BASE, "build_env")
UI2 = os.path.join(BASE, "ui2")
PY = os.path.join(APP, "venv", "Scripts", "python.exe")
NAME = "和纱_v97"

# ---------- 1. 生成 ui2 ----------
shutil.rmtree(UI2, ignore_errors=True)
os.makedirs(UI2, exist_ok=True)
for f in os.listdir(os.path.join(SRC, "ui")):
    shutil.copy2(os.path.join(SRC, "ui", f), os.path.join(UI2, f))
shutil.copytree(os.path.join(RES, "assets"), os.path.join(UI2, "assets"), dirs_exist_ok=True)
print("  ui2 生成完毕")

# ---------- 2. 刷新资源版本号 ----------
p = os.path.join(UI2, "index.html")
s = io.open(p, encoding="utf-8").read()
v = time.strftime("%m%d%H%M%S")
for name in ("opt.css", "opt.js", "uitext.js", "menubar.css", "menubar.js",
             "screens.css", "screens.js", "game450.css", "game.js", "savetabs.js"):
    s = re.sub(re.escape(name) + r"\?v=[^\"']+", name + "?v=" + v, s)
io.open(p, "w", encoding="utf-8").write(s)
print("  版本 %s" % v)

# 同步 src 到 build_env（保证打包内容就是当前源码）
DATA = ("persona.txt", "persona_core.txt", "worldbook.json", "story_index.json", "fewshot.json")
for _f in os.listdir(SRC):
    if _f.endswith(".py") or _f in DATA:
        shutil.copy2(os.path.join(SRC, _f), os.path.join(BASE, "build_env", _f))

# ---------- 3. 拷进 app/ 并打包 ----------
shutil.rmtree(os.path.join(APP, "ui2"), ignore_errors=True)
shutil.copytree(UI2, os.path.join(APP, "ui2"))
args = [PY, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed",
        "--name", NAME, "--icon", os.path.join("ui2", "assets", "wa2.ico"),
        "--add-data", "ui2;ui2", "--add-data", "assets;assets",
        "--add-data", "persona.txt;.", "--add-data", "persona_core.txt;.",
        "--add-data", "worldbook.json;.", "--add-data", "story_index.json;.",
        "--collect-all", "webview", "--collect-all", "PIL",
        "--collect-submodules", "PIL", "--hidden-import", "clr_loader",
        "--hidden-import", "fontTools", "--hidden-import", "tts_client",
        "--hidden-import", "applog", "main.py"]
r = subprocess.run(args, cwd=APP, capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
ok = os.path.exists(os.path.join(APP, "dist", NAME + ".exe"))
print("  打包 %s" % ("成功" if ok else "失败"))
if not ok:
    print((r.stdout or "")[-1500:])
    sys.exit(1)

# ---------- 4. 收尾 ----------
shutil.copy2(os.path.join(APP, "dist", NAME + ".exe"),
             os.path.join(os.path.dirname(BASE), "release", "和纱_v6_字模版.exe"))
for d in ("build", "dist"):
    shutil.rmtree(os.path.join(APP, d), ignore_errors=True)
for f in os.listdir(APP):
    if f.endswith(".spec"):
        os.remove(os.path.join(APP, f))
shutil.rmtree(UI2, ignore_errors=True)          # 中间产物删掉
print("  exe 已更新，ui2/ 已清理")
