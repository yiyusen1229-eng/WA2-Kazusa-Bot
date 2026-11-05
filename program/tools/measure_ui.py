# -*- coding: utf-8 -*-
"""界面像素测量（#14）：把《界面像素测量方法.md》的步骤写成一条命令。

不装 numpy 也能跑（项目 venv 里没有）：用 256 桶直方图算中位数，纯 Python + Pillow。

用法：
    # 1) 量原版整帧截图（自动换算到 800×450 舞台）
    python tools/measure_ui.py profile program/g2.jpg

    # 2) 量自己渲染的网页截图（自动裁黑边 + 缩到 800×450，再量同一套特征）
    python tools/measure_ui.py verify shot.png

    # 3) 原图 + 预览图 → 偏移量 / 宽高比（#14 缺的那一步）
    python tools/measure_ui.py compare program/g2.jpg shot.png --asset 1896x288

量什么：沿 x 取中位数压掉文字，得到「行亮度曲线」→ 找周期峰（行距）与第一个峰（起点）；
在峰与峰之间沿 y 取中位数，得到「列亮度曲线」→ 50% 交叉点定左右边（槽位宽）。
宽高比 = 宽 / 行距，必须等于素材宽高比（差 >1% 就是哪里错了）。

对外（自测会 import）：
    load_lum / row_profile / col_profile / find_peaks / pitch_of / cross
    detect(path, asset=None)   → dict
    compare(a, b, asset=None)  → dict
    main()
"""
import argparse
import os
import sys

from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

STAGE_W, STAGE_H = 800, 450
TARGET_ASPECT = 16.0 / 9.0


# ------------------------------------------------------------------ 图像 / 剖面

def load_lum(path):
    """打开并转灰度；返回 (Image, w, h)"""
    im = Image.open(path).convert("L")
    return im, im.width, im.height


def _median_256(vals):
    """256 桶直方图求中位数（纯 Python，够快；不装 numpy）"""
    n = len(vals)
    if not n:
        return 0
    hist = [0] * 256
    for v in vals:
        hist[v] += 1
    half = n // 2
    acc = 0
    for i, c in enumerate(hist):
        acc += c
        if acc > half:
            return i
    return 255


def row_profile(im, x0=None, x1=None):
    """每一行的中位数（压掉文字）"""
    w, h = im.size
    x0 = 0 if x0 is None else max(0, int(x0))
    x1 = w if x1 is None else min(w, int(x1))
    if x1 - x0 < 2:
        x1 = w
    crop = im.crop((x0, 0, x1, h))
    data = crop.tobytes()                 # 灰度图：1 字节 1 像素，切片最快
    stride = x1 - x0
    return [_median_256(data[y * stride:(y + 1) * stride]) for y in range(h)]


def col_profile(im, y0, y1, x0=0, x1=None):
    """每一列的中位数（压掉行内文字），y0~y1 限定在一条槽位里"""
    w, h = im.size
    x1 = w if x1 is None else min(w, int(x1))
    y0 = max(0, int(y0))
    y1 = min(h, int(y1))
    if y1 - y0 < 2:
        y1 = min(h, y0 + 2)
    crop = im.crop((max(0, int(x0)), y0, x1, y1))
    cw = crop.width
    data = crop.tobytes()
    return [_median_256(data[x::cw]) for x in range(cw)]


def find_peaks(prof, y0, y1, min_v):
    """局部极大值；min_v 是「够亮」的门槛（默认自适应：窗口内 min + 0.6×(max-min)）"""
    y0 = max(1, int(y0))
    y1 = min(len(prof) - 1, int(y1))
    if y1 <= y0:
        return []
    out = []
    for i in range(y0, y1):
        if prof[i] >= min_v and prof[i] >= prof[i - 1] and prof[i] > prof[i + 1]:
            # 相邻两个都过线时只留最高的那个
            if out and i - out[-1] <= 2:
                if prof[i] > prof[out[-1]]:
                    out[-1] = i
                continue
            out.append(i)
    return out


def smooth(p, k=3):
    """轻度平滑（文字边缘会让剖面出现一串小尖峰，先抹平再找峰）"""
    if k <= 1 or not p:
        return list(p)
    half = k // 2
    n = len(p)
    out = []
    for i in range(n):
        a = max(0, i - half)
        b = min(n, i + half + 1)
        seg = p[a:b]
        out.append(sum(seg) / float(len(seg)))
    return out


