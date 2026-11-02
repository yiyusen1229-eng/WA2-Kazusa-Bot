# -*- coding: utf-8 -*-
"""特别模式 → 角色配置：把用户选的文件收进对应的资源

界面上有 5 个底框按钮，每个对应一种资源：

    portrait   角色立绘        图片 → 直接进游戏的立绘目录 assets/sprites/<衣服编号>/
    prompt     提示词          文本 → char/prompt/
    worldbook  世界书          文本 → char/worldbook/
    memory     记忆书          文本 → char/memory/
    voice      参考音频        音频 → char/voice/

立绘为什么单独处理：
    对话框换立绘用的是 assets/sprites/<衣服>/<文件>.png + index.json，
    所以立绘必须放到那套目录里才能真的用上。按文件名自动归类：
        kaz + 衣服编号(3位) + 变化编号(3位) + 扩展名   例：kaz001101.png → sprites/001/
    文件名对不上就拒绝（不做内容识别）。

其余四类只保留最新一份（它们本来就是一个配置）。
文件类型在这里做硬校验（前端的 accept 只是筛选提示，不能当安全边界）。
"""
import json
import os
import re
import subprocess
import sys

ROOT_NAME = "char"
MAX_BYTES = 25 * 1024 * 1024

# 立绘文件名：kaz + 衣服 3 位 + 变化 3 位
SPRITE_RE = re.compile(r"^kaz(\d{3})(\d{3})\.(png|jpg|jpeg|webp|bmp|gif)$", re.I)
SPRITE_HINT = "文件名要像 kaz001101.png（kaz + 衣服编号3位 + 变化编号3位）"

KINDS = {
    "prompt": {
        "dir": "prompt", "label": "提示词", "hint": "只能放文本文件",
        "exts": (".txt", ".md"),
    },
    "worldbook": {
        "dir": "worldbook", "label": "世界书", "hint": "只能放文本文件",
        "exts": (".txt", ".md", ".json"),
    },
    "memory": {
        "dir": "memory", "label": "记忆书", "hint": "只能放文本文件",
        "exts": (".txt", ".md"),
    },
    "voice": {
        "dir": "voice", "label": "参考音频", "hint": "只能放音频文件",
        "exts": (".wav", ".mp3", ".ogg", ".flac", ".m4a"),
    },
}

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif")


def _user_dir():
    if getattr(sys, "_MEIPASS", None):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


CHAR_DIR = os.path.join(_user_dir(), ROOT_NAME)

# 素材根目录由 main.py 起服务时注进来（开发时是 program/res/assets，打包版是 ui2/assets）
ASSETS_DIR = None


def set_assets_dir(path):
    global ASSETS_DIR
    ASSETS_DIR = path


def _assets():
    if ASSETS_DIR:
        return ASSETS_DIR
    cand = os.path.join(os.path.dirname(os.path.abspath(__file__)), "res", "assets")
    return cand


def _safe_name(name):
    """只留文件名本身，去掉路径和 Windows 不允许的字符"""
    name = os.path.basename((name or "").replace("\\", "/")).strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.strip(" .")
    if not name:
        name = "file"
    if len(name) > 80:
        root, ext = os.path.splitext(name)
        name = root[:80 - len(ext)] + ext
    return name


def save_upload(kind, filename, data):
    if kind == "portrait":
        return save_portrait(filename, data)
    spec = KINDS.get(kind)
    if not spec:
        return {"ok": False, "error": "未知的资源类型"}
    if not data:
        return {"ok": False, "error": "文件是空的"}
    if len(data) > MAX_BYTES:
        return {"ok": False, "error": "文件太大（上限 25MB）"}

    name = _safe_name(filename)
    ext = os.path.splitext(name)[1].lower()
    if ext not in spec["exts"]:
        return {"ok": False, "error": spec["hint"]}

    folder = os.path.join(CHAR_DIR, spec["dir"])
    try:
        os.makedirs(folder, exist_ok=True)
        target = os.path.join(folder, name)
        with open(target, "wb") as f:
            f.write(data)
    except Exception as e:
        return {"ok": False, "error": "写入失败: %s" % e}

    # 这几类只保留最新的一份
    for fn in os.listdir(folder):
        p = os.path.join(folder, fn)
        if os.path.isfile(p) and os.path.abspath(p) != os.path.abspath(target):
            try:
                os.remove(p)
            except OSError:
                pass

    return {"ok": True, "kind": kind, "name": name, "size": len(data), "path": target}


# ------------------------------------------------------------------ 打开文件夹
def folder_for(kind):
    """这一类资源落在哪个目录（界面上的「查看文件」打开的就是它）"""
    if kind == "portrait":
        return os.path.join(_assets(), "sprites")
    spec = KINDS.get(kind)
    if not spec:
        return None
    return os.path.join(CHAR_DIR, spec["dir"])


def open_folder(kind):
    """在系统文件管理器里打开这一类资源的目录（没有就先建出来）

    只认这 5 种 kind，路径全部由上面的常量拼出来，不接受外部路径，
    避免前端传个任意路径过来就能打开/探测磁盘。
    """
    folder = folder_for(kind)
    if not folder:
        return {"ok": False, "error": "未知的资源类型"}
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception as e:
        return {"ok": False, "error": "建不了目录：%s" % e}
    try:
        if os.name == "nt":
            os.startfile(folder)                      # 资源管理器
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])
    except Exception as e:
        return {"ok": False, "error": "打不开文件夹：%s" % e}
    return {"ok": True, "path": folder}


# ------------------------------------------------------------------ 立绘
def save_portrait(filename, data):
    """立绘：按 kaz<衣服3><变化3>.png 归类进 assets/sprites/<衣服>/"""
    if not data:
        return {"ok": False, "error": "文件是空的"}
    if len(data) > MAX_BYTES:
        return {"ok": False, "error": "文件太大（上限 25MB）"}
    name = _safe_name(filename)
    m = SPRITE_RE.match(name)
    if not m:
        return {"ok": False, "error": SPRITE_HINT}
    outfit, variant = m.group(1), m.group(2)
    ext = os.path.splitext(name)[1].lower()
    if ext not in IMAGE_EXTS:
        return {"ok": False, "error": "只能放图片文件"}

    folder = os.path.join(_assets(), "sprites", outfit)
    try:
        os.makedirs(folder, exist_ok=True)
        target = os.path.join(folder, name)
        with open(target, "wb") as f:
            f.write(data)
    except Exception as e:
        return {"ok": False, "error": "写入失败: %s" % e}

    _register_sprite(outfit, variant, name)
    return {"ok": True, "kind": "portrait", "name": name, "outfit": outfit,
            "variant": variant, "size": len(data), "path": target}


def _register_sprite(outfit, variant, filename):
    """把新立绘写进 sprites/index.json（没有这套衣服就新建一条），保留其它内容"""
    idx_path = os.path.join(_assets(), "sprites", "index.json")
    try:
        with open(idx_path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return False
        outfits = data.setdefault("outfits", {})
        o = outfits.get(outfit)
        if not isinstance(o, dict):
            o = {"label": "自定义 " + outfit, "default": filename, "variants": []}
            outfits[outfit] = o
        if not o.get("default"):
            o["default"] = filename
        variants = o.setdefault("variants", [])
        if not any((v or {}).get("file") == filename for v in variants):
            variants.append({"variant": variant, "file": filename})
        tmp = idx_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, idx_path)
        return True
    except Exception:
        return False
