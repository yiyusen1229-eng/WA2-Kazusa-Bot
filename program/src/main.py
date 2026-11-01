# -*- coding: utf-8 -*-
"""
AI 聊天界面架构 —— 可插拔的桌面聊天 UI 框架
内嵌本地 HTTP 服务 + WebView2 原生窗口
"""
import os
import sys
import applog
import tts_client
import json
import time
import threading
import subprocess
try:
    import story_rag as STORY
except Exception:
    STORY = None
try:
    import gdi_text as GLIB
except Exception:
    GLIB = None
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

BUILD_TAG = time.strftime("%H%M%S")
APP_NAME = "AI 聊天界面架构"
WINDOW_TITLE = "%s  [%s]" % (APP_NAME, BUILD_TAG)
OLLAMA = "http://127.0.0.1:11434"
# 安全模式: 存在 模型开关.txt(或环境变量 WA2_NO_MODELS=1) 时不加载任何模型
def _no_models_flag():
    if os.environ.get("WA2_NO_MODELS") == "1":
        return True
    roots = [os.path.dirname(os.path.abspath(__file__))]
    if getattr(sys, "frozen", False):
        roots.insert(0, os.path.dirname(os.path.abspath(sys.executable)))
    for r in roots:
        for name in ("模型开关.txt", "no_models.flag"):
            if os.path.exists(os.path.join(r, name)):
                return True
    return False


NO_MODELS = _no_models_flag()

DEFAULT_MODEL = "kazusa14b-v7"
FALLBACK_MODEL = "kazusa14b-v6"


def res_dir():
    """资源目录: 打包后为 _MEIPASS, 开发时为脚本目录"""
    if getattr(sys, "_MEIPASS", None):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


BASE = res_dir()
UI_DIR = os.path.join(BASE, "ui2")
# 界面素材目录：开发时直接用 program/res/assets（run_dev.py 用环境变量指过来），
# 免得每次都把 200MB 素材复制进 ui2；打包版没有这个变量，就用 ui2/assets。
ASSETS_DIR = os.environ.get("WA2_ASSETS_DIR") or os.path.join(UI_DIR, "assets")
PERSONA_FILE = os.path.join(BASE, "persona.txt")
PERSONA_CORE_FILE = os.path.join(BASE, "persona_core.txt")
# 用户可改的文件放 exe 同目录（打包后 BASE 是临时解包目录，不能放这里）
EXE_DIR = (os.path.dirname(os.path.abspath(sys.executable))
           if getattr(sys, "frozen", False) else BASE)
CLOUD_CFG_FILE = os.path.join(EXE_DIR, "config.json")
FEWSHOT_FILE = os.path.join(EXE_DIR, "fewshot.json")
# 界面设置（音量 / 确认开关 / 右键功能 / 文字速度 / 对话框透明度…）
# 放 exe 同目录：清理缓存、private_mode 清 localStorage 都不影响它
PREFS_FILE = os.path.join(EXE_DIR, "prefs.json")


# 窗口模式的窗口大小（DIP/CSS 像素）。退出全屏后回到这个尺寸：
# 这台机器 250% 缩放下 1280x720 已经占满屏幕 83%，全屏和"窗口"肉眼一样大，
# 所以窗口模式固定用更小的一档（也是程序的 min_size）。
WINDOWED_SIZE = (1024, 576)


def _screen_size():
    """物理像素的屏幕尺寸（含任务栏区域）"""
    try:
        import ctypes
        u = ctypes.WinDLL("user32")
        return int(u.GetSystemMetrics(0)), int(u.GetSystemMetrics(1))
    except Exception:
        return 0, 0


def _dpi_scale():
    try:
        import ctypes
        return ctypes.WinDLL("user32").GetDpiForSystem() / 96.0
    except Exception:
        return 1.0


def prefs_load():
    """读界面设置；文件坏了就当没有（不抛异常，否则整个界面起不来）"""
    try:
        with open(PREFS_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def prefs_save(d):
    """整体覆写界面设置（先写临时文件再原子替换，避免写一半留下坏 JSON）"""
    if not isinstance(d, dict):
        return False
    try:
        tmp = PREFS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, PREFS_FILE)
        return True
    except Exception as e:
        try:
            applog.log("保存界面设置失败: %s" % e)
        except Exception:
            pass
        return False


def ensure_cloud_cfg():
    """首次启动没有 config.json 就生成一份空白模板（不含任何密钥）"""
    try:
        if os.path.exists(CLOUD_CFG_FILE):
            return
        blank = {
            "provider": "",
            "base_url": "",
            "api_key": "",
            "model": "",
            "models": {
                "chat":  {"endpoint": "", "key": "", "model": "", "connected": False},
                "voice": {"endpoint": "", "key": "", "model": "", "connected": False},
                "mt":    {"endpoint": "", "key": "", "model": "", "connected": False},
            },
        }
        with open(CLOUD_CFG_FILE, "w", encoding="utf-8") as f:
            json.dump(blank, f, ensure_ascii=False, indent=1)
        log("generated blank config: %s" % CLOUD_CFG_FILE)
    except Exception as e:
        try:
            log("ensure_cloud_cfg failed: %s" % e)
        except Exception:
            pass

def cloud_cfg():
    try:
        d = json.load(open(CLOUD_CFG_FILE, encoding="utf-8"))
        if d.get("api_key") and d.get("model"):
            return d
    except Exception:
        pass
    return {}

def _http_ok(url, headers=None, timeout=4):
    """访问一下，能拿到 HTTP 响应就算通"""
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return 200 <= r.status < 400 or r.status in (401, 403)
    except urllib.error.HTTPError as e:
        # 有响应（比如 404/401）说明服务是活的
        return e.code in (400, 401, 403, 404, 405, 422)
    except Exception:
        return False


def probe_endpoint(sec, endpoint, key, model):
    """按板块类型探测端点是否可用，返回 (ok, latency_ms, models)"""
    ep = (endpoint or "").rstrip("/")
    if not ep:
        return False, 0, []
    t0 = time.time()
    ok, models = False, []

    if sec == "chat":
        hdr = {"Authorization": "Bearer " + key} if key else {}
        for path in ("/models", "/v1/models"):
            try:
                with urllib.request.urlopen(
                        urllib.request.Request(ep + path, headers=hdr),
                        timeout=4) as r:
                    d = json.loads(r.read().decode("utf-8"))
                    models = [m.get("id") for m in d.get("data", []) if m.get("id")]
                    ok = True
                    break
            except Exception:
                continue

    elif sec == "voice":
        hdr = {}
        if key:
            hdr["Authorization"] = "Bearer " + key
            hdr["xi-api-key"] = key
        for path in ("/docs", "/", "/openapi.json", "/v1/models", "/health"):
            if _http_ok(ep + path, hdr):
                ok = True
                break

    else:  # mt
        for path in ("/api/tags", "/v1/models", "/api/version"):
            if _http_ok(ep + path):
                ok = True
                break
        if ok:
            try:
                with urllib.request.urlopen(ep + "/api/tags", timeout=4) as r:
                    d = json.loads(r.read().decode("utf-8"))
                    models = [m.get("name") for m in d.get("models", []) if m.get("name")]
            except Exception:
                pass

    return ok, int((time.time() - t0) * 1000), models


def ensure_cloud_cfg():
    """首次启动若没有 config.json，生成一份空白模板（不含任何密钥）"""
    try:
        if os.path.exists(CLOUD_CFG_FILE):
            return
        blank = {
            "provider": "",
            "base_url": "",
            "api_key": "",
            "model": "",
            "models": {
                "chat":  {"endpoint": "", "key": "", "model": "", "connected": False},
                "voice": {"endpoint": "", "key": "", "model": "", "connected": False},
                "mt":    {"endpoint": "", "key": "", "model": "", "connected": False},
            },
        }
        with open(CLOUD_CFG_FILE, "w", encoding="utf-8") as f:
            json.dump(blank, f, ensure_ascii=False, indent=1)
        log("generated blank config: %s" % CLOUD_CFG_FILE)
    except Exception as e:
        try:
            log("ensure_cloud_cfg failed: %s" % e)
        except Exception:
            pass
def apply_model_cfg():
    """把保存过的配置应用到运行时（聊天扁平字段 / 语音地址）"""
    try:
        cfg = model_cfg_all()
    except Exception:
        return
    voice = cfg.get("voice") or {}
    ep = (voice.get("endpoint") or "").strip()
    if ep:
        try:
            tts_client.URL = ep.rstrip("/")
        except Exception:
            pass








