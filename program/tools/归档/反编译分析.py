# -*- coding: utf-8 -*-
"""静态分析 v2: 用字节特征直接定位 D3D9 虚表调用, 不依赖全段反汇编

D3D9 的 IDirect3DDevice9 虚表:
  SetRenderState(index 57) -> 偏移 57*4 = 0xE4
调用编码(32 位):
  FF 90 E4 00 00 00   call dword ptr [eax+0xE4]
  FF 91 E4 00 00 00   call dword ptr [ecx+0xE4]
  FF 92/93 ...        [edx] / [ebx]
找出这些点, 再把前面 40 字节反汇编, 看 push 的常量。
"""
import struct

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

EXE = r"E:\IDM下载目录\ollydbg\WA2_chs.exe"
D3D_RS_SRCBLEND = 0x13
D3D_RS_DESTBLEND = 0x14
BLEND = {0: "ZERO", 1: "ONE??", 2: "ONE", 3: "SRCCOLOR", 4: "INVSRCCOLOR",
         5: "SRCALPHA", 6: "INVSRCALPHA", 7: "DESTALPHA", 8: "INVDESTALPHA",
         9: "DESTCOLOR", 10: "INVDESTCOLOR", 11: "SRCALPHASAT"}

data = open(EXE, "rb").read()
e = struct.unpack_from("<I", data, 0x3C)[0]
nsec = struct.unpack_from("<H", data, e + 6)[0]
optsz = struct.unpack_from("<H", data, e + 20)[0]
sec = e + 24 + optsz
image_base = struct.unpack_from("<I", data, e + 24 + 28)[0]

code, code_va = None, 0
for i in range(nsec):
    o = sec + i * 40
    name = data[o:o + 8].rstrip(b"\x00").decode("latin1")
    vsize, vaddr, rsize, raddr = struct.unpack_from("<IIII", data, o + 8)
    if name == ".text":
        code = data[raddr:raddr + rsize]
        code_va = image_base + vaddr
print("代码段 %d 字节 @ 0x%08X" % (len(code), code_va))

md = Cs(CS_ARCH_X86, CS_MODE_32)

PATTERNS = []
for reg, b in (("eax", 0x90), ("ecx", 0x91), ("edx", 0x92), ("ebx", 0x93),
               ("esp", 0x94), ("ebp", 0x95), ("esi", 0x96), ("edi", 0x97)):
    PATTERNS.append((bytes([0xFF, b, 0xE4, 0x00, 0x00, 0x00]), reg))

hits = []
for pat, reg in PATTERNS:
    start = 0
    while True:
        k = code.find(pat, start)
        if k < 0:
            break
        hits.append((code_va + k, reg))
        start = k + 1

hits.sort()
print("call [reg+0xE4] 命中:", len(hits))

found = []
for va, reg in hits:
    off = va - code_va
    win = code[max(0, off - 48):off + 6]
    win_va = va - min(48, off)
    pushes = []
    for ins in md.disasm(win, win_va):
        if ins.mnemonic == "push" and ins.op_str.startswith("0x"):
            try:
                pushes.append(int(ins.op_str, 16))
            except ValueError:
                pass
    tag = []
    if D3D_RS_SRCBLEND in pushes:
        tag.append("SRCBLEND")
    if D3D_RS_DESTBLEND in pushes:
        tag.append("DESTBLEND")
    if tag:
        found.append((va, pushes[-6:], tag))

print("疑似混合状态设置点:", len(found))
for va, pushes, tag in found[:30]:
    vals = [BLEND.get(p, hex(p)) for p in pushes]
    print("  0x%08X  push序列 %s   %s" % (va, vals, ",".join(tag)))
