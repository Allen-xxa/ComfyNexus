"""LoRA 扩展路径解析测试

覆盖需求：LoRA 管理页需要能识别 extra_model_paths.yaml 中扩展的 loras 目录，
以及 ComfyUI 默认的 models/loras。
"""

import sys
from pathlib import Path

import pytest

_BACKEND_DIR = Path(__file__).resolve().parents[4]
_SOURCE_ROOT = _BACKEND_DIR.parent
for _p in (str(_BACKEND_DIR), str(_SOURCE_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.src.core.lora.path_resolver import (  # noqa: E402
    build_scan_paths,
    resolve_extra_lora_dirs,
)

SAMPLE_YAML = """\
comfyui:
    base_path: {base}/shared
    checkpoints: checkpoints
    loras: loras

extra_absolute:
    loras: {base}/abs_loras

multi_line:
    base_path: {base}/multi
    loras: |
        sub_a
        sub_b

placeholder:
    base_path: {base}/ph
    loras: "{{base_path}}/nested"
"""


@pytest.fixture
def yaml_env(tmp_path):
    """构造一个包含各类 loras 写法的 extra_model_paths.yaml"""
    yaml_path = tmp_path / "extra_model_paths.yaml"
    yaml_path.write_text(SAMPLE_YAML.format(base=tmp_path.as_posix()), encoding="utf-8")
    return yaml_path, tmp_path


def test_解析相对路径与绝对路径(yaml_env):
    yaml_path, base = yaml_env
    dirs = [Path(d) for d in resolve_extra_lora_dirs(yaml_path)]
    names = {d.name for d in dirs}

    assert "loras" in names, "base_path + 相对 loras 未被解析"
    assert "abs_loras" in names, "绝对路径 loras 未被解析"
    assert (base / "shared" / "loras") in dirs


def test_解析多行与占位符(yaml_env):
    yaml_path, base = yaml_env
    dirs = [Path(d) for d in resolve_extra_lora_dirs(yaml_path)]

    assert (base / "multi" / "sub_a") in dirs
    assert (base / "multi" / "sub_b") in dirs
    assert (base / "ph" / "nested") in dirs, "{base_path} 占位符未被替换"


def test_yaml不存在时返回空(tmp_path):
    assert resolve_extra_lora_dirs(tmp_path / "nope.yaml") == []


def test_合并默认目录与扩展目录(tmp_path):
    comfyui = tmp_path / "ComfyUI"
    default_lora = comfyui / "models" / "loras"
    extra_lora = tmp_path / "shared" / "loras"
    default_lora.mkdir(parents=True)
    extra_lora.mkdir(parents=True)

    (comfyui / "extra_model_paths.yaml").write_text(
        f"shared:\n    base_path: {tmp_path.as_posix()}/shared\n    loras: loras\n",
        encoding="utf-8",
    )

    paths = build_scan_paths([], str(comfyui))
    resolved = {Path(p["path"]).name for p in paths}

    assert "loras" in resolved
    assert len(paths) >= 2, "默认 models/loras 与扩展目录应同时纳入"


def test_用户配置优先且不重复(tmp_path):
    comfyui = tmp_path / "ComfyUI"
    default_lora = comfyui / "models" / "loras"
    default_lora.mkdir(parents=True)

    user_paths = [
        {
            "id": "u1",
            "path": str(default_lora),
            "name": "我的LoRA",
            "category": "flux",
            "enabled": True,
        }
    ]
    paths = build_scan_paths(user_paths, str(comfyui))

    matched = [p for p in paths if Path(p["path"]) == default_lora]
    assert len(matched) == 1, "同一目录被重复纳入扫描"
    assert matched[0]["name"] == "我的LoRA", "用户配置的分类信息被覆盖"


def test_禁用路径被过滤_用户显式路径保留(tmp_path):
    """已禁用的不参与扫描；用户显式添加的路径即使暂不存在也保留，避免配置被静默丢弃"""
    comfyui = tmp_path / "ComfyUI"
    comfyui.mkdir()
    ghost = tmp_path / "ghost"

    user_paths = [
        {"id": "u1", "path": str(tmp_path / "disabled"), "name": "d", "enabled": False},
        {"id": "u2", "path": str(ghost), "name": "g", "enabled": True},
    ]
    paths = build_scan_paths(user_paths, str(comfyui))

    assert all(p["id"] != "u1" for p in paths), "已禁用的路径不应参与扫描"
    assert any(Path(p["path"]) == ghost for p in paths), "用户显式添加的路径不应被丢弃"


def test_自动发现的目录必须存在(tmp_path):
    """由 yaml 与默认目录自动发现时，不存在的目录不应加入扫描列表"""
    comfyui = tmp_path / "ComfyUI"
    comfyui.mkdir()
    missing = tmp_path / "missing_loras"

    (comfyui / "extra_model_paths.yaml").write_text(
        f"shared:\n    base_path: {tmp_path.as_posix()}\n    loras: missing_loras\n",
        encoding="utf-8",
    )

    paths = build_scan_paths([], str(comfyui))
    assert all(Path(p["path"]) != missing for p in paths)


def test_无ComfyUI路径时仅返回用户配置(tmp_path):
    real = tmp_path / "my_loras"
    real.mkdir()
    user_paths = [{"id": "u1", "path": str(real), "name": "mine", "enabled": True}]

    paths = build_scan_paths(user_paths, None)
    assert len(paths) == 1
    assert paths[0]["path"] == str(real)
