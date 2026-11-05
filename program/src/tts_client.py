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
import audio_gain
import cache_io
import diag

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
# 等 GPT-SoVITS 起来的超时（第一次要加载模型，给足）；单句合成超时
READY_TIMEOUT_S = 120
SYNTH_TIMEOUT_S = 60
T_PY = os.path.join(os.path.dirname(GSV), "翻译服务.py")
_tproc = None
URL = "http://%s:%d" % (HOST, PORT)

# 本地 TTS 权重（由使用者自行准备并放入对应目录）
GPT_W = os.path.join(GSV, "GPT_weights_v4", "Touma_Kazusa-e15.ckpt")
SOVITS_W = os.path.join(GSV, "SoVITS_weights_v4", "Touma_Kazusa_e8_s33072_l32.pth")

_model_key = ""      # 合并版：当前已加载的角色语音配置签名


def _char_json(name):
    """读当前角色文件夹里的可选配置文件；没有/坏了都返回 {}。"""
    try:
        import characters
        p = os.path.join(characters.active_dir(), name)
        if os.path.isfile(p):
            import json
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            return d if isinstance(d, dict) else {}
    except Exception:
        pass
    return {}


def _character_tts():
    """角色的 tts.json：{gpt, sovits}；相对路径按 GPT-SoVITS 根目录解析"""
    d = _char_json("tts.json")
    g = (d.get("gpt") or "").strip()
    s = (d.get("sovits") or "").strip()
    if not g or not s:
        return {}
    if not os.path.isabs(g):
        g = os.path.join(GSV, g)
    if not os.path.isabs(s):
        s = os.path.join(GSV, s)
    return {"gpt": g, "sovits": s}

# 参考音频：按情绪准备（语气由参考决定，音色由模型决定）
# 现在放在当前角色文件夹的 voice/<情绪>/ 下；老版本的 refs_touma 只当兜底
LEGACY_REFS_DIR = os.path.join(os.path.dirname(GSV), "refs_touma")
_REFS_OVERRIDE = ""      # 自测用：把参考音频目录指到临时位置

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
    "毒舌":     {"speed_factor": 1.02, "temperature": 0.55, "top_k": 4,  "top_p": 0.88},
    "撒娇":     {"speed_factor": 0.94, "temperature": 0.70, "top_k": 6,  "top_p": 0.92},
    "哭腔":     {"speed_factor": 0.90, "temperature": 0.55, "top_k": 4,  "top_p": 0.88},
    "调侃吐槽": {"speed_factor": 1.05, "temperature": 0.72, "top_k": 7,  "top_p": 0.93},
    "问句":     {"speed_factor": 1.00, "temperature": 0.60, "top_k": 5,  "top_p": 0.90},
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

def refs_dir():
    """参考音频根目录：当前角色 voice/ 里有情绪子目录就用它，否则回落到自带的 refs_touma。

    「查看文件」也打开这里，所以两边是同一个地方。自测可以用 `_REFS_OVERRIDE` 指到临时目录。
    """
    if _REFS_OVERRIDE:
        return _REFS_OVERRIDE
    try:
        d = char_res.voice_dir()
    except Exception:
        d = ""
    if d and os.path.isdir(d):
        try:
            if any(os.path.isdir(os.path.join(d, n)) for n in os.listdir(d)):
                return d
        except OSError:
            pass
    return LEGACY_REFS_DIR


def _has_refs():
    """参考音频根目录里有没有 wav（递归，情绪子目录也算）"""
    for _dp, _dn, files in os.walk(refs_dir()):
        for f in files:
            if f.lower().endswith(".wav"):
                return True
    return False


_ref_cache = {}
# 特别模式导入的参考音频（角色 voice/ 顶层的散装 wav）：优先于按情绪分组的
_IMPORTED = {"global": [], "by_emo": {}}
_refs_sig = ""


