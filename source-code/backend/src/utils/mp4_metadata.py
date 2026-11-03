"""
MP4 容器自定义元数据读取（纯 Python，不依赖 ffprobe）

ComfyUI 的 VHS_VideoCombine 等节点在用 ffmpeg 合成 mp4 时会带上
``-movflags use_metadata_tags``，把 ``workflow`` / ``prompt`` 写成容器的
自定义标签，位置在 ``moov/udta/meta/{keys,ilst}`` 里。

ffprobe 能直接看到这些标签，但项目里不能假设用户装了 ffmpeg（ComfyUI 自带的那份
通常也不在 PATH 上），所以这里按 ISO BMFF 的盒子结构自己解析。只需要读
``moov`` 这一段，几 MB 的视频通常几十毫秒。

对外只暴露两个函数：

- :func:`read_mp4_tags` 返回 ``{标签名: 原始字节}``
- :func:`read_mp4_text_tags` 返回 ``{标签名: 字符串}``（utf-8 解码，失败跳过）
"""

from pathlib import Path
from typing import Dict, Union

__all__ = ["read_mp4_tags", "read_mp4_text_tags"]

# 递归查找 meta 盒子时允许的最大层级，正常结构是 moov/udta/meta，留点余量
_MAX_DEPTH = 5
# 元数据盒子的读取上限，防止异常文件把内存吃满
_MAX_META_BYTES = 8 * 1024 * 1024
# 这些盒子内部还可能嵌套子盒子，需要递归进去找 meta
_CONTAINER_BOXES = {b"moov", b"udta", b"trak", b"mdia", b"minf", b"stbl", b"edts"}


def _iter_boxes(handle, start: int, end: int):
    """遍历 [start, end) 区间内的顶层盒子，产出 (类型, 载荷起点, 载荷终点)"""
    pos = start
    while pos + 8 <= end:
        handle.seek(pos)
        header = handle.read(8)
        if len(header) < 8:
            return
        size = int.from_bytes(header[:4], "big")
        box_type = header[4:8]
        header_size = 8
        if size == 1:
            # 64 位长度：紧跟在盒子头后面
            extended = handle.read(8)
            if len(extended) < 8:
                return
            size = int.from_bytes(extended, "big")
            header_size = 16
        elif size == 0:
            # 0 表示一直到文件尾
            size = end - pos
        if size < header_size or pos + size > end:
            return
        yield box_type, pos + header_size, pos + size
        pos += size


def _find_meta_box(handle, start: int, end: int, depth: int = 0):
    """递归找到 meta 盒子，返回其载荷区间（已跳过 full box 的 version/flags）"""
    if depth > _MAX_DEPTH:
        return None
    for box_type, payload_start, payload_end in _iter_boxes(handle, start, end):
        if box_type == b"meta":
            # meta 是 full box，前 4 字节是 version + flags
            return payload_start + 4, payload_end
        if box_type in _CONTAINER_BOXES:
            found = _find_meta_box(handle, payload_start, payload_end, depth + 1)
            if found:
                return found
    return None


def _read_keys(handle, start: int, end: int) -> Dict[int, str]:
    """解析 keys 盒子，返回 {序号: 标签名}"""
    handle.seek(start)
    payload = handle.read(min(end - start, _MAX_META_BYTES))
    if len(payload) < 8:
        return {}

    count = int.from_bytes(payload[4:8], "big")
    keys: Dict[int, str] = {}
    offset = 8
    for index in range(1, count + 1):
        if offset + 8 > len(payload):
            break
        size = int.from_bytes(payload[offset:offset + 4], "big")
        if size < 8 or offset + size > len(payload):
            break
        # 每个条目是 size(4) + namespace(4) + name
        name = payload[offset + 8:offset + size].decode("utf-8", "replace")
        keys[index] = name
        offset += size
    return keys


def _read_data_payload(handle, start: int, end: int) -> bytes:
    """从 ilst 条目里取出 data 盒子的实际内容"""
    for box_type, payload_start, payload_end in _iter_boxes(handle, start, end):
        if box_type != b"data":
            continue
        handle.seek(payload_start)
        raw = handle.read(min(payload_end - payload_start, _MAX_META_BYTES))
        # data 盒子头部：version/flags(4) + 类型标识(4) + 语言(4)
        return raw[8:] if len(raw) > 8 else b""
    return b""


def read_mp4_tags(file_path: Union[str, Path]) -> Dict[str, bytes]:
    """读取 mp4 的自定义标签，返回 {标签名: 原始字节}"""
    path = Path(file_path)
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            file_end = handle.tell()
            handle.seek(0)
            # 只处理标准 mp4/mov，其它格式直接放弃
            head = handle.read(12)
            if len(head) < 12 or head[4:8] != b"ftyp":
                return {}

            meta_range = _find_meta_box(handle, 0, file_end)
            if not meta_range:
                return {}

            keys: Dict[int, str] = {}
            ilst_range = None
            for box_type, payload_start, payload_end in _iter_boxes(handle, *meta_range):
                if box_type == b"keys":
                    keys = _read_keys(handle, payload_start, payload_end)
                elif box_type == b"ilst":
                    ilst_range = (payload_start, payload_end)
            if not ilst_range or not keys:
                return {}

            tags: Dict[str, bytes] = {}
            for box_type, payload_start, payload_end in _iter_boxes(handle, *ilst_range):
                index = int.from_bytes(box_type, "big")
                name = keys.get(index)
                if not name:
                    continue
                tags[name] = _read_data_payload(handle, payload_start, payload_end)
            return tags
    except (OSError, ValueError):
        return {}


def read_mp4_text_tags(file_path: Union[str, Path]) -> Dict[str, str]:
    """读取 mp4 自定义标签并解码成字符串，解码失败的条目跳过"""
    result: Dict[str, str] = {}
    for name, raw in read_mp4_tags(file_path).items():
        if not raw:
            continue
        try:
            result[name] = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
    return result
