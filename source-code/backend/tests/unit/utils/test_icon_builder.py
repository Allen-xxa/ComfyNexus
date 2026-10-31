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

from backend.src.utils.icon_builder import build_app_icons, describe_ico  # noqa: E402


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
