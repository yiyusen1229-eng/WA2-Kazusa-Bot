# -*- coding: utf-8 -*-
"""解开 ck-gal.pak 里的一条 .txt, 看中文到底用什么编码存的"""
import os
import struct
import zlib

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
PAK = r"E:\Games\GALGAMES\WHITE ALBUM2\ck-gal.pak"

d = open(PAK, "rb").read()
cnt = struct.unpack_from("<I", d, 12)[0]
ents = []
for i in range(cnt):
    off = 16 + i * 44
    name = d[off + 4:off + 36].split(b"\x00")[0]
    fo, fs = struct.unpack_from("<II", d, off + 36)
    try:
        nm = name.decode("shift-jis")
    except Exception:
        nm = name.decode("latin1", "ignore")
    ents.append((nm, fo, fs))

target = None
for nm, fo, fs in ents:
    if nm.endswith(".txt"):
        target = (nm, fo, fs)
        break
print("目标条目:", target)
nm, fo, fs = target
blob = d[fo:fo + fs]
print("大小 %d  头 16 字节: %s" % (fs, blob[:16].hex()))

# 头 8 字节看起来是两个 dword, 之后 0xFF 开头
head = blob[:8]
a, b = struct.unpack_from("<II", head)
print("头两个 dword: %d %d" % (a, b))

data = blob[8:]
print("去掉 8 字节头后 前 16 字节:", data[:16].hex())

# 尝试几种解压
cands = []
for label, fn in (
    ("zlib", lambda x: zlib.decompress(x)),
    ("raw-deflate", lambda x: zlib.decompress(x, -15)),
):
    for skip in (0, 1):
        try:
            out = fn(data[skip:])
            cands.append((label, skip, out))
            break
        except Exception:
            pass
print("解压成功的方式:", [(c[0], c[1], len(c[2])) for c in cands])

if cands:
    out = cands[0][2]
    print("\n解出 %d 字节, 前 64:" % len(out), out[:64].hex())
    for enc in ("gbk", "shift_jis", "utf-16-le", "utf-8"):
        try:
            t = out.decode(enc, "ignore")
            cn = sum(1 for ch in t if "\u4e00" <= ch <= "\u9fff")
            print("  %-10s 汉字 %4d  前 60 字: %s" % (enc, cn, t[:60].replace("\n", " ")))
        except Exception as e:
            print("  %-10s 失败" % enc)
