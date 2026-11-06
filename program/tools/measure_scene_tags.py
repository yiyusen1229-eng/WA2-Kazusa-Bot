# -*- coding: utf-8 -*-
"""量一量本地模型输出 <scene> 的命中率（改提示词前后各跑一次）。

用法：
    python tools/measure_scene_tags.py [轮数] [端口]
只读：不写存档。
"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PORT = sys.argv[2] if len(sys.argv) > 2 else "8794"
ROUNDS = int(sys.argv[1]) if len(sys.argv) > 1 else 5

# 都是「人已经到了某处」的说法，按规则应该给 <scene>
ARRIVE = [
    "（我们推门进了咖啡厅，暖气扑面而来）",
    "（两个人走进教室，放学后的教室空着）",
    "（到了车站前的路口，雪还在下）",
    "（一进家门就闻到了锅里的味道）",
    "（走进第二音乐室，钢琴盖是开着的）",
    "（穿过走廊，窗外已经黑透了）",
]
# 只是提议、还没到，按规则**不该**给
PROPOSE = [
    "要不我们去咖啡厅坐坐吧？",
    "明天去公园走走怎么样。",
]


def ask(text, port):
    """带一段前情：没有「之前在哪」的话，模型说「没发生地点变化」也不算错。"""
    body = {"messages": [
        {"role": "user", "content": "放学了，外面天都黑了，一起走吗？"},
        {"role": "assistant", "content": "「…ああ、いいけど」"},
        {"role": "user", "content": text},
    ]}
    rq = urllib.request.Request("http://127.0.0.1:%s/api/chat" % port,
                                data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(rq, timeout=300).read().decode("utf-8"))


def main():
    print("到达类（应该给 <scene>），跑 %d 轮：" % ROUNDS)
    hit = 0
    total = 0
    for i in range(ROUNDS):
        u = ARRIVE[i % len(ARRIVE)]
        try:
            d = ask(u, PORT)
        except Exception as e:
            print("  %d 请求失败 %s" % (i + 1, e))
            continue
        total += 1
        sc, bg = (d.get("scene") or ""), (d.get("bg") or "")
        ok = bool(sc)
        hit += 1 if ok else 0
        print("  %d %s  scene=%-10r bg=%r" % (i + 1, "✓" if ok else "✗", sc, bg))

    print("\n提议类（不该给 <scene>）：")
    false_pos = 0
    for i in range(min(2, len(PROPOSE))):
        try:
            d = ask(PROPOSE[i], PORT)
        except Exception as e:
            print("  %d 请求失败 %s" % (i + 1, e))
            continue
        sc = d.get("scene") or ""
        if sc:
            false_pos += 1
        print("  %d %s  scene=%r" % (i + 1, "✗误报" if sc else "✓没乱给", sc))

    print("\n到达命中 %d/%d，提议误报 %d" % (hit, total, false_pos))
    return 0


if __name__ == "__main__":
    sys.exit(main())
