"""话题自动命名测试

覆盖：话题仍为默认名时，用首条用户消息推导标题。
"""

import sys
from pathlib import Path

import pytest

_BACKEND_DIR = Path(__file__).resolve().parents[4]
_SOURCE_ROOT = _BACKEND_DIR.parent
for _p in (str(_BACKEND_DIR), str(_SOURCE_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.src.core.ai.ai_service import AIService  # noqa: E402


@pytest.mark.parametrize(
    "content,expected",
    [
        ("帮我写一个 ComfyUI 工作流", "写一个 ComfyUI 工作流"),
        ("请分析这段报错信息", "分析这段报错信息"),
        ("  多行\n文本  合并  ", "多行 文本 合并"),
        ("ComfyUI 是什么", "ComfyUI 是什么"),
    ],
)
def test_标题推导(content, expected):
    assert AIService._derive_topic_title(content) == expected


def test_超长标题被截断():
    title = AIService._derive_topic_title("a" * 50)
    assert len(title) == 21
    assert title.endswith("…")


def test_空内容不生成标题():
    assert AIService._derive_topic_title("") == ""
    assert AIService._derive_topic_title("   \n  ") == ""


def test_短句不被误删前缀():
    """前缀剥离不能把整句吃掉，需保留至少 4 个字符"""
    assert AIService._derive_topic_title("请测试") == "请测试"
