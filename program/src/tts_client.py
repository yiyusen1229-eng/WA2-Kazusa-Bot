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
import urllib.parse
import urllib.request

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


def load_refs():
    """扫描参考音频目录：<emotion>/*.wav + 同名 .txt（prompt_text）

    返回 {emotion: [(wav_path, prompt_text), ...]}
    顶层散放的 wav 归入 neutral。
    """
    global _ref_cache
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
    return out


def pick_ref(emo="neutral"):
    """按情绪随机挑一条参考音频，拿不到就回落 neutral"""
    emo = EMOTION_ALIAS.get(emo, emo)
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
    import random
    return random.choice(items)


def available():
    """依赖是否齐全"""
    return all(os.path.exists(p) for p in (API_PY, PY, GPT_W, SOVITS_W, REF_WAV))


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
    load_refs()
    """拉起 API 服务并切到我们的权重（幂等）"""
    global _proc, _ready, _last_err, _starting
    # 已有线程在启动中: 不阻塞请求, 直接报告当前状态
    if _starting and not _ready:
        return False
    if _ready:
        return True
    with _lock:
        if _ready:
            return True
        _starting = True
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
            _starting = False
            return False

        try:
            _post("/set_gpt_weights?weights_path=" + urllib.parse.quote(GPT_W))
            _post("/set_sovits_weights?weights_path=" + urllib.parse.quote(SOVITS_W))
        except Exception as e:
            _last_err = "加载权重失败: %s" % e
            return False

        _ready = True
        _starting = False
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


def synthesize(text, lang="zh", timeout=60, emo="neutral"):
    """返回 wav 字节；失败返回 None"""
    if not _ready:
        return None
    # 按情绪随机挑参考音频；参数也跟着情绪走
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
        return _post("/tts?" + q, timeout=timeout)
    except Exception as e:
        global _last_err
        _last_err = "合成失败: %s" % e
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
