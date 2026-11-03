"""
窗口边界检查和自动调整工具
用于多显示器环境下防止窗口移出可视区域

注意：所有函数必须在主 UI 线程中调用，不能在后台线程中调用。
"""

import ctypes
import ctypes.wintypes as wintypes
import os
from typing import Tuple, Optional
from backend.src.utils.logger import app_logger as logger


# ============================================================================
# Windows 结构体定义
# ============================================================================

class RECT(ctypes.Structure):
    """Windows RECT 结构体"""
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class MONITORINFO(ctypes.Structure):
    """Windows MONITORINFO 结构体"""
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", ctypes.c_ulong),
    ]


class POINT(ctypes.Structure):
    """Windows POINT 结构体"""
    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
    ]


# ============================================================================
# Win32 API 类型安全定义（64位系统兼容）
# 
# 重要：使用 ctypes.WinDLL 创建单独的 user32 实例，而不是使用 windll.user32
# 因为 windll.user32 是全局单例，设置 argtypes 会影响所有使用它的代码（包括 pywebview）
# ============================================================================

_user32 = ctypes.WinDLL("user32")

# MonitorFromWindow
_user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
_user32.MonitorFromWindow.restype = wintypes.HMONITOR

# MonitorFromPoint
_user32.MonitorFromPoint.argtypes = [POINT, wintypes.DWORD]
_user32.MonitorFromPoint.restype = wintypes.HMONITOR

# GetMonitorInfoW
_user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
_user32.GetMonitorInfoW.restype = wintypes.BOOL

# GetWindowRect
_user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
_user32.GetWindowRect.restype = wintypes.BOOL

# GetCursorPos
_user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
_user32.GetCursorPos.restype = wintypes.BOOL

# SetWindowPos
_user32.SetWindowPos.argtypes = [
    wintypes.HWND,      # hWnd
    wintypes.HWND,      # hWndInsertAfter
    ctypes.c_int,       # X
    ctypes.c_int,       # Y
    ctypes.c_int,       # cx
    ctypes.c_int,       # cy
    wintypes.UINT       # uFlags
]
_user32.SetWindowPos.restype = wintypes.BOOL

# FindWindowW
_user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
_user32.FindWindowW.restype = wintypes.HWND

# EnumWindows / 窗口归属查询（按进程筛选窗口）
_enum_windows_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
_user32.EnumWindows.argtypes = [_enum_windows_proc, wintypes.LPARAM]
_user32.EnumWindows.restype = wintypes.BOOL
_user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_user32.GetWindowThreadProcessId.restype = wintypes.DWORD
_user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
_user32.GetWindowTextLengthW.restype = ctypes.c_int
_user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_user32.GetWindowTextW.restype = ctypes.c_int

# ShowWindow
_user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.ShowWindow.restype = wintypes.BOOL


# ============================================================================
# 核心函数
# ============================================================================

def get_monitor_info(hwnd: int) -> Optional[dict]:
    """
    获取窗口所在显示器的信息
    
    关键：使用 MonitorFromWindow 获取窗口所在的显示器，
    而不是主显示器。这是多显示器支持的核心。
    
    Args:
        hwnd: 窗口句柄
        
    Returns:
        dict: {
            "monitor_rect": (left, top, right, bottom),  # 显示器完整区域
            "work_rect": (left, top, right, bottom),     # 工作区（排除任务栏）
            "is_primary": bool                            # 是否主显示器
        }
    """
    try:
        # 获取窗口所在的显示器（MONITOR_DEFAULTTONEAREST = 2）
        hmonitor = _user32.MonitorFromWindow(hwnd, 2)
        
        if not hmonitor:
            logger.warning("[WindowBounds] MonitorFromWindow 返回空")
            return None
        
        # 获取显示器信息
        monitor_info = MONITORINFO()
        monitor_info.cbSize = ctypes.sizeof(MONITORINFO)
        
        if not _user32.GetMonitorInfoW(hmonitor, ctypes.byref(monitor_info)):
            logger.warning("[WindowBounds] GetMonitorInfoW 失败")
            return None
        
        return {
            "monitor_rect": (
                monitor_info.rcMonitor.left,
                monitor_info.rcMonitor.top,
                monitor_info.rcMonitor.right,
                monitor_info.rcMonitor.bottom,
            ),
            "work_rect": (
                monitor_info.rcWork.left,
                monitor_info.rcWork.top,
                monitor_info.rcWork.right,
                monitor_info.rcWork.bottom,
            ),
            "is_primary": bool(monitor_info.dwFlags & 1),  # MONITORINFOF_PRIMARY = 1
        }
    except Exception as e:
        logger.error(f"[WindowBounds] 获取显示器信息失败: {e}")
        return None


