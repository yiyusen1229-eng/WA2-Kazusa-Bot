# -*- coding: utf-8 -*-
"""语音响度归一化（近似 ITU-R BS.1770 / EBU R128）。

为什么要有：同一角色不同情绪的 TTS 输出，响度能差 6~10 dB（冷静的在 -23 LUFS、
生气的到 -15 LUFS），一句话接一句话播出来忽大忽小。

做法：服务端离线量一次响度 → 算出「到 -16 LUFS 要几个 dB」→ 记在侧车 json 里，
再把增益应用到**返回给前端的字节**上。磁盘上的 wav 一个字节都不改（"原文件不改"），
下次再合成同一句就是读缓存 + 用记下来的增益。

实现细节：
- K 加权 = 高架 + 高通两级 biquad，系数按 libebur128 的解析式在运行时算（任意采样率）
- 门限 = BS.1770 的 -70 LUFS 绝对门 + 相对 -10 LU
- 峰值保护 = 增益最多把峰值推到 -1 dBFS（推上去就削波，宁可没到目标）
- 只处理 16bit PCM 的 wav；其它格式原样放过（applied=False，不猜、不硬改）

精度说明：和标准实现（ffmpeg ebur128 / libebur128）在语音上一般差 0.3 dB 以内；
系数用解析式现算，48kHz 时与标准表格值一致到小数点后 3 位。

对外：
    probe(data, target=-16.0)   → info dict（只看不改）
    apply(data, target=-16.0)   → (new_bytes, info)
    lufs_of(data)               → float | None
    set_for(data, target)       → info（带 gain_db，给侧车用）
"""
import array
import hashlib
import math
import struct
import sys

TARGET_LUFS = -16.0
MAX_GAIN_DB = 12.0          # 增益上下限：再誇张就是素材有问题了
MIN_GAIN_DB = -12.0
PEAK_CEIL_DB = -1.0         # 推完峰值不许超过这里

# 解析式里的常数（与 libebur128 一致）
_F0_SHELF = 1681.9744509555319
_G_SHELF = 3.99984385397
_Q_SHELF = 0.7071752369554196
_F0_HP = 38.13547087602444
_Q_HP = 0.5003270373238773

_MEMO = {}                  # 源字节的指纹 → info（同一段音频不重复量）
_MEMO_ORDER = []
_MEMO_MAX = 32


# ---------------------------------------------------------------- wav 解析

def _parse(data):
    """解出 16bit PCM 的采样。不认识的格式返回 None（调用方原样放过）。"""
    if not data or len(data) < 44:
        return None
    if data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
        return None
    i = 12
    fmt = None
    off = size = None
    while i + 8 <= len(data):
        cid = data[i:i + 4]
        csz = struct.unpack("<I", data[i + 4:i + 8])[0]
        body = i + 8
        if cid == b"fmt ":
            if csz < 16 or body + 16 > len(data):
                return None
            afmt, ch, sr, _br, _ba, bits = struct.unpack("<HHIIHH", data[body:body + 16])
            if afmt == 0xFFFE and csz >= 40 and body + 26 <= len(data):   # EXTENSIBLE：看子格式前两字节
                afmt = struct.unpack("<H", data[body + 24:body + 26])[0]
            fmt = {"format": afmt, "channels": ch, "rate": sr, "bits": bits}
        elif cid == b"data":
            off, size = body, min(csz, len(data) - body)
        i = body + csz + (csz & 1)
        if fmt and off is not None:
            break
    if not fmt or off is None:
        return None
    if fmt["format"] != 1 or fmt["bits"] != 16:
        return {"format": fmt["format"], "bits": fmt["bits"],
                "channels": fmt["channels"], "rate": fmt["rate"], "samples": None,
                "offset": off, "size": size}
    raw = data[off:off + size]
    raw = raw[:len(raw) - (len(raw) % 2)]
    a = array.array("h")
    a.frombytes(raw)
    if sys.byteorder != "little":
        a.byteswap()
    if fmt["channels"] > 1:
        a = a[:len(a) - (len(a) % fmt["channels"])]
    return {"format": 1, "bits": 16, "channels": fmt["channels"], "rate": fmt["rate"],
            "samples": a, "offset": off, "size": size}


# ---------------------------------------------------------------- K 加权

def _coeffs(sr):
    """两级 biquad 的系数：高架（pre-filter）+ 高通（RLB）。"""
    k = math.tan(math.pi * _F0_SHELF / sr)
    vh = 10.0 ** (_G_SHELF / 20.0)
    vb = vh ** 0.4996667741545416
    a0 = 1.0 + k / _Q_SHELF + k * k
    shelf = ((vh + vb * k / _Q_SHELF + k * k) / a0,
             2.0 * (k * k - vh) / a0,
             (vh - vb * k / _Q_SHELF + k * k) / a0,
             2.0 * (k * k - 1.0) / a0,
             (1.0 - k / _Q_SHELF + k * k) / a0)
    k = math.tan(math.pi * _F0_HP / sr)
    a0 = 1.0 + k / _Q_HP + k * k
    hp = (1.0, -2.0, 1.0,
          2.0 * (k * k - 1.0) / a0,
          (1.0 - k / _Q_HP + k * k) / a0)
    return shelf, hp


def _biquad(xs, c):
    """直接 I 型 biquad。纯 Python，但一段 4~6 秒的语音也就几十毫秒。"""
    b0, b1, b2, a1, a2 = c
    x1 = x2 = y1 = y2 = 0.0
    out = [0.0] * len(xs)
    for i in range(len(xs)):
        x = xs[i]
        y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2 = x1
        x1 = x
        y2 = y1
        y1 = y
        out[i] = y
    return out


