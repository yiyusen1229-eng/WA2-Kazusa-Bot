# -*- coding: utf-8 -*-
"""回复文本的纯函数工具：拆标签、清日文。

这些函数不依赖运行时状态（没有全局、不碰文件），所以单独一层，
改标签规则、加新标签只动这里，不用读 main.py。
"""

import re

# <action>…</action>
ACTION_RE = re.compile(r"<action>\s*(.*?)\s*</action>", re.S)

# 没标签时的兜底情绪（也是“什么线索都没有”时的结果）
EMO_DEFAULT = "calm"

# 最近一次 split_emotion 的情绪是怎么来的：tag（模型写了）/ inferred（按台词猜的）/ default（真没线索）
# api_chat 拿它写日志：模型偷懒的频率要看得见，别再静默 at 成 calm。
LAST_EMO_SOURCE = "default"

# 按台词形态猜情绪：只认很明确的线索，猜不准就回 default（宁可 calm，也别乱选参考音频）。
# 顺序有意义：先看疑问句形态，再看哭 / 毒舌 / 撒娇 / 温柔的字眼。
_EMO_HINTS = (
    ("哭腔", re.compile(r"涙|泣|ごめん|ひどい|苦しい|つらい|寂しい|さみしい")),
    ("毒舌", re.compile(r"ばか|バカ|あほ|アホ|うるさい|ウザ|きもい|ムカつく|嫌い|っ嫌")),
    ("撒娇", re.compile(r"お願い|やだ|いやだ|ずるい|ねえ|だって|別に|べつに|〜して|してよ")),
    ("soft", re.compile(r"ありがと|うれし|嬉し|好き|すき|大好き|よかった|助かった|優し")),
)
_QUESTION_TAIL = re.compile(r"(か|の|かな|のよ|でしょ|どう|なの)[」』\s]*$")

# 「明显是在难过」的强线索：模型偶尔把这种句子标成 calm / 毒舌，声音会明显不对。
# 只在这两种标签上纠偏，别的标签一律尊重模型。
_SAD_STRONG = re.compile(r"涙|泣|ごめん|どうせ|いらない|もういい|寂しい|さみしい|さよなら|バイバイ")
_SAD_OVERRIDABLE = ("calm", "平静", "毒舌")


def infer_emotion(text):
    """没有 <emotion> 标签时，按台词猜一个情绪；猜不出来返回 ""（调用方回 default）。

    为什么要有这层：模型经常不写标签（实测明显生气 / 难过 / 温柔的句子里 3/5 都没写），
    而以前没标签直接当 calm，结果参考音频永远用同一组，听起来毫无起伏。
    这里只认**明确**的线索，宁可漏判也不乱判。
    """
    t = (text or "").strip()
    if not t:
        return ""
    if "？" in t or "?" in t or _QUESTION_TAIL.search(t):
        return "问句"
    for emo, rx in _EMO_HINTS:
        if rx.search(t):
            return emo
    return ""


def split_emotion(text):
    """取出 <emotion>xxx</emotion>，返回 (正文, 情绪)。

    模型偶尔把标签拼错（`</emomotion>`），以前只清 `emotion` 这两个词，
    残留的标签会直接出现在台词里。所以开标签用 `<emotion>`、闭标签放宽到 `emo…`。

    没标签时不再一律 calm：先按台词形态猜（`infer_emotion`），实在没线索才用
    `EMO_DEFAULT`；怎么来的记在 `LAST_EMO_SOURCE` 里。
    """
    global LAST_EMO_SOURCE
    if not text:
        LAST_EMO_SOURCE = "default"
        return text, EMO_DEFAULT
    m = re.search(r"<emotion>\s*([^<\n]{1,20})\s*</?\s*emo[a-z]*\s*>", text, re.I)
    emo = ""
    if m:
        emo = m.group(1).strip()
        text = (text[:m.start()] + text[m.end():]).strip()
    # 兼容模型把标记写在其它位置 / 拼错 / 多次出现
    text = re.sub(r"</?\s*emo[a-z]*[^>]*>", "", text, flags=re.I).strip()
    if emo:
        # 模型自己写了标签就用它的；只有「明显难过却标成 calm/毒舌」这种硬矛盾才纠一下，
        # 不然一句哽咽的台词会被念得又冷又冲（实测模型会把难过句标成毒舌）。
        if emo in _SAD_OVERRIDABLE and _SAD_STRONG.search(text):
            LAST_EMO_SOURCE = "override"
            return text, "哭腔"
        LAST_EMO_SOURCE = "tag"
        return text, emo
    guessed = infer_emotion(text)
    if guessed:
        LAST_EMO_SOURCE = "inferred"
        return text, guessed
    LAST_EMO_SOURCE = "default"
    return text, EMO_DEFAULT


