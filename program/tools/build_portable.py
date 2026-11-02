# -*- coding: utf-8 -*-
"""打包「绿色版」（--onedir）：启动快，分发时打包成 zip

产物：
    release/和纱绿色版/            <-- 文件夹，双击 和纱.exe 直接跑
    release/和纱绿色版_v1.zip       <-- 发给别人的压缩包
"""
import io
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\program"
SRC = os.path.join(BASE, "src")
RES = os.path.join(BASE, "res")
APP = os.path.join(BASE, "build_env")
UI2 = os.path.join(BASE, "ui2")
OUTDIR = os.path.join(os.path.dirname(BASE), "release", "和纱绿色版")
ZIP = os.path.join(os.path.dirname(BASE), "release", "和纱绿色版_v1.zip")
PY = os.path.join(APP, "venv", "Scripts", "python.exe")
NAME = "和纱"

# ---------- 1. 生成 ui2 ----------
shutil.rmtree(UI2, ignore_errors=True)
os.makedirs(UI2, exist_ok=True)
for f in os.listdir(os.path.join(SRC, "ui")):
    shutil.copy2(os.path.join(SRC, "ui", f), os.path.join(UI2, f))
shutil.copytree(os.path.join(RES, "assets"), os.path.join(UI2, "assets"), dirs_exist_ok=True)
print("  ui2 生成完毕")

# ---------- 2. 刷新版本号 ----------
p = os.path.join(UI2, "index.html")
s = io.open(p, encoding="utf-8").read()
v = time.strftime("%m%d%H%M%S")
for name in ("opt.css", "opt.js", "uitext.js", "menubar.css", "menubar.js",
             "screens.css", "screens.js", "game450.css", "savetabs.js"):
    s = re.sub(re.escape(name) + r"\?v=[^\"']+", name + "?v=" + v, s)
io.open(p, "w", encoding="utf-8").write(s)
print("  版本 %s" % v)

# 同步 src 到 build_env（保证打包内容就是当前源码）
DATA = ("story_index.json", "fewshot.json")
DATA_DIRS = ("persona", "worldbook")
for _f in os.listdir(SRC):
    if _f.endswith(".py") or _f in DATA:
        shutil.copy2(os.path.join(SRC, _f), os.path.join(BASE, "build_env", _f))
for _d in DATA_DIRS:
    _s = os.path.join(SRC, _d)
    if os.path.isdir(_s):
        shutil.copytree(_s, os.path.join(BASE, "build_env", _d), dirs_exist_ok=True)

# ---------- 3. 打包 onedir ----------
shutil.rmtree(os.path.join(APP, "ui2"), ignore_errors=True)
shutil.copytree(UI2, os.path.join(APP, "ui2"))
args = [PY, "-m", "PyInstaller", "--noconfirm", "--onedir", "--windowed",
        "--name", NAME, "--icon", os.path.join("ui2", "assets", "wa2.ico"),
        "--add-data", "ui2;ui2", "--add-data", "assets;assets",
        "--add-data", "persona;persona", "--add-data", "worldbook;worldbook",
        "--add-data", "story_index.json;.",
        "--collect-all", "webview", "--collect-all", "PIL",
        "--collect-submodules", "PIL", "--hidden-import", "clr_loader",
        "--hidden-import", "fontTools", "--hidden-import", "tts_client",
        "--hidden-import", "applog", "main.py"]
r = subprocess.run(args, cwd=APP, capture_output=True, text=True,
                   encoding="utf-8", errors="replace")
built = os.path.join(APP, "dist", NAME, NAME + ".exe")
ok = os.path.exists(built)
print("  onedir 打包 %s" % ("成功" if ok else "失败"))
if not ok:
    print((r.stdout or "")[-1200:])
    print((r.stderr or "")[-800:])
    sys.exit(1)

# ---------- 4. 复制产物 ----------
shutil.rmtree(OUTDIR, ignore_errors=True)
shutil.copytree(os.path.join(APP, "dist", NAME), OUTDIR)
# 附带空配置模板（不含密钥）
cfg = os.path.join(OUTDIR, "config.example.json")
if not os.path.exists(cfg):
    with open(cfg, "w", encoding="utf-8") as f:
        f.write('{\n  "base_url": "https://api.deepseek.com",\n'
                '  "api_key": "",\n  "model": "deepseek-flash"\n}\n')
size_dir = sum(os.path.getsize(os.path.join(dp, f))
               for dp, _d, fs in os.walk(OUTDIR) for f in fs)
print("  绿色版目录 %.1f MB" % (size_dir / 1024 / 1024))

# ---------- 5. 打 zip ----------
if os.path.exists(ZIP):
    os.remove(ZIP)
with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for dp, _d, fs in os.walk(OUTDIR):
        for f in fs:
            full = os.path.join(dp, f)
            rel = os.path.join(NAME, os.path.relpath(full, OUTDIR))
            z.write(full, rel)
print("  zip %.1f MB → %s" % (os.path.getsize(ZIP) / 1024 / 1024, ZIP))

# ---------- 6. 清理 ----------
for d in ("build", "dist"):
    shutil.rmtree(os.path.join(APP, d), ignore_errors=True)
for f in os.listdir(APP):
    if f.endswith(".spec"):
        os.remove(os.path.join(APP, f))
shutil.rmtree(UI2, ignore_errors=True)
print("  清理完成")
