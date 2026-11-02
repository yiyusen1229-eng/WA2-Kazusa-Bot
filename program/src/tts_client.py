# -*- coding: utf-8 -*-
"""语音合成客户端

程序启动时拉起 GPT-SoVITS 的 API 服务（用它的独立 python 运行时），
之后每次合成走本地 HTTP 请求。

若 GPT-SoVITS 目录或模型不存在，则整体降级为"无语音"，不影响聊天。
"""
import atexit
import io
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import char_res

BASE = os.path.dirname(os.path.abspath(__file__))
def _find_gsv():
    cands = [
        os.path.join(os.path.dirname(BASE), "tts", "GPT-SoVITS"),
        os.path.join(os.path.dirname(os.path.dirname(BASE)), "tts", "GPT-SoVITS"),
        # 整理后的位置：<项目根>/other/dev/tts/GPT-SoVITS
        os.path.join(os.path.dirname(os.path.dirname(BASE)), "other", "dev", "tts", "GPT-SoVITS"),
        os.path.join(os.path.dirname(os.path.dirname(BASE)), "dev", "tts", "GPT-SoVITS"),
    ]
    for c in cands:
        if os.path.exists(os.path.join(c, "api_v2.py")):
            return c
    return cands[0]


GSV = _find_gsv()
DATA = os.path.join(os.path.dirname(GSV), "..", "语音训练集")
API_PY = os.path.join(GSV, "api_v2.py")
PY = os.path.join(GSV, "runtime", "python.exe")

HOST = "127.0.0.1"
PORT = 9880
T_PORT = 9881
T_PY = os.path.join(os.path.dirname(GSV), "翻译服务.py")
_tproc = None
URL = "http://%s:%d" % (HOST, PORT)

# 本地 TTS 权重（由使用者自行准备并放入对应目录））
GPT_W = os.path.join(GSV, "GPT_weights_v4", "Touma_Kazusa-e15.ckpt")
SOVITS_W = os.path.join(GSV, "SoVITS_weights_v4", "Touma_Kazusa_e8_s33072_l32.pth")
_WAV_DIR = os.path.join(os.path.dirname(GSV), "..", "语音训练集", "wav")
_TOUMA_REF = os.path.join(os.path.dirname(GSV), "refs_touma", "1005_0427_01.wav")
_TOUMA_TXT = "その程度のニュアンスの違い、成績優秀な委員長様なら正しく理解できるんじゃない?"

# 按情绪准备参考音频: 语气由参考决定, 音色由模型决定
# 该模型自带配套参考音频，所有情绪统一用它，保证音色一致
REFS = {
    "neutral": (_TOUMA_REF, _TOUMA_TXT),
    "angry":   (_TOUMA_REF, _TOUMA_TXT),
    "sad":     (_TOUMA_REF, _TOUMA_TXT),
    "warm":    (_TOUMA_REF, _TOUMA_TXT),
}
REF_WAV = REFS["neutral"][0]
REF_TEXT = REFS["neutral"][1]

_proc = None
_ready = False
_lock = threading.Lock()
_synth_lock = threading.Lock()      # 合成串行：GPT-SoVITS 的 api 不是并发安全的
_last_err = ""
_starting = False


# ===== 情绪 → TTS 参数（你筛完音频后可以在这里微调）=====
EMOTION_PARAMS = {
    "neutral": {"speed_factor": 1.00, "temperature": 0.62, "top_k": 5,  "top_p": 0.90},
    "calm":    {"speed_factor": 0.98, "temperature": 0.55, "top_k": 4,  "top_p": 0.88},
    "soft":    {"speed_factor": 0.92, "temperature": 0.50, "top_k": 3,  "top_p": 0.85},
    "cold":    {"speed_factor": 1.02, "temperature": 0.35, "top_k": 2,  "top_p": 0.80},
    "angry":   {"speed_factor": 1.14, "temperature": 0.75, "top_k": 8,  "top_p": 0.95},
    "shy":     {"speed_factor": 0.90, "temperature": 0.70, "top_k": 6,  "top_p": 0.92},
    "surprised": {"speed_factor": 1.12, "temperature": 0.80, "top_k": 9, "top_p": 0.95},
}

# 别名：前端按关键字判断出来的是 sad / warm，映射到新情绪
EMOTION_ALIAS = {
    "sad": "soft", "warm": "soft", "smile": "soft",
    "happy": "soft", "default": "neutral", "": "neutral",
}

