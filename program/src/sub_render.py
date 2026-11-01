# -*- coding: utf-8 -*-
"""字幕渲染 —— 优先直接搬用补丁字模

两套来源:
  1. 补丁的 subfont.tga（891 个格子）—— 直接贴，像素级 1:1
  2. 字模里没有的字 —— 用拟合出的参数（雅黑常规 27px、偏移 (3,-3)、2px 描边）现画

这样只要字在补丁字库里, 输出就和游戏里一模一样。

补丁源码依据 (script/sub_compiler.py):
    FONT_SIZE = 28
    FONT_STROKE = 2
    FONT_OCCUPATION = FONT_SIZE + 2*FONT_STROKE   # 32
    FONT_PER_LINE = 20
    charset = sorted(set(所有字幕字符))
    draw.text((2 + 32*(i%20), 2 + 32*(i//20) - 2), ch, 'white', font,
              stroke_width=2, stroke_fill='black')

引擎绘制 (WA2SubPatch_TextRenderer.cpp):
    每字取 32×32 格子, pos.x += 28
"""
import json
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(BASE, "assets")

STRICT = os.environ.get("WA2_STRICT", "1") != "0"

FONT_SIZE = 28
FONT_STROKE = 2
FONT_OCCUPATION = FONT_SIZE + 2 * FONT_STROKE      # 32
FONT_ADVANCE = FONT_SIZE                           # 28
# 半角字符的紧凑步进（tight 模式）：数字/字母不再占满 28px 全角格
TIGHT_ADVANCE = 16
FONT_PER_LINE = 20
SUBTITLE_TOP = 40
SCREEN_WIDTH = 1280

FONT_PATH = r"C:/Windows/Fonts/msyh.ttc"
STRICT_FONT = r"C:/Windows/Fonts/msyh.ttc"
STRICT_SIZE = 27
STRICT_DX = 3
STRICT_DY = -3

FILL_COLOR = (255, 255, 255, 255)
STROKE_COLOR = (0, 0, 0, 255)
BLUR = 0.0
VERT_SQUASH = 1.0
ADVANCE_TWEAK = 1.0
MARGIN = 0

# ---------------------------------------------------------------- 补丁字模
# 两份字模: 本篇(20 列) + 特别篇(30 列), 合并后覆盖约 1600 个字
_ATLASES = None
_CHARMAP = None


def _load_atlas():
    global _ATLASES, _CHARMAP
    if _ATLASES is not None:
        return
    _ATLASES = []
    _CHARMAP = {}
    # 只用本篇字模: 索引已验证准确 (shift 0, IoU 0.864)
    # 特别篇那份 sub.yaml 与生成图集的不同步, 会取错字, 弃用
    spec = [
        ("subfont.tga", "subfont_charset.json", 20),
    ]
    for tga, js, cols in spec:
        tp = os.path.join(ASSETS, tga)
        jp = os.path.join(ASSETS, js)
        if not (os.path.exists(tp) and os.path.exists(jp)):
            continue
        try:
            im = Image.open(tp).convert("RGBA")
            chars = json.load(open(jp, encoding="utf-8"))
        except Exception:
            continue
        src = len(_ATLASES)
        _ATLASES.append((im, cols))
        for i, c in enumerate(chars):
            if c not in _CHARMAP:
                _CHARMAP[c] = (src, i)


def atlas_coverage():
    _load_atlas()
    return len(_CHARMAP)