MODEL_SECTIONS = ("chat", "voice", "mt")
TTS_ENDPOINT_HINT = "http://127.0.0.1:9880"


def model_cfg_all():
    """三个板块的配置；没有存过就按当前实际在用的值给默认"""
    try:
        d = json.load(open(CLOUD_CFG_FILE, encoding="utf-8"))
    except Exception:
        d = {}
    m = d.get("models") or {}

    def pick(sec, ep, key, model):
        got = m.get(sec) or {}
        return {
            "endpoint": got.get("endpoint") or ep,
            "key": got.get("key") or key,
            "model": got.get("model") or model,
            "connected": bool(got.get("connected")),
        }

    chat_ep = d.get("base_url") or OLLAMA
    chat_key = d.get("api_key") or ""
    chat_model = d.get("model") or DEFAULT_MODEL
    return {
        "chat": pick("chat", chat_ep, chat_key, chat_model),
        "voice": pick("voice", TTS_ENDPOINT_HINT, "", "GPT-SoVITS"),
        "mt": pick("mt", OLLAMA, "", TRANSLATE_MODEL),
    }


def model_cfg_save(sec, endpoint, key, model, connected):
    try:
        d = json.load(open(CLOUD_CFG_FILE, encoding="utf-8"))
    except Exception:
        d = {}
    m = d.get("models") or {}
    m[sec] = {"endpoint": endpoint, "key": key,
              "model": model, "connected": bool(connected)}
    d["models"] = m
    # 聊天板块同时写扁平字段，_chat() 立刻用新值
    if sec == "chat":
        d["base_url"] = endpoint
        d["api_key"] = key
        d["model"] = model
    try:
        with open(CLOUD_CFG_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        return True
    except Exception as e:
        log("model cfg save failed: %s" % e)
        return False


def fewshot_msgs():
    try:
        rows = json.load(open(FEWSHOT_FILE, encoding="utf-8"))
    except Exception:
        return []
    out = []
    for r in rows:
        u, a = (r.get("u") or "").strip(), (r.get("a") or "").strip()
        if u and a:
            out.append({"role": "user", "content": u})
            out.append({"role": "assistant", "content": a})
    return out

import re as _re
ACTION_RE = _re.compile(r"<action>\s*(.*?)\s*</action>", _re.S)

def split_scene(text):
    """取出 <scene>地点</scene> 与 <outfit>编号</outfit>，返回 (正文, 场景, 服装)"""
    import re
    scene = ""
    outfit = ""
    if not text:
        return text, scene, outfit
    m = re.search(r"<scene>\s*([^<]{1,24})\s*</scene>", text)
    if m:
        scene = m.group(1).strip()
        text = text[:m.start()] + text[m.end():]
    m = re.search(r"<outfit>\s*([^<]{1,12})\s*</outfit>", text)
    if m:
        outfit = m.group(1).strip()
        text = text[:m.start()] + text[m.end():]
    text = re.sub(r"</?(scene|outfit)[^>]*>", "", text).strip()
    return text, scene, outfit


def split_emotion(text):
    """取出 <emotion>xxx</emotion>，返回 (正文, 情绪)。没有标记时情绪为 calm。"""
    import re
    if not text:
        return text, "calm"
    m = re.search(r"<emotion>\s*([^<]{1,20})\s*</emotion>", text)
    emo = "calm"
    if m:
        emo = m.group(1).strip()
        text = (text[:m.start()] + text[m.end():]).strip()
    # 兼容模型把标记写在其它位置/多次出现
    text = re.sub(r"</?emotion[^>]*>", "", text).strip()
    return text, emo


def split_action(text):
    """把 <action> 从回复里拆出来，返回 (action, 纯台词)"""
    acts = ACTION_RE.findall(text or "")
    rest = ACTION_RE.sub("", text or "").strip()
    return acts, rest

WORLDBOOK_FILE = os.path.join(BASE, "worldbook.json")


# ---------------- 人设 / 世界书 ----------------
import threading as _th
from winutil import _win_hwnd, _user32, _quiet_act
from sessions import session_save, session_load, session_list, session_thumb
import sessions as _sessions
import memory as _memory
import pricing as _pricing


def qs(q, names, default=""):
    """从 parse_qs 结果里取第一个存在的参数名（正式名 + 兼容旧名）"""
    for n in names:
        v = q.get(n)
        if v and v[0] != "":
            return v[0]
    return default
_RENDER_LOCK = _th.Lock()
_TEXT_CACHE = {}


def _clear_text_cache():
    """启动时清空字模磁盘缓存：下次用到再重新生成，避免缓存无限增长"""
    try:
        import shutil
        d = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                          "..", "res", "assets", "ui", "text_cache"))
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
    except Exception:
        pass


def _text_disk_path(key):
    """文字渲染的磁盘缓存路径（同参数只渲染一次，之后直接读文件）"""
    import hashlib
    h = hashlib.md5(repr(key).encode("utf-8")).hexdigest()[:16]
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "res", "assets", "ui", "text_cache")
    d = os.path.normpath(d)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, h + ".png")
_TEXT_CACHE_MAX = 2000


def log(msg):
    """轻量日志: 打包后没有控制台, 写文件方便排查"""
    try:
        import datetime
        p = os.path.join(os.environ.get("TEMP", "."), "wa2_app.log")
        with open(p, "a", encoding="utf-8") as f:
            f.write("[%s] %s\\n" % (datetime.datetime.now().strftime("%H:%M:%S"), msg))
    except Exception:
        pass


def split_thinking(text):
    """把 <thinking>…</thinking> 从回复里拆出来"""
    import re as _re
    m = _re.search(r"<thinking>(.*?)</thinking>", text or "", _re.S)
    if not m:
        return (text or "").strip(), ""
    inner = m.group(1).strip()
    rest = _re.sub(r"<thinking>.*?</thinking>", "", text, flags=_re.S).strip()
    return rest, inner


_JA_CACHE = {}
TRANSLATE_MODEL = 'qwen2.5:14b-instruct-q4_K_M'

_JA_SHOTS = [
    ('别管我。', 'ほっといて。'),
    ('你真是个大笨蛋。', 'お前って本当にバカね。'),
    ('我今天不想说话。', '今日は話したくない。'),
]


def _ja_clean(x):
    """只留第一行, 去掉假名/汉字/日文标点以外的字符, 并截掉解释性尾巴"""
    x = (x or '').split('\\n')[0].strip()
    for stop in ('翻訳', '場合は', '注意', 'つまり', '：', ':', '，', ','):
        i = x.find(stop)
        if i > 0:
            x = x[:i]
    # 句号后还有解释的, 只取第一句
    if '。' in x[:-1]:
        x = x.split('。')[0] + '。'

    out = []
    for c in x:
        o = ord(c)
        if (0x3040 <= o <= 0x30FF) or (0x4E00 <= o <= 0x9FFF) or \
           (0x3000 <= o <= 0x303F) or (0xFF00 <= o <= 0xFF60) or c in '　 ー…':
            out.append(c)
    j = ''.join(out).strip()
    # 人称修正: 和纱用「あたし」, 不用「俺/僕/わたし」
    for bad in ('俺', '僕', 'わたし', '私'):
        j = j.replace(bad, 'あたし')
    return j


def _ja_ok(x):
    return sum(1 for c in x if 0x3040 <= ord(c) <= 0x30FF) >= 2


def translate_ja(text):
    """中译日(用户侧指令 + 和纱模型), 用于日文配音; 失败返回空串"""
    t = (text or '').strip()
    if not t:
        return ''
    if t in _JA_CACHE:
        return _JA_CACHE[t]
    _mt = (model_cfg_all().get("mt") or {})
    mt_ep = (_mt.get("endpoint") or OLLAMA).rstrip("/")
    mt_model = _mt.get("model") or TRANSLATE_MODEL
    # 优先: 专用翻译模型 Hy-MT2（准确、快）
    try:
        tts_client.start_translate()
        ja = tts_client.translate_via_service(t, "ja")
        if ja and _ja_ok(ja):
            if len(_JA_CACHE) < 500:
                _JA_CACHE[t] = ja
            return ja
    except Exception as e:
        log("专用翻译失败: %s" % e)
    # 兜底: 本地模型
    try:
        payload = {
            'model': mt_model,          # 和纱模型, 日文最自然
            'messages': [
                {'role': 'user',
                 'content': '把这句话翻译成日语，只输出日语，不要中文：' + t},
            ],
            'stream': False,
            'max_tokens': 90,
            'reasoning_effort': 'none',
        }
        rq = urllib.request.Request(
            mt_ep + '/v1/chat/completions',
            data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
        )
        with urllib.request.urlopen(rq, timeout=45) as r:
            d = json.loads(r.read().decode('utf-8'))
        raw = d['choices'][0]['message'].get('content') or ''
        raw, _ = split_thinking(raw)
        ja = _ja_clean(raw)
        if _ja_ok(ja):
            if len(_JA_CACHE) < 500:
                _JA_CACHE[t] = ja
            return ja
        log('翻译结果不含日文: %r' % raw[:60])
    except Exception as e:
        log('翻译失败: %s' % e)
    return ''


