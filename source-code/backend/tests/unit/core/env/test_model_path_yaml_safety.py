"""extra_model_paths.yaml 安全性测试

背景：环境设置 → 模型路径 页面在没有任何配置时点击「保存配置」，
会经 update_environment() 触发 generate_yaml()。旧实现直接 unlink()
ComfyUI 根目录下的 extra_model_paths.yaml，导致用户手工维护的文件被静默删除。

本测试锁定修复后的行为：
- 用户手写文件（无归属标记）在任何情况下都不被删除
- 仅清理本应用生成的文件（首行带 YAML_OWNERSHIP_MARKER）
"""

import sys
from pathlib import Path
from types import SimpleNamespace

_BACKEND_DIR = Path(__file__).resolve().parents[4]
_SOURCE_ROOT = _BACKEND_DIR.parent
for _p in (str(_BACKEND_DIR), str(_SOURCE_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.src.core.env.model_path_manager import (  # noqa: E402
    YAML_OWNERSHIP_MARKER,
    ModelPathManager,
)

HANDWRITTEN_CONTENT = """\
comfyui:
    base_path: D:/Models
    checkpoints: checkpoints
    loras: loras
"""


def _make_manager(comfyui_path: Path, configs):
    """构造只依赖 comfyui_path 与 model_path_configs 的最小管理器"""
    env = SimpleNamespace(
        model_path_configs=configs,
        config=SimpleNamespace(
            general=SimpleNamespace(comfyui_path=str(comfyui_path))
        ),
    )
    config_manager = SimpleNamespace(get_environment=lambda env_id: env)
    environment_manager = SimpleNamespace(config_manager=config_manager)
    return ModelPathManager(environment_manager)


def test_空配置时保留用户手写文件(tmp_path):
    """无配置 + 手写文件：必须原样保留，不得删除或覆盖"""
    yaml_file = tmp_path / "extra_model_paths.yaml"
    yaml_file.write_text(HANDWRITTEN_CONTENT, encoding="utf-8")

    manager = _make_manager(tmp_path, configs=[])
    result = manager.generate_yaml("env-1")

    assert result["success"] is True
    assert result.get("preserved") is True
    assert yaml_file.exists(), "用户手写的 extra_model_paths.yaml 被删除了"
    assert yaml_file.read_text(encoding="utf-8") == HANDWRITTEN_CONTENT


def test_空配置时清理本应用生成的文件(tmp_path):
    """无配置 + 带归属标记：视为本应用产物，允许清理"""
    yaml_file = tmp_path / "extra_model_paths.yaml"
    yaml_file.write_text(
        YAML_OWNERSHIP_MARKER + "\ncomfyui:\n    base_path: D:/Models\n",
        encoding="utf-8",
    )

    manager = _make_manager(tmp_path, configs=[])
    result = manager.generate_yaml("env-1")

    assert result["success"] is True
    assert not yaml_file.exists(), "本应用生成的 YAML 未被清理"


def test_空配置且文件不存在时正常返回(tmp_path):
    """无配置 + 无文件：不应报错"""
    manager = _make_manager(tmp_path, configs=[])
    result = manager.generate_yaml("env-1")

    assert result["success"] is True
    assert result.get("skipped") is True


def test_标记不在首行时仍视为用户文件(tmp_path):
    """标记出现在中间而非首行，不足以证明归属，必须保留"""
    yaml_file = tmp_path / "extra_model_paths.yaml"
    content = "comfyui:\n    base_path: D:/Models\n" + YAML_OWNERSHIP_MARKER + "\n"
    yaml_file.write_text(content, encoding="utf-8")

    manager = _make_manager(tmp_path, configs=[])
    result = manager.generate_yaml("env-1")

    assert result["success"] is True
    assert yaml_file.exists()
    assert yaml_file.read_text(encoding="utf-8") == content


def test_有配置时生成带标记的yaml(tmp_path):
    """正常生成路径：首行写入归属标记，后续配置正确落盘"""
    config = SimpleNamespace(
        name="comfyui",
        base_path="D:/Models",
        paths={"checkpoints": "checkpoints", "clipVision": "clip_vision"},
    )
    manager = _make_manager(tmp_path, configs=[config])
    result = manager.generate_yaml("env-1")

    assert result["success"] is True
    yaml_file = tmp_path / "extra_model_paths.yaml"
    lines = yaml_file.read_text(encoding="utf-8").splitlines()
    assert lines[0] == YAML_OWNERSHIP_MARKER
    body = "\n".join(lines[1:])
    assert "base_path: D:/Models" in body
    assert "clip_vision: clip_vision" in body, "驼峰字段未映射为 ComfyUI 下划线命名"


def test_生成的yaml可被再次安全清理(tmp_path):
    """先有配置生成、后清空配置：生成的产物应被清理，形成闭环"""
    config = SimpleNamespace(
        name="comfyui", base_path="D:/Models", paths={"checkpoints": "checkpoints"}
    )
    _make_manager(tmp_path, configs=[config]).generate_yaml("env-1")
    yaml_file = tmp_path / "extra_model_paths.yaml"
    assert yaml_file.exists()

    result = _make_manager(tmp_path, configs=[]).generate_yaml("env-1")

    assert result["success"] is True
    assert not yaml_file.exists()
