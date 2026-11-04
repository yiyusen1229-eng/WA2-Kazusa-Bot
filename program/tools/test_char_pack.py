# -*- coding: utf-8 -*-
"""角色包导出 / 导入的自测（不联网、不弹窗）。

跑法：
    cd program
    build_env/venv/Scripts/python.exe tools/test_char_pack.py

验的是这条链路：
  1. 导出只带 5 类资源 + name.txt + manifest.json；sessions/、story.json、tts.json 不带
  2. 导出 → 导入 内容一致（提示词 / 世界书 / 记忆书 / 立绘 / 语音）
  3. 重名自动加序号；导入不切换当前角色
  4. 包装层（和纱/prompt/...）能剥掉
  5. 路径穿越、绝对路径、盘符条目被丢掉，不会写到 characters/ 外面
  6. 不是 zip / 空包 / 超大条目 有明确报错，且不在 characters/ 里留半个角色
"""
import json
import os
import sys
import tempfile
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROGRAM, "src"))

FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:300]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def write(path, text, binary=False):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = "wb" if binary else "w"
    with open(path, mode, **({} if binary else {"encoding": "utf-8"})) as f:
        f.write(text)
    return path


def make_character(root, cid, name="和纱"):
    """造一个「全都有」的角色：5 类资源 + 存档 + story.json + tts.json"""
    d = os.path.join(root, cid)
    write(os.path.join(d, "name.txt"), name)
    write(os.path.join(d, "prompt", "base.txt"), "人设 base")
    write(os.path.join(d, "prompt", "stage1.txt"), "阶段一")
    write(os.path.join(d, "worldbook", "worldbook.json"),
          json.dumps({"entries": [{"keys": ["冬天"], "text": "很冷"}]}, ensure_ascii=False))
    write(os.path.join(d, "memory", "standing.txt"), "常驻记忆")
    write(os.path.join(d, "portrait", "index.json"),
          json.dumps({"outfits": {"礼服": {"code": "001"}}}, ensure_ascii=False))
    write(os.path.join(d, "portrait", "礼服", "微笑.png"), b"\x89PNG\r\n\x1a\nfake", binary=True)
    write(os.path.join(d, "voice", "soft", "a.wav"), b"RIFFfakewav", binary=True)
    # 这些不该进包
    write(os.path.join(d, "sessions", "auto.json"), "{}")
    write(os.path.join(d, "story.json"), '{"enabled": false}')
    write(os.path.join(d, "tts.json"), '{"gpt": "D:/secret/model.ckpt"}')
    write(os.path.join(d, "opening.json"), '{"zh": "开场"}')
    return d


def names(zpath):
    with zipfile.ZipFile(zpath) as z:
        return sorted(i.filename for i in z.infolist() if not i.is_dir())


