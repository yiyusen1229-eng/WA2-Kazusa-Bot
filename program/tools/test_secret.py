# -*- coding: utf-8 -*-
"""密钥与日志脱敏的自测（不联网、不启动程序）。

跑法：
    cd program
    build_env/venv/Scripts/python.exe tools/test_secret.py

验的是：
  1. 环境变量优先级：WA2_API_KEY > DEEPSEEK_API_KEY > config.json
  2. 掩码：只露前缀 3 位 + 末 4 位；短 key 全遮
  3. redact：sk- / Bearer / "api_key": "..." 都被抹掉，普通文本不动
  4. applog 写日志时自动脱敏
  5. apply_env 不改原 dict；没有环境变量时原样返回（文件里的 key 不被清掉）
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROGRAM, "src"))

import secret          # noqa: E402
import applog          # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:300]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def clean_env():
    for k in secret.ENV_KEYS:
        os.environ.pop(k, None)


def main():
    print("== 1. 环境变量优先级 ==")
    clean_env()
    check("都没有 → 空串", secret.env_key() == "")
    os.environ["DEEPSEEK_API_KEY"] = "sk-from-deepseek-env"
    check("DEEPSEEK_API_KEY 生效", secret.env_key() == "sk-from-deepseek-env", secret.env_key())
    os.environ["WA2_API_KEY"] = "sk-from-wa2-env"
    check("WA2_API_KEY 优先", secret.env_key() == "sk-from-wa2-env", secret.env_key())
    os.environ["WA2_API_KEY"] = "   "
    check("空白环境变量不算数", secret.env_key() == "sk-from-deepseek-env", secret.env_key())

    print("== 2. apply_env ==")
    clean_env()
    base = {"api_key": "sk-file-key", "model": "deepseek-flash"}
    same = secret.apply_env(base)
    check("没有环境变量 → 原样返回", same is base and same["api_key"] == "sk-file-key")
    os.environ["WA2_API_KEY"] = "sk-env-key-123456"
    got = secret.apply_env(base)
    check("有环境变量 → 覆盖", got["api_key"] == "sk-env-key-123456", got)
    check("标了 key_from_env", got.get("key_from_env") is True, got)
    check("原 dict 没被改", base["api_key"] == "sk-file-key", base)

    print("== 3. 掩码 ==")
    check("长 key 留前 3 后 4",
          secret.mask("sk-abcdefghijklmnop") == "sk-****mnop",
          secret.mask("sk-abcdefghijklmnop"))
    check("短 key 全遮", secret.mask("short") == "****", secret.mask("short"))
    check("空 key 还是空", secret.mask("") == "")
    check("认出掩码", secret.is_masked("sk-****mnop") is True)
    check("认出界面上的圆点", secret.is_masked("\u2022\u2022\u2022\u2022") is True)
    check("真 key 不算掩码", secret.is_masked("sk-abcdefghijklmnop") is False)

    print("== 4. redact ==")
    check("sk- 抹掉",
          secret.redact("key=sk-abcdef1234567890") == "key=****",
          secret.redact("key=sk-abcdef1234567890"))
    check("Bearer 抹掉值",
          secret.redact("Authorization: Bearer abcdefgh12345678") ==
          "Authorization: Bearer ****",
          secret.redact("Authorization: Bearer abcdefgh12345678"))
    check("json 里的 api_key 抹掉",
          secret.redact('{"api_key": "abcdef1234567890xyz"}') ==
          '{"api_key": "****"}',
          secret.redact('{"api_key": "abcdef1234567890xyz"}'))
    check("普通文本不动",
          secret.redact("今天很冷，她说「走吧」") == "今天很冷，她说「走吧」")
    check("task-master 不被误伤",
          secret.redact("task-master 跑完了") == "task-master 跑完了",
          secret.redact("task-master 跑完了"))
    check("None 原样返回", secret.redact(None) is None)

    print("== 5. applog 自动脱敏 ==")
    old = applog._FILE
    buf = io.StringIO()
    applog._FILE = buf
    try:
        applog.log("调用失败 Authorization: Bearer abcdefgh12345678", "ERROR")
        applog.log("key=sk-abcdef1234567890")
        text = buf.getvalue()
    finally:
        applog._FILE = old
    check("日志里没有 sk-", "sk-abcdef" not in text, text)
    check("日志里没有 Bearer 真值", "abcdefgh12345678" not in text, text)
    check("日志行还在", "调用失败" in text and "key=" in text, text)

    clean_env()
    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), ", ".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
