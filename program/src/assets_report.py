# -*- coding: utf-8 -*-
"""素材自检报告：启动 / 导入时写一份 asset_report.json。

查的是「运行时会用到、缺了就会穿帮」的那部分：
  * 场景背景：assets/cg/index.json 里列出的文件在不在、是不是 0 字节
  * 角色立绘：portrait/index.json 里列出的每套衣服/每个表情在不在
  * 参考语音：voice/ 下的文件是不是 0 字节

只读不写素材；缺了也不阻塞启动，只在日志里报一句 + 落一份报告。
"""
import json
import os
import time

import cache_io


def _size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return -1


def build(assets_dir, char_dir=""):
    """返回 {ok, checked, bytes, missing[], zero[], ...}"""
    missing, zero = [], []
    checked = total = 0

    # 1) 场景背景
    cg_dir = os.path.join(assets_dir, "cg")
    idx = cache_io.read_json(os.path.join(cg_dir, "index.json"), {}) or {}
    for it in (idx.get("items") or []):
        if not isinstance(it, dict):
            continue
        f = it.get("file")
        if not f:
            continue
        checked += 1
        p = os.path.join(cg_dir, f)
        sz = _size(p)
        if sz < 0:
            missing.append({"kind": "cg", "id": it.get("id", ""), "file": f})
        elif sz == 0:
            zero.append({"kind": "cg", "file": f})
        else:
            total += sz

    # 2) 角色立绘 + 参考语音
    if char_dir:
        pdir = os.path.join(char_dir, "portrait")
        pidx = cache_io.read_json(os.path.join(pdir, "index.json"), {}) or {}
        for outfit, meta in (pidx.get("outfits") or {}).items():
            files = set()
            if isinstance(meta, dict):
                if meta.get("default"):
                    files.add(meta["default"])
                for v in (meta.get("variants") or []):
                    if isinstance(v, dict) and v.get("file"):
                        files.add(v["file"])
            for f in sorted(files):
                checked += 1
                p = os.path.join(pdir, outfit, f)
                sz = _size(p)
                if sz < 0:
                    missing.append({"kind": "portrait", "outfit": outfit, "file": f})
                elif sz == 0:
                    zero.append({"kind": "portrait", "file": os.path.join(outfit, f)})
                else:
                    total += sz

        vdir = os.path.join(char_dir, "voice")
        if os.path.isdir(vdir):
            for root, _dirs, fs in os.walk(vdir):
                for f in fs:
                    p = os.path.join(root, f)
                    checked += 1
                    sz = _size(p)
                    if sz == 0:
                        zero.append({"kind": "voice", "file": os.path.relpath(p, char_dir)})
                    elif sz > 0:
                        total += sz

    return {"ok": not missing and not zero,
            "checked": checked,
            "bytes": total,
            "missing": missing,
            "zero": zero,
            "assets_dir": assets_dir,
            "char_dir": char_dir,
            "at": time.strftime("%Y-%m-%d %H:%M:%S")}


def write(path, report):
    """原子写报告（先 .tmp 再替换）"""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
        return path
    except Exception:
        return ""


def summary(report):
    """给日志用的一行"""
    n_miss = len(report.get("missing") or [])
    n_zero = len(report.get("zero") or [])
    if not n_miss and not n_zero:
        return "素材自检：%d 个文件都正常（%.1f MB）" % (
            report.get("checked", 0), report.get("bytes", 0) / 1048576.0)
    return "素材自检：缺 %d 项、0 字节 %d 项（详见 asset_report.json）" % (n_miss, n_zero)
