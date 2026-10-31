"""搜索代理解析

搜索引擎（尤其 DuckDuckGo / Tavily）在境内直连会超时，
需要复用应用自身的代理配置：优先使用系统设置里的代理，
未启用时回退到 Windows 系统代理。
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_proxy_url() -> str:
    """
    获取可用代理地址

    Returns:
        str: 形如 http://127.0.0.1:7890 的代理地址；无可用代理时返回空串
    """
    # 1. 应用内代理设置优先
    try:
        from backend.src.core.settings_manager import SettingsManager

        result = SettingsManager().get_settings()
        settings = (result or {}).get("settings") or {}
        proxy = settings.get("proxy") or {}
        if proxy.get("enabled") and proxy.get("host"):
            port = proxy.get("port") or "80"
            return f"http://{proxy['host']}:{port}"
    except Exception as e:
        logger.debug(f"[ProxyResolver] 读取应用代理设置失败: {e}")

    # 2. 回退到系统代理
    try:
        from backend.src.core.system_proxy_manager import SystemProxyManager

        sys_proxy = SystemProxyManager().get_system_proxy()
        if sys_proxy.get("success") and sys_proxy.get("enabled") and sys_proxy.get("host"):
            if sys_proxy.get("url"):
                return sys_proxy["url"]
            port = sys_proxy.get("port") or "80"
            return f"http://{sys_proxy['host']}:{port}"
    except Exception as e:
        logger.debug(f"[ProxyResolver] 读取系统代理失败: {e}")

    return ""


def resolve_proxy(explicit: Optional[str] = None) -> str:
    """允许调用方显式指定代理，否则走自动解析"""
    if explicit:
        return explicit
    return get_proxy_url()