def _char_voice_sig():
    """参考音频目录的 mtime 签名：导入/删除了文件、或者换了角色，缓存都跟着失效"""
    sig = []
    for d in (refs_dir(), char_res.voice_dir()):
        try:
            sig.append(os.path.getmtime(d) if d and os.path.isdir(d) else 0)
        except Exception:
            sig.append(0)
    try:
        import characters
        cid = characters.active_id()
    except Exception:
        cid = ""
    return "%s|%.0f/%.0f" % (cid, sig[0], sig[1])


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
    root = refs_dir()
    try:
        if not os.path.isdir(root):
            return out
        for name in os.listdir(root):
            p = os.path.join(root, name)
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
                tpath = os.path.join(root, base + ".txt")
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
    """依赖是否齐全：权重 / 运行时 / 参考音频（角色 voice/ 里按情绪分组的那些）。"""
    if not all(os.path.exists(p) for p in (API_PY, PY, GPT_W, SOVITS_W)):
        return False
    if _has_refs():
        return True
    try:
        return bool(char_res.voice_refs())
    except Exception:
        return False


def _post(path, timeout=30):
    with urllib.request.urlopen(URL + path, timeout=timeout) as r:
        return r.read()


def _ensure_char_model():
    """合并版：切到当前角色 tts.json 里的 GPT/SoVITS 权重（同一进程，不重启）"""
    global _model_key, _last_err
    m = _character_tts()
    if not m:
        return True
    key = m["gpt"] + "|" + m["sovits"]
    if key == _model_key:
        return True
    try:
        _post("/set_gpt_weights?weights_path=" + urllib.parse.quote(m["gpt"]))
        _post("/set_sovits_weights?weights_path=" + urllib.parse.quote(m["sovits"]))
        _model_key = key
        return True
    except Exception as e:
        _last_err = "切换角色权重失败: %s" % e
        return False


def _wait_ready(timeout=READY_TIMEOUT_S):
    import socket
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with socket.create_connection((HOST, PORT), timeout=2):
                return True
        except Exception:
            time.sleep(1.0)
    return False


def _child_env():
    """给 GPT-SoVITS 子进程准备环境：runtime/ 里的 ffmpeg 进 PATH，TMP 指到 tts/tmp。"""
    env = os.environ.copy()
    rt = os.path.dirname(PY)
    if os.path.isdir(rt):
        env["PATH"] = rt + os.pathsep + env.get("PATH", "")
    tmp = os.path.join(os.path.dirname(GSV), "tmp")
    try:
        os.makedirs(tmp, exist_ok=True)
        env["TMP"] = tmp
        env["TEMP"] = tmp
    except Exception:
        pass
    return env


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
            env=_child_env(),
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
            [PY, T_PY], cwd=GSV, env=_child_env(),
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
    # 每次现算参考音频目录的签名（两次 stat，很便宜）：刚导入完的那一句也能立刻换新，
    # 不会先命中导入前的旧缓存
    key = "%s|%s|%s|%s" % (text, lang, emo, _char_voice_sig())
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


def _gain_path(wav_path):
    """增益侧车：wav 旁边一个 .gain.json，wav 本身永远不改。"""
    return wav_path + ".gain.json"


def _record_gain(wav_path, data):
    """量一次响度，把「到 -16 LUFS 要几个 dB」记在侧车 json 里。

    同一段音频（字节数没变、目标没变）就沿用旧记录，不重复量。
    量不出来（格式不认识 / 静音 / 出错）就返回 None，不影响播放。
    """
    if not wav_path or not data:
        return None
    side = _gain_path(wav_path)
    try:
        old = cache_io.read_json(side, None)
    except Exception:
        old = None
    if (isinstance(old, dict) and old.get("target") == audio_gain.TARGET_LUFS
            and old.get("bytes") == len(data)):
        return old
    try:
        info = dict(audio_gain.probe(data))
    except Exception as e:
        applog.log("响度测量失败：%s" % e, "WARN")
        return None
    info["bytes"] = len(data)
    info["at"] = int(time.time())
    try:
        diag.note("tts", lufs=info.get("lufs"), peak_db=info.get("peak_db"),
                  gain_db=info.get("gain_db"), target=info.get("target"),
                  secs=round(len(data) / 2.0 / max(1, info.get("rate") or 32000), 2))
    except Exception:
        pass
    try:
        os.makedirs(os.path.dirname(side), exist_ok=True)
        with open(side, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False)
    except Exception:
        pass
    try:
        applog.log("TTS 响度：%.1f LUFS / 峰值 %.1f dBFS → 增益 %+.1f dB"
                   % (info.get("lufs") or -99.0, info.get("peak_db") or -99.0,
                      info.get("gain_db") or 0.0), "TTS")
    except Exception:
        pass
    return info


