# -*- coding: utf-8 -*-
"""特别模式导入的角色资源 → 程序真正读取的地方（「资源接线」）

导入端在 special_files.py（写当前角色文件夹 characters/<角色>/<kind>/），这里是读端：

    prompt     提示词      整段替换 persona*.txt
    worldbook  世界书      .json 替换 worldbook.json（关键词触发）；
                           .txt / .md 整段附加进 system
    memory     记忆书      总是附加的一段「事先记好的旧事」
    voice      参考音频    tts_client.load_refs() 优先用它

规矩：
  1. **优先读角色文件夹，没有再用默认文件** —— 不覆盖用户原来的 persona / worldbook，
     导入的东西删掉就自动回落，接错了也不影响程序启动。
  2. 按 (路径, mtime) 缓存，导入后不用重启，下一条消息就生效。
  3. 读不出来就返回空，绝不抛异常 —— 资源坏了也不能影响聊天。
"""
import json
import os

import special_files as _sf

# (路径 -> (mtime, 解析结果))，文件一改就自动重新读
_CACHE = {}

TEXT_EXTS = (".txt", ".md")
JSON_EXTS = (".json",)

# 注入上限：这两个是用户自己写的资料，写太长会把上下文吃光
MAX_PROMPT_CHARS = 20000
MAX_WORLDBOOK_CHARS = 3000
MAX_MEMORY_CHARS = 1500


def char_file(kind, exts=None):
    """这一类资源当前导入的是哪个文件（统一由 special_files 找，别写两份）"""
    return _sf.char_file(kind, exts)


def _cached(path, loader):
    """按 mtime 缓存读取结果；文件不在返回 None"""
    if not path:
        return None
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return None
    hit = _CACHE.get(path)
    if hit and hit[0] == mt:
        return hit[1]
    try:
        val = loader(path)
    except Exception:
        val = None
    _CACHE[path] = (mt, val)
    return val


def _read_text(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read().strip()


# ------------------------------------------------------------------ 提示词
def prompt_path():
    return char_file("prompt", TEXT_EXTS)


def _has_staged_persona():
    """角色文件夹里是不是「base.txt + stageN.txt」那套分阶段人设。

    是的话这里就不返回单文件 —— 交给 persona_ctx 拼 base + 当前阶段，
    否则只会读到 base.txt、阶段文件等于白放。
    """
    p = prompt_path()
    if not p:
        return False
    d = os.path.dirname(p)
    try:
        return os.path.isfile(os.path.join(d, "base.txt"))
    except OSError:
        return False


def prompt_text():
    """导入的提示词（整份替换）；分阶段人设 / 没有时返回空串（调用方回落 persona_ctx）"""
    if _has_staged_persona():
        return ""
    text = _cached(prompt_path(), _read_text) or ""
    if len(text) > MAX_PROMPT_CHARS:
        text = text[:MAX_PROMPT_CHARS]
    return text


# ------------------------------------------------------------------ 世界书
def worldbook():
    """导入的 .json 世界书（结构同 worldbook.json）；不是 JSON 就返回 None"""
    path = char_file("worldbook", JSON_EXTS)
    data = _cached(path, lambda p: json.load(open(p, encoding="utf-8")))
    if isinstance(data, dict) and isinstance(data.get("entries"), list):
        return data
    return None


def worldbook_text():
    """导入的 .txt / .md 世界书：当成整段设定资料附加"""
    text = _cached(char_file("worldbook", TEXT_EXTS), _read_text) or ""
    if len(text) > MAX_WORLDBOOK_CHARS:
        text = text[:MAX_WORLDBOOK_CHARS]
    return text


# ------------------------------------------------------------------ 记忆书
def memory_path():
    return char_file("memory", TEXT_EXTS)


def memory_text():
    """导入的记忆书：一段事先记好的旧事，每轮都带上"""
    text = _cached(memory_path(), _read_text) or ""
    if len(text) > MAX_MEMORY_CHARS:
        text = text[:MAX_MEMORY_CHARS]
    return text


# ------------------------------------------------------------------ 参考音频
def voice_dir():
    """tts_client 也要用它判断「导入的参考音频有没有变」"""
    return _sf.kind_dir("voice")


def voice_refs():
    """导入的参考音频：[(wav 路径, prompt_text)]，同名 .txt 当参考文本"""
    d = voice_dir()
    if not d:
        return []
    out = []
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return []
    for name in names:
        if not name.lower().endswith(".wav"):
            continue
        wav = os.path.join(d, name)
        if not os.path.isfile(wav):
            continue
        txt = ""
        tpath = os.path.join(d, os.path.splitext(name)[0] + ".txt")
        if os.path.isfile(tpath):
            try:
                txt = _read_text(tpath)
            except Exception:
                txt = ""
        out.append((wav, txt))
    return out


# ------------------------------------------------------------------ 调试
def status():
    """当前实际生效的是哪个文件（给 /api/special/status 和界面提示用）

    每项：{file, path, source, size}；
    source = character（在当前角色文件夹里）/ imported（老位置导入的）/ default（程序默认）
    """
    def in_character(p):
        try:
            import characters
            root = os.path.normcase(os.path.abspath(characters.active_dir()))
            return bool(root) and os.path.normcase(os.path.abspath(p)).startswith(root)
        except Exception:
            return False

    def one(kind, exts=None):
        p = char_file(kind, exts)
        if p:
            try:
                size = os.path.getsize(p)
            except OSError:
                size = 0
            return {"file": os.path.basename(p), "path": p,
                    "source": "character" if in_character(p) else "imported", "size": size}
        # 角色文件夹里的这一类还是空的 → 就是「还没设置」（「查看文件」会打开这个空目录）
        if _sf.kind_dir(kind):
            return None
        # 连角色文件夹都没有（老安装）：告诉前端程序实际用的是哪个默认文件/目录
        d = _sf.DEFAULT_PATHS.get(kind) or ""
        if d and os.path.isfile(d):
            try:
                size = os.path.getsize(d)
            except OSError:
                size = 0
            return {"file": os.path.basename(d), "path": d,
                    "source": "default", "size": size}
        if d and os.path.isdir(d):
            return {"file": "", "path": d, "source": "default", "size": 0}
        return None

    def voice_one():
        """参考音频在角色 voice/ 里是按情绪分组的（calm/、撒娇/…），顶层的单文件反而少见"""
        d = _sf.kind_dir("voice")
        if not d:
            return one("voice")
        n = 0
        for _dp, _dn, files in os.walk(d):
            n += sum(1 for f in files if f.lower().endswith(".wav"))
        if n:
            return {"file": "", "path": d, "source": "character", "size": 0, "count": n}
        return None

    return {
        "prompt": one("prompt", TEXT_EXTS),
        "worldbook": one("worldbook", JSON_EXTS + TEXT_EXTS),
        "memory": one("memory", TEXT_EXTS),
        "voice": voice_one(),
        "prompt_chars": len(prompt_text()),
        "worldbook_text_chars": len(worldbook_text()),
        "memory_chars": len(memory_text()),
        "voice_count": len(voice_refs()),
    }
