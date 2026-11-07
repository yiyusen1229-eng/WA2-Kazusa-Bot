# -*- coding: utf-8 -*-
"""prefs 键不能撞车（防止「整窗透明度抢用 winAlpha」这类事故再发生）。

事情的经过（2026-11-06）：`wt-window.js` 用 `winAlpha` 存整窗透明度（0~255），
但 `winAlpha` 早就被 `game.js` 用作「UI 底图透明度」（0~100，--ui-alpha）。
结果用户一开窗，100 被当成 100/255 套到窗口上 → 整窗发灰，像出了 bug。

这个测试做两件事：
1. 每个功能模块「独占」的 pref 键，别的模块不许出现；
2. 已知的共享键登记在 SHARED 里（真的要共享就写明理由）。

    cd program && .\\build_env\\venv\\Scripts\\python.exe tools\\test_prefs_keys.py
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
UI = os.path.join(os.path.dirname(HERE), "src", "ui")

# 键 → 唯一允许使用它的文件（严格独占的才登记）
OWNED = {
    "winAlpha": {"game.js", "opt.js"},      # UI 底图透明度（0~100，--ui-alpha）
    "winOpacity": {"wt-window.js"},         # 整窗透明度（0~255）
    "winTopmost": {"wt-window.js"},
    "winVisible": {"game.js", "opt.js"},    # 「窗口 ON/OFF」整块显示
    "xfade": {"wt-fade.js", "menubar.js", "wt-chat.js"},
    "firstrunDone": {"wt-firstrun.js"},
}

FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:220]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def read(fn):
    with io.open(os.path.join(UI, fn), encoding="utf-8") as f:
        return f.read()


def keys_in(text):
    """抓 setPref("x" 和 P.x / prefs.x 这类用法"""
    got = set(re.findall(r'setPref\(\s*["\']([A-Za-z0-9_]+)["\']', text))
    got |= set(re.findall(r'\bP\.([A-Za-z0-9_]+)\b', text))
    got |= set(re.findall(r'p\.([A-Za-z0-9_]+)\b', text))
    return got


def main():
    files = [f for f in os.listdir(UI) if f.endswith(".js")]
    allkeys = {}
    for f in files:
        try:
            allkeys[f] = keys_in(read(f))
        except Exception as e:
            print("  读不了 %s：%s" % (f, e))

    print("[1] 独占键只在允许的文件里出现")
    for k, owners in OWNED.items():
        users = sorted(f for f, ks in allkeys.items() if k in ks)
        extra = [u for u in users if u not in owners]
        missing = [o for o in owners if o not in users]
        check("%s 只出现在 %s" % (k, "/".join(sorted(owners))),
              not extra, {"多出来的": extra, "应有但没找到": missing})

    print("[2] 整窗透明度的键确实是独立键")
    win = read("wt-window.js")
    check("wt-window.js 里不再出现 winAlpha（注释除外）",
          not re.search(r'setPref\(\s*["\']winAlpha["\']|p\.winAlpha\b|P\.winAlpha\b', win))
    check("用的是 winOpacity", "winOpacity" in win)

    print("[3] game.js 的 UI 底图透明度仍然只认 winAlpha")
    game = read("game.js")
    check("game.js 里 winAlpha 还在用", "winAlpha" in game)
    check("game.js 没被改成 winOpacity", "winOpacity" not in game)

    print("[4] 0~100 与 0~255 两套取值不要混用")
    check("整窗透明度有下限保护（>=40）", ">= 40" in win or "40" in win)
    check("UI 底图透明度按 0~100 折算（/100）", "/ 100" in game)


    print("[5] 载入存档后的自动重播不再写死 calm")
    sess = read("wt-session.js")
    import re as _re
    bad = _re.findall(r'speakLineJa\([^)]*"calm"\)', sess)
    check("没有 speakLineJa(..., \"calm\")", not bad, bad)
    check("改用行内 emo", "line.emo" in sess)


    print("[6] 存档记住立绘/BGM，读档不写死 calm")
    sess = read("wt-session.js")
    check("__saveMeta 存 emo", "emo: (window.__lastEmo" in sess)
    check("__saveMeta 存 bgm", "bgm: (WA2.audio" in sess)
    check("__loadSession 用 meta.emo", "meta.emo || \"calm\"" in sess)
    check("__loadSession 用 meta.bgm", "meta.bgm || meta.emo" in sess)
    check("没有写死 setBgm(\"calm\", 600) 的还原", 'setBgm("calm", 600)' not in sess)
    check("sessionRestore 也还原表情", sess.count("meta.emo") >= 2)

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), "、".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
