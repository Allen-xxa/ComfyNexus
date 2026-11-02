"""应用图标构建测试"""

import sys
from pathlib import Path

import pytest
from PIL import Image

_BACKEND_DIR = Path(__file__).resolve().parents[3]
_SOURCE_ROOT = _BACKEND_DIR.parent
for _p in (str(_BACKEND_DIR), str(_SOURCE_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.src.utils.icon_builder import (  # noqa: E402
    build_app_icons,
    describe_ico,
    make_background_transparent,
)


@pytest.fixture
def square_source(tmp_path):
    src = tmp_path / "src.png"
    Image.new("RGBA", (1024, 1024), (250, 200, 40, 255)).save(src)
    return src


def test_生成多尺寸ico与png(square_source, tmp_path):
    ico = tmp_path / "out" / "icon.ico"
    png = tmp_path / "out" / "icon.png"

    build_app_icons(square_source, ico, png)

    assert ico.exists() and png.exists()
    assert describe_ico(ico) == [16, 24, 32, 48, 64, 128, 256]
    with Image.open(png) as image:
        assert image.size == (512, 512)


def test_非正方形源图被居中裁切(square_source, tmp_path):
    wide = tmp_path / "wide.png"
    Image.new("RGBA", (1600, 800), (10, 20, 30, 255)).save(wide)

    ico = tmp_path / "icon.ico"
    png = tmp_path / "icon.png"
    build_app_icons(wide, ico, png)

    with Image.open(png) as image:
        assert image.size == (512, 512), "非正方形源图应被裁成正方形"


def test_源图不存在时报错(tmp_path):
    with pytest.raises(FileNotFoundError):
        build_app_icons(tmp_path / "nope.png", tmp_path / "a.ico", tmp_path / "a.png")


def test_可自定义尺寸(square_source, tmp_path):
    ico = tmp_path / "icon.ico"
    png = tmp_path / "icon.png"
    build_app_icons(square_source, ico, png, ico_sizes=(32, 64), png_size=256)

    assert describe_ico(ico) == [32, 64]
    with Image.open(png) as image:
        assert image.size == (256, 256)


def _draw_ring_on_white(size=512):
    """白底 + 近白色闭合圆环 + 环内白底中心一点彩色

    复刻本项目图标的构图：主体本身接近白色，只能靠"与边缘连通"来区分背景。
    """
    from PIL import ImageDraw

    image = Image.new("RGBA", (size, size), (250, 250, 249, 255))
    draw = ImageDraw.Draw(image)
    margin = size // 6
    draw.ellipse(
        (margin, margin, size - margin, size - margin),
        fill=(240, 240, 240, 255),
        outline=(224, 224, 224, 255),
        width=6,
    )
    draw.ellipse(
        (size // 2 - 40, size // 2 - 40, size // 2 + 40, size // 2 + 40),
        fill=(240, 192, 64, 255),
    )
    return image


def test_抠图后角落透明而中心保留():
    image = _draw_ring_on_white()

    result = make_background_transparent(image)

    assert result.mode == "RGBA"
    assert result.getpixel((0, 0))[3] == 0, "外侧背景应完全透明"
    assert result.getpixel((256, 256))[3] == 255, "环内主体不应被误删"


def test_抠图不影响已带透明通道的图():
    image = Image.new("RGBA", (64, 64), (250, 250, 250, 255))
    image.putpixel((0, 0), (250, 250, 250, 0))

    result = make_background_transparent(image)

    assert result.getpixel((32, 32))[3] == 255
    assert result.getpixel((0, 0))[3] == 0


def test_容差过小时背景残留():
    image = _draw_ring_on_white()

    result = make_background_transparent(image, tolerance=0, feather=0)

    # 背景色是 (250,250,249)，容差 0 时只有完全相等的像素会被判定为背景
    hist = result.getchannel("A").histogram()
    opaque_ratio = (sum(hist) - hist[0]) / (512 * 512)
    assert opaque_ratio > 0.9, "容差过小应导致大部分背景未被抠掉"


def test_build_app_icons_透明选项(tmp_path):
    source = tmp_path / "src.png"
    _draw_ring_on_white().save(source)

    ico = tmp_path / "icon.ico"
    png = tmp_path / "icon.png"
    build_app_icons(source, ico, png, transparent=True, png_size=128)

    with Image.open(png) as image:
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0))[3] == 0
