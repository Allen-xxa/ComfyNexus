"""搜索配置加载测试

覆盖：新增 tavily provider 后，旧配置文件加载时需自动补齐默认值。
"""

import json
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[4]
_SOURCE_ROOT = _BACKEND_DIR.parent
for _p in (str(_BACKEND_DIR), str(_SOURCE_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.src.core.ai.search.search_config import SearchConfig  # noqa: E402


def test_旧配置加载后补齐tavily默认值(tmp_path):
    """旧版 search_config.json 没有 tavily 字段，加载后应自动补全"""
    config_file = tmp_path / "search_config.json"
    config_file.write_text(
        json.dumps(
            {
                "enabled": True,
                "provider": "duckduckgo",
                "max_results": 5,
                "timeout": 10,
                "providers": {
                    "duckduckgo": {"enabled": True},
                    "google": {"enabled": False, "api_key": "k", "search_engine_id": "e"},
                },
            }
        ),
        encoding="utf-8",
    )

    config = SearchConfig(config_file=config_file).load()

    assert "tavily" in config["providers"], "未补齐 tavily 默认值"
    assert config["providers"]["tavily"]["api_key"] == ""
    assert config["providers"]["google"]["api_key"] == "k", "已有配置被覆盖"


def test_保留用户自定义provider(tmp_path):
    config_file = tmp_path / "search_config.json"
    config_file.write_text(
        json.dumps(
            {
                "enabled": True,
                "provider": "duckduckgo",
                "max_results": 5,
                "timeout": 10,
                "providers": {"my_custom": {"enabled": True}},
            }
        ),
        encoding="utf-8",
    )

    config = SearchConfig(config_file=config_file).load()
    assert "my_custom" in config["providers"]


def test_tavily需要api_key才允许保存():
    cfg = dict(SearchConfig.DEFAULT_CONFIG)
    cfg["provider"] = "tavily"
    cfg["providers"] = {"tavily": {"enabled": True, "api_key": ""}}

    manager = SearchConfig.__new__(SearchConfig)
    valid, message = manager.validate(cfg)

    assert valid is False
    assert "API Key" in message


def test_tavily有api_key时校验通过():
    cfg = dict(SearchConfig.DEFAULT_CONFIG)
    cfg["provider"] = "tavily"
    cfg["providers"] = {"tavily": {"enabled": True, "api_key": "tvly-xxx"}}

    manager = SearchConfig.__new__(SearchConfig)
    valid, _ = manager.validate(cfg)
    assert valid is True