def gain_of_cache(wav_path):
    """读侧车（没有就 None）；给自测 / 调试用。"""
    try:
        d = cache_io.read_json(_gain_path(wav_path), None)
        return d if isinstance(d, dict) else None
    except Exception:
        return None



# 角色名的中文写法 → 日文读音。数据放当前角色文件夹的 pronunciation.json，
# 代码里不写死具体角色；没有这个文件就原样送 TTS。
_NAME_CACHE = {"path": "", "mtime": 0, "pairs": []}


def _name_pairs():
    try:
        import characters
        p = os.path.join(characters.active_dir(), "pronunciation.json")
        if not os.path.isfile(p):
            return []
        mt = os.path.getmtime(p)
        if _NAME_CACHE["path"] == p and _NAME_CACHE["mtime"] == mt:
            return _NAME_CACHE["pairs"]
        import json
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        pairs = []
        if isinstance(d, dict):
            pairs = [(str(k), str(v)) for k, v in d.items()]
        elif isinstance(d, list):
            for it in d:
                if isinstance(it, (list, tuple)) and len(it) >= 2:
                    pairs.append((str(it[0]), str(it[1])))
                elif isinstance(it, dict) and it.get("from") and it.get("to"):
                    pairs.append((str(it["from"]), str(it["to"])))
        pairs.sort(key=lambda x: -len(x[0]))
        _NAME_CACHE.update({"path": p, "mtime": mt, "pairs": pairs})
        return pairs
    except Exception:
        return []


def normalize_ja_names(text):
    """按角色 pronunciation.json 把名字换成假名；界面文字不变。"""
    if not text:
        return text
    for a, b in _name_pairs():
        if a in text:
            text = text.replace(a, b)
    return text


def synthesize(text, lang="zh", timeout=SYNTH_TIMEOUT_S, emo="neutral"):
    """返回 wav 字节；失败返回 None

    合成串行：GPT-SoVITS 的 api 同时来两个请求会抢模型，这里排队；
    排队时先看缓存，同一句重复播不会重复合成。
    """
    global _last_err, _ready
    if not _ready:
        return None
    if lang == "ja":
        text = normalize_ja_names(text)
    try:
        _cp = _tts_cache_path(text, lang, emo)
    except Exception:
        _cp = None
    with _synth_lock:
        if not _ensure_char_model():
            return None
        if _cp:
            try:
                if os.path.exists(_cp):
                    with open(_cp, 'rb') as _f:
                        _cached = _f.read()
                    if _cached:
                        diag.count("tts.hit")
                        _record_gain(_cp, _cached)      # 侧车缺了就补一份，下次直接读
                        return _cached
            except Exception:
                pass
        # 按情绪挑参考音频；参数也跟着情绪走（一条都没有就别合成，交给上层回报）
        ref_path, ref_text = pick_ref(emo)
        if not ref_path:
            return None
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
                    diag.count("tts.render")
                    os.makedirs(os.path.dirname(_cp), exist_ok=True)
                    with open(_cp, 'wb') as _f:
                        _f.write(_data)
                    _record_gain(_cp, _data)            # 增益记在侧车，wav 不动
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