def main():
    tmp = tempfile.mkdtemp(prefix="wa2_pack_")
    user1 = os.path.join(tmp, "user1")
    user2 = os.path.join(tmp, "user2")
    out = os.path.join(tmp, "out")
    os.makedirs(out)
    os.makedirs(user1)
    os.makedirs(user2)

    # characters.py 用 WA2_USER_DIR 定位角色总目录（和自测/便携版一个规矩）
    os.environ["WA2_USER_DIR"] = user1
    import characters  # noqa: E402
    import char_pack   # noqa: E402

    root1 = characters.root()
    make_character(root1, "和纱")
    write(os.path.join(tmp, "tpl", "base.txt"), "模板人设")
    characters.set_seed_sources(os.path.join(tmp, "tpl"), "")

    print("== 1. 导出 ==")
    res = char_pack.export_pack("和纱", out)
    check("导出成功", res.get("ok"), res)
    zp = res.get("path") or ""
    check("zip 落在导出目录", os.path.isfile(zp), zp)
    check("文件名是角色名", os.path.basename(zp) == "和纱.zip", zp)
    got = names(zp)
    check("带 name.txt", "name.txt" in got, got)
    check("带 manifest.json", "manifest.json" in got, got)
    check("带提示词", "prompt/base.txt" in got and "prompt/stage1.txt" in got, got)
    check("带世界书", "worldbook/worldbook.json" in got, got)
    check("带记忆书", "memory/standing.txt" in got, got)
    check("带立绘 + index", "portrait/index.json" in got and "portrait/礼服/微笑.png" in got, got)
    check("带参考音频", "voice/soft/a.wav" in got, got)
    check("不带存档", not any(n.startswith("sessions/") for n in got), got)
    check("不带 story.json", "story.json" not in got, got)
    check("不带 tts.json", "tts.json" not in got, got)
    check("不带 opening.json", "opening.json" not in got, got)
    with zipfile.ZipFile(zp) as z:
        man = json.loads(z.read("manifest.json").decode("utf-8"))
        png = z.getinfo("portrait/礼服/微笑.png")
    check("manifest 格式对", man.get("format") == "wa2-char-pack", man)
    check("manifest 记了角色名", man.get("name") == "和纱", man)
    check("png 用 STORED（不再压一遍）", png.compress_type == zipfile.ZIP_STORED,
          png.compress_type)

    print("== 2. 导入（换一个用户目录）==")
    os.environ["WA2_USER_DIR"] = user2
    check("导入前角色总目录是空的", not os.path.isdir(characters.root()) or
          not os.listdir(characters.root()))
    res2 = char_pack.import_pack(zp)
    check("导入成功", res2.get("ok"), res2)
    check("id = 和纱", res2.get("id") == "和纱", res2)
    check("name.txt 回来了", os.path.isfile(os.path.join(characters.root(), "和纱", "name.txt")))
    check("提示词回来了", os.path.isfile(
        os.path.join(characters.root(), "和纱", "prompt", "base.txt")))
    check("世界书回来了", os.path.isfile(
        os.path.join(characters.root(), "和纱", "worldbook", "worldbook.json")))
    check("立绘回来了", os.path.isfile(
        os.path.join(characters.root(), "和纱", "portrait", "礼服", "微笑.png")))
    check("语音回来了", os.path.isfile(
        os.path.join(characters.root(), "和纱", "voice", "soft", "a.wav")))
    check("没带存档进来", not os.path.isdir(
        os.path.join(characters.root(), "和纱", "sessions")))
    check("没带 tts.json 进来", not os.path.isfile(
        os.path.join(characters.root(), "和纱", "tts.json")))
    check("没自动切换（active.json 没写）", not os.path.isfile(
        os.path.join(characters.root(), "active.json")))
    check("临时目录没留下", not any(n.startswith(".importing_")
                                  for n in os.listdir(characters.root())))

    print("== 3. 重名自动加序号 ==")
    res3 = char_pack.import_pack(zp)
    check("第二次导入成功", res3.get("ok"), res3)
    check("id 变成 和纱2", res3.get("id") == "和纱2", res3)
    check("两个角色都在", len(characters.list_characters()) == 2,
          characters.list_characters())

    print("== 4. 包装层（整个角色文件夹压进去）==")
    wrap = os.path.join(tmp, "wrap.zip")
    with zipfile.ZipFile(wrap, "w") as z:
        z.writestr("和纱/name.txt", "包了一层")
        z.writestr("和纱/prompt/base.txt", "包里的提示词")
        z.writestr("和纱/portrait/index.json", "{}")
    res4 = char_pack.import_pack(wrap)
    check("包装层导入成功", res4.get("ok"), res4)
    check("没有 manifest 时用包里的 name.txt 当角色名", res4.get("id") == "包了一层", res4)
    d4 = os.path.join(characters.root(), res4.get("id") or "")
    check("包装层被剥掉", os.path.isfile(os.path.join(d4, "prompt", "base.txt")), d4)
    check("包装层没被当成子目录", not os.path.isdir(os.path.join(d4, "和纱")), d4)

    print("== 5. 路径穿越 / 绝对路径被丢掉 ==")
    evil = os.path.join(tmp, "evil.zip")
    with zipfile.ZipFile(evil, "w") as z:
        z.writestr("../../evil.txt", "x")
        z.writestr("C:/Windows/evil.txt", "x")
        z.writestr("/abs/evil.txt", "x")
        z.writestr("prompt/ok.txt", "ok")
    res5 = char_pack.import_pack(evil)
    check("恶意包也能导入（只收安全的）", res5.get("ok"), res5)
    check("报出了被跳过的条目", res5.get("skipped_count", 0) >= 3, res5.get("skipped"))
    outside = os.path.join(tmp, "evil.txt")
    check("没写到 characters/ 外面", not os.path.isfile(outside), outside)

    print("== 6. 坏包 / 空包 ==")
    notzip = write(os.path.join(tmp, "notzip.zip"), "hello")
    check("不是 zip 会报错", not char_pack.import_pack(notzip).get("ok"))
    empty = os.path.join(tmp, "empty.zip")
    with zipfile.ZipFile(empty, "w") as z:
        z.writestr("readme.txt", "nothing")
    r6 = char_pack.import_pack(empty)
    check("空包会报错", not r6.get("ok"), r6)
    check("空包没留下角色", len(characters.list_characters()) == 4,
          characters.list_characters())
    check("不存在的文件会报错", not char_pack.import_pack(
        os.path.join(tmp, "nope.zip")).get("ok"))
    check("导出不存在的角色会报错", not char_pack.export_pack("没有这个", out).get("ok"))

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), ", ".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