# 情绪分组：条数少的合并到主情绪（只影响读取，不移动文件）
REF_GROUPS = {
    "calm":  ["calm"],
    "soft":  ["soft", "轻快"],
    "毒舌":  ["毒舌", "回嘴", "争执"],
    "撒娇":  ["撒娇"],
    "哭腔":  ["哭腔", "悲伤"],
    "调侃吐槽": ["调侃吐槽"],
    "问句":  ["问句"],
}

# 别名：模型可能输出的近义词 → 上面的主情绪
EMOTION_ALIAS = {
    "neutral": "calm", "平静": "calm", "冷静": "calm", "cold": "calm",
    "温柔": "soft", "轻快": "soft", "happy": "soft", "warm": "soft", "开心": "soft",
    "angry": "毒舌", "生气": "毒舌", "冷淡": "毒舌", "冷嘲": "毒舌",
    "shy": "撒娇", "害羞": "撒娇", "害羞撒娇": "撒娇",
    "悲伤": "哭腔", "委屈": "哭腔", "哽咽": "哭腔", "sad": "哭腔",
    "吐槽": "调侃吐槽", "调侃": "调侃吐槽",
    "疑问": "问句", "疑惑": "问句",
}

_REFS_DIR = os.path.join(os.path.dirname(GSV), "refs_touma")
_ref_cache = {}
# 特别模式导入的参考音频（char/voice）：优先于 refs_touma
_IMPORTED = {"global": [], "by_emo": {}}
_refs_sig = ""


def _char_voice_sig():
    """参考音频目录的 mtime 签名：导入/删除了文件就换签名，缓存跟着失效"""
    sig = []
    for d in (_REFS_DIR, char_res.voice_dir()):
        try:
            sig.append(os.path.getmtime(d) if d and os.path.isdir(d) else 0)
        except Exception:
            sig.append(0)
    return "%.0f/%.0f" % (sig[0], sig[1])


def _emo_from_filename(path):
    """文件名里带情绪就用它（angry_01.wav / 毒舌.wav / soft-2.wav）"""
    stem = os.path.splitext(os.path.basename(path))[0].lower()
    for emo, keys in REF_GROUPS.items():
        for k in keys:
            if k and k.lower() in stem:
                return emo
    for alias, emo in EMOTION_ALIAS.items():
        if alias and alias.lower() in stem:
            return emo
    return ""


def _load_imported():
    """扫 char/voice/*.wav → {global:[...], by_emo:{情绪:[...]}}"""
    out = {"global": [], "by_emo": {}}
    try:
        for wav, txt in char_res.voice_refs():
            emo = _emo_from_filename(wav)
            if emo:
                out["by_emo"].setdefault(emo, []).append((wav, txt))
            else:
                out["global"].append((wav, txt))
    except Exception:
        pass
    return out


def load_refs():
    """扫描参考音频目录：<emotion>/*.wav + 同名 .txt（prompt_text）

    返回 {emotion: [(wav_path, prompt_text), ...]}
    顶层散放的 wav 归入 neutral。
    另外把特别模式导入的 char/voice/*.wav 读进 _IMPORTED（合成时优先用）。
    """
    global _ref_cache, _IMPORTED, _refs_sig
    out = {}
    try:
        if not os.path.isdir(_REFS_DIR):
            return out
        for name in os.listdir(_REFS_DIR):
            p = os.path.join(_REFS_DIR, name)
            if os.path.isdir(p):
                emo = name.lower()
                items = []
                for f in os.listdir(p):
                    if f.lower().endswith(".wav"):
                        base = os.path.splitext(f)[0]
                        tpath = os.path.join(p, base + ".txt")
                        txt = ""
                        if os.path.exists(tpath):
                            try:
                                txt = io.open(tpath, encoding="utf-8").read().strip()
                            except Exception:
                                txt = ""
                        items.append((os.path.join(p, f), txt))
                if items:
                    out[emo] = items
            elif name.lower().endswith(".wav"):
                base = os.path.splitext(name)[0]
                tpath = os.path.join(_REFS_DIR, base + ".txt")
                txt = ""
                if os.path.exists(tpath):
                    try:
                        txt = io.open(tpath, encoding="utf-8").read().strip()
                    except Exception:
                        txt = ""
                out.setdefault("neutral", []).append((p, txt))
    except Exception as e:
        log_err = str(e)
    _ref_cache = out
    _IMPORTED = _load_imported()
    _refs_sig = _char_voice_sig()
    return out


