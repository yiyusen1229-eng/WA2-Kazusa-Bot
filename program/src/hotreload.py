# -*- coding: utf-8 -*-
"""素材热重载（#20）：盯着素材目录，变了就让缓存失效、前端重拉。

不装 watchdog：每 2 秒 stat 一遍受监视的目录（几百个文件，毫秒级），够了。

规矩：
  · **只在签名稳定后动作**：正在拷贝一张大图时文件大小会变，等它稳定一个周期再触发，
    免得加载到半张图（`SETTLE`）。
  · **失败不影响别人**：每个回调单独 try/except，失败的记进 `last["errors"]` 并写 WARN，
    别的勾子照跑；素材本身不动，前端继续用旧图。
  · **可关**：`WA2_HOTRELOAD=0`，或运行时 `POST /api/hotreload {"on": false}`。
  · 只留最近一次状态，不写文件。

对外：
    start() / stop() / enabled() / set_enabled()
    watch(assets_dir, char_dir)   设置要盯的两个根
    set_hooks(dict)               注入失效动作（main 里接）
    tick()                        跑一次检查（返回是否触发了重载；自测直接调）
    state()                       {enabled, gen, last_at, last_kinds, interval, errors}
"""
import os
import threading
import time

import applog
import characters

INTERVAL = max(0.5, float(os.environ.get("WA2_HOTRELOAD_S") or 2.0))
SETTLE = 0.8                     # 签名要保持这么久不变才动作
MAX_ENTRIES = 6000               # 单次扫描上限（超大素材目录不至于卡）

# 不参与签名的目录：这些是**运行时数据**，聊天时每轮都在变（自动存档、缩略图、缓存）。
# 盯着它们会让「素材已更新」提示每几秒弹一次（2026-11-05 用户反馈的实际问题）。
SKIP_DIRS = {"sessions", "cache", "_deleted", "logs", "work_scratch", "tmp",
             "__pycache__", ".git"}
# 单个文件级的排除：常驻记忆书的关系摘要会随阶段刷新，但那不是「素材」
SKIP_FILES = {"standing.json"}

_LOCK = threading.Lock()
_THREAD = None
_STOP = threading.Event()
_ENABLED = (os.environ.get("WA2_HOTRELOAD") or "1") != "0"

_ROOTS = {"assets": "", "character": ""}
_HOOKS = {}
_SEEN = {}           # 上一次「稳定」的签名
_PENDING = {}        # 观察到但还没稳定的签名
_PENDING_AT = 0.0
_GEN = 0
_LAST = {"at": "", "kinds": [], "errors": [], "ms": 0}


def set_hooks(hooks):
    """{"name": callable(kind)}；main 里接：字模缓存 / 立绘索引 / 素材报告"""
    _HOOKS.clear()
    _HOOKS.update(hooks or {})


def watch(assets_dir="", char_dir=""):
    _ROOTS["assets"] = assets_dir or ""
    _ROOTS["character"] = char_dir or ""


def enabled():
    return _ENABLED


def set_enabled(on):
    global _ENABLED, _PENDING_AT
    _ENABLED = bool(on)
    _PENDING.clear()
    _PENDING_AT = 0.0
    return _ENABLED


def _sig_dir(root):
    """(文件数, 最大 mtime_ns, 总字节)；扫不到返回 (0, 0, 0)

    跳过 SKIP_DIRS / SKIP_FILES：存档、缓存、日志这些聊天时一直在变，
    算进签名就会「素材已更新」狂弹。
    """
    if not root or not os.path.isdir(root):
        return (0, 0, 0)
    n = 0
    mx = 0
    total = 0
    stack = [root]
    while stack and n < MAX_ENTRIES:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            if e.name in SKIP_DIRS:
                                continue
                            if len(stack) < 64:
                                stack.append(e.path)
                            continue
                        if e.name in SKIP_FILES:
                            continue
                        st = e.stat(follow_symlinks=False)
                        n += 1
                        total += st.st_size
                        if st.st_mtime_ns > mx:
                            mx = st.st_mtime_ns
                    except OSError:
                        continue
        except OSError:
            continue
    return (n, mx, total)


