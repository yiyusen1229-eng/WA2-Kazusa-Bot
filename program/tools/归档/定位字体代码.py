# -*- coding: utf-8 -*-
"""在 exe 里定位「字体文件」相关的代码位置

思路:
  1. 在文件里找 "subfont.tga" / ".ttf" / "default" 等字符串, 换算成虚拟地址(VA)
  2. 在 .text 里搜索对这串 VA 的立即数引用 (32 位小端)
  3. 把引用点前后反汇编出来, 那通常就是 加载字库 / 建索引 的函数
输出给你在反编译器里直接跳转的地址列表。
"""
import struct
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

EXE = sys.argv[1] if len(sys.argv) > 1 else r"E:\IDM下载目录\ollydbg\WA2_chs.exe"

data = open(EXE, "rb").read()
e = struct.unpack_from("<I", data, 0x3C)[0]
nsec = struct.unpack_from("<H", data, e + 6)[0]
optsz = struct.unpack_from("<H", data, e + 20)[0]
sec = e + 24 + optsz
image_base = struct.unpack_from("<I", data, e + 24 + 28)[0]

secs = []
for i in range(nsec):
    o = sec + i * 40
    name = data[o:o + 8].rstrip(b"\x00").decode("latin1")
    vs, va, rs, ra = struct.unpack_from("<IIII", data, o + 8)
    secs.append((name, image_base + va, rs, ra, vs))
    print("节 %-8s VA 0x%08X 文件偏移 %d 大小 %d 虚拟大小 %d" % (name, image_base + va, ra, rs, vs))


def va_of_offset(off):
    for name, va, rs, ra, vs in secs:
        if ra <= off < ra + rs:
            return va + (off - ra)
    return None


def code_bytes():
    for name, va, rs, ra, vs in secs:
        if name == ".text":
            return va, data[ra:ra + rs]
    return 0, b""


TARGETS = [b"subfont.tga", b".tga", b".ttf", b"default", b"font", b"subtext.dat"]

print("\n=== 关键字符串 ===")
found = []
for t in TARGETS:
    start = 0
    while True:
        k = data.find(t, start)
        if k < 0:
            break
        start = k + 1
        va = va_of_offset(k)
        if va:
            # 往前找字符串起点(可打印连续段)
            s = k
            while s > 0 and 32 <= data[s - 1] < 127:
                s -= 1
            e2 = k
            while e2 < len(data) and 32 <= data[e2] < 127:
                e2 += 1
            text = data[s:e2].decode("latin1")
            va_s = va_of_offset(s)
            found.append((text, va_s, va))
            print("  %-40s 字符串VA 0x%08X" % (text[:40], va_s))

text_va, code = code_bytes()
print("\n=== 代码里引用这些地址的位置 ===")
md = Cs(CS_ARCH_X86, CS_MODE_32)
md.skipdata = True
seen = set()
for text, va_s, va_hit in found:
    if va_s is None:
        continue
    for target in {va_s, va_hit}:
        pat = struct.pack("<I", target)
        p = 0
        while True:
            k = code.find(pat, p)
            if k < 0:
                break
            p = k + 1
            ins_va = text_va + k
            if (ins_va, target) in seen:
                continue
            seen.add((ins_va, target))
            lo = max(0, k - 12)
            print("  引用 %-28s @ 0x%08X" % (text[:28], ins_va - 12))
            for ins in md.disasm(code[lo:k + 8], text_va + lo):
                mark = "  <<<" if ins.address <= ins_va < ins.address + ins.size + 6 else ""
                print("      0x%08X  %-8s %s%s" % (ins.address, ins.mnemonic, ins.op_str, mark))
print("\n把上面的 0x%08X 附近地址填进反编译器的跳转栏即可" % (found[0][1] if found else 0))