def persona_text():
    # 优先用训练时一致的精简人设(persona_core), 保证训练/推理分布一致
    for f in (PERSONA_CORE_FILE, PERSONA_FILE):
        try:
            t = open(f, encoding="utf-8").read().strip()
            if t:
                return t
        except Exception:
            continue
    return "你是示例角色，说话简短，只用简体中文。"


def load_worldbook():
    try:
        return json.load(open(WORLDBOOK_FILE, encoding="utf-8"))
    except Exception:
        return {"entries": []}


WB = load_worldbook()

# ---------------- 训练管理 ----------------
TRAIN_DIR = os.environ.get("KAZUSA_TRAIN_DIR",
                           r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\train")
_train_proc = {"p": None}


def train_status():
    """返回完整训练状态(与旧 WebUI 一致)"""
    info = {"ok": True, "dir": TRAIN_DIR, "exists": os.path.isdir(TRAIN_DIR),
            "state": "idle", "step": 0, "total_steps": 0, "progress": 0,
            "loss": None, "lr": None, "eta": None, "speed": None,
            "losses": [], "logs": [], "meta": {}, "gpu_mem": None}
    pf = os.path.join(TRAIN_DIR, "progress.json")
    if os.path.exists(pf):
        try:
            d = json.load(open(pf, encoding="utf-8"))
            for k in ("state", "step", "total_steps", "progress", "loss",
                      "lr", "elapsed", "eta", "speed", "losses", "logs",
                      "meta", "gpu_mem", "updated_at", "preview", "eval_loss"):
                if k in d:
                    info[k] = d[k]
        except Exception as e:
            info["error"] = str(e)
    out = os.path.join(TRAIN_DIR, "output")
    ckpts = []
    if os.path.isdir(out):
        for n in os.listdir(out):
            if n.startswith("checkpoint-"):
                f = os.path.join(out, n, "adapter_model.safetensors")
                if os.path.exists(f):
                    ckpts.append({"name": n,
                                  "mb": round(os.path.getsize(f) / 1048576, 1),
                                  "mtime": time.strftime("%m-%d %H:%M",
                                                         time.localtime(os.path.getmtime(f)))})
    info["can_resume"] = len(ckpts) > 0
    info["last_ckpt"] = max([int(c["name"].split("-")[1]) for c in ckpts] or [0])
    info["checkpoints"] = sorted(ckpts, key=lambda c: int(c["name"].split("-")[1]))
    # 进程可能在应用之外启动, 用进度文件是否新鲜兜底判断
    _alive = bool(_train_proc["p"] and _train_proc["p"].poll() is None)
    try:
        _fresh = (time.time() - os.path.getmtime(pf)) < 180
    except Exception:
        _fresh = False
    info["running"] = bool(_alive or (_fresh and info.get("state") == "running"))

    # 续训位移: 进度文件里的 step 是本次相对计数, 显示时补上检查点基数
    try:
        _base = max([int(c["name"].split("-")[1]) for c in ckpts] or [0])
        _step = int(info.get("step") or 0)
        if _base and _step < _base:
            info["step"] = _step + _base
            if info.get("total_steps"):
                info["total_steps"] = int(info["total_steps"]) + _base
            info["progress"] = round(100.0 * info["step"] / max(1, info.get("total_steps") or 1), 2)
            info["resumed_from"] = _base
    except Exception:
        pass
    # 日志: 进度文件里的 logs + stdout 末尾
    logs = list(info.get("logs") or [])
    lf = os.path.join(TRAIN_DIR, "train.log")
    if os.path.exists(lf):
        try:
            tail = open(lf, encoding="utf-8", errors="ignore").read().splitlines()[-40:]
            logs = logs + [t for t in tail if t.strip()]
        except Exception:
            pass
    info["logs"] = logs[-60:]
    return info


def train_info():
    """模型/数据配置(与旧 WebUI 一致)"""
    def rd(p, default):
        try:
            return json.load(open(p, encoding="utf-8"))
        except Exception:
            return default
    prog = rd(os.path.join(TRAIN_DIR, "progress.json"), {})
    return {"config": rd(os.path.join(TRAIN_DIR, "config.json"), {}),
            "stats": rd(os.path.join(TRAIN_DIR, "data", "stats.json"), {}),
            "meta": prog.get("meta", {})}


def model_probe(url):
    """探测模型服务: 先试 Ollama, 再试 OpenAI 兼容"""
    out = {"ok": False, "type": "", "models": [], "latency_ms": 0}
    u = (url or "").strip().rstrip("/")
    if not u:
        out["error"] = "地址为空"
        return out
    if not (u.startswith("http://") or u.startswith("https://")):
        out["error"] = "只支持 http/https"
        return out
    t0 = time.time()
    try:
        with urllib.request.urlopen(u + "/api/tags", timeout=6) as r:
            d = json.loads(r.read().decode("utf-8", "ignore"))
        names = [m.get("name") or m.get("model") for m in d.get("models", [])]
        out.update(ok=True, type="Ollama", models=[x for x in names if x])
    except Exception as e1:
        try:
            with urllib.request.urlopen(u + "/v1/models", timeout=6) as r:
                d = json.loads(r.read().decode("utf-8", "ignore"))
            names = [m.get("id") for m in d.get("data", [])]
            out.update(ok=True, type="OpenAI", models=[x for x in names if x])
        except Exception as e2:
            out["error"] = str(e1)[:80] + " / " + str(e2)[:80]
    out["latency_ms"] = int((time.time() - t0) * 1000)
    return out

def train_start(extra=None):
    # 已在训练则拒绝重复启动(避免双开爆显存)
    _pf = os.path.join(TRAIN_DIR, "progress.json")
    try:
        _pg = json.load(open(_pf, encoding="utf-8"))
        _fresh = (time.time() - os.path.getmtime(_pf)) < 180
        _alive = bool(_train_proc["p"] and _train_proc["p"].poll() is None)
        if _alive or (_fresh and _pg.get("state") == "running"):
            return {"error": "训练正在进行中", "running": True}
    except Exception:
        pass
    if _train_proc["p"] and _train_proc["p"].poll() is None:
        return {"ok": False, "error": "已经在跑了"}
    py = os.path.join(TRAIN_DIR, "venv", "Scripts", "python.exe")
    if not os.path.exists(py):
        py = sys.executable
    log = open(os.path.join(TRAIN_DIR, "train.log"), "a", encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    # 自动续训: 若存在检查点则从最新一个恢复, 只补剩余轮数
    out = os.path.join(TRAIN_DIR, "output")
    ckpts = []
    if os.path.isdir(out):
        for n in os.listdir(out):
            if n.startswith("checkpoint-") and os.path.exists(
                    os.path.join(out, n, "adapter_model.safetensors")):
                try:
                    ckpts.append((int(n.split("-")[1]), os.path.join(out, n)))
                except Exception:
                    pass
    cfgp = os.path.join(TRAIN_DIR, "config.json")
    try:
        _cfg = json.load(open(cfgp, encoding="utf-8-sig"))
        _total = int(_cfg.get("epochs", 3))
    except Exception:
        _total = 3
    if ckpts and not os.environ.get("KAZUSA_NO_RESUME"):
        ckpts.sort()
        last_step, last_path = ckpts[-1]
        env["KAZUSA_RESUME"] = last_path
        # 已完成轮数(按 849 步/轮估算)
        done = max(0, min(_total - 1, last_step // 849))
        env["KAZUSA_EPOCHS"] = str(max(1, _total - done))
    if extra:
        env.update({k: str(v) for k, v in extra.items()})
    flags = 0x08000000 if os.name == "nt" else 0   # CREATE_NO_WINDOW
    _train_proc["p"] = subprocess.Popen([py, "train_qlora.py"], cwd=TRAIN_DIR,
                                        stdout=log, stderr=subprocess.STDOUT,
                                        env=env, creationflags=flags)
    return {"ok": True, "pid": _train_proc["p"].pid}


def train_stop():
    p = _train_proc["p"]
    if p and p.poll() is None:
        p.terminate()
        return {"ok": True}
    return {"ok": False, "error": "没有在跑"}


def worldbook_context(messages, depth=None, max_entries=None, max_chars=None):
    """按关键词匹配注入世界书"""
    wb = WB
    depth = depth or wb.get("scan_depth", 3)
    max_entries = max_entries or wb.get("max_entries", 3)
    max_chars = max_chars or wb.get("max_chars", 1200)
    recent = " ".join((m.get("content") or "") for m in messages[-depth:])
    hits = []
    for e in wb.get("entries", []):
        cs = e.get("case_sensitive", False)
        hay = recent if cs else recent.lower()
        for kw in e.get("keywords", []):
            k = kw if cs else kw.lower()
            if k and k in hay:
                hits.append(e)
                break
    hits.sort(key=lambda e: -e.get("priority", 0))
    hits = hits[:max_entries]
    if not hits:
        return "", []
    parts, names, total = [], [], 0
    for e in hits:
        c = e.get("content", "").strip()
        if not c:
            continue
        if total + len(c) > max_chars:
            break
        parts.append("【%s】\n%s" % (e.get("name", ""), c))
        names.append(e.get("name", ""))
        total += len(c)
    return "\n\n".join(parts), names


# ---------------- token / 花费统计 ----------------
_USAGE = {"tokens": 0, "cost": 0.0, "calls": 0,
          "since": time.strftime("%Y-%m-%d %H:%M:%S")}
_USAGE_LOCK = _th.Lock()


def _record_usage(model, usage):
    """记一次模型调用，返回这次的花费信息（给界面显示用）。

    usage 直接用接口返回的 usage 字段（有 prompt_cache_hit_tokens 就更准）；
    拿不到 usage 时记 0 —— 统计不准也不能影响对话。
    """
    usage = usage or {}
    try:
        c = _pricing.cost(model, usage)
    except Exception:
        c = 0.0
    tokens = int(usage.get("total_tokens") or 0)
    with _USAGE_LOCK:
        _USAGE["tokens"] += tokens
        _USAGE["cost"] += c
        _USAGE["calls"] += 1
        cum_t, cum_c = _USAGE["tokens"], _USAGE["cost"]
    return {"tokens": tokens,
            "in": int(usage.get("prompt_tokens") or 0),
            "out": int(usage.get("completion_tokens") or 0),
            "cost": round(c, 6),
            "model": model,
            "cumTokens": cum_t,
            "cumCost": round(cum_c, 6),
            "currency": _pricing.currency()}


def _usage_snapshot():
    with _USAGE_LOCK:
        d = dict(_USAGE)
        d["cost"] = round(d["cost"], 6)
    try:
        _t, src = _pricing.table()
        d["priceSource"] = src
        d["peak"] = _pricing.is_peak()
        d["currency"] = _pricing.currency()
    except Exception:
        d["priceSource"] = "builtin"
        d["peak"] = False
        d["currency"] = "CNY"
    d["ok"] = True
    return d

# ---------------- 记忆书（见 memory.py） ----------------
_MEM_PACK_LOCK = _th.Lock()


def _mem_llm(prompt, max_tokens=1200, timeout=90):
    """给记忆书用的模型调用：不加载人设，只让它把一段对话压成条目。"""
    cc = cloud_cfg()
    if cc:
        base_url = (cc.get("base_url") or OLLAMA).rstrip("/")
        key = cc.get("api_key") or ""
        model = cc.get("model") or DEFAULT_MODEL
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + key}
    else:
        base_url = OLLAMA.rstrip("/")
        model = DEFAULT_MODEL
        headers = {"Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": _memory.SUM_SYSTEM},
                     {"role": "user", "content": prompt}],
        "stream": False,
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    if not cc:
        payload["reasoning_effort"] = "none"
    if cc and "pro" in model:
        payload["thinking"] = {"type": "disabled"}
    rq = urllib.request.Request(
        base_url + "/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers)
    try:
        with urllib.request.urlopen(rq, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8"))
        try:
            _record_usage(model, d.get("usage") or {})
        except Exception:
            pass
        return (d["choices"][0]["message"].get("content") or "").strip()
    except Exception as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")[:200]
        except Exception:
            pass
        log("记忆书：模型调用失败 %s: %s %s" % (type(e).__name__, e, detail))
        raise


def _memory_context(msgs, cloud):
    """按 token 预算决定这一轮发什么。

    没超阈值：原样全发（和以前一样）。
    超了阈值：只发「最近一段原文」，更早的压成记忆条目一起注入。

    **不会留空洞**：`covered`（已总结到哪）如果落后于「最近段起点」，
    窗口就往前拉到 covered，宁可多发几句，也不让中间那段两头不着。
    """
    try:
        trig, recent_b, entries_b = _memory.budget(cloud)
        total = _memory.est_messages(msgs)
        if total <= trig or len(msgs) < 4:
            return msgs, ""
        r = _memory.runtime()
        aligned = _memory.recent_start(msgs, recent_b, 0)
        if aligned <= 0:
            return msgs, ""
        covered = int(r.get("covered") or 0)
        # 历史变短了（"开始游戏"清空 / 换了存档）→ 记忆书作废，别把上一段对话的印象带过来
        if covered > len(msgs):
            _memory.reset_for_load([], 0, "")
            r = _memory.runtime()
            covered = 0
        # 第一次跨过阈值：必须先把旧的那段压成条目，否则就只能整段拒发
        if not r.get("entries"):
            ok, n = _memory.pack_span(msgs, 0, aligned, _mem_llm,
                                      max_chunks=int(_memory.cfg()["sync_chunks"]))
            covered = int(_memory.runtime().get("covered") or 0) if ok else 0
            log("记忆书：首次压缩%s（%d 条，覆盖到第 %d 条）"
                % ("成功" if ok else "失败", n, covered))
        start = min(aligned, covered) if covered else 0
        r = _memory.runtime()
        note = _memory.render_note(r.get("entries") or [], entries_b)
        turn = int(r.get("turns") or 0) + 1
        _memory.runtime_set(turns=turn, window_start=start)
        repack = int(_memory.cfg()["repack_turns"])
        if covered and aligned > covered and repack > 0 and turn % repack == 0:
            _repack_async(msgs, covered, aligned)
        log("记忆书：估算 %d / 阈值 %d，发最近 %d 条（共 %d 条，%d 条记忆）"
            % (total, trig, len(msgs) - start, len(msgs), len(r.get("entries") or [])))
        return (msgs[start:], note) if start > 0 else (msgs, note)
    except Exception as e:
        log("记忆书失败（本轮按全量发送）: %s" % e)
        return msgs, ""


def _repack_async(msgs, a, b):
    """后台重新打包被折叠的那一段；同时在跑就跳过（不排队）。"""
    def work():
        if not _MEM_PACK_LOCK.acquire(blocking=False):
            return
        try:
            ok, n = _memory.pack_span(msgs, a, b, _mem_llm,
                                      max_chunks=int(_memory.cfg()["async_chunks"]))
            if ok:
                log("记忆书：后台打包 %d~%d（%d 条）" % (a, b, n))
        except Exception as e:
            log("记忆书：后台打包失败 %s" % e)
        finally:
            _MEM_PACK_LOCK.release()
    _th.Thread(target=work, daemon=True).start()


def _pack_until(msgs, target, slot="", budget_sec=45):
    """一直打包到 covered >= target（或超时）。只给后台线程用。"""
    t0 = time.time()
    while True:
        cur = int(_memory.runtime().get("covered") or 0)
        if cur >= target or (time.time() - t0) > budget_sec:
            return cur
        ok, n = _memory.pack_span(msgs, cur, target, _mem_llm, slot,
                                  max_chunks=int(_memory.cfg()["async_chunks"]))
        if not ok:
            log("记忆书：打包中断（%d/%d）" % (cur, target))
            return int(_memory.runtime().get("covered") or 0)


def _finalize_save_memory(slot, saved_at, msgs):
    """存档后的后台任务：把会被折叠的那段压成条目，写回同一个存档文件。

    写回前会核对 saved_at：期间玩家又存过档就放弃，绝不覆盖新内容。
    """
    try:
        trig, recent_b, entries_b = _memory.budget(bool(cloud_cfg()))
        aligned = _memory.recent_start(msgs, recent_b, 0)
        r = _memory.runtime()
        covered = int(r.get("covered") or 0)
        if aligned > covered:
            with _MEM_PACK_LOCK:
                cur = _pack_until(msgs, aligned, slot)
            log("记忆书：存档 %s 覆盖到 %d/%d" % (slot, cur, aligned))
        r = _memory.runtime()
        mem = {
            "enabled": True,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "covered_upto": int(r.get("covered") or 0),
            "entries": list(r.get("entries") or []),
        }
        if _sessions.session_patch_memory(slot, mem, expect_saved_at=saved_at):
            log("记忆书：已写入存档 %s（%d 条）" % (slot, len(mem["entries"])))
        else:
            log("记忆书：存档 %s 已被覆盖，丢弃这次总结" % slot)
    except Exception as e:
        log("记忆书：存档后台任务失败 %s" % e)


# ---------------- HTTP 服务 ----------------


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=UI_DIR, **kw)

    def end_headers(self):
        # 禁止 WebView2 缓存, 否则改了 css/js 看不到效果
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        super().end_headers()

    def log_message(self, *a):
        pass

    def translate_path(self, path):
        p = path.split("?")[0].split("#")[0]
        if p == "/" or p == "/game" or p == "/game/":
            p = "/index.html"
        elif p.startswith("/game/"):
            p = p[len("/game"):]
        elif p.startswith("/api/"):
            return os.path.join(UI_DIR, "__api__")
        import posixpath, urllib.parse
        p = urllib.parse.unquote(p)
        p = posixpath.normpath(p).lstrip("/")
        # /game/assets/** 走素材目录（开发时指向 program/res/assets）
        if p.split("/")[0] == "assets" and os.path.isdir(ASSETS_DIR):
            parts = p.split("/")[1:]
            return os.path.join(ASSETS_DIR, *parts)
        return os.path.join(UI_DIR, *p.split("/"))

    def _json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def send_response(self, code, message=None):
        self._last_status = code
        return super().send_response(code, message)

    def handle_one_request(self):
        self._req_start = time.time()
        try:
            return super().handle_one_request()
        finally:
            self._log_request(getattr(self, "_last_status", ""))

    def send_head(self):
        """支持 Range 的静态文件服务（视频能边下边播、可跳读）"""
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            return super().send_head()
        try:
            f = open(path, "rb")
        except OSError:
            return super().send_head()
        try:
            fs = os.fstat(f.fileno())
            size = fs[6]
            ctype = self.guess_type(path)
            rng = self.headers.get("Range")
            start, end = 0, size - 1
            partial = False
            if rng and rng.startswith("bytes=") and size > 0:
                spec = rng[6:].split(",")[0].strip()
                a, _, b = spec.partition("-")
                try:
                    if a:
                        start = int(a)
                        if b:
                            end = min(int(b), size - 1)
                    elif b:                      # bytes=-N 取末尾 N 字节
                        start = max(0, size - int(b))
                except ValueError:
                    start, end = 0, size - 1
                if start > end or start >= size:
                    self.send_error(416)
                    f.close()
                    return None
                partial = True
            count = end - start + 1
            self.send_response(206 if partial else 200)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(count))
            if partial:
                self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
            self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
            self.end_headers()
            f.seek(start)
            self._range_left = count
            return f
        except Exception:
            f.close()
            raise

    def copyfile(self, source, outputfile):
        left = getattr(self, "_range_left", None)
        self._range_left = None
        if left is None:
            import shutil
            shutil.copyfileobj(source, outputfile, 1024 * 256)
            return
        while left > 0:
            chunk = source.read(min(1024 * 256, left))
            if not chunk:
                break
            outputfile.write(chunk)
            left -= len(chunk)

    def _log_request(self, status=None):
        try:
            dur = (time.time() - self._req_start) * 1000 if hasattr(self, "_req_start") else 0
            lvl = "SLOW" if dur > applog._SLOW_REQUEST_MS else "REQ"
            applog.log("%s %s -> %s  %.0fms" % (getattr(self, "command", "?"),
                       self.path[:120], status or "", dur), lvl)
        except Exception:
            pass

    def do_GET(self):
        self._req_start = time.time()
        if self.path.startswith("/api/window"):
            return self._window_ctl()
        if self.path.startswith("/api/log/dump"):
            applog.dump_stacks("手动触发")
            return self._json({"ok": True, "log": applog.path()})
        if self.path.startswith("/api/tts"):
            return self._tts()
        if self.path == "/api/ping":
            return self._json({"ok": True, "app": APP_NAME})
        if self.path == "/api/voice/ok":
            try:
                import tts_client as _tc
                _st = _tc.status()
                return self._json({"ok": (not NO_MODELS) and bool(_st.get("available")),
                                   "ready": bool(_st.get("ready")),
                                   "error": _st.get("error") or ""})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)})
        if self.path == "/api/ollama":
            return self._json({"models": ollama_models()})
        if self.path == "/api/usage":
            return self._json(_usage_snapshot())
        if self.path.startswith("/api/price"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            m = (q.get("model") or [""])[0]
            try:
                p, src = _pricing.prices_for(m)
                return self._json({"ok": True, "model": m, "price": p, "source": src,
                                   "peak": _pricing.is_peak(),
                                   "currency": _pricing.currency()})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)})
        if self.path == "/api/prefs":
            return self._json({"ok": True, "prefs": prefs_load()})
        if self.path == "/api/modelcfg":
            return self._json(model_cfg_all())
        if self.path.startswith("/api/session/load"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            slot = (q.get("slot") or ["auto"])[0]
            d = session_load(slot)
            # 读档：看到 memory 标记就把记忆书接到运行时缓存上
            try:
                mem = (d or {}).get("memory") or {}
                if mem.get("enabled"):
                    _memory.reset_for_load(mem.get("entries") or [],
                                           mem.get("covered_upto") or 0, slot)
                    log("记忆书：读档 %s，带 %d 条记忆" % (slot, len(mem.get("entries") or [])))
                else:
                    _memory.reset_for_load([], 0, slot)
            except Exception as e:
                log("记忆书：读档恢复失败 %s" % e)
            if isinstance(d, dict):
                d.pop("memory", None)          # 记忆书对前端不可见
            return self._json(d)
        if self.path.startswith("/api/session/list"):
            return self._json(session_list())
        if self.path.startswith("/api/session/thumb"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            data = session_thumb((q.get("slot") or [""])[0])
            if not data:
                return self._json({"ok": False, "error": "no thumb"}, 404)
            try:
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "public, max-age=600")
                self.end_headers()
                self.wfile.write(data)
            except Exception:
                pass
            return
        if self.path.startswith("/api/text"):
            return self._text_img()
        if self.path == "/api/train/status":
            return self._json(train_status())
        if self.path == "/api/train/info":
            return self._json(train_info())
        if self.path.startswith("/api/model/probe"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            return self._json(model_probe((q.get("url") or [""])[0]))
        return super().do_GET()

    def do_POST(self):
        self._req_start = time.time()
        if self.path == "/api/prefs":
            try:
                body = self._body()
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 400)
            if not isinstance(body, dict):
                return self._json({"ok": False, "error": "bad prefs"}, 400)
            return self._json({"ok": prefs_save(body)})
        if self.path == "/api/modelcfg":
            return self._modelcfg()
        if self.path.startswith("/api/session/save"):
            try:
                body = self._body()
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 400)
            if not isinstance(body, dict):
                return self._json({"ok": False, "error": "bad body"}, 400)
            msgs = body.get("messages") or []
            over = False
            try:
                trig, _rb, _eb = _memory.budget(bool(cloud_cfg()))
                over = _memory.est_messages(msgs) > trig
            except Exception:
                pass
            if over:
                # 先写"生成中"的标记：读档立刻能用，条目由后台补
                r = _memory.runtime()
                body["memory"] = {"enabled": True, "generated_at": None,
                                  "covered_upto": int(r.get("covered") or 0),
                                  "entries": list(r.get("entries") or [])}
            res = session_save(body)
            if res.get("ok") and over:
                _th.Thread(target=_finalize_save_memory,
                           args=(body.get("slot") or "auto", res.get("saved_at"),
                                 list(msgs)),
                           daemon=True).start()
            return self._json(res)
        if self.path == "/api/chat":
            return self._chat()
        if self.path == "/api/train/start":
            try:
                return self._json(train_start())
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 500)
        if self.path == "/api/train/stop":
            return self._json(train_stop())
        self.send_error(404)

    def _window_ctl(self):
        """无边框窗口的关闭 / 最小化 / 最大化（走 HTTP，避免依赖 js_api）"""
        from urllib.parse import urlparse, parse_qs
        try:
            q = parse_qs(urlparse(self.path).query)
            action = qs(q, ("action", "act")).strip()
            w = globals().get("_WINDOW")
            try:
                applog.log("窗口控制: action=%s window=%s" % (action, "有" if w else "无"), "WIN")
            except Exception:
                pass
            if w is None:
                return self._json({"ok": False, "error": "窗口未就绪"})
            if action == "close":
                w.destroy()
            elif action == "min":
                w.minimize()
            elif action == "max":
                try:
                    w.maximize()
                except Exception:
                    w.toggle_fullscreen()
            elif action == "move":
                import ctypes
                from ctypes import wintypes
                u = ctypes.WinDLL("user32", use_last_error=True)
                u.FindWindowW.restype = wintypes.HWND
                u.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
                u.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
                u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                           ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
                dx = int(q.get("dx", ["0"])[0]); dy = int(q.get("dy", ["0"])[0])
                hw = u.FindWindowW(None, WINDOW_TITLE)
                r = wintypes.RECT(); u.GetWindowRect(hw, ctypes.byref(r))
                u.SetWindowPos(hw, None, r.left + dx, r.top + dy, 0, 0, 0x0001 | 0x0004)
            elif action == "dragbegin":
                try:
                    _api_ref = globals().get("_API")
                    if _api_ref is not None:
                        return self._json(_api_ref.drag_begin())
                except Exception as e:
                    return self._json({"ok": False, "error": str(e)})
                return self._json({"ok": False})
            elif action == "togglemax":
                u = _user32()
                hw = _win_hwnd()
                if hw:
                    maxed = bool(u.IsZoomed(hw))
                    u.ShowWindow(hw, 9 if maxed else 3)      # SW_RESTORE / SW_MAXIMIZE
                    return self._json({"ok": True, "maxed": bool(u.IsZoomed(hw))})
                # 拿不到 hwnd 时退回 pywebview（和最小化/关闭同一条路）
                try:
                    if getattr(w, "_wa2_maxed", False):
                        w.restore(); w._wa2_maxed = False
                    else:
                        w.maximize(); w._wa2_maxed = True
                    return self._json({"ok": True, "maxed": w._wa2_maxed})
                except Exception as e:
                    return self._json({"ok": False, "error": str(e)})
            elif action == "togglefull":
                # 浏览器 Fullscreen API 在无边框 WebView2 上会让窗口变成
                # “铺满屏幕但点不动”的透明层，所以改走 pywebview 自己的全屏开关
                try:
                    w.toggle_fullscreen()
                    w._wa2_full = not bool(getattr(w, "_wa2_full", False))
                    return self._json({"ok": True, "fullscreen": w._wa2_full})
                except Exception as e:
                    try:
                        w.maximize()
                        return self._json({"ok": True, "fallback": "maximize"})
                    except Exception:
                        return self._json({"ok": False, "error": str(e)})
            elif action == "fullscreen":
                # OPTION 1 的「窗口模式 / 全屏模式」：按目标状态切，不是盲目 toggle。
                # 退出全屏时必须回到一个**明显小于全屏**的窗口 —— 不然在 4K/高 DPI 上
                # 全屏与"最大化"看起来一样大（用户实测反馈过）。
                want = qs(q, ("on",), "1")
                target = (want != "0")
                try:
                    cur = bool(getattr(w, "_wa2_full", False))
                    if target != cur:
                        w.toggle_fullscreen()
                    w._wa2_full = target
                    if not target:
                        try:
                            w.restore()                      # 先解除最大化
                        except Exception:
                            pass
                        try:
                            w.resize(*WINDOWED_SIZE)
                        except Exception:
                            pass
                        try:
                            # move() 收的是 DIP，GetSystemMetrics 给的是物理像素，先换算
                            sw, sh = _screen_size()
                            dp = _dpi_scale()
                            if sw and sh and dp > 0:
                                w.move(int((sw / dp - WINDOWED_SIZE[0]) / 2),
                                       int((sh / dp - WINDOWED_SIZE[1]) / 2))
                        except Exception:
                            pass
                    return self._json({"ok": True, "fullscreen": target})
                except Exception as e:
                    # 全屏 API 不可用时退回最大化，至少不是"点了没反应"
                    try:
                        w.maximize()
                        w._wa2_full = target
                        return self._json({"ok": True, "fullscreen": target, "fallback": "maximize"})
                    except Exception:
                        return self._json({"ok": False, "error": str(e)})
            elif action == "state":
                u = _user32()
                hw = _win_hwnd()
                return self._json({"ok": bool(hw), "maxed": bool(u.IsZoomed(hw)) if hw else False,
                                   "fullscreen": bool(getattr(w, "_wa2_full", False))})
            elif action == "resize":
                try:
                    nw = int(q.get("w", ["0"])[0])
                    nh = int(q.get("h", ["0"])[0])
                except Exception:
                    return self._json({"ok": False, "error": "bad size"})
                if nw < 640 or nh < 360:
                    return self._json({"ok": False, "error": "too small"})
                w = globals().get("_WINDOW")
                try:
                    w.resize(nw, nh)
                    return self._json({"ok": True, "w": nw, "h": nh})
                except Exception as e:
                    return self._json({"ok": False, "error": str(e)})
            elif action == "restore":
                try:
                    w.restore()
                except Exception:
                    w.toggle_fullscreen()
            return self._json({"ok": True, "action": action})
        except Exception as e:
            return self._json({"ok": False, "error": str(e)})

    def _tts(self):
        """合成语音，返回 wav

        参数（正式名 / 兼容旧名）：
            text      / t       要念的文字
            lang                 zh | ja
            emotion   / emo      情绪标签，影响语气
            speak_ja  / sp       日文原文；给了就直接念它（不再过翻译）
        """
        from urllib.parse import urlparse, parse_qs
        try:
            q = parse_qs(urlparse(self.path).query)
            text = qs(q, ("text", "t")).strip()
            lang = qs(q, ("lang",), "zh").strip() or "zh"
            emotion = qs(q, ("emotion", "emo"), "neutral").strip() or "neutral"
            speak_ja = qs(q, ("speak_ja", "sp")).strip()
            if not text:
                return self._json({"error": "empty"}, 400)
            if NO_MODELS:
                return self._json({"error": "安全模式: 未加载语音模型"}, 503)
            if not tts_client.start():
                # 语音还在预热: 立刻返回, 前端只显示文字
                applog.log("语音未就绪: %s" % tts_client.status(), "WARN")
                return self._json({"error": "语音未就绪"}, 503)
            speak_text = text
            t_t0 = time.time()
            if speak_ja:
                speak_text = speak_ja
                lang = "ja"
            elif lang == "ja":
                ja = translate_ja(text)
                if ja:
                    speak_text = ja
                    log("日文配音: %s" % ja)
                else:
                    lang = "zh"          # 翻译失败就退回中文
            applog.log("TTS 准备: lang=%s emo=%s 文本=%s (翻译耗时 %.1fs)"
                       % (lang, emotion, speak_text[:24], time.time() - t_t0), "TTS")
            t_s0 = time.time()
            data = tts_client.synthesize(speak_text, lang, emo=emotion)
            applog.log("TTS 合成: %s 字节, 耗时 %.1fs"
                       % (len(data or b""), time.time() - t_s0), "TTS")
            if not data:
                return self._json({"error": tts_client.status()}, 500)
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            return self._json({"error": str(e)}, 500)

    def _modelcfg(self):
        """POST /api/modelcfg  body: {section, endpoint, key, model, probe}"""
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n).decode("utf-8") or "{}")
        except Exception as e:
            return self._json({"ok": False, "error": "bad json: %s" % e})

        sec = body.get("section")
        if sec not in MODEL_SECTIONS:
            return self._json({"ok": False, "error": "bad section"})

        if body.get("disconnect"):
            cur = (model_cfg_all().get(sec) or {})
            model_cfg_save(sec, cur.get("endpoint") or "", cur.get("key") or "",
                           cur.get("model") or "", False)
            return self._json({"ok": False, "saved": True, "disconnected": True,
                               "cfg": model_cfg_all()})

        endpoint = (body.get("endpoint") or "").strip()
        key = (body.get("key") or "").strip()
        model = (body.get("model") or "").strip()

        if body.get("probe"):
            ok, latency, models = probe_endpoint(sec, endpoint, key, model)
            # 语音板块：端点没起来就顺手把本地 GPT-SoVITS 拉起来再探一次
            if (not ok) and sec == "voice":
                ep = (endpoint or "").lower()
                if "127.0.0.1" in ep or "localhost" in ep:
                    try:
                        log("voice: starting local GPT-SoVITS ...")
                        tts_client.start()
                        ok, latency, models = probe_endpoint(sec, endpoint, key, model)
                    except Exception as e:
                        log("voice start failed: %s" % e)
        else:
            ok = False
            latency, models = 0, []

        # 模型名以探测结果为准：填的不在列表里就按板块偏好挑一个
        if models:
            if model not in models:
                pref = {
                    "mt": ["hy-mt", "mt", "qwen"],
                    "chat": ["deepseek", "chat"],
                    "voice": ["sovits", "gpt"],
                }.get(sec, [])
                model = None
                for token in pref:
                    for mm in models:
                        if token in mm.lower():
                            model = mm
                            break
                    if model:
                        break
                if not model:
                    model = models[0]

        saved = model_cfg_save(sec, endpoint, key, model, ok)
        if saved:
            apply_model_cfg()
        return self._json({"ok": ok, "saved": saved, "latency_ms": latency,
                           "models": models, "cfg": model_cfg_all()})

    def _text_img(self):
        """把文字渲染成 PNG（和对话框走同一套字模流程）

        参数（正式名 / 兼容旧名）：
            text            / t            要渲染的文字
            plain           / p            1 = 无描边、无边距
            max_width       / w            单行最大像素宽
            chars_per_line  / per_line     单行最多几个全角字（不传用默认 20）
            size            / s            兼容旧参数的兜底字号（仅 GLIB 回退用）
            embolden        / e            兼容旧参数的加粗（仅 GLIB 回退用）
            color           / c            染色，RRGGBB
        """
        from urllib.parse import urlparse, parse_qs
        try:
            q = parse_qs(urlparse(self.path).query)
            text = qs(q, ("text", "t")).strip()
            plain = qs(q, ("plain", "p"), "0") == "1"
            try:
                max_width = int(qs(q, ("max_width", "w"), "1200"))
            except ValueError:
                max_width = 1200
            try:
                chars_per_line = int(qs(q, ("chars_per_line", "per_line"), "0")) or None
            except ValueError:
                chars_per_line = None
            color = qs(q, ("color", "c")).strip().lstrip("#") or None
            size = int(qs(q, ("size", "s"), "56") or 56)
            embolden = int(qs(q, ("embolden", "e"), "0") or 0)
            if not text:
                text = " "
            _key = (text, plain, max_width, chars_per_line, color)
            _disk = _text_disk_path(_key)
            _TEXT_DISK = _disk
            if os.path.exists(_disk):
                data = open(_disk, "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                self.wfile.write(data)
                return
            if _key in _TEXT_CACHE:
                data = _TEXT_CACHE[_key]
            else:
                try:
                    import io as _io
                    import sub_render
                    with _RENDER_LOCK:
                        img = sub_render.render_block(
                            text, maxw=max_width, stroke=not plain,
                            margin=(None if not plain else 0), per_line=chars_per_line, color=color)
                        _buf = _io.BytesIO()
                        img.save(_buf, "PNG")
                        data = _buf.getvalue()
                        # 缓存上限：超过 400 条就丢掉最早的，避免内存一直涨
                        if len(_TEXT_CACHE) >= 400:
                            try:
                                _TEXT_CACHE.pop(next(iter(_TEXT_CACHE)))
                            except Exception:
                                _TEXT_CACHE.clear()
                except Exception:
                    if not GLIB:
                        raise
                    data = GLIB.render_cached(text, maxw=max_width, size=size, embolden=embolden)
                if len(_TEXT_CACHE) < _TEXT_CACHE_MAX:
                    _TEXT_CACHE[_key] = data
                try:
                    if not os.path.exists(_disk):
                        with open(_disk, "wb") as _f:
                            _f.write(data)
                except Exception:
                    pass
        except Exception as e:
            import traceback
            try:
                open(os.path.join(os.environ.get("TEMP", "."), "wa2_text_error.log"), "a", encoding="utf-8").write(
                    traceback.format_exc() + "\n----\n")
            except Exception:
                pass
            return self._json({"error": str(e)}, 500)
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n).decode("utf-8"))

    def _chat(self):
        try:
            req = self._body()
        except Exception as e:
            return self._json({"error": "bad request: %s" % e}, 400)

        if NO_MODELS and not cloud_cfg():
            return self._json({"reply": "（安全模式：模型未加载）", "thinking": ""})

        emo = "calm"
        scene_now = ""
        outfit_now = ""
        cc = cloud_cfg()
        base_url = (req.get("base_url") or (cc.get("base_url") if cc else "") or OLLAMA).strip()
        if not (base_url.startswith("http://") or base_url.startswith("https://")):
            base_url = OLLAMA
        model = req.get("model") or (cc.get("model") if cc else "") or DEFAULT_MODEL
        if not cc and model not in ollama_models():
            model = FALLBACK_MODEL if FALLBACK_MODEL in ollama_models() else model
        msgs = req.get("messages") or []

        # 上下文预算：超过阈值就切成「记忆书 + 最近一段原文」
        msgs, mem_note = _memory_context(msgs, bool(cc))

        wb_ctx, wb_names = worldbook_context(msgs)
        system = persona_text()
        if mem_note:
            system = system + "\n\n" + mem_note
        if wb_ctx:
            system = system + "\n\n" + wb_ctx

        # 剧本检索: 找出和这句话相关的往事, 作为"记忆"而非台词
        try:
            if STORY is not None and req.get("memory"):
                last_user = ""
                for m in reversed(msgs):
                    if m.get("role") == "user":
                        last_user = m.get("content") or ""
                        break
                mem = STORY.memory_context(last_user, k=2, max_chars=900)
                if mem:
                    system = system + (
                        "\n\n【你想起的一些往事（资料，不是台词）】\n"
                        + mem
                        + "\n（这些只是你记得的事。用你自己的口气简短说出来，"
                          "不要照抄格式，不要整段复述，不要描写场景。）")
        except Exception as e:
            log("story_rag 失败: %s" % e)

        if cc:
            # 云端：人设末尾补语言/格式约束，前面插 few-shot
            system = system + (
                "\n\n【语言】无论对方用什么语言说话，你都只用日语回答。"
                "\n【场景】只有在对话里明确发生了地点变化时才输出 <scene>地点</scene>，"
                "可选值：classroom(教室) corridor(走廊) music(音乐室) street(街道) cafe(咖啡馆) "
                "home(家里) night(夜晚) stage(舞台)。没有换地点就不要输出这个标记。"
                "\n【服装】只有明确换了一套衣服时才输出 <outfit>编号</outfit>："
                "001(校服) 003(演出服) 008(常服) 022(常服2) 020(居家) 027(礼服) 029(睡衣) 036(和服)。"
                "平时绝对不要输出。"
                "\n【情绪】在回复最前面输出一个情绪标记，格式 <emotion>情绪</emotion>，"
                "只能从这些里选：calm(平静) soft(温柔) 毒舌 撒娇 哭腔 调侃吐槽 问句。"
                "标记只能是开头那一个，正文里不要再出现。"
                "\n【格式】只输出你要说的话。如果有动作或表情，必须写成 "
                "<action>（…）</action> 放在台词前面，不允许出现没有标签的描写句。")
        payload = {
            "model": model,
            "messages": ([{"role": "system", "content": system}]
                         + (fewshot_msgs() if cc else []) + msgs),
            "stream": False,
            "max_tokens": 400 if cc else 260,
        }
        if not cc:
            payload["reasoning_effort"] = "none"
        if cc and "pro" in model:
            payload["thinking"] = {"type": "disabled"}
        t0 = time.time()
        try:
            rq = urllib.request.Request(
                base_url.rstrip("/") + "/v1/chat/completions",
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers=({"Content-Type": "application/json",
                          "Authorization": "Bearer " + cc["api_key"]} if cc
                         else {"Content-Type": "application/json"}))
            with urllib.request.urlopen(rq, timeout=300) as r:
                d = json.loads(r.read().decode("utf-8"))
            raw = (d["choices"][0]["message"].get("content") or "").strip()
            _uinfo = _record_usage(model, d.get("usage") or {})
            raw, emo = split_emotion(raw)
            raw, scene_now, outfit_now = split_scene(raw)
            acts, raw = split_action(raw)
            reply, think = split_thinking(raw)
            action = " ".join(a for a in acts if a).strip()
            # 游戏里角色台词一律用「」包起来，由程序统一处理，不让模型自己加
            _r = (reply or "").strip()
            if _r:
                _r = _r.strip("「」『』")
                reply = "「" + _r + "」"

            # v7 用日文回答: 日文原文留给语音, 中文译文给对话框
            reply_zh = ""
            action_zh = ""
            try:
                if any("\u3040" <= c <= "\u30ff" for c in reply):
                    tts_client.start_translate()
                    reply_zh = tts_client.translate_via_service(_r, "zh")
                    if action:
                        action_zh = tts_client.translate_via_service(action, "zh")
            except Exception as e:
                log("日译中失败: %s" % e)

            self._json({"reply": reply, "reply_zh": reply_zh, "thinking": think,
                        "action": action, "action_zh": action_zh,
                        "usage": _uinfo,
                        "model": model,
                        "ms": int((time.time() - t0) * 1000),
                        "worldbook": wb_names})
        except urllib.error.HTTPError as e:
            self._json({"error": "HTTP %s %s" % (e.code, e.read().decode("utf-8", "replace")[:200])})
        except Exception as e:
            self._json({"error": "连不上 Ollama（%s），请先启动 Ollama" % e})


