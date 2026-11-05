# -*- coding: utf-8 -*-
"""日志保留 + 诊断包的自测（#15，不联网、不开界面）。

跑法：
    cd program
    build_env/venv/Scripts/python.exe tools/test_logpack.py

验的是：
  1. 脱敏：密钥、对话/朗读查询串、用户目录、其它绝对路径
  2. 按天清理：过期删、近期留、正在写的那个不删、dry-run 不删、崩溃现场只留 10 份
  3. 诊断包：结构齐全（版本 / 日志 / 素材报告 / 运行状态 / 调试状态 / 配置摘要）
  4. 默认**不含**对话原文；`turns=2` 才带，而且带之前每段都脱敏
  5. 包里任何地方都没有真 key、决定不外传的对话原文、用户名
  6. README 写清楚包含什么、脱敏做了什么、含对话时的风险提示
"""
import datetime
import json
import os
import re
import sys
import tempfile
import time
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROGRAM, "src"))

_TMP = tempfile.mkdtemp(prefix="wa2_logpack_test_")
os.environ["WA2_CACHE_DIR"] = os.path.join(_TMP, "cache")
os.environ["WA2_SESS_DIR"] = os.path.join(_TMP, "sessions")
os.environ["WA2_LOG_KEEP_DAYS"] = "14"

import applog     # noqa: E402
import logpack    # noqa: E402

FAILS = []
SECRET = "sk-REALKEY1234567890"
SECRET_TEXT = "这是绝不该外传的台词"
USER_HOME = os.path.expanduser("~")


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:220]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def unzip_texts(path):
    out = {}
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            out[n] = z.read(n).decode("utf-8", "replace")
    return out


