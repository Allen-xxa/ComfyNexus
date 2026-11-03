"""
系统监控 API 控制器

提供 pywebview API 入口，用于获取系统监控数据
"""

from ...core.monitor.monitor_collector import MonitorCollector
from ...core.settings_manager import SettingsManager
from ...utils.logger import app_logger as logger


class SystemMonitorController:
    """系统监控 API 控制器"""
    
    def __init__(self):
        """初始化控制器"""
        self._collector = MonitorCollector()
        self._settings_manager = SettingsManager()
        self._floating_window_visible = False
        self._base_url = ""
        self._screen_width = 1920
        self._screen_height = 1080
        self._dpi_scale = 1.0
        
        result = self._settings_manager.get_floating_window_settings()
        if result.get("success") and result.get("settings"):
            self._floating_window_settings = result["settings"]
            self._floating_window_visible = result["settings"].get("visible", False)
        else:
            self._floating_window_settings = {
                "opacity": 75,
                "visibleItems": ["cpu", "gpu", "ram", "vram", "net", "page"],
                "itemOrder": ["cpu", "gpu", "ram", "vram", "net", "page"],
                "visible": False
            }
        
        self._collector.start()
        logger.info("Monitor collector auto-started")
    
    def get_monitor_data(self) -> dict:
        """
        获取系统监控数据
        
        Returns:
            dict: 标准响应格式
            {
                "success": bool,
                "data": {
                    "cpu": {"load": int, "temp": int, "power": int, "freq": float},
                    "gpu": {"load": int, "temp": int, "power": int, "core_clock": int},
                    "sys": {
                        "ram": {"used": float, "total": float, "percent": float},
                        "vram": {"used": float, "total": float, "percent": float},
                        "page": {"used": float, "total": float, "percent": float}
                    },
                    "net": {"up": float, "down": float},
                    "disks": [{"letter": str, "name": str, "used": int, "total": int}]
                },
                "error_message": str (仅在失败时)
            }
        """
        try:
            data = self._collector.get_data()
            return {
                "success": True,
                "data": data
            }
        except Exception as e:
            logger.error(f"Failed to get monitor data: {e}")
            return {
                "success": False,
                "error_message": str(e),
                "data": self._get_empty_data()
            }
    
    def start_monitoring(self) -> dict:
        """
        启动后台监控采集
        
        Returns:
            dict: {"success": bool}
        """
        try:
            self._collector.start()
            return {"success": True}
        except Exception as e:
            logger.error(f"Failed to start monitoring: {e}")
            return {"success": False, "error_message": str(e)}
    
    def stop_monitoring(self) -> dict:
        """
        停止后台监控采集
        
        Returns:
            dict: {"success": bool}
        """
        try:
            self._collector.stop()
            return {"success": True}
        except Exception as e:
            logger.error(f"Failed to stop monitoring: {e}")
            return {"success": False, "error_message": str(e)}
    
    def toggle_floating_window(self, visible: bool) -> dict:
        """
        切换悬浮窗显示状态
        
        Args:
            visible: 是否显示悬浮窗
            
        Returns:
            dict: {"success": bool}
        """
        try:
            from backend.src.ui import floating_window_manager
            
            if visible == self._floating_window_visible:
                logger.debug(f"[toggle_floating_window] 状态未变化（visible={visible}），跳过操作")
                return {"success": True}
            
            if visible:
                if floating_window_manager._window is not None:
                    floating_window_manager._window.show()
                    floating_window_manager._visible = True
                    floating_window_manager._apply_toolwindow_style()
                    success = True
                    logger.info("[toggle_floating_window] 悬浮窗已显示")
                elif self._base_url:
                    logger.info("[toggle_floating_window] 悬浮窗不存在，开始创建（hidden=True，等待前端就绪）...")
                    
                    if not floating_window_manager._main_hwnd:
                        from backend.src.utils.window_bounds import find_window_by_title
                        main_hwnd = find_window_by_title("ComfyNexus", max_retries=1, retry_interval=0)
                        if main_hwnd:
                            floating_window_manager.set_main_hwnd(main_hwnd)
                            logger.debug(f"[toggle_floating_window] 设置主窗口句柄: {main_hwnd}")
                    
                    floating_window_manager.create_window(
                        base_url=self._base_url,
                        screen_width=self._screen_width,
                        screen_height=self._screen_height,
                        dpi_scale=self._dpi_scale,
                        hidden=True
                    )
                    success = floating_window_manager._window is not None
                    logger.info(f"[toggle_floating_window] 悬浮窗已创建（等待前端回调显示）: success={success}")
                else:
                    success = False
                    logger.warning("[toggle_floating_window] 悬浮窗上下文未设置，无法创建")
            else:
                success = floating_window_manager.hide()
                logger.info("[toggle_floating_window] 悬浮窗已隐藏")
            
            self._floating_window_visible = visible
            
            settings = self._floating_window_settings.copy()
            settings["visible"] = visible
            self._settings_manager.save_floating_window_settings(settings)
            self._floating_window_settings = settings
            
            return {"success": success}
        except Exception as e:
            logger.error(f"Failed to toggle floating window: {e}")
            return {"success": False, "error_message": str(e)}
    
    def get_floating_window_visible(self) -> dict:
        """
        获取悬浮窗可见状态
        
        Returns:
            dict: {"success": bool, "visible": bool}
        """
        return {
            "success": True,
            "visible": self._floating_window_visible
        }
    
    def set_floating_window_context(self, base_url: str, screen_width: int, screen_height: int, dpi_scale: float):
        """
        设置悬浮窗上下文信息
        
        Args:
            base_url: 基础 URL
            screen_width: 屏幕宽度
            screen_height: 屏幕高度
            dpi_scale: DPI 缩放因子
        """
        self._base_url = base_url
        self._screen_width = screen_width
        self._screen_height = screen_height
        self._dpi_scale = dpi_scale
    
    def update_floating_window_settings(self, settings: dict) -> dict:
        """
        更新悬浮窗设置
        
        Args:
            settings: 悬浮窗设置（opacity, visibleItems, itemOrder）
            
        Returns:
            dict: {"success": bool}
        """
        try:
            settings["visible"] = self._floating_window_visible
            self._floating_window_settings = settings
            self._settings_manager.save_floating_window_settings(settings)
            logger.info(f"Floating window settings saved: {settings}")
            return {"success": True}
        except Exception as e:
            logger.error(f"Failed to update floating window settings: {e}")
            return {"success": False, "error_message": str(e)}
    
    def get_floating_window_settings(self) -> dict:
        """
        获取悬浮窗设置
        
        Returns:
            dict: {"success": bool, "data": dict}
        """
        return {
            "success": True,
            "data": self._floating_window_settings
        }
    
    def resize_floating_window(self, width: int, height: int) -> dict:
        """
        接收前端动态调整悬浮窗尺寸的请求
        
        Args:
            width: 窗口宽度
            height: 窗口高度
            
        Returns:
            dict: {"success": bool}
        """
        try:
            from backend.src.ui import floating_window_manager
            success = floating_window_manager.resize_window(width, height)
            return {"success": success}
        except Exception as e:
            logger.error(f"动态调整悬浮窗尺寸失败: {e}")
            return {"success": False, "error_message": str(e)}
    
    def get_hardware_info(self) -> dict:
        """
        获取硬件信息
        
        Returns:
            dict: {
                "success": bool,
                "data": {
                    "cpu": {"name": str, "cores": int, "threads": int, "vendor": str},
                    "gpu": {"name": str, "vendor": str, "vram_total": int}
                }
            }
        """
        try:
            info = self._collector.get_hardware_info()
            return {"success": True, "data": info}
        except Exception as e:
            logger.error(f"Failed to get hardware info: {e}")
            return {"success": False, "error_message": str(e)}
    
    def get_network_interface_name(self) -> dict:
        """
        获取活动网络接口名称
        
        Returns:
            dict: {"success": bool, "data": str}
        """
        try:
            name = self._collector.get_network_interface_name()
            return {"success": True, "data": name}
        except Exception as e:
            logger.error(f"Failed to get network interface name: {e}")
            return {"success": False, "error_message": str(e)}
    
    def get_hardware_monitor_status(self) -> dict:
        """
        获取硬件监控状态
        
        Returns:
            dict: {
                "success": bool,
                "data": {
                    "available": bool,
                    "has_admin_privilege": bool,
                    "error": str|None
                }
            }
        """
        try:
            status = self._collector.get_hardware_monitor_status()
            return {"success": True, "data": status}
        except Exception as e:
            logger.error(f"Failed to get hardware monitor status: {e}")
            return {"success": False, "error_message": str(e)}
    
    def _get_empty_data(self) -> dict:
        """返回空数据结构"""
        return {
            "cpu": {"load": 0, "temp": 0, "power": 0, "freq": 0.0},
            "gpu": {"load": 0, "temp": 0, "power": 0, "core_clock": 0},
            "sys": {
                "ram": {"used": 0, "total": 0, "percent": 0},
                "vram": {"used": 0, "total": 0, "percent": 0},
                "page": {"used": 0, "total": 0, "percent": 0}
            },
            "net": {"up": 0.0, "down": 0.0},
            "disks": []
        }
    
    def close(self):
        """清理资源"""
        try:
            self._collector.close()
        except Exception as e:
            logger.error(f"Failed to close monitor collector: {e}")
