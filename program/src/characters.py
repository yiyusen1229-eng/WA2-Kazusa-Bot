# -*- coding: utf-8 -*-
"""多角色：总角色资源文件夹 / 当前角色 / 立绘

用户数据目录（打包版是 exe 同目录，开发时是 program/build_env）下的结构：

    characters/                  总角色资源文件夹
        active.json              当前用的是哪个角色：{"id": "和纱"}
        <角色名>/                文件夹名就是角色 id
            name.txt             对话框左上角显示的名字
            prompt/              提示词（整份替换自带的 persona）
            worldbook/           世界书（关键词触发）
            memory/              常驻记忆书（每轮注入）
            voice/               参考音频（优先于 tts/refs_*）
            portrait/            立绘（kaz<衣服3><变化3>.png + index.json）

规矩：
  1. 角色文件夹是「这一角色的导入资源」；程序自带的 persona/、worldbook/ 仍然是
     谁都没导入时的兜底（不搬、不复制，免得两份人设各改各的）。
  2. 老版本的 `char/<kind>/` 在第一次启动时整体搬进当前角色的文件夹（只搬一次）。
  3. 立绘只写角色自己的 portrait/；读的时候和 assets/sprites/index.json 合并
     （角色的优先），所以不导入也照样能显示自带立绘。
"""
import json
import os
import re
import shutil
import subprocess
import sys

ROOT_NAME = "characters"
LEGACY_NAME = "char"
SUBDIRS = ("prompt", "worldbook", "memory", "voice", "portrait")
ACTIVE_FILE = "active.json"
DEFAULT_ID = "和纱"
DEFAULT_NEW_NAME = "新角色"

# 和 special_files 一样：自测时可以用 WA2_USER_DIR 指到临时目录
def user_dir():
    env = os.environ.get("WA2_USER_DIR")
    if env:
        return env
    if getattr(sys, "_MEIPASS", None):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def root():
    """总角色资源文件夹"""
    return os.path.join(user_dir(), ROOT_NAME)


def _log(msg):
    try:
        import applog
        applog.log(msg, "CHAR")
    except Exception:
        pass


def _sanitize(name):
    """文件夹名：去掉路径与 Windows 不允许的字符"""
    name = os.path.basename((name or "").replace("\\", "/")).strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.strip(" .")
    return name[:40]


def _read(path, default=""):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip() or default
    except Exception:
        return default


def _write(path, text):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
        return True
    except Exception:
        return False


