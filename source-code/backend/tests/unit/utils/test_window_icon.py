"""窗口图标 / AppUserModelID 工具测试

对应缺陷：pywebview 6.2.1 的 edgechromium 后端未实现 icon 参数，
导致开发模式下任务栏显示 python.exe 的默认图标。
"""

import sys
from pathlib import Path

import pytest

_BACKEND_DIR = Path(__file__).resolve().parents[3]
_SOURCE_ROOT = _BACKEND_DIR.parent
for _p in (str(_BACKEND_DIR), str(_SOURCE_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.src.utils import window_icon  # noqa: E402

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="仅在 Windows 上有意义"
)

PROJECT_ICO = _SOURCE_ROOT / "icon.ico"


def test_设置AppUserModelID成功且可重复调用():
    assert window_icon.set_app_user_model_id() is True
    # 第二次应直接命中缓存并返回 True，不应报错
    assert window_icon.set_app_user_model_id() is True


def test_图标文件不存在时返回False(tmp_path):
    assert window_icon.apply_window_icon(1, tmp_path / "missing.ico") is False


def test_窗口句柄为空时返回False():
    assert window_icon.apply_window_icon(0, PROJECT_ICO) is False


def test_未找到窗口时返回False():
    assert (
        window_icon.apply_icon_to_window_by_title(
            "__不存在的窗口标题__", PROJECT_ICO, retries=1, interval=0
        )
        is False
    )


def test_能加载项目自带ico():
    assert PROJECT_ICO.is_file(), "项目根目录应存在 icon.ico"
    handle = window_icon._load_icon(PROJECT_ICO, 32)
    assert handle != 0, "LoadImageW 应能从 icon.ico 加载出图标句柄"


def test_读取空句柄返回0():
    assert window_icon.get_window_icon_handle(0) == 0
