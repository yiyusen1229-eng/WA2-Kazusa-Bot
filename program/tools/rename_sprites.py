# -*- coding: utf-8 -*-
"""立绘改名：`衣服编号/ kaz<衣服><变化>.png` → `衣服名称/ 表情名.png`

为什么需要它：
    立绘目录原来是「数字编号 + kaz 前缀」的机器命名，配置角色时看不出哪张是哪个表情。
    这个脚本按 index.json 里的 `label`（衣服名）和变体→表情表，把目录和文件改成中文，
    并同步重写 index.json（保留 code / variant，方便回溯和对旧存档兼容）。

映射表（全项目只此一份）：
    衣服名   = index.json 里每套衣服的 label（重名时补 `_编号`，否则目录会撞车）
    表情名   = 变体号 → 表情（serious/cold/smile/angry/sad/surprise/shy）→ 中文
    没有映射的 = 「其他」+ 序号（原变体号仍记在 index.json 的 variants 里）

用法：
    python tools/rename_sprites.py --root <立绘目录> --dry-run
    python tools/rename_sprites.py --root <立绘目录>
    # 不给 --root 时用「当前角色文件夹/portrait」
"""
import argparse
import json
import os
import re
import sys

SPRITE_RE = re.compile(r"^kaz(\d{3})(\d{3})\.(png|jpg|jpeg|webp|bmp|gif)$", re.I)

# 变体号 → 表情（和 special_files.VARIANT_EMOTION 保持一致）
VAR_EMOTION = {
    "101": "serious",
    "104": "cold", "110": "cold", "134": "cold",
    "109": "smile", "307": "smile", "323": "smile",
    "115": "surprise", "218": "surprise",
    "125": "sad", "131": "sad", "224": "sad",
    "140": "shy",
    "205": "angry", "212": "angry",
}

EMOTION_CN = {
    "serious": "认真",
    "cold": "冷淡",
    "smile": "微笑",
    "angry": "生气",
    "sad": "难过",
    "surprise": "惊讶",
    "shy": "害羞",
}
OTHER = "其他"


def _default_root():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
    import characters  # noqa: E402
    return characters.sprite_dir()


def plan(root):
    """算出「旧路径 → 新路径」和新 index；不落盘"""
    idx_path = os.path.join(root, "index.json")
    with open(idx_path, encoding="utf-8") as f:
        idx = json.load(f)
    outfits = idx.get("outfits") or {}

    # ① 衣服编号 → 新目录名（label 重名时补编号）
    used = set()
    name_of = {}
    for code, o in outfits.items():
        label = (o.get("label") or "").strip() or ("衣服" + code)
        name = label
        if name in used:
            name = "%s_%s" % (label, code)
        used.add(name)
        name_of[code] = name

    moves = []            # (old_abs, new_rel, code, variant, file, emotion_cn)
    new_outfits = {}
    for code, o in outfits.items():
        old_dir = os.path.join(root, code)
        if not os.path.isdir(old_dir):
            old_dir = os.path.join(root, name_of[code])   # 已经改过名的就按新名字找
        emo_of_file = {}
        for emo, f in (o.get("emotions") or {}).items():
            emo_of_file[f] = emo
        listed = {}
        for v in (o.get("variants") or []):
            if v.get("file"):
                listed[v["file"]] = v.get("variant") or ""

        files = []
        if os.path.isdir(old_dir):
            files = [f for f in sorted(os.listdir(old_dir))
                     if os.path.isfile(os.path.join(old_dir, f))]
        # index 里登记了、但目录里没有的，保留条目（生成时 file 名照算，缺失不搬）
        for f in listed:
            if f not in files:
                files.append(f)

        used_names = set()
        variants_out = []
        new_emotions = {}

        def new_name(base, ext=".png"):
            n = base
            i = 2
            while n.lower() in used_names:
                n = base + str(i)
                i += 1
            used_names.add(n.lower())
            return n + ext

        # 先处理有表情的，保证「认真.png」这种短名字留给第一个
        order = sorted(files, key=lambda f: (0 if (emo_of_file.get(f) or
                                                   VAR_EMOTION.get(_variant_of(f, code) or "")) else 1, f))
        for f in order:
            variant = _variant_of(f, code) or listed.get(f, "")
            emo = emo_of_file.get(f) or VAR_EMOTION.get(variant) or ""
            base = EMOTION_CN.get(emo, "") or OTHER
            ext = os.path.splitext(f)[1].lower() or ".png"
            nname = new_name(base, ext)
            if f in listed or os.path.isfile(os.path.join(old_dir, f)):
                moves.append((os.path.join(old_dir, f),
                              os.path.join(name_of[code], nname), code, variant, f, base))
            variants_out.append({"variant": variant or "", "file": nname,
                                 **({"emotion": emo} if emo else {})})
            if emo and nname not in new_emotions.values():
                new_emotions.setdefault(emo, nname)

        # default / emotions 指向新名字
        def to_new(old_file):
            for _o, _n, _c, _v, of, _b in moves:
                if _c == code and of == old_file:
                    return os.path.basename(_n)
            return old_file

        default = to_new(o.get("default") or "")
        emotions = {}
        for emo, f in (o.get("emotions") or {}).items():
            emotions[emo] = to_new(f)
        for emo, f in new_emotions.items():
            emotions.setdefault(emo, f)

        entry = dict(o)
        entry["code"] = code
        entry["label"] = o.get("label") or name_of[code]
        entry["default"] = default
        entry["emotions"] = emotions
        entry["variants"] = variants_out
        new_outfits[name_of[code]] = entry

    new_idx = dict(idx)
    new_idx["outfits"] = new_outfits
    return moves, new_idx, name_of


