# -*- coding: utf-8 -*-
"""开发运行：把 src/ 同步到 build_env/ 并直接用 python 启动（改完代码立刻生效）

program/  = 实时程序（源码 + 这个入口）
release/  = 打包好的分发版本
"""
import os
import shutil
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "src")
RES = os.path.join(BASE, "res")
ENV = os.path.join(BASE, "build_env")
PY = os.path.join(ENV, "venv", "Scripts", "python.exe")

DATA = ("persona.txt", "persona_core.txt", "wordbook.json",
        "worldbook.json", "story_index.json", "fewshot.json")

# 1. 同步后端代码与数据
n = 0
for f in os.listdir(SRC):
    if f.endswith(".py") or f in DATA:
        shutil.copy2(os.path.join(SRC, f), os.path.join(ENV, f))
        n += 1
print("  同步 %d 个后端文件 → build_env/" % n)

# 2. 组装前端（src/ui + res/assets → build_env/ui2）
ui2 = os.path.join(ENV, "ui2")
shutil.rmtree(ui2, ignore_errors=True)
os.makedirs(ui2, exist_ok=True)
for f in os.listdir(os.path.join(SRC, "ui")):
    shutil.copy2(os.path.join(SRC, "ui", f), os.path.join(ui2, f))
print("  组装 ui2 完成（素材不再复制，运行时直接读 res/assets）")

# 3. 启动
print("  启动程序…")
env = os.environ.copy()
env["WA2_ASSETS_DIR"] = os.path.join(RES, "assets")   # 界面素材直接读 res/
subprocess.Popen([PY, "main.py"], cwd=ENV, env=env)
