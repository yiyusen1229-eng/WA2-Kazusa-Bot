# -*- coding: utf-8 -*-
"""读取 exe 里的字符→字模序号映射表, 并验证

结构(按反编译结果):
  单字节: 3 组, 每组 8 字节:
      +0 起(byte) +1 止(byte) ... +4 基准(dword)
  双字节: 53 组:
      word_4C22C4[4*n]  起(16位)
      word_4C22C6[4*n]  止(16位)
      dword_4C22C0[2*n] 基准(32位)

注意地址关系: dword_4C22C0[2*n] = 0x4C22C0 + 8*n
              word_4C22C4[4*n]  = 0x4C22C4 + 8*n
              word_4C22C6[4*n]  = 0x4C22C6 + 8*n
=> 每项 8 字节: [+0]基准(4字节) [+4]起(2字节) [+6]止(2字节)
"""
import struct

EXE = r"E:\Games\GALGAMES\WHITE ALBUM2\WA2_chs.exe"
EXE_JP = r"E:\Games\GALGAMES\WHITE ALBUM2\WA2.exe"

d = open(EXE, "rb").read()
e = struct.unpack_from("<I", d, 0x3C)[0]
nsec = struct.unpack_from("<H", d, e + 6)[0]
optsz = struct.unpack_from("<H", d, e + 20)[0]
sec = e + 24 + optsz
base = struct.unpack_from("<I", d, e + 24 + 28)[0]
secs = []
for i in range(nsec):
    o = sec + i * 40
    nm = d[o:o + 8].rstrip(b"\x00").decode("latin1")
    vs, va, rs, ra = struct.unpack_from("<IIII", d, o + 8)
    secs.append((nm, base + va, rs, ra))


def off_of(va):
    for nm, sva, rs, ra in secs:
        if sva <= va < sva + rs:
            return ra + (va - sva)
    return None


print("=== 双字节区间表 (0x4C22C0, 53 项) ===")
o = off_of(0x004C22C0)
print("文件偏移: 0x%X" % o)
rows = []
for n in range(53):
    bs, lo, hi = struct.unpack_from("<IHH", d, o + n * 8)
    rows.append((lo, hi, bs))
    if n < 8 or n > 48:
        print("  [%2d] %04X ~ %04X  基准 %d" % (n, lo, hi, bs))
    elif n == 8:
        print("   ...")

print("\n=== 单字节表 (0x4C2468 附近, 3 项) ===")
o2 = off_of(0x004C2460)
for n in range(3):
    v = struct.unpack_from("<I", d, o2 + n * 8)[0]
    lo = d[off_of(0x004C246C) + n * 8]
    hi = d[off_of(0x004C246D) + n * 8]
    print("  [%d] %02X ~ %02X  值=%d" % (n, lo, hi, v))


def glyph_index(ch):
    """按反编译逻辑算字模序号"""
    try:
        sj = ch.encode("shift_jis")
    except Exception:
        return None
    if len(sj) == 1:
        code = sj[0]
        for n in range(3):
            bs = struct.unpack_from("<I", d, o2 + n * 8)[0]
            lo = d[off_of(0x004C246C) + n * 8]
            hi = d[off_of(0x004C246D) + n * 8]
            if lo <= code <= hi:
                return code + bs - lo
        return None
    code = (sj[0] << 8) | sj[1]
    for lo, hi, bs in rows:
        if lo <= code <= hi:
            return code + bs - lo
    return None


print("\n=== 用公式验证几个字 ===")
for ch in "我是不起可的，。あア亜":
    print("  %s -> 序号 %s" % (ch, glyph_index(ch)))