def signature():
    """{"assets": (...), "character": (...)}；角色目录每次现取，切角色自动跟着走"""
    roots = {"assets": _ROOTS["assets"], "character": _ROOTS["character"]}
    if not roots["character"]:
        try:
            roots["character"] = characters.active_dir()
        except Exception:
            roots["character"] = ""
    return {k: _sig_dir(v) for k, v in roots.items()}


def _changed_kinds(old, new):
    return [k for k in new if old.get(k) != new.get(k)]


def _fire(kinds):
    global _GEN
    t0 = time.time()
    errors = []
    for name, fn in list(_HOOKS.items()):
        try:
            fn(kinds)
        except Exception as e:
            errors.append("%s: %s" % (name, e))
            try:
                applog.log("热重载：%s 失败（继续用旧素材）：%s" % (name, e), "WARN")
            except Exception:
                pass
    with _LOCK:
        _GEN += 1
        _LAST.update({"at": time.strftime("%H:%M:%S"), "kinds": list(kinds),
                      "errors": errors, "ms": int((time.time() - t0) * 1000)})
    if not errors:
        try:
            applog.log("热重载：%s 变了，缓存已失效（第 %d 代）"
                       % ("/".join(kinds), _GEN), "ASSET")
        except Exception:
            pass
    return not errors


def tick(now=None):
    """检查一次。返回是否触发了一次重载（自测直接调，不起线程）。"""
    global _PENDING_AT
    if not _ENABLED:
        return False
    now = time.time() if now is None else now
    sig = signature()
    if not _SEEN:
        # 第一次只记基线，不触发（启动时不该算「变了」）
        _SEEN.update(sig)
        return False
    kinds = _changed_kinds(_SEEN, sig)
    if not kinds:
        _PENDING.clear()
        _PENDING_AT = 0.0
        return False
    if _PENDING and _changed_kinds(_PENDING, sig):
        # 还在变（正在拷贝）→ 继续等它稳定
        _PENDING.clear()
        _PENDING.update(sig)
        _PENDING_AT = now
        return False
    if not _PENDING:
        _PENDING.update(sig)
        _PENDING_AT = now
        return False
    if now - _PENDING_AT < SETTLE:
        return False
    # 稳定了一个 SETTLE 周期：动作
    _SEEN.clear()
    _SEEN.update(sig)
    _PENDING.clear()
    _PENDING_AT = 0.0
    _fire(kinds)
    return True


def _loop():
    while not _STOP.is_set():
        try:
            tick()
        except Exception as e:
            try:
                applog.log("热重载巡检异常（不影响使用）：%s" % e, "WARN")
            except Exception:
                pass
        _STOP.wait(INTERVAL)


def start():
    global _THREAD
    if _THREAD and _THREAD.is_alive():
        return False
    if not _ENABLED:
        return False
    _STOP.clear()
    _THREAD = threading.Thread(target=_loop, name="hotreload", daemon=True)
    _THREAD.start()
    return True


def stop():
    _STOP.set()
    t = _THREAD
    if t and t.is_alive():
        t.join(timeout=INTERVAL + 1)
    return True


def state():
    with _LOCK:
        return {"ok": True, "enabled": _ENABLED, "gen": _GEN,
                "interval": INTERVAL, "settle": SETTLE,
                "last_at": _LAST["at"], "last_kinds": list(_LAST["kinds"]),
                "errors": list(_LAST["errors"]), "ms": _LAST["ms"],
                "watching": {k: bool(v) for k, v in _ROOTS.items()},
                "running": bool(_THREAD and _THREAD.is_alive())}


def reset():
    """自测用"""
    global _GEN, _PENDING_AT
    with _LOCK:
        _GEN = 0
        _LAST.update({"at": "", "kinds": [], "errors": [], "ms": 0})
    _SEEN.clear()
    _PENDING.clear()
    _PENDING_AT = 0.0
    _HOOKS.clear()
