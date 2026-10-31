"""应用图标构建工具

把一张正方形源图转换为项目所需的两份图标产物：
- 多尺寸 .ico：窗口图标与 PyInstaller 打包图标
- 512px .png：系统托盘图标

单独抽成模块是为了可测试，命令行入口见 scripts/set_app_icon.py。
"""

from pathlib import Path
from typing import Iterable, Sequence, Tuple

from PIL import Image

# Windows 资源管理器与任务栏实际会用到的尺寸
DEFAULT_ICO_SIZES: Tuple[int, ...] = (16, 24, 32, 48, 64, 128, 256)
DEFAULT_PNG_SIZE = 512


def _load_square(source: Path) -> Image.Image:
    """读取源图并统一为正方形 RGBA"""
    if not source.exists():
        raise FileNotFoundError(f"源图不存在: {source}")

    image = Image.open(source).convert("RGBA")
    if image.width != image.height:
        # 非正方形时居中裁成正方形，避免图标变形
        side = min(image.width, image.height)
        left = (image.width - side) // 2
        top = (image.height - side) // 2
        image = image.crop((left, top, left + side, top + side))
    return image


def build_app_icons(
    source: Path,
    ico_path: Path,
    png_path: Path,
    ico_sizes: Iterable[int] = DEFAULT_ICO_SIZES,
    png_size: int = DEFAULT_PNG_SIZE,
) -> Tuple[Path, Path]:
    """
    由源图生成 ico 与 png

    Args:
        source: 源图路径（建议 1024px 以上正方形）
        ico_path: 输出的 .ico 路径
        png_path: 输出的 .png 路径
        ico_sizes: ico 内包含的尺寸集合
        png_size: png 边长

    Returns:
        (ico_path, png_path)
    """
    image = _load_square(source)

    ico_path.parent.mkdir(parents=True, exist_ok=True)
    png_path.parent.mkdir(parents=True, exist_ok=True)

    sizes: Sequence[Tuple[int, int]] = [(s, s) for s in ico_sizes]
    image.save(ico_path, format="ICO", sizes=sizes)

    image.resize((png_size, png_size), Image.LANCZOS).save(png_path, format="PNG")

    return ico_path, png_path


def describe_ico(ico_path: Path) -> list:
    """读取 ico 内含尺寸，用于校验"""
    with Image.open(ico_path) as image:
        sizes = image.info.get("sizes")
        if sizes:
            return sorted({size[0] for size in sizes})
        return [image.width]
