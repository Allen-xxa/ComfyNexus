"""应用图标构建工具

把一张正方形源图转换为项目所需的两份图标产物：
- 多尺寸 .ico：窗口图标与 PyInstaller 打包图标
- 512px .png：系统托盘图标

单独抽成模块是为了可测试，命令行入口见 scripts/set_app_icon.py。

关于透明背景
------------
AI 出图的图标通常是纯白不透明背景，直接做成 .ico 后任务栏会显示成一个白方块。
`make_background_transparent` 负责把外侧背景抠掉。

注意不能简单地"把白色变透明"：本项目的齿轮主体本身就是近白色（约 #F0F0F0），
只比背景深十级左右，全局阈值会把齿轮一起抹掉。因此这里只删除**与图像边缘连通**
的背景区域，齿轮内部、字母 C 的镂空等封闭白色区域会被保留。
"""

from pathlib import Path
from typing import Iterable, Sequence, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageFilter

# Windows 资源管理器与任务栏实际会用到的尺寸
DEFAULT_ICO_SIZES: Tuple[int, ...] = (16, 24, 32, 48, 64, 128, 256)
DEFAULT_PNG_SIZE = 512

# 抠图前先把源图缩到这个边长，兼顾边缘质量与速度
_WORK_SIZE = 1024


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


def _corner_background(image: Image.Image) -> Tuple[int, int, int]:
    """取四条边像素的中位数作为背景色估计"""
    rgb = image.convert("RGB")
    width, height = rgb.size
    samples = []
    step = max(1, width // 64)
    for x in range(0, width, step):
        samples.append(rgb.getpixel((x, 0)))
        samples.append(rgb.getpixel((x, height - 1)))
    for y in range(0, height, step):
        samples.append(rgb.getpixel((0, y)))
        samples.append(rgb.getpixel((width - 1, y)))

    channels = list(zip(*samples))
    return tuple(sorted(channel)[len(channel) // 2] for channel in channels)  # type: ignore[return-value]


def make_background_transparent(
    image: Image.Image,
    tolerance: int = 10,
    feather: float = 0.8,
) -> Image.Image:
    """把与图像边缘连通的纯色背景抠成透明。

    Args:
        image: 输入图（RGBA）
        tolerance: 与背景色的最大通道差，越大抠得越狠
        feather: 对 alpha 做的高斯模糊半径，用于柔化边缘（0 表示不柔化）

    Returns:
        新的 RGBA 图像。若输入已经带透明通道则原样返回。
    """
    image = image.convert("RGBA")

    # 已有透明信息就不动它，避免二次处理把边缘吃掉
    if image.getchannel("A").getextrema()[0] < 255:
        return image

    work = image.resize((_WORK_SIZE, _WORK_SIZE), Image.LANCZOS)
    rgb = work.convert("RGB")
    bg = _corner_background(work)

    # 每个通道与背景色的差值，取三者最大 → 灰度"像不像背景"
    diff = ImageChops.difference(rgb, Image.new("RGB", rgb.size, bg))
    r, g, b = diff.split()
    near_bg = ImageChops.lighter(ImageChops.lighter(r, g), b).point(
        lambda v: 255 if v < tolerance else 0
    )

    # 只保留与边缘连通的背景：从四角分别灌色，封闭区域（齿轮内部、C 的镂空）不受影响
    mask = near_bg.copy()
    width, height = mask.size
    for seed in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)):
        if mask.getpixel(seed) == 255:
            ImageDraw.floodfill(mask, seed, 128, thresh=0)

    alpha = mask.point(lambda v: 0 if v == 128 else 255)
    if feather > 0:
        alpha = alpha.filter(ImageFilter.GaussianBlur(feather))

    # alpha 是在 _WORK_SIZE 上算的，缩回原尺寸再合成
    alpha = alpha.resize(image.size, Image.LANCZOS)
    result = image.copy()
    result.putalpha(alpha)
    return result


def build_app_icons(
    source: Path,
    ico_path: Path,
    png_path: Path,
    ico_sizes: Iterable[int] = DEFAULT_ICO_SIZES,
    png_size: int = DEFAULT_PNG_SIZE,
    transparent: bool = False,
    tolerance: int = 10,
) -> Tuple[Path, Path]:
    """
    由源图生成 ico 与 png

    Args:
        source: 源图路径（建议 1024px 以上正方形）
        ico_path: 输出的 .ico 路径
        png_path: 输出的 .png 路径
        ico_sizes: ico 内包含的尺寸集合
        png_size: png 边长
        transparent: 是否把纯色背景抠成透明
        tolerance: 抠图容差，仅 transparent 为 True 时生效

    Returns:
        (ico_path, png_path)
    """
    image = _load_square(source)
    if transparent:
        image = make_background_transparent(image, tolerance=tolerance)

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
