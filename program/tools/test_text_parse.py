# -*- coding: utf-8 -*-
"""回复标签解析（text_parse.py）的自测（纯函数，不联网、不开界面）。

跑法：
    cd program
    build_env/venv/Scripts/python.exe tools/test_text_parse.py

验的是：
  1. <emotion> 正常拆出来；模型拼错闭标签（</emomotion>）也不能漏到台词里
  2. <scene> / <outfit> 拆出来；写坏的标签统一清掉
  3. <action> 可以多次出现
  4. <thinking> 整段拿走
  5. ja_clean：只留第一行、去解释尾巴、人称改「あたし」
  6. ja_ok：两个假名才算日语
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAM = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(PROGRAM, "src"))

import text_parse as T  # noqa: E402

FAILS = []


def check(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name +
          (("  " + str(extra)[:200]) if extra and not cond else ""))
    if not cond:
        FAILS.append(name)


def main():
    # 1) emotion
    body, emo = T.split_emotion("<emotion>smile</emotion>「おはよう」")
    check("正常 emotion 拆出来", body == "「おはよう」" and emo == "smile", (body, emo))
    body, emo = T.split_emotion("<emotion>问句</emomotion>「覚えてる」")
    check("拼错的闭标签也能拆", emo == "问句" and body == "「覚えてる」", (body, emo))
    body, emo = T.split_emotion("「やあ」</emomotion>")
    check("只有残留标签时清掉、不吞台词", body == "「やあ」" and emo == "calm", (body, emo))
    body, emo = T.split_emotion("「やあ」")
    check("没线索时还是 calm", emo == "calm" and body == "「やあ」" and
          T.LAST_EMO_SOURCE == "default", (body, emo, T.LAST_EMO_SOURCE))
    check("空输入不炸", T.split_emotion("") == ("", "calm"), T.split_emotion(""))
    # 没有标签时按台词形态猜（模型经常不写标签：实测 5 句里 3 句没有）
    body, emo = T.split_emotion("<emotion>问句</emotion>「覚えてる？」")
    check("模型写了标签就用标签", emo == "问句" and T.LAST_EMO_SOURCE == "tag",
          (emo, T.LAST_EMO_SOURCE))
    body, emo = T.split_emotion("「あんたなんか、ほんとに大っ嫌い！」")
    check("猜得出毒舌", emo == "毒舌" and T.LAST_EMO_SOURCE == "inferred", (emo, T.LAST_EMO_SOURCE))
    body, emo = T.split_emotion("<action>（目をそらす）</action>「べ、別に…ずるい」")
    check("猜得出撒娇", emo == "撒娇", (emo, T.LAST_EMO_SOURCE))
    body, emo = T.split_emotion("「…ごめん、ひどいこと言った」")
    check("猜得出哭腔", emo == "哭腔", (emo, T.LAST_EMO_SOURCE))
    body, emo = T.split_emotion("「ありがと…助かった」")
    check("猜得出温柔", emo == "soft", (emo, T.LAST_EMO_SOURCE))
    body, emo = T.split_emotion("「ねえ、それで？」")
    check("猜得出问句", emo == "问句", (emo, T.LAST_EMO_SOURCE))
    body, emo = T.split_emotion("「寒いな」")
    check("没线索的普通句子仍然是 calm", emo == "calm", (emo, T.LAST_EMO_SOURCE))
    check("推断只认明确线索（不乱猜）", T.infer_emotion("「うん」") == "",
          T.infer_emotion("「うん」"))
    body, emo = T.split_emotion("「べ、別に。あんたのためじゃないから」")
    check("别扭（別に）算撒娇", emo == "撒娇", (emo, T.LAST_EMO_SOURCE))
    # 硬矛盾纠偏：明显难过却标 calm/毒舌 → 哭腔（别的标签一律尊重模型）
    body, emo = T.split_emotion("<emotion>毒舌</emotion>「…もういい。どうせあたしなんて」")
    check("难过句被标毒舌 → 纠成哭腔", emo == "哭腔" and T.LAST_EMO_SOURCE == "override",
          (emo, T.LAST_EMO_SOURCE))
    body, emo = T.split_emotion("<emotion>calm</emotion>「ごめん…ひどいこと言った」")
    check("难过句被标 calm → 纠成哭腔", emo == "哭腔", (emo, T.LAST_EMO_SOURCE))
    body, emo = T.split_emotion("<emotion>毒舌</emotion>「ばか、うるさい」")
    check("真毒舌不被误纠", emo == "毒舌" and T.LAST_EMO_SOURCE == "tag",
          (emo, T.LAST_EMO_SOURCE))
    body, emo = T.split_emotion("<emotion>撒娇</emotion>「…もういい。どうせあたしなんて」")
    check("模型给的撒娇不被覆盖", emo == "撒娇", (emo, T.LAST_EMO_SOURCE))

    # 双语块（模型自己给中文，省掉一次翻译）
    rest, ja, zh = T.split_bilingual('<emotion>x</emotion><action>（别过脸）</action>'
                                     '<ja>「べ、別に」</ja><zh>「才、才不是」</zh>')
    check("双语块拆出 ja/zh", ja == "「べ、別に」" and zh == "「才、才不是」", (ja, zh))
    check("双语块不残留标签", "<ja>" not in rest and "<zh>" not in rest, rest)
    rest, ja, zh = T.split_bilingual("<jp>「やあ」</jp>")
    check("jp 标签也认", ja == "「やあ」" and zh == "", (ja, zh))
    rest, ja, zh = T.split_bilingual("<中文>「你好」</中文>")
    check("中文标签也认", ja == "" and zh == "「你好」", (ja, zh))
    rest, ja, zh = T.split_bilingual("「普通的句子」")
    check("没有双语块时原样留在 rest", rest == "「普通的句子」" and not ja and not zh, (rest, ja, zh))
    rest, ja, zh = T.split_bilingual("<ja>「片方だけ」</ja>")
    check("只有一种语言也不炸", ja == "「片方だけ」" and zh == "" and rest == "", (rest, ja, zh))
    check("像中文（有汉字、没假名）", T.looks_zh("「才不是呢」") is True)
    check("日语不算中文", T.looks_zh("「べ、別に」") is False)
    check("空白不算中文", T.looks_zh("") is False)

    # 2) scene / outfit
    body, sc, of = T.split_scene("<scene>第二音乐室</scene><outfit>冬季校服</outfit>「…」")
    check("scene/outfit 拆出来", sc == "第二音乐室" and of == "冬季校服" and body == "「…」",
          (body, sc, of))
    body, sc, of = T.split_scene("<scene>和纱家别墅（客厅）</scene>「…」")
    check("场景名允许括号标签", sc == "和纱家别墅（客厅）", sc)
    body, sc, of = T.split_scene("「…」</scene >")
    check("写坏的 scene 标签清掉", "</scene" not in body, body)

    # 3) action
    acts, rest = T.split_action("<action>叹气</action>「…」<action>转身</action>")
    check("action 可以多次出现", acts == ["叹气", "转身"], acts)
    check("action 不出现在台词里", "action" not in rest and rest == "「…」", rest)

    # 4) thinking
    rest, think = T.split_thinking("<thinking>想一想</thinking>「答え」")
    check("thinking 整段拿走", think == "想一想" and rest == "「答え」", (rest, think))
    rest, think = T.split_thinking("「答え」")
    check("没有 thinking 时正文原样", think == "" and rest == "「答え」", (rest, think))

    # 5) ja_clean
    check("只留第一行", T.ja_clean("「おはよう」\n第二行") == "「おはよう」", T.ja_clean("「おはよう」\n第二行"))
    check("砍掉解释尾巴", T.ja_clean("「やあ」翻訳：你好") == "「やあ」", T.ja_clean("「やあ」翻訳：你好"))
    check("人称改成あたし", "あたし" in T.ja_clean("私のピアノ"), T.ja_clean("私のピアノ"))
    check("去掉英文/数字", "abc" not in T.ja_clean("abc「やあ」123"), T.ja_clean("abc「やあ」123"))
    check("空输入返回空", T.ja_clean("") == "", repr(T.ja_clean("")))

    # 6) ja_ok
    check("两个假名算日语", T.ja_ok("「やあ」") is True)
    check("纯中文不算日语", T.ja_ok("你好啊") is False)
    check("一个假名不算", T.ja_ok("あ") is False)

    print()
    if FAILS:
        print("失败 %d 项：%s" % (len(FAILS), " / ".join(FAILS)))
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