def prominent(prof, peaks, lo, hi, frac=0.3, win=40):
    """只留「比左右两边明显高」的峰（文字/装饰的浅峰会被这条筛掉）"""
    span = (hi - lo) or 1
    out = []
    n = len(prof)
    for i in peaks:
        a = max(0, i - win)
        b = min(n, i + win + 1)
        left = prof[a:i + 1] or [prof[i]]
        right = prof[i:b] or [prof[i]]
        prom = prof[i] - max(min(left), min(right))
        if prom >= frac * span:
            out.append(i)
    return out


def pitch_of(peaks):
    if len(peaks) < 2:
        return 0.0
    diffs = [peaks[i + 1] - peaks[i] for i in range(len(peaks) - 1)]
    diffs.sort()
    mid = len(diffs) // 2
    return float(diffs[mid]) if len(diffs) % 2 else (diffs[mid - 1] + diffs[mid]) / 2.0


def mode_pitch(peaks, tol=2):
    """相邻差值的**众数**（文档 Step 1 的做法）：返回 (周期, 出现次数)"""
    if len(peaks) < 2:
        return (0.0, 0)
    diffs = [peaks[i + 1] - peaks[i] for i in range(len(peaks) - 1)]
    clusters = []
    for d in sorted(diffs):
        for c in clusters:
            if abs(c["avg"] - d) <= tol:
                c["n"] += 1
                c["sum"] += d
                c["avg"] = c["sum"] / c["n"]
                break
        else:
            clusters.append({"avg": float(d), "n": 1, "sum": d})
    best = max(clusters, key=lambda c: (c["n"], c["avg"]))
    return (best["avg"], best["n"])


def periodic_chain(peaks, pitch, tol=3):
    """只留能排成「行距 = pitch」等差数列的那一串（压掉文字边缘之类的假峰）"""
    if len(peaks) < 3 or not pitch:
        return peaks
    best = []
    for i in range(len(peaks)):
        chain = [peaks[i]]
        for j in range(i + 1, len(peaks)):
            if abs((peaks[j] - chain[-1]) - pitch) <= tol:
                chain.append(peaks[j])
        if len(chain) > len(best):
            best = chain
    return best if len(best) >= 3 else peaks


def cross(p, i0, i1, rising):
    """50% 交叉点（最大值与最小值的中间），精度 ~0.1px；找不到返回 None"""
    i0 = max(0, int(i0))
    i1 = min(len(p) - 1, int(i1))
    if i1 <= i0:
        return None
    seg = p[i0:i1 + 1]
    mid = (max(seg) + min(seg)) / 2.0
    for k in range(len(seg) - 1):
        a, b = seg[k], seg[k + 1]
        if (rising and a < mid <= b) or ((not rising) and a > mid >= b):
            if b == a:
                return i0 + k
            return i0 + k + (mid - a) / (b - a)
    return None


# ------------------------------------------------------------------ 测量

def stage_scale(w):
    """图上 px → 舞台 px"""
    return STAGE_W / float(w or STAGE_W)


