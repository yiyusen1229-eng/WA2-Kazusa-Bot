# -*- coding: utf-8 -*-
"""解析 OllyDbg 的 .udd 文件结构

OllyDbg 1.10 的 udd 是按 记录 存的:
   0x0A + 4 字节标签 + u32 长度 + 数据
把每条记录列出来, 重点看:
   Comm / Labl / Bpnt / Pnam / Patc  —— 注释/标号/断点/补丁
"""
import os
import struct
import sys

PATH = sys.argv[1] if len(sys.argv) > 1 else r"E:\IDM下载目录\ollydbg\WA2_chs.udd"

data = open(PATH, "rb").read()
print("文件: %s  %d 字节" % (os.path.basename(PATH), len(data)))

recs = []
i = 0
n = len(data)
while i < n - 5:
    if data[i] == 0x0A:
        tag = data[i + 1:i + 5]
        if all(32 <= c < 127 for c in tag):
            ln = struct.unpack_from("<I", data, i + 5)[0]
            if 0 <= ln <= n - i - 9:
                recs.append((i, tag.decode("latin1"), ln, data[i + 9:i + 9 + ln]))
                i += 9 + ln
                continue
    i += 1

print("记录数:", len(recs))
from collections import Counter
cnt = Counter(t for _, t, _, _ in recs)
for t, c in cnt.most_common(20):
    print("   %-6s %d 条" % (t, c))

print("\n--- 含文本的记录 ---")
for off, tag, ln, payload in recs:
    if tag in ("Comm", "Labl", "Bpnt", "Pnam", "Patc", "Modl", "Prmp"):
        txt = payload.decode("gbk", "ignore")
        txt = "".join(ch if ch.isprintable() else "." for ch in txt)
        print("   %-5s (0x%06X, %d 字节): %s" % (tag, off, ln, txt[:120]))
