"""
系统代理管理器
用于获取系统代理配置
"""

import platform
from typing import Dict

from backend.src.utils.logger import app_logger as logger


class SystemProxyManager:
    """系统代理管理器"""
    
    def get_system_proxy(self) -> Dict:
        """
        获取 Windows 系统代理配置
        
        使用 winreg 直接读取注册表
        
        Returns:
            dict: {
                "success": bool,
                "message": str (可选),
                "enabled": bool,
                "host": str,
                "port": str
            }
        """
        try:
            if platform.system() != "Windows":
                return {
                    "success": False,
                    "message": "仅支持 Windows 系统",
                    "enabled": False,
                    "host": "",
                    "port": ""
                }
            
            import winreg
            
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
            )
            
            try:
                proxy_enable = winreg.QueryValueEx(key, "ProxyEnable")[0]
            except FileNotFoundError:
                proxy_enable = 0
            
            try:
                proxy_server = winreg.QueryValueEx(key, "ProxyServer")[0]
            except FileNotFoundError:
                proxy_server = ""
            
            winreg.CloseKey(key)
            
            logger.debug(f"[SystemProxyManager] ProxyEnable: {proxy_enable}")
            logger.debug(f"[SystemProxyManager] ProxyServer: {proxy_server}")
            
            host = ""
            port = ""
            scheme = "http"
            
            if proxy_server:
                raw = proxy_server.strip()
                # 形如 "http=127.0.0.1:7890;https=127.0.0.1:7890" 时只取 http 段
                if '=' in raw:
                    for part in raw.split(';'):
                        if part.strip().startswith('http='):
                            raw = part.split('=', 1)[1].strip()
                            break
                
                # 注册表里可能带协议前缀（如 http://127.0.0.1:29290），
                # 必须先剥离，否则按冒号切分会把 "http" 当成主机名
                if '://' in raw:
                    scheme, raw = raw.split('://', 1)
                    scheme = scheme or "http"
                
                if ':' in raw:
                    host, port = raw.rsplit(':', 1)
                else:
                    host, port = raw, "80"
                
                host = host.strip()
                port = port.strip()
            
            return {
                "success": True,
                "enabled": bool(proxy_enable),
                "host": host,
                "port": port,
                "scheme": scheme,
                "url": f"{scheme}://{host}:{port}" if host else ""
            }
            
        except Exception as e:
            logger.error(f"[SystemProxyManager] 获取系统代理失败: {str(e)}")
            return {
                "success": False,
                "message": f"获取系统代理失败: {str(e)}",
                "enabled": False,
                "host": "",
                "port": ""
            }
