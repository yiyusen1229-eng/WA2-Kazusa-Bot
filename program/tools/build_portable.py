# -*- coding: utf-8 -*-
"""打包「绿色版」（--onedir）：启动快，分发时打包成 zip

产物：
    release/和纱_本地测试/            <-- 文件夹，双击 和纱.exe 直接跑
    release/和纱_本地测试.zip          <-- 本地测试用压缩包（不含 API key）

说明：
    · 包含 res/assets 全部素材、persona/worldbook、story_index、fewshot、char/
    · 不包含 sessions/（存档）、cache/、logs/
    · config.json 默认不进 zip（避免把 key 带出去）；打完包后复制到本地运行目录
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
OUTNAME = "和纱_本地测试"
OUTDIR = os.path.join(os.path.dirname(BASE), "release", OUTNAME)
ZIP = os.path.join(os.path.dirname(BASE), "release", OUTNAME + ".zip")
PY = os.path.join(APP, "venv", "Scripts", "python.exe")
NAME = "和纱"

# ---------- 1. 生成 ui2（含全部素材） ----------
shutil.rmtree(UI2, ignore_errors=True)
os.makedirs(UI2, exist_ok=True)
for f in os.listdir(os.path.join(SRC, "ui")):
    shutil.copy2(os.path.join(SRC, "ui", f), os.path.join(UI2, f))
shutil.copytree(os.path.join(RES, "assets"), os.path.join(UI2, "assets"), dirs_exist_ok=True)
# 运行时生成的字模缓存不进包
shutil.rmtree(os.path.join(UI2, "assets", "ui", "text_cache"), ignore_errors=True)
print("  ui2 生成完毕（含素材）")

# ---------- 2. 刷新版本号 ----------
p = os.path.join(UI2, "index.html")
s = io.open(p, encoding="utf-8").read()
v = time.strftime("%m%d%H%M%S")
for name in ("opt.css", "opt.js", "uitext.js", "menubar.css", "menubar.js",
             "screens.css", "screens.js", "game450.css", "savetabs.js"):
    s = re.sub(re.escape(name) + r"\?v=[^\"']+", name + "?v=" + v, s)
io.open(p, "w", encoding="utf-8").write(s)
print("  版本 %s" % v)

# ---------- 3. 同步源码与数据 ----------
DATA = ("story_index.json", "story_index.json.gz", "fewshot.json")
DATA_DIRS = ("persona", "worldbook")
for _f in os.listdir(SRC):
    if _f.endswith(".py") or _f in DATA:
        shutil.copy2(os.path.join(SRC, _f), os.path.join(APP, _f))
for _d in DATA_DIRS:
    _s = os.path.join(SRC, _d)
    if os.path.isdir(_s):
        shutil.copytree(_s, os.path.join(APP, _d), dirs_exist_ok=True)

# ---------- 4. 打包 onedir ----------
shutil.rmtree(os.path.join(APP, "ui2"), ignore_errors=True)
shutil.copytree(UI2, os.path.join(APP, "ui2"))
data_args = ["--add-data", "ui2;ui2", "--add-data", "assets;assets",
             "--add-data", "persona;persona", "--add-data", "worldbook;worldbook"]
for extra in ("story_index.json.gz", "story_index.json"):
    if os.path.exists(os.path.join(APP, extra)):
        data_args += ["--add-data", extra + ";."]
args = [PY, "-m", "PyInstaller", "--noconfirm", "--onedir", "--windowed",
        "--name", NAME, "--icon", os.path.join("ui2", "assets", "wa2.ico")] + data_args + [
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
    print((r.stdout or "")[-1600:])
    print((r.stderr or "")[-1000:])
    sys.exit(1)

# ---------- 5. 复制产物 + 运行时文件（不含存档） ----------
shutil.rmtree(OUTDIR, ignore_errors=True)
shutil.copytree(os.path.join(APP, "dist", NAME), OUTDIR)


def _copy_into(src, name):
    if not os.path.exists(src):
        return
    dst = os.path.join(OUTDIR, name)
    if os.path.isdir(src):
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dst)


# 用户数据：fewshot / 界面偏好 / 上下文设置 / 导入的角色资源（不复制存档、缓存、日志）
for f in ("fewshot.json", "prefs.json", "memory.json"):
    _copy_into(os.path.join(APP, f), f)
_copy_into(os.path.join(APP, "char"), "char")
# 空配置模板（不含密钥）
cfg = os.path.join(OUTDIR, "config.example.json")
if not os.path.exists(cfg):
    with open(cfg, "w", encoding="utf-8") as f:
        f.write('{\n  "base_url": "https://api.deepseek.com",\n'
                '  "api_key": "",\n  "model": "deepseek-flash"\n}\n')

size_dir = sum(os.path.getsize(os.path.join(dp, f))
               for dp, _d, fs in os.walk(OUTDIR) for f in fs)
print("  目录 %.1f MB" % (size_dir / 1024 / 1024))

# ---------- 6. 打 zip（不含 config.json，避免带出 key） ----------
if os.path.exists(ZIP):
    os.remove(ZIP)
with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for dp, _d, fs in os.walk(OUTDIR):
        for f in fs:
            if f == "config.json":
                continue
            full = os.path.join(dp, f)
            rel = os.path.join(OUTNAME, os.path.relpath(full, OUTDIR))
            z.write(full, rel)
print("  zip %.1f MB → %s" % (os.path.getsize(ZIP) / 1024 / 1024, ZIP))

# ---------- 7. 本地运行：把 key 配置放到运行目录（不进 zip） ----------
cfg_src = os.path.join(APP, "config.json")
if os.path.exists(cfg_src):
    shutil.copy2(cfg_src, os.path.join(OUTDIR, "config.json"))
    print("  已把 config.json 复制到运行目录（仅在本地，zip 里没有）")

# ---------- 8. 清理 ----------
for d in ("build", "dist"):
    shutil.rmtree(os.path.join(APP, d), ignore_errors=True)
for f in os.listdir(APP):
    if f.endswith(".spec"):
        os.remove(os.path.join(APP, f))
shutil.rmtree(UI2, ignore_errors=True)
print("  清理完成")
