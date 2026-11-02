"""
网络代理解析工具

统一决定"这次请求该走哪条链路"，供插件市场、依赖下载等模块复用。

背景：
    VPN / Clash / V2Ray 这类客户端开启"系统代理"后，只写 Windows 注册表
    （Internet Settings 的 ProxyEnable / ProxyServer），并不会设置
    HTTP_PROXY / HTTPS_PROXY 环境变量。Python 的 requests 默认只读环境变量，
    因此会出现"浏览器能打开 GitHub，应用内请求全部超时"的现象。

策略：
    应用内代理（设置项 proxy.enabled）优先；
    未配置时回退到系统代理；
    都不行就直连（TUN 模式 / 无需代理的网络）。
"""

import os
from typing import List, Optional

from backend.src.utils.logger import app_logger as logger


def get_app_proxy(settings_manager=None) -> Optional[str]:
    """
    读取应用设置里的代理

    Args:
        settings_manager: 设置管理器，None 时自行创建

    Returns:
        "http://host:port"，未启用或配置不完整时返回 None
    """
    try:
        if settings_manager is None:
            from backend.src.core.settings_manager import SettingsManager

            settings_manager = SettingsManager()

        result = settings_manager.get_settings()
        if not result.get("success"):
            return None

        proxy = (result.get("settings") or {}).get("proxy") or {}
        if not proxy.get("enabled"):
            return None

        host = str(proxy.get("host", "")).strip()
        port = str(proxy.get("port", "")).strip()
        if not host or not port:
            return None

        return f"http://{host}:{port}"
    except Exception as e:
        logger.debug(f"[ProxyHelper] 读取应用代理失败: {e}")
        return None


def get_system_proxy() -> Optional[str]:
    """
    读取系统代理

    先查 Windows 注册表，再退回环境变量（macOS / Linux 主要靠后者）。

    Returns:
        代理 URL，未启用时返回 None
    """
    try:
        from backend.src.core.system_proxy_manager import SystemProxyManager

        info = SystemProxyManager().get_system_proxy()
        if info.get("success") and info.get("enabled") and info.get("host"):
            url = info.get("url") or f"http://{info['host']}:{info.get('port', '')}"
            if url.strip():
                return url
    except Exception as e:
        logger.debug(f"[ProxyHelper] 读取 Windows 系统代理失败: {e}")

    for key in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        value = os.environ.get(key, "").strip()
        if value:
            return value

    return None


def get_proxy_candidates(settings_manager=None) -> List[Optional[str]]:
    """
    按优先级返回代理候选列表

    Returns:
        [应用代理?, 系统代理?, None]，最后一项固定为 None 表示直连
    """
    candidates: List[Optional[str]] = []

    for url in (get_app_proxy(settings_manager), get_system_proxy()):
        if url and url not in candidates:
            candidates.append(url)

    candidates.append(None)
    return candidates


def describe_candidates(settings_manager=None) -> str:
    """生成用于日志的可读描述"""
    names = []
    for url in get_proxy_candidates(settings_manager):
        names.append(url if url else "直连")
    return " → ".join(names)
