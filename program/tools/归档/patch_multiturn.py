# -*- coding: utf-8 -*-
"""把 train_qlora.py 的 encode 改成支持多轮:
- 目标 = 最后一条 assistant
- 前文 = 它之前的所有消息(按原顺序保留)
- 只对最后那条 assistant 计算 loss
"""
P = r"E:\IDM下载目录\DSH工作产生文件\WA2-Kazusa-Bot\train\train_qlora.py"
s = open(P, encoding="utf-8").read()

old = '''    def encode(ex):
        msgs = ex["messages"]
        # 系统 + 用户 作为 prompt, assistant 作为要学的回答
        prompt_msgs = [m for m in msgs if m["role"] != "assistant"]
        short_sys = cfg.get("train_system")
        if short_sys:
            prompt_msgs = [{"role": "system", "content": short_sys}] + \\
                          [m for m in prompt_msgs if m["role"] != "system"]
        ans = [m["content"] for m in msgs if m["role"] == "assistant"][0]
        prompt_text = tok.apply_chat_template(prompt_msgs, tokenize=False,
                                              add_generation_prompt=True)
        full_text = prompt_text + ans + (tok.eos_token or "")
        p_ids = tok(prompt_text, add_special_tokens=False)["input_ids"]
        f_ids = tok(full_text, add_special_tokens=False)["input_ids"][:max_len]
        labels = list(f_ids)
        for i in range(min(len(p_ids), len(labels))):
            labels[i] = -100
        return {"input_ids": f_ids, "labels": labels,
                "attention_mask": [1] * len(f_ids)}'''

new = '''    def encode(ex):
        msgs = list(ex["messages"])
        short_sys = cfg.get("train_system")
        if short_sys and msgs and msgs[0]["role"] == "system":
            msgs[0] = {"role": "system", "content": short_sys}
        # 目标 = 最后一条 assistant; 之前全部作为前文(保留顺序)
        if not msgs or msgs[-1]["role"] != "assistant":
            return {"input_ids": [], "labels": [], "attention_mask": []}
        ans = msgs[-1]["content"]
        prompt_msgs = msgs[:-1]
        prompt_text = tok.apply_chat_template(prompt_msgs, tokenize=False,
                                              add_generation_prompt=True)
        full_text = prompt_text + ans + (tok.eos_token or "")
        p_ids = tok(prompt_text, add_special_tokens=False)["input_ids"]
        f_ids = tok(full_text, add_special_tokens=False)["input_ids"]
        # 前文过长时, 从左侧裁剪, 保证回答完整保留
        if len(f_ids) > max_len:
            cut = len(f_ids) - max_len
            f_ids = f_ids[cut:]
            p_ids = p_ids[cut:] if len(p_ids) > cut else []
        labels = list(f_ids)
        for i in range(min(len(p_ids), len(labels))):
            labels[i] = -100
        return {"input_ids": f_ids, "labels": labels,
                "attention_mask": [1] * len(f_ids)}'''

assert old in s, "未匹配 encode"
s = s.replace(old, new, 1)
open(P, "w", encoding="utf-8").write(s)
print("train_qlora.py 已支持多轮样本")
import ast
ast.parse(open(P, encoding="utf-8").read())
print("语法 OK")
