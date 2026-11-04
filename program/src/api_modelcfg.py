# -*- coding: utf-8 -*-
"ModelCfgApi 的 mixin：从 main.py 拆出，方法体未改动。"

import json
import tts_client


class ModelCfgApi:
    """见 main.Handler；从 main 注入运行时全局。"""

    def _modelcfg(self):
        from main import (MODEL_SECTIONS, apply_model_cfg, log, model_cfg_all, model_cfg_save, probe_endpoint)
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
