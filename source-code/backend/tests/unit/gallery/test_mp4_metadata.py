"""MP4 容器元数据读取测试

ComfyUI 合成视频时会把 workflow / prompt 写成 mp4 的自定义标签
（``moov/udta/meta/{keys,ilst}``），和 PNG 的文本块是同一份内容。
这里用最小的合法盒子结构构造 mp4，验证纯 Python 解析器不依赖 ffprobe 也能读到。
"""

import json
import struct

import pytest

from backend.src.gallery.scanner import gallery_scanner
from backend.src.utils.mp4_metadata import read_mp4_tags, read_mp4_text_tags


def _box(box_type: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload) + 8) + box_type + payload


def _full_box(box_type: bytes, payload: bytes) -> bytes:
    return _box(box_type, b"\x00\x00\x00\x00" + payload)


def _keys_box(names) -> bytes:
    entries = b""
    for name in names:
        raw = name.encode("utf-8")
        entries += struct.pack(">I", len(raw) + 8) + b"mdta" + raw
    return _full_box(b"keys", struct.pack(">I", len(names)) + entries)


def _ilst_box(values) -> bytes:
    entries = b""
    for index, text in enumerate(values, start=1):
        payload = b"\x00\x00\x00\x01" + b"\x00\x00\x00\x00" + text.encode("utf-8")
        data_box = _box(b"data", payload)
        entries += struct.pack(">I", len(data_box) + 8) + struct.pack(">I", index) + data_box
    return _box(b"ilst", entries)


def _write_mp4(path, tags: dict) -> None:
    """写一个只有 ftyp + moov(udta(meta(keys+ilst))) + mdat 的最小 mp4"""
    meta = _full_box(b"meta", _keys_box(list(tags)) + _ilst_box(list(tags.values())))
    moov = _box(b"moov", _box(b"udta", meta))
    ftyp = _box(b"ftyp", b"isom" + b"\x00\x00\x02\x00" + b"isomiso2avc1mp41")
    path.write_bytes(ftyp + moov + _box(b"mdat", b"\x00" * 64))


class TestReadMp4Tags:
    def test_读到自定义标签(self, tmp_path):
        target = tmp_path / "clip.mp4"
        _write_mp4(target, {"workflow": '{"nodes": []}', "prompt": '{"1": {}}'})

        tags = read_mp4_tags(target)

        assert set(tags) == {"workflow", "prompt"}
        assert tags["workflow"] == b'{"nodes": []}'

    def test_解码为字符串(self, tmp_path):
        target = tmp_path / "clip.mp4"
        _write_mp4(target, {"workflow": '{"名称": "测试"}'})

        tags = read_mp4_text_tags(target)

        assert json.loads(tags["workflow"]) == {"名称": "测试"}

    def test_非mp4文件返回空(self, tmp_path):
        target = tmp_path / "not_a_video.mp4"
        target.write_bytes(b"just some bytes, no ftyp box")

        assert read_mp4_tags(target) == {}

    def test_没有meta盒子返回空(self, tmp_path):
        target = tmp_path / "plain.mp4"
        ftyp = _box(b"ftyp", b"isom" + b"\x00\x00\x02\x00" + b"isomiso2avc1mp41")
        target.write_bytes(ftyp + _box(b"moov", _box(b"udta", b"")))

        assert read_mp4_tags(target) == {}

    def test_文件不存在返回空(self, tmp_path):
        assert read_mp4_tags(tmp_path / "missing.mp4") == {}


class TestVideoMetadataExtraction:
    """扫描器对视频资产的元数据提取"""

    def test_从mp4内嵌工作流取到提示词与参数(self, tmp_path):
        workflow = {
            "nodes": [
                {"id": 1, "type": "CheckpointLoaderSimple",
                 "widgets_values": ["sd_xl_base_1.0.safetensors", "normal"]},
                {"id": 2, "type": "CLIPTextEncode",
                 # 真实导出的工作流节点都带 inputs/outputs，判定文本编码节点依赖它们
                 "inputs": [{"name": "clip", "type": "CLIP"},
                            {"name": "text", "type": "STRING", "widget": {"name": "text"}}],
                 "outputs": [{"name": "CONDITIONING", "type": "CONDITIONING"}],
                 "widgets_values": ["a cat sitting on a windowsill, soft light"]},
                {"id": 3, "type": "KSampler",
                 "widgets_values": [424242, "fixed", 24, 6.5, "euler", "simple", 1.0]},
            ],
            "links": [],
        }
        target = tmp_path / "clip.mp4"
        _write_mp4(target, {"workflow": json.dumps(workflow, ensure_ascii=False)})

        metadata = gallery_scanner._extract_video_metadata(target)

        assert metadata["has_workflow"] is True
        assert metadata["prompt"] == "a cat sitting on a windowsill, soft light"
        assert metadata["model"] == "sd_xl_base_1.0.safetensors"
        assert metadata["sampler"] == "euler"
        assert metadata["steps"] == 24
        assert metadata["seed"] == 424242

    def test_没有标签的视频返回空字典(self, tmp_path):
        target = tmp_path / "plain.mp4"
        ftyp = _box(b"ftyp", b"isom" + b"\x00\x00\x02\x00" + b"isomiso2avc1mp41")
        target.write_bytes(ftyp + _box(b"mdat", b"\x00" * 64))

        assert gallery_scanner._extract_video_metadata(target) == {}

    @pytest.mark.parametrize("suffix", [".webm", ".png"])
    def test_只处理mp4容器(self, tmp_path, suffix):
        """webm 是 EBML 结构，标签位置完全不同，这里明确不支持"""
        target = tmp_path / f"clip{suffix}"
        _write_mp4(target, {"workflow": '{"nodes": []}'})

        assert gallery_scanner._extract_video_metadata(target) == {}

    def test_读取内嵌工作流统一入口(self, tmp_path):
        workflow = {"nodes": [{"id": 1, "type": "Note", "widgets_values": ["hi"]}], "links": []}
        target = tmp_path / "clip.mp4"
        _write_mp4(target, {"workflow": json.dumps(workflow)})

        data = gallery_scanner.read_embedded_workflow(target)

        assert data == workflow
