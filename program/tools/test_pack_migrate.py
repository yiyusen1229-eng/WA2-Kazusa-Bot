# -*- coding: utf-8 -*-
"""角色包规范 / 迁移工具自测（#22）。

验的是「脏包能不能被修干净、修完能不能真的导入」——不是只看函数返回 True。

    cd program && .\\build_env\\venv\\Scripts\\python.exe tools\\test_pack_migrate.py
"""
import io
import json
import os
import shutil
import sys
import tempfile
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROGRAM, "src"))
sys.path.insert(0, HERE)

# 必须在 import characters 之前改用户目录，否则会去动真实角色文件夹
TMP = tempfile.mkdtemp(prefix="wa2_packtest_")
os.environ["WA2_USER_DIR"] = TMP
os.environ["WA2_SESS_DIR"] = os.path.join(TMP, "sessions")

import char_pack  # noqa: E402
import characters  # noqa: E402
import char_pack_migrate as mig  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:220]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def make_dirty_pack(path):
    """造一个「什么毛病都有」的包：

    - 多包了一层目录（雪见/prompt/...）
    - 没有 manifest.json
    - prompt 里混了 .bak 和 .bak-20261105-2015
    - standing.json 带着私人进度
    - 塞了白名单外的东西（config.json、sessions/1.json）
    - 有一条 ../ 穿越路径
    """
    ent = [
        ("雪见/name.txt", "雪见".encode("utf-8")),
        ("雪见/prompt/base.txt", "你是雪见。".encode("utf-8")),
        ("雪见/prompt/base.txt.bak", "旧版人设（私人）".encode("utf-8")),
        ("雪见/prompt/stage1.txt.bak-20261105-2015", "更旧的人设".encode("utf-8")),
        ("雪见/worldbook/worldbook.json",
         json.dumps({"entries": [{"name": "冬木堂", "keywords": ["书店"],
                                  "content": "旧书店"}]}, ensure_ascii=False).encode("utf-8")),
        ("雪见/memory/standing.json", json.dumps({
            "version": 1, "fixed": "雪见，店员。",
            "relation_summary": "他说了很私人的事" * 5,
            "stage": 4, "updated_at": "2026-11-01", "source_msgs": 81,
        }, ensure_ascii=False).encode("utf-8")),
        ("雪见/config.json", b'{"api_key": "sk-should-not-ship"}'),
        ("雪见/sessions/1.json", b'{"messages": []}'),
        ("雪见/../evil.txt", b"path traversal"),
    ]
    with zipfile.ZipFile(path, "w") as z:
        for n, data in ent:
            z.writestr(n, data)


def main():
    work = os.path.join(TMP, "work")
    os.makedirs(work, exist_ok=True)
    dirty = os.path.join(work, "dirty.zip")
    fixed = os.path.join(work, "fixed.zip")
    make_dirty_pack(dirty)

    print("[1] 检查脏包：该报的都报了")
    mig.PROBLEM[:] = []
    mig.NOTE[:] = []
    ok, info = mig.inspect(dirty)
    text = " / ".join(mig.NOTE + mig.PROBLEM)
    check("识别出包装目录", info["wrapper"] == "雪见", info["wrapper"])
    check("列出 .bak 垃圾", len(info["junk"]) == 2, info["junk"])
    check("列出白名单外条目", len(info["stray"]) >= 2, info["stray"])
    check("指出 standing 带私人进度", len(info["standing_private"]) == 3,
          info["standing_private"])
    check("提示没有 manifest", "manifest" in text, text)
    check("提到穿越路径不安全", "不安全" in text or "路径" in text, text)

    print("[2] --fix 修干净")
    rc = mig.fix(dirty, fixed)
    check("fix 返回 0", rc == 0, rc)
    mig.PROBLEM[:] = []
    mig.NOTE[:] = []
    ok2, info2 = mig.inspect(fixed)
    check("修完没有垃圾了", not info2["junk"], info2["junk"])
    check("修完没有白名单外条目", not info2["stray"], info2["stray"])
    check("修完有 manifest", (info2["manifest"] or {}).get("format") == char_pack.FORMAT,
          info2["manifest"])
    check("修完 standing 已脱敏", not info2["standing_private"], info2["standing_private"])
    check("修完没有包装目录", info2["wrapper"] == "", info2["wrapper"])
    with zipfile.ZipFile(fixed) as z:
        names = z.namelist()
        st = json.loads(z.read("memory/standing.json").decode("utf-8"))
    check("包里没有 config.json", not any(n.endswith("config.json") for n in names), names)
    check("包里没有 sessions", not any("/sessions/" in n for n in names), names)
    check("relation_summary 清空", st.get("relation_summary") == "", st.get("relation_summary"))
    check("stage 回 1", st.get("stage") == 1, st.get("stage"))
    check("source_msgs 归零", st.get("source_msgs") == 0, st.get("source_msgs"))
    check("fixed 保留", st.get("fixed") == "雪见，店员。", st.get("fixed"))

    print("[3] 修完能真的导入")
    res = char_pack.import_pack(fixed)
    check("导入成功", res.get("ok"), res)
    cid = res.get("id") or ""
    cdir = os.path.join(characters.root(), cid)
    check("角色文件夹建出来了", os.path.isdir(cdir), cdir)
    check("显示名是雪见", characters.display_name(cid) == "雪见", characters.display_name(cid))
    base = os.path.join(cdir, "prompt", "base.txt")
    check("prompt/base.txt 在", os.path.isfile(base))
    if os.path.isfile(base):
        with io.open(base, encoding="utf-8") as f:
            check("人设内容没被 .bak 覆盖", f.read().strip() == "你是雪见。")
    for junk in ("base.txt.bak", "stage1.txt.bak-20261105-2015"):
        check("导入后没有 " + junk, not os.path.exists(os.path.join(cdir, "prompt", junk)))

    print("[4] --from-dir 从散文件夹打包")
    exdir = os.path.join(PROGRAM, "..", "other", "docs", "examples", "min_pack", "雪见")
    exdir = os.path.normpath(exdir)
    if os.path.isdir(exdir):
        out = os.path.join(work, "fromdir.zip")
        rc = mig.from_dir(exdir, out)
        check("from-dir 返回 0", rc == 0, rc)
        mig.PROBLEM[:] = []
        mig.NOTE[:] = []
        ok3, info3 = mig.inspect(out)
        check("打出来的包能被检查通过", ok3, mig.PROBLEM)
        check("条目数与源一致", info3["entries"] == 7, info3["entries"])
        check("清单 id 是雪见", (info3["manifest"] or {}).get("id") == "雪见",
              info3["manifest"])
    else:
        check("示例源目录存在", False, exdir)

    print("[5] 烂输入不炸")
    check("不是 zip → 报错不抛异常", mig.report(os.path.join(work, "nope.zip")) == 1)
    bogus = os.path.join(work, "bogus.zip")
    with io.open(bogus, "wb") as f:
        f.write(b"not a zip at all")
    mig.PROBLEM[:] = []
    mig.NOTE[:] = []
    ok4, _ = mig.inspect(bogus)
    check("非 zip 返回 False", ok4 is False)
    empty = os.path.join(work, "empty.zip")
    with zipfile.ZipFile(empty, "w") as z:
        z.writestr("readme.txt", b"nothing here")
    mig.PROBLEM[:] = []
    mig.NOTE[:] = []
    ok5, _ = mig.inspect(empty)
    check("没有角色内容的包判为不合格", ok5 is False)

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), "、".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
