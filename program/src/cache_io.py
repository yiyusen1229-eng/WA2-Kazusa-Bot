# -*- coding: utf-8 -*-
"""磁盘缓存的读取守卫。

读缓存前先确认：文件存在、大小够、内容能解码。坏了就删掉（下次重新生成）并记 WARN，
绝不把 0 字节 / 半截文件当成有效缓存——断电、磁盘满最容易留下这种文件。

对外：
    read_bytes(path, min_size=1)     → bytes | None
    read_json(path, default=None)    → dict/list | default
    read_gz_json(path, default=None) → 同上（.json.gz）
    read_image(path)                 → PNG bytes | None（校验文件头 + IEND 结尾）
    stats()                          → {"checked": n, "dropped": n}
"""
import gzip
import json
import os

import applog

_STATS = {"checked": 0, "dropped": 0}

_PNG_SIG = b"\x89PNG\r\n\x1a\n"


def stats():
    return dict(_STATS)


def reset_stats():
    _STATS["checked"] = 0
    _STATS["dropped"] = 0


def _drop(path, why):
    """坏缓存：删掉，别让它继续被当成有效文件"""
    _STATS["dropped"] += 1
    try:
        os.remove(path)
    except Exception:
        pass
    try:
        applog.log("缓存：%s 不可用（%s），已删除" % (path, why), "WARN")
    except Exception:
        pass


def read_bytes(path, min_size=1):
    """读文件。文件不存在 → None（不算坏）；空文件 / 读失败 → 删掉并返回 None。"""
    _STATS["checked"] += 1
    try:
        size = os.path.getsize(path)
    except OSError:
        return None
    if size < min_size:
        _drop(path, "只有 %d 字节" % size)
        return None
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError as e:
        _drop(path, "读失败：%s" % e)
        return None
    if len(data) < min_size:
        _drop(path, "读出来只有 %d 字节" % len(data))
        return None
    return data


def read_json(path, default=None):
    data = read_bytes(path)
    if data is None:
        return default
    try:
        return json.loads(data.decode("utf-8"))
    except Exception as e:
        _drop(path, "JSON 解不开：%s" % e)
        return default


def read_gz_json(path, default=None):
    data = read_bytes(path)
    if data is None:
        return default
    try:
        return json.loads(gzip.decompress(data).decode("utf-8"))
    except Exception as e:
        _drop(path, "gz/JSON 解不开：%s" % e)
        return default


def read_image(path):
    """PNG：文件头 + 结尾 IEND 都在才算完整（挡 0 字节和写了一半的图）"""
    data = read_bytes(path, min_size=32)
    if data is None:
        return None
    if not data.startswith(_PNG_SIG):
        _drop(path, "不是 PNG")
        return None
    if b"IEND" not in data[-16:]:
        _drop(path, "PNG 不完整（没有 IEND）")
        return None
    return data
