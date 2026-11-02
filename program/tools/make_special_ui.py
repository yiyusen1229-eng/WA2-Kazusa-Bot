# -*- coding: utf-8 -*-
"""特别模式用图：把竖版滚动条精灵转成横向滑条，并把配置项底框里的箭头抠出来。

sys_00030.png 是解包出来的滚动条精灵（96x640），三列各有用途：
    第 1 列 x 3..28   常态轨道
    第 2 列 x 35..60  悬停态轨道（更亮的描边）
    第 3 列 x 65..92  亮色按钮 + 滑块（pill）
每列纵向：y 0..47 上箭头按钮 / 50..589 轨道 / 592..639 下箭头按钮。

设置界面的百分比滑条是横着放的，所以这里把「轨道」「滑块」各转 90°，
存成独立 PNG 给 CSS 用（素材不在仓库里，换机器要重跑这个脚本）。

sys_04100.png（配置项底框，400x128 = 4 帧 x 32）第 3 帧左边有个 ▶。
下拉面板要把这个箭头转 90°，所以拆成：
    item_frame.png  底框（箭头补掉，其它三帧原样）
    item_arrow.png  箭头（带 alpha，-90° 旋转用）

用法：
    python tools/make_special_ui.py
"""
import os
import sys

from PIL import Image, ImageDraw

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "res", "assets", "ui", "sys_00030.png")
OUT = os.path.join(BASE, "res", "assets", "ui", "special")

# (名字, 左, 上, 右, 下) —— 右下不含
SLICES = [
    ("slider_track",      3,  50, 29, 590),
    ("slider_track_hover", 35, 50, 61, 590),
]

# 滑块：原素材是一条长药丸（86x28），按用户要求做成小圆角方块。
# 颜色直接从药丸上取，保证和轨道是同一套配色。
KNOB_SRC = (65, 49, 93, 135)
KNOB_SIZE = 19
KNOB_RADIUS = 4


