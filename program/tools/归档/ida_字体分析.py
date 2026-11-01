# -*- coding: utf-8 -*-
"""IDA 批量脚本: 反编译字体相关函数并导出伪代码

用法(由 PowerShell 调用):
   idat.exe -A -S"本脚本" WA2_chs.exe
"""
import os

import ida_auto
import ida_hexrays
import ida_funcs
import idautils
import ida_pro
import ida_ua
import ida_bytes

OUT = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\work\IDA_字体函数.txt"

ida_auto.auto_wait()

targets = [
    (0x004441F0, "字体加载入口"),
    (0x00437820, "字模读取函数"),
    (0x00444276, "调用字模读取处"),
]

lines = []
lines.append("=== IDA 反编译结果 ===\n")

for ea, name in targets:
    lines.append("\n" + "=" * 70)
    lines.append("### %s  0x%08X\n" % (name, ea))
    # 函数信息
    f = ida_funcs.get_func(ea)
    if f:
        lines.append("函数范围: 0x%08X - 0x%08X\n" % (f.start_ea, f.end_ea))
        # 被谁调用
        lines.append("调用者:\n")
        n = 0
        for x in idautils.XrefsTo(f.start_ea):
            lines.append("   0x%08X\n" % x.frm)
            n += 1
            if n > 20:
                lines.append("   ...\n")
                break
    try:
        cf = ida_hexrays.decompile(ea)
        if cf:
            lines.append(str(cf))
        else:
            lines.append("(反编译返回空)\n")
    except Exception as e:
        lines.append("反编译失败: %s\n" % e)
        # 退化为反汇编
        lines.append("--- 反汇编 ---\n")
        cur = f.start_ea if f else ea
        end = f.end_ea if f else ea + 0x120
        while cur < end:
            lines.append("0x%08X  %s\n" % (cur, ida_ua.generate_disasm_text(cur)))
            cur = ida_bytes.get_item_end(cur)

open(OUT, "w", encoding="utf-8").write("".join(lines))
print("已写出:", OUT)
ida_pro.qexit(0)
