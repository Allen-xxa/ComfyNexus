"""LoRA 扫描路径解析

LoRA 管理页原先只扫描用户在页面上显式添加的目录，因此
ComfyUI 通过 extra_model_paths.yaml 扩展出来的 LoRA 目录完全不可见。

本模块负责把三类来源合并成一份扫描路径列表：
1. 用户在 LoRA 管理中配置的目录（优先级最高，保留其分类设置）
2. ComfyUI 默认的 <comfyui>/models/loras
3. extra_model_paths.yaml 中每个配置节声明的 loras 目录

YAML 中 loras 的取值可以是：
- 相对路径（相对于同节的 base_path，或相对于 YAML 所在目录）
- 绝对路径
- 多行字符串，每行一个子路径
- 含 {base_path} 占位符的路径
"""

from pathlib import Path
from typing import Dict, List, Optional

import yaml

from ...utils.logger import app_logger as logger

LORA_KEYS = ("loras", "lora")


def _is_absolute(raw: str) -> bool:
    """判断是否为绝对路径（兼容 Windows 盘符与 POSIX 根路径）"""
    if not raw:
        return False
    if raw.startswith(("/", "\\")):
        return True
    return len(raw) > 1 and raw[1] == ":"


def _split_values(value) -> List[str]:
    """把 loras 字段拆成多个路径项，支持多行字符串与列表"""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        items: List[str] = []
        for entry in value:
            items.extend(_split_values(entry))
        return items
    text = str(value)
    return [line.strip() for line in text.splitlines() if line.strip()]


def _resolve(base_path: str, item: str) -> str:
    """把单个路径项解析为绝对路径"""
    if "{base_path}" in item:
        return item.replace("{base_path}", base_path)
    if _is_absolute(item):
        return item
    if base_path:
        return str(Path(base_path) / item)
    return item


def resolve_extra_lora_dirs(yaml_path: Path) -> List[str]:
    """
    解析 extra_model_paths.yaml 中所有 loras 目录

    Args:
        yaml_path: YAML 文件路径

    Returns:
        List[str]: 绝对路径列表（未去重，未校验存在性）
    """
    if not yaml_path or not yaml_path.exists():
        return []

    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"解析 extra_model_paths.yaml 失败: {e}")
        return []

    if not isinstance(data, dict):
        return []

    yaml_dir = str(yaml_path.parent)
    result: List[str] = []

    for section_name, section in data.items():
        if not isinstance(section, dict):
            continue

        base_path = str(section.get("base_path") or "").strip()
        if base_path and not _is_absolute(base_path):
            base_path = str(Path(yaml_dir) / base_path)

        for key in LORA_KEYS:
            if key not in section:
                continue
            for item in _split_values(section.get(key)):
                resolved = _resolve(base_path or yaml_dir, item)
                result.append(resolved)
            break

    return result


def _dedupe(paths: List[str]) -> List[str]:
    """按规范化路径去重（Windows 下大小写不敏感）"""
    seen = set()
    unique: List[str] = []
    for raw in paths:
        if not raw:
            continue
        key = str(Path(raw)).replace("\\", "/").rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(str(Path(raw)))
    return unique


def build_scan_paths(
    user_paths: Optional[List[Dict]],
    comfyui_path: Optional[str],
    extra_yaml: Optional[str] = None,
) -> List[Dict]:
    """
    合并生成 LoRA 扫描路径列表

    Args:
        user_paths: LoRA 管理页配置的路径，格式
            [{"id": str, "path": str, "name": str, "category": str, "enabled": bool}, ...]
        comfyui_path: 当前环境的 ComfyUI 根目录
        extra_yaml: extra_model_paths.yaml 路径，缺省时取 <comfyui_path>/extra_model_paths.yaml

    Returns:
        List[Dict]: 扫描路径配置列表，字段与 LoraScanner.scan_all_paths 兼容
    """
    result: List[Dict] = []
    covered: List[str] = []

    for item in user_paths or []:
        if not isinstance(item, dict):
            continue
        if item.get("enabled") is False:
            continue
        path = item.get("path")
        if not path:
            continue
        result.append(
            {
                "id": item.get("id") or f"user:{path}",
                "path": path,
                "name": item.get("name") or Path(path).name,
                "category": item.get("category") or "uncategorized",
                "enabled": True,
            }
        )
        covered.append(path)

    if not comfyui_path:
        return result

    root = Path(comfyui_path)

    default_lora_dir = root / "models" / "loras"
    if default_lora_dir.exists():
        covered.append(str(default_lora_dir))

    yaml_path = Path(extra_yaml) if extra_yaml else root / "extra_model_paths.yaml"
    covered.extend(resolve_extra_lora_dirs(yaml_path))

    for path in _dedupe(covered):
        # 已由用户配置覆盖的目录不再重复添加（按规范化路径比较）
        key = str(Path(path)).replace("\\", "/").rstrip("/").lower()
        if any(
            str(Path(entry["path"])).replace("\\", "/").rstrip("/").lower() == key
            for entry in result
        ):
            continue
        if not Path(path).is_dir():
            continue
        result.append(
            {
                "id": f"auto:{path}",
                "path": path,
                "name": Path(path).name,
                "category": "uncategorized",
                "enabled": True,
                "auto": True,
            }
        )

    return result
