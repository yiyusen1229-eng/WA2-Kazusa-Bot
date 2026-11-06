# -*- coding: utf-8 -*-
"""#18 真机验收：开**真的主窗口**，用 HTTP 驱动置顶 / 不透明 / 穿透 / 夹回，再关掉。

为什么不用合成窗口：`SetWindowPos(HWND_TOPMOST)` 对程序自己造的离屏窗口不落样式位，
只有真实、可见、被合成的窗口才能验出「是不是真的浮在最上面」。

    cd program && .\\build_env\\venv\\Scripts\\python.exe tools\\test_desktop_app.py

⚠️ 会短暂弹出主程序窗口（约 10 秒），验完自动关闭。
"""
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
PORT = 8801
FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:220]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def get(action, **params):
    q = "/api/window?action=" + action
    for k, v in params.items():
        q += "&%s=%s" % (k, v)
    with urllib.request.urlopen("http://127.0.0.1:%d%s" % (PORT, q), timeout=8) as r:
        return json.loads(r.read().decode("utf-8"))


def wait_up(secs=40):
    t0 = time.time()
    while time.time() - t0 < secs:
        try:
            get("state")
            return True
        except Exception:
            time.sleep(0.5)
    return False


def main():
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["WA2_SESS_DIR"] = os.path.join(PROGRAM, "work_scratch", "sess_desktop")
    os.makedirs(env["WA2_SESS_DIR"], exist_ok=True)
    proc = subprocess.Popen([sys.executable, "main.py", "--port", str(PORT)],
                            cwd=os.path.join(PROGRAM, "build_env"), env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not wait_up():
            print("窗口没起来（端口 %d 没响应）" % PORT)
            return 1
        print("主窗口已起，开始验\n")

        print("[1] 置顶")
        st = get("state")
        check("state 里有 topmost 字段", "topmost" in st, st)
        r = get("topmost", on=1)
        check("topmost on 返回 ok", r.get("ok"), r)
        time.sleep(0.4)
        check("state 读回去是置顶", get("state").get("topmost") is True, get("state"))
        r = get("topmost", on=0)
        time.sleep(0.3)
        check("能撤掉置顶", get("state").get("topmost") is False, get("state"))

        print("[2] 不透明度")
        r = get("alpha", v=180)
        check("设 180 返回 ok", r.get("ok") and r.get("alpha") == 180, r)
        check("state 读回 180", get("state").get("alpha") == 180, get("state"))
        r = get("alpha", v=255)
        check("回到 255", r.get("alpha") == 255, r)

        print("[3] 点击穿透")
        r = get("clickthrough", on=1)
        check("开穿透返回 ok", r.get("ok") and r.get("click_through") is True, r)
        check("state 读回穿透", get("state").get("click_through") is True, get("state"))
        r = get("clickthrough", on=0)
        check("能关掉穿透（不然窗口就废了）",
              r.get("ok") and get("state").get("click_through") is False, r)

        print("[4] 多显示器 / 夹回")
        r = get("workarea")
        check("拿得到工作区", r.get("ok") and len(r.get("workarea") or []) == 4, r)
        r = get("clamp")
        check("clamp 不报错", r.get("ok"), r)

        print("[5] 结束时把窗口恢复原样")
        get("alpha", v=255)
        get("topmost", on=0)
        get("clickthrough", on=0)
        check("收尾后不是穿透", get("state").get("click_through") is False)
    finally:
        try:
            get("close")
        except Exception:
            pass
        time.sleep(1.0)
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=8)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), "、".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
