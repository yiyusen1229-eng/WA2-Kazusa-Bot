# -*- coding: utf-8 -*-
"""选择分支的素材：从原版两张图里切出来（本地素材，不入库）。

源文件：`other/dev/game_pak/gh/gcn_unpack/`
  · sys_00200.tga（784×216）—— 选项条贴图，竖排三段，**每段 784×72**：
        段1 = 常态（顶部高光 + 条身 + 两端渐隐）
        段2 = 悬停**高亮层**（和段1 同画布；原版是把它**加**在段1 上，不是替换）
        段3 = 只有两端雪花（叠在条身上面的一层，也是加法）
  · sys_00011.tga（408×288）—— 菜单图集，里面有一块**小白牌**（带蓝色别针，
        实测 alpha 盒 x 219..236 / y 64..96 = 18×33）

产物（`program/res/assets/ui/choice/`）：
  bar_off.png   段1 原样（784×72）
  bar_on.png    **段1 + 段2 按加法烘成一张**（784×72，alpha 仍取段1 的）
  snow.png      段3 原样（784×72，两端雪花）
  tag.png       小白牌，按 alpha 裁到最小

为什么悬停要烘成一张、而不是叠两层实时相加：
  用 `mix-blend-mode: plus-lighter` 叠的时候，浏览器算的是
  `α出 = α源 + α底`（夹到 1）。选项层有 z-index，它的混合背景只有**条子自己**
  （不含背后的 CG），于是 α 一夹满，这一块就变**不透明**、CG 被顶掉——
  条子软边那几行正好是 α 小的地方，结果出现一圈明显的黑边／框线（实测最暗 −110）。
  改成「预先烘好、悬停只换图」之后，两张图的 **alpha 完全一样**，轮廓一模一样，
  结构上不可能再接出边；亮度用下面的补偿公式跟真加法对齐。

加法补偿公式（逐像素）：
  想还原的是  C = C0*α0 + C1*α1（预乘后相加）
  烘出来的图只有 alpha = α0，所以取  C' = (C0*α0 + C1*α1) / α0
  这样「C' 以 α0 盖上去」和「C0 以 α0 盖、再叠 C1*α1」预乘后等价。

用法：
    python program/tools/make_choice_assets.py
"""
import os

from PIL import Image

PROG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GCN = os.path.join(os.path.dirname(PROG), "other", "dev", "game_pak", "gh", "gcn_unpack")
OUT = os.path.join(PROG, "res", "assets", "ui", "choice")

# 图集里小白牌的 alpha 盒（手工定位后写死；改素材才需要动）
TAG_BOX = (219, 64, 237, 97)


def _save(im, name):
    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, name)
    im.save(dst)
    print("%-12s %-9s -> %s" % (name, "%dx%d" % im.size, dst))


def bake_hover(base, glow):
    """段1 + 段2 → 一张「悬停态」。alpha 保持段1 的，颜色按加法补偿。"""
    w, h = base.size
    bp, gp = base.load(), glow.load()
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    op = out.load()
    for y in range(h):
        for x in range(w):
            r0, g0, b0, a0 = bp[x, y]
            r1, g1, b1, a1 = gp[x, y]
            if a0 == 0:
                continue                     # 底子透明的地方留空，别把高亮的边扩出去
            # C' = (C0*a0 + C1*a1) / a0，逐通道夹到 255
            op[x, y] = (min(255, round((r0 * a0 + r1 * a1) / a0)),
                        min(255, round((g0 * a0 + g1 * a1) / a0)),
                        min(255, round((b0 * a0 + b1 * a1) / a0)),
                        a0)
    return out


def main():
    bar = Image.open(os.path.join(GCN, "sys_00200.tga")).convert("RGBA")
    w, h = bar.size
    seg = h // 3
    off = bar.crop((0, 0, w, seg))
    hl = bar.crop((0, seg, w, seg * 2))
    _save(off, "bar_off.png")
    _save(bake_hover(off, hl), "bar_on.png")
    _save(bar.crop((0, seg * 2, w, seg * 3)), "snow.png")

    atlas = Image.open(os.path.join(GCN, "sys_00011.tga")).convert("RGBA")
    tag = atlas.crop(TAG_BOX)
    bbox = tag.split()[3].getbbox()
    if bbox:
        tag = tag.crop(bbox)
    _save(tag, "tag.png")

    # 旧版本的拆件：雪花已经并进 snow.png，删掉免得下次又有人用
    for old in ("snow_l.png", "snow_r.png"):
        p = os.path.join(OUT, old)
        if os.path.exists(p):
            os.remove(p)
            print("删掉旧拆件 %s" % p)


if __name__ == "__main__":
    main()