def main():
    # ---------------------------------------------------------------- 1 脱敏
    s = logpack.scrub("key=%s 换一个 Bearer abcdefghijk123" % SECRET)
    check("密钥被抹掉", SECRET not in s and "abcdefghijk123" not in s, s)
    s = logpack.scrub('GET /api/text?text=%s&w=600 -> 200' % SECRET_TEXT)
    check("字模查询串被隐藏（对话内容不落日志）",
          SECRET_TEXT not in s and "<已隐藏>" in s, s)
    s = logpack.scrub("GET /api/tts?text=%s&lang=ja -> 200" % SECRET_TEXT)
    check("语音查询串被隐藏", SECRET_TEXT not in s and "<已隐藏>" in s, s)
    s = logpack.scrub(r"打开 C:\Users\someuser\AppData\Local\Temp\wa2\x.log 失败")
    check("用户目录被替换", "someuser" not in s and "%USERPROFILE%" in s, s)
    check("文件名还留着（排查要用）", "x.log" in s, s)
    s = logpack.scrub(r"读 D:\games\wa2\logs\app-20261105.log 失败")
    check("其它盘符路径只留文件名", "games" not in s and "app-20261105.log" in s, s)
    s = logpack.scrub("/home/alice/project/x.py 报错")
    check("Linux 用户目录也被替换", "alice" not in s, s)
    plain = "心跳: 线程 3 个, 内存 120 MB"
    check("普通文本不动", logpack.scrub(plain) == plain, logpack.scrub(plain))
    check("None 不炸", logpack.scrub(None) == "", repr(logpack.scrub(None)))

    # ---------------------------------------------------------------- 2 清理
    d = tempfile.mkdtemp(prefix="wa2_logs_")
    today = datetime.date.today()
    for days in (0, 3, 40):
        day = (today - datetime.timedelta(days=days)).strftime("%Y%m%d")
        with open(os.path.join(d, "app-%s.log" % day), "w", encoding="utf-8") as f:
            f.write("x" * 100)
    for i in range(12):
        with open(os.path.join(d, "crash_2026-11-05_12-00-%02d.log" % i), "w", encoding="utf-8") as f:
            f.write("boom")
    # 性能采样 csv（#14）也跟着同一个保留天数滚
    for days in (0, 40):
        day = (today - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
        with open(os.path.join(d, "perf-%s.csv" % day), "w", encoding="utf-8") as f:
            f.write("ts,round\n")
            f.write("2026-11-05 12:00:00,1\n")

    r = logpack.prune(keep_days=14, d=d, dry=True)
    check("dry-run 只报不删", len(r["removed"]) >= 1 and
          len([f for f in os.listdir(d) if f.startswith("app-")]) == 3, r)

    r = logpack.prune(keep_days=14, d=d)
    names = sorted(f for f in os.listdir(d) if f.startswith("app-"))
    check("过期日志被删", len(names) == 2, names)
    check("近期的留着", any((today - datetime.timedelta(days=3)).strftime("%Y%m%d") in n for n in names), names)
    check("今天的留着", os.path.join(d, "app-%s.log" % today.strftime("%Y%m%d")) in
          [os.path.join(d, n) for n in names])
    crashes = [f for f in os.listdir(d) if f.startswith("crash_")]
    check("崩溃现场只留 %d 份" % logpack.CRASH_KEEP, len(crashes) == logpack.CRASH_KEEP, len(crashes))
    perfs = sorted(f for f in os.listdir(d) if f.startswith("perf-"))
    check("性能采样 csv 也按天数滚（只留今天的）", len(perfs) == 1, perfs)
    check("清理返回释放字节数", r["freed"] > 0, r)

    # 正在写的那个永远不删
    very_old = today - datetime.timedelta(days=90)
    p_old = os.path.join(d, "app-%s.log" % very_old.strftime("%Y%m%d"))
    with open(p_old, "w", encoding="utf-8") as f:
        f.write("active")
    orig_path = applog.path
    applog.path = lambda: p_old
    try:
        logpack.prune(keep_days=7, d=d)
    finally:
        applog.path = orig_path
    check("正在写的日志不删（哪怕日期很旧）", os.path.isfile(p_old))

    # ---------------------------------------------------------------- 3/4/5 诊断包
    exe = tempfile.mkdtemp(prefix="wa2_exe_")
    with open(os.path.join(exe, "prefs.json"), "w", encoding="utf-8") as f:
        json.dump({"volMaster": 80, "apiKey": SECRET, "rightClick": "save"}, f)
    with open(os.path.join(exe, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"api_key": SECRET, "base_url": "https://api.example.com", "model": "m1"}, f)

    d2 = tempfile.mkdtemp(prefix="wa2_logs2_")
    with open(os.path.join(d2, "app-%s.log" % today.strftime("%Y%m%d")), "w", encoding="utf-8") as f:
        f.write("===== 启动 =====\n")
        f.write("[12:00:00] [ +0.10s] [REQ  ] [MainThread] GET /api/text?text=%s -> 200\n" % SECRET_TEXT)
        f.write("[12:00:01] [ +1.10s] [REQ  ] [MainThread] GET /api/tts?text=%s&lang=ja -> 200\n" % SECRET_TEXT)
        f.write("[12:00:02] [ +2.10s] [ERROR] [MainThread] 打开 %s\n" % os.path.join(USER_HOME, "logs", "x.log"))
        f.write("[12:00:03] [ +3.10s] [WARN ] [MainThread] key=%s\n" % SECRET)
    with open(os.path.join(d2, "asset_report.json"), "w", encoding="utf-8") as f:
        json.dump({"ok": True, "checked": 3, "assets_dir": "D:/games/assets"}, f)
    with open(os.path.join(d2, "run_state.json"), "w", encoding="utf-8") as f:
        json.dump({"pid": 1234, "started_at": "2026-11-05 12:00:00"}, f)
    with open(os.path.join(d2, "perf-%s.csv" % today.strftime("%Y-%m-%d")), "w", encoding="utf-8") as f:
        f.write("ts,round,rss_mb,handles\n")
        f.write("2026-11-05 12:00:00,20,180,540\n")

    sess = os.path.join(_TMP, "sessions")
    os.makedirs(sess, exist_ok=True)
    msgs = []
    for i in range(6):
        if i % 2 == 0:
            msgs.append({"role": "user", "content": "%s %d" % (SECRET_TEXT, i)})
        else:
            # 故意把密钥和本机路径写进对话：选了「含对话」也不该把它们带出去
            msgs.append({"role": "assistant",
                         "content": "「%s %d，顺便测 %s 和 %s」" % (SECRET_TEXT, i, SECRET,
                                                              os.path.join(USER_HOME, "x.log"))})
    with open(os.path.join(sess, "auto.json"), "w", encoding="utf-8") as f:
        json.dump({"slot": "auto", "time": "2026-11-05 12:00", "messages": msgs}, f, ensure_ascii=False)

    res = logpack.bundle(include_turns=0, out_dir=d2, d=d2, exe_dir=exe)
    check("诊断包生成成功", res.get("ok") and os.path.isfile(res["path"]), res)
    names = unzip_texts(res["path"])
    check("有 README", "README.txt" in names, list(names))
    check("有版本信息", "version.json" in names and "python" in names["version.json"], list(names))
    check("有日志", any(n.startswith("logs/app-") for n in names), list(names))
    check("有素材报告", "asset_report.json" in names)
    check("有运行状态", "run_state.json" in names)
    check("有性能采样 csv（#14）",
          any(n.startswith("logs/perf-") and n.endswith(".csv") for n in names), list(names))
    check("有调试状态", "diag_state.json" in names and "modules" in names["diag_state.json"])
    check("有配置摘要", "config_summary.json" in names and "prefs" in names["config_summary.json"],
          names.get("config_summary.json"))
    check("默认不含对话原文", "conversation.json" not in names, list(names))
    check("README 说明了默认不含对话", "默认不含对话原文" in names["README.txt"], names["README.txt"][:80])

    blob = "\n".join(names.values())
    check("包里没有真 key", SECRET not in blob)
    check("包里没有「完整的密钥形状」（掩码 sk-****abcd 不算）",
          re.search(r"sk-[A-Za-z0-9_\-]{6,}", blob) is None,
          (re.search(r"sk-[A-Za-z0-9_\-]{6,}", blob) or [""])[0] if re.search(r"sk-[A-Za-z0-9_\-]{6,}", blob) else "")
    check("包里有 key 掩码", "****" in blob)
    check("包里没有用户目录", USER_HOME not in blob and "someuser" not in blob.lower())
    check("日志里的对话查询串已隐藏", SECRET_TEXT not in blob)

    # 带对话
    res2 = logpack.bundle(include_turns=2, out_dir=d2, d=d2, exe_dir=exe)
    names2 = unzip_texts(res2["path"])
    check("turns=2 时带 conversation.json", "conversation.json" in names2, list(names2))
    conv = json.loads(names2["conversation.json"])
    check("只带最近 2 轮（4 条）", len(conv.get("messages") or []) == 4, len(conv.get("messages") or []))
    conv_blob = json.dumps(conv, ensure_ascii=False)
    check("对话正文保留（用户明确选择要带）", SECRET_TEXT in conv_blob)
    check("对话里的密钥仍被抹掉", SECRET not in conv_blob)
    check("对话里的本机路径仍被抹掉", USER_HOME not in conv_blob, conv_blob[:120])
    check("README 里有风险提示", "包含最近 2 轮对话原文" in names2["README.txt"], names2["README.txt"][:200])
    check("返回值提示含对话", res2.get("include_turns") == 2 and "对话" in res2.get("note", ""), res2)

    # turns 上限夹取
    res3 = logpack.bundle(include_turns=999, out_dir=d2, d=d2, exe_dir=exe)
    check("turns 被夹到 200", res3.get("include_turns") == 200, res3.get("include_turns"))

    # 空目录也能出包（没有日志 / 没有配置）
    empty = tempfile.mkdtemp(prefix="wa2_empty_")
    res4 = logpack.bundle(d=empty, out_dir=empty, exe_dir=empty)
    check("没有日志也能出包（有 README + 版本）", res4.get("ok") and
          set(unzip_texts(res4["path"])) >= {"README.txt", "version.json"}, res4.get("items"))

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), " / ".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
