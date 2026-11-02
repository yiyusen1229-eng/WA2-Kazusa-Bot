# -*- coding: utf-8 -*-
"""特别模式 → 角色配置：把用户选的文件收进对应的资源

界面上有 5 个底框按钮，每个对应一种资源：

    portrait   角色立绘        图片 → characters/<角色>/portrait/
    prompt     提示词          文本 → characters/<角色>/prompt/
    worldbook  世界书          文本 → characters/<角色>/worldbook/
    memory     记忆书          文本 → characters/<角色>/memory/
    voice      参考音频        音频 → characters/<角色>/voice/

（角色文件夹由 characters.py 管理；老版本的 `char/<kind>/` 会被自动搬过去。）

立绘为什么单独处理：
    对话框换立绘用的是「衣服目录 + index.json」，所以立绘必须按同样的结构摆：
        文件名 kaz + 衣服编号(3位) + 变化编号(3位) + 扩展名   例：kaz001101.png → portrait/001/
    文件名对不上就拒绝（不做内容识别）。角色自己的 portrait/ 优先，
    没有的图回落到自带的 assets/sprites/。

其余四类只保留最新一份（它们本来就是一个配置）。
文件类型在这里做硬校验（前端的 accept 只是筛选提示，不能当安全边界）。
"""
import json
import os
import re
import subprocess
import sys

import characters

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


# 兼容：自测脚本可以直接改这个常量把资源目录指到临时位置；平时留空，
# 走当前角色文件夹（characters/<角色>/）。
CHAR_DIR = ""


def char_dir():
    """当前角色的资源根目录（prompt/worldbook/memory/voice/portrait 都在它下面）"""
    return CHAR_DIR or characters.active_dir()


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

    folder = kind_dir(kind)
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
    """这一类资源在当前角色文件夹里的目录（characters/<角色>/<kind>/）"""
    spec = KINDS.get(kind)
    root = char_dir()
    return os.path.join(root, spec["dir"]) if (spec and root) else ""


def portrait_dir():
    """当前角色的立绘目录（characters/<角色>/portrait/）"""
    root = char_dir()
    return os.path.join(root, "portrait") if root else ""


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
    """「查看文件」打开哪儿：一律是当前角色文件夹里的这一类（自包含）。

    这一类有文件 → 打开目录并选中它；没有 → 打开空目录，方便往里面放。
    只有连角色文件夹都拿不到时（老安装 / 自测把 CHAR_DIR 清掉），才回落到程序默认位置。

    返回 {folder, select, source}；source ∈ imported / empty / default / assets
    """
    if kind == "portrait":
        d = portrait_dir()
        if d:
            return {"folder": d, "select": "", "source": "imported"}
        return {"folder": os.path.join(_assets(), "sprites"), "select": "", "source": "assets"}
    if kind not in KINDS:
        return None
    p = char_file(kind)
    d = kind_dir(kind)
    if d:
        return {"folder": d, "select": p or "", "source": "imported" if p else "empty"}
    if p:
        return {"folder": os.path.dirname(p), "select": p, "source": "imported"}
    dd = DEFAULT_PATHS.get(kind) or ""
    if dd and os.path.isfile(dd):
        return {"folder": os.path.dirname(dd), "select": dd, "source": "default"}
    if dd and os.path.isdir(dd):
        return {"folder": dd, "select": "", "source": "default"}
    return {"folder": "", "select": "", "source": "empty"}


def open_folder(kind):
    """在系统文件管理器里打开这一类资源**实际被读取**的位置。

    · 导入过 → 打开 characters/<角色>/<kind>/ 并选中那个文件
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
    """立绘：按 kaz<衣服3><变化3>.png 归类进当前角色的 portrait/<衣服>/"""
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

    pdir = portrait_dir()
    if not pdir:
        return {"ok": False, "error": "没有当前角色文件夹"}
    folder = os.path.join(pdir, outfit)
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
    """把新立绘写进**角色自己的** portrait/index.json（没有这套衣服就新建一条）。

    自带的 assets/sprites/index.json 一个字都不改：读取时由 characters.sprite_index()
    把两份合起来（角色的优先），所以不导入也照样能用自带立绘。
    """
    pdir = portrait_dir()
    if not pdir:
        return False
    idx_path = os.path.join(pdir, "index.json")
    try:
        data = {}
        if os.path.isfile(idx_path):
            with open(idx_path, encoding="utf-8") as f:
                data = json.load(f)
        if not isinstance(data, dict):
            data = {}
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