def detect(path, asset=None, out=print):
    """量一张图：行距 / 峰位 / 槽位宽 / 宽高比。`asset` 形如 (宽, 高)。"""
    im, w, h = load_lum(path)
    aspect = w / float(h or 1)
    info = {"path": path, "w": w, "h": h, "aspect": aspect,
            "scale": stage_scale(w), "warnings": []}
    if abs(aspect - TARGET_ASPECT) > 0.02 * TARGET_ASPECT:
        info["warnings"].append("不是 16:9（%.3f），换算可能不准；整帧原图才是可靠的" % aspect)

    # 行剖面：x 取中间一段（避开两侧装饰）
    x0 = int(w * 0.073)
    x1 = int(w * 0.458)
    prof = row_profile(im, x0, x1)
    y0 = int(h * 0.10)
    y1 = int(h * 0.90)
    win = prof[y0:y1] or prof
    lo, hi = min(win), max(win)
    min_v = lo + 0.6 * (hi - lo)
    peaks = find_peaks(smooth(prof, 3), y0, y1, min_v)
    peaks = prominent(prof, peaks, lo, hi)
    # 峰太多（噪声）时只留亮的那几个
    if len(peaks) > 12:
        peaks = sorted(peaks, key=lambda i: -prof[i])[:12]
        peaks.sort()
    # 文档 Step 1：先看「相邻差值的众数」，确认这是行距而不是别的周期；
    # 再只留能排成等差数列的那一串（文字边缘、装饰线会被筛掉）
    mp, mn = mode_pitch(peaks)
    chain = periodic_chain(peaks, mp, tol=max(2.0, mp * 0.06)) if mp else peaks
    confident = (mn >= 3 and len(chain) >= 3)
    if confident:
        peaks = chain
    pitch = mp if confident else pitch_of(peaks)
    info["confident"] = confident
    info["pitch_hits"] = mn
    if not confident:
        info["warnings"].append(
            "没找到稳定的行距（相邻差值重复 %d 次）：这张图可能不是整帧原图，"
            "或不是这个界面；下面的数字只能当参考" % mn)
    s = info["scale"]
    info.update({
        "peaks": peaks,
        "pitch_px": pitch,
        "pitch_stage": pitch * s,
        "first_stage": (peaks[0] * s) if peaks else None,
        "peaks_stage": [round(p * s, 2) for p in peaks],
        "threshold": min_v,
    })

    # 槽位宽：取第一个峰到第二个峰之间那一条，沿 y 取中位数
    width_stage = None
    width_px = None
    if len(peaks) >= 2:
        band0 = int(peaks[0] + (peaks[1] - peaks[0]) * 0.15)
        band1 = int(peaks[0] + (peaks[1] - peaks[0]) * 0.85)
        cp = col_profile(im, band0, band1)
        left = cross(cp, 0, len(cp) - 1, rising=True)       # 暗→亮：左边缘
        right = cross(cp, 0, len(cp) - 1, rising=False)     # 亮→暗：右边缘
        if left is not None and right is not None and abs(right - left) > 4:
            width_px = abs(right - left)
            width_stage = width_px * s
    info["width_stage"] = width_stage
    # 宽高比用**同一坐标系**的两个量算（px / px，或 舞台px / 舞台px），别一个 px 一个舞台
    if width_px and pitch:
        info["ratio"] = width_px / pitch
    else:
        info["ratio"] = None
    if asset:
        aw, ah = asset
        if ah:
            info["asset_ratio"] = aw / float(ah)
            if info["ratio"]:
                info["ratio_error"] = abs(info["ratio"] - info["asset_ratio"]) / info["asset_ratio"]
    return info


def _print_info(info, out=print, title="测量"):
    out("%s：%s（%d×%d，缩放 %.4f）" % (title, os.path.basename(info["path"]),
                                   info["w"], info["h"], info["scale"]))
    for wmsg in info["warnings"]:
        out("  ! " + wmsg)
    out("  行（竖直） 周期 %.1f 图上px → %.2f 舞台px" %
        (info["pitch_px"], info["pitch_stage"]))
    out("  峰位 %s" % (info["peaks_stage"] or "（没找到）"))
    if info["first_stage"] is not None:
        out("  第一个峰 %.2f 舞台px" % info["first_stage"])
    if info["width_stage"]:
        out("  槽位宽 %.2f 舞台px" % info["width_stage"])
    if info["ratio"]:
        line = "  宽高比 %.3f" % info["ratio"]
        if info.get("asset_ratio"):
            line += "（素材 %.3f，差 %.2f%%）" % (info["asset_ratio"], info["ratio_error"] * 100)
            if info["ratio_error"] > 0.01:
                line += "  ← 超 1%%：元素被拉伸了"
        out(line)


def verify(path, out=print):
    """渲染截图：裁掉黑边 → 缩到 800×450 → 用同一套检测器量"""
    im, w, h = load_lum(path)
    mask = im.point(lambda v: 255 if v > 8 else 0)
    box = mask.getbbox()
    if box:
        im = im.crop(box)
    if im.size != (STAGE_W, STAGE_H):
        im = im.resize((STAGE_W, STAGE_H), Image.LANCZOS)
    tmp = path + ".stage.png"
    im.save(tmp)
    try:
        info = detect(tmp)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    info["path"] = path
    info["cropped"] = box
    _print_info(info, out, "渲染")
    return info


