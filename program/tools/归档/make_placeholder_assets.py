# -*- coding: utf-8 -*-
"""生成占位素材：让没有游戏素材的人也能把程序跑起来

思路：
  扫描前端代码里引用到的 assets/... 路径，
  对缺失的图片生成一张「文件名写在中间」的占位 PNG，
  尺寸尽量按代码里出现的 width/height 推断，推断不出就用默认值。

用法：
    python tools/make_placeholder_assets.py            # 只补缺失的
    python tools/make_placeholder_assets.py --force    # 全部重写
    python tools/make_placeholder_assets.py --dry-run  # 只看会生成什么
"""
import argparse
import io
import json
import os
import re
import struct

_DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = _DEFAULT_ROOT
UI = os.path.join(ROOT, "ui2")
APP = os.path.join(ROOT, "app")


def set_root(root):
    global ROOT, UI, APP
    ROOT = os.path.abspath(root)
    UI = os.path.join(ROOT, "ui2")
    APP = os.path.join(ROOT, "app")

# 默认尺寸（推断不出来时用）
DEFAULT_SIZE = (256, 64)

# 少数值得给具体尺寸的（避免界面全是大方块）
SPECIAL = {
    "assets/title.png": (1280, 720),
    "assets/ui_logo.png": (365, 210),
    "assets/bg_classroom.png": (1280, 720),
    "assets/bg_corridor.png": (1280, 720),
    "assets/bg_music.png": (1280, 720),
    "assets/bg_street.png": (1280, 720),
    "assets/copyright.png": (300, 24),
    "assets/input_frame.png": (800, 56),
    "assets/bar_gloss.png": (800, 40),
}

COLORS = [
    (54, 84, 110), (72, 100, 128), (46, 74, 98),
    (90, 118, 140), (62, 92, 116), (104, 132, 150),
]


# ---------- 极简 PNG 写入（不依赖 Pillow）----------

def _png_bytes(w, h, rgb):
    """生成纯色 PNG"""
    raw = b""
    row = bytes(rgb) * w
    for _ in range(h):
        raw += b"\x00" + row

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", _crc(c[4:]))

    def _crc(data):
        import zlib
        return zlib.crc32(data) & 0xFFFFFFFF

    import zlib
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    idat = zlib.compress(raw, 6)
    return (sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat)
            + chunk(b"IEND", b""))


def write_png(path, w, h, rgb):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(_png_bytes(w, h, rgb))


# ---------- 扫描代码里引用的素材 ----------

ASSET_RE = re.compile(r"""["'(]?(assets/[A-Za-z0-9_\-./]+\.(?:png|jpg|jpeg|webp|ico|ogg|mp3|wav))""")


