# -*- coding: utf-8 -*-
"""把界面里的**固定文案**预先渲染成 PNG，当 UI 素材用。

为什么不实时渲染：
    每次 /api/text 都要走一遍字模渲染，图片从空到有会闪一下；
    而这些文案永远不变，烤成静态图后前端直接 <img src> 加载，零延迟、无闪烁。

用法：
    python tools/bake_ui_text.py            # 全部重烤
    python tools/bake_ui_text.py --list     # 只看清单
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "src")
OUT = os.path.join(BASE, "res", "assets", "ui", "text")

sys.path.insert(0, SRC)

# 文案清单：key -> (文字, 字号, 是否描边, 染色)
# 说明：字号与界面里 uitext 实际用的值一致；描边只给"叠在画面上的字"开
ITEMS = {
    # ---- 模型管理 ----
    "mgr_chat":     ("聊天模型", 12, True, None),
    "mgr_voice":    ("语音模型", 12, True, None),
    "mgr_mt":       ("翻译模型", 12, True, None),
    "mgr_endpoint": ("端点", 11, True, None),
    "mgr_apikey":   ("API 密钥", 11, True, None),
    "mgr_model":    ("模型名称", 11, True, None),
    "mgr_switch":   ("切换模型", 11, True, None),
    "mgr_connect":  ("连接", 11, True, None),
    "mgr_ok":       ("已连接", 11, True, None),
    "mgr_fail":     ("连接失败", 11, True, None),

    # ---- 存档 / 读档提示 ----
    "save_done":    ("存档已保存", 12, True, None),
    "save_over":    ("覆盖这个存档吗？", 12, True, None),
    "save_yes":     ("是", 12, True, None),
    "save_no":      ("否", 12, True, None),
    "load_empty":   ("这个槽位没有存档", 12, True, None),
    "save_short":   ("对话不足两条不能存档", 12, True, None),

    # ---- 回想 / 输入框 ----
    "log_ph":       ("对和纱说点什么…（Enter 发送）", 13, True, None),
    "log_act_on":   ("动作：开", 11, True, None),
    "log_act_off":  ("动作：关", 11, True, None),
    "log_send":     ("发送", 11, True, None),
}


def main():
    if "--list" in sys.argv:
        for k, (t, fs, stroke, _c) in ITEMS.items():
            print("%-14s %s（%dpx）" % (k, t, fs))
        return

    import sub_render
    os.makedirs(OUT, exist_ok=True)
    made = 0
    for key, (text, fs, stroke, color) in ITEMS.items():
        path = os.path.join(OUT, key + ".png")
        img = sub_render.render_block(text, maxw=2000, stroke=bool(stroke),
                                      margin=None if stroke else 0, color=color)
        img.save(path)
        made += 1
        print("%-14s %-22s %dx%d" % (key, text, img.width, img.height))
    print("\n共生成 %d 张 → %s" % (made, OUT))


if __name__ == "__main__":
    main()