def _cell(index, cols, atlas):
    cx = (index % cols) * FONT_OCCUPATION
    cy = (index // cols) * FONT_OCCUPATION
    return atlas.crop((cx, cy, cx + FONT_OCCUPATION, cy + FONT_OCCUPATION))


def _render_char(ch):
    """字模里没有的字, 按拟合参数现画一个 32×32 格子"""
    cell = Image.new("RGBA", (FONT_OCCUPATION, FONT_OCCUPATION), (0, 0, 0, 0))
    d = ImageDraw.Draw(cell)
    font = ImageFont.truetype(STRICT_FONT, STRICT_SIZE)
    d.text((STRICT_DX, STRICT_DY), ch, FILL_COLOR, font,
           stroke_width=FONT_STROKE, stroke_fill=STROKE_COLOR)
    return cell


def _draw_line_strict(text, tight=False):
    _load_atlas()
    xs = []
    x = 0
    for ch in text:
        xs.append(x)
        # tight：半角字符（数字/字母/符号）不走 28px 全角格子，挤紧一点
        x += TIGHT_ADVANCE if (tight and ord(ch) < 128) else FONT_ADVANCE
    w = x + FONT_STROKE * 2
    canvas = Image.new("RGBA", (max(1, w), FONT_OCCUPATION), (0, 0, 0, 0))
    for i, ch in enumerate(text):
        hit = _CHARMAP.get(ch)
        if hit:
            src, idx = hit
            atlas, cols = _ATLASES[src]
            cell = _cell(idx, cols, atlas)
        else:
            cell = _render_char(ch)
        canvas.alpha_composite(cell, (xs[i], 0))
    return canvas



def _draw_line_soft(text, font_path=FONT_PATH, stroke=True):
    """非严格模式: 目视调校的那套"""
    w = int(FONT_ADVANCE * 0.98 * len(text)) + FONT_STROKE * 6 + 12
    canvas = Image.new("RGBA", (max(1, w), 72), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(font_path, FONT_SIZE)
    x = FONT_STROKE * 2
    for ch in text:
        d.text((x, 8), ch, (245, 247, 248, 255), font,
               stroke_width=FONT_STROKE if stroke else 0,
               stroke_fill=STROKE_COLOR)
        x += FONT_ADVANCE * 0.98
    return canvas


def tint_rgba(img, hexcolor):
    """把白色字染成指定颜色（只改 RGB，alpha 不动）"""
    try:
        c = hexcolor.lstrip("#")
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except Exception:
        return img
    px = img.split()
    rgb = Image.merge("RGB", px[:3])
    lut = (r / 255.0, g / 255.0, b / 255.0)
    ch = rgb.split()
    ch = [ch[0].point(lambda v, k=lut[0]: int(v * k)),
          ch[1].point(lambda v, k=lut[1]: int(v * k)),
          ch[2].point(lambda v, k=lut[2]: int(v * k))]
    out = Image.merge("RGBA", (ch[0], ch[1], ch[2], px[3]))
    return out


def render_line(text, font_path=FONT_PATH, stroke=True, margin=None, tight=False):
    text = text.replace("\r", "")
    if not text:
        text = " "
    if STRICT:
        return _draw_line_strict(text, tight)

    canvas = _draw_line_soft(text, font_path, stroke)
    canvas = canvas.resize((canvas.width, max(1, int(canvas.height * 0.97))), Image.BILINEAR)
    canvas = canvas.filter(ImageFilter.GaussianBlur(0.7))
    bb = canvas.split()[3].getbbox()
    if bb:
        mg = 4
        canvas = canvas.crop((max(0, bb[0] - mg), max(0, bb[1] - mg),
                              min(canvas.width, bb[2] + mg), min(canvas.height, bb[3] + mg)))
    return canvas


def render_block(text, maxw=1200, stroke=True, margin=None, per_line=None, color=None, tight=False):
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if len(cur) >= (int(per_line) if per_line else FONT_PER_LINE) or len(cur) * FONT_ADVANCE > maxw:
            lines.append(cur)
            cur = ""
        cur += ch
    lines.append(cur)

    imgs = [render_line(ln, FONT_PATH, stroke, margin, tight) for ln in lines]
    W = max(i.width for i in imgs)
    line_h = FONT_OCCUPATION if STRICT else max(i.height for i in imgs)
    out = Image.new("RGBA", (W, line_h * len(imgs)), (0, 0, 0, 0))
    for i, im in enumerate(imgs):
        out.alpha_composite(im, (0, i * line_h))
    if color:
        out = tint_rgba(out, color)
    return out