def split_scene(text):
    """取出 <scene>地点</scene> 与 <outfit>衣服</outfit>，返回 (正文, 场景, 服装)。

    场景名放宽到 40 字：素材里的地名带括号标签（如「和纱家别墅（客厅）」），
    模型偶尔会整串抄过来，别被卡掉。
    """
    scene = ""
    outfit = ""
    if not text:
        return text, scene, outfit
    m = re.search(r"<scene>\s*([^<]{1,40})\s*</scene>", text)
    if m:
        scene = m.group(1).strip()
        text = text[:m.start()] + text[m.end():]
    m = re.search(r"<outfit>\s*([^<]{1,12})\s*</outfit>", text)
    if m:
        outfit = m.group(1).strip()
        text = text[:m.start()] + text[m.end():]
    text = re.sub(r"</?(scene|outfit)[^>]*>", "", text).strip()
    return text, scene, outfit


_JA_BLOCK = re.compile(r"<\s*(?:ja|jp|jpn|日本语|日语)\s*>\s*(.*?)\s*<\s*/\s*(?:ja|jp|jpn|日本语|日语)\s*>", re.S)
_ZH_BLOCK = re.compile(r"<\s*(?:zh|cn|chs|中文|汉语)\s*>\s*(.*?)\s*<\s*/\s*(?:zh|cn|chs|中文|汉语)\s*>", re.S)
_BI_LEFTOVER = re.compile(r"</?\s*(?:ja|jp|jpn|zh|cn|chs|日本语|日语|中文|汉语)[^>]*>", re.I)


def split_bilingual(text):
    """拆 <ja>日语</ja><zh>中文</zh> 双语块，返回 (剩下的文本, 日语, 中文)。

    为什么要这个：让**对话模型自己**把中文一起给出来——它知道这句话是什么意思，
    比事后再找一个翻译模型（经常把人名译成「春树」、中译日满口敬语）准得多，
    还省掉一次往返。模型没给就当没有，调用方回落到翻译层，不影响玩。

    标签写坏 / 只用一种（`<jp>`、`<中文>`）也认；没有块的句子原样留在 rest 里。
    """
    if not text:
        return text, "", ""
    ja = zh = ""
    m = _JA_BLOCK.search(text)
    if m:
        ja = m.group(1).strip()
        text = text[:m.start()] + text[m.end():]
    m = _ZH_BLOCK.search(text)
    if m:
        zh = m.group(1).strip()
        text = text[:m.start()] + text[m.end():]
    text = _BI_LEFTOVER.sub("", text).strip()
    return text, ja, zh


def looks_zh(x):
    """像中文吗：有汉字、几乎没有假名（用来判断模型给的是不是真的中文译文）"""
    t = x or ""
    cjk = sum(1 for c in t if 0x4E00 <= ord(c) <= 0x9FFF)
    kana = sum(1 for c in t if 0x3040 <= ord(c) <= 0x30FF)
    return cjk >= 2 and kana < 2


def split_action(text):
    """把 <action> 从回复里拆出来，返回 (action 列表, 纯台词)"""
    acts = ACTION_RE.findall(text or "")
    rest = ACTION_RE.sub("", text or "").strip()
    return acts, rest


def split_thinking(text):
    """把 <thinking>…</thinking> 从回复里拆出来，返回 (正文, 思考)"""
    m = re.search(r"<thinking>(.*?)</thinking>", text or "", re.S)
    if not m:
        return (text or "").strip(), ""
    inner = m.group(1).strip()
    rest = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.S).strip()
    return rest, inner


def ja_clean(x):
    """只留第一行，去掉假名/汉字/日文标点以外的字符，并截掉解释性尾巴。

    **不按句号截断**：以前这里有「句号后还有解释就只取第一句」，
    结果两句台词被砍成一句半 —— 字幕显示两句、语音只念半句（用户实测反馈）。
    解释性尾巴交给下面的停止词处理。
    """
    # 注意：以前写成 split("\\n")（字面反斜杠+n），真换行根本切不开，
    # 多行回复会被后面的字符过滤拼成一句。这里按真换行取第一行。
    x = (x or "").replace("\r", "").split("\n")[0].strip()
    # 只留「解释性」的停止词；「，」「,」 是句中停顿，不能拿来截断，
    # 否则正常的多句台词也会被砍掉后半句。
    for stop in ("翻訳", "場合は", "注意", "つまり", "：", ":"):
        i = x.find(stop)
        if i > 0:
            x = x[:i]

    out = []
    for c in x:
        o = ord(c)
        if (0x3040 <= o <= 0x30FF) or (0x4E00 <= o <= 0x9FFF) or \
           (0x3000 <= o <= 0x303F) or (0xFF00 <= o <= 0xFF60) or c in "　 ー…":
            out.append(c)
    j = "".join(out).strip()
    # 人称修正: 和纱用「あたし」, 不用「俺/僕/わたし」
    for bad in ("俺", "僕", "わたし", "私"):
        j = j.replace(bad, "あたし")
    return j


def ja_ok(x):
    """至少两个假名才算“像日语”，防止把中文塞给 TTS。"""
    return sum(1 for c in x if 0x3040 <= ord(c) <= 0x30FF) >= 2
