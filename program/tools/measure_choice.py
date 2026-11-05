# -*- coding: utf-8 -*-
"""选项条几何测量：用同一套检测器量「原版整帧」和「自己渲染的截图」。

用途（对应 other/docs/界面像素测量方法.md 的 Step 1~3 与 Step 7）：
  · 改 choice.css 之后，别靠眼睛对图，用它把渲染结果再量一遍，和原版数字并排比。
  · 只依赖 Pillow（项目 venv 里没有 numpy）。

检测器原理（为什么不用亮度）：
  选项条是**半透明青色**的，压在人物 CG 上时亮度完全不可靠（上一版就是这么量错的：
  把高光当条高，读出 22，实际 45）。但「蓝减红」(B-R) 很稳：
  条子是青蓝的，B-R 高；背景再亮也抬不高 B-R。
  沿 y 取「中位数」压掉文字，再找 50% 交叉点定上下沿；
  沿 x 取中位数找左右端（条子两端是渐隐的，所以只认 50% 点）。

换算：原版整帧 2730×1536 → 800×450 舞台，系数 800/2730 = 0.29304；
  非 800×450 的图会自动缩放（截图先裁黑边再缩放）。

用法：
    python program/tools/measure_choice.py <图> [<图2> ...]
    python program/tools/measure_choice.py --compare 原版.png 渲染.png

输出：每条的上沿/下沿/高、行距、左右端/宽，以及在贴图坐标里的「quad 上沿」
      （条子贴图 50% 不透明处离帧顶 11.5/72，×0.625 = 7.2px）。
"""
import sys

from PIL import Image

STAGE_W, STAGE_H = 800, 450
XWIN = (380, 540)        # 取剖面的横窗：条子中段，避开文字（229~350）和两端雪花
YWIN = (100, 345)        # 找条子的纵向范围
TEX_TOP_INSET = 11.5 * 0.625   # 贴图里 50% 不透明的行 → 舞台上 = 7.19px

# 基准值 = 原版整帧（program/work_scratch/orig_game.jpg → 800×450）用同一个检测器的读数。
# 校验的是「渲染结果量出来像不像原版」，不是「像不像 CSS 里写的数」——所以这里钉原版读数。
#
# 为什么以「最亮那条」（悬停态）为准：
#   常态条是半透明的（alpha 最高 204），它的 50% 交叉点会被背景带跑，同一份 CSS
#   换个背景就能量出差 3~4px；悬停态几乎不透明（alpha 255），读数才稳（实测差 ≤1.3px）。
#   所以上下沿以 strong_* 判，行距和左右端只做参考（容差放宽，背景一换就会漂）。
EXPECT = {
    "strong_top":    (207.8, 2.0),
    "strong_bottom": (232.7, 2.0),
    "left50":        (175.3, 4.0),
    "pitch":         (51.8, 3.0),
}
# 不与基准门限的项：条宽。右端那一段被**右雪花**压着（雪花在条内 x 416~452），
# 亮度剖面在那里会先被判成"条子结束"，量出来短 50px；所以只打印、不做判定。
# 宽度 490 由两处独立证据钉住：雪花模板互相关（两朵花心相距 392.5 = 628×0.625）
# 和「把素材按 490×45 贴回原版整帧，边沿/雪花/小白牌全部对得上」。


def _load_stage(path):
    """读图 → (800×450 的 RGB 图, 说明)"""
    im = Image.open(path).convert("RGB")
    w, h = im.size
    note = "%dx%d" % (w, h)
    if (w, h) != (STAGE_W, STAGE_H):
        # 先裁掉可能的黑边，再整幅缩到舞台尺寸
        gray = im.convert("L")
        bbox = gray.point(lambda v: 255 if v > 12 else 0).getbbox()
        if bbox and (bbox[2] - bbox[0]) > 200 and (bbox[3] - bbox[1]) > 100:
            im = im.crop(bbox)
            note += " →裁到 %dx%d" % im.size
        im = im.resize((STAGE_W, STAGE_H), Image.LANCZOS)
        note += " →缩放 800x450"
    return im, note


def _br_pixels(im):
    """(原始字节, 宽高)。用 tobytes 而不是 getdata：Pillow 14 起 getdata 已弃用"""
    return im.tobytes(), im.size


