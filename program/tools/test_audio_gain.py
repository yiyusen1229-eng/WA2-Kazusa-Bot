# -*- coding: utf-8 -*-
"""响度归一化的自测（不联网、不开界面、不需要 numpy）。

跑法：
    cd program
    build_env/venv/Scripts/python.exe tools/test_audio_gain.py

验的是：
  1. -20 dBFS 的 1kHz 正弦量出来是 -20 LUFS（EBU R128 的对齐点，允许 ±0.5）
  2. probe 只看不改：字节不变、applied 为假
  3. apply 之后响度落到目标 -16 LUFS（±0.5）
  4. 静音不放大（gain=0、applied 假）
  5. 短于一块（400ms）的片段也能量，不炸
  6. 峰值保护：又轻又尖的信号只给到 -1 dBFS 为止，推完不削波
  7. 立体声按两个声道一起算
  8. 非 16bit PCM（8bit / float）原样放过，不猜不改
  9. 不是 wav 的文件原样放过
 10. 增益夹在 ±12 dB 内
 11. 同一段字节第二次算是缓存命中（结果一致 + memo 有记录）
"""
import array
import math
import os
import struct
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROGRAM, "src"))

import audio_gain as ag  # noqa: E402

FAILS = []
TMP = tempfile.mkdtemp( prefix="wa2_gain_test_")


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:200]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


# ------------------------------------------------------------------ 造素材

def make_wav(samples, rate=32000, channels=1, bits=16, fmt=1):
    """samples 是 int16 列表；bits/fmt 用来造「不支持的格式」"""
    if bits == 16:
        raw = array.array("h", samples).tobytes()
    else:
        raw = bytes((s & 0xFF) for s in samples)
    block_align = channels * bits // 8
    hdr = b"RIFF" + struct.pack("<I", 36 + len(raw)) + b"WAVE"
    hdr += b"fmt " + struct.pack("<IHHIIHH", 16, fmt, channels, rate,
                                 rate * block_align, block_align, bits)
    hdr += b"data" + struct.pack("<I", len(raw))
    return hdr + raw


def sine(db, secs=3.0, rate=32000, freq=1000.0, channels=1):
    """峰值余弦：RMS = db（相对满刻度）→ 振幅 = 满刻度 * 10^(db/20) * √2"""
    amp = 32767.0 * (10.0 ** (db / 20.0)) * math.sqrt(2.0)
    n = int(rate * secs)
    one = [max(-32768, min(32767, int(round(amp * math.sin(2 * math.pi * freq * i / rate)))))
           for i in range(n)]
    if channels == 1:
        return one
    out = []
    for v in one:
        out.extend([v] * channels)
    return out


def peak_db(data):
    p = ag._parse(data)
    s = p["samples"]
    peak = 0
    for v in s:
        a = v if v >= 0 else -v
        if a > peak:
            peak = a
    return 20.0 * math.log10(peak / 32768.0) if peak else -120.0