def compare(a, b, asset=None, out=print):
    """原图 + 预览图 → 偏移量 / 宽高比（两张都先换算到舞台坐标系）"""
    ia = detect(a, asset=asset)
    ib = detect(b, asset=asset)
    _print_info(ia, out, "原图")
    out("")
    _print_info(ib, out, "预览")
    out("")

    res = {"a": ia, "b": ib, "ok": True, "problems": []}
    if ia["first_stage"] is None or ib["first_stage"] is None:
        res["ok"] = False
        res["problems"].append("至少一张没找到行峰，没法比")
        out("× " + res["problems"][-1])
        return res
    if not ia.get("confident") or not ib.get("confident"):
        res["ok"] = False
        res["problems"].append("至少一张没找到稳定的行距（不是整帧原图？），偏移量不可信")
        out("× " + res["problems"][-1])
        return res

    n = min(len(ia["peaks_stage"]), len(ib["peaks_stage"]))
    deltas = [round(ib["peaks_stage"][i] - ia["peaks_stage"][i], 2) for i in range(n)]
    deltas.sort()
    offset = deltas[len(deltas) // 2]
    res["offset_px"] = offset
    res["deltas"] = deltas

    pitch_ratio = (ib["pitch_stage"] / ia["pitch_stage"]) if ia["pitch_stage"] else None
    res["pitch_ratio"] = pitch_ratio
    if pitch_ratio and abs(pitch_ratio - 1) > 0.01:
        res["problems"].append("行距差 %.1f%%（缩放假定错了，或元素被拉伸）"
                               % ((pitch_ratio - 1) * 100))

    if ia["width_stage"] and ib["width_stage"]:
        ratio = ib["width_stage"] / ia["width_stage"]
        res["width_ratio"] = ratio
        if abs(ratio - 1) > 0.01:
            res["problems"].append("槽位宽差 %.1f%%" % ((ratio - 1) * 100))
    else:
        res["width_ratio"] = None

    if ia["ratio"] and ib["ratio"]:
        res["ratio_a"], res["ratio_b"] = ia["ratio"], ib["ratio"]
        res["ratio_diff"] = abs(ib["ratio"] - ia["ratio"]) / ia["ratio"]
        if res["ratio_diff"] > 0.01:
            res["problems"].append("宽高比差 %.1f%%（元素被压扁/拉长）" % (res["ratio_diff"] * 100))

    out("偏移 %+.2f 舞台px（逐峰 %s）" % (offset, "/".join("%+.1f" % d for d in deltas[:5])))
    if pitch_ratio:
        out("周期比 %.4f" % pitch_ratio)
    if res["width_ratio"]:
        out("宽比 %.4f" % res["width_ratio"])
    if res.get("ratio_diff") is not None:
        out("宽高比 %.3f → %.3f（差 %.2f%%）" %
            (res["ratio_a"], res["ratio_b"], res["ratio_diff"] * 100))
    if res["problems"]:
        out("× " + "；".join(res["problems"]))
    else:
        out("√ 只有平移没有形变（偏移 %+.2f px）" % offset)
    res["ok"] = not res["problems"]
    return res


# ------------------------------------------------------------------ CLI

def _asset(s):
    if not s:
        return None
    for sep in ("x", "X", "*"):
        if sep in s:
            a, b = s.split(sep, 1)
            return (int(a), int(b))
    raise argparse.ArgumentTypeError("素材尺寸写成 1896x288")


def main():
    ap = argparse.ArgumentParser(description="界面像素测量（#14）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("profile", help="量原版整帧截图")
    p1.add_argument("image")
    p1.add_argument("--asset", type=_asset, help="素材尺寸，如 1896x288（给了就检查宽高比）")
    p2 = sub.add_parser("verify", help="量渲染截图（自动裁黑边 + 缩到 800×450）")
    p2.add_argument("image")
    p2.add_argument("--asset", type=_asset)
    p3 = sub.add_parser("compare", help="原图 + 预览图 → 偏移量 / 宽高比")
    p3.add_argument("a")
    p3.add_argument("b")
    p3.add_argument("--asset", type=_asset)
    a = ap.parse_args()

    if a.cmd == "profile":
        _print_info(detect(a.image, asset=a.asset), title="原图")
        return 0
    if a.cmd == "verify":
        verify(a.image)
        return 0
    res = compare(a.a, a.b, asset=a.asset)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
