# -*- coding: utf-8 -*-
"""角色包检查 / 修复 / 从文件夹打包（#22 迁移工具）。

    cd program
    python tools/char_pack_migrate.py --check  某个角色包.zip
    python tools/char_pack_migrate.py --fix    某个角色包.zip --out 修好的.zip
    python tools/char_pack_migrate.py --from-dir .\\我的角色 --out 我的角色.zip

--check 只读：报告缺什么、脏在哪（不写任何文件）。
--fix 重打一个干净包：补 manifest、扔掉白名单外的条目和 .bak，脱敏 standing.json。
--from-dir 自己写角色时最方便：源目录按规范布局，直接出包（同样会脱敏+过滤）。

规范见 other/docs/角色包规范.md。
"""
import argparse
import io
import json
import os
import shutil
import sys
import tempfile
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import char_pack  # noqa: E402

PACK_DIRS = char_pack.PACK_DIRS
PACK_FILES = char_pack.PACK_FILES
MANIFEST = char_pack.MANIFEST
MAX_ENTRY = char_pack.MAX_ENTRY
MAX_TOTAL = char_pack.MAX_TOTAL
MAX_ENTRIES = char_pack.MAX_ENTRIES

PROBLEM = []
NOTE = []


def bad(msg):
    PROBLEM.append(msg)


def note(msg):
    NOTE.append(msg)


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return "%.1f%s" % (n, unit)
        n /= 1024.0


# ------------------------------------------------------------------ 检查
def inspect(zip_path):
    """返回 (ok, 报告字典)；同时把问题记进 PROBLEM / NOTE"""
    info = {"path": zip_path, "entries": 0, "bytes": 0, "dirs": {}, "manifest": None,
            "junk": [], "stray": [], "has_prompt": False, "standing_private": [],
            "wrapper": "", "bad_paths": []}
    if not os.path.isfile(zip_path):
        bad("文件不存在：%s" % zip_path)
        return False, info
    if not zipfile.is_zipfile(zip_path):
        bad("不是有效的 zip：%s" % zip_path)
        return False, info
    with zipfile.ZipFile(zip_path) as z:
        infos = z.infolist()
        info["entries"] = len(infos)
        if len(infos) > MAX_ENTRIES:
            bad("条目太多：%d（上限 %d）" % (len(infos), MAX_ENTRIES))

        names, total = [], 0
        for i in infos:
            if i.is_dir():
                continue
            total += i.file_size
            if i.file_size > MAX_ENTRY:
                bad("单文件太大：%s（%s）" % (i.filename, human(i.file_size)))
            safe = char_pack._safe_rel(i.filename)
            if not safe:
                info["bad_paths"].append(i.filename)
                bad("路径不安全，会被拒绝：%s" % i.filename)
            else:
                names.append(safe)
        info["bytes"] = total
        if total > MAX_TOTAL:
            bad("解压后总量超限：%s（上限 %s）" % (human(total), human(MAX_TOTAL)))

        if info["bad_paths"]:
            pass
        prefix = char_pack._wrapper_dir(names)
        info["wrapper"] = prefix
        if prefix:
            note("有多余的包装目录「%s」，导入时会自动剥掉" % prefix)

        try:
            info["manifest"] = char_pack._read_manifest(z, prefix)
        except Exception:
            info["manifest"] = {}

        for n in names:
            rel = n[len(prefix) + 1:] if prefix and n.startswith(prefix + "/") else n
            if rel == MANIFEST:
                continue
            base = os.path.basename(rel)
            top = rel.split("/")[0] if "/" in rel else ""
            if char_pack._is_junk(base):
                info["junk"].append(rel)
            elif rel in PACK_FILES or top in PACK_DIRS:
                if top:
                    info["dirs"][top] = info["dirs"].get(top, 0) + 1
                else:
                    info["dirs"][rel] = info["dirs"].get(rel, 0) + 1
            else:
                info["stray"].append(rel)

        # prompt 里有没有能用的 txt
        for n in names:
            rel = n[len(prefix) + 1:] if prefix and n.startswith(prefix + "/") else n
            if rel.startswith("prompt/") and rel.lower().endswith(".txt") \
                    and not char_pack._is_junk(os.path.basename(rel)):
                info["has_prompt"] = True

        # standing.json 里有没有私人进度
        sp = (prefix + "/memory/standing.json") if prefix else "memory/standing.json"
        if sp in names:
            try:
                raw = z.read(sp).decode("utf-8")
                d = json.loads(raw)
                if (d.get("relation_summary") or "").strip():
                    info["standing_private"].append(
                        "relation_summary 有 %d 字" % len(d["relation_summary"]))
                if int(d.get("stage") or 1) > 1:
                    info["standing_private"].append("stage=%s" % d.get("stage"))
                if int(d.get("source_msgs") or 0) > 0:
                    info["standing_private"].append("source_msgs=%s" % d.get("source_msgs"))
            except Exception as e:
                bad("memory/standing.json 读不出来：%s" % e)

    m = info["manifest"] or {}
    if not m:
        note("没有 manifest.json（能导入，但缺格式标记；--fix 会补一份）")
    else:
        if m.get("format") != char_pack.FORMAT:
            bad("manifest.format = %r，应为 %r" % (m.get("format"), char_pack.FORMAT))
        v = m.get("version")
        if v is not None and int(v) > char_pack.FORMAT_VERSION:
            bad("包格式版本 %s 比本程序支持的 %s 新，导入可能不完整"
                % (v, char_pack.FORMAT_VERSION))
    if not info["has_prompt"]:
        note("prompt/ 里没有 .txt：导入后会用自带模板铺一份（是个空角色）")
    if info["junk"]:
        note("有 %d 个备份/临时文件，--fix 会扔掉" % len(info["junk"]))
    if info["stray"]:
        note("有 %d 个白名单外的条目，导入时会被跳过" % len(info["stray"]))
    if info["standing_private"]:
        note("standing.json 带着私人进度（%s），--fix 会脱敏"
             % "、".join(info["standing_private"]))
    if not info["dirs"]:
        bad("包里没有任何角色内容")
    return not PROBLEM, info


