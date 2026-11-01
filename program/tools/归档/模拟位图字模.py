# -*- coding: utf-8 -*-
"""让对话框文字模拟游戏的位图字模效果

游戏: 用 GDI 以约 30px 把字画进 32×32 的格子, 显示时再放大, 所以边缘略糊、有栅格感。
本补丁: 先用 30px 渲染到小图, 再用 NEAREST 整数倍放大, 最后走原来的描边/模糊流程。
"""
P = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\app\gdi_text.py"
s = open(P, encoding="utf-8").read()

if "EMULATE_BITMAP" in s:
    print("补丁已存在")
else:
    # 1) 参数
    s = s.replace(
        "PAD = 3",
        "PAD = 3\n\n# 模拟游戏位图字模: 先按 30px 渲染再放大\nEMULATE_BITMAP = True\nBITMAP_SIZE = 30",
        1,
    )

    # 2) 在绘制段前插入「小图放大」逻辑: 替换 PIL 绘制分支
    old = '''    ft = _pil_font(size)
    if ft is not None:
        base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        from PIL import ImageDraw
        dr = ImageDraw.Draw(base)
        for i, ln in enumerate(lines):
            y = pad + outline_w + i * line_pitch
            for ex in range(embolden + 1):
                for ey in range(embolden + 1):
                    dr.text((pad + outline_w + ex, y + ey), ln, font=ft,
                            fill=(color[0], color[1], color[2], 255))'''

    new = '''    ft = _pil_font(size)
    if ft is not None:
        base = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        from PIL import ImageDraw
        if EMULATE_BITMAP and size > BITMAP_SIZE:
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
                                fill=(color[0], color[1], color[2], 255))'''

    if old not in s:
        print("!! 未匹配绘制段, 需手工检查")
    else:
        s = s.replace(old, new, 1)
        # 3) 缓存版本 +1
        import re
        m = re.search(r"RENDER_VER\s*=\s*(\d+)", s)
        if m:
            s = s.replace(m.group(0), "RENDER_VER = %d" % (int(m.group(1)) + 1))
        open(P, "w", encoding="utf-8").write(s)
        print("补丁已写入")

import ast
ast.parse(open(P, encoding="utf-8").read())
print("语法 OK")