def pick_ref(emo="neutral"):
    """按情绪挑参考音频：特别模式导入的优先，其次 refs_touma 的分组，最后兜底"""
    import random
    emo = EMOTION_ALIAS.get(emo, emo)
    if _char_voice_sig() != _refs_sig:      # 导入 / 删除过参考音频 → 重新扫
        load_refs()
    if _IMPORTED["by_emo"].get(emo):        # 文件名带情绪的，只在对应情绪里用
        return random.choice(_IMPORTED["by_emo"][emo])
    if _IMPORTED["global"]:                 # 没带情绪的就是通用参考，优先于自带素材
        return random.choice(_IMPORTED["global"])
    refs = _ref_cache or load_refs()
    names = REF_GROUPS.get(emo, [emo])
    items = []
    for n in names:
        items.extend(refs.get(n, []))
    if not items:                     # 兜底：任意一条
        for v in refs.values():
            items.extend(v)
    if not items:
        return None, ""
    return random.choice(items)


def available():
    """依赖是否齐全。

    参考音频这里放宽：特别模式导入过 char/voice 的，就不再要求自带
    的 refs_touma 那条必须在（否则导入自己的参考音频反而起不来）。
    """
    if not all(os.path.exists(p) for p in (API_PY, PY, GPT_W, SOVITS_W)):
        return False
    if os.path.exists(REF_WAV):
        return True
    try:
        return bool(char_res.voice_refs())
    except Exception:
        return False


def _post(path, timeout=30):
    with urllib.request.urlopen(URL + path, timeout=timeout) as r:
        return r.read()


def _wait_ready(timeout=120):
    import socket
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with socket.create_connection((HOST, PORT), timeout=2):
                return True
        except Exception:
            time.sleep(1.0)
    return False


def start():
    """拉起 API 服务并切到我们的权重（幂等）。

    `_starting` 只在真正启动过程中是 True，任何失败路径都在 finally 里复位 ——
    否则一次「依赖缺失」就会让之后所有请求直接返回 False，再也拉不起来。
    """
    global _starting
    load_refs()
    # 已有线程在启动中: 不阻塞请求, 直接报告当前状态
    if _starting and not _ready:
        return False
    if _ready:
        return True
    with _lock:
        if _ready:
            return True
        _starting = True
        try:
            return _start_locked()
        finally:
            _starting = False


def _start_locked():
    """真正启动（调用方已持有 _lock）"""
    global _proc, _ready, _last_err
    if not available():
        _last_err = "语音依赖缺失"
        return False
    import socket
    in_use = False
    try:
        with socket.create_connection((HOST, PORT), timeout=1):
            in_use = True
    except Exception:
        pass
    if in_use:
        # 已有服务在跑: 直接复用（可能是上次残留）
        try:
            _post("/set_gpt_weights?weights_path=" + urllib.parse.quote(GPT_W))
            _post("/set_sovits_weights?weights_path=" + urllib.parse.quote(SOVITS_W))
            _ready = True
            return True
        except Exception:
            pass   # 复用失败就走重新启动
    try:
        cfg = os.path.join(GSV, "GPT_SoVITS", "configs", "tts_infer.yaml")
        _proc = subprocess.Popen(
            [PY, API_PY, "-a", HOST, "-p", str(PORT), "-c", cfg],
            cwd=GSV,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000 if os.name == "nt" else 0,
        )
    except Exception as e:
        _last_err = "启动失败: %s" % e
        return False

    if not _wait_ready():
        _last_err = "服务未就绪"
        return False

    try:
        _post("/set_gpt_weights?weights_path=" + urllib.parse.quote(GPT_W))
        _post("/set_sovits_weights?weights_path=" + urllib.parse.quote(SOVITS_W))
    except Exception as e:
        _last_err = "加载权重失败: %s" % e
        return False

    _ready = True
    return True