_models_cache = {"t": 0, "v": []}


def ollama_models():
    now = time.time()
    if now - _models_cache["t"] < 10:
        return _models_cache["v"]
    try:
        with urllib.request.urlopen(OLLAMA + "/api/tags", timeout=3) as r:
            d = json.loads(r.read().decode("utf-8"))
        v = [m["name"] for m in d.get("models", [])]
    except Exception:
        v = []
    _models_cache.update({"t": now, "v": v})
    return v


def _warm_font():
    try:
        import sub_render
        n = sub_render.atlas_coverage()
        log("字模预热完成: %d 个字" % n)
    except Exception as e:
        log("字模预热失败: %s" % e)


threading.Thread(target=_warm_font, daemon=True).start()
if not NO_MODELS:
    threading.Thread(target=lambda: tts_client.start_translate(), daemon=True).start()
if not NO_MODELS:
    threading.Thread(target=lambda: tts_client.start(), daemon=True).start()
applog.start_heartbeat(30)
applog.log("程序启动: 安全模式=%s 语音依赖=%s 模型=%s" % (NO_MODELS, tts_client.available(), DEFAULT_MODEL))


class _Server(ThreadingHTTPServer):
    """Windows 上 SO_REUSEADDR 允许**两个进程同时绑同一个端口**：
    第二个进程以为自己起来了，但连接都被前一个吃掉 —— 表现就是
    「--serve-only 启动后进程活着，端口却不响应」。这里必须关掉。"""
    allow_reuse_address = False


