# -*- coding: utf-8 -*-
"""/api/chat 的实现，从 main.py 拆出；逻辑未改动。"""

import json, os, time
import char_res
import characters
import diag
import perf
import perfcfg
import persona_ctx
import persona_stage
import scene_cg
import standing
import text_parse as _tp
from text_parse import split_bilingual
import tts_client

# 关键参数（#12：以前散在函数体里的数字，集中在这里；表见 other/docs/参数与指标.md）
MAX_TOKENS_CLOUD = 400       # 云端一次回复的上限
MAX_TOKENS_LOCAL = 260       # 本地小模型回复更短
CHAT_TIMEOUT_S = 300         # 等云端回复的超时
STORY_K = 2                  # 原作检索注入几块
STORY_MAX_CHARS = 900        # 原作检索最多注入多少字


def performance_hints(cc, outfit_hint=""):
    """人设末尾的演出标签提示（场景 / 服装 / 情绪 / 动作；云端另加语言 + 双语）。

    **云端和本地都要加**：以前整段挂在 `if cc:` 下面，本地模型（Ollama）
    压根不知道要输出 <scene>/<outfit>/<emotion>，于是场景 CG、立绘、BGM
    全都不会变（2026-11-06 用户反馈「基本没自动换过」）。
    本地不加的只有「只用日语」和「双语输出」：小模型做不好双语，
    硬要求反而写坏，中文由 translate.py 兜底。
    单独提出来是为了能测（见 tools/test_chat_hints.py）。
    """
    s = (scene_cg.prompt_hint() +
         "\n【服装】只有明确换了一套衣服时才输出 <outfit>衣服名</outfit>："
         + (outfit_hint or "（按当前角色立绘）") +
         "平时绝对不要输出。"
         "\n【情绪】在回复最前面输出一个情绪标记，格式 <emotion>情绪</emotion>，"
         "只能从这些里选：calm(平静) soft(温柔) 毒舌 撒娇 哭腔 调侃吐槽 问句。"
         "按这句台词的实际语气挑，只有心情真的平复时才用 calm；"
         "标记只能是开头那一个，正文里不要再出现。"
         "\n【格式】只输出你要说的话。如果有动作或表情，必须写成 "
         "<action>（…）</action> 放在台词前面，不允许出现没有标签的描写句。")
    if cc:
        s += ("\n\n【语言】无论对方用什么语言说话，你都只用日语回答。"
              "\n【双语】台词必须给两份，紧跟在一起：<ja>日语原句</ja><zh>对应的中文</zh>。"
              "<zh> 不是另一个人写的翻译，就是你自己那句话的意思，"
              "所以要和 <ja> 对得上（不许改口、不许省略、不许加戏），中文要口语、带情绪。"
              '<action> 里的描写也用中文写。例：'
              '<emotion>毒舌</emotion><action>（别过脸）</action>'
              '<ja>「べ、別に。あんたのためじゃないから」</ja>'
              '<zh>「才、才不是。不是为你才做的」</zh>')
    return s


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

        # 演出 / 切片规则（#19）：每角色的 persona_slices.json，缺了就是默认值
        try:
            _sl = perfcfg.slices()
        except Exception as e:
            log("切片配置读取失败（用默认值）: %s" % e)
            _sl = dict(perfcfg.DEFAULTS_SLICES)

        wb_ctx, wb_names = persona_ctx.worldbook_context(
            msgs, period=period,
            max_entries=_sl["worldbook_entries"], max_chars=_sl["worldbook_chars"])
        system = persona_ctx.persona_text(raw_msgs, period=period)
        _seg["persona"] = len(system)

        # system 的拼装顺序（措辞必须分开，否则模型会把设定和"这次聊过的事"混一起）：
        #   人设 → 常驻记忆书（角色固定设定）→ 世界书（设定）→ 对话记忆书（自动摘要）
        #   后面还有：剧本检索（原作片段）
        try:
            # 常驻记忆书（#3）：两段化之后是「固定设定 + 关系摘要」；没 standing.json 就回落老文本
            mem_extra = standing.text()
            # 切片配置（#19）可以再压一道上限
            if mem_extra and _sl.get("memory_max_chars"):
                mem_extra = mem_extra[:_sl["memory_max_chars"]]
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
                _prev_users = []
                for m in reversed(msgs):
                    if m.get("role") == "user":
                        _u = m.get("content") or ""
                        if not last_user:
                            last_user = _u
                        elif len(_prev_users) < 2:
                            _prev_users.append(_u)
                        if len(_prev_users) >= 2:
                            break
                # 情境/时期加权：现在是 coda 就别拿 IC 的教室段子；
                # 这句像亲密/调情/拌嘴，就优先取同情境的片段（语气才对）。
                _sit = STORY.situation_of(last_user + " " + " ".join(_prev_users), loose=True)
                _per = (period or "").lower() or None
                mem = STORY.memory_context(last_user, k=_sl["story_k"],
                                           max_chars=_sl["story_max_chars"],
                                           period=_per, tags=_sit)
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
        # 演出标签（场景 / 服装 / 情绪 / 动作）：云端和本地都要，见 performance_hints
        system = system + performance_hints(cc, outfit_hint)
        _seg["tail"] = len(system) - _before_tail
        _few = fewshot_msgs() if cc else []
        payload = {
            "model": model,
            "messages": ([{"role": "system", "content": system}] + _few + msgs),
            "stream": False,
            "max_tokens": MAX_TOKENS_CLOUD if cc else MAX_TOKENS_LOCAL,
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
            with urllib.request.urlopen(rq, timeout=CHAT_TIMEOUT_S) as r:
                d = json.loads(r.read().decode("utf-8"))
            raw = (d["choices"][0]["message"].get("content") or "").strip()
            _uinfo = _record_usage(model, d.get("usage") or {})
            raw, emo = split_emotion(raw)
            # 情绪标签是模型该给的；它经常偷懒不写（实测 5 句里 3 句没有），
            # 以前没标签直接当 calm，参考音频就永远停在同一组。这里让偷懒看得见：
            #   source=tag      模型自己写了
            #   source=inferred 按台词形态猜的（可能猜错，日志里能对账）
            #   source=default  真没线索，用 calm
            try:
                _src = _tp.LAST_EMO_SOURCE
                if _src != "tag":
                    log("情绪标签%s：%s（模型没写 <emotion>）"
                        % ("推断" if _src == "inferred" else "缺失", emo))
            except Exception:
                pass
            raw, scene_now, outfit_now = split_scene(raw)
            acts, raw = split_action(raw)
            # 模型自己给的双语：<ja>日语</ja><zh>中文</zh>（比事后再翻译准，还省一次往返）
            raw, _ja, _zh_model = split_bilingual(raw)
            reply, think = split_thinking(raw)
            if _ja:                      # 有 <ja> 就以它为准（那是模型的原句）
                reply = _ja
            action = " ".join(a for a in acts if a).strip()
            # 游戏里角色台词一律用「」包起来，由程序统一处理，不让模型自己加
            _r = (reply or "").strip()
            if _r:
                _r = _r.strip("「」『』")
                reply = "「" + _r + "」"

            # 中文：优先用模型自己写的那句；没写 / 不像中文才回落翻译层
            reply_zh = ""
            action_zh = ""
            try:
                _z = (_zh_model or "").strip().strip("「」『』")
                if _z and _tp.looks_zh(_z):
                    reply_zh = _z
                elif any("\u3040" <= c <= "\u30ff" for c in reply):
                    # 走统一翻译层：云端优先、本地兜底，人名过术语表
                    # （原来只调本地 Hy-MT2，はるき 会被译成「春树」）
                    import translate as _tr
                    reply_zh = _tr.to_zh(_r)
                if action:
                    # 动作描写模型一般直接给中文；是日语才翻
                    if _tp.looks_zh(action) or not any("\u3040" <= c <= "\u30ff" for c in action):
                        action_zh = action
                    else:
                        import translate as _tr2
                        action_zh = _tr2.to_zh(action)
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
            _stage = (persona_stage.debug_state() or {}).get("stage")
            # 调试面板：这一轮的提示词分段 / token 估算 / 耗时 / 用量（只记数字和标签）
            try:
                _tok = {"system": diag.token_est(system),
                        "msgs": sum(diag.token_est(m.get("content") or "") + 4 for m in msgs),
                        "fewshot": sum(diag.token_est(m.get("content") or "") + 4 for m in _few)}
                diag.round_record(
                    model=model, tier=("cloud" if cc else "local"), period=period,
                    stage=_stage,
                    seg=_seg, tokens=_tok,
                    usage={k: _uinfo.get(k) for k in ("tokens", "in", "out", "cost") if k in (_uinfo or {})},
                    scene={"id": bg_hit.get("id", ""), "score": bg_hit.get("score")},
                    emotion=emo, outfit=(outfit_now or "")[:16],
                    reply_chars=len(reply or ""), ms=_ms)
            except Exception as e:
                log("调试账本写入失败（不影响对话）: %s" % e)
            # 常驻记忆书（#3）：关系阶段变了才在后台刷一次关系摘要（每个阶段最多一次）
            try:
                standing.note(_stage, raw_msgs)
            except Exception:
                pass
            # 性能采样（#14）：每 N 轮记一行，后台线程写，不占这一轮
            try:
                perf.maybe()
            except Exception:
                pass

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