def get_window_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
    """
    获取窗口的当前位置和尺寸
    
    Args:
        hwnd: 窗口句柄
        
    Returns:
        Tuple[int, int, int, int]: (left, top, right, bottom)
    """
    try:
        rect = RECT()
        
        if _user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return (rect.left, rect.top, rect.right, rect.bottom)
        
        return None
    except Exception as e:
        logger.error(f"[WindowBounds] 获取窗口矩形失败: {e}")
        return None


def check_and_fix_window_bounds(hwnd: int, dpi_scale: float = 1.0) -> bool:
    """
    检查窗口是否超出当前显示器边界，并自动调整
    
    这是核心修复函数，会：
    1. 获取窗口当前位置
    2. 获取窗口所在显示器的工作区
    3. 检查窗口是否超出边界
    4. 自动调整窗口位置和尺寸
    
    注意：此函数必须在主 UI 线程中调用！
    
    Args:
        hwnd: 窗口句柄
        dpi_scale: DPI 缩放因子
        
    Returns:
        bool: 是否进行了调整
    """
    try:
        # 获取窗口当前位置
        window_rect = get_window_rect(hwnd)
        if not window_rect:
            logger.warning("[WindowBounds] 无法获取窗口位置")
            return False
        
        win_left, win_top, win_right, win_bottom = window_rect
        win_width = win_right - win_left
        win_height = win_bottom - win_top
        
        logger.debug(f"[WindowBounds] 窗口当前位置: ({win_left}, {win_top}, {win_right}, {win_bottom})")
        logger.debug(f"[WindowBounds] 窗口尺寸: {win_width}x{win_height}")
        
        # 获取窗口所在显示器信息
        monitor_info = get_monitor_info(hwnd)
        if not monitor_info:
            logger.warning("[WindowBounds] 无法获取显示器信息，跳过边界检查")
            return False
        
        work_rect = monitor_info["work_rect"]
        work_left, work_top, work_right, work_bottom = work_rect
        work_width = work_right - work_left
        work_height = work_bottom - work_top
        
        logger.debug(f"[WindowBounds] 工作区: ({work_left}, {work_top}, {work_right}, {work_bottom})")
        logger.debug(f"[WindowBounds] 工作区尺寸: {work_width}x{work_height}")
        
        # 检查窗口是否超出工作区
        needs_fix = False
        new_left = win_left
        new_top = win_top
        new_width = win_width
        new_height = win_height
        
        # 检查宽度是否超出
        if win_width > work_width:
            new_width = work_width
            needs_fix = True
            logger.info(f"[WindowBounds] 窗口宽度超出工作区，调整: {win_width} -> {new_width}")
        
        # 检查高度是否超出
        if win_height > work_height:
            new_height = work_height
            needs_fix = True
            logger.info(f"[WindowBounds] 窗口高度超出工作区，调整: {win_height} -> {new_height}")
        
        # 检查左边界
        if win_left < work_left:
            new_left = work_left
            needs_fix = True
            logger.info(f"[WindowBounds] 窗口左边界超出，调整: {win_left} -> {new_left}")
        
        # 检查右边界
        if win_right > work_right:
            new_left = work_right - new_width
            needs_fix = True
            logger.info(f"[WindowBounds] 窗口右边界超出，调整左边界: {win_left} -> {new_left}")
        
        # 检查上边界
        if win_top < work_top:
            new_top = work_top
            needs_fix = True
            logger.info(f"[WindowBounds] 窗口上边界超出，调整: {win_top} -> {new_top}")
        
        # 检查下边界
        if win_bottom > work_bottom:
            new_top = work_bottom - new_height
            needs_fix = True
            logger.info(f"[WindowBounds] 窗口下边界超出，调整上边界: {win_top} -> {new_top}")
        
        # 如果需要调整，执行调整
        if needs_fix:
            # SWP_NOZORDER = 0x0004, SWP_SHOWWINDOW = 0x0040
            flags = 0x0044
            _user32.SetWindowPos(hwnd, None, new_left, new_top, new_width, new_height, flags)
            
            logger.info(f"[WindowBounds] 窗口位置已调整: ({new_left}, {new_top}, {new_width}x{new_height})")
            return True
        
        logger.debug("[WindowBounds] 窗口位置正常，无需调整")
        return False
        
    except Exception as e:
        logger.error(f"[WindowBounds] 边界检查和调整失败: {e}", exc_info=True)
        return False