def serve(port_holder, prefer_port=None):
    ports = ([prefer_port] if prefer_port else []) + [8771, 8772, 0]
    srv = None
    for p in ports:
        try:
            srv = _Server(("127.0.0.1", p), Handler)
            break
        except OSError:
            continue
    if srv is None:
        srv = _Server(("127.0.0.1", 0), Handler)
    port_holder.append(srv.server_address[1])
    srv.serve_forever()


def serve_only(prefer_port=None):
    """只起 HTTP 服务，不创建窗口。

    用途：只改后端 / 用 curl 调接口 / 在没有界面素材的机器上调试。
    启动后访问 http://127.0.0.1:<端口>/api/ping 验证。
    """
    os.environ.setdefault("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
                          "--autoplay-policy=no-user-gesture-required")
    _memory.clear_runtime()          # 后端模式也当作一次"新启动"

    port_holder = []
    t = threading.Thread(target=serve, args=(port_holder, prefer_port), daemon=True)
    t.start()
    for _ in range(100):
        if port_holder:
            break
        time.sleep(0.05)

    port = port_holder[0] if port_holder else 0
    if not port:
        log("启动失败：没有拿到可用端口（8771/8772/随机端口都绑定失败）")
        return 0
    base = "http://127.0.0.1:%d" % port

    log("=" * 60)
    log("  后端模式（不开窗口）")
    log("  %s" % base)
    log("")
    log("  自检      GET  %s/api/ping" % base)
    log("  对话      POST %s/api/chat" % base)
    log("  文字渲染  GET  %s/api/text?text=测试" % base)
    log("  语音      GET  %s/api/tts?text=テスト" % base)
    log("  训练进度  GET  %s/api/train/status" % base)
    log("")
    log("  Ctrl+C 退出")
    log("=" * 60)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("\n已退出")
    return port