def _state():
    try:
        with open(os.path.join(root(), ACTIVE_FILE), encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and d.get("id"):
            return d
    except Exception:
        pass
    return {}


def _save_state(cid):
    return _write(os.path.join(root(), ACTIVE_FILE),
                  json.dumps({"id": cid}, ensure_ascii=False))


def _make_dirs(path):
    for sub in SUBDIRS:
        try:
            os.makedirs(os.path.join(path, sub), exist_ok=True)
        except OSError:
            pass


# ------------------------------------------------------------------ 迁移 / 初始化
def _migrate_legacy(target):
    """把老版本 char/<kind>/ 里的文件搬进角色文件夹（搬完删空目录）"""
    legacy = os.path.join(user_dir(), LEGACY_NAME)
    if not os.path.isdir(legacy):
        return 0
    moved = 0
    for kind in ("prompt", "worldbook", "memory", "voice"):
        src = os.path.join(legacy, kind)
        if not os.path.isdir(src):
            continue
        dst = os.path.join(target, kind)
        for fn in os.listdir(src):
            sp = os.path.join(src, fn)
            if not os.path.isfile(sp):
                continue
            dp = os.path.join(dst, fn)
            try:
                if os.path.exists(dp):
                    os.remove(dp)
                shutil.move(sp, dp)
                moved += 1
            except Exception as e:
                _log("迁移 %s 失败: %s" % (sp, e))
        try:
            os.rmdir(src)                 # 空了才删得掉
        except OSError:
            pass
    # 角色名也搬过来
    nsrc = os.path.join(legacy, "name.txt")
    ndst = os.path.join(target, "name.txt")
    if os.path.isfile(nsrc) and not os.path.exists(ndst):
        try:
            shutil.move(nsrc, ndst)
            moved += 1
        except Exception:
            pass
    # 老目录下剩下的空子目录（以前建过 portrait/ 之类的）一并清掉，空了整目录才删得掉
    try:
        for fn in os.listdir(legacy):
            p = os.path.join(legacy, fn)
            if os.path.isdir(p):
                try:
                    os.rmdir(p)
                except OSError:
                    pass
    except OSError:
        pass
    return moved


def ensure():
    """第一次启动：建总目录 + 迁老数据 + 定当前角色。可重复调用。"""
    r = root()
    st = _state()
    if st.get("id") and os.path.isdir(os.path.join(r, st["id"])):
        _make_dirs(os.path.join(r, st["id"]))
        return st["id"]
    try:
        os.makedirs(r, exist_ok=True)
    except OSError as e:
        _log("建不了总角色目录 %s: %s" % (r, e))
        return ""

    cid = _sanitize(st.get("id") or "") or DEFAULT_ID
    target = os.path.join(r, cid)
    if not os.path.isdir(target):
        cid = _unique(cid)
        target = os.path.join(r, cid)
        os.makedirs(target, exist_ok=True)
    _make_dirs(target)

    moved = _migrate_legacy(target)
    if not os.path.isfile(os.path.join(target, "name.txt")):
        _write(os.path.join(target, "name.txt"), cid)
    _save_state(cid)
    if moved:
        _log("多角色：老 char/ 的 %d 个文件已搬进 %s" % (moved, target))
    # 老目录空了就删掉，免得下次又找一遍
    try:
        os.rmdir(os.path.join(user_dir(), LEGACY_NAME))
    except OSError:
        pass
    return cid


# ------------------------------------------------------------------ 基本查询
def active_id():
    st = _state()
    cid = st.get("id") or ""
    if not cid:
        cid = ensure()
    return cid


def active_dir():
    cid = active_id()
    return os.path.join(root(), cid) if cid else ""


def name_file():
    d = active_dir()
    return os.path.join(d, "name.txt") if d else ""


def display_name(cid=None):
    """对话框上的名字：角色文件夹里的 name.txt，没有就用文件夹名"""
    d = os.path.join(root(), cid) if cid else active_dir()
    if not d:
        return DEFAULT_ID
    return _read(os.path.join(d, "name.txt")) or os.path.basename(d) or DEFAULT_ID


def _unique(base):
    r = root()
    cid = base
    i = 2
    while os.path.isdir(os.path.join(r, cid)):
        cid = "%s%d" % (base, i)
        i += 1
    return cid


def list_characters():
    r = root()
    out = []
    try:
        names = sorted(os.listdir(r))
    except OSError:
        return out
    cur = active_id()
    for n in names:
        p = os.path.join(r, n)
        if not os.path.isdir(p):
            continue
        out.append({
            "id": n,
            "name": _read(os.path.join(p, "name.txt")) or n,
            "active": n == cur,
            "portrait": os.path.isdir(os.path.join(p, "portrait")),
        })
    return out


# ------------------------------------------------------------------ 切换 / 新建
def switch(cid):
    cid = _sanitize(cid)
    if not cid:
        return {"ok": False, "error": "角色名不对"}
    p = os.path.join(root(), cid)
    if not os.path.isdir(p):
        return {"ok": False, "error": "没有这个角色文件夹：%s" % cid}
    _make_dirs(p)
    if not _save_state(cid):
        return {"ok": False, "error": "写不了 active.json"}
    if not os.path.isfile(os.path.join(p, "name.txt")):
        _write(os.path.join(p, "name.txt"), cid)
    _log("多角色：切换到 %s" % cid)
    return {"ok": True, "id": cid, "name": display_name(cid)}


def create(name=None):
    """新建角色文件夹（含子目录），并切换过去"""
    base = _sanitize(name or "") or DEFAULT_NEW_NAME
    r = root()
    try:
        os.makedirs(r, exist_ok=True)
    except OSError as e:
        return {"ok": False, "error": "建不了总角色目录: %s" % e}
    cid = _unique(base)
    p = os.path.join(r, cid)
    try:
        os.makedirs(p)
    except OSError as e:
        return {"ok": False, "error": "建不了角色文件夹: %s" % e}
    _make_dirs(p)
    _write(os.path.join(p, "name.txt"), (name or "").strip()[:12] or cid)
    res = switch(cid)
    if res.get("ok"):
        res["created"] = True
        _log("多角色：新建 %s" % cid)
    return res


def pick_folder():
    """弹系统的「选择文件夹」窗口，从总角色资源文件夹里挑一个角色。

    用 PowerShell 的 FolderBrowserDialog（独立进程）：不用 tkinter，
    打包后也不需要额外的隐藏依赖。返回 {"ok": True, "id": ...} 或 cancelled。
    """
    r = root()
    try:
        os.makedirs(r, exist_ok=True)
    except OSError as e:
        return {"ok": False, "error": "建不了总角色目录: %s" % e}
    if os.name != "nt":
        return {"ok": False, "error": "只有 Windows 支持文件夹选择窗口"}

    def q(s):
        return (s or "").replace("'", "''")

    ps = (
        "$ErrorActionPreference='Stop';"
        "Add-Type -AssemblyName System.Windows.Forms;"
        "$d=New-Object System.Windows.Forms.FolderBrowserDialog;"
        "$d.Description='选择角色文件夹（总角色资源：%s）';"
        "$d.SelectedPath='%s';"
        "$d.ShowNewFolderButton=$false;"
        "if($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK)"
        "{[Console]::Out.Write($d.SelectedPath)}"
    ) % (q(r), q(r))
    try:
        p = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=300)
    except subprocess.TimeoutExpired:
        return {"ok": False, "cancelled": True}
    except Exception as e:
        return {"ok": False, "error": "打不开选择窗口: %s" % e}
    picked = (p.stdout or "").strip()
    if not picked:
        return {"ok": False, "cancelled": True}
    _log("多角色：选择窗口返回 %s" % picked)
    picked = os.path.normpath(picked)
    # Windows 的路径大小写不敏感：选中的就是总目录本身时要挡住
    if os.path.normcase(picked) == os.path.normcase(os.path.normpath(r)):
        return {"ok": False, "error": "请选一个角色文件夹，不要选总目录本身"}
    cid = os.path.basename(picked)
    res = switch(cid)
    if not res.get("ok"):
        res["error"] = "选中的不是总目录里的角色文件夹：%s" % picked
    return res