def _make_knob(pill):
    color = pill.getpixel((pill.width // 3, pill.height // 2))
    edge = (min(255, color[0] + 50), min(255, color[1] + 50), min(255, color[2] + 50), 255)
    im = Image.new("RGBA", (KNOB_SIZE, KNOB_SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, KNOB_SIZE - 1, KNOB_SIZE - 1],
                        radius=KNOB_RADIUS, fill=color, outline=edge, width=1)
    return im

# 恢复默认设置的按钮：sys_03030.png 是 208x72（3 帧 x 24 高），
# 左边写着 "DEFAULT"，只要右边的按钮本体（x 66..208），三帧原样保留。
RESET_SRC = os.path.join(BASE, "res", "assets", "ui", "sys_03030.png")
RESET_CROP = (66, 0, 208, 72)

# 配置项底框：sys_04100.png 是 400x128（4 帧 x 32 高），第 3 帧左边画着一个
# 白色三角箭头 ▶。下拉面板要自己把箭头转 90°，所以这里把箭头从底框上抠掉、
# 单独存一张带 alpha 的 item_arrow.png；底框存成 item_frame.png（其它三帧不动）。
FRAME_SRC = os.path.join(BASE, "res", "assets", "ui", "sys_04100.png")
FRAME_H = 32
ARROW_FRAME = 2            # 第 3 帧（从 0 数）
ARROW_REGION = (18, 8, 38, 25)   # 只在框左边这一小块里找箭头
ARROW_TH = 78              # 比该行背景亮这么多就算箭头（含抗锯齿边）


def _fit_row_bg(px, y, x_ranges):
    """用箭头左右两段像素做行内线性拟合，返回 (mx, my[3], slope[3])"""
    pts = [(x, px[x, y]) for a, b in x_ranges for x in range(a, b)]
    n = float(len(pts))
    mx = sum(p[0] for p in pts) / n
    my = [sum(p[1][i] for p in pts) / n for i in range(3)]
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    slope = []
    for i in range(3):
        sxy = sum((p[0] - mx) * (p[1][i] - my[i]) for p in pts)
        slope.append(sxy / sxx if sxx else 0.0)
    return mx, my, slope


def _make_item_frame(im):
    """从 4 帧底框里抠出箭头：返回 (补干净的 4 帧底框, 箭头 RGBA)"""
    frames = [im.crop((0, i * FRAME_H, im.width, (i + 1) * FRAME_H)) for i in range(4)]
    src = frames[ARROW_FRAME].convert("RGB")
    px = src.load()
    x0, y0, x1, y1 = ARROW_REGION
    fit = {y: _fit_row_bg(px, y, [(8, 20), (38, 52)]) for y in range(FRAME_H)}

    def bg_at(y, x):
        mx, my, slope = fit[y]
        return [my[i] + slope[i] * (x - mx) for i in range(3)]

    def lum(p):
        return (p[0] + p[1] + p[2]) / 3.0

    mask = set()
    for y in range(y0, y1):
        for x in range(x0, x1):
            bg = tuple(int(v) for v in bg_at(y, x))
            if lum(px[x, y]) - lum(bg) > ARROW_TH:
                mask.add((x, y))
    # 膨胀 1 圈：把箭头的抗锯齿边一起吃掉，否则补完会留一圈轮廓
    mask = {(x + dx, y + dy)
            for (x, y) in mask for dx in (-1, 0, 1) for dy in (-1, 0, 1)
            if 0 <= x + dx < src.width and 0 <= y + dy < FRAME_H}
    xs = [p[0] for p in mask]
    ys = [p[1] for p in mask]
    box = (min(xs), min(ys), max(xs) + 1, max(ys) + 1)

    clean = src.copy().convert("RGBA")
    cp = clean.load()
    for (x, y) in mask:
        cp[x, y] = tuple(max(0, min(255, int(v))) for v in bg_at(y, x)) + (255,)

    arrow = Image.new("RGBA", (box[2] - box[0], box[3] - box[1]), (0, 0, 0, 0))
    ap = arrow.load()
    for (x, y) in mask:
        bg = bg_at(y, x)
        v, bv = lum(px[x, y]), lum(tuple(int(t) for t in bg))
        a = max(0.0, min(1.0, (v - bv) / max(1.0, 255.0 - bv)))
        if a > 0.05:
            ap[x - box[0], y - box[1]] = (238, 255, 242, int(round(a * 255)))

    frames[ARROW_FRAME] = clean
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    for i, f in enumerate(frames):
        out.paste(f, (0, i * FRAME_H))
    return out, arrow, box


def main():
    if not os.path.exists(SRC):
        sys.exit("找不到 %s（先用 tools/check_assets.py 确认素材）" % SRC)
    im = Image.open(SRC).convert("RGBA")
    os.makedirs(OUT, exist_ok=True)
    for name, l, t, r, b in SLICES:
        piece = im.crop((l, t, r, b)).rotate(90, expand=True)
        path = os.path.join(OUT, name + ".png")
        piece.save(path)
        print("%-20s %dx%d -> %s" % (name, piece.width, piece.height, path))

    knob = _make_knob(im.crop(KNOB_SRC).rotate(90, expand=True))
    path = os.path.join(OUT, "slider_knob.png")
    knob.save(path)
    print("%-20s %dx%d -> %s" % ("slider_knob", knob.width, knob.height, path))

    if os.path.exists(RESET_SRC):
        btn = Image.open(RESET_SRC).convert("RGBA").crop(RESET_CROP)
        path = os.path.join(OUT, "reset_btn.png")
        btn.save(path)
        print("%-20s %dx%d -> %s" % ("reset_btn", btn.width, btn.height, path))
    else:
        print("跳过 reset_btn：找不到 %s" % RESET_SRC)

    if os.path.exists(FRAME_SRC):
        frame, arrow, box = _make_item_frame(Image.open(FRAME_SRC).convert("RGBA"))
        path = os.path.join(OUT, "item_frame.png")
        frame.save(path)
        print("%-20s %dx%d -> %s" % ("item_frame", frame.width, frame.height, path))
        path = os.path.join(OUT, "item_arrow.png")
        arrow.save(path)
        print("%-20s %dx%d（原位 %s）-> %s" % ("item_arrow", arrow.width, arrow.height, box, path))
    else:
        print("跳过 item_frame / item_arrow：找不到 %s" % FRAME_SRC)


if __name__ == "__main__":
    main()
