# -*- coding: utf-8 -*-
"""运行状态标记：判断上次是不是正常退出，崩了留现场。

约定：
- 启动时 `begin()`：先读旧标记（存在 = 上次没正常退出），再写自己的标记
- 正常退出 `end()`：删标记
- 未处理异常（主线程 / 子线程）：`install_hooks()` 写 `crash_<时间戳>.log`，
  并把最近一次自动存档复制一份，方便事后恢复

标记和崩溃日志都放在 applog 的日志目录（打包后是 exe 旁边的 logs/）。
"""
import json
import os
import shutil
import sys
import time
import traceback

import applog
import sessions

_STATE_NAME = "run_state.json"
_state = {}          # 本次运行的快照，给 /api/run/state 用


def _dir():
    try:
        return applog._log_dir()
    except Exception:
        return os.environ.get("TEMP", ".")


def _path():
    return os.path.join(_dir(), _STATE_NAME)


def _read():
    try:
        with open(_path(), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except Exception:
        return None


def begin(app="", version=""):
    """启动时调用。返回上次运行的信息；None = 第一次启动或上次正常退出。"""
    prev = _read()
    now = {"app": app, "version": version, "pid": os.getpid(),
           "started_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    try:
        os.makedirs(_dir(), exist_ok=True)
        with open(_path(), "w", encoding="utf-8") as f:
            json.dump(now, f, ensure_ascii=False, indent=1)
    except Exception as e:
        applog.log("运行状态：写标记失败 %s" % e, "WARN")
    _state.clear()
    _state.update({"dirty_exit": bool(prev), "prev": prev or {},
                   "started_at": now["started_at"]})
    if prev:
        applog.log("运行状态：上次没有正常退出（pid=%s，%s 启动）"
                   % (prev.get("pid"), prev.get("started_at")), "WARN")
    return prev


def end():
    """正常退出：删标记"""
    try:
        os.remove(_path())
    except FileNotFoundError:
        pass
    except Exception as e:
        applog.log("运行状态：删标记失败 %s" % e, "WARN")


def _autosave_path():
    try:
        p = os.path.join(sessions.SESS_DIR, "auto.json")
        return p if os.path.isfile(p) else ""
    except Exception:
        return ""


def has_autosave():
    return bool(_autosave_path())


def state():
    """给前端 / 接口看的状态"""
    return {"ok": True,
            "dirty_exit": bool(_state.get("dirty_exit")),
            "prev": _state.get("prev") or {},
            "started_at": _state.get("started_at", ""),
            "has_autosave": has_autosave(),
            "log_dir": _dir()}


def crash_log(exc_text, note=""):
    """写崩溃现场：crash_<时间戳>.log + 最近一次自动存档的副本"""
    ts = time.strftime("%Y-%m-%d_%H-%M-%S")
    d = _dir()
    p = os.path.join(d, "crash_%s.log" % ts)
    try:
        lines = ["时间: %s" % time.strftime("%Y-%m-%d %H:%M:%S"),
                 "说明: %s" % (note or "未处理异常"),
                 "pid: %s" % os.getpid(),
                 "", exc_text or ""]
        with open(p, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception as e:
        applog.log("崩溃现场：写日志失败 %s" % e, "WARN")
    src = _autosave_path()
    if src:
        try:
            shutil.copy2(src, os.path.join(d, "crash_%s_auto.json" % ts))
        except Exception as e:
            applog.log("崩溃现场：复制存档失败 %s" % e, "WARN")
    return p


def install_hooks():
    """未处理异常（主线程 + 子线程）都记成崩溃现场"""
    def _hook(exc_type, exc, tb):
        try:
            crash_log("".join(traceback.format_exception(exc_type, exc, tb)))
        except Exception:
            pass
        sys.__excepthook__(exc_type, exc, tb)

    def _thook(args):
        try:
            crash_log("".join(traceback.format_exception(
                args.exc_type, args.exc_value, args.exc_traceback)),
                note="线程 %s 未处理异常" % getattr(args.thread, "name", "?"))
        except Exception:
            pass

    sys.excepthook = _hook
    try:
        import threading
        threading.excepthook = _thook
    except Exception:
        pass
