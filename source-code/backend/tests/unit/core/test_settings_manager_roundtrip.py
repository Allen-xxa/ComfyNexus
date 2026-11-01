"""SettingsManager 读写回归测试（全部在 tmp_path 下，不触碰真实 settings.json）。

替代原 test_settings_save.py：该文件调用了未定义的 get_settings_file()（NameError），
并且直接改写用户真实配置、没有任何断言。
"""

import json

import pytest

from backend.src.core.settings_manager import SettingsManager


@pytest.mark.unit
def test_首次读取生成默认配置并落盘(tmp_path):
    manager = SettingsManager(config_dir=str(tmp_path))

    result = manager.get_settings()

    assert result["success"] is True
    assert (tmp_path / "settings.json").exists()
    # 二次开发分支：自动更新默认关闭，避免下载上游发布包覆盖本地修改
    assert result["settings"]["general"]["autoUpdate"] is False


@pytest.mark.unit
def test_更新后落盘内容与重新读取一致(tmp_path):
    manager = SettingsManager(config_dir=str(tmp_path))
    manager.get_settings()

    update = manager.update_settings(
        {"pluginManagement": {"hideDisabledPlugins": True}}
    )

    assert update["success"] is True
    assert update["message"] == "设置已保存"

    on_disk = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert on_disk["pluginManagement"]["hideDisabledPlugins"] is True

    reloaded = manager.get_settings()
    assert reloaded["settings"]["pluginManagement"]["hideDisabledPlugins"] is True


@pytest.mark.unit
def test_深度合并保留同节其他字段(tmp_path):
    manager = SettingsManager(config_dir=str(tmp_path))
    original_general = manager.get_settings()["settings"]["general"].copy()

    manager.update_settings({"general": {"autoUpdate": True}})

    saved_general = json.loads(
        (tmp_path / "settings.json").read_text(encoding="utf-8")
    )["general"]
    assert saved_general["autoUpdate"] is True
    # 未被更新的字段必须保持不变
    assert saved_general["configMode"] == original_general["configMode"]
    assert saved_general["comfyuiStartupAction"] == original_general["comfyuiStartupAction"]


@pytest.mark.unit
def test_全新配置目录的默认值与生产代码一致(tmp_path):
    """锁定 fork 的安全默认值：更新源指向上游，默认必须关闭。"""
    manager = SettingsManager(config_dir=str(tmp_path))

    defaults = manager.get_default_config()

    assert defaults["general"]["autoUpdate"] is False
    assert defaults["version"] == SettingsManager.CURRENT_VERSION
