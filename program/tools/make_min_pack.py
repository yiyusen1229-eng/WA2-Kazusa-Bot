# -*- coding: utf-8 -*-
"""生成「最小可用角色包」示例（原创内容，可直接导入跑起来）。

    cd program
    .\\build_env\\venv\\Scripts\\python.exe tools\\make_min_pack.py

产物：
    other/docs/examples/min_pack/雪见/           源码（可改）
    other/docs/examples/min_pack/雪见.zip        打好的包（3 KB 级别）

为什么要有它：规范文档只有文字说明时，别人（和未来的自己）总要问「到底要哪些文件」。
这里给一个真的能导入、能对话、缺立绘会自动回落的最小例子。
"""
import io
import json
import os
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(REPO, "other", "docs", "examples", "min_pack")
CID = "雪见"

NAME_TXT = "雪见\n"

BASE_TXT = """你是雪见，二十四岁，在北方小城的旧书店「冬木堂」当店员，已经做了三年。

性格：话少、语气平，不主动找话题；别人对她好会别扭地顶一句，然后默默记住。
不会撒娇，也不会说漂亮话。对熟的人会露出笨拙的关心（比如把热水放在你手边就走开）。

说话方式：一次只说一两句，句子短。动作和神态写在括号里，不写内心独白。
不要自称「我」以外的称呼，不要用「呢」「哦」语气词凑句子。

（这是示例角色，不为任何原作角色，只为演示角色包的最小结构。）
"""

STAGE1_TXT = """现在刚认识不久：保持距离，回答简短，不主动打探对方的事。
对方问私事时转移话题，或者说「跟你没关系」。
"""

WORLDBOOK = {
    "name": "冬木堂世界书",
    "version": 1,
    "scan_depth": 8,
    "max_entries": 4,
    "max_chars": 1200,
    "entries": [
        {
            "name": "冬木堂",
            "keywords": ["书店", "冬木堂", "店里"],
            "content": "冬木堂是一间开了三十年的旧书店，木地板会响。"
                       "靠窗有一张旧沙发，雪见上班时会坐在那儿理书。",
            "priority": 10,
            "case_sensitive": False
        },
        {
            "name": "北方的冬天",
            "keywords": ["雪", "冬天", "冷"],
            "content": "小城的冬天很长，十一月初就下雪，路面结冰。"
                       "雪见总是走得很慢，说「摔一下要疼半个月」。",
            "priority": 8,
            "case_sensitive": False
        }
    ]
}

MEMORY_TXT = """【常驻记忆书】
- 雪见在冬木堂当店员，做满三年了。
- 她怕摔，冬天走路很慢。
"""

STANDING = {
    "version": 1,
    "fixed": "雪见，二十四岁，冬木堂店员。话少、别扭、会笨拙地关心人。",
    "relation_summary": "",
    "stage": 1,
    "updated_at": "",
    "source_msgs": 0
}


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main():
    src = os.path.join(OUT, CID)
    write(os.path.join(src, "name.txt"), NAME_TXT)
    write(os.path.join(src, "prompt", "base.txt"), BASE_TXT)
    write(os.path.join(src, "prompt", "stage1.txt"), STAGE1_TXT)
    write(os.path.join(src, "worldbook", "worldbook.json"),
          json.dumps(WORLDBOOK, ensure_ascii=False, indent=1) + "\n")
    write(os.path.join(src, "memory", "记忆书.txt"), MEMORY_TXT)
    write(os.path.join(src, "memory", "standing.json"),
          json.dumps(STANDING, ensure_ascii=False, indent=1) + "\n")

    # 打 zip：格式和 char_pack 导出一致（manifest + 白名单目录 + name.txt）
    members = []
    for dirpath, _dirs, files in os.walk(src):
        for fn in sorted(files):
            p = os.path.join(dirpath, fn)
            members.append((p, os.path.relpath(p, src).replace("\\", "/")))
    parts = {}
    total = 0
    for p, rel in members:
        top = rel.split("/")[0] if "/" in rel else rel
        parts[top] = parts.get(top, 0) + 1
        total += os.path.getsize(p)
    manifest = {
        "format": "wa2-char-pack",
        "version": 1,
        "id": CID,
        "name": CID,
        "created_at": "2026-11-06 14:30:00",
        "app": "WA2-Kazusa-Bot",
        "parts": parts,
        "files": len(members),
        "bytes": total
    }
    zpath = os.path.join(OUT, CID + ".zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))
        for p, rel in members:
            z.write(p, rel)
    print("源目录: %s（%d 个文件）" % (src, len(members)))
    print("打包:   %s（%.1f KB）" % (zpath, os.path.getsize(zpath) / 1024.0))
    for k in sorted(parts):
        print("  %-10s %d" % (k, parts[k]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
