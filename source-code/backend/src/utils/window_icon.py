"""Windows 任务栏图标修正。

背景
----
pywebview 6.2.1 只有 ``winforms`` 后端会读取 ``icon`` 参数并设置 ``Form.Icon``，
而本项目使用的是 ``edgechromium`` 后端，该后端**完全没有实现 icon 参数**
（在 ``webview/platforms/edgechromium.py`` 中检索不到任何 icon 处理）。

结果是：开发模式下窗口没有显式图标，Windows 回退到宿主进程的图标，
任务栏与标题栏都显示 ``python.exe`` 的默认图标。

本模块用 Win32 API 补齐两件事：

1. ``set_app_user_model_id`` —— 设置进程级 AppUserModelID。
   未设置时 Windows 会把窗口归到 ``python.exe`` 的任务栏分组，图标同样取自它。
2. ``apply_window_icon`` —— 通过 ``WM_SETICON`` 向窗口写入大/小图标。

两者配合使用，顺序为：**先设置 AppUserModelID，再在窗口创建后设置图标**。
"""

from __future__ import annotations

import ctypes
import logging
import time
from ctypes import wintypes
from pathlib import Path

# 与 dotnet_runtime 等运行时模块保持一致，挂到主日志器上，
# 否则 __name__ 命名器没有 handler，日志会被静默丢弃。
logger = logging.getLogger("ComfyNexus")

# 应用在任务栏中的唯一标识，格式建议为 CompanyName.Product[.SubProduct]
APP_USER_MODEL_ID = "ComfyNexus.Desktop"

WM_SETICON = 0x0080
WM_GETICON = 0x007F

ICON_SMALL = 0
ICON_BIG = 1
ICON_SMALL2 = 2

IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010

SM_CXICON = 11
SM_CYICON = 12
SM_CXSMICON = 49
SM_CYSMICON = 50

# 保存已加载的图标句柄，避免被释放后窗口失去图标
_ICON_HANDLES: list[int] = []
_AUMID_APPLIED = False

if hasattr(ctypes, "WinDLL"):
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _shell32 = ctypes.WinDLL("shell32", use_last_error=True)

    _shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [wintypes.LPCWSTR]
    _shell32.SetCurrentProcessExplicitAppUserModelID.restype = ctypes.c_long

    _user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    _user32.FindWindowW.restype = wintypes.HWND

    _user32.LoadImageW.argtypes = [
        wintypes.HINSTANCE,
        wintypes.LPCWSTR,
        wintypes.UINT,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    _user32.LoadImageW.restype = wintypes.HANDLE

    _user32.SendMessageW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    _user32.SendMessageW.restype = wintypes.LPARAM

    _user32.GetSystemMetrics.argtypes = [ctypes.c_int]
    _user32.GetSystemMetrics.restype = ctypes.c_int
else:  # 非 Windows 平台，保持可导入
    _user32 = None
    _shell32 = None


def set_app_user_model_id(app_id: str = APP_USER_MODEL_ID) -> bool:
    """设置进程级 AppUserModelID。

    必须在创建任何窗口之前调用。重复调用是安全的。
    """
    global _AUMID_APPLIED

    if _shell32 is None:
        return False
    if _AUMID_APPLIED:
        return True

    try:
        hr = _shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        if hr != 0:
            logger.warning(f"[窗口图标] 设置 AppUserModelID 失败，HRESULT=0x{hr & 0xFFFFFFFF:08X}")
            return False
        _AUMID_APPLIED = True
        logger.info(f"[窗口图标] 已设置 AppUserModelID: {app_id}")
        return True
    except Exception as e:  # pragma: no cover - 平台相关
        logger.warning(f"[窗口图标] 设置 AppUserModelID 异常: {e}")
        return False


def _load_icon(path: Path, size: int) -> int:
    """从 .ico 文件加载指定尺寸的图标，返回句柄（0 表示失败）。"""
    handle = _user32.LoadImageW(
        None,
        str(path),
        IMAGE_ICON,
        size,
        size,
        LR_LOADFROMFILE,
    )
    return int(handle or 0)


def apply_window_icon(hwnd: int, ico_path: str | Path) -> bool:
    """向指定窗口写入大/小图标。

    Args:
        hwnd: 目标窗口句柄
        ico_path: .ico 文件路径

    Returns:
        是否至少成功设置了图标
    """
    if _user32 is None or not hwnd:
        return False

    path = Path(ico_path)
    if not path.is_file():
        logger.warning(f"[窗口图标] 图标文件不存在: {path}")
        return False

    try:
        big_size = _user32.GetSystemMetrics(SM_CXICON) or 32
        small_size = _user32.GetSystemMetrics(SM_CXSMICON) or 16

        big = _load_icon(path, big_size)
        small = _load_icon(path, small_size)

        if big:
            _ICON_HANDLES.append(big)
            _user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, big)
        if small:
            _ICON_HANDLES.append(small)
            _user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, small)
            _user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL2, small)

        if not big and not small:
            logger.warning(f"[窗口图标] LoadImage 失败，无法加载: {path}")
            return False

        logger.info(f"[窗口图标] 已应用到窗口 hwnd={hwnd}（big={big_size}px, small={small_size}px）")
        return True
    except Exception as e:  # pragma: no cover - 平台相关
        logger.warning(f"[窗口图标] 应用图标异常: {e}")
        return False


def apply_icon_to_window_by_title(
    title: str,
    ico_path: str | Path,
    retries: int = 10,
    interval: float = 0.1,
) -> bool:
    """按窗口标题查找窗口并设置图标（用于拿不到窗口对象的场景）。

    窗口可能尚未创建，因此带重试。
    """
    if _user32 is None:
        return False

    hwnd = 0
    for _ in range(max(1, retries)):
        hwnd = int(_user32.FindWindowW(None, title) or 0)
        if hwnd:
            break
        time.sleep(interval)

    if not hwnd:
        logger.warning(f"[窗口图标] 未找到标题为 {title!r} 的窗口")
        return False

    return apply_window_icon(hwnd, ico_path)


def get_window_icon_handle(hwnd: int, big: bool = True) -> int:
    """读取窗口当前的大/小图标句柄，用于自检。"""
    if _user32 is None or not hwnd:
        return 0
    try:
        which = ICON_BIG if big else ICON_SMALL
        return int(_user32.SendMessageW(hwnd, WM_GETICON, which, 0) or 0)
    except Exception:  # pragma: no cover
        return 0