# ------------------------------------------------------------------ 立绘
def sprite_dir():
    d = active_dir()
    return os.path.join(d, "portrait") if d else ""


def _read_index(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def sprite_index(assets_sprites):
    """合并：自带 assets/sprites/index.json + 当前角色的 portrait/index.json（角色优先）"""
    base = _read_index(os.path.join(assets_sprites, "index.json"))
    own = _read_index(os.path.join(sprite_dir(), "index.json")) if sprite_dir() else {}
    outfits = dict(base.get("outfits") or {})
    for k, v in (own.get("outfits") or {}).items():
        o = dict(outfits.get(k) or {})
        o.update(v or {})
        # 角色自己加的情绪映射要叠在自带上面，不能把自带的整套覆盖掉
        emo = dict(((outfits.get(k) or {}).get("emotions")) or {})
        emo.update((v or {}).get("emotions") or {})
        if emo:
            o["emotions"] = emo
        outfits[k] = o
    out = dict(base)
    out["outfits"] = outfits
    return out


def sprite_file(assets_sprites, rel):
    """按相对路径找立绘图：角色 portrait/ 优先，没有再用自带 assets/sprites/"""
    rel = (rel or "").replace("\\", "/").strip("/")
    if not rel or ".." in rel.split("/"):
        return ""
    own = os.path.join(sprite_dir(), *rel.split("/")) if sprite_dir() else ""
    if own and os.path.isfile(own):
        return own
    base = os.path.join(assets_sprites, *rel.split("/"))
    if os.path.isfile(base):
        return base
    return ""
