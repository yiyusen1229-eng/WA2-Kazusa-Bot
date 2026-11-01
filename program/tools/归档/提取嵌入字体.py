# -*- coding: utf-8 -*-
"""从 ck-gal.pak 里提取那个 TTF 条目"""
import os
import struct

G = r"E:\Games\GALGAMES\WHITE ALBUM2"
PAK = os.path.join(G, "ck-gal.pak")
OUT = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\game_pak\ckgal"

d = open(PAK, "rb").read()
cnt = struct.unpack_from("<I", d, 8)[0]
print("条目数:", cnt)

for i in range(cnt):
    off = 16 + i * 44
    ent = d[off:off + 44]
    if len(ent) < 44:
        break
    name = ent[4:36].split(b"\x00")[0]
    foff, fsz = struct.unpack_from("<II", ent, 36)
    magic = d[foff:foff + 4]
    if magic == b"\x00\x01\x00\x00":
        print("\n命中条目 %d" % i)
        print("  名字原始字节:", name.hex(), " 可打印:", "".join(chr(c) if 32 <= c < 127 else "." for c in name))
        print("  偏移 %d  声明大小 %d" % (foff, fsz))
        # 声明大小荒谬, 用下一个条目的起点或文件末尾兜底
        next_off = len(d)
        for j in range(cnt):
            o2 = 16 + j * 44
            fo2, _ = struct.unpack_from("<II", d, o2 + 36)
            if fo2 > foff:
                next_off = min(next_off, fo2)
        real = next_off - foff
        print("  实际可用长度(到下一个条目): %d" % real)
        blob = d[foff:foff + real]
        os.makedirs(OUT, exist_ok=True)
        fp = os.path.join(OUT, "ckgal_embedded.ttf")
        open(fp, "wb").write(blob)
        print("  已写出:", fp, len(blob), "字节")
        # 读 TTF 表目录
        numTables = struct.unpack_from(">H", blob, 4)[0]
        print("  TTF 表数量:", numTables)
        for t in range(min(numTables, 20)):
            tag = blob[12 + t * 16:16 + t * 16]
            chk, offs, ln = struct.unpack_from(">III", blob, 16 + t * 16)
            print("    %-5s 偏移 %8d 长度 %8d" % (tag.decode("latin1"), offs, ln))
        break