def reset_window_to_center(hwnd: int, default_width: int = 1680, default_height: int = 1080) -> bool:
    """
    将窗口重置到当前显示器中心，并恢复默认尺寸
    
    用于用户手动恢复窗口位置。
    同时重置窗口大小，解决窗口尺寸大于目标屏幕的问题。
    
    注意：此函数必须在主 UI 线程中调用！
    
    Args:
        hwnd: 窗口句柄
        default_width: 默认窗口宽度
        default_height: 默认窗口高度
        
    Returns:
        bool: 是否成功
    """
    try:
        # 获取窗口所在显示器信息
        monitor_info = get_monitor_info(hwnd)
        if not monitor_info:
            logger.warning("[WindowBounds] 无法获取显示器信息")
            return False
        
        work_rect = monitor_info["work_rect"]
        work_left, work_top, work_right, work_bottom = work_rect
        work_width = work_right - work_left
        work_height = work_bottom - work_top
        
        # 确保默认尺寸不超过工作区
        final_width = min(default_width, work_width)
        final_height = min(default_height, work_height)
        
        # 计算居中位置
        new_left = work_left + (work_width - final_width) // 2
        new_top = work_top + (work_height - final_height) // 2
        
        # 确保窗口不会超出边界
        new_left = max(work_left, min(new_left, work_right - final_width))
        new_top = max(work_top, min(new_top, work_bottom - final_height))
        
        # SWP_NOZORDER = 0x0004, SWP_SHOWWINDOW = 0x0040
        flags = 0x0044
        _user32.SetWindowPos(hwnd, None, new_left, new_top, final_width, final_height, flags)
        
        logger.info(f"[WindowBounds] 窗口已重置: 位置({new_left}, {new_top}), 尺寸{final_width}x{final_height}")
        return True
        
    except Exception as e:
        logger.error(f"[WindowBounds] 重置窗口位置失败: {e}", exc_info=True)
        return False


def _find_own_window_by_title(title: str, exclude: Tuple[str, ...]) -> Optional[int]:
    """在本进程创建的顶层窗口里按标题查找句柄，找不到返回 None。

    不能直接用 FindWindowW：任务栏会为应用另建一个
    Windows.Internal.Shell.TabProxyWindow，它同样携带窗口标题且 Z 序更靠前，
    拿它当主窗口会让后续的样式/位置/消息调用全部静默打在别人的窗口上。
    """
    own_pid = os.getpid()
    matches = []

    @_enum_windows_proc
    def callback(hwnd, _lparam):
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value != own_pid:
            return True

        length = _user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True

        buffer = ctypes.create_unicode_buffer(length + 1)
        _user32.GetWindowTextW(hwnd, buffer, length + 1)
        window_title = buffer.value
        if window_title.startswith(title) and not any(x in window_title for x in exclude):
            matches.append((int(hwnd or 0), window_title))
        return True

    _user32.EnumWindows(callback, 0)

    for hwnd, window_title in matches:
        if hwnd and window_title == title:
            return hwnd
    return matches[0][0] if matches and matches[0][0] else None


def find_window_by_title(
    title: str,
    max_retries: int = 10,
    retry_interval: float = 0.2,
    exclude: Tuple[str, ...] = ("Floating",),
) -> Optional[int]:
    """
    通过窗口标题查找本进程的窗口句柄（带重试机制）

    只做 Win32 只读查询，不触碰 WinForms 对象，因此可以在后台线程中调用。

    Args:
        title: 窗口标题
        max_retries: 最大重试次数
        retry_interval: 重试间隔（秒）
        exclude: 标题需排除的子串，默认排除悬浮窗

    Returns:
        Optional[int]: 窗口句柄，如果未找到返回 None
    """
    try:
        import time

        for attempt in range(max_retries):
            hwnd = _find_own_window_by_title(title, exclude)

            if hwnd:
                logger.debug(f"[WindowBounds] 找到窗口 '{title}': {hwnd} (尝试 {attempt + 1}/{max_retries})")
                return hwnd

            time.sleep(retry_interval)

        logger.warning(f"[WindowBounds] 未找到窗口 '{title}' (尝试 {max_retries} 次)")
        return None

    except Exception as e:
        logger.error(f"[WindowBounds] 查找窗口失败: {e}")
        return None
