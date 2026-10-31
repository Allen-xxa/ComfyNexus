"""工作流节点计数解析测试

覆盖需求：工作流目录中混入非工作流 JSON（如预设列表）时不应抛异常，
同时要正确统计 UI 格式与 API 格式的节点数。
"""

import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[4]
_SOURCE_ROOT = _BACKEND_DIR.parent
for _p in (str(_BACKEND_DIR), str(_SOURCE_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.src.core.workflow.parser import WorkflowParser  # noqa: E402


def test_ui格式按nodes计数():
    data = {"nodes": [{"id": 1}, {"id": 2}, {"id": 3}], "links": []}
    assert WorkflowParser.extract_node_count(data) == 3


def test_api格式按class_type计数():
    data = {
        "1": {"class_type": "KSampler", "inputs": {}},
        "2": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
        "extra": "非节点字段",
    }
    assert WorkflowParser.extract_node_count(data) == 2


def test_顶层为列表时返回零不抛异常():
    """复现原缺陷：020-stg_advanced_presets.json 顶层是列表，旧实现直接 AttributeError"""
    assert WorkflowParser.extract_node_count([{"preset": "a"}, {"preset": "b"}]) == 0


def test_其他类型返回零():
    assert WorkflowParser.extract_node_count(None) == 0
    assert WorkflowParser.extract_node_count("text") == 0
    assert WorkflowParser.extract_node_count(42) == 0


def test_空字典返回零():
    assert WorkflowParser.extract_node_count({}) == 0


def test_nodes字段不是列表时回退到class_type计数():
    data = {"nodes": "broken", "1": {"class_type": "KSampler"}}
    assert WorkflowParser.extract_node_count(data) == 1
