# -*- coding: utf-8 -*-
"""用映射表算中文(GBK 编码)的序号, 抠出对应字模格子看像不像"""
import os
import struct

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BASE = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot"
EXE = r"E:\Games\GALGAMES\WHITE ALBUM2\WA2_chs.exe"
ATLAS = os.path.join(BASE, r"work\fnt_only\戃塭80.tga")
CELL = 32
COLS = 100

d = open(EXE, "rb").read()
e = struct.unpack_from("<I", d, 0x3C)[0]
nsec = struct.unpack_from("<H", d, e + 6)[0]
optsz = struct.unpack_from("<H", d, e + 20)[0]
sec = e + 24 + optsz
base_va = struct.unpack_from("<I", d, e + 24 + 28)[0]
secs = []
for i in range(nsec):
    o = sec + i * 40
    vs, va, rs, ra = struct.unpack_from("<IIII", d, o + 8)
    secs.append((base_va + va, rs, ra))


def off_of(va):
    for sva, rs, ra in secs:
        if sva <= va < sva + rs:
            return ra + (va - sva)
    return None


o_tbl = off_of(0x004C22C0)
rows = []
for n in range(53):
    bs, lo, hi = struct.unpack_from("<IHH", d, o_tbl + n * 8)
    rows.append((lo, hi, bs))


def glyph_index_bytes(b1, b2):
    code = (b1 << 8) | b2
    for lo, hi, bs in rows:
        if lo <= code <= hi:
            return code + bs - lo
    return None


alpha = np.array(Image.open(ATLAS).convert("RGBA").split()[3])
ROWS = alpha.shape[0] // CELL


def cell(k):
    if k is None or k < 0 or k >= ROWS * COLS:
        return None
    r, c = divmod(k, COLS)
    return alpha[r * CELL:(r + 1) * CELL, c * CELL:(c + 1) * CELL]


TESTS = "吧这开始游戏你我是的"
f = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 30)
tiles = []
for ch in TESTS:
    gb = ch.encode("gbk")
    idx = glyph_index_bytes(gb[0], gb[1])
    got = cell(idx)
    ref = Image.new("L", (CELL, CELL), 0)
    dd = ImageDraw.Draw(ref)
    dd.text((0, 0), ch, font=f, fill=255)
    print("  %s  GBK %02X%02X  序号 %5s  格子有内容 %s" % (
        ch, gb[0], gb[1], idx,
        "是" if (got is not None and got.sum() > 200) else "空/无"))
    tiles.append((ch, got, ref))

# 拼图: 每行 = 该字图集格子 | 正常字形
sheet = Image.new("L", (CELL * 2 * len(tiles), CELL * 4), 0)
for i, (ch, got, ref) in enumerate(tiles):
    if got is not None:
        sheet.paste(Image.fromarray((got > 110).astype(np.uint8) * 255), (i * CELL * 2, 0))
    sheet.paste(ref, (i * CELL * 2 + CELL, 0))
    # 再放两行放大图
big = sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST)
big.save(os.path.join(BASE, "work", "序号验证.png"))
print("已存 序号验证.png (左边=图集格子, 右边=该字正常样子)")
