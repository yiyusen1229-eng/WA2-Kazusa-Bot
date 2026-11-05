# -*- coding: utf-8 -*-
"""翻译层（translate.py）自测：术语表 / 引擎兜底 / 清洗 / 缓存。

     cd program
     build_env/venv/Scripts/python.exe tools/test_translate.py

不联网：云端和本地两个引擎都被替换成假的，只验「选哪条路、失败了怎么办」。
"""
import json
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROGRAM, "src"))

import translate as T

FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:200]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def main():
    tmp = tempfile.mkdtemp(prefix="wa2_mt_")
    gl_path = os.path.join(tmp, "translation_glossary.json")
    with open(gl_path, "w", encoding="utf-8") as f:
        json.dump({"to_zh": {"はるき": "春希", "春树": "春希", "せつな": "雪菜"}}, f,
                  ensure_ascii=False)

    # ---------- 术语表
    g = T.glossary("zh", gl_path)
    check("读术语表", g.get("はるき") == "春希", g)
    check("不存在的方向给空", T.glossary("ja", gl_path) == {})
    check("文件不存在给空", T.glossary("zh", os.path.join(tmp, "无.json")) == {})
    check("音译错的名字纠正回来",
          T.apply_glossary("…春树，你醒了没？", "zh", gl_path) == "…春希，你醒了没？",
          T.apply_glossary("…春树，你醒了没？", "zh", gl_path))
    check("假名也能纠正",
          T.apply_glossary("…はるき、起きてるか", "zh", gl_path).startswith("…春希"),
          T.apply_glossary("…はるき、起きてるか", "zh", gl_path))
    check("没命中的句子原样返回",
          T.apply_glossary("今天有点冷", "zh", gl_path) == "今天有点冷")
    # 长键优先：同时有「春」「春树」时不能被短的先替换
    with open(gl_path, "w", encoding="utf-8") as f:
        json.dump({"to_zh": {"春": "X", "春树": "春希"}}, f, ensure_ascii=False)
    check("长键优先", T.apply_glossary("春树来了", "zh", gl_path) == "春希来了",
          T.apply_glossary("春树来了", "zh", gl_path))

    # ---------- 清洗
    check("去掉「译文：」前缀", T._clean("译文：今天很冷", "zh") == "今天很冷")
    check("去掉引号", T._clean("「今天很冷」", "zh") == "今天很冷")
    check("多行只留第一行", T._clean("今天很冷\n（解释）", "zh") == "今天很冷")
    check("日文方向只认带假名的行", T._clean("（thinking）\nおはよう", "ja") == "おはよう",
          T._clean("（thinking）\nおはよう", "ja"))
    check("日文方向没有假名就算失败", T._clean("中文解释", "ja") == "")

    # ---------- 引擎兜底（两个引擎都用假的）
    calls = {"cloud": 0, "local": 0}
    orig_cloud, orig_local, orig_prov = T._cloud_raw, T._local_raw, T.provider
    orig_cache = dict(T.CACHE)
    try:
        T.CACHE.clear()

        def fake_cloud(text, p="zh"):
            calls["cloud"] += 1
            ok = "GOOD" in text
            return ("云端译文" if ok else ""), ("" if ok else "云端返回空")

        def fake_local(text, p="zh"):
            calls["local"] += 1
            return "本地译文"

        T._cloud_raw, T._local_raw = fake_cloud, fake_local

        T.provider = lambda: "cloud"
        check("云端优先，云端成功就不碰本地",
              T.translate("这句GOOD", "zh") == "云端译文" and calls["local"] == 0, calls)

        T.CACHE.clear()
        calls.update(cloud=0, local=0)
        out = T.translate("这句没有", "zh")
        check("云端返回空 → 回落本地", out == "本地译文" and calls["local"] == 1, (out, calls))

        T.CACHE.clear()
        calls.update(cloud=0, local=0)
        T.provider = lambda: "local"
        out = T.translate("本地先行", "zh")
        check("provider=local 时先本地", out == "本地译文" and calls["local"] == 1, (out, calls))
        check("本地成功就不问云端", calls["cloud"] == 0, calls)

        T.CACHE.clear()
        T.provider = lambda: "cloud"
        T._cloud_raw = lambda t, p="zh": ("", "挂了")
        T._local_raw = lambda t, p="zh": ""
        check("两边都失败给空串", T.translate("没救", "zh") == "")
        check("空输入直接空", T.translate("", "zh") == "")

        # 缓存
        T.CACHE.clear()
        calls.update(cloud=0, local=0)
        T._cloud_raw, T._local_raw = fake_cloud, fake_local
        T.translate("缓存这句ok", "zh")
        T.translate("缓存这句ok", "zh")
        check("同一句只翻一次（缓存）", calls["cloud"] == 1, calls)
    finally:
        T._cloud_raw, T._local_raw, T.provider = orig_cloud, orig_local, orig_prov
        T.CACHE.clear()
        T.CACHE.update(orig_cache)

    # ---------- provider 读取顺序
    os.environ.pop("WA2_MT_PROVIDER", None)
    check("没配 key 时自动选本地", T.provider() in ("local", "cloud"), T.provider())
    os.environ["WA2_MT_PROVIDER"] = "local"
    check("环境变量能强制本地", T.provider() == "local", T.provider())
    os.environ["WA2_MT_PROVIDER"] = "cloud"
    check("环境变量能强制云端", T.provider() == "cloud", T.provider())
    os.environ.pop("WA2_MT_PROVIDER", None)

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), " / ".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
