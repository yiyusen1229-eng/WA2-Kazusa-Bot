# -*- coding: utf-8 -*-
"""烤「翻页提示」图标：对话文字打完、还有下一页时在末尾闪动的页面图标。

素材来源（本地，不进仓库）：原版 `page_02` 精灵动画。
    .ani 描述 120 帧、60fps；每帧 28×28，在 256×512 的图集里按 30px 网格排布
    （从 (1,1) 开始，8 列 × 15 行）。帧画面是页面里的「文字行」在流动/明暗变化。

输出：`res/assets/ui/text/page_cursor.png` —— 120 帧横向排成一条 3360×28 的图，
      前端用 `background-position` + `steps(120)` 播；2 秒一轮（60fps）。

用法：
    python tools/bake_page_cursor.py
    python tools/bake_page_cursor.py --src <page_02.tga 所在目录或文件>
"""
import argparse
import os
import sys

from PIL import Image

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "res", "assets", "ui", "text", "page_cursor.png")

# 默认读本机解包出来的原版素材
DEFAULT_SRC = os.path.join(os.path.dirname(BASE), "other", "dev", "game_pak",
                           "gh", "gcn_unpack", "page_02.tga")

FRAMES = 120
CELL = 30          # 图集里每格的步进
ICON = 28          # 每帧实际像素
ORIGIN = (1, 1)    # 第一帧的左上角
COLS = 8


def load_frames(src):
    im = Image.open(src).convert("RGBA")
    frames = []
    for i in range(FRAMES):
        r, c = divmod(i, COLS)
        x = ORIGIN[0] + c * CELL
        y = ORIGIN[1] + r * CELL
        if x + ICON > im.width or y + ICON > im.height:
            raise SystemExit("图集尺寸不够：%dx%d，第 %d 帧越界" % (im.width, im.height, i))
        frames.append(im.crop((x, y, x + ICON, y + ICON)))
    return frames


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="烤翻页提示图标")
    ap.add_argument("--src", default=os.environ.get("WA2_PAGE_SRC") or DEFAULT_SRC)
    args = ap.parse_args()

    if not os.path.exists(args.src):
        print("找不到素材：%s" % args.src)
        print("（本地解包的原版素材，仓库里没有；给出 --src 指定 page_02.tga）")
        return 1

    frames = load_frames(args.src)
    strip = Image.new("RGBA", (ICON * len(frames), ICON), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        strip.alpha_composite(f, (i * ICON, 0))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    strip.save(OUT, optimize=True)
    print("帧数 %d，尺寸 %dx%d → %s（%.1f KB）" % (
        len(frames), strip.width, strip.height, OUT,
        os.path.getsize(OUT) / 1024.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
