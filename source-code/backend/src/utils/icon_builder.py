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
from typing import Iterable, Optional, Sequence, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter

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


def dim_near_white(
    image: Image.Image,
    factor: float = 0.84,
    min_luma: int = 200,
    max_saturation: int = 18,
) -> Image.Image:
    """把接近纯白、低饱和的区域整体压暗一档。

    为什么需要：本项目图标主体（齿轮）是白色。抠掉白底后，在 Windows 浅色主题的
    任务栏（约 #F3F3F3）上白色主体没有对比度，只剩中间的黄色 C 可见。
    压暗一档后深浅背景下都能看清，且不改变设计结构。

    Args:
        image: 输入图（RGBA）
        factor: 亮度系数，1.0 表示不变，越小越暗
        min_luma: 亮度高于此值的像素才参与压暗
        max_saturation: 饱和度低于此值的像素才参与压暗（避免把彩色部分一起压暗）

    Returns:
        新的 RGBA 图像
    """
    if factor >= 1.0:
        return image

    image = image.convert("RGBA")
    rgb = image.convert("RGB")
    r, g, b = rgb.split()

    brightest = ImageChops.lighter(ImageChops.lighter(r, g), b)
    darkest = ImageChops.darker(ImageChops.darker(r, g), b)
    saturation = ImageChops.subtract(brightest, darkest)

    # 两个条件同时成立才压暗：够亮 且 够灰
    bright_mask = brightest.point(lambda v: 255 if v > min_luma else 0)
    gray_mask = saturation.point(lambda v: 255 if v < max_saturation else 0)
    mask = ImageChops.multiply(bright_mask, gray_mask)

    dimmed = ImageEnhance.Brightness(rgb).enhance(factor)

    # 注意：不能直接对 RGBA 图 paste(..., mask)。PIL 在带 mask 的 paste 里会连
    # alpha 通道一起混合，透明像素会被刷成不透明。这里只在 RGB 上合成，
    # 再把原始 alpha 原封不动贴回去。
    out_rgb = rgb.copy()
    out_rgb.paste(dimmed, (0, 0), mask)

    result = out_rgb.convert("RGBA")
    result.putalpha(image.getchannel("A"))
    return result


def build_app_icons(
    source: Path,
    ico_path: Path,
    png_path: Path,
    ico_sizes: Iterable[int] = DEFAULT_ICO_SIZES,
    png_size: int = DEFAULT_PNG_SIZE,
    transparent: bool = False,
    tolerance: int = 10,
    dim_whites: Optional[float] = None,
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
        dim_whites: 近白色主体的压暗系数（如 0.84），None 表示不处理

    Returns:
        (ico_path, png_path)
    """
    image = _load_square(source)
    if transparent:
        image = make_background_transparent(image, tolerance=tolerance)
    if dim_whites is not None:
        image = dim_near_white(image, factor=dim_whites)

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
