# -*- coding: utf-8 -*-
"""/api/chat 的实现，从 main.py 拆出；逻辑未改动。"""

import json, os, time
import char_res
import characters
import diag
import persona_ctx
import persona_stage
import scene_cg
import tts_client


class ChatApi:
    """见 main.Handler。"""

    def _chat(self):
        from main import (ASSETS_DIR, DEFAULT_MODEL, FALLBACK_MODEL, NO_MODELS, OLLAMA, STORY, _memory_context, _record_usage, cloud_cfg, fewshot_msgs, log, ollama_models, split_action, split_emotion, split_scene, split_thinking, urllib)
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
        raw_msgs = list(msgs)          # 关系阶段要看完整历史，不能用裁剪后的
        # 当前背景图（前端带的）：模型没说时间时，新场景沿用这个时段
        prev_bg = (req.get("bg") or "").strip()
        # 当前衣服 / 手动时期：决定这一轮用哪套人设和世界书
        outfit_now = (req.get("outfit") or "").strip()
        period_req = (req.get("period") or "").strip().lower()
        period = period_req if period_req in ("ic", "cc", "coda") else persona_ctx.period_of(outfit_now)
        log("时期: %s (outfit=%s, 手动=%s)" % (persona_ctx.PERIOD_LABELS.get(period, period),
                                              outfit_now[:20], period_req or "auto"))

        # 上下文预算：超过阈值就切成「记忆书 + 最近一段原文」
        msgs, mem_note = _memory_context(msgs, bool(cc))

        # ---- 调试面板（#13）：这一轮 system 花在哪一段、送了多少条 ----
        # 只记字数和估算 token，不记正文（面板不该变成聊天记录查看器）
        _seg = {"msgs_total": len(raw_msgs), "msgs_sent": len(msgs),
                "mem_note": len(mem_note or ""),
                "mem_trimmed": len(msgs) < len(raw_msgs)}

        wb_ctx, wb_names = persona_ctx.worldbook_context(msgs, period=period)
        system = persona_ctx.persona_text(raw_msgs, period=period)
        _seg["persona"] = len(system)

        # system 的拼装顺序（措辞必须分开，否则模型会把设定和"这次聊过的事"混一起）：
        #   人设 → 常驻记忆书（角色固定设定）→ 世界书（设定）→ 对话记忆书（自动摘要）
        #   后面还有：剧本检索（原作片段）
        try:
            mem_extra = char_res.memory_text()
            _seg["memory_extra"] = len(mem_extra or "")
            if mem_extra:
                system = system + (
                    "\n\n【你记得的旧事（角色设定的一部分，事先记好的，不是这轮对话里发生的事；"
                    "用你自己的口气提起，不要照抄原文）】\n" + mem_extra)
            wb_extra = char_res.worldbook_text()
            _seg["wb_extra"] = len(wb_extra or "")
            if wb_extra:
                system = system + (
                    "\n\n【设定补充（用户整理好的资料，只作参考，不要整段复述）】\n"
                    + wb_extra)
        except Exception as e:
            log("角色资源读取失败: %s" % e)

        if wb_ctx:
            system = system + "\n\n" + wb_ctx
        _seg["worldbook"] = len(wb_ctx or "")
        _seg["wb_names"] = (wb_names or [])[:8]
        if mem_note:
            system = system + "\n\n" + mem_note
        _seg["mem_note"] = len(mem_note or "")

        # 剧本检索: 找出和这句话相关的原作片段, 作为"想起来的事"而不是台词。
        # 和世界书分开写：世界书是「设定」，这里是「原作里真的发生过什么」。
        try:
            if STORY is not None and req.get("memory") and STORY.enabled():
                last_user = ""
                for m in reversed(msgs):
                    if m.get("role") == "user":
                        last_user = m.get("content") or ""
                        break
                mem = STORY.memory_context(last_user, k=2, max_chars=900)
                _seg["story"] = len(mem or "")
                if mem:
                    system = system + (
                        "\n\n【原作里发生过的片段（资料，不是这轮对话的内容，也不是你的台词）】\n"
                        + mem
                        + "\n（这些是以前真实发生过的事。只在聊天自然提及时，用你自己的口气带一句；"
                          "不要照抄原文，不要整段复述，不要把它说成刚刚发生的事。）")
                    log("story_rag 命中 %d 字（问：%s）" % (len(mem), last_user[:20]))
        except Exception as e:
            log("story_rag 失败: %s" % e)

        try:
            _sp = characters.sprite_index(os.path.join(ASSETS_DIR, "sprites"))
            _outfit_names = list((_sp.get("outfits") or {}).keys())
            outfit_hint = "、".join(_outfit_names) if _outfit_names else "（按当前角色立绘）"
        except Exception:
            outfit_hint = "（按当前角色立绘）"
        _before_tail = len(system)
        if cc:
            # 云端：人设末尾补语言/格式约束，前面插 few-shot
            # 【场景】的地点表由素材目录（assets/cg/index.json）生成，加了新背景图不用改这里
            system = system + (
                "\n\n【语言】无论对方用什么语言说话，你都只用日语回答。"
                + scene_cg.prompt_hint() +
                "\n【服装】只有明确换了一套衣服时才输出 <outfit>衣服名</outfit>："
                + outfit_hint +
                "平时绝对不要输出。"
                "\n【情绪】在回复最前面输出一个情绪标记，格式 <emotion>情绪</emotion>，"
                "只能从这些里选：calm(平静) soft(温柔) 毒舌 撒娇 哭腔 调侃吐槽 问句。"
                "标记只能是开头那一个，正文里不要再出现。"
                "\n【格式】只输出你要说的话。如果有动作或表情，必须写成 "
                "<action>（…）</action> 放在台词前面，不允许出现没有标签的描写句。")
        _seg["tail"] = len(system) - _before_tail
        _few = fewshot_msgs() if cc else []
        payload = {
            "model": model,
            "messages": ([{"role": "system", "content": system}] + _few + msgs),
            "stream": False,
            "max_tokens": 400 if cc else 260,
        }
        if not cc:
            payload["reasoning_effort"] = "none"
        if cc and ("pro" in model or "deepseek" in (base_url or "").lower() or "deepseek" in (model or "").lower()):
            payload["thinking"] = {"type": "disabled"}
            payload["reasoning_effort"] = "none"
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

            # 场景：把 <scene> 的地点/时间对上素材里的背景图（匹配逻辑在 scene_cg.py）
            bg_hit = {}
            if scene_now:
                try:
                    bg_hit = scene_cg.match(scene_now, prev_bg)
                except Exception as e:
                    log("场景匹配失败: %s" % e)
                if not bg_hit:
                    log("场景没匹配上：%r（当前背景 %r）" % (scene_now, prev_bg))
            diag.note("scene", query=scene_now[:24], id=bg_hit.get("id", ""),
                      place=bg_hit.get("place", ""), time=bg_hit.get("time", ""),
                      score=bg_hit.get("score"))

            _ms = int((time.time() - t0) * 1000)
            # 调试面板：这一轮的提示词分段 / token 估算 / 耗时 / 用量（只记数字和标签）
            try:
                _tok = {"system": diag.token_est(system),
                        "msgs": sum(diag.token_est(m.get("content") or "") + 4 for m in msgs),
                        "fewshot": sum(diag.token_est(m.get("content") or "") + 4 for m in _few)}
                diag.round_record(
                    model=model, tier=("cloud" if cc else "local"), period=period,
                    stage=(persona_stage.debug_state() or {}).get("stage"),
                    seg=_seg, tokens=_tok,
                    usage={k: _uinfo.get(k) for k in ("tokens", "in", "out", "cost") if k in (_uinfo or {})},
                    scene={"id": bg_hit.get("id", ""), "score": bg_hit.get("score")},
                    emotion=emo, outfit=(outfit_now or "")[:16],
                    reply_chars=len(reply or ""), ms=_ms)
            except Exception as e:
                log("调试账本写入失败（不影响对话）: %s" % e)

            self._json({"reply": reply, "reply_zh": reply_zh, "thinking": think,
                        "action": action, "action_zh": action_zh,
                        "emotion": emo,
                        "scene": scene_now, "outfit": outfit_now,
                        "bg": bg_hit.get("id", ""),
                        "period": period,
                        "usage": _uinfo,
                        "model": model,
                        "ms": _ms,
                        "worldbook": wb_names})
        except urllib.error.HTTPError as e:
            diag.count("chat.error")
            self._json({"error": "HTTP %s %s" % (e.code, e.read().decode("utf-8", "replace")[:200])})
        except Exception as e:
            diag.count("chat.error")
            self._json({"error": "连不上 Ollama（%s），请先启动 Ollama" % e})
