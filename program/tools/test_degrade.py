# -*- coding: utf-8 -*-
"""降级类自测（#11：核心 / 边界 / 降级三类里的「降级」，不联网、不开界面）。

跑法：
    cd program
    build_env/venv/Scripts/python.exe tools/test_degrade.py

验的是「需求没满足时不崩、还能继续玩」：
  1. 语音未命中：一条参考音频都没有 → 不合成、返回 None（前端只显示文字）
  2. 响度算不出来：坏 wav / 未知格式 → 原样放行，不抛
  3. 场景匹配失败：没有素材目录 / 目录里没这张 → 返回 {}，prompt_hint 仍给得出话
  4. 原作检索不可用：没索引 / 角色关掉了检索 → 返回空串，不抛
  5. 关系判定超时 / 返回怪东西：保留原阶段，不崩，下一轮还能再判
"""
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROGRAM, "src"))

_TMP = tempfile.mkdtemp(prefix="wa2_degrade_test_")
os.environ["WA2_CACHE_DIR"] = _TMP
os.environ["WA2_SESS_DIR"] = os.path.join(_TMP, "sessions")

import audio_gain    # noqa: E402
import persona_stage  # noqa: E402
import scene_cg     # noqa: E402
import story_rag    # noqa: E402
import tts_client   # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:200]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def main():
    # ------------------------------------------------ 1 语音未命中（没有参考音频）
    tts_client._IMPORTED = {"global": [], "by_emo": {}}
    tts_client._ref_cache = {}
    tts_client.load_refs = lambda: {}
    tts_client._refs_sig = tts_client._char_voice_sig()
    ref = tts_client.pick_ref("neutral")
    check("没有参考音频：pick_ref 返回 (None, '')", ref == (None, ""), ref)
    check("没有参考音频：任意情绪也不炸", tts_client.pick_ref("不存在的情绪") == (None, ""))
    check("未就绪时 synthesize 返回 None（不抛）", tts_client.synthesize("测试一句") is None)
    st = tts_client.status()
    check("status 结构没变坏", isinstance(st, dict) and "ready" in st and "available" in st, st)

    # ------------------------------------------------ 2 响度算不出来 → 原样放行
    junk = b"NOT A WAV" * 100
    info = audio_gain.probe(junk)
    check("坏 wav：probe 标 not-wav、增益 0", info["format"] == "not-wav" and info["gain_db"] == 0.0, info)
    out, info2 = audio_gain.apply(junk)
    check("坏 wav：apply 原样返回", out == junk and info2["applied"] is False)
    check("空字节也不炸", audio_gain.apply(b"")[0] == b"")

    # ------------------------------------------------ 3 场景匹配失败
    empty = tempfile.mkdtemp(prefix="wa2_no_assets_")
    scene_cg.set_assets_dir(empty)
    check("没有素材目录：match 返回 {}", scene_cg.match("教室（白天）", "") == {})
    hint = scene_cg.prompt_hint()
    check("没有素材目录：prompt_hint 仍返回字符串", isinstance(hint, str) and len(hint) > 0, hint[:40])
    check("prompt_hint 不会堆出空括号", "【场景】" in hint, hint[:40])

    # ------------------------------------------------ 4 原作检索不可用
    story_rag._CACHE = {}
    story_rag.GLOBAL_INDEX = os.path.join(_TMP, "没有这个索引.json.gz")
    check("没有索引：memory_context 返回空串",
          story_rag.memory_context("今天天气不错") == "")
    check("没有索引：last_hits 是合法空值",
          isinstance(story_rag.last_hits().get("hits"), list), story_rag.last_hits())
    check("没有索引：cached_blocks 返回 0", story_rag.cached_blocks() == 0, story_rag.cached_blocks())

    # ------------------------------------------------ 5 关系判定超时 / 怪输出
    persona_stage.reset()
    msgs = []
    for i in range(6):
        msgs.append({"role": "user", "content": "在吗"})
        msgs.append({"role": "assistant", "content": "「在的」"})

    def boom(system, user):
        raise TimeoutError("模拟云端超时")

    persona_stage.set_llm(boom)
    before = persona_stage.debug_state()
    got = persona_stage.classify_now(msgs)
    after = persona_stage.debug_state()
    check("判定超时：保留原阶段、不抛", got == before["stage"], (got, before))
    check("判定超时：轮数仍然记上了", after["rounds"] >= before["rounds"], (before, after))

    persona_stage.set_llm(lambda s, u: "我不知道")     # 没有数字
    check("返回怪东西：解析不到数字就保留原阶段",
          persona_stage.classify_now(msgs) == after["stage"])

    persona_stage.set_llm(lambda s, u: "3")            # 正常：只升不降
    check("正常返回数字：阶段升到 3", persona_stage.classify_now(msgs) == 3)
    persona_stage.set_llm(lambda s, u: "1")            # 想降回去：不许
    check("只升不降：返回 1 也不降", persona_stage.classify_now(msgs) == 3)

    persona_stage.set_llm(None)
    persona_stage.reset()
    marriage = [{"role": "user", "content": "我们结婚吧"},
                {"role": "assistant", "content": "「……嗯」"}]
    check("明确提到结婚：本地关键词直接封顶 4",
          persona_stage.current(marriage) == 4, persona_stage.current(marriage))
    check("封顶后 debug_state 也报 4", persona_stage.debug_state()["stage"] == 4)

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), " / ".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
