# -*- coding: utf-8 -*-
"""睡眠 / 唤醒检测（#18 桌面行为的一部分）。

为什么不挂 WM_POWERBROADCAST：窗口消息循环在 pywebview 里面，拿不到；
引 pystray / pywin32 又只为这一件事，不值当。

原理：看**墙钟**。这个模块有个 5 秒一轮的巡检线程，机器睡着的时候它不会跑，
醒来后第一轮就会看到「距上次 > 20 秒」。正常运行时每轮只差 5 秒左右，
所以跳一下就是刚唤醒（或者系统卡了很久 —— 两种情况都该重建音频/连接）。

对外：
    start() / stop()      起停巡检线程
    tick(wall=None)       跑一次检查（自测直接喂假的墙钟）
    state()               {gen, last_gap, at, interval}
    gen()                 唤醒了多少次（前端拿它当「该重建了」的信号）
"""
import threading
import time

INTERVAL = 5.0
JUMP_S = 20.0                    # 超过这么久没跑过一轮 = 睡过 / 卡过

_LOCK = threading.Lock()
_THREAD = None
_STOP = threading.Event()
_LAST_WALL = 0.0
_GEN = 0
_STATE = {"gen": 0, "last_gap": 0.0, "at": ""}


def _now():
    return time.time()


def tick(wall=None, now=None):
    """检查一次；判定「刚唤醒」返回 True。自测喂 wall 就行。"""
    global _LAST_WALL, _GEN
    wall = _now() if wall is None else float(wall)
    with _LOCK:
        prev = _LAST_WALL
        _LAST_WALL = wall
    if not prev:
        return False                 # 第一轮只记基线
    gap = wall - prev
    with _LOCK:
        _STATE["last_gap"] = round(gap, 1)
        if gap >= JUMP_S:
            _GEN += 1
            _STATE["gen"] = _GEN
            _STATE["at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(wall))
            return True
    return False


def gen():
    with _LOCK:
        return _GEN


def state():
    with _LOCK:
        d = dict(_STATE)
    d["interval"] = INTERVAL
    d["jump_s"] = JUMP_S
    d["running"] = bool(_THREAD and _THREAD.is_alive())
    return d


def reset():
    """自测用"""
    global _LAST_WALL, _GEN
    with _LOCK:
        _LAST_WALL = 0.0
        _GEN = 0
        _STATE.update({"gen": 0, "last_gap": 0.0, "at": ""})


def _loop():
    while not _STOP.is_set():
        try:
            if tick():
                try:
                    import applog
                    applog.log("系统刚从睡眠/长卡顿恢复：通知前端重建音频与连接", "PWR")
                except Exception:
                    pass
        except Exception:
            pass
        _STOP.wait(INTERVAL)


def start():
    global _THREAD
    if _THREAD and _THREAD.is_alive():
        return False
    _STOP.clear()
    _LAST_WALL = _now()              # 记基线，免得一启动就被当成刚唤醒
    _THREAD = threading.Thread(target=_loop, name="powerwatch", daemon=True)
    _THREAD.start()
    return True


def stop():
    _STOP.set()
    t = _THREAD
    if t and t.is_alive():
        t.join(timeout=INTERVAL + 1)
    return True