def report(zip_path):
    print("检查：%s" % zip_path)
    ok, info = inspect(zip_path)
    print("  条目 %d 个 / 解压后 %s" % (info["entries"], human(info["bytes"])))
    if info["dirs"]:
        print("  内容：" + "，".join("%s %d" % (k, v) for k, v in sorted(info["dirs"].items())))
    m = info["manifest"] or {}
    if m:
        print("  清单：format=%s version=%s id=%s name=%s"
              % (m.get("format"), m.get("version"), m.get("id"), m.get("name")))
    for n in NOTE:
        print("  · " + n)
    for b in PROBLEM:
        print("  ✗ " + b)
    print("  结论：%s" % ("可以导入" if ok else "有问题，建议 --fix"))
    return 0 if ok else 1


# ------------------------------------------------------------------ 修复
def build(out_zip, members, ident, display, created_at=None):
    """members: [(绝对路径或 (名字, 字节), 包内相对路径)]"""
    parts, total = {}, 0
    for src, rel in members:
        top = rel.split("/")[0] if "/" in rel else rel
        parts[top] = parts.get(top, 0) + 1
        total += os.path.getsize(src) if isinstance(src, str) else len(src[1])
    manifest = {
        "format": char_pack.FORMAT,
        "version": char_pack.FORMAT_VERSION,
        "id": ident,
        "name": display or ident,
        "created_at": created_at or time.strftime("%Y-%m-%d %H:%M:%S"),
        "app": "WA2-Kazusa-Bot",
        "parts": parts,
        "files": len(members),
        "bytes": total,
    }
    tmp = out_zip + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        z.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=1))
        for src, rel in members:
            if isinstance(src, str):
                z.write(src, rel)
            else:
                z.writestr(rel, src[1])
    os.replace(tmp, out_zip)
    return manifest


