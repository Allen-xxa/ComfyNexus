"""资产库生成参数提取测试

覆盖「资产库转入提示词库」依赖的参数解析：
- 传统 KSampler 工作流
- 新式采样链（SamplerCustomAdvanced：RandomNoise + KSamplerSelect +
  BasicScheduler + CFGGuider）——这类工作流没有 KSampler 节点，
  早期实现只能拿到模型名，采样器/步数/种子全丢
"""

import pytest

from backend.src.gallery.scanner import gallery_scanner


def _workflow(nodes):
    """构造一个最小可用的 UI 工作流结构"""
    return {"nodes": nodes, "links": []}


def _node(node_id, node_type, widgets_values):
    return {"id": node_id, "type": node_type, "widgets_values": widgets_values}


class TestLegacyKSampler:
    def test_解析KSampler参数(self):
        workflow = _workflow([
            _node(1, "CheckpointLoaderSimple", ["sd_xl_base_1.0.safetensors", "normal"]),
            _node(2, "KSampler", [12345, "fixed", 30, 7.5, "dpmpp_2m", "karras", 1.0]),
        ])

        params = gallery_scanner._extract_params_from_workflow(
            workflow["nodes"], {}
        )

        assert params["model"] == "sd_xl_base_1.0.safetensors"
        assert params["seed"] == 12345
        assert params["steps"] == 30
        assert params["cfg"] == 7.5
        assert params["sampler"] == "dpmpp_2m"
        assert params["scheduler"] == "karras"


class TestCustomSamplingChain:
    """新式采样链：参数被拆到多个独立节点上"""

    def test_解析拆分后的采样参数(self):
        workflow = _workflow([
            _node(1, "UNETLoader", ["flux1-dev.safetensors", "default"]),
            _node(2, "RandomNoise", [987654321, "fixed"]),
            _node(3, "KSamplerSelect", ["euler"]),
            _node(4, "BasicScheduler", ["simple", 4, 1.0]),
            _node(5, "CFGGuider", [1.0]),
            _node(6, "SamplerCustomAdvanced", None),
        ])

        params = gallery_scanner._extract_params_from_workflow(
            workflow["nodes"], {}
        )

        assert params["model"] == "flux1-dev.safetensors"
        assert params["seed"] == 987654321
        assert params["sampler"] == "euler"
        assert params["scheduler"] == "simple"
        assert params["steps"] == 4
        assert params["cfg"] == 1.0

    def test_种子为0也要保留(self):
        """RandomNoise 的 seed 可能是 0，不能被当成没取到"""
        workflow = _workflow([
            _node(1, "RandomNoise", [0, "fixed"]),
        ])

        params = gallery_scanner._extract_params_from_workflow(
            workflow["nodes"], {}
        )

        assert params["seed"] == 0

    def test_两种采样链同时存在时以先出现的为准(self):
        workflow = _workflow([
            _node(1, "KSampler", [111, "fixed", 20, 6.0, "euler", "normal", 1.0]),
            _node(2, "KSamplerSelect", ["heun"]),
            _node(3, "RandomNoise", [222, "fixed"]),
        ])

        params = gallery_scanner._extract_params_from_workflow(
            workflow["nodes"], {}
        )

        assert params["sampler"] == "euler"
        assert params["seed"] == 111


class TestEmptyWorkflow:
    @pytest.mark.parametrize("nodes", [[], [{"id": 1, "type": "Note", "widgets_values": ["hi"]}]])
    def test_没有可用节点时返回空字典(self, nodes):
        params = gallery_scanner._extract_params_from_workflow(nodes, {})

        assert params == {}