def scan_sources():
    """返回 {assets/xxx.png: {来源文件}}"""
    hits = {}
    for root, dirs, files in os.walk(UI):
        dirs[:] = [d for d in dirs if d not in ("assets", "__pycache__")]
        for f in files:
            if not f.endswith((".js", ".css", ".html")):
                continue
            fp = os.path.join(root, f)
            try:
                txt = io.open(fp, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            for m in ASSET_RE.finditer(txt):
                hits.setdefault(m.group(1), set()).add(os.path.relpath(fp, ROOT))
    return hits


# ---------- 生成 ----------

def gen_placeholder(rel_path, force=False, dry=False):
    """rel_path 形如 assets/sprites/uniform/kaz_uniform_01.png（相对 ui2/）"""
    dst = os.path.join(UI, rel_path.replace("/", os.sep))
    if os.path.exists(dst) and not force:
        return "skip"
    if dry:
        return "would-create"

    ext = os.path.splitext(rel_path)[1].lower()
    os.makedirs(os.path.dirname(dst), exist_ok=True)

    if ext == ".png":
        w, h = SPECIAL.get(rel_path, DEFAULT_SIZE)
        idx = sum(ord(c) for c in rel_path) % len(COLORS)
        write_png(dst, w, h, COLORS[idx])
        return "png"

    if ext in (".jpg", ".jpeg"):
        w, h = SPECIAL.get(rel_path, DEFAULT_SIZE)
        idx = sum(ord(c) for c in rel_path) % len(COLORS)
        write_png(dst + ".png", w, h, COLORS[idx])
        os.replace(dst + ".png", dst)      # 扩展名骗人，内容是 PNG，浏览器能认
        return "jpg"

    if ext == ".ico":
        # 1x1 透明 ICO 过于麻烦，直接写一个最小 PNG 改名
        write_png(dst, 64, 64, (54, 84, 110))
        return "ico"

    if ext in (".ogg", ".mp3", ".wav"):
        # 空音频：静音，长度为 0
        open(dst, "wb").close()
        return "audio"

    return "skip"


def make_story_index():
    p = os.path.join(APP, "story_index.json")
    if os.path.exists(p):
        return
    io.open(p, "w", encoding="utf-8").write('{"entries": [], "docs": []}')
    print("  生成占位 app/story_index.json（往事检索将不可用）")


def make_font_placeholders():
    """空字形映射 → 文字走 GDI 回退"""
    for name, content in (
        ("subfont_charset.json", "{}"),
        ("字体映射表.json", "{}"),
    ):
        p = os.path.join(APP, "assets", name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if not os.path.exists(p):
            io.open(p, "w", encoding="utf-8").write(content)
            print("  生成占位 app/assets/%s（文字将走 GDI 回退）" % name)


def make_sprites_index():
    """立绘索引：扫描 sprites 目录生成"""
    d = os.path.join(UI, "assets", "sprites")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "index.json")
    if os.path.exists(p):
        return
    outfits = {}
    if os.path.isdir(d):
        for outfit in sorted(os.listdir(d)):
            od = os.path.join(d, outfit)
            if not os.path.isdir(od):
                continue
            variants = [f for f in os.listdir(od) if f.endswith(".png")]
            if variants:
                outfits[outfit] = {"emotions": {}, "files": variants}
    io.open(p, "w", encoding="utf-8").write(
        json.dumps(outfits, ensure_ascii=False, indent=2))
    print("  生成占位 assets/sprites/index.json（%d 套）" % len(outfits))


def make_config():
    src = os.path.join(ROOT, "config.example.json")
    dst = os.path.join(ROOT, "最新版", "config.json")
    if os.path.exists(dst) or not os.path.exists(src):
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    io.open(dst, "w", encoding="utf-8").write(
        io.open(src, encoding="utf-8").read())
    print("  生成最新版/config.json（记得填 API key）")


# 代码里用到的服装编号（见 ui2/game.js 的 OUTFIT_BY_SCENE）
OUTFITS = ["001", "003", "004", "007", "008", "020", "022", "027", "029", "036"]

# 情绪 → 文件名后缀（与 game.js 的 MOOD_TO_EMO 对齐）
EMOTIONS = {
    "cold": "kaz_cold.png",
    "angry": "kaz_angry.png",
    "sad": "kaz_sad.png",
    "smile": "kaz_smile.png",
    "surprise": "kaz_surprise.png",
    "shy": "kaz_shy.png",
    "serious": "kaz_serious.png",
}
SPRITE_SIZE = (768, 900)     # 游戏立绘是 900px 高


def make_default_sprites(dry=False):
    """每套服装生成 7 种情绪占位图，并写 index.json"""
    d = os.path.join(UI, "assets", "sprites")
    index = {}
    made = 0
    for outfit in OUTFITS:
        od = os.path.join(d, outfit)
        emo_map = {}
        for emo, fname in EMOTIONS.items():
            fp = os.path.join(od, fname)
            emo_map[emo] = fname
            if os.path.exists(fp) or dry:
                continue
            make_dirs(od)
            write_png(fp, SPRITE_SIZE[0], SPRITE_SIZE[1],
                      COLORS[sum(ord(c) for c in outfit) % len(COLORS)])
            made += 1
        index[outfit] = {"emotions": emo_map}
    p = os.path.join(d, "index.json")
    if not os.path.exists(p) and not dry:
        make_dirs(d)
        io.open(p, "w", encoding="utf-8").write(
            json.dumps(index, ensure_ascii=False, indent=2))
        print("  生成立绘占位：%d 套 × %d 情绪（共 %d 张），已写 index.json"
              % (len(OUTFITS), len(EMOTIONS), made))
    return made


def make_dirs(path):
    os.makedirs(path, exist_ok=True)



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--root", help="项目根目录（默认是本脚本的上一级）")
    args = ap.parse_args()
    if args.root:
        set_root(args.root)

    hits = scan_sources()
    print("=" * 70)
    print(" 占位素材生成器")
    print("=" * 70)
    print("  代码里引用到的素材：%d 个" % len(hits))

    stat = {"png": 0, "jpg": 0, "ico": 0, "audio": 0, "skip": 0, "would-create": 0}
    for rel in sorted(hits):
        r = gen_placeholder(rel, args.force, args.dry_run)
        stat[r] = stat.get(r, 0) + 1

    if not args.dry_run:
        make_story_index()
        make_font_placeholders()
        made = make_default_sprites()
        make_sprites_index()
        make_config()
    else:
        made = make_default_sprites(dry=True)
        print("  将生成立绘占位 %d 张" % made)

    print("\n  图片 %d、音频 %d、跳过 %d%s"
          % (stat["png"] + stat["jpg"] + stat["ico"], stat["audio"], stat["skip"],
             "、将创建 %d" % stat["would-create"] if args.dry_run else ""))
    print("""
  注意：
    1. 占位图只是纯色方块，界面能跑起来但很难看
    2. 文字会走 GDI 回退（微软雅黑），不是补丁字形
    3. 立绘 / 背景 / UI 全部是占位，看不出游戏的样子
    4. 想要真效果，按 docs/本地素材获取指南.md 自己解包游戏

  跑一次自检确认：
    python tools/check_assets.py
""")


if __name__ == "__main__":
    main()