def fix(zip_path, out_zip):
    ok, info = inspect(zip_path)
    if not info["dirs"]:
        print("包里没有角色内容，无法修。")
        return 1
    prefix = info["wrapper"]
    tmpd = tempfile.mkdtemp(prefix="packfix_")
    members, dropped = [], 0
    try:
        with zipfile.ZipFile(zip_path) as z:
            for i in z.infolist():
                if i.is_dir():
                    continue
                safe = char_pack._safe_rel(i.filename)
                if not safe:
                    dropped += 1
                    continue
                rel = safe[len(prefix) + 1:] if prefix and safe.startswith(prefix + "/") else safe
                if rel == MANIFEST:
                    continue
                base = os.path.basename(rel)
                top = rel.split("/")[0] if "/" in rel else ""
                if char_pack._is_junk(base) or not (rel in PACK_FILES or top in PACK_DIRS):
                    dropped += 1
                    continue
                data = z.read(i)
                if rel == "memory/standing.json":
                    p = os.path.join(tmpd, "standing.json")
                    with open(p, "wb") as f:
                        f.write(data)
                    data = char_pack._sanitize_standing(p)   # 返回的就是 bytes
                members.append(((rel, data), rel))
        m = info["manifest"] or {}
        ident = m.get("id") or m.get("name") or \
            os.path.splitext(os.path.basename(zip_path))[0]
        created = m.get("created_at")
        man = build(out_zip, members, ident, m.get("name") or ident, created)
        print("已写入：%s" % out_zip)
        print("  %d 个文件（过滤掉 %d 个），%s" % (len(members), dropped, human(man["bytes"])))
        for k, v in sorted(man["parts"].items()):
            print("    %-10s %d" % (k, v))
        return 0
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)


# ------------------------------------------------------------------ 从目录打包
def from_dir(src_dir, out_zip):
    if not os.path.isdir(src_dir):
        print("不是文件夹：%s" % src_dir)
        return 1
    members, dropped = [], 0
    for dirpath, _dirs, files in os.walk(src_dir):
        for fn in sorted(files):
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, src_dir).replace("\\", "/")
            top = rel.split("/")[0] if "/" in rel else rel
            if char_pack._is_junk(fn) or not (rel in PACK_FILES or top in PACK_DIRS):
                dropped += 1
                continue
            members.append((p, rel))
    if not members:
        print("这个文件夹里没有可打包的内容（要 prompt/ worldbook/ memory/ portrait/ voice/ 或 name.txt）")
        return 1
    # 名字：name.txt > 目录名
    ident = os.path.basename(os.path.normpath(src_dir))
    try:
        with io.open(os.path.join(src_dir, "name.txt"), encoding="utf-8") as f:
            ident = f.read().strip() or ident
    except Exception:
        pass
    man = build(out_zip, members, ident, ident)
    print("已写入：%s" % out_zip)
    print("  %d 个文件（过滤掉 %d 个），%s" % (len(members), dropped, human(man["bytes"])))
    print("  导入后角色名：%s" % ident)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="角色包检查 / 修复 / 从文件夹打包")
    ap.add_argument("pack", nargs="?", help="要检查或修复的角色包 .zip")
    ap.add_argument("--check", action="store_true", help="只检查，不写文件")
    ap.add_argument("--fix", action="store_true", help="重打一个干净包")
    ap.add_argument("--from-dir", metavar="目录", help="从散文件夹打包")
    ap.add_argument("--out", metavar="输出.zip", help="输出路径")
    a = ap.parse_args(argv)

    if a.from_dir:
        out = a.out or (os.path.basename(os.path.normpath(a.from_dir)) + ".zip")
        return from_dir(a.from_dir, out)
    if not a.pack:
        ap.print_help()
        return 2
    if a.fix:
        out = a.out or (os.path.splitext(a.pack)[0] + "_fixed.zip")
        return fix(a.pack, out)
    return report(a.pack)


if __name__ == "__main__":
    sys.exit(main())
