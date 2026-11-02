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

# 「变化编号 → 表情」：从现有 index.json 的 emotions 里统计出来的一致规律
# （同一个尾号在不同衣服上都指向同一种表情）。导入新立绘时按尾号自动补映射，
# 这样对话里换表情才会真的换到这张图。
VARIANT_EMOTION = {
    "101": "serious",
    "104": "cold", "110": "cold", "134": "cold",
    "109": "smile", "307": "smile", "323": "smile",
    "115": "surprise", "218": "surprise",
    "125": "sad", "131": "sad", "224": "sad",
    "140": "shy",
    "205": "angry", "212": "angry",
}

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
    """用户数据目录（char/ 在这里）。WA2_USER_DIR 可以改，自测时指到临时目录用。"""
    env = os.environ.get("WA2_USER_DIR")
    if env:
        return env
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
# 程序实际读取的默认位置（main.py 启动时注入）：没导入时「查看文件」打开这里，
# 不然用户看到的是一个空的导入目录，会以为接错了。
DEFAULT_PATHS = {"prompt": "", "worldbook": "", "memory": "", "voice": ""}


def set_default_paths(prompt="", worldbook="", memory="", voice=""):
    DEFAULT_PATHS.update({"prompt": prompt, "worldbook": worldbook,
                          "memory": memory, "voice": voice})


def kind_dir(kind):
    """这一类资源的导入目录（char/<kind>/）"""
    spec = KINDS.get(kind)
    return os.path.join(CHAR_DIR, spec["dir"]) if spec else ""


def char_file(kind, exts=None):
    """导入端只保留最新一份：返回那一份的路径（没有就是空串）。

    exts 不传就按这一类的白名单过滤 —— 参考音频目录里可能还有同名 .txt
    （prompt_text），不能被当成"导入的音频"。
    """
    d = kind_dir(kind)
    if not d:
        return ""
    if not exts:
        exts = (KINDS.get(kind) or {}).get("exts") or ()
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return ""
    for name in names:
        if exts and os.path.splitext(name)[1].lower() not in exts:
            continue
        p = os.path.join(d, name)
        if os.path.isfile(p):
            return p
    return ""


def open_target(kind):
    """「查看文件」到底该打开哪儿：优先指到导入的那份，没导入就指到程序实际用的默认。

    返回 {folder, select, source}；source ∈ imported / default / empty / assets
    """
    if kind == "portrait":
        return {"folder": os.path.join(_assets(), "sprites"), "select": "", "source": "assets"}
    if kind not in KINDS:
        return None
    p = char_file(kind)
    if p:
        return {"folder": os.path.dirname(p), "select": p, "source": "imported"}
    d = DEFAULT_PATHS.get(kind) or ""
    if d and os.path.isfile(d):
        return {"folder": os.path.dirname(d), "select": d, "source": "default"}
    if d and os.path.isdir(d):
        return {"folder": d, "select": "", "source": "default"}
    return {"folder": kind_dir(kind), "select": "", "source": "empty"}


def open_folder(kind):
    """在系统文件管理器里打开这一类资源**实际被读取**的位置。

    · 导入过 → 打开 char/<kind>/ 并选中那个文件
    · 没导入 → 打开程序真正在用的默认文件/目录（persona_core.txt、worldbook.json、
      sessions/、tts/refs_touma），而不是一个空目录
    只认这 5 种 kind，路径全部由常量拼出来，不接受外部路径。
    """
    t = open_target(kind)
    if not t:
        return {"ok": False, "error": "未知的资源类型"}
    folder, sel = t["folder"], t["select"]
    if folder and t["source"] in ("imported", "assets", "empty"):
        # 只给「导入目录 / 素材目录」兜底建目录；默认位置是程序原来就有的，别乱建
        try:
            os.makedirs(folder, exist_ok=True)
        except Exception as e:
            return {"ok": False, "error": "建不了目录：%s" % e}
    try:
        if os.name == "nt":
            if sel:
                # 打开目录并选中文件（资源管理器会高亮它）
                subprocess.Popen(["explorer", "/select," + os.path.abspath(sel)])
            else:
                os.startfile(folder)
        elif sys.platform == "darwin":
            if sel:
                subprocess.Popen(["open", "-R", sel])
            else:
                subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])
    except Exception as e:
        return {"ok": False, "error": "打不开文件夹：%s" % e}
    return {"ok": True, "path": folder, "file": os.path.basename(sel) if sel else "",
            "source": t["source"]}


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
    emo = VARIANT_EMOTION.get(variant, "")
    return {"ok": True, "kind": "portrait", "name": name, "outfit": outfit,
            "variant": variant, "emotion": emo, "size": len(data), "path": target}


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
        # 变化编号 → 表情：补上 emotions，对话换表情时才会选中这张图
        emo = VARIANT_EMOTION.get(variant)
        if emo:
            o.setdefault("emotions", {})[emo] = filename
        tmp = idx_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, idx_path)
        return True
    except Exception:
        return False