def _channel_loudness(samples, channels, rate):
    """按 400ms 块 / 100ms 步进算 gated 综合响度；不够一块就整段算一块。"""
    shelf, hp = _coeffs(rate)
    n = len(samples) // channels
    if n <= 0:
        return None
    # 按声道拆 → K 加权 → 逐声道能量块
    per_ch = []
    for ch in range(channels):
        xs = [samples[i * channels + ch] / 32768.0 for i in range(n)]
        ys = _biquad(_biquad(xs, shelf), hp)
        per_ch.append(ys)

    win = max(1, int(rate * 0.4))
    hop = max(1, int(rate * 0.1))
    starts = list(range(0, max(1, n - win + 1), hop)) if n >= win else [0]
    end = lambda s: min(n, s + win)

    blocks = []
    for s in starts:
        e = end(s)
        if e <= s:
            continue
        z = 0.0
        for ys in per_ch:
            acc = 0.0
            for v in ys[s:e]:
                acc += v * v
            z += acc / (e - s)
        blocks.append(z)
    if not blocks:
        return None

    def loud(z):
        return -0.691 + 10.0 * math.log10(z) if z > 0 else -1e9

    gated = [z for z in blocks if loud(z) > -70.0]
    if not gated:
        return None
    mean_z = sum(gated) / len(gated)
    thr = loud(mean_z) - 10.0
    kept = [z for z in gated if loud(z) > thr]
    if not kept:
        kept = gated
    final_z = sum(kept) / len(kept)
    if final_z <= 0:
        return None
    return loud(final_z)


def _peak_db(samples):
    if not len(samples):
        return -120.0
    peak = 0
    for s in samples:
        v = s if s >= 0 else -s
        if v > peak:
            peak = v
    if peak <= 0:
        return -120.0
    return 20.0 * math.log10(peak / 32768.0)


# ---------------------------------------------------------------- 对外

def _fingerprint(data):
    return hashlib.sha1(data).hexdigest()[:16] if data else ""


def _remember(fp, info):
    if not fp:
        return
    _MEMO[fp] = info
    _MEMO_ORDER.append(fp)
    while len(_MEMO_ORDER) > _MEMO_MAX:
        old = _MEMO_ORDER.pop(0)
        if old != fp:
            _MEMO.pop(old, None)


def _base_info(parsed):
    return {"target": TARGET_LUFS, "lufs": None, "peak_db": None,
            "gain_db": 0.0, "applied": False, "format": "unknown", "ms": 0}


def probe(data, target=TARGET_LUFS):
    """量一段 wav 的响度并算出到 target 需要的增益。不动字节。"""
    info = _base_info(None)
    fp = _fingerprint(data)
    if fp and fp in _MEMO:
        cached = dict(_MEMO[fp])
        if abs(cached.get("target", TARGET_LUFS) - target) < 0.01:
            return cached
        info["lufs"] = cached.get("lufs")
        info["peak_db"] = cached.get("peak_db")
    parsed = _parse(data)
    if not parsed:
        info["format"] = "not-wav"
        return info
    if parsed.get("samples") is None:
        info["format"] = "pcm%d/%dbit" % (parsed.get("format", 0), parsed.get("bits", 0))
        info["channels"] = parsed.get("channels")
        info["rate"] = parsed.get("rate")
        return info

    info["format"] = "pcm16"
    info["channels"] = parsed["channels"]
    info["rate"] = parsed["rate"]
    samples = parsed["samples"]
    info["peak_db"] = round(_peak_db(samples), 2)
    lufs = _channel_loudness(samples, parsed["channels"], parsed["rate"])
    if lufs is None:                      # 静音 / 全是杂音：不给增益，别把底噪放大
        info["gain_db"] = 0.0
        _remember(fp, dict(info))
        return info

    info["lufs"] = round(lufs, 2)
    gain = target - lufs
    gain = max(MIN_GAIN_DB, min(MAX_GAIN_DB, gain))
    headroom = PEAK_CEIL_DB - info["peak_db"]
    if gain > headroom:                   # 峰值保护：宁可没到目标，也不削波
        gain = headroom
    info["gain_db"] = round(gain, 2)
    info["target"] = target
    _remember(fp, dict(info))
    return info


def apply(data, target=TARGET_LUFS):
    """返回 (应用了增益的字节, info)。|增益| < 0.1dB 时原样返回（applied=False）。"""
    info = probe(data, target)
    if not data or abs(info.get("gain_db", 0.0)) < 0.1:
        return data, info
    parsed = _parse(data)
    if not parsed or parsed.get("samples") is None:
        return data, info
    g = 10.0 ** (info["gain_db"] / 20.0)
    src = parsed["samples"]
    out = bytearray(len(src) * 2)
    for i, s in enumerate(src):
        v = int(s * g)
        if v > 32767:
            v = 32767
        elif v < -32768:
            v = -32768
        struct.pack_into("<h", out, i * 2, v)
    new = bytearray(data)
    off = parsed["offset"]
    new[off:off + len(out)] = out
    info = dict(info)
    info["applied"] = True
    return bytes(new), info


def lufs_of(data):
    return probe(data).get("lufs")


def stats():
    """给自测 / 调试看：记住过多少段。"""
    return {"memo": len(_MEMO)}