def start_translate():
    """拉起翻译服务（Hy-MT2 + llama.cpp）"""
    global _tproc
    if _tproc is not None:
        return True
    if not os.path.exists(T_PY):
        return False
    import socket
    try:
        with socket.create_connection(("127.0.0.1", T_PORT), timeout=1):
            return True
    except Exception:
        pass
    try:
        _tproc = subprocess.Popen(
            [PY, T_PY], cwd=GSV,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=0x08000000 if os.name == "nt" else 0)
    except Exception:
        return False
    for _ in range(60):
        try:
            with socket.create_connection(("127.0.0.1", T_PORT), timeout=1):
                return True
        except Exception:
            time.sleep(0.5)
    return False


def translate_via_service(text, to="ja", timeout=30):
    """调用翻译服务; 失败返回空串"""
    try:
        q = urllib.parse.urlencode({"t": text, "to": to})
        with urllib.request.urlopen("http://127.0.0.1:%d/translate?%s" % (T_PORT, q),
                                    timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8"))
        return (d.get("text") or "").strip() if d.get("ok") else ""
    except Exception:
        return ""


_TTS_CACHE_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                "..", "cache", "tts"))


def _tts_cache_path(text, lang, emo):
    """文本+语种+情绪+参考音频版本 唯一决定一段音频。

    参考音频版本算进 key：导入了新参考音频，旧的缓存就不再命中（否则换了音色
    还是播昨天那段）。
    """
    import hashlib
    key = "%s|%s|%s|%s" % (text, lang, emo, _refs_sig or _char_voice_sig())
    h = hashlib.md5(key.encode("utf-8")).hexdigest()[:20]
    return os.path.join(_TTS_CACHE_DIR, h + ".wav")


def clear_tts_cache():
    """启动时清空语音缓存（与字模缓存同策略：本次运行有效，退出即弃）"""
    try:
        import shutil
        if os.path.isdir(_TTS_CACHE_DIR):
            shutil.rmtree(_TTS_CACHE_DIR, ignore_errors=True)
    except Exception:
        pass


def synthesize(text, lang="zh", timeout=60, emo="neutral"):
    """返回 wav 字节；失败返回 None

    合成串行：GPT-SoVITS 的 api 同时来两个请求会抢模型，这里排队；
    排队时先看缓存，同一句重复播不会重复合成。
    """
    global _last_err, _ready
    if not _ready:
        return None
    try:
        _cp = _tts_cache_path(text, lang, emo)
    except Exception:
        _cp = None
    with _synth_lock:
        if _cp:
            try:
                if os.path.exists(_cp):
                    with open(_cp, 'rb') as _f:
                        return _f.read()
            except Exception:
                pass
        # 按情绪挑参考音频；参数也跟着情绪走
        ref_path, ref_text = pick_ref(emo)
        if not ref_path:
            try:
                rw, rt = REFS.get(emo, REFS["neutral"])
                ref_path = os.path.join(_WAV_DIR, rw)
                ref_text = rt
            except Exception:
                ref_path, ref_text = "", ""
        prm = EMOTION_PARAMS.get(EMOTION_ALIAS.get(emo, emo)) or EMOTION_PARAMS["neutral"]
        q = urllib.parse.urlencode({
            "text": text,
            "text_lang": lang,
            "ref_audio_path": ref_path,
            "prompt_text": ref_text,
            "prompt_lang": "ja",
            "top_k": prm["top_k"],
            "top_p": prm["top_p"],
            "temperature": prm["temperature"],
            "text_split_method": "cut5",
            "batch_size": 1,
            "speed_factor": prm["speed_factor"],
        })
        try:
            # 第一次合成要加载模型，给足时间
            _data = _post("/tts?" + q, timeout=timeout)
            try:
                if _data and _cp:
                    os.makedirs(os.path.dirname(_cp), exist_ok=True)
                    with open(_cp, 'wb') as _f:
                        _f.write(_data)
            except Exception:
                pass
            return _data
        except Exception as e:
            _last_err = "合成失败: %s" % e
            # 连不上 / 超时 = 服务像是挂了：标记未就绪，下次请求会重新拉起。
            # （HTTP 4xx/5xx 说明服务还活着，只是这句没合成出来，不重拉）
            if isinstance(e, urllib.error.HTTPError):
                pass
            elif isinstance(e, (urllib.error.URLError, OSError)):
                _ready = False
            return None


def stop():
    global _proc, _ready
    if _proc is not None:
        try:
            _proc.terminate()
        except Exception:
            pass
        _proc = None
    _ready = False


atexit.register(stop)


def status():
    return {"available": available(), "ready": _ready, "error": _last_err}
