# -*- coding: utf-8 -*-
"""在汉化 exe 的 .rdata 里寻找「字符→字模序号」映射表

判据: 连续的一串 uint16, 数值大多落在 0..12000(字模图总数 11815 附近),
      且整体随地址递增(按编码顺序排列)。
"""
import struct

G = r"E:\Games\GALGAMES\WHITE ALBUM2"


def get_sec(path, name):
    d = open(path, "rb").read()
    e = struct.unpack_from("<I", d, 0x3C)[0]
    nsec = struct.unpack_from("<H", d, e + 6)[0]
    optsz = struct.unpack_from("<H", d, e + 20)[0]
    sec = e + 24 + optsz
    base = struct.unpack_from("<I", d, e + 24 + 28)[0]
    for i in range(nsec):
        o = sec + i * 40
        sname = d[o:o + 8].rstrip(b"\x00").decode("latin1")
        if sname == name:
            vs, va, rs, ra = struct.unpack_from("<IIII", d, o + 8)
            return d[ra:ra + rs], base + va
    return None, 0


for exe in ("WA2_chs.exe", "WA2.exe"):
    rd, va = get_sec(G + "\\" + exe, ".rdata")
    n = len(rd) // 2
    print("\n=== %s .rdata %d 字节, 可切 %d 个 uint16 ===" % (exe, len(rd), n))
    # 找最长的「值都 < 12288 且非零且递增为主」的连续段
    vals = struct.unpack_from("<%dH" % n, rd, 0)
    best = (0, 0)
    i = 0
    while i < n:
        if 0 < vals[i] < 12288:
            j = i
            ok = 0
            while j < n and 0 < vals[j] < 12288:
                j += 1
                ok += 1
                if ok > 4000:
                    break
            if j - i > best[1] - best[0]:
                best = (i, j)
            i = j
        else:
            i += 1
    s, e = best
    print("  最长候选段: 第 %d..%d 项, 共 %d 项, 文件偏移 0x%X (VA 0x%08X)"
          % (s, e, e - s, s * 2, va + s * 2))
    if e - s > 20:
        seg = vals[s:e]
        inc = sum(1 for k in range(1, len(seg)) if seg[k] >= seg[k - 1])
        print("  前 12 个值: %s" % list(seg[:12]))
        print("  递增比例: %.0f%%" % (100.0 * inc / max(1, len(seg) - 1)))
        print("  最小值 %d 最大值 %d" % (min(seg), max(seg)))
