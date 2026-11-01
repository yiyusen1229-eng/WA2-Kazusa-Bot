# -*- coding: utf-8 -*-
"""对比原版 WA2.exe 与汉化 WA2_chs.exe 的 .rdata 差异, 看补丁到底改了什么数据"""
import struct

G = r"E:\Games\GALGAMES\WHITE ALBUM2"


def sections(name):
    d = open(G + "\\" + name, "rb").read()
    e = struct.unpack_from("<I", d, 0x3C)[0]
    nsec = struct.unpack_from("<H", d, e + 6)[0]
    optsz = struct.unpack_from("<H", d, e + 20)[0]
    sec = e + 24 + optsz
    base = struct.unpack_from("<I", d, e + 24 + 28)[0]
    out = {}
    for i in range(nsec):
        o = sec + i * 40
        sname = d[o:o + 8].rstrip(b"\x00").decode("latin1")
        vs, va, rs, ra = struct.unpack_from("<IIII", d, o + 8)
        out[sname] = (d[ra:ra + rs], base + va)
    return out


a = sections("WA2.exe")
b = sections("WA2_chs.exe")
ra, va = a[".rdata"]
rb, vb = b[".rdata"]
n = min(len(ra), len(rb))
# 找出连续差异区间
runs = []
i = 0
while i < n:
    if ra[i] != rb[i]:
        j = i
        while j < n and ra[j] != rb[j]:
            j += 1
        runs.append((i, j))
        i = j
    else:
        i += 1
print(".rdata 差异区间数:", len(runs))


def printable(buf):
    return "".join(chr(c) if 32 <= c < 127 else "." for c in buf)


print("\n差异区间(合并相邻 8 字节内):")
merged = []
for s, e in runs:
    if merged and s - merged[-1][1] <= 8:
        merged[-1] = (merged[-1][0], e)
    else:
        merged.append((s, e))
print("合并后:", len(merged))
for s, e in merged[:40]:
    old = ra[max(0, s - 4):e + 4]
    new = rb[max(0, s - 4):e + 4]
    print("\n  0x%06X 长度 %d  VA 0x%08X" % (s, e - s, va + s))
    print("    原: %s" % printable(old))
    print("    新: %s" % printable(new))
