# -*- coding: utf-8 -*-
"""一键准备素材（能自动下的自动下，不能自动下的告诉你手动怎么做）

用法：
    python tools/setup_assets.py --check          # 只自检
    python tools/setup_assets.py --model 14b      # 下载 Qwen2.5-14B（魔搭，约 29 GB）
    python tools/setup_assets.py --model 7b       # 下载 Qwen2.5-7B（约 15 GB）
    python tools/setup_assets.py --tts            # 克隆 GPT-SoVITS
    python tools/setup_assets.py --all            # 上面全做（不含游戏素材）

游戏素材（立绘 / UI / 剧本 / 语音）无法自动下载，见 docs/本地素材获取指南.md。
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MODELSCOPE_API = ("https://modelscope.cn/api/v1/models/Qwen/{name}/repo/files"
                  "?Revision=master")
MODELSCOPE_RESOLVE = "https://modelscope.cn/models/Qwen/{name}/resolve/master/{file}"

MODELS = {
    "7b": "Qwen2.5-7B-Instruct",
    "14b": "Qwen2.5-14B-Instruct",
}


def log(msg):
    print(msg, flush=True)


def http_json(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "wa2-setup/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def list_files(name):
    """拿仓库文件清单（只取文件，不要目录）"""
    data = http_json(MODELSCOPE_API.format(name=name))
    files = []
    for item in data.get("Data", {}).get("Files", []):
        if item.get("Type") == "blob":
            files.append(item["Path"])
    return files


def download(name, out_dir, skip_existing=True):
    os.makedirs(out_dir, exist_ok=True)
    files = list_files(name)
    if not files:
        log("  拿不到文件清单，可能接口变了。请手动下载：")
        log("    https://modelscope.cn/models/Qwen/%s" % name)
        return False

    log("  %s 共 %d 个文件" % (name, len(files)))
    total = 0
    for i, rel in enumerate(files, 1):
        dst = os.path.join(out_dir, rel.replace("/", os.sep))
        if skip_existing and os.path.exists(dst) and os.path.getsize(dst) > 0:
            total += os.path.getsize(dst)
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        url = MODELSCOPE_RESOLVE.format(name=name, file=urllib.parse.quote(rel))
        log("    [%d/%d] %s" % (i, len(files), rel))
        try:
            with urllib.request.urlopen(url, timeout=600) as r, open(dst, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            total += os.path.getsize(dst)
        except Exception as e:
            log("      失败：%s" % e)
            log("      可手动下载：%s" % url)
            return False
    log("  完成，约 %.1f GB" % (total / 1024 ** 3))
    return True


def clone_tts():
    dst = os.path.join(ROOT, "tts", "GPT-SoVITS")
    if os.path.isdir(dst):
        log("  tts/GPT-SoVITS 已存在，跳过")
        return True
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    log("  克隆 GPT-SoVITS（约 1 GB，含子模块）…")
    r = subprocess.run(
        ["git", "clone", "--depth", "1",
         "https://github.com/RVC-Boss/GPT-SoVITS.git", dst],
        cwd=ROOT)
    if r.returncode != 0:
        log("  克隆失败，请手动：git clone https://github.com/RVC-Boss/GPT-SoVITS tts/GPT-SoVITS")
        return False
    log("  完成。权重与运行时仍需自己补：")
    log("    - GPT-SoVITS 的独立 python 运行时（runtime/）")
    log("    - Touma_Kazusa 权重（见 docs/参考与致谢.md 里的 B 站视频）")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只做素材自检")
    ap.add_argument("--model", choices=["7b", "14b", "all"], help="下载基座模型")
    ap.add_argument("--tts", action="store_true", help="克隆 GPT-SoVITS")
    ap.add_argument("--all", action="store_true", help="模型 + TTS")
    args = ap.parse_args()

    if args.check or not any([args.model, args.tts, args.all]):
        os.execv(sys.executable, [sys.executable,
                                  os.path.join(ROOT, "tools", "check_assets.py")])
        return

    if args.all:
        args.model = "all"
        args.tts = True

    if args.model:
        targets = ["7b", "14b"] if args.model == "all" else [args.model]
        for t in targets:
            name = MODELS[t]
            out = os.path.join(ROOT, "train", "models", name)
            log("\n[下载] %s → train/models/%s" % (name, name))
            download(name, out)

    if args.tts:
        log("\n[克隆] GPT-SoVITS")
        clone_tts()

    log("\n完成。跑一次自检看看还缺什么：")
    log("  python tools/check_assets.py")


if __name__ == "__main__":
    main()