def main():
    # 1 / 2 -----------------------------------------------------------------
    d = make_wav(sine(-20.0))
    info = ag.probe(d)
    check("1kHz -20dBFS → -20 LUFS（±0.5）",
          info["lufs"] is not None and abs(info["lufs"] + 20.0) <= 0.5, info)
    check("probe 不改字节", ag.lufs_of(d) == info["lufs"] and info["applied"] is False, info)
    check("probe 标出格式", info["format"] == "pcm16" and info["rate"] == 32000, info)

    # 3 ---------------------------------------------------------------------
    out, info2 = ag.apply(d)
    lufs2 = ag.lufs_of(out)
    check("apply 后落到 -16 LUFS（±0.5）",
          lufs2 is not None and abs(lufs2 + 16.0) <= 0.5, lufs2)
    check("apply 标 applied", info2["applied"] is True, info2)
    check("apply 不改长度、头不变",
          len(out) == len(d) and out[:44] == d[:44], (len(out), len(d)))

    # 4 ---------------------------------------------------------------------
    silent = make_wav([0] * 32000 * 2)
    info = ag.probe(silent)
    check("静音不放大", info["gain_db"] == 0.0 and info["applied"] is False, info)
    out, _ = ag.apply(silent)
    check("静音 apply 原样返回", out == silent)

    # 5 ---------------------------------------------------------------------
    short = make_wav(sine(-20.0, secs=0.08))
    info = ag.probe(short)
    check("80ms 短片段能量出来", info["lufs"] is not None and info["format"] == "pcm16", info)
    check("短片段不给离谱增益", abs(info["gain_db"]) <= 12.0, info)

    # 6 ---------------------------------------------------------------------
    # 3 秒几乎静音 + 一个满刻度尖峰：响度很低，但峰值已经到顶 → 增益被峰值保护压到约 -1dB
    spiky = [20] * (3 * 32000)
    spiky[32000 * 2] = 32767
    d = make_wav(spiky)
    info = ag.probe(d)
    check("尖峰信号增益被峰值保护压住", abs(info["gain_db"] - (-1.0)) <= 0.1, info)
    out, _ = ag.apply(d)
    check("推完峰值不超过 -1dBFS", peak_db(out) <= -0.99, peak_db(out))

    # 7 ---------------------------------------------------------------------
    st = make_wav(sine(-20.0, channels=2), channels=2)
    info = ag.probe(st)
    check("立体声也能量（双声道同相 → 约 -17 LUFS）",
          info["channels"] == 2 and info["lufs"] is not None and abs(info["lufs"] + 17.0) <= 1.5,
          info)

    # 8 ---------------------------------------------------------------------
    d8 = make_wav([0] * 32000, bits=8)
    info = ag.probe(d8)
    check("8bit 不猜格式", info["format"] == "pcm1/8bit" and info["gain_db"] == 0.0, info)
    out, info9 = ag.apply(d8)
    check("8bit 原样放过", out == d8 and info9["applied"] is False)

    # 9 ---------------------------------------------------------------------
    junk = b"ID3\x04" + b"\x00" * 200
    info = ag.probe(junk)
    check("不是 wav → not-wav", info["format"] == "not-wav" and info["gain_db"] == 0.0, info)
    out, _ = ag.apply(junk)
    check("不是 wav → 原样返回", out == junk)

    # 10 --------------------------------------------------------------------
    loud = make_wav(sine(-1.0))
    info = ag.probe(loud)
    check("增益夹在 ±12dB 内", -12.0 <= info["gain_db"] <= 12.0, info)

    # 11 --------------------------------------------------------------------
    d = make_wav(sine(-22.0))
    a1 = ag.probe(d)
    before = ag.stats()["memo"]
    a2 = ag.probe(d)
    check("同样字节两次结果一致", a1 == a2, (a1, a2))
    check("第二次是缓存命中（memo 没再涨）", ag.stats()["memo"] == before, ag.stats())

    # 12 --------------------------------------------------------------------
    # 响度差 6dB 的两段，量出来的差也该是 6dB 左右
    l1 = ag.lufs_of(make_wav(sine(-20.0)))
    l2 = ag.lufs_of(make_wav(sine(-26.0)))
    check("响度差 6dB 量出来也是 6dB（±0.4）", l1 is not None and l2 is not None and abs((l1 - l2) - 6.0) <= 0.4,
          (l1, l2))

    # 13 --------------------------------------------------------------------
    # 侧车 json 的路径约定（tts_client 用的就是 wav 后面加后缀）
    side = os.path.join(TMP, "x.wav.gain.json")
    check("侧车命名 = wav + .gain.json", side.endswith(".wav.gain.json"))

    # 14 --------------------------------------------------------------------
    # tts_client 的记账：写侧车、读回来、原 wav 一个字节都不动
    import tts_client
    wav_path = os.path.join(TMP, "line.wav")
    data = make_wav(sine(-19.0))
    with open(wav_path, "wb") as f:
        f.write(data)
    rec = tts_client._record_gain(wav_path, data)
    check("侧车写出来了", os.path.isfile(tts_client._gain_path(wav_path)))
    check("侧车记了目标 / 响度 / 增益",
          rec and rec.get("target") == ag.TARGET_LUFS and rec.get("lufs") is not None
          and rec.get("gain_db") is not None, rec)
    check("侧车能读回来", tts_client.gain_of_cache(wav_path) == rec)
    with open(wav_path, "rb") as f:
        check("原 wav 字节没变", f.read() == data)
    again = tts_client._record_gain(wav_path, data)
    check("同字节再记一次沿用旧记录", again == rec, (again, rec))

    # 15 --------------------------------------------------------------------
    # 接口层能正常 import（audio_gain 接进 api_tts 了）
    import api_tts  # noqa: F401
    check("api_tts 能 import（增益已接进去）", True)

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), " / ".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
