# -*- coding: utf-8 -*-
"""把「模拟位图字模」改成正确做法:
   整块文字按 30px 渲染(含描边), 最后整数倍放大到目标尺寸。
   这样不会出现行尾被裁, 描边粗细也随之等比。
"""
import re

P = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\app\gdi_text.py"
s = open(P, encoding="utf-8").read()

# 1) 移除上一版插在绘制分支里的缩略画布逻辑, 恢复普通绘制
old_block = """        if EMULATE_BITMAP and size > BITMAP_SIZE:
            # 先画到缩小版画布, 再整数倍放大 -> 复刻位图字模的栅格感
            f = size / float(BITMAP_SIZE)
            sw, sh = max(1, int(round(W / f))), max(1, int(round(H / f)))
            small = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
            sdr = ImageDraw.Draw(small)
            sft = _pil_font(BITMAP_SIZE)
            spad = (pad + outline_w) / f
            spitch = line_pitch / f
            for i, ln in enumerate(lines):
                y = spad + i * spitch
                for ex in range(embolden + 1):
                    for ey in range(embolden + 1):
                        sdr.text((spad + ex / f, y + ey / f), ln, font=sft,
                                 fill=(color[0], color[1], color[2], 255))
            base = small.resize((W, H), Image.NEAREST)
        else:
            dr = ImageDraw.Draw(base)
            for i, ln in enumerate(lines):
                y = pad + outline_w + i * line_pitch
                for ex in range(embolden + 1):
                    for ey in range(embolden + 1):
                        dr.text((pad + outline_w + ex, y + ey), ln, font=ft,
                                fill=(color[0], color[1], color[2], 255))"""

new_block = """        dr = ImageDraw.Draw(base)
        for i, ln in enumerate(lines):
            y = pad + outline_w + i * line_pitch
            for ex in range(embolden + 1):
                for ey in range(embolden + 1):
                    dr.text((pad + outline_w + ex, y + ey), ln, font=ft,
                            fill=(color[0], color[1], color[2], 255))"""

if old_block in s:
    s = s.replace(old_block, new_block, 1)
    print("已恢复普通绘制")
else:
    print("绘制段未匹配(可能已改过)")

# 2) 函数开头: 目标尺寸 > 30 时, 内部按 30px 渲染, 记下放大倍数
anchor = "    lines = wrap_text(text, maxw, size, face)"
if anchor in s and "upscale" not in s:
    s = s.replace(anchor,
"""    # 模拟游戏位图字模: 内部按 30px 渲染, 最后整数倍放大
    upscale = 1.0
    if EMULATE_BITMAP and size > BITMAP_SIZE:
        upscale = size / float(BITMAP_SIZE)
        size = BITMAP_SIZE
        maxw = max(1, int(maxw / upscale))

    lines = wrap_text(text, maxw, size, face)""", 1)
    print("已加内部 30px 渲染")

# 3) 返回前放大
old_ret = """    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue(), W, H"""
new_ret = """    if upscale > 1.0:
        W, H = int(round(W * upscale)), int(round(H * upscale))
        img = img.resize((W, H), Image.NEAREST)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue(), W, H"""
if old_ret in s:
    s = s.replace(old_ret, new_ret, 1)
    print("已加末尾放大")

open(P, "w", encoding="utf-8").write(s)

import ast
ast.parse(s)
print("语法 OK")