def _b(data, W, x, y):
    return data[(y * W + x) * 3 + 2]


def _r(data, W, x, y):
    return data[(y * W + x) * 3]


def _median(vals):
    vals = sorted(vals)
    n = len(vals)
    return vals[n // 2] if n else 0


def _cross(prof, i0, i1, mid, rising):
    """在 prof[i0..i1] 上找 50% 交叉点（线性插值）"""
    for i in range(i0, i1):
        a, b = prof[i], prof[i + 1]
        if rising and a < mid <= b:
            return i + (mid - a) / float(b - a)
        if (not rising) and a > mid >= b:
            return i + (a - mid) / float(a - b)
    return None


def _row_profile(data, W):
    x0, x1 = XWIN
    prof = {}
    for y in range(YWIN[0], YWIN[1]):
        prof[y] = _median([_b(data, W, x, y) - _r(data, W, x, y) for x in range(x0, x1)])
    return prof


def _bands(prof):
    """找条子：局部极大 → 往两边找 50% 交叉点。返回 [(top, bottom, peak)]"""
    ys = sorted(prof)
    peaks = []
    for i in range(1, len(ys) - 1):
        y = ys[i]
        if prof[y] >= prof[ys[i - 1]] and prof[y] >= prof[ys[i + 1]] and prof[y] > 60:
            peaks.append(y)
    # 平台会有好几个等值极大：先按间隔合并
    merged = []
    for y in peaks:
        if merged and y - merged[-1] <= 6:
            if prof[y] > prof[merged[-1]]:
                merged[-1] = y
        else:
            merged.append(y)
    out = []
    for y in merged:
        left = max(YWIN[0], y - 40)
        right = min(YWIN[1] - 1, y + 40)
        base = _median([prof[k] for k in list(range(left, max(left + 1, y - 18))) +
                        list(range(min(right, y + 18), right))] or [prof[y]])
        mid = (base + prof[y]) / 2.0
        top = _cross(prof, left, y, mid, True)
        bot = _cross(prof, y, right, mid, False)
        if top is None or bot is None:
            continue
        # 同一个平台被拆成两条：上沿差 <12px 的丢掉
        if out and abs(top - out[-1][0]) < 12:
            continue
        out.append((top, bot, prof[y]))
    return out


def _cols(data, W, top, bot):
    """沿 x 取横向剖面。

    只取条子**最上面那几行**：条子顶边是一条贯通全宽的高光线，而中间那些行会被
    文字占掉大半（悬停态文字 16 行 / 条厚 25 行），中位数会被字带跑，
    量出来的右端会停在文字那里（实测短 50px）。
    """
    y0 = int(round(top))
    rows = [y for y in range(y0, min(y0 + 4, STAGE_H)) if y >= 0]
    if not rows:
        return {x: 0 for x in range(W)}
    prof = {}
    for x in range(0, W):
        prof[x] = _median([_b(data, W, x, y) - _r(data, W, x, y) for y in rows])
    return prof


def _xends(prof, y_mid):
    """条子左右端：两个端头各自用自己的邻域当基线，取 50% 交叉点"""
    base_l = _median([prof[x] for x in range(130, 152)])
    base_r = _median([prof[x] for x in range(660, 682)])
    peak = max(prof[x] for x in range(220, 600))
    mid_l = (base_l + peak) / 2.0
    mid_r = (base_r + peak) / 2.0
    left = _cross(prof, 130, 300, mid_l, True)
    right = _cross(prof, 400, 690, mid_r, False)
    return left, right, peak


def measure(path):
    im, note = _load_stage(path)
    data, (W, H) = _br_pixels(im)
    prof = _row_profile(data, W)
    bands = _bands(prof)
    res = {"path": path, "note": note, "bands": bands}
    if len(bands) >= 2:
        res["pitch"] = bands[1][0] - bands[0][0]
    elif len(bands) == 1:
        res["pitch"] = None
    if bands:
        # 最亮那条 = 悬停态：alpha 满，50% 交叉点不会被背景带跑
        strong = max(bands, key=lambda b: b[2])
        res["strong"] = strong
        cprof = _cols(data, W, strong[0], strong[1])
        left, right, _pk = _xends(cprof, (strong[0] + strong[1]) / 2)
        res["left"], res["right"] = left, right
        res["width"] = (right - left) if (left is not None and right is not None) else None
    return res


def report(res):
    print("=" * 66)
    print("%s\n  %s" % (res["path"], res["note"]))
    bands = res["bands"]
    if not bands:
        print("  没找到选项条（这张图里没有？或者剖面窗 XWIN 要挪）")
        return False
    print("  找到 %d 条：" % len(bands))
    for i, (top, bot, pk) in enumerate(bands):
        print("    第%d条  上沿 %6.1f  下沿 %6.1f  厚度 %5.1f  峰值 %3d"
              % (i + 1, top, bot, bot - top, pk))
    print("  行距 %s" % ("%.1f" % res["pitch"] if res.get("pitch") else "—（只有一条）"))
    s = res.get("strong")
    if s:
        print("  最亮那条（悬停态，读数最稳） 上沿 %.1f  下沿 %.1f  峰值 %d"
              % (s[0], s[1], s[2]))
    if res.get("width"):
        print("  左端(50%%) %6.1f  右端 %6.1f  宽 %6.1f"
              % (res["left"], res["right"], res["width"]))
    quad0 = bands[0][0] - TEX_TOP_INSET
    print("  第1条 quad 上沿 %6.1f（= 上沿 %.1f - %.2f）" % (quad0, bands[0][0], TEX_TOP_INSET))
    return True


def check_expect(res):
    """把实测和「原版读数」并排比（这是文档 Step 7 的回测）"""
    if not res["bands"]:
        print("  （跳过回测：没找到条子）")
        return 0
    s = res.get("strong") or res["bands"][0]
    got = {"strong_top": s[0],
           "strong_bottom": s[1],
           "left50": res.get("left"),
           "pitch": res.get("pitch")}
    bad = 0
    print("  回测（基准 = 原版整帧同一检测器读数）：")
    for k in ("strong_top", "strong_bottom", "left50", "pitch"):
        exp, tol = EXPECT[k]
        v = got.get(k)
        if v is None:
            continue
        d = v - exp
        flag = "√" if abs(d) <= tol else "×"
        if abs(d) > tol:
            bad += 1
        print("    %-13s 原版 %7.1f  实测 %7.1f  差 %+6.1f  (容差 %.0f) %s"
              % (k, exp, v, d, tol, flag))
    return bad


def compare(a, b):
    """两条输出并排，差 >2px 提示"""
    ra, rb = a, b
    ok = report(ra) and report(rb)
    if not ok:
        return 1
    print("-" * 66)
    print("并排对比（%s → %s）" % (ra["path"], rb["path"]))
    rows = []
    rows.append(("第1条上沿", ra["bands"][0][0], rb["bands"][0][0]))
    rows.append(("第1条下沿", ra["bands"][0][1], rb["bands"][0][1]))
    if ra.get("pitch") and rb.get("pitch"):
        rows.append(("行距", ra["pitch"], rb["pitch"]))
    if ra.get("width") and rb.get("width"):
        rows.append(("左端", ra["left"], rb["left"]))
        rows.append(("条宽", ra["width"], rb["width"]))
    bad = 0
    for name, va, vb in rows:
        d = vb - va
        flag = "√" if abs(d) <= 2.0 else "×"
        if abs(d) > 2.0:
            bad += 1
        print("  %-10s 原版 %7.1f  渲染 %7.1f  差 %+6.1f  %s" % (name, va, vb, d, flag))
    print("  → %s" % ("全部 ≤2px" if not bad else "有 %d 项超过 2px，回去改 choice.css" % bad))
    return 0 if not bad else 1


def main(argv):
    files = [a for a in argv if not a.startswith("-")]
    if not files:
        print(__doc__)
        return 2
    if "--compare" in argv and len(files) >= 2:
        a = measure(files[0])
        b = measure(files[1])
        if not (report(a) and report(b)):
            return 1
        return compare(a, b)
    bad = 0
    for f in files:
        res = measure(f)
        if not report(res):
            bad += 1
            continue
        bad += check_expect(res)
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
