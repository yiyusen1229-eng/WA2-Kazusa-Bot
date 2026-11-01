# -*- coding: utf-8 -*-
"""解包素材预览器：把 tga/bmp 转成缩略图，生成可以直接翻的 HTML 画廊

用法：
    python tools/preview_assets.py <目录> [--out 输出目录] [--max 320] [--limit N]

产出：
    <out>/thumbs/*.png     缩略图
    <out>/index.html       画廊（按文件夹分组）
    <out>/report.txt       格式清单 + 无法识别文件的头部信息
"""
import argparse
import html
import io
import os
import sys
from collections import defaultdict

from PIL import Image

IMG_EXT = {".tga", ".bmp", ".png", ".jpg", ".jpeg", ".webp", ".gif"}


def sniff(path):
    """读前 64 字节，猜这是什么"""
    try:
        with open(path, "rb") as f:
            head = f.read(64)
    except OSError:
        return "读取失败", ""

    hexs = " ".join("%02X" % b for b in head[:16])

    if head[:4] == b"INAS":
        return "动画容器（头 INAS）", hexs
    if head[:3] == b"MZP":
        return "MZP 容器（疑似精灵表）", hexs
    if head[:4] == b"\x89PNG":
        return "PNG 图片", hexs
    if head[:2] == b"BM":
        return "BMP 图片", hexs
    if head[:2] == b"MZ":
        return "Windows 可执行文件", hexs
    if b"LSCR" in head:
        return "含 LSCR 段（疑似压缩横幅）", hexs

    # 猜文本：Shift-JIS / ASCII 可读比例
    try:
        txt = head.decode("shift_jis", errors="strict")
        printable = sum(1 for c in txt if c.isprintable() or c in "\r\n\t")
        if printable >= len(txt) * 0.8:
            return "文本（Shift-JIS）", hexs
    except Exception:
        pass
    try:
        txt = head.decode("ascii", errors="strict")
        if sum(1 for c in txt if c.isprintable()) >= len(txt) * 0.8:
            return "文本（ASCII）", hexs
    except Exception:
        pass

    # 纯数据：看是否像递增序列
    if len(head) >= 8 and all(head[i] < head[i + 1] for i in range(min(7, len(head) - 1))):
        return "递增字节序列（疑似索引表）", hexs

    return "未知二进制", hexs


def make_thumb(src, dst, max_side):
    im = Image.open(src)
    im.load()
    w, h = im.size
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA")
    im.thumbnail((max_side, max_side), Image.LANCZOS)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    im.save(dst, "PNG", optimize=True)
    return w, h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--out", default=None)
    ap.add_argument("--max", type=int, default=320, help="缩略图最长边")
    ap.add_argument("--limit", type=int, default=0, help="最多处理几张（调试用）")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    out = os.path.abspath(args.out or (root.rstrip(os.sep) + "_preview"))
    thumbs = os.path.join(out, "thumbs")
    os.makedirs(thumbs, exist_ok=True)

    by_dir = defaultdict(list)
    others = []
    imgs = []

    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            p = os.path.join(dirpath, f)
            ext = os.path.splitext(f)[1].lower()
            if ext in IMG_EXT:
                imgs.append(p)
            else:
                others.append(p)

    print("  目录: %s" % root)
    print("  图片 %d 个，其他 %d 个" % (len(imgs), len(others)))
    if args.limit:
        imgs = imgs[:args.limit]

    ok, fail = 0, 0
    for i, p in enumerate(imgs, 1):
        rel = os.path.relpath(p, root)
        key = rel.replace(os.sep, "/")
        dst = os.path.join(thumbs, key.rsplit(".", 1)[0] + ".png")
        try:
            w, h = make_thumb(p, dst, args.max)
            by_dir[os.path.dirname(key) or "."].append(
                (key, os.path.relpath(dst, out).replace(os.sep, "/"), w, h,
                 os.path.getsize(p)))
            ok += 1
        except Exception as e:
            fail += 1
            by_dir[os.path.dirname(key) or "."].append((key, "", 0, 0, 0))
            print("    [失败] %s  %s" % (rel, e))
        if i % 200 == 0:
            print("    已处理 %d/%d" % (i, len(imgs)), flush=True)

    # ---- 报告 ----
    rep = io.open(os.path.join(out, "report.txt"), "w", encoding="utf-8")
    rep.write("图片 %d（成功 %d，失败 %d）\n其他文件 %d\n\n" % (len(imgs), ok, fail, len(others)))
    rep.write("=== 其他格式清单 ===\n")
    cnt = defaultdict(int)
    for p in others:
        cnt[os.path.splitext(p)[1].lower() or "(无)"] += 1
    for ext, n in sorted(cnt.items(), key=lambda kv: -kv[1]):
        rep.write("  %-10s %5d\n" % (ext, n))

    rep.write("\n=== 非图片文件辨认（每类抽样 3 个）===\n")
    samples = defaultdict(list)
    for p in others:
        ext = os.path.splitext(p)[1].lower()
        if len(samples[ext]) < 3:
            samples[ext].append(p)
    for ext, ps in sorted(samples.items()):
        rep.write("\n-- %s --\n" % (ext or "(无扩展名)"))
        for p in ps:
            kind, hexs = sniff(p)
            rep.write("  %s\n    判定: %s\n    头: %s\n"
                      % (os.path.relpath(p, root), kind, hexs))
    rep.close()

    # ---- HTML ----
    h = io.open(os.path.join(out, "index.html"), "w", encoding="utf-8")
    h.write("""<!doctype html><meta charset="utf-8">
<title>素材预览</title>
<style>
body{background:#1b1d21;color:#ddd;font:13px/1.5 system-ui,sans-serif;margin:0;padding:16px}
h2{font-size:14px;color:#7fd0e0;border-bottom:1px solid #333;padding-bottom:4px;margin:24px 0 12px}
.grid{display:flex;flex-wrap:wrap;gap:10px}
.card{background:#25282d;border-radius:6px;padding:6px;width:180px}
.card img{width:100%;height:130px;object-fit:contain;background:
  repeating-conic-gradient(#2c2f34 0 25%,#23262a 0 50%) 0 0/16px 16px}
.card .n{font-size:11px;color:#9ab;word-break:break-all;margin-top:4px}
.card .d{font-size:10px;color:#667}
</style><body>
""")
    total = 0
    for d in sorted(by_dir):
        h.write("<h2>%s/</h2><div class=grid>\n" % html.escape(d))
        for key, thumb, w, hh, size in sorted(by_dir[d]):
            name = os.path.basename(key)
            if thumb:
                h.write('<div class=card><a href="thumbs/%s" target=_blank>'
                        '<img loading=lazy src="%s"></a>'
                        '<div class=n>%s</div><div class=d>%dx%d · %.1f KB</div></div>\n'
                        % (html.escape(thumb), html.escape(thumb), html.escape(name),
                           w, hh, size / 1024))
                total += 1
            else:
                h.write('<div class=card><div class=n>%s</div>'
                        '<div class=d>无法预览</div></div>\n' % html.escape(name))
        h.write("</div>\n")
    h.write("</body>")
    h.close()

    print("\n  完成：缩略图 %d 张" % total)
    print("  画廊: %s" % os.path.join(out, "index.html"))
    print("  报告: %s" % os.path.join(out, "report.txt"))


if __name__ == "__main__":
    main()