def main():
    _clear_text_cache()
    _memory.clear_runtime()          # 记忆缓存只活这一次运行
    try:
        import tts_client as _tc
        _tc.clear_tts_cache()
    except Exception:
        pass
    os.environ.setdefault("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
                      "--autoplay-policy=no-user-gesture-required")
    import webview

    port_holder = []
    t = threading.Thread(target=serve, args=(port_holder,), daemon=True)
    t.start()
    for _ in range(100):
        if port_holder:
            break
        time.sleep(0.05)
    bind_port_zero = True
    port = port_holder[0] if port_holder else 0
    url = "http://127.0.0.1:%d/game/index.html?t=%d" % (port, int(time.time()))

    class _Api:
        """窗口控制（无边框窗口需要自己实现关闭/最小化）"""

        def __init__(self):
            self._window = None

        def win(self, action):
            try:
                if action == "close":
                    self._window.destroy()
                elif action == "min":
                    self._window.minimize()
                return {"ok": True}
            except Exception as e:
                return {"ok": False, "error": str(e)}

        def drag_begin(self):
            """真正在用的拖动：后端开一个很轻的线程，盯着鼠标光标挪窗口。

            为什么不走前端算坐标：
              * JS 的 screenX 是 CSS 像素，GetWindowRect 是物理像素，高 DPI 下必然错位；
              * 每帧一次 JS→Python 桥调用，快拖时调用会排队，窗口追不上光标。
            这里光标位置和窗口位置都是物理像素，同一个坐标系，直接相减，不会有跳和偏。
            """
            try:
                import ctypes
                import threading
                import time as _t
                from ctypes import wintypes
                hw = _win_hwnd()
                if not hw:
                    return {"ok": False, "error": "no hwnd"}
                u = ctypes.WinDLL("user32", use_last_error=True)
                pt = wintypes.POINT()
                u.GetCursorPos(ctypes.byref(pt))
                r = wintypes.RECT()
                u.GetWindowRect(hw, ctypes.byref(r))
                sx, sy, wx, wy = pt.x, pt.y, r.left, r.top
                VK_LBUTTON = 0x01
                SWP = 0x0001 | 0x0004 | 0x0010   # NOSIZE | NOZORDER | NOACTIVATE
                if getattr(self, "_dragging", False):
                    return {"ok": True}          # 已经在拖了，别开第二个循环
                self._dragging = True
                state = {"run": True}

                def loop():
                    try:
                        while state["run"]:
                            if not (u.GetAsyncKeyState(VK_LBUTTON) & 0x8000):
                                break                      # 左键松开就结束
                            p = wintypes.POINT()
                            u.GetCursorPos(ctypes.byref(p))
                            u.SetWindowPos(hw, None, wx + (p.x - sx), wy + (p.y - sy),
                                           0, 0, SWP)
                            _t.sleep(0.008)                # ~120Hz
                    except Exception:
                        pass
                    finally:
                        state["run"] = False
                        self._dragging = False

                threading.Thread(target=loop, daemon=True).start()
                return {"ok": True}
            except Exception as e:
                return {"ok": False, "error": str(e)}

    _api = _Api()
    globals()["_API"] = _api
    window = webview.create_window(
        WINDOW_TITLE, url,
        width=1280, height=720,
        min_size=(1024, 576),
        background_color="#02070f",
        text_select=False,
        frameless=True,
        # 关闭"按住任意位置拖窗口"：否则拖历史界面滑块时整个窗口会跟着动
        easy_drag=False,
        js_api=_api,
    )
    _api._window = window
    global _WINDOW
    _WINDOW = window
    ensure_cloud_cfg()
    apply_model_cfg()
    # private_mode=True: 每次启动都用全新的 WebView2 数据目录, 彻底避免旧缓存
    webview.start(private_mode=True)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="AI 聊天界面架构 · 和纱")
    ap.add_argument("--serve-only", action="store_true",
                    help="只起 HTTP 服务，不创建窗口（调后端用）")
    ap.add_argument("--port", type=int, default=None,
                    help="指定端口（默认 8771，占用则自动换）")
    args = ap.parse_args()

    if args.serve_only:
        serve_only(args.port)
    else:
        main()