def _variant_of(filename, code):
    m = SPRITE_RE.match(filename or "")
    if not m:
        return ""
    if m.group(1) != code:
        return ""
    return m.group(2)


def apply(root, moves, new_idx, dry_run=False):
    # 先搬到临时名，避免 a→b、b→a 这种互相覆盖
    tmp_moves = []
    for i, (old, new, *_rest) in enumerate(moves):
        if not os.path.isfile(old):
            continue
        tmp = os.path.join(root, "__tmp_%04d%s" % (i, os.path.splitext(old)[1]))
        if not dry_run:
            os.replace(old, tmp)
        tmp_moves.append((tmp, new))
    for tmp, new in tmp_moves:
        dst_dir = os.path.join(root, os.path.dirname(new))
        if not dry_run:
            os.makedirs(dst_dir, exist_ok=True)
            os.replace(tmp, os.path.join(root, new))
    # 删掉空的旧数字目录
    for name in sorted(os.listdir(root)):
        p = os.path.join(root, name)
        if os.path.isdir(p) and re.match(r"^\d{3}$", name):
            try:
                os.rmdir(p)
            except OSError:
                pass
    if not dry_run:
        tmp = os.path.join(root, "index.json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(new_idx, f, ensure_ascii=False, indent=1)
        os.replace(tmp, os.path.join(root, "index.json"))


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="立绘改名（编号 → 衣服名 / 表情名）")
    ap.add_argument("--root", default="")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = args.root or _default_root()
    if not os.path.isdir(root) or not os.path.isfile(os.path.join(root, "index.json")):
        print("找不到立绘目录或 index.json：%s" % root)
        return 1

    moves, new_idx, name_of = plan(root)
    print("立绘目录: %s" % root)
    print("衣服：%d 套，文件：%d 个" % (len(new_idx["outfits"]), len(moves)))
    for code, name in name_of.items():
        cnt = sum(1 for m in moves if m[2] == code)
        print("  %s → %s（%d 张）" % (code, name, cnt))
    by_cn = {}
    for m in moves:
        by_cn[m[5]] = by_cn.get(m[5], 0) + 1
    print("命名分布:", ", ".join("%s×%d" % (k, v) for k, v in sorted(by_cn.items(), key=lambda kv: -kv[1])))
    if args.dry_run:
        print("\n[dry-run] 没有改动任何文件")
        for old, new, *_ in moves[:8]:
            print("  %s → %s" % (os.path.basename(old), new))
        return 0
    apply(root, moves, new_idx)
    print("\n完成。可回滚：把 index.json 的 code 还原即可重新算（源文件已改名）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
