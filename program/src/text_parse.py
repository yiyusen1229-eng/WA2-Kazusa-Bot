# -*- coding: utf-8 -*-
"""回复文本的纯函数工具：拆标签、清日文。

这些函数不依赖运行时状态（没有全局、不碰文件），所以单独一层，
改标签规则、加新标签只动这里，不用读 main.py。
"""

import re

# <action>…</action>
ACTION_RE = re.compile(r"<action>\s*(.*?)\s*</action>", re.S)


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


def split_emotion(text):
    """取出 <emotion>xxx</emotion>，返回 (正文, 情绪)。没有标记时情绪为 calm。

    模型偶尔把标签拼错（`</emomotion>`），以前只清 `emotion` 这两个词，
    残留的标签会直接出现在台词里。所以开标签用 `<emotion>`、闭标签放宽到 `emo…`。
    """
    if not text:
        return text, "calm"
    m = re.search(r"<emotion>\s*([^<\n]{1,20})\s*</?\s*emo[a-z]*\s*>", text, re.I)
    emo = "calm"
    if m:
        emo = m.group(1).strip()
        text = (text[:m.start()] + text[m.end():]).strip()
    # 兼容模型把标记写在其它位置 / 拼错 / 多次出现
    text = re.sub(r"</?\s*emo[a-z]*[^>]*>", "", text, flags=re.I).strip()
    return text, emo


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
    """只留第一行，去掉假名/汉字/日文标点以外的字符，并截掉解释性尾巴。"""
    # 注意：以前写成 split("\\n")（字面反斜杠+n），真换行根本切不开，
    # 多行回复会被后面的字符过滤拼成一句。这里按真换行取第一行。
    x = (x or "").replace("\r", "").split("\n")[0].strip()
    for stop in ("翻訳", "場合は", "注意", "つまり", "：", ":", "，", ","):
        i = x.find(stop)
        if i > 0:
            x = x[:i]
    # 句号后还有解释的, 只取第一句
    if "。" in x[:-1]:
        x = x.split("。")[0] + "。"

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
