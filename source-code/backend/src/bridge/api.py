"""
API 类
用于暴露给前端的所有 API
"""

import time
import threading
from typing import Dict, Optional
from pathlib import Path
from tkinter import filedialog
from backend.src.core.config import ModuleConfigManager
from backend.src.bridge.controllers.environment_controller import EnvironmentController
from backend.src.bridge.controllers.system_monitor_controller import SystemMonitorController
from backend.src.bridge.controllers.folder_shortcut_controller import FolderShortcutController
from backend.src.bridge.controllers.version_controller import VersionController
from backend.src.bridge.controllers.plugin_controller_bridge import PluginControllerBridge
from backend.src.bridge.controllers.marketplace_controller_bridge import MarketplaceControllerBridge
from backend.src.core.system_proxy_manager import SystemProxyManager
from backend.src.core.settings_manager import SettingsManager
from backend.src.utils.logger import app_logger as logger
from backend.src.utils import image_downloader

_commit_time_cache: Dict[str, dict] = {}
_COMMIT_TIME_CACHE_TTL = 3600


class Api:
    """
    前端可调用的 API 类（注意：类名必须是 Api）
    
    注意: pywebview 序列化机制
    - 公共属性和方法会被暴露给前端 JavaScript
    - 以单下划线 _ 开头的属性被视为私有，不会被序列化
    - 所有内部对象引用（window、控制器等）必须使用私有命名
    """
    
    def __init__(self):
        """初始化 API 类"""
        self._window = None
        self._is_maximized = False
        self._is_fullscreen = False
        self._window_state = None
        self._stop_listener = False
        self._dependencies_update_started = False
        self._dpi_scale = 1.0
        self._frontend_heartbeat_received = False
        self._app_exit_requested = False
        # 关闭确认弹窗待处理标志：ALT+F4 等系统关闭请求被拦截并触发弹窗后置位，
        # 置位期间忽略新的关闭请求；弹窗关闭时由前端调用 resetCloseDialogState() 复位
        self._close_dialog_pending = False
        
        # 直接初始化所有控制器 - 使用私有属性命名
        from backend.src.core.config import ModuleConfigManager
        from backend.src.bridge.controllers.environment_controller import EnvironmentController
        from backend.src.bridge.controllers.system_monitor_controller import SystemMonitorController
        from backend.src.core.system_proxy_manager import SystemProxyManager
        from backend.src.core.settings_manager import SettingsManager
        
        self._module_config_manager = ModuleConfigManager()
        self._environment_controller = EnvironmentController()
        self._system_monitor_controller = SystemMonitorController()
        self._system_proxy_manager = SystemProxyManager()
        self._settings_manager = SettingsManager()
        
        # 依赖 environment_controller 的控制器稍后初始化
        from backend.src.bridge.controllers.folder_shortcut_controller import FolderShortcutController
        from backend.src.bridge.controllers.version_controller import VersionController
        from backend.src.bridge.controllers.plugin_controller_bridge import PluginControllerBridge
        from backend.src.bridge.controllers.marketplace_controller_bridge import MarketplaceControllerBridge
        from backend.src.bridge.controllers.ai_controller import AIController
        
        self._folder_shortcut_controller = FolderShortcutController(self._environment_controller.manager)
        self._version_controller = VersionController(environment_manager=self._environment_controller.manager)
        self._plugin_controller = PluginControllerBridge(environment_manager=self._environment_controller.manager)
        self._marketplace_controller = MarketplaceControllerBridge(
            environment_manager=self._environment_controller.manager,
            settings_manager=self._settings_manager
        )
        self._ai_controller = AIController()
        
        # 依赖管理控制器
        from backend.src.bridge.controllers.dependency_controller import DependencyController
        self._dependency_controller = DependencyController(environment_manager=self._environment_controller.manager)
        
        # 救援模式控制器
        from backend.src.bridge.controllers.rescue_controller import RescueController
        self._rescue_controller = RescueController(environment_manager=self._environment_controller.manager)
        
        # 自动更新控制器
        from backend.src.core.updater import UpdateController
        self._update_controller = UpdateController(settings_manager=self._settings_manager)
        
        # LoRA 配置管理器
        from backend.src.core.config import LoraConfigManager
        self._lora_config_manager = LoraConfigManager()
        
        # 工作流配置管理器
        from backend.src.core.config import WorkflowConfigManager
        self._workflow_config_manager = WorkflowConfigManager()
        
        # 提示词库控制器
        from backend.src.bridge.controllers.prompt_library_controller import PromptLibraryController
        self._prompt_library_controller = PromptLibraryController()
        
        # 工作流管理控制器
        from backend.src.bridge.controllers.workflow_controller import WorkflowController
        self._workflow_controller = WorkflowController(
            environment_manager=self._environment_controller.manager,
            plugin_controller=self._plugin_controller,
            workflow_config_manager=self._workflow_config_manager
        )
        
        # 资产库控制器
        from backend.src.gallery.controller import gallery_controller
        self._gallery_controller = gallery_controller
        
        # 缓存管理服务
        from backend.src.core.cache import CacheService
        self._cache_service = CacheService()
        
        # 开发环境断言：验证关键属性是私有的
        if __debug__:
            assert hasattr(self, '_window'), "window 引用必须是私有属性"
            assert hasattr(self, '_environment_controller'), "environment_controller 必须是私有属性"
            assert hasattr(self, '_module_config_manager'), "module_config_manager 必须是私有属性"
        
        logger.debug(f"[API] __init__ 完成（直接初始化模式）")
        logger.debug("[API] 所有内部引用已设置为私有属性")
        # 调试：打印所有公共方法
        public_methods = [name for name in dir(self) if not name.startswith('_') and callable(getattr(self, name))]
        logger.debug(f"[API] 公共方法数量: {len(public_methods)}")
        logger.debug(f"[API] 前 20 个公共方法: {public_methods[:20]}")
    
    
    def set_window(self, window):
        """设置窗口引用（内部使用）"""
        logger.debug("[API] set_window 被调用")
        self._window = window
        
        # 将窗口引用传递给所有控制器
        self._environment_controller.set_window(window)
        self._folder_shortcut_controller.set_window(window)
        self._version_controller.set_window(window)
        self._plugin_controller.set_window(window)
        self._marketplace_controller.set_window(window)
        self._ai_controller.window = window
        self._dependency_controller.set_window(window)
        self._rescue_controller.set_window(window)
        self._update_controller.set_window(window)
        
        # 初始化工作流控制器
        self._workflow_controller.initialize()
        
        # 启动窗口移动监听器（用于拖动还原）
        self._start_window_move_listener()
    
    def start_async_dependencies_update(self):
        """
        启动异步依赖信息更新
        
        此方法在应用启动完成后调用，后台异步更新所有环境的依赖信息。
        只会执行一次，避免重复更新。
        
        Returns:
            dict: 操作结果
        """
        if self._dependencies_update_started:
            return {
                "success": False,
                "message": "异步更新已经启动"
            }
        
        self._dependencies_update_started = True
        
        def update_all_dependencies():
            """后台线程：更新所有环境的依赖信息"""
            try:
                # 获取所有环境
                result = self._environment_controller.manager.get_environments()
                if not result.get("success"):
                    return
                
                environments = result.get("environments", [])
                
                if not environments:
                    logger.info("[异步依赖更新] 没有环境需要更新")
                    return
                
                logger.info(f"[异步依赖更新] 开始更新 {len(environments)} 个环境的依赖信息")
                
                # 批量更新：先更新所有环境，不保存配置
                last_config_data = None
                success_count = 0
                
                for env in environments:
                    env_id = env.get("id")
                    
                    try:
                        # save_config=False：不立即保存，只更新内存中的数据
                        update_result = self._environment_controller.manager.update_dependencies(
                            env_id, 
                            save_config=False
                        )
                        
                        if update_result.get("success"):
                            # 保存最后一次更新的配置数据
                            last_config_data = update_result.get("config_data")
                            success_count += 1
                            logger.debug(f"[异步依赖更新] 环境 {env_id} 依赖信息已更新")
                        else:
                            logger.warning(f"[异步依赖更新] 环境 {env_id} 更新失败: {update_result.get('error_message')}")
                    except Exception as e:
                        logger.error(f"[异步依赖更新] 环境 {env_id} 更新异常: {e}")
                
                # 统一保存配置（只保存一次）
                if last_config_data and success_count > 0:
                    try:
                        self._environment_controller.manager.config_manager.save_config(last_config_data)
                        logger.info(f"[异步依赖更新] 完成！成功更新 {success_count}/{len(environments)} 个环境，配置已保存")
                    except Exception as e:
                        logger.error(f"[异步依赖更新] 保存配置失败: {e}")
                else:
                    logger.warning(f"[异步依赖更新] 没有成功更新任何环境")
                
            except Exception as e:
                logger.error(f"[异步依赖更新] 批量更新失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
        
        # 启动后台线程
        thread = threading.Thread(target=update_all_dependencies, daemon=True)
        thread.start()
        
        return {
            "success": True,
            "message": "异步依赖信息更新已启动"
        }
    
    def ping(self):
        """前端心跳信号，用于健康检查"""
        self._frontend_heartbeat_received = True
        return {"status": "ok"}

    def getAppInfo(self):
        """获取应用信息"""
        import sys
        import backend
        return {
            "version": backend.get_version(),
            "env": f"host_python_{sys.version_info.major}.{sys.version_info.minor}"
        }
    
    def check_for_update(self) -> Dict:
        """
        检查更新
        
        Returns:
            {
                "success": bool,
                "has_update": bool,
                "current_version": str,
                "latest_version": str,
                "download_url": str,
                "release_notes": str,
                "published_at": str,
                "file_size": int,
                "error": str  # 可选
            }
        """
        return self._update_controller.check_for_update()
    
    def download_update(self) -> Dict:
        """
        下载更新
        
        Returns:
            {
                "success": bool,
                "zip_path": str,
                "error": str  # 可选
            }
        """
        return self._update_controller.download_update()
    
    def get_download_progress(self) -> Dict:
        """
        获取下载进度
        
        Returns:
            {
                "downloaded": int,
                "total": int,
                "percentage": int
            }
        """
        return self._update_controller.get_download_progress()
    
    def apply_update(self) -> Dict:
        """
        应用更新
        
        Returns:
            {
                "success": bool,
                "message": str
            }
        """
        return self._update_controller.apply_update()
    
    def cancel_download(self) -> Dict:
        """
        取消下载
        
        Returns:
            {
                "success": bool,
                "message": str
            }
        """
        return self._update_controller.cancel_download()
    
    def check_local_update(self) -> Dict:
        """
        检查本地是否已有可用的更新包
        
        Returns:
            {
                "success": bool,
                "has_local_file": bool,
                "hash_match": bool,
                "file_path": str,
                "file_size": int,
                "partial_download": {
                    "has_partial": bool,
                    "downloaded_size": int,
                    "total_size": int,
                    "percentage": int
                },
                "error": str  # 可选
            }
        """
        return self._update_controller.check_local_update()
    
    def clear_download_cache(self) -> Dict:
        """
        清理下载缓存
        
        Returns:
            {
                "success": bool,
                "message": str
            }
        """
        return self._update_controller.clear_download_cache()
    
    def getCloseBehavior(self) -> dict:
        """获取关闭行为设置"""
        try:
            result = self._settings_manager.get_settings()
            if result.get("success"):
                settings = result.get("settings", {})
                behavior = settings.get("closeBehavior", {})
                return {
                    "success": True,
                    "action": behavior.get("action"),
                    "dontAskAgain": behavior.get("dontAskAgain", False)
                }
            return {"success": False, "action": None, "dontAskAgain": False}
        except Exception as e:
            logger.error(f"[getCloseBehavior] 获取关闭行为设置失败: {str(e)}")
            return {"success": False, "action": None, "dontAskAgain": False}
    
    def setCloseBehavior(self, action: str, dontAskAgain: bool) -> dict:
        """保存关闭行为设置"""
        try:
            result = self._settings_manager.update_settings({
                "closeBehavior": {
                    "action": action,
                    "dontAskAgain": dontAskAgain
                }
            })
            return {
                "success": result.get("success", False),
                "message": result.get("message", "")
            }
        except Exception as e:
            logger.error(f"[setCloseBehavior] 保存关闭行为设置失败: {str(e)}")
            return {"success": False, "message": str(e)}
    
    def resetCloseDialogState(self) -> dict:
        """关闭确认弹窗已关闭时复位待处理标志

        由前端在弹窗关闭时调用（无论选择最小化、直接关闭弹窗还是退出程序），
        使后续 ALT+F4 能重新按 closeBehavior 配置处理。退出程序路径由
        closeApp() 设置的 _app_exit_requested 放行，不受本复位影响。
        """
        self._close_dialog_pending = False
        return {"success": True}
    
    def closeApp(self):
        """关闭应用"""
        self._app_exit_requested = True
        try:
            from backend.src.ui import floating_window_manager
            floating_window_manager.destroy()
        except Exception as e:
            logger.debug(f"[closeApp] 关闭悬浮窗时出错: {str(e)}")
        
        try:
            from backend.src.ui import system_tray_manager
            system_tray_manager.destroy()
        except Exception as e:
            logger.debug(f"[closeApp] 销毁托盘图标时出错: {str(e)}")
        
        try:
            if hasattr(self, '_comfyui_process') and self._comfyui_process:
                if self._comfyui_process.is_running:
                    try:
                        self._comfyui_process.stop()
                    except Exception as e:
                        logger.warning(f"[closeApp] 关闭 ComfyUI 进程时出错: {str(e)}")
        except Exception as e:
            logger.warning(f"[closeApp] 检查 ComfyUI 进程时出错: {str(e)}")
        
        try:
            self._system_monitor_controller.close()
        except Exception as e:
            logger.debug(f"[closeApp] 清理硬件监控资源时出错: {str(e)}")
        
        if self._window:
            try:
                import ctypes
                hwnd = ctypes.windll.user32.FindWindowW(None, "ComfyNexus")
                if hwnd:
                    ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)
                else:
                    self._window.destroy()
            except Exception:
                self._window.destroy()
                self._window.destroy()
        logger.info("[closeApp] 执行完毕")
    
    def minimizeApp(self):
        """最小化应用"""
        if self._window:
            # 如果窗口处于最大化状态，先还原再最小化
            # 这样可以避免最小化后恢复时出现状态混乱
            if self._is_maximized:
                logger.debug("[最小化] 窗口处于最大化状态，先还原")
                try:
                    import ctypes
                    user32 = ctypes.windll.user32
                    
                    # 获取窗口句柄
                    hwnd = None
                    if hasattr(self._window, 'gui') and hasattr(self._window.gui, 'hwnd'):
                        hwnd = self._window.gui.hwnd
                    
                    if not hwnd or hwnd == 0:
                        hwnd = user32.FindWindowW(None, "ComfyNexus")
                    
                    if hwnd and hwnd != 0:
                        # 先还原窗口
                        if self._window_state:
                            x = self._window_state['x']
                            y = self._window_state['y']
                            width = self._window_state['width']
                            height = self._window_state['height']
                            
                            # SWP_NOZORDER = 0x0004
                            user32.SetWindowPos(hwnd, None, x, y, width, height, 0x0004)
                            logger.debug(f"[最小化] 已还原窗口: ({x}, {y}), {width}x{height}")
                        
                        self._is_maximized = False
                except Exception as e:
                    logger.error(f"[最小化] 还原窗口失败: {e}")
            
            # 执行最小化
            self._window.minimize()
            logger.debug("[最小化] 窗口已最小化")
    
    def minimizeToTray(self):
        """最小化到系统托盘（隐藏窗口）"""
        try:
            from backend.src.ui import system_tray_manager
            
            if not system_tray_manager.is_running:
                system_tray_manager.show()
                logger.info("[minimizeToTray] 托盘图标已创建")
            
            if self._window:
                self._window.hide()
                logger.info("[minimizeToTray] 窗口已隐藏到托盘")
            
            return {"success": True}
        except Exception as e:
            logger.error(f"[minimizeToTray] 最小化到托盘失败: {e}")
            return {"success": False, "message": str(e)}
    
    def restoreFromTray(self):
        """从托盘恢复窗口"""
        try:
            if self._window:
                self._window.show()
                logger.info("[restoreFromTray] 窗口已从托盘恢复")
            
            return {"success": True}
        except Exception as e:
            logger.error(f"[restoreFromTray] 恢复窗口失败: {e}")
            return {"success": False, "message": str(e)}
    
    def maximizeApp(self):
            """最大化/还原应用窗口（保留系统托盘栏）"""
            if not self._window:
                logger.error("[最大化] 错误: 窗口对象不存在")
                return

            try:
                import ctypes

                # 优先尝试从 pywebview 获取窗口句柄
                hwnd = None
                if hasattr(self._window, 'gui') and hasattr(self._window.gui, 'hwnd'):
                    hwnd = self._window.gui.hwnd
                    logger.debug(f"[最大化] 从 pywebview.gui.hwnd 获取窗口句柄: {hwnd}")

                # 如果失败，尝试通过窗口标题查找
                if not hwnd or hwnd == 0:
                    user32 = ctypes.windll.user32
                    hwnd = user32.FindWindowW(None, "ComfyNexus")
                    logger.debug(f"[最大化] 通过 FindWindowW 查找窗口句柄: {hwnd}")

                if hwnd and hwnd != 0:
                    user32 = ctypes.windll.user32

                    if self._is_maximized:
                        logger.debug("[最大化] 还原窗口")
                        width, height = self._get_settings_window_size()
                        logger.debug(f"[最大化] 从设置获取窗口大小: {width}x{height}")
                        
                        if self._window_state:
                            x = self._window_state['x']
                            y = self._window_state['y']
                        else:
                            x = 100
                            y = 100

                        user32.SetWindowPos(hwnd, None, x, y, width, height, 0x0004)
                        logger.debug(f"[最大化] 还原到: ({x}, {y}), 大小: {width}x{height}")

                        self._is_maximized = False
                    else:
                        # 保存当前窗口位置和大小
                        self._save_window_rect(hwnd)

                        # 获取窗口当前所在的显示器信息
                        from backend.src.utils.window_bounds import get_monitor_info
                        
                        monitor_info = get_monitor_info(hwnd)
                        if not monitor_info:
                            logger.warning("[最大化] 无法获取显示器信息，使用降级方案")
                            self._maximize_fallback()
                            return

                        # 使用工作区（排除任务栏）
                        work_rect = monitor_info['work_rect']
                        work_left, work_top, work_right, work_bottom = work_rect
                        work_width = work_right - work_left
                        work_height = work_bottom - work_top

                        logger.debug(f"[最大化] 当前显示器工作区大小: {work_width}x{work_height}")
                        logger.debug(f"[最大化] 当前显示器工作区位置: ({work_left}, {work_top})")

                        # 移动并调整窗口大小到当前显示器的工作区
                        # SWP_NOZORDER = 0x0004
                        user32.SetWindowPos(
                            hwnd, 
                            None, 
                            work_left, 
                            work_top, 
                            work_width, 
                            work_height, 
                            0x0004
                        )

                        logger.debug("[最大化] 窗口已最大化到当前显示器的工作区")
                        self._is_maximized = True
                else:
                    # 降级方案：使用 pywebview API
                    logger.debug("[最大化] 窗口句柄获取失败，使用降级方案")
                    self._maximize_fallback()

            except Exception as e:
                logger.error(f"[最大化] 异常: {e}")
                import traceback
                traceback.print_exc()
                # 降级方案
                self._maximize_fallback()

    
    def isMaximized(self):
        """检查窗口是否最大化"""
        return self._is_maximized
    
    def set_dpi_scale(self, dpi_scale: float):
        """设置 DPI 缩放因子（由 main.py 在启动时调用）"""
        self._dpi_scale = dpi_scale
        logger.debug(f"[DPI] 缩放因子已设置: {dpi_scale}")
    
    def resetWindowPosition(self):
        """
        重置窗口位置到当前显示器中心，并恢复默认尺寸
        
        用于多显示器环境下窗口移出可视区域时的恢复。
        同时重置窗口大小，解决窗口尺寸大于目标屏幕的问题。
        
        注意：此 API 由前端在适当时机调用（如用户点击按钮），
        在主 UI 线程中执行，符合 Windows 线程亲和性要求。
        
        Returns:
            dict: {"success": bool, "message": str}
        """
        try:
            from backend.src.utils.window_bounds import reset_window_to_center, find_window_by_title
            
            # 获取窗口句柄
            hwnd = None
            if hasattr(self._window, 'gui') and hasattr(self._window.gui, 'hwnd'):
                hwnd = self._window.gui.hwnd
            
            if not hwnd or hwnd == 0:
                hwnd = find_window_by_title("ComfyNexus", max_retries=3, retry_interval=0.2)
            
            if hwnd and hwnd != 0:
                # 从配置获取默认窗口尺寸
                default_width, default_height = self._get_settings_window_size()
                
                # 重置窗口到当前显示器中心，并恢复默认尺寸
                success = reset_window_to_center(hwnd, default_width, default_height)
                
                if success:
                    logger.info(f"[resetWindowPosition] 窗口已重置: 位置居中, 尺寸{default_width}x{default_height}")
                    return {"success": True, "message": "窗口位置已重置"}
                else:
                    logger.warning("[resetWindowPosition] 窗口位置重置失败")
                    return {"success": False, "message": "窗口位置重置失败"}
            else:
                logger.error("[resetWindowPosition] 无法找到窗口")
                return {"success": False, "message": "无法找到窗口"}
                
        except Exception as e:
            logger.error(f"[resetWindowPosition] 异常: {e}", exc_info=True)
            return {"success": False, "message": f"重置窗口位置时出错: {str(e)}"}
    
    def checkWindowBounds(self):
        """
        检查并修复窗口边界
        
        用于前端在窗口获得焦点等时机调用，确保窗口在可视区域内。
        
        Returns:
            dict: {"success": bool, "adjusted": bool, "message": str}
        """
        try:
            from backend.src.utils.window_bounds import check_and_fix_window_bounds, find_window_by_title
            
            # 获取窗口句柄
            hwnd = None
            if hasattr(self._window, 'gui') and hasattr(self._window.gui, 'hwnd'):
                hwnd = self._window.gui.hwnd
            
            if not hwnd or hwnd == 0:
                hwnd = find_window_by_title("ComfyNexus", max_retries=1, retry_interval=0)
            
            if hwnd and hwnd != 0:
                adjusted = check_and_fix_window_bounds(hwnd)
                
                if adjusted:
                    logger.info("[checkWindowBounds] 窗口边界已修复")
                    return {"success": True, "adjusted": True, "message": "窗口边界已修复"}
                else:
                    return {"success": True, "adjusted": False, "message": "窗口边界正常"}
            else:
                return {"success": False, "adjusted": False, "message": "无法找到窗口"}
                
        except Exception as e:
            logger.error(f"[checkWindowBounds] 异常: {e}", exc_info=True)
            return {"success": False, "adjusted": False, "message": f"检查窗口边界时出错: {str(e)}"}
    
    def _get_settings_window_size(self):
        """从配置文件获取窗口大小（返回物理像素），失败时使用默认值
        
        注意：前端以 CSS 像素保存窗口大小到 settings，
        此处乘以 _dpi_scale 转换为物理像素，
        与 _window_state（通过 GetWindowRect 获取，天然是物理像素）保持一致。
        """
        try:
            settings_result = self._settings_manager.get_settings()
            if settings_result.get('success') and settings_result.get('settings'):
                window_size = settings_result['settings'].get('appearance', {}).get('windowSize', '1680x1080')
                width_str, height_str = window_size.split('x')
                return round(int(width_str) * self._dpi_scale), round(int(height_str) * self._dpi_scale)
        except Exception as e:
            logger.error(f"[窗口尺寸] 读取配置失败: {e}")
        return round(1680 * self._dpi_scale), round(1080 * self._dpi_scale)

    def _save_window_rect(self, hwnd):
        """保存窗口位置和大小"""
        try:
            from backend.src.utils.window_bounds import get_window_rect
            
            rect = get_window_rect(hwnd)
            if rect:
                left, top, right, bottom = rect
                self._window_state = {
                    'x': left,
                    'y': top,
                    'width': right - left,
                    'height': bottom - top
                }
                logger.debug(f"[保存窗口位置] 成功: {self._window_state}")
            else:
                logger.warning("[保存窗口位置] 无法获取窗口矩形")
        except Exception as e:
            logger.error(f"[保存窗口位置] 失败: {e}")
    
    def _maximize_fallback(self):
        """降级方案：使用 pywebview API 模拟最大化
        
        注意：pywebview 的 move()/resize() 使用逻辑像素，
        而 _window_state 和 _get_settings_window_size() 使用物理像素，
        需要进行 DPI 转换。
        """
        try:
            import tkinter as tk
            
            if self._is_maximized:
                width, height = self._get_settings_window_size()
                logical_width = round(width / self._dpi_scale)
                logical_height = round(height / self._dpi_scale)
                logger.debug(f"[降级方案] 从设置获取窗口大小: {width}x{height} (逻辑: {logical_width}x{logical_height})")
                if self._window_state:
                    logical_x = round(self._window_state['x'] / self._dpi_scale)
                    logical_y = round(self._window_state['y'] / self._dpi_scale)
                    self._window.move(logical_x, logical_y)
                else:
                    self._window.move(100, 100)
                self._window.resize(logical_width, logical_height)
                self._is_maximized = False
            else:
                saved_width, saved_height = self._get_settings_window_size()
                logical_saved_width = round(saved_width / self._dpi_scale)
                logical_saved_height = round(saved_height / self._dpi_scale)
                logger.debug(f"[降级方案] 从设置获取窗口大小: {saved_width}x{saved_height} (逻辑: {logical_saved_width}x{logical_saved_height})")
                
                self._window_state = {
                    'x': round(100 * self._dpi_scale),
                    'y': round(100 * self._dpi_scale),
                    'width': saved_width,
                    'height': saved_height
                }
                
                root = tk.Tk()
                screen_width = root.winfo_screenwidth()
                screen_height = root.winfo_screenheight()
                root.destroy()
                
                taskbar_height = 40
                self._window.move(0, 0)
                self._window.resize(screen_width, screen_height - taskbar_height)
                self._is_maximized = True
                
        except Exception as e:
            logger.error(f"[降级方案] 失败: {e}")
    
    def _start_window_move_listener(self):
        """启动窗口移动监听（后台线程）"""
        def listen_for_window_move():
            """监听窗口移动的后台线程"""
            try:
                import ctypes
                import time
                from backend.src.utils.window_bounds import RECT, get_window_rect
                
                # 监听器线程已启动（不输出日志，避免干扰）
                
                user32 = ctypes.windll.user32
                
                # 等待窗口创建完成（最多等待 5 秒）
                hwnd = None
                for attempt in range(50):  # 50 次 * 0.1 秒 = 5 秒
                    # 优先尝试从 pywebview 获取
                    if hasattr(self._window, 'gui') and hasattr(self._window.gui, 'hwnd'):
                        hwnd = self._window.gui.hwnd
                        if hwnd and hwnd != 0:
                            logger.debug(f"[窗口监听] 从 pywebview.gui.hwnd 获取窗口句柄: {hwnd}")
                            break
                    
                    # 尝试通过窗口标题查找
                    hwnd = user32.FindWindowW(None, "ComfyNexus")
                    if hwnd and hwnd != 0:
                        logger.debug(f"[窗口监听] 通过 FindWindowW 获取窗口句柄: {hwnd} (尝试 {attempt + 1}/50)")
                        break
                    
                    time.sleep(0.1)
                
                if not hwnd or hwnd == 0:
                    logger.warning("[窗口监听] 无法获取窗口句柄，监听器退出")
                    return
                
                # 成功获取窗口句柄（不输出日志，避免干扰）
                
                last_rect = None
                is_dragging = False
                VK_LBUTTON = 0x01  # 左键虚拟键码
                
                # 拖动异常检测变量
                drag_anomaly_detected = False
                drag_anomaly_start_time = None
                ANOMALY_THRESHOLD = 0.1  # 100ms
                
                while not self._stop_listener:
                    try:
                        # 只在最大化状态下监听
                        if self._is_maximized:
                            # 获取当前窗口位置
                            rect = RECT()
                            user32.GetWindowRect(hwnd, ctypes.pointer(rect))
                            
                            # 检查鼠标左键状态
                            is_left_button_down = user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000
                            
                            # 检测窗口移动
                            if last_rect:
                                dx = abs(rect.left - last_rect.left)
                                dy = abs(rect.top - last_rect.top)
                                
                                if dx > 1 or dy > 1:
                                    # 检测到移动
                                    if not is_dragging:
                                        is_dragging = True
                                    last_rect = rect
                                    
                                    # 异常检测：窗口在移动但鼠标已释放
                                    if not is_left_button_down:
                                        if not drag_anomaly_detected:
                                            drag_anomaly_detected = True
                                            drag_anomaly_start_time = time.time()
                                        elif time.time() - drag_anomaly_start_time > ANOMALY_THRESHOLD:
                                            # 确认异常，尝试自动修复
                                            logger.warning("[拖动异常] 检测到拖动异常，尝试自动释放鼠标")
                                            self._handle_drag_anomaly(hwnd)
                                            drag_anomaly_detected = False
                                            drag_anomaly_start_time = None
                                    else:
                                        drag_anomaly_detected = False
                                        drag_anomaly_start_time = None
                                        
                                elif is_dragging and not is_left_button_down:
                                    # 拖动结束（窗口停止移动且鼠标左键已释放）
                                    self._restore_on_move(hwnd)
                                    is_dragging = False
                                    last_rect = None
                                    drag_anomaly_detected = False
                                    drag_anomaly_start_time = None
                                    continue
                            else:
                                last_rect = rect
                        else:
                            last_rect = None
                            is_dragging = False
                            drag_anomaly_detected = False
                            drag_anomaly_start_time = None
                        
                        # 20ms 检查一次（更快的响应）
                        time.sleep(0.02)
                        
                    except Exception as e:
                        logger.error(f"[窗口监听] 循环异常: {e}")
                        time.sleep(0.1)
                
                # 监听器线程已停止（不输出日志，避免干扰）
                
            except Exception as e:
                logger.error(f"[窗口监听] 线程异常: {e}")
                import traceback
                traceback.print_exc()
        
        # 启动后台线程
        listener_thread = threading.Thread(target=listen_for_window_move, daemon=True)
        listener_thread.start()
    
    def _restore_on_move(self, hwnd):
        """窗口移动时还原"""
        try:
            import ctypes
            from backend.src.utils.window_bounds import POINT, MONITORINFO
            
            user32 = ctypes.windll.user32
            
            cursor_pos = POINT()
            user32.GetCursorPos(ctypes.pointer(cursor_pos))
            
            saved_width, saved_height = self._get_settings_window_size()
            logger.debug(f"[拖动还原] 从设置获取窗口大小: {saved_width}x{saved_height}")
            
            new_x = round(cursor_pos.x - saved_width / 2)
            new_y = round(cursor_pos.y - saved_height / 2)
            
            # 获取鼠标当前所在的显示器
            hmonitor = user32.MonitorFromPoint(cursor_pos, 2)  # MONITOR_DEFAULTTONEAREST = 2
            
            # 获取该显示器的工作区信息
            monitor_info = MONITORINFO()
            monitor_info.cbSize = ctypes.sizeof(MONITORINFO)
            user32.GetMonitorInfoW(hmonitor, ctypes.pointer(monitor_info))
            
            # 使用鼠标所在显示器的工作区
            work_area = monitor_info.rcWork
            
            logger.debug(f"[拖动还原] 鼠标位置: ({cursor_pos.x}, {cursor_pos.y})")
            logger.debug(f"[拖动还原] 目标显示器工作区: ({work_area.left}, {work_area.top}) - ({work_area.right}, {work_area.bottom})")
            
            # 限制 x 坐标
            if new_x < work_area.left:
                new_x = work_area.left
            elif new_x + saved_width > work_area.right:
                new_x = work_area.right - saved_width
            
            # 限制 y 坐标
            if new_y < work_area.top:
                new_y = work_area.top
            elif new_y + saved_height > work_area.bottom:
                new_y = work_area.bottom - saved_height
            
            self._is_maximized = False
            self._window_state = None
            
            GWL_STYLE = -16
            WS_MAXIMIZE = 0x01000000
            SWP_FRAMECHANGED = 0x0020
            SWP_NOZORDER = 0x0004
            
            style = user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
            if style & WS_MAXIMIZE:
                style &= ~WS_MAXIMIZE
                user32.SetWindowLongPtrW(hwnd, GWL_STYLE, style)
            
            user32.SetWindowPos(hwnd, None, new_x, new_y, saved_width, saved_height, SWP_FRAMECHANGED | SWP_NOZORDER)
            
            logger.debug(f"[拖动还原] 窗口已还原到: ({new_x}, {new_y}), 大小: {saved_width}x{saved_height}")
            
        except Exception as e:
            logger.error(f"[窗口监听] 还原失败: {e}")
            import traceback
            traceback.print_exc()
    
    def _handle_drag_anomaly(self, hwnd):
        """处理拖动异常：尝试自动释放鼠标"""
        try:
            import ctypes
            import time
            
            user32 = ctypes.windll.user32
            
            # 方法 1：ReleaseCapture
            user32.ReleaseCapture()
            logger.debug("[拖动异常] 已调用 ReleaseCapture")
            
            # 方法 2：发送 WM_CANCELMODE 取消模态循环
            WM_CANCELMODE = 0x001F
            user32.PostMessageW(hwnd, WM_CANCELMODE, 0, 0)
            logger.debug("[拖动异常] 已发送 WM_CANCELMODE")
            
            # 方法 3：发送 WM_LBUTTONUP 模拟鼠标释放
            WM_LBUTTONUP = 0x0202
            user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, 0)
            logger.debug("[拖动异常] 已发送 WM_LBUTTONUP")
            
            # 方法 4：枚举子窗口并发送释放消息
            def enum_child_windows_callback(child_hwnd, lparam):
                user32.PostMessageW(child_hwnd, WM_CANCELMODE, 0, 0)
                user32.PostMessageW(child_hwnd, WM_LBUTTONUP, 0, 0)
                return True
            
            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            user32.EnumChildWindows(hwnd, EnumWindowsProc(enum_child_windows_callback), 0)
            logger.debug("[拖动异常] 已向子窗口发送释放消息")
            
            # 等待 50ms 让消息处理完成
            time.sleep(0.05)
            
            # 检查是否释放成功：获取当前窗口位置，看是否还在移动
            from backend.src.utils.window_bounds import RECT
            
            rect1 = RECT()
            user32.GetWindowRect(hwnd, ctypes.pointer(rect1))
            time.sleep(0.1)
            rect2 = RECT()
            user32.GetWindowRect(hwnd, ctypes.pointer(rect2))
            
            is_still_moving = (abs(rect1.left - rect2.left) > 1 or abs(rect1.top - rect2.top) > 1)
            
            if is_still_moving:
                # 自动释放失败，通知前端显示 Toast
                logger.warning("[拖动异常] 自动释放失败，通知前端显示 Toast")
                self._show_drag_error_toast()
            else:
                logger.info("[拖动异常] 自动释放成功")
                
        except Exception as e:
            logger.error(f"[拖动异常] 处理失败: {e}")
            import traceback
            traceback.print_exc()
            # 异常情况下也通知前端
            self._show_drag_error_toast()
    
    def _show_drag_error_toast(self):
        """通知前端显示拖动错误提示"""
        try:
            if self._window:
                js_code = """
                if (window.showDragErrorToast) {
                    window.showDragErrorToast();
                }
                """
                self._window.evaluate_js(js_code)
                logger.debug("[拖动异常] 已通知前端显示 Toast")
        except Exception as e:
            logger.error(f"[拖动异常] 通知前端失败: {e}")
    
    def forceReleaseMouse(self):
        """强制释放鼠标（供前端 ESC 键调用）"""
        try:
            import ctypes
            
            user32 = ctypes.windll.user32
            
            # 获取窗口句柄
            hwnd = None
            if hasattr(self._window, 'gui') and hasattr(self._window.gui, 'hwnd'):
                hwnd = self._window.gui.hwnd
            
            if not hwnd or hwnd == 0:
                hwnd = user32.FindWindowW(None, "ComfyNexus")
            
            if hwnd and hwnd != 0:
                # 释放鼠标捕获
                user32.ReleaseCapture()
                
                # 发送取消消息
                WM_CANCELMODE = 0x001F
                WM_LBUTTONUP = 0x0202
                user32.PostMessageW(hwnd, WM_CANCELMODE, 0, 0)
                user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, 0)
                
                # 枚举子窗口并发送释放消息
                def enum_child_windows_callback(child_hwnd, lparam):
                    user32.PostMessageW(child_hwnd, WM_CANCELMODE, 0, 0)
                    user32.PostMessageW(child_hwnd, WM_LBUTTONUP, 0, 0)
                    return True
                
                EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
                user32.EnumChildWindows(hwnd, EnumWindowsProc(enum_child_windows_callback), 0)
                
                logger.debug("[强制释放] 鼠标已释放")
                return {"success": True}
            
            return {"success": False, "error": "无法获取窗口句柄"}
            
        except Exception as e:
            logger.error(f"[强制释放] 失败: {e}")
            return {"success": False, "error": str(e)}
    
    def restoreWindowOnDrag(self, mouse_x=None, mouse_y=None):
        """
        在最大化状态下拖动时还原窗口（供前端 mousedown 事件调用）
        
        前端在最大化时使用 pywebview-no-drag 禁用原生拖动，
        由本方法完成还原并启动原生拖动操作。
        
        Args:
            mouse_x: 鼠标点击位置的 X 坐标（相对于视口）
            mouse_y: 鼠标点击位置的 Y 坐标（相对于视口）
        
        Returns:
            dict: 包含 success 和 message 的字典
        """
        if not self._window:
            logger.warning("[拖动还原] 窗口对象不存在")
            return {"success": False, "message": "窗口对象不存在"}
        
        if not self._is_maximized:
            logger.debug("[拖动还原] 窗口未最大化，无需还原")
            return {"success": False, "message": "窗口未最大化"}
        
        try:
            import ctypes
            
            user32 = ctypes.windll.user32
            
            hwnd = None
            if hasattr(self._window, 'gui') and hasattr(self._window.gui, 'hwnd'):
                hwnd = self._window.gui.hwnd
            
            if not hwnd or hwnd == 0:
                hwnd = user32.FindWindowW(None, "ComfyNexus")
            
            if not hwnd or hwnd == 0:
                logger.error("[拖动还原] 无法获取窗口句柄")
                return {"success": False, "message": "无法获取窗口句柄"}
            
            from backend.src.utils.window_bounds import POINT, MONITORINFO
            
            width, height = self._get_settings_window_size()
            logger.debug(f"[拖动还原] 从设置获取窗口大小: {width}x{height}")
            
            cursor_pos = POINT()
            user32.GetCursorPos(ctypes.pointer(cursor_pos))
            screen_mouse_x = cursor_pos.x
            screen_mouse_y = cursor_pos.y
            
            x = round(screen_mouse_x - width / 2)
            y = round(screen_mouse_y - height / 2)
            logger.debug(f"[拖动还原] 以鼠标屏幕位置 ({screen_mouse_x}, {screen_mouse_y}) 为中心计算窗口位置: ({x}, {y})")
            
            hmonitor = user32.MonitorFromPoint(cursor_pos, 2)
            monitor_info = MONITORINFO()
            monitor_info.cbSize = ctypes.sizeof(MONITORINFO)
            user32.GetMonitorInfoW(hmonitor, ctypes.pointer(monitor_info))
            work_area = monitor_info.rcWork
            
            if x < work_area.left:
                x = work_area.left
            elif x + width > work_area.right:
                x = work_area.right - width
            
            if y < work_area.top:
                y = work_area.top
            elif y + height > work_area.bottom:
                y = work_area.bottom - height
            
            GWL_STYLE = -16
            WS_MAXIMIZE = 0x01000000
            SWP_FRAMECHANGED = 0x0020
            SWP_NOZORDER = 0x0004
            SWP_NOACTIVATE = 0x0010
            
            style = user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
            if style & WS_MAXIMIZE:
                style &= ~WS_MAXIMIZE
                user32.SetWindowLongPtrW(hwnd, GWL_STYLE, style)
                logger.debug("[拖动还原] 已移除 WS_MAXIMIZE 样式")
            
            user32.SetWindowPos(hwnd, None, x, y, width, height, SWP_FRAMECHANGED | SWP_NOZORDER | SWP_NOACTIVATE)
            logger.debug(f"[拖动还原] 还原到: ({x}, {y}), 大小: {width}x{height}")
            
            self._is_maximized = False
            self._window_state = None
            
            return {
                "success": True, 
                "message": "窗口已还原",
                "windowX": round(x / self._dpi_scale),
                "windowY": round(y / self._dpi_scale)
            }
            
        except Exception as e:
            logger.error(f"[拖动还原] 异常: {e}")
            return {"success": False, "message": str(e)}
    
    def toggleFullscreen(self):
        """切换全屏模式"""
        if self._window:
            self._window.toggle_fullscreen()
            # 切换全屏状态
            self._is_fullscreen = not self._is_fullscreen
            logger.debug(f"[API] 全屏状态切换为: {self._is_fullscreen}")
    
    def fullscreenToMaximize(self):
        """
        从全屏直接切换到最大化状态
        跳过中间的恢复窗口步骤，避免闪烁
        """
        if not self._window:
            return {"success": False, "message": "窗口对象不存在"}
        
        if not self._is_fullscreen:
            return {"success": False, "message": "当前不是全屏状态"}
        
        try:
            import ctypes
            user32 = ctypes.windll.user32
            
            hwnd = None
            if hasattr(self._window, 'gui') and hasattr(self._window.gui, 'hwnd'):
                hwnd = self._window.gui.hwnd
                logger.debug(f"[全屏转最大化] 获取窗口句柄: {hwnd}")
            
            if not hwnd or hwnd == 0:
                hwnd = user32.FindWindowW(None, "ComfyNexus")
                logger.debug(f"[全屏转最大化] 通过 FindWindowW 查找窗口句柄: {hwnd}")
            
            if hwnd and hwnd != 0:
                self._save_window_rect(hwnd)
                
                from backend.src.utils.window_bounds import MONITORINFO
                
                hmonitor = user32.MonitorFromWindow(hwnd, 2)
                
                monitor_info = MONITORINFO()
                monitor_info.cbSize = ctypes.sizeof(MONITORINFO)
                user32.GetMonitorInfoW(hmonitor, ctypes.pointer(monitor_info))
                
                work_area = monitor_info.rcWork
                work_width = work_area.right - work_area.left
                work_height = work_area.bottom - work_area.top
                
                self._window.toggle_fullscreen()
                self._is_fullscreen = False
                
                user32.SetWindowPos(hwnd, None, work_area.left, work_area.top, 
                                   work_width, work_height, 0x0004)
                
                self._is_maximized = True
                logger.debug(f"[全屏转最大化] 完成，窗口大小: {work_width}x{work_height}")
                return {"success": True}
            
            return {"success": False, "message": "无法获取窗口句柄"}
            
        except Exception as e:
            logger.error(f"[全屏转最大化] 异常: {e}")
            return {"success": False, "message": str(e)}
    
    def isFullscreen(self):
        """检查是否全屏"""
        return self._is_fullscreen
    
    def moveWindow(self, x, y):
        """移动窗口，使窗口中心位于指定位置
        
        前端传入逻辑像素（CSS像素），需转换为物理像素后调用 Win32 API。
        """
        if not self._window:
            return
        
        physical_x = round(x * self._dpi_scale)
        physical_y = round(y * self._dpi_scale)
        
        try:
            import ctypes
            user32 = ctypes.windll.user32
            
            hwnd = None
            if hasattr(self._window, 'gui') and hasattr(self._window.gui, 'hwnd'):
                hwnd = self._window.gui.hwnd
            
            if not hwnd or hwnd == 0:
                hwnd = user32.FindWindowW(None, "ComfyNexus")
            
            if hwnd and hwnd != 0:
                from backend.src.utils.window_bounds import RECT
                
                rect = RECT()
                user32.GetWindowRect(hwnd, ctypes.pointer(rect))
                width = rect.right - rect.left
                height = rect.bottom - rect.top
                
                new_x = round(physical_x - width / 2)
                new_y = round(physical_y - height / 2)
                
                user32.SetWindowPos(hwnd, None, new_x, new_y, 0, 0, 0x0001 | 0x0004)
        except Exception:
            self._window.move(x, y)
    
    def moveWindowTo(self, x, y):
        """移动窗口到指定位置（窗口左上角）
        
        前端传入逻辑像素（CSS像素），需转换为物理像素后调用 Win32 API。
        """
        if not self._window:
            return
        
        physical_x = round(x * self._dpi_scale)
        physical_y = round(y * self._dpi_scale)
        
        try:
            import ctypes
            user32 = ctypes.windll.user32
            
            hwnd = None
            if hasattr(self._window, 'gui') and hasattr(self._window.gui, 'hwnd'):
                hwnd = self._window.gui.hwnd
            
            if not hwnd or hwnd == 0:
                hwnd = user32.FindWindowW(None, "ComfyNexus")
            
            if hwnd and hwnd != 0:
                user32.SetWindowPos(hwnd, None, physical_x, physical_y, 0, 0, 0x0001 | 0x0004)
        except Exception:
            self._window.move(x, y)
    
    def resizeWindow(self, width, height):
        """改变窗口大小并居中显示
        
        前端传入逻辑像素（CSS像素），内部需转换为物理像素进行边界检查，
        再转换回逻辑像素调用 pywebview API。
        
        Args:
            width: 窗口宽度（逻辑像素）
            height: 窗口高度（逻辑像素）
        """
        if not self._window:
            return False
        
        try:
            import ctypes
            
            user32 = ctypes.windll.user32
            
            screen_width = user32.GetSystemMetrics(0)
            screen_height = user32.GetSystemMetrics(1)
            
            physical_width = round(width * self._dpi_scale)
            physical_height = round(height * self._dpi_scale)
            
            max_width = round(screen_width * 0.95)
            max_height = round(screen_height * 0.95)
            
            adjusted_physical_width = min(physical_width, max_width)
            adjusted_physical_height = min(physical_height, max_height)
            
            x = max(0, (screen_width - adjusted_physical_width) // 2)
            y = max(0, (screen_height - adjusted_physical_height) // 2)
            
            logical_width = round(adjusted_physical_width / self._dpi_scale)
            logical_height = round(adjusted_physical_height / self._dpi_scale)
            logical_x = round(x / self._dpi_scale)
            logical_y = round(y / self._dpi_scale)
            
            logger.debug(f"[resizeWindow] 屏幕尺寸: {screen_width}x{screen_height}")
            logger.debug(f"[resizeWindow] 请求窗口大小: {width}x{height} (逻辑)")
            logger.debug(f"[resizeWindow] 调整后窗口大小: {logical_width}x{logical_height} (逻辑)")
            logger.debug(f"[resizeWindow] 窗口位置: ({logical_x}, {logical_y}) (逻辑)")
            
            self._window.resize(logical_width, logical_height)
            self._window.move(logical_x, logical_y)
            
            return True
        except Exception as e:
            logger.error(f"[resizeWindow] 调整窗口大小失败: {e}")
            try:
                self._window.resize(width, height)
                return True
            except (OSError, RuntimeError) as resize_error:
                logger.error(f"[resizeWindow] 降级方案也失败: {resize_error}")
                return False
    
    def resizeWindowWithPosition(self, width, height, x, y):
        """改变窗口大小并移动到指定位置（用于拖动调整窗口大小）
        
        前端传入逻辑像素（CSS像素），内部需转换为物理像素进行边界检查，
        再转换回逻辑像素调用 pywebview API。
        
        Args:
            width: 窗口宽度（逻辑像素）
            height: 窗口高度（逻辑像素）
            x: 窗口 X 坐标（逻辑像素）
            y: 窗口 Y 坐标（逻辑像素）
            
        Returns:
            bool: 操作是否成功
        """
        if not self._window:
            return False
        
        try:
            import ctypes
            
            user32 = ctypes.windll.user32
            
            virtual_x = user32.GetSystemMetrics(76)
            virtual_y = user32.GetSystemMetrics(77)
            virtual_width = user32.GetSystemMetrics(78)
            virtual_height = user32.GetSystemMetrics(79)
            
            physical_width = round(width * self._dpi_scale)
            physical_height = round(height * self._dpi_scale)
            physical_x = round(x * self._dpi_scale)
            physical_y = round(y * self._dpi_scale)
            
            min_physical_width = round(1280 * self._dpi_scale)
            min_physical_height = round(720 * self._dpi_scale)
            
            adjusted_physical_width = max(min_physical_width, min(physical_width, round(virtual_width * 0.95)))
            adjusted_physical_height = max(min_physical_height, min(physical_height, round(virtual_height * 0.95)))
            
            adjusted_physical_x = max(virtual_x, min(physical_x, virtual_x + virtual_width - adjusted_physical_width))
            adjusted_physical_y = max(virtual_y, min(physical_y, virtual_y + virtual_height - adjusted_physical_height))
            
            logical_width = round(adjusted_physical_width / self._dpi_scale)
            logical_height = round(adjusted_physical_height / self._dpi_scale)
            logical_x = round(adjusted_physical_x / self._dpi_scale)
            logical_y = round(adjusted_physical_y / self._dpi_scale)
            
            self._window.resize(logical_width, logical_height)
            self._window.move(logical_x, logical_y)
            
            return True
        except Exception as e:
            logger.error(f"[resizeWindowWithPosition] 调整窗口大小和位置失败: {e}")
            try:
                self._window.resize(width, height)
                self._window.move(x, y)
                return True
            except (OSError, RuntimeError) as fallback_error:
                logger.error(f"[resizeWindowWithPosition] 降级方案也失败: {fallback_error}")
                return False
    
    def open_url(self, url: str):
        """
        在浏览器中打开 URL（根据用户设置的浏览器）
        
        Args:
            url: 要打开的 URL 地址
            
        Returns:
            dict: 操作结果
        """
        try:
            from backend.src.utils.browser_detector import open_url_with_browser
            
            # 获取用户设置的浏览器
            browser_path = None
            try:
                from backend.src.core.settings_manager import SettingsManager
                settings = SettingsManager()
                config = settings.load_config()
                browser_path = config.get("general", {}).get("selectedBrowser", "")
                if not browser_path:
                    browser_path = None
            except Exception:
                pass
            
            success = open_url_with_browser(url, browser_path)
            
            if success:
                return {
                    "success": True,
                    "message": f"已在浏览器中打开: {url}"
                }
            else:
                return {
                    "success": False,
                    "error": "打开 URL 失败"
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"打开 URL 失败: {str(e)}"
            }
    
    def get_installed_browsers(self):
        """
        获取系统已安装的浏览器列表
        
        Returns:
            dict: 包含浏览器列表的响应
        """
        try:
            from backend.src.utils.browser_detector import get_installed_browsers
            browsers = get_installed_browsers()
            return {
                "success": True,
                "browsers": browsers
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"获取浏览器列表失败: {str(e)}",
                "browsers": []
            }
    
    def get_app_version(self):
        """
        获取应用版本号
        
        Returns:
            str: 版本号
        """
        import sys
        from pathlib import Path
        
        logger.info(f"[get_app_version] sys.frozen: {getattr(sys, 'frozen', False)}")
        logger.info(f"[get_app_version] sys._MEIPASS: {getattr(sys, '_MEIPASS', 'N/A')}")
        
        try:
            import backend
            logger.info(f"[get_app_version] backend module: {backend}")
            logger.info(f"[get_app_version] backend.__file__: {getattr(backend, '__file__', 'N/A')}")
            version = backend.get_version()
            logger.info(f"[get_app_version] version from backend.get_version(): {version}")
            return version
        except Exception as e:
            logger.error(f"[get_app_version] 导入 backend 失败: {e}")
            
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                version_file = Path(sys._MEIPASS) / "comfy_nexus_version.py"
                logger.info(f"[get_app_version] 尝试直接读取: {version_file}")
                logger.info(f"[get_app_version] 文件存在: {version_file.exists()}")
                if version_file.exists():
                    content = version_file.read_text(encoding='utf-8')
                    logger.info(f"[get_app_version] 文件内容: {content}")
                    for line in content.splitlines():
                        if line.startswith('__version__'):
                            version = line.split('=')[1].strip().strip('"').strip("'")
                            logger.info(f"[get_app_version] 解析版本: {version}")
                            return version
            return "1.0.0"
    
    # ========== 模块配置管理 API ==========
    
    def get_module_config(self):
        """
        获取模块配置
        
        Returns:
            dict: 模块配置对象
        """
        try:
            manager = self._module_config_manager
            config = manager.load_config()
            
            # 确保返回有效的配置对象
            if config is None:
                logger.warning("[API] get_module_config 返回 None，使用默认配置")
                # 返回默认配置结构
                return {
                    "modules": {
                        "home": {"enabled": True, "order": 0},
                        "core": {"enabled": True, "order": 1},
                        "plugins": {"enabled": True, "order": 2},
                        "terminal": {"enabled": True, "order": 3},
                        "settings": {"enabled": True, "order": 4}
                    }
                }
            
            logger.debug(f"[API] get_module_config 成功，模块数量: {len(config.get('modules', {}))}")
            return config
            
        except Exception as e:
            logger.error(f"[API] get_module_config 异常: {e}")
            import traceback
            traceback.print_exc()
            
            # 返回默认配置
            return {
                "modules": {
                    "home": {"enabled": True, "order": 0},
                    "core": {"enabled": True, "order": 1},
                    "plugins": {"enabled": True, "order": 2},
                    "terminal": {"enabled": True, "order": 3},
                    "settings": {"enabled": True, "order": 4}
                }
            }
    
    def save_module_config(self, config):
        """
        保存模块配置
        
        Args:
            config: 模块配置对象
            
        Returns:
            bool: 保存是否成功
        """
        return self._module_config_manager.save_config(config)
    
    def reset_module_config(self):
        """
        重置模块配置为默认值
        
        Returns:
            dict: 重置后的完整配置，失败时返回 None
        """
        success = self._module_config_manager.reset_config()
        if success:
            return self._module_config_manager.load_config()
        return None
    
    # ========== Environment Management API ==========
    
    def get_environments(self):
        """
        Get all environments.
        
        Returns:
            dict: Environments list response
        """
        try:
            result = self._environment_controller.get_environments()
            
            # 确保返回结构完整，即使环境列表为空
            if result.get("success"):
                environments = result.get("environments", [])
                current_id = result.get("current_environment_id")
                
                logger.debug(f"[API] get_environments 成功，环境数量: {len(environments)}")
                
                return {
                    "success": True,
                    "environments": environments,
                    "current_environment_id": current_id
                }
            else:
                error_msg = result.get("error_message", "未知错误")
                logger.error(f"[API] get_environments 失败: {error_msg}")
                
                return {
                    "success": False,
                    "error_message": error_msg,
                    "environments": [],
                    "current_environment_id": None
                }
        except Exception as e:
            logger.error(f"[API] get_environments 异常: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "success": False,
                "error_message": str(e),
                "environments": [],
                "current_environment_id": None
            }
    
    def add_environment(self, path, name=None, lang="en"):
        """
        Add a new environment.
        
        Args:
            path: Path to ComfyUI installation
            name: Optional name for the environment
            lang: Language code ("en" or "zh")
            
        Returns:
            dict: Operation result
        """
        result = self._environment_controller.add_environment(path, name, lang)

        if result.get("success"):
            # 添加环境后重置工作流控制器，确保下次访问时重新初始化
            self._workflow_controller.reset_initialization()

            # 清空 node_mapper 的本地插件缓存，确保下次检查时重新扫描
            from backend.src.utils.node_mapper import node_mapper
            node_mapper._local_plugins.clear()
            logger.info(f"环境添加成功，已重置工作流控制器和清空本地插件缓存")

        return result
    
    def delete_environment(self, env_id):
        """
        Delete an environment.
        
        Args:
            env_id: Environment ID
            
        Returns:
            dict: Operation result
        """
        result = self._environment_controller.delete_environment(env_id)
        if result.get("success"):
            self._workflow_config_manager.remove_env_path(env_id)
        return result
    
    def set_current_environment(self, env_id):
        """
        Set the current active environment.
        
        Args:
            env_id: Environment ID
            
        Returns:
            dict: Operation result
        """
        result = self._environment_controller.set_current_environment(env_id)
        
        if result.get("success"):
            self._workflow_controller.reset_initialization()
            
            # 清空 node_mapper 的本地插件缓存，确保下次检查时重新扫描
            from backend.src.utils.node_mapper import node_mapper
            node_mapper._local_plugins.clear()
            logger.info(f"环境切换成功，已重置工作流控制器和清空本地插件缓存: {env_id}")
        
        return result
    
    def reorder_environments(self, env_ids):
        """
        Reorder environments.
        
        Args:
            env_ids: List of environment IDs in the new order
            
        Returns:
            dict: Operation result
        """
        return self._environment_controller.reorder_environments(env_ids)
    
    def update_environment(self, env_id, config):
        """
        Update environment configuration.
        
        Args:
            env_id: Environment ID
            config: Configuration dictionary
            
        Returns:
            dict: Operation result
        """
        return self._environment_controller.update_environment(env_id, config)
    
    def scan_environment(self, path, lang="en"):
        """
        Scan a ComfyUI environment.
        
        Args:
            path: Path to ComfyUI installation
            lang: Language code ("en" or "zh")
            
        Returns:
            dict: Scan results
        """
        return self._environment_controller.scan_environment(path, lang)
    
    def get_dependencies(self, env_id):
        """
        Get dependency information for an environment.
        
        Args:
            env_id: Environment ID
            
        Returns:
            dict: Dependency information
        """
        return self._environment_controller.get_dependencies(env_id)
    
    def select_directory(self):
        """
        Open directory selection dialog.
        
        Returns:
            dict: Selected directory path
        """
        return self._environment_controller.select_directory()
    
    def select_file(self, file_types=()):
        """
        Open file selection dialog.
        
        Args:
            file_types: Tuple of file type filters
        
        Returns:
            dict: Selected file path
        """
        return self._environment_controller.select_file(file_types)
    
    def save_file_dialog(self, default_name: str = "", file_filter: str = "JSON files (*.json)"):
        """
        Open file save dialog.
        
        Args:
            default_name: Default file name
            file_filter: File filter
            
        Returns:
            dict: Save file path
        """
        return self._environment_controller.save_file_dialog(default_name, file_filter)
    
    def save_preset_to_file(self, file_path: str, preset_data: dict):
        """
        Save preset data to file.
        
        Args:
            file_path: File save path
            preset_data: Preset data
            
        Returns:
            dict: Operation result
        """
        return self._environment_controller.save_preset_to_file(file_path, preset_data)

    def batch_export_presets(self, presets_data: list, save_path: str):
        """
        批量导出预设到文件
        
        Args:
            presets_data: 预设数据列表
            save_path: 保存路径
        """
        return self._environment_controller.batch_export_presets(presets_data, save_path)

    def save_image_with_dialog(self, image_url: str, suggested_filename: str = None) -> dict:
        """
        显示文件保存对话框并下载图片
        
        该方法是图片下载功能的核心入口，负责协调整个下载流程：
        1. 验证图片 URL 的有效性
        2. 从配置中读取上次的下载路径
        3. 显示系统原生的文件保存对话框
        4. 下载图片到用户选择的位置
        5. 保存下载路径以便下次使用
        
        工作流程：
        - 参数验证 → 读取配置 → 显示对话框 → 下载图片 → 保存配置 → 返回结果
        
        错误处理：
        - USER_CANCELLED: 用户取消操作（静默处理）
        - INVALID_URL: 图片 URL 无效或无法访问
        - DOWNLOAD_FAILED: 网络下载失败
        - PERMISSION_DENIED: 文件系统权限不足
        - DISK_FULL: 磁盘空间不足
        - TKINTER_UNAVAILABLE: 文件对话框不可用
        - UNKNOWN_ERROR: 其他未知错误

        Args:
            image_url: 图片完整 URL（支持 http/https/data 协议）
            suggested_filename: 建议的文件名（可选，如果不提供则自动生成）

        Returns:
            dict: {
                "success": bool,           # 操作是否成功
                "message": str,            # 成功或错误信息
                "saved_path": str,         # 保存的完整路径（仅成功时）
                "error_code": str          # 错误代码（仅失败时）
            }
        """
        import os
        import traceback
        from datetime import datetime

        try:
            logger.info("[图片下载] ===== 开始图片保存流程 =====")
            
            # ========== 步骤 1: 验证 image_url 参数 ==========
            # 确保 URL 不为空且格式正确
            if not image_url:
                logger.error("[图片下载] 参数验证失败: image_url 为空")
                return {
                    "success": False,
                    "message": "图片 URL 不能为空",
                    "error_code": "INVALID_URL"
                }

            # 使用 image_downloader 模块验证 URL 格式和协议
            if not image_downloader.validate_image_url(image_url):
                logger.error("[图片下载] URL 验证失败")
                return {
                    "success": False,
                    "message": "无法访问图片",
                    "error_code": "INVALID_URL"
                }

            logger.debug(f"[图片下载] URL 验证通过: {image_url[:100]}{'...' if len(image_url) > 100 else ''}")

            # ========== 步骤 2: 读取初始下载目录 ==========
            # 优先从 WebView2 Preferences 读取（与浏览器行为一致）
            # 如果读取失败，则从 SettingsManager 读取
            from backend.src.utils.webview2_preferences import WebView2PreferencesManager
            
            settings_manager = SettingsManager()
            webview2_prefs = WebView2PreferencesManager()
            
            # 始终读取应用配置，作为 WebView2 Preferences 不可用时的稳定回退。
            settings_initial_dir = settings_manager.get_last_download_path()

            # 尝试从 WebView2 Preferences 读取
            initial_dir = webview2_prefs.get_last_download_directory()
            
            # 如果 WebView2 Preferences 中没有，则从 SettingsManager 读取
            if not initial_dir:
                initial_dir = settings_initial_dir
                logger.debug(f"[图片下载] 从 SettingsManager 读取初始目录: {initial_dir}")
            else:
                logger.debug(f"[图片下载] 从 WebView2 Preferences 读取初始目录: {initial_dir}")
            
            logger.info(f"[图片下载] 初始目录: {initial_dir}")

            # ========== 步骤 3: 生成建议的文件名（如果未提供）==========
            # 如果前端没有提供文件名，使用时间戳生成一个默认文件名
            if not suggested_filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                suggested_filename = f"image_{timestamp}.png"
                logger.debug(f"[图片下载] 自动生成文件名: {suggested_filename}")
            else:
                logger.debug(f"[图片下载] 使用建议文件名: {suggested_filename}")

            # 确保文件名有扩展名（如果用户提供的文件名没有扩展名，添加默认的 .png）
            if not os.path.splitext(suggested_filename)[1]:
                suggested_filename += ".png"
                logger.debug(f"[图片下载] 添加默认扩展名: {suggested_filename}")

            # ========== 步骤 4: 调用 tkinter.filedialog.asksaveasfilename() 显示对话框 ==========
            # 使用系统原生的文件保存对话框，让用户选择保存位置
            # 降级处理：如果 tkinter 不可用（例如无 GUI 环境），记录警告并返回错误
            try:
                logger.info("[图片下载] 打开文件保存对话框")
                logger.debug(f"[图片下载] 对话框参数 - 初始目录: {initial_dir}, 建议文件名: {suggested_filename}")

                # 显示文件保存对话框
                # - title: 对话框标题
                # - initialdir: 初始目录（上次保存的位置）
                # - initialfile: 建议的文件名
                # - defaultextension: 默认扩展名
                # - filetypes: 文件类型过滤器
                file_path = filedialog.asksaveasfilename(
                    title="保存图片",
                    initialdir=initial_dir,
                    initialfile=suggested_filename,
                    defaultextension=".png",
                    filetypes=[
                        ("PNG 图片", "*.png"),
                        ("JPEG 图片", "*.jpg;*.jpeg"),
                        ("GIF 图片", "*.gif"),
                        ("WebP 图片", "*.webp"),
                        ("所有文件", "*.*")
                    ]
                )
            except Exception as tk_error:
                # tkinter 不可用的情况（例如无 GUI 环境、tkinter 未安装等）
                logger.warning(f"[图片下载] tkinter 文件对话框不可用: {tk_error}")
                logger.warning("[图片下载] 降级处理：建议使用浏览器默认下载功能")
                return {
                    "success": False,
                    "message": "文件对话框不可用，请使用浏览器默认下载功能",
                    "error_code": "TKINTER_UNAVAILABLE"
                }

            # ========== 步骤 5: 处理用户取消的情况 ==========
            # 如果用户点击了"取消"按钮，file_path 会是空字符串
            # 这种情况下静默处理，不显示错误提示
            if not file_path:
                logger.info("[图片下载] 用户取消了保存操作")
                return {
                    "success": False,
                    "message": "用户取消",
                    "error_code": "USER_CANCELLED"
                }

            logger.info(f"[图片下载] 用户选择的保存路径: {file_path}")

            # ========== 步骤 6: 调用 download_image() 下载图片 ==========
            # 使用 image_downloader 模块下载图片到用户选择的路径
            logger.info("[图片下载] 开始下载图片到本地")
            download_success = image_downloader.download_image(image_url, file_path)

            if not download_success:
                logger.error("[图片下载] 图片下载失败")
                return {
                    "success": False,
                    "message": "下载失败，请重试",
                    "error_code": "DOWNLOAD_FAILED"
                }

            # ========== 步骤 7: 同步保存下载路径到两个位置 ==========
            # 1. 保存到 SettingsManager（应用配置）
            # 2. 保存到 WebView2 Preferences（浏览器配置）
            # 这样可以确保路径记忆功能在两个系统中都生效
            logger.debug("[图片下载] 同步保存下载路径到配置")
            
            # 保存到 SettingsManager
            settings_save_success = settings_manager.set_last_download_path(file_path)
            if settings_save_success:
                logger.info(f"[图片下载] ✅ 已更新 SettingsManager 配置: {os.path.dirname(file_path)}")
            else:
                logger.warning("[图片下载] ⚠️  保存到 SettingsManager 失败")
            
            # 保存到 WebView2 Preferences
            webview2_save_success = webview2_prefs.sync_from_file_path(file_path)
            if webview2_save_success:
                logger.info(f"[图片下载] ✅ 已更新 WebView2 Preferences: {os.path.dirname(file_path)}")
            else:
                logger.warning("[图片下载] ⚠️  保存到 WebView2 Preferences 失败")
            
            # 只要有一个保存成功就认为是成功的
            if not (settings_save_success or webview2_save_success):
                logger.warning("[图片下载] ⚠️  所有配置保存都失败（图片已成功保存）")

            # ========== 步骤 8: 返回成功结果 ==========
            logger.info(f"[图片下载] ===== 图片保存成功 =====")
            logger.info(f"[图片下载] 保存位置: {file_path}")
            return {
                "success": True,
                "message": "图片已保存",
                "saved_path": file_path
            }

        except PermissionError as e:
            # 权限错误：用户选择的路径没有写入权限
            logger.error(f"[图片下载] 权限错误: 没有写入权限")
            logger.debug(f"[图片下载] 异常详情: {e}")
            logger.debug(f"[图片下载] 错误堆栈:\n{traceback.format_exc()}")
            return {
                "success": False,
                "message": "没有写入权限，请选择其他位置",
                "error_code": "PERMISSION_DENIED"
            }
        except OSError as e:
            # 文件系统错误：磁盘空间不足、路径无效等
            # 特别检查磁盘空间不足的情况
            error_msg = str(e)
            if "No space left on device" in error_msg or "磁盘空间不足" in error_msg:
                logger.error("[图片下载] 磁盘空间不足")
                logger.debug(f"[图片下载] 异常详情: {e}")
                logger.debug(f"[图片下载] 错误堆栈:\n{traceback.format_exc()}")
                return {
                    "success": False,
                    "message": "磁盘空间不足",
                    "error_code": "DISK_FULL"
                }
            else:
                logger.error(f"[图片下载] 文件系统错误: {error_msg}")
                logger.debug(f"[图片下载] 错误堆栈:\n{traceback.format_exc()}")
                return {
                    "success": False,
                    "message": "保存失败，请查看日志",
                    "error_code": "UNKNOWN_ERROR"
                }
        except Exception as e:
            # 未知错误：记录详细信息以便调试
            logger.error(f"[图片下载] 未知错误: {e}")
            logger.error(f"[图片下载] 图片 URL: {image_url[:100]}{'...' if len(image_url) > 100 else ''}")
            logger.error(f"[图片下载] 错误堆栈:\n{traceback.format_exc()}")
            return {
                "success": False,
                "message": "保存失败，请查看日志",
                "error_code": "UNKNOWN_ERROR"
            }

    def inject_script_to_comfyui_iframe(self, script_content: str) -> dict:
        """
        注入脚本到 ComfyUI iframe
        
        该方法使用 pywebview 的 evaluate_js 方法，可以绕过浏览器的跨域限制。
        
        工作原理：
        1. 在主窗口的上下文中执行 JavaScript
        2. 查找 ComfyUI iframe
        3. 通过 contentDocument 创建 <script> 标签
        4. 将脚本内容插入到 iframe 的 <head> 中
        
        注意：
        - 这个方法只能在 pywebview 环境中使用
        - 脚本内容中的特殊字符需要转义
        
        Args:
            script_content: 要注入的 JavaScript 脚本内容
            
        Returns:
            dict: {
                "success": bool,
                "message": str
            }
        """
        try:
            logger.info("[脚本注入] ===== 开始注入脚本到 ComfyUI iframe =====")
            
            if not self._window:
                logger.error("[脚本注入] 错误：窗口对象不存在")
                return {
                    "success": False,
                    "message": "窗口对象不存在"
                }
            
            # 转义脚本内容中的特殊字符
            # 1. 反斜杠需要转义为 \\
            # 2. 反引号需要转义为 \`
            # 3. ${} 需要转义为 \${}
            escaped_script = script_content.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')
            
            logger.debug(f"[脚本注入] 脚本内容长度: {len(script_content)} 字符")
            logger.debug(f"[脚本注入] 转义后长度: {len(escaped_script)} 字符")
            
            # 构造注入脚本的 JavaScript 代码
            injection_js = f"""
            (function() {{
                console.log('[后端脚本注入] ===== 开始执行 =====');
                console.log('[后端脚本注入] 当前 URL:', window.location.href);
                
                // 查找 ComfyUI iframe
                const iframes = document.querySelectorAll('iframe');
                console.log('[后端脚本注入] 找到 iframe 数量:', iframes.length);
                
                const iframe = Array.from(iframes).find(
                    iframe => iframe.title === 'ComfyUI Workspace' || iframe.src.includes('8188')
                );
                
                if (!iframe) {{
                    console.error('[后端脚本注入] ❌ 找不到 ComfyUI iframe');
                    console.log('[后端脚本注入] 所有 iframe:', Array.from(iframes).map(f => ({{
                        title: f.title,
                        src: f.src
                    }})));
                    return false;
                }}
                
                console.log('[后端脚本注入] ✅ 找到 iframe');
                console.log('[后端脚本注入] iframe.src:', iframe.src);
                console.log('[后端脚本注入] iframe.title:', iframe.title);
                
                // 尝试访问 contentDocument
                try {{
                    console.log('[后端脚本注入] 尝试访问 contentDocument...');
                    const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                    
                    if (!iframeDoc) {{
                        console.error('[后端脚本注入] ❌ 无法访问 contentDocument');
                        console.log('[后端脚本注入] iframe.contentDocument:', iframe.contentDocument);
                        console.log('[后端脚本注入] iframe.contentWindow:', iframe.contentWindow);
                        return false;
                    }}
                    
                    console.log('[后端脚本注入] ✅ 成功访问 contentDocument');
                    console.log('[后端脚本注入] iframeDoc.readyState:', iframeDoc.readyState);
                    console.log('[后端脚本注入] iframeDoc.URL:', iframeDoc.URL);
                    
                    // 检查脚本是否已经注入
                    let script = iframeDoc.getElementById('comfyui-download-script');
                    if (script) {{
                        console.log('[后端脚本注入] ⚠️  脚本已存在，先移除');
                        script.remove();
                    }}
                    
                    // 创建新的 <script> 标签
                    console.log('[后端脚本注入] 创建 <script> 标签...');
                    script = iframeDoc.createElement('script');
                    script.id = 'comfyui-download-script';
                    script.textContent = `{escaped_script}`;
                    
                    console.log('[后端脚本注入] 脚本内容长度:', script.textContent.length);
                    
                    // 插入到 <head> 中
                    const head = iframeDoc.head || iframeDoc.getElementsByTagName('head')[0];
                    if (!head) {{
                        console.error('[后端脚本注入] ❌ 找不到 <head> 标签');
                        console.log('[后端脚本注入] iframeDoc.documentElement:', iframeDoc.documentElement);
                        return false;
                    }}
                    
                    console.log('[后端脚本注入] ✅ 找到 <head> 标签');
                    head.appendChild(script);
                    console.log('[后端脚本注入] ✅ 脚本已插入到 <head>');
                    
                    // 验证脚本是否成功插入
                    const insertedScript = iframeDoc.getElementById('comfyui-download-script');
                    if (insertedScript) {{
                        console.log('[后端脚本注入] ✅✅✅ 脚本注入成功！');
                        return true;
                    }} else {{
                        console.error('[后端脚本注入] ❌ 脚本插入后无法找到');
                        return false;
                    }}
                    
                }} catch (error) {{
                    console.error('[后端脚本注入] ❌ 注入失败:', error.message);
                    console.error('[后端脚本注入] 错误堆栈:', error.stack);
                    return false;
                }}
            }})();
            """
            
            logger.debug("[脚本注入] 开始执行注入脚本")
            
            # 使用 pywebview 的 evaluate_js 方法执行脚本
            result = self._window.evaluate_js(injection_js)
            
            logger.debug(f"[脚本注入] evaluate_js 返回结果: {result}")
            
            if result:
                logger.info("[脚本注入] ✅ 脚本注入成功")
                return {
                    "success": True,
                    "message": "脚本注入成功"
                }
            else:
                logger.warning("[脚本注入] ⚠️  脚本注入失败（可能是跨域限制）")
                return {
                    "success": False,
                    "message": "脚本注入失败，可能是跨域限制"
                }
                
        except Exception as e:
            logger.error(f"[脚本注入] 异常: {e}")
            import traceback
            logger.error(f"[脚本注入] 错误堆栈:\n{traceback.format_exc()}")
            return {
                "success": False,
                "message": f"脚本注入异常: {str(e)}"
            }

    
    def export_config(self, env_id):
        """
        Export environment configuration.
        
        Args:
            env_id: Environment ID
            
        Returns:
            dict: Exported configuration
        """
        return self._environment_controller.export_config(env_id)
    
    def import_config(self, config_data):
        """
        Import environment configuration.
        
        Args:
            config_data: Configuration JSON string
            
        Returns:
            dict: Operation result
        """
        return self._environment_controller.import_config(config_data)
    
    def get_compute_devices(self):
        """
        获取计算设备列表
        
        Returns:
            dict: 设备列表响应
        """
        return self._environment_controller.get_compute_devices()

    def get_pytorch_backend(self, env_id):
        """
        获取指定环境的 PyTorch 后端信息

        Args:
            env_id: 环境 ID

        Returns:
            dict: PyTorch 后端信息
        """
        return self._environment_controller.get_pytorch_backend(env_id)

    def get_filtered_compute_devices(self, env_id):
        """
        获取过滤后的计算设备列表（根据 PyTorch 后端兼容性）

        Args:
            env_id: 环境 ID

        Returns:
            dict: 过滤后的设备列表和 PyTorch 后端信息
        """
        return self._environment_controller.get_filtered_compute_devices(env_id)

    
    def apply_preset(self, env_id, preset_id):
        """
        应用预设方案到环境
        
        Args:
            env_id: 环境 ID
            preset_id: 预设方案 ID
            
        Returns:
            dict: 操作结果
        """
        return self._environment_controller.apply_preset(env_id, preset_id)
    
    def get_presets(self):
        """
        获取所有预设方案
        
        Returns:
            dict: 预设方案列表
        """
        return self._environment_controller.get_presets()
    
    def add_model_path_config(self, env_id, config):
        """
        添加模型路径配置
        
        Args:
            env_id: 环境 ID
            config: 模型路径配置字典
            
        Returns:
            dict: 操作结果
        """
        return self._environment_controller.add_model_path_config(env_id, config)
    
    def update_model_path_config(self, env_id, config_name, config):
        """
        更新模型路径配置
        
        Args:
            env_id: 环境 ID
            config_name: 配置名称
            config: 新的模型路径配置字典
            
        Returns:
            dict: 操作结果
        """
        return self._environment_controller.update_model_path_config(env_id, config_name, config)
    
    def delete_model_path_config(self, env_id, config_name):
        """
        删除模型路径配置
        
        Args:
            env_id: 环境 ID
            config_name: 配置名称
            
        Returns:
            dict: 操作结果
        """
        return self._environment_controller.delete_model_path_config(env_id, config_name)
    
    def generate_model_paths_yaml(self, env_id):
        """
        生成模型路径 YAML 文件
        
        Args:
            env_id: 环境 ID
            
        Returns:
            dict: 操作结果
        """
        return self._environment_controller.generate_model_paths_yaml(env_id)
    
    def detect_model_paths_structure(self, path):
        """
        检测目录结构，识别模型路径配置
        
        Args:
            path: 要检测的目录路径
            
        Returns:
            dict: {
                "success": True,
                "is_comfyui_style": bool,
                "detected_paths": {...}
            }
        """
        return self._environment_controller.detect_model_paths_structure(path)
    
    def get_launch_args(self, env_id):
        """
        获取启动参数列表
        
        Args:
            env_id: 环境 ID
            
        Returns:
            dict: 启动参数列表
        """
        return self._environment_controller.get_launch_args(env_id)
    
    # ========== 预设管理 API ==========
    
    def export_preset(self, env_id, name, description="", vram_requirement="N/A"):
        """
        导出当前环境配置为预设
        
        Args:
            env_id: 环境 ID
            name: 预设名称
            description: 预设描述
            vram_requirement: 显存需求
            
        Returns:
            dict: 操作结果
        """
        
        return self._environment_controller.export_preset(env_id, name, description, vram_requirement)
    
    def import_preset(self, preset_data, env_id):
        """
        从预设数据导入配置到环境
        
        Args:
            preset_data: 预设数据字典
            env_id: 目标环境 ID
            
        Returns:
            dict: 操作结果
        """
        return self._environment_controller.import_preset(preset_data, env_id)
    
    def create_custom_preset(self, env_id, preset_id=None, name="用户预设", description=""):
        """
        创建用户预设
        
        Args:
            env_id: 源环境 ID
            preset_id: 预设 ID，可选（不提供则自动生成）
            name: 预设名称
            description: 预设描述
            
        Returns:
            dict: 操作结果
        """
        return self._environment_controller.create_custom_preset(env_id, preset_id, name, description)
    
    def delete_custom_preset(self, preset_id):
        """
        删除用户预设
        
        Args:
            preset_id: 预设 ID
            
        Returns:
            dict: 操作结果
        """
        return self._environment_controller.delete_custom_preset(preset_id)
    
    def update_custom_preset(self, preset_id, updates):
        """
        更新用户预设
        
        Args:
            preset_id: 预设 ID
            updates: 更新字段字典（name, description, config 等）
            
        Returns:
            dict: 操作结果
        """
        return self._environment_controller.update_custom_preset(preset_id, updates)
    
    def get_preset_details(self, preset_id):
        """
        获取预设详细信息
        
        Args:
            preset_id: 预设 ID
            
        Returns:
            dict: 预设详情
        """
        return self._environment_controller.get_preset_details(preset_id)
    
    def get_all_presets(self):
        """
        获取所有预设列表（包含索引信息）
        
        Returns:
            dict: 预设列表
        """
        return self._environment_controller.get_all_presets()
    
    # ========== 配置管理 API ==========
    
    def validate_config(self, config):
        """
        验证配置的完整性和正确性
        
        Args:
            config: 配置字典
            
        Returns:
            dict: 验证结果 {is_valid, errors, warnings}
        """
        from backend.src.core.env.config_validator import ConfigValidator
        
        try:
            # 根据配置类型选择验证方法
            if 'acceleration' in config or 'general' in config:
                # 环境配置
                result = ConfigValidator.validate_environment_config(config)
            elif 'config' in config and 'id' in config:
                # 预设配置
                result = ConfigValidator.validate_preset_config(config)
            elif all(k in config for k in ['vram_mode', 'use_cpu', 'unet_precision']):
                # 加速配置
                result = ConfigValidator.validate_acceleration_config(config)
            elif 'comfyui_path' in config and 'python_path' in config:
                # 通用配置
                result = ConfigValidator.validate_general_config(config)
            else:
                result = {
                    "is_valid": False,
                    "errors": ["无法识别的配置类型"],
                    "warnings": []
                }
            
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error_message": str(e)}
    
    def get_config_version_info(self):
        """
        获取配置版本信息
        
        Returns:
            dict: 版本信息
        """
        from backend.src.core.env.config_version_manager import get_config_version_info
        
        return {"success": True, "data": get_config_version_info()}
    
    def migrate_config(self, config, from_version=None, to_version=None):
        """
        迁移配置到指定版本
        
        Args:
            config: 要迁移的配置
            from_version: 源版本（可选）
            to_version: 目标版本（可选，默认为当前版本）
            
        Returns:
            dict: 迁移结果 {config, logs}
        """
        from backend.src.core.env.config_version_manager import ConfigVersionManager
        
        try:
            migrated_config, logs = ConfigVersionManager.migrate_config(
                config, from_version, to_version
            )
            return {
                "success": True,
                "data": {
                    "config": migrated_config,
                    "logs": logs
                }
            }
        except Exception as e:
            return {"success": False, "error_message": str(e)}
    
    def upgrade_config_to_latest(self, config):
        """
        升级配置到最新版本
        
        Args:
            config: 要升级的配置
            
        Returns:
            dict: 升级结果 {config, logs}
        """
        from backend.src.core.env.config_version_manager import ConfigVersionManager
        
        try:
            migrated_config, logs = ConfigVersionManager.upgrade_to_latest(config)
            return {
                "success": True,
                "data": {
                    "config": migrated_config,
                    "logs": logs
                }
            }
        except Exception as e:
            return {"success": False, "error_message": str(e)}
    
    def transform_config_to_frontend(self, config):
        """
        将后端配置（snake_case）转换为前端配置（camelCase）
        
        Args:
            config: 后端配置字典
            
        Returns:
            dict: 前端配置字典
        """
        from backend.src.core.env.config_transformer import ConfigTransformer
        
        return {
            "success": True,
            "data": ConfigTransformer.backend_to_frontend(config)
        }
    
    def transform_config_to_backend(self, config):
        """
        将前端配置（camelCase）转换为后端配置（snake_case）
        
        Args:
            config: 前端配置字典
            
        Returns:
            dict: 后端配置字典
        """
        from backend.src.core.env.config_transformer import ConfigTransformer
        
        return {
            "success": True,
            "data": ConfigTransformer.frontend_to_backend(config)
        }

    
    # ========== ComfyUI 进程管理 API ==========
    
    def __init_process_manager(self):
        """初始化进程管理器（延迟初始化）"""
        if not hasattr(self, '_comfyui_process'):
            from backend.src.core.process.comfyui_process import ComfyUIProcess
            self._comfyui_process = ComfyUIProcess(self._window)
            # 将进程实例传递给版本控制器
            self._version_controller.set_comfyui_process(self._comfyui_process)
            # 将进程实例传递给救援模式控制器
            self._rescue_controller.set_process_manager(self._comfyui_process)
    
    def get_current_log_file(self):
        """
        获取当前日志文件路径
        
        Returns:
            dict: 日志文件路径
        """
        try:
            self.__init_process_manager()
            
            log_file_path = self._comfyui_process.get_log_file_path()
            
            return {
                "success": True,
                "log_file_path": log_file_path
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def read_log_file(self, file_path: str = None):
        """
        读取日志文件内容
        
        Args:
            file_path: 日志文件路径（可选，默认读取当前日志文件）
            
        Returns:
            dict: 日志文件内容
        """
        try:
            self.__init_process_manager()
            
            # 如果没有指定文件路径，使用当前日志文件
            if not file_path:
                file_path = self._comfyui_process.get_log_file_path()
            
            if not file_path:
                return {
                    "success": False,
                    "error": "没有可用的日志文件"
                }
            
            # 读取文件内容
            from pathlib import Path
            log_path = Path(file_path)
            
            if not log_path.exists():
                return {
                    "success": False,
                    "error": f"日志文件不存在: {file_path}"
                }
            
            with open(log_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return {
                "success": True,
                "content": content,
                "file_path": file_path
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def list_log_files(self):
        """
        列出所有历史日志文件
        
        Returns:
            dict: 日志文件列表
        """
        try:
            from pathlib import Path
            import os
            import sys
            
            # 获取项目根目录
            from backend.src.utils.paths import get_project_root
            project_root = get_project_root()
            
            # 查询 ComfyUI 运行日志
            logs_dir = project_root / "logs" / "comfyui"
            
            if not logs_dir.exists():
                return {
                    "success": True,
                    "log_files": []
                }
            
            # 获取所有日志文件
            log_files = []
            for file_path in logs_dir.glob("comfyui_*.log"):
                stat = os.stat(file_path)
                log_files.append({
                    "path": str(file_path),
                    "name": file_path.name,
                    "size": stat.st_size,
                    "created_time": datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                    "modified_time": datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                })
            
            # 按创建时间倒序排序
            log_files.sort(key=lambda x: x['created_time'], reverse=True)
            
            return {
                "success": True,
                "log_files": log_files
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def start_comfyui(self, env_id):
        """
        启动 ComfyUI
        
        Args:
            env_id: 环境 ID
            
        Returns:
            dict: 操作结果
        """
        try:
            logger.debug(f'[start_comfyui] 开始启动 ComfyUI, env_id={env_id}')
            
            # 初始化进程管理器
            self.__init_process_manager()
            logger.debug(f'[start_comfyui] 进程管理器初始化完成')
            
            # 检查是否已经在运行
            if self._comfyui_process.is_running:
                logger.debug(f'[start_comfyui] ComfyUI 已在运行中')
                return {
                    "success": False,
                    "error": "ComfyUI 已经在运行中"
                }
            
            # 获取环境配置
            logger.debug(f'[start_comfyui] 获取环境配置...')
            result = self._environment_controller.manager.get_environment(env_id)
            logger.debug(f'[start_comfyui] get_environment 返回: success={result.get("success")}')
            
            if not result.get("success"):
                error_msg = result.get("error_message", "环境不存在")
                logger.debug(f'[start_comfyui] 获取环境失败: {error_msg}')
                return {
                    "success": False,
                    "error": f"环境不存在: {error_msg}"
                }
            
            env = result.get("environment")
            logger.debug(f'[start_comfyui] environment 类型: {type(env).__name__}')
            logger.debug(f'[start_comfyui] environment keys: {list(env.keys()) if isinstance(env, dict) else "N/A"}')
            
            # 直接从 env 获取 general 和 acceleration（顶层字段）
            general = env.get("general", {})
            acceleration = env.get("acceleration", {})
            
            logger.debug(f'[start_comfyui] general keys: {list(general.keys())}')
            logger.debug(f'[start_comfyui] acceleration keys: {list(acceleration.keys())}')
            
            # 确保 acceleration 是字典类型（防止传递 EnvironmentConfig 对象）
            if not isinstance(acceleration, dict):
                logger.debug(f'[start_comfyui] acceleration 不是字典，尝试转换...')
                if hasattr(acceleration, 'to_dict'):
                    acceleration = acceleration.to_dict()
                else:
                    acceleration = {}
            
            # 获取路径（使用驼峰命名）
            python_path = general.get("pythonPath")
            comfyui_path = general.get("comfyuiPath")
            
            logger.debug(f'[start_comfyui] python_path: {python_path}')
            logger.debug(f'[start_comfyui] comfyui_path: {comfyui_path}')
            
            if not python_path or not comfyui_path:
                logger.debug(f'[start_comfyui] 路径配置不完整')
                return {
                    "success": False,
                    "error": "环境配置不完整，缺少 Python 或 ComfyUI 路径"
                }
            
            # 构建启动参数
            logger.debug(f'[start_comfyui] 构建启动参数...')
            args = self._build_launch_args(acceleration)
            
            # 补充模型路径配置
            model_path_configs = env.get('modelPathConfigs', [])
            if model_path_configs:
                has_extra_model_paths = any(
                    '--extra-model-paths-config' in str(a) for a in args
                )
                if not has_extra_model_paths:
                    args.extend(["--extra-model-paths-config", "extra_model_paths.yaml"])
            
            logger.debug(f'[start_comfyui] 启动参数: {args}')
            
            # 准备环境配置（包含 advanced_env_vars, env_type, desktop_data_path）
            advanced_env_vars = env.get('advancedEnvVars', '')
            env_config = {
                'advanced_env_vars': advanced_env_vars,
                'env_type': env.get('envType', 'portable'),
                'desktop_data_path': env.get('desktopDataPath', ''),
                'acceleration': acceleration
            }
            logger.debug(f'[start_comfyui] env_type: {env.get("envType", "portable")}')
            logger.debug(f'[start_comfyui] desktop_data_path: {env.get("desktopDataPath", "")}')
            logger.debug(f'[start_comfyui] advanced_env_vars 长度: {len(advanced_env_vars)}')
            
            # 从设置中读取是否显示控制台窗口
            show_console_window = False
            try:
                settings_result = self._settings_manager.get_settings()
                if settings_result.get('success') and settings_result.get('settings'):
                    show_console_window = settings_result['settings'].get('general', {}).get('showConsoleWindow', False)
                    logger.debug(f'[start_comfyui] show_console_window: {show_console_window}')
            except Exception as e:
                logger.warning(f'读取控制台窗口设置失败: {e}')
            
            # 启动进程
            logger.debug(f'[start_comfyui] 调用 process.start()...')
            self._comfyui_process.env_id = env_id
            self._comfyui_process.start(python_path, comfyui_path, args, env_config, show_console_window)
            logger.debug(f'[start_comfyui] process.start() 调用成功')
            
            return {
                "success": True,
                "message": "ComfyUI 启动成功"
            }
            
        except Exception as e:
            import traceback
            logger.debug(f'[start_comfyui] 异常: {type(e).__name__}: {e}')
            logger.debug(f'[start_comfyui] 堆栈: {traceback.format_exc()}')
            return {
                "success": False,
                "error": str(e)
            }
    
    def stop_comfyui(self):
        """
        停止 ComfyUI
        
        支持停止由 ComfyNexus 启动的进程，以及外部启动的 ComfyUI 进程
        
        Returns:
            dict: 操作结果
        """
        try:
            # 初始化进程管理器
            self.__init_process_manager()
            
            # 首先检查是否是由 ComfyNexus 启动的进程（进程正在运行）
            if self._comfyui_process.is_running and self._comfyui_process.process:
                # 停止由 ComfyNexus 启动的进程
                self._comfyui_process.stop()
                return {
                    "success": True,
                    "message": "ComfyUI 已停止"
                }
            
            # 如果 ComfyNexus 没有启动进程，检查是否有外部进程
            status = self._comfyui_process.get_status()
            port_available = status.get("port_available", False)
            
            # 如果端口可用，说明有外部进程在运行
            if port_available:
                external_pid = status.get("pid")
                if external_pid:
                    import psutil
                    try:
                        proc = psutil.Process(external_pid)
                        proc.terminate()
                        # 等待进程结束
                        try:
                            proc.wait(timeout=5)
                        except psutil.TimeoutExpired:
                            proc.kill()
                            proc.wait()
                        return {
                            "success": True,
                            "message": f"外部 ComfyUI 进程 (PID: {external_pid}) 已停止"
                        }
                    except psutil.NoSuchProcess:
                        return {
                            "success": False,
                            "error_message": "进程不存在"
                        }
                    except psutil.AccessDenied:
                        return {
                            "success": False,
                            "error_message": "权限不足，无法停止进程"
                        }
            
            # 没有运行中的进程
            return {
                "success": False,
                "error_message": "ComfyUI 未运行"
            }
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"停止 ComfyUI 失败: {e}", exc_info=True)
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def get_comfyui_status(self):
        """
        获取 ComfyUI 运行状态
        
        Returns:
            dict: 运行状态
        """
        try:
            # 初始化进程管理器
            self.__init_process_manager()
            
            status = self._comfyui_process.get_status()
            
            # 构建 URL
            port = status.get("port", 8188)
            url = f"http://127.0.0.1:{port}" if status.get("is_running", False) else None
            
            # 转换为前端期望的格式（驼峰命名）
            return {
                "success": True,
                "data": {
                    "isRunning": status.get("is_running", False),
                    "isExternal": status.get("is_external", False),
                    "pid": status.get("pid"),
                    "envId": status.get("env_id"),
                    "port": port,
                    "portAvailable": status.get("port_available", False),
                    "uptime": status.get("uptime", 0),
                    "url": url,
                    "wasStarted": status.get("was_started", False),
                    "exitCode": status.get("exit_code"),
                    "processAlive": status.get("process_alive", False)
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "data": {
                    "isRunning": False,
                    "pid": None,
                    "envId": None,
                    "port": 8188,
                    "portAvailable": False,
                    "uptime": 0,
                    "url": None
                },
                "error_message": str(e)
            }
    
    def _build_launch_args(self, acceleration_config):
        """
        根据加速配置构建启动参数
        
        Args:
            acceleration_config: 加速配置字典
            
        Returns:
            list: 启动参数列表
        """
        from ..core.env.launch_args_builder import LaunchArgsBuilder
        builder = LaunchArgsBuilder()
        return builder.build_args_from_dict(acceleration_config)
    
    # ========== 系统监控 API ==========
    
    def get_system_monitor_data(self):
        """
        获取系统监控数据
        
        Returns:
            dict: 包含所有监控指标的字典
        """
        return self._system_monitor_controller.get_system_monitor_data()
    
    def get_monitor_data(self):
        """
        获取监控中心数据（新格式）
        
        Returns:
            dict: 包含 CPU、GPU、系统存储、网络、磁盘的监控数据
        """
        return self._system_monitor_controller.get_monitor_data()
    
    def toggle_floating_window(self, visible: bool):
        """
        切换悬浮窗显示状态
        
        Args:
            visible: 是否显示悬浮窗
            
        Returns:
            dict: 操作结果
        """
        return self._system_monitor_controller.toggle_floating_window(visible)
    
    def close_floating_window(self):
        """
        关闭悬浮窗
        
        Returns:
            dict: 操作结果
        """
        from backend.src.ui import floating_window_manager
        success = floating_window_manager.hide()
        return {"success": success}
    
    def resize_floating_window(self, width: int, height: int) -> dict:
        """
        调整悬浮窗尺寸
        
        Args:
            width: 宽度（像素）
            height: 高度（像素）
            
        Returns:
            dict: 操作结果
        """
        from backend.src.ui import floating_window_manager
        success = floating_window_manager.resize_window(width, height)
        return {"success": success}
    
    def floating_window_ready(self, width: int = None, height: int = None) -> dict:
        """
        悬浮窗前端渲染完成回调
        
        由悬浮窗前端在 React 渲染完成后调用，
        触发后端执行 finalize_setup() 完成窗口归位和显示。
        
        Args:
            width: 窗口宽度（可选）
            height: 窗口高度（可选）
        
        Returns:
            dict: 操作结果
        """
        from backend.src.ui import floating_window_manager
        import threading
        
        def _finalize():
            floating_window_manager.configure_and_show()
            floating_window_manager.finalize_setup(width, height)
        
        threading.Thread(target=_finalize, daemon=True).start()
        return {"success": True}
    
    def get_floating_window_position(self):
        """
        获取悬浮窗位置
        
        Returns:
            dict: 包含位置的响应
        """
        return self._settings_manager.get_floating_window_position()
    
    def save_floating_window_position(self, x: int, y: int):
        """
        保存悬浮窗位置
        
        Args:
            x: X 坐标
            y: Y 坐标
            
        Returns:
            dict: 操作结果
        """
        return self._settings_manager.save_floating_window_position(x, y)
    
    def get_floating_window_visible(self):
        """
        获取悬浮窗可见状态
        
        Returns:
            dict: 包含可见状态的响应
        """
        return self._system_monitor_controller.get_floating_window_visible()
    
    def get_floating_window_settings(self):
        """
        获取悬浮窗设置
        
        Returns:
            dict: 包含设置的响应
        """
        return self._system_monitor_controller.get_floating_window_settings()
    
    def update_floating_window_settings(self, settings: dict):
        """
        更新悬浮窗设置
        
        Args:
            settings: 悬浮窗设置（opacity, visibleItems, itemOrder）
            
        Returns:
            dict: 操作结果
        """
        return self._system_monitor_controller.update_floating_window_settings(settings)
    
    def get_hardware_info(self):
        """
        获取硬件信息
        
        Returns:
            dict: 包含 CPU 和 GPU 信息的响应
        """
        return self._system_monitor_controller.get_hardware_info()
    
    def get_network_interface_name(self):
        """
        获取活动网络接口名称
        
        Returns:
            dict: 包含网络接口名称的响应
        """
        return self._system_monitor_controller.get_network_interface_name()
    
    def get_hardware_monitor_status(self):
        """
        获取硬件监控状态
        
        Returns:
            dict: 包含硬件监控状态的响应
        """
        return self._system_monitor_controller.get_hardware_monitor_status()
    
    # ========== 文件夹快捷方式 API ==========
    
    def get_folder_shortcuts(self):
        """
        获取文件夹快捷方式配置
        
        Returns:
            dict: 包含快捷方式列表的响应
        """
        return self._folder_shortcut_controller.get_folder_shortcuts()
    
    def save_folder_shortcuts(self, shortcuts):
        """
        保存文件夹快捷方式配置
        
        Args:
            shortcuts: 快捷方式列表
            
        Returns:
            dict: 操作结果
        """
        return self._folder_shortcut_controller.save_folder_shortcuts(shortcuts)
    
    def open_folder(self, path):
        """
        在文件管理器中打开文件夹
        
        Args:
            path: 文件夹路径
            
        Returns:
            dict: 操作结果
        """
        return self._folder_shortcut_controller.open_folder(path)
    
    def validate_folder_path(self, path):
        """
        验证文件夹路径是否有效
        
        Args:
            path: 文件夹路径
            
        Returns:
            dict: 验证结果
        """
        return self._folder_shortcut_controller.validate_folder_path(path)
    
    def browse_folder_for_shortcut(self):
        """
        打开系统文件夹选择器（用于文件夹快捷方式）
        
        Returns:
            dict: 选择结果
        """
        return self._folder_shortcut_controller.browse_folder(self._window)

    # ========== 版本管理 API ==========
    
    def get_versions(self, version_type='stable', page=1, page_size=20, branch=None, force_refresh=False):
        """
        获取版本列表（支持增量获取）
        
        Args:
            version_type: 版本类型 ('stable' 或 'dev')
            page: 页码
            page_size: 每页数量
            branch: 指定分支名称（可选）
            force_refresh: 是否强制全量刷新
            
        Returns:
            dict: 版本列表响应
        """
        return self._version_controller.get_versions(version_type, page, page_size, branch, force_refresh)
    
    def get_current_version(self):
        """
        获取当前版本信息
        
        Returns:
            dict: 当前版本信息
        """
        return self._version_controller.get_current_version()
    
    def get_remote_info(self):
        """
        获取远端信息
        
        Returns:
            dict: 远端信息
        """
        return self._version_controller.get_remote_info()
    
    def switch_version(self, version_id, version_type, force=False):
        """
        切换版本
        
        Args:
            version_id: 版本 ID (commit hash)
            version_type: 版本类型 ('stable' 或 'dev')
            force: 是否强制切换（忽略本地修改）
            
        Returns:
            dict: 切换结果
        """
        return self._version_controller.switch_version(version_id, version_type, force)
    
    def rollback_version(self, commit_hash):
        """
        回退到指定版本
        
        Args:
            commit_hash: 目标 commit hash
            
        Returns:
            dict: 回退结果
        """
        return self._version_controller.rollback_version(commit_hash)
    
    def update_dependencies(self):
        """
        更新依赖
        
        Returns:
            dict: 更新结果
        """
        return self._version_controller.update_dependencies()
    
    def restart_process(self):
        """
        重启进程
        
        Returns:
            dict: 重启结果
        """
        return self._version_controller.restart_process()
    
    def check_process_status(self):
        """
        检查进程状态
        
        Returns:
            dict: 进程状态
        """
        return self._version_controller.check_process_status()
    
    def update_remote_url(self, url):
        """
        更新远端地址
        
        Args:
            url: 远端仓库地址
            
        Returns:
            dict: 更新结果
        """
        return self._version_controller.update_remote_url(url)
    
    def fix_git_ownership(self):
        """
        修复 Git 所有权问题
        
        Returns:
            dict: 修复结果
        """
        return self._version_controller.fix_git_ownership()
    
    def get_branches(self):
        """
        获取分支列表
        
        Returns:
            dict: 分支列表响应
        """
        return self._version_controller.get_branches()
    
    def switch_branch(self, branch_name):
        """
        切换分支
        
        Args:
            branch_name: 分支名称
            
        Returns:
            dict: 切换结果
        """
        return self._version_controller.switch_branch(branch_name)
    
    def get_system_proxy(self):
        """
        获取系统代理配置
        
        Returns:
            dict: {
                "success": bool,
                "message": str (可选),
                "enabled": bool,
                "host": str,
                "port": str
            }
        """
        return self._system_proxy_manager.get_system_proxy()
    
    def get_settings(self):
        """
        获取系统设置
        
        Returns:
            dict: {
                "success": bool,
                "settings": dict
            }
        """
        return self._settings_manager.get_settings()
    
    def update_settings(self, updates):
        """
        更新系统设置
        
        Args:
            updates: 要更新的设置
            
        Returns:
            dict: {
                "success": bool,
                "message": str,
                "settings": dict (可选)
            }
        """
        result = self._settings_manager.update_settings(updates)
        
        # 如果更新成功，处理需要立即生效的设置
        if result.get('success'):
            # 如果更新了日志级别，立即生效
            if 'logging' in updates and 'level' in updates.get('logging', {}):
                new_level = updates['logging']['level']
                self._apply_log_level(new_level)
            
            # 如果更新了窗口大小，重置最大化状态
            if 'appearance' in updates:
                if 'windowSize' in updates['appearance']:
                    logger.debug("[API] 检测到窗口大小更新，重置最大化状态")
                    # 清除保存的窗口状态
                    self._window_state = None
                    # 如果当前是最大化状态，标记为非最大化
                    # （下次拖动还原时会使用新的配置大小）
                    if self._is_maximized:
                        self._is_maximized = False
        
        return result
    
    def _apply_log_level(self, level: str):
        """
        应用日志级别更改（立即生效，无需重启）
        
        Args:
            level: 日志级别 (DEBUG/INFO/DEV/WARNING/ERROR)
        """
        try:
            import logging
            from backend.src.utils.logger import DEV_LEVEL
            
            # 获取日志记录器
            logger_instance = logging.getLogger("ComfyNexus")
            
            # 将级别字符串转换为日志级别值
            level_value = {
                "DEBUG": logging.DEBUG,      # 10
                "INFO": logging.INFO,        # 20
                "DEV": DEV_LEVEL,            # 25
                "WARNING": logging.WARNING,  # 30
                "ERROR": logging.ERROR       # 40
            }.get(level.upper(), logging.INFO)
            
            # 更新日志记录器级别
            logger_instance.setLevel(level_value)
            
            # 更新所有处理器的级别
            for handler in logger_instance.handlers:
                handler.setLevel(level_value)
            
            logger.info(f"[API] 日志级别已更改为: {level}（立即生效，无需重启）")
            
        except Exception as e:
            logger.error(f"[API] 更改日志级别失败: {str(e)}")
    
    def reset_settings(self):
        """
        重置系统设置为默认值
        
        Returns:
            dict: {
                "success": bool,
                "message": str
            }
        """
        return self._settings_manager.reset_settings()
    
    # ========== GitHub 镜像加速 API ==========
    
    def get_github_mirror_settings(self):
        """
        获取 GitHub 镜像设置和状态
        
        Returns:
            dict: {
                "success": bool,
                "settings": dict (包含 statusText, currentPreset, isTesting, testResults)
            }
        """
        try:
            from backend.src.utils.github_mirror import github_mirror_manager
            return {
                "success": True,
                "settings": github_mirror_manager.get_settings()
            }
        except Exception as e:
            logger.error(f"[API] 获取 GitHub 镜像设置失败: {e}")
            return {"success": False, "message": str(e), "settings": {}}
    
    def update_github_mirror_settings(self, updates):
        """
        更新 GitHub 镜像设置
        
        Args:
            updates: 要更新的设置项
            
        Returns:
            dict: {"success": bool, "message": str}
        """
        try:
            from backend.src.utils.github_mirror import github_mirror_manager
            github_mirror_manager.update_settings(updates)
            return {"success": True, "message": "镜像设置已更新"}
        except Exception as e:
            logger.error(f"[API] 更新 GitHub 镜像设置失败: {e}")
            return {"success": False, "message": str(e)}
    
    def start_github_mirror_speed_test(self):
        """
        开始 GitHub 镜像测速
        
        Returns:
            dict: {"success": bool, "message": str}
        """
        try:
            from backend.src.utils.github_mirror import github_mirror_manager
            return github_mirror_manager.start_speed_test()
        except Exception as e:
            logger.error(f"[API] 开始镜像测速失败: {e}")
            return {"success": False, "message": str(e)}
    
    def get_github_mirror_speed_test_status(self):
        """
        获取镜像测速进度和结果
        
        Returns:
            dict: {
                "success": bool,
                "isRunning": bool,
                "progress": list,
                "results": dict
            }
        """
        try:
            from backend.src.utils.github_mirror import github_mirror_manager
            status = github_mirror_manager.get_speed_test_status()
            return {"success": True, **status}
        except Exception as e:
            logger.error(f"[API] 获取测速状态失败: {e}")
            return {"success": False, "message": str(e)}
    
    def get_github_mirror_presets(self):
        """
        获取所有镜像预设方案
        
        Returns:
            dict: {"success": bool, "presets": dict}
        """
        try:
            from backend.src.utils.github_mirror import MIRROR_PRESETS
            presets = {}
            for key, value in MIRROR_PRESETS.items():
                presets[key] = {
                    "name": value["name"],
                    "description": value["description"],
                    "github": value.get("github"),
                    "raw": value.get("raw"),
                    "release": value.get("release"),
                }
            return {"success": True, "presets": presets}
        except Exception as e:
            logger.error(f"[API] 获取镜像预设失败: {e}")
            return {"success": False, "message": str(e), "presets": {}}

    # ========== PyPI 镜像源 API ==========

    def get_pypi_mirror_settings(self):
        """
        获取 PyPI 镜像设置和状态

        Returns:
            dict: {
                "success": bool,
                "settings": dict (包含 statusText, currentSource, isTesting, testResults)
            }
        """
        try:
            from backend.src.utils.pypi_mirror import pypi_mirror_manager
            return {
                "success": True,
                "settings": pypi_mirror_manager.get_settings()
            }
        except Exception as e:
            logger.error(f"[API] 获取 PyPI 镜像设置失败: {e}")
            return {"success": False, "message": str(e), "settings": {}}

    def update_pypi_mirror_settings(self, updates):
        """
        更新 PyPI 镜像设置

        Args:
            updates: 要更新的设置项

        Returns:
            dict: {"success": bool, "message": str}
        """
        try:
            from backend.src.utils.pypi_mirror import pypi_mirror_manager
            pypi_mirror_manager.update_settings(updates)
            return {"success": True, "message": "PyPI 镜像设置已更新"}
        except Exception as e:
            logger.error(f"[API] 更新 PyPI 镜像设置失败: {e}")
            return {"success": False, "message": str(e)}

    def start_pypi_mirror_speed_test(self):
        """
        开始 PyPI 镜像测速

        Returns:
            dict: {"success": bool, "message": str}
        """
        try:
            from backend.src.utils.pypi_mirror import pypi_mirror_manager
            return pypi_mirror_manager.start_speed_test()
        except Exception as e:
            logger.error(f"[API] 开始 PyPI 镜像测速失败: {e}")
            return {"success": False, "message": str(e)}

    def get_pypi_mirror_speed_test_status(self):
        """
        获取 PyPI 镜像测速进度和结果

        Returns:
            dict: {
                "success": bool,
                "isRunning": bool,
                "progress": list,
                "results": dict
            }
        """
        try:
            from backend.src.utils.pypi_mirror import pypi_mirror_manager
            status = pypi_mirror_manager.get_speed_test_status()
            return {"success": True, **status}
        except Exception as e:
            logger.error(f"[API] 获取 PyPI 测速状态失败: {e}")
            return {"success": False, "message": str(e)}

    def _get_requests_proxies(self) -> Optional[Dict]:
        try:
            result = self._settings_manager.get_settings()
            if not result.get("success"):
                return None
            settings = result.get("settings", {})
            proxy = settings.get("proxy", {})
            if not proxy.get("enabled"):
                return None
            host = proxy.get("host", "").strip()
            port = proxy.get("port", "").strip()
            if not host or not port:
                return None
            proxy_url = f"http://{host}:{port}"
            logger.dev(f"[API] 使用代理: {proxy_url}")
            return {"http": proxy_url, "https": proxy_url}
        except Exception as e:
            logger.dev(f"[API] 获取代理配置失败: {e}")
            return None

    def get_github_releases(self, owner: str = "Allen-xxa", repo: str = "ComfyNexus", per_page: int = 3):
        """
        获取 GitHub 仓库的 Releases 列表（通过镜像代理）
        
        Args:
            owner: 仓库所有者
            repo: 仓库名称
            per_page: 每页数量
            
        Returns:
            dict: {
                "success": bool,
                "releases": [
                    {
                        "id": int,
                        "tag_name": str,
                        "name": str,
                        "body": str,
                        "published_at": str,
                        "html_url": str,
                        "prerelease": bool
                    }
                ]
            }
        """
        cache_key = f"releases:{owner}/{repo}/{per_page}"
        cached = _commit_time_cache.get(cache_key)
        if cached and time.time() - cached["ts"] < _COMMIT_TIME_CACHE_TTL:
            return cached["result"]
        
        try:
            import requests
            
            url = f"https://api.github.com/repos/{owner}/{repo}/releases"
            headers = {
                "User-Agent": "ComfyNexus/1.0",
                "Accept": "application/vnd.github.v3+json"
            }
            
            if self._settings_manager:
                token = self._settings_manager.get_github_api_token()
                if token:
                    headers["Authorization"] = f"token {token}"
            
            verify_ssl = True
            try:
                from backend.src.utils.github_mirror import github_mirror_manager
                if github_mirror_manager.is_enabled():
                    mirror_url, mirror_headers = github_mirror_manager.transform_url(url, "api")
                    url = mirror_url
                    headers.update(mirror_headers)
                    settings = github_mirror_manager._load_settings()
                    verify_ssl = settings.get("verifySSL", True)
                    logger.dev(f"[API] 使用 API 镜像源获取 Releases, verify_ssl={verify_ssl}")
            except Exception as e:
                logger.dev(f"[API] 获取镜像设置失败: {e}")
            
            proxies = self._get_requests_proxies()
            
            response = requests.get(
                url,
                headers=headers,
                params={"per_page": per_page},
                timeout=15,
                verify=verify_ssl,
                proxies=proxies
            )
            response.raise_for_status()
            
            releases = response.json()
            releases = [r for r in releases if not r.get("draft", False)]
            
            result = {
                "success": True,
                "releases": releases
            }
            _commit_time_cache[cache_key] = {"result": result, "ts": time.time()}
            return result
        except Exception as e:
            logger.error(f"[API] 获取 GitHub Releases 失败: {e}")
            return {"success": False, "message": str(e), "releases": []}
    
    def _get_commit_time_from_local_repo(self, owner: str, repo: str, branch: str = "main") -> Optional[dict]:
        """
        从本地 custom_nodes 目录读取仓库最后提交时间（不走网络）
        
        Returns:
            dict or None: 成功返回 {"success": True, "commit_date": ..., "commit_sha": ...}，失败返回 None
        """
        try:
            current_env = self._environment_controller.manager.get_current_environment()
            if not current_env:
                return None
            
            comfyui_path = Path(current_env.config.general.comfyui_path)
            plugin_dir = comfyui_path / "custom_nodes" / repo
            
            if not plugin_dir.exists() or not (plugin_dir / ".git").exists():
                return None
            
            git_path = None
            try:
                from backend.src.utils.git_config import get_git_executable
                git_path = get_git_executable()
            except Exception:
                pass
            
            import subprocess, os, platform
            
            cmd_args = [git_path or "git", "-c", "safe.directory=*",
                        "log", "-1", f"--format=%aI|%h", f"origin/{branch}"]
            
            creation_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            
            result = subprocess.run(
                cmd_args,
                cwd=str(plugin_dir),
                capture_output=True, text=True, timeout=10,
                encoding="utf-8", errors="replace",
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
                creationflags=creation_flags,
            )
            
            if result.returncode != 0 or not result.stdout.strip():
                logger.dev(f"[API] 本地 git log 失败: {result.stderr.strip()[:100]}")
                return None
            
            parts = result.stdout.strip().split("|", 1)
            commit_date = parts[0]
            commit_sha = parts[1] if len(parts) > 1 else ""
            
            return {
                "success": True,
                "commit_date": commit_date,
                "commit_sha": commit_sha,
            }
        except Exception as e:
            logger.dev(f"[API] 本地读取提交时间异常: {e}")
            return None

    def _get_commit_time_from_api(self, owner: str, repo: str, branch: str = "main") -> dict:
        """通过 GitHub API 获取最后提交时间"""
        import requests
        
        url = f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}"
        headers = {
            "User-Agent": "ComfyNexus/1.0",
            "Accept": "application/vnd.github.v3+json"
        }
        
        if self._settings_manager:
            token = self._settings_manager.get_github_api_token()
            if token:
                headers["Authorization"] = f"token {token}"
        
        verify_ssl = True
        try:
            from backend.src.utils.github_mirror import github_mirror_manager
            if github_mirror_manager.is_enabled():
                mirror_url, mirror_headers = github_mirror_manager.transform_url(url, "api")
                url = mirror_url
                headers.update(mirror_headers)
                settings = github_mirror_manager._load_settings()
                verify_ssl = settings.get("verifySSL", True)
                logger.dev(f"[API] 使用 API 镜像源获取最后提交时间, verify_ssl={verify_ssl}")
        except Exception as e:
            logger.dev(f"[API] 获取镜像设置失败: {e}")
        
        proxies = self._get_requests_proxies()
        
        response = requests.get(
            url,
            headers=headers,
            timeout=15,
            verify=verify_ssl,
            proxies=proxies
        )
        response.raise_for_status()
        
        data = response.json()
        commit_date = data.get("commit", {}).get("committer", {}).get("date", "")
        commit_sha = data.get("sha", "")[:7] if data.get("sha") else ""
        
        return {
            "success": True,
            "commit_date": commit_date,
            "commit_sha": commit_sha
        }

    def get_last_commit_time(self, owner: str, repo: str, branch: str = "main"):
        """
        获取 GitHub 仓库最后一次提交时间
        
        优先从本地 custom_nodes 读取 git log（零网络开销），
        失败则通过 GitHub API 获取并缓存 1 小时。
        
        Args:
            owner: 仓库所有者
            repo: 仓库名称
            branch: 分支名称
            
        Returns:
            dict: {
                "success": bool,
                "commit_date": str (ISO 格式),
                "commit_sha": str,
                "message": str
            }
        """
        cache_key = f"{owner}/{repo}/{branch}"
        
        cached = _commit_time_cache.get(cache_key)
        if cached and time.time() - cached["ts"] < _COMMIT_TIME_CACHE_TTL:
            return cached["result"]
        
        local_result = self._get_commit_time_from_local_repo(owner, repo, branch)
        if local_result and local_result.get("success"):
            _commit_time_cache[cache_key] = {"result": local_result, "ts": time.time()}
            return local_result
        
        try:
            result = self._get_commit_time_from_api(owner, repo, branch)
            if result.get("success"):
                _commit_time_cache[cache_key] = {"result": result, "ts": time.time()}
            return result
        except Exception as e:
            logger.error(f"[API] 获取最后提交时间失败: {e}")
            return {"success": False, "message": str(e)}
    
    # ========== 缓存管理 API ==========
    
    def get_cache_stats(self):
        """
        获取所有缓存的统计信息
        
        Returns:
            dict: {
                "success": bool,
                "data": {
                    "caches": [
                        {
                            "type": str,
                            "name": str,
                            "description": str,
                            "size_bytes": int,
                            "size_formatted": str,
                            "file_count": int,
                            "last_updated": str (ISO格式)
                        }
                    ],
                    "total_size_bytes": int,
                    "total_size_formatted": str,
                    "total_file_count": int
                }
            }
        """
        try:
            stats = self._cache_service.get_all_cache_stats()
            return {
                "success": True,
                "data": stats
            }
        except Exception as e:
            logger.error(f"[API] 获取缓存统计失败: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_cache_types(self):
        """
        获取所有缓存类型信息
        
        Returns:
            dict: {
                "success": bool,
                "data": [
                    {
                        "type": str,
                        "name": str,
                        "description": str
                    }
                ]
            }
        """
        try:
            types = self._cache_service.get_cache_types()
            return {
                "success": True,
                "data": types
            }
        except Exception as e:
            logger.error(f"[API] 获取缓存类型失败: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def clear_cache(self, cache_type: str):
        """
        清理指定类型的缓存
        
        Args:
            cache_type: 缓存类型 (version/translation/plugin/update/marketplace)
            
        Returns:
            dict: {
                "success": bool,
                "data": {
                    "type": str,
                    "name": str,
                    "cleared_size": int,
                    "cleared_files": int
                },
                "error": str (可选)
            }
        """
        try:
            from backend.src.core.cache import CacheType
            
            cache_type_enum = CacheType(cache_type)
            result = self._cache_service.clear_cache(cache_type_enum)
            
            return {
                "success": result.get("success", False),
                "data": result,
                "error": result.get("error")
            }
        except ValueError:
            return {
                "success": False,
                "error": f"无效的缓存类型: {cache_type}"
            }
        except Exception as e:
            logger.error(f"[API] 清理缓存失败: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def clear_all_caches(self):
        """
        清理所有缓存
        
        Returns:
            dict: {
                "success": bool,
                "data": {
                    "results": [...],
                    "total_cleared_size": int,
                    "total_cleared_size_formatted": str,
                    "total_cleared_files": int
                }
            }
        """
        try:
            result = self._cache_service.clear_all_caches()
            return {
                "success": result.get("success", False),
                "data": result
            }
        except Exception as e:
            logger.error(f"[API] 清理所有缓存失败: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # ========== 进程冲突检测 API ==========
    
    def check_comfyui_processes(self):
        """
        检查系统中的 ComfyUI 进程
        
        扫描系统中不受当前应用管理的 ComfyUI 进程，并检测端口冲突。
        
        Returns:
            dict: {
                "success": bool,
                "data": {
                    "processes": List[Dict],  # 不受管理的进程列表
                    "has_conflict": bool,      # 是否存在端口冲突
                    "target_port": int         # 目标端口
                },
                "error": str  # 错误信息（如果失败）
            }
        """
        try:
            from backend.src.core.process.process_detector import ProcessDetector
            import logging
            logger = logging.getLogger(__name__)
            
            # 获取当前管理的进程 PID（如果存在）
            managed_pid = None
            if hasattr(self, '_comfyui_process') and self._comfyui_process:
                if self._comfyui_process.process:
                    managed_pid = self._comfyui_process.process.pid
            
            logger.info(f"[check_comfyui_processes] 开始检测，管理的 PID: {managed_pid}")
            
            # 初始化进程检测器
            detector = ProcessDetector(managed_pid=managed_pid)
            
            # 扫描系统中的 ComfyUI 进程
            processes = detector.scan_comfyui_processes()
            
            logger.info(f"[check_comfyui_processes] 检测到 {len(processes)} 个不受管理的进程")
            for proc in processes:
                logger.info(f"  - PID: {proc['pid']}, 端口: {proc['port']}, 路径: {proc['cwd']}")
            
            # 获取目标端口（从当前环境配置）
            target_port = 8188  # 默认端口
            
            try:
                # 尝试从当前环境配置中获取端口
                current_env = self._environment_controller.manager.get_current_environment()
                if current_env:
                    # current_env 是 Environment 对象
                    config = current_env.config  # EnvironmentConfig 对象
                    if config and hasattr(config, 'acceleration'):
                        acceleration = config.acceleration  # AccelerationSettings 对象
                        if hasattr(acceleration, 'port') and acceleration.port:
                            target_port = acceleration.port
            except Exception as e:
                # 获取端口配置失败，使用默认端口
                logger.warning(f"获取目标端口配置失败，使用默认端口 {target_port}: {e}")
            
            # 检测端口冲突
            has_conflict = detector.check_port_conflict(processes, target_port)
            
            logger.info(f"[check_comfyui_processes] 目标端口: {target_port}, 端口冲突: {has_conflict}")
            
            return {
                "success": True,
                "data": {
                    "processes": processes,
                    "has_conflict": has_conflict,
                    "target_port": target_port
                },
                "error": None
            }
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"检查 ComfyUI 进程时发生异常: {e}", exc_info=True)
            
            return {
                "success": False,
                "data": {
                    "processes": [],
                    "has_conflict": False,
                    "target_port": 8188
                },
                "error": str(e)
            }
    
    def kill_process(self, pid: int) -> Dict:
        """
        终止指定进程
        
        调用 ProcessDetector.kill_process 终止指定 PID 的进程。
        
        Args:
            pid: 进程 ID
            
        Returns:
            dict: {
                "success": bool,
                "message": str,
                "error": str  # 错误信息（如果失败）
            }
        """
        try:
            from backend.src.core.process.process_detector import ProcessDetector
            
            # 调用 ProcessDetector 的静态方法终止进程
            result = ProcessDetector.kill_process(pid)
            
            return result
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"终止进程 {pid} 时发生异常: {e}", exc_info=True)
            
            return {
                "success": False,
                "message": f"终止进程 {pid} 时发生异常",
                "error": str(e)
            }

    # ========== 极客模式 API ==========
    
    def get_geek_presets(self):
        """
        获取所有极客模式预设
        
        Returns:
            dict: 包含预设列表的字典
        """
        try:
            from ..core.env.geek_mode_manager import GeekModeManager
            manager = GeekModeManager()
            presets = manager.get_all_presets()
            
            return {
                "success": True,
                "data": presets
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_geek_preset(self, preset_id: str):
        """
        获取指定极客模式预设
        
        Args:
            preset_id: 预设ID
            
        Returns:
            dict: 包含预设数据的字典
        """
        try:
            from ..core.env.geek_mode_manager import GeekModeManager
            manager = GeekModeManager()
            preset = manager.get_preset(preset_id)
            
            if preset:
                return {
                    "success": True,
                    "data": preset
                }
            else:
                return {
                    "success": False,
                    "error": "预设不存在"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def create_geek_preset(self, name: str, description: str, args: str, preset_id: str = None):
        """
        创建极客模式预设
        
        Args:
            name: 预设名称
            description: 预设描述
            args: 启动参数（多行文本）
            preset_id: 预设ID（可选，如果不提供则自动生成）
            
        Returns:
            dict: 包含创建的预设数据的字典
        """
        try:
            from ..core.env.geek_mode_manager import GeekModeManager
            manager = GeekModeManager()
            preset = manager.create_preset(name, description, args, preset_id)
            
            return {
                "success": True,
                "data": preset
            }
        except ValueError as e:
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"创建预设失败: {str(e)}"
            }
    
    def update_geek_preset(self, preset_id: str, name: str = None, description: str = None, args: str = None):
        """
        更新极客模式预设
        
        Args:
            preset_id: 预设ID
            name: 预设名称（可选）
            description: 预设描述（可选）
            args: 启动参数（可选）
            
        Returns:
            dict: 包含更新后的预设数据的字典
        """
        try:
            from ..core.env.geek_mode_manager import GeekModeManager
            manager = GeekModeManager()
            preset = manager.update_preset(preset_id, name, description, args)
            
            return {
                "success": True,
                "data": preset
            }
        except FileNotFoundError as e:
            return {
                "success": False,
                "error": str(e)
            }
        except ValueError as e:
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"更新预设失败: {str(e)}"
            }
    
    def delete_geek_preset(self, preset_id: str):
        """
        删除极客模式预设
        
        Args:
            preset_id: 预设ID
            
        Returns:
            dict: 操作结果
        """
        try:
            from ..core.env.geek_mode_manager import GeekModeManager
            manager = GeekModeManager()
            manager.delete_preset(preset_id)
            
            return {
                "success": True,
                "message": "预设删除成功"
            }
        except FileNotFoundError as e:
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"删除预设失败: {str(e)}"
            }
    
    def validate_geek_args(self, args: str):
        """
        验证极客模式参数
        
        Args:
            args: 启动参数（多行文本）
            
        Returns:
            dict: 验证结果
        """
        try:
            from ..core.env.geek_mode_manager import GeekModeManager
            manager = GeekModeManager()
            is_valid, errors = manager.validate_args(args)
            
            return {
                "success": True,
                "data": {
                    "isValid": is_valid,
                    "errors": errors
                }
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    # ==================== 翻译 API ====================
    
    def translate_text(self, text: str, provider: str = None, llm_config_id: str = None, target_lang: str = None):
        """
        翻译文本
        
        Args:
            text: 要翻译的文本
            provider: 翻译提供商（"google" 或 "llm"），默认使用设置中的值
            llm_config_id: LLM配置ID（provider为"llm"时使用）
            target_lang: 目标语言，默认使用设置中的值
            
        Returns:
            dict: {
                "success": bool,
                "translated_text": str,
                "provider": str,
                "cached": bool,
                "error_message": str (可选)
            }
        """
        try:
            from ..core.translation import TranslationManager
            
            manager = TranslationManager(self._settings_manager)
            result = manager.translate(
                text=text,
                provider=provider,
                llm_config_id=llm_config_id,
                target_lang=target_lang,
            )
            
            return result.to_dict()
            
        except Exception as e:
            logger.error(f"[API] 翻译失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def get_translation_settings(self):
        """
        获取翻译设置
        
        Returns:
            dict: {
                "success": bool,
                "settings": {
                    "provider": str,
                    "llmConfigId": str,
                    "sourceLanguage": str,
                    "targetLanguage": str
                }
            }
        """
        return self._settings_manager.get_translation_settings()
    
    def update_translation_settings(self, settings: dict):
        """
        更新翻译设置
        
        Args:
            settings: 翻译设置
            
        Returns:
            dict: {
                "success": bool,
                "message": str,
                "settings": dict
            }
        """
        return self._settings_manager.update_translation_settings(settings)
    
    def translate_batch(self, items: list, provider: str = None, llm_config_id: str = None, target_lang: str = None):
        """
        批量翻译多条文本
        
        Args:
            items: 要翻译的条目列表，格式为 [{"id": "xxx", "text": "xxx"}, ...]
            provider: 翻译提供商（"google" 或 "llm"），默认使用设置中的值
            llm_config_id: LLM配置ID（provider为"llm"时使用）
            target_lang: 目标语言，默认使用设置中的值
            
        Returns:
            dict: {
                "success": bool,
                "results": [{"id": str, "translated": str, "success": bool}, ...],
                "provider": str,
                "target_lang": str
            }
        """
        try:
            from ..core.translation import TranslationManager
            
            manager = TranslationManager(self._settings_manager)
            return manager.translate_batch(
                items=items,
                provider=provider,
                llm_config_id=llm_config_id,
                target_lang=target_lang,
            )
            
        except Exception as e:
            logger.error(f"[API] 批量翻译失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": [],
            }
    
    def clear_translation_cache(self):
        """
        清除翻译缓存
        
        Returns:
            dict: {
                "success": bool,
                "message": str,
                "deleted_count": int
            }
        """
        try:
            from ..core.translation import TranslationManager
            
            manager = TranslationManager(self._settings_manager)
            return manager.clear_cache()
            
        except Exception as e:
            logger.error(f"[API] 清除翻译缓存失败: {e}")
            return {
                "success": False,
                "message": str(e)
            }
    
    def get_translation_cache_stats(self):
        """
        获取翻译缓存统计信息
        
        Returns:
            dict: 缓存统计信息
        """
        try:
            from ..core.translation import TranslationManager
            
            manager = TranslationManager(self._settings_manager)
            return manager.get_cache_stats()
            
        except Exception as e:
            logger.error(f"[API] 获取缓存统计失败: {e}")
            return {
                "error": str(e)
            }
    
    def get_version_settings(self):
        """
        获取版本设置
        
        Returns:
            dict: {
                "success": bool,
                "settings": {
                    "autoTranslateChangelog": bool
                }
            }
        """
        return self._settings_manager.get_version_settings()
    
    def update_version_settings(self, settings: dict):
        """
        更新版本设置
        
        Args:
            settings: 版本设置
            
        Returns:
            dict: {
                "success": bool,
                "message": str,
                "settings": dict
            }
        """
        return self._settings_manager.update_version_settings(settings)

    # ==================== 插件管理 API ====================

    def get_plugins(self, use_cache: bool = True):
        """获取插件列表"""
        return self._plugin_controller.get_plugins(use_cache)

    def search_plugins(self, keyword: str):
        """搜索插件"""
        return self._plugin_controller.search_plugins(keyword)

    def refresh_plugins(self):
        """刷新插件列表"""
        return self._plugin_controller.refresh_plugins()
    
    def refresh_plugin_git_info(self, plugin_name: str):
        """
        刷新单个插件的 Git 信息
        
        Args:
            plugin_name: 插件名称
            
        Returns:
            dict: 刷新结果，包含更新后的插件信息
        """
        return self._plugin_controller.refresh_plugin_git_info(plugin_name)
    
    def get_refresh_progress(self):
        """获取刷新进度"""
        return self._plugin_controller.get_refresh_progress()
    
    def cancel_background_update(self):
        """取消后台更新任务"""
        return self._plugin_controller.cancel_background_update()

    def get_plugin_dependencies(self, plugin_name: str):
        """获取插件依赖"""
        return self._plugin_controller.get_plugin_dependencies(plugin_name)

    def install_dependency(self, plugin_name: str, package: str, version: str = "", pip_options: list = None):
        """
        安装依赖
        
        Args:
            plugin_name: 插件名称
            package: 包名
            version: 版本要求
            pip_options: pip 额外选项列表（可选，如 ["--extra-index-url", "https://..."]）
        
        Returns:
            安装结果
        """
        return self._plugin_controller.install_dependency(plugin_name, package, version, pip_options)
    
    def open_log_file(self, log_file_path: str):
        """
        打开日志文件
        
        Args:
            log_file_path: 日志文件路径
            
        Returns:
            dict: 操作结果
        """
        try:
            import os
            import subprocess
            from pathlib import Path
            
            log_path = Path(log_file_path)
            
            # 检查文件是否存在
            if not log_path.exists():
                return {
                    'success': False,
                    'message': f'日志文件不存在: {log_file_path}'
                }
            
            # 使用系统默认程序打开文件
            if os.name == 'nt':  # Windows
                os.startfile(str(log_path))
            elif os.name == 'posix':  # macOS/Linux
                if sys.platform == 'darwin':  # macOS
                    subprocess.run(['open', str(log_path)])
                else:  # Linux
                    subprocess.run(['xdg-open', str(log_path)])
            
            return {
                'success': True,
                'message': '已打开日志文件'
            }
        
        except Exception as e:
            logger.error(f"[API] 打开日志文件失败: {str(e)}")
            return {
                'success': False,
                'message': f'打开日志文件失败: {str(e)}'
            }

    def update_plugin(self, plugin_name: str, force: bool = False):
        """
        更新插件
        
        Args:
            plugin_name: 插件名称
            force: 是否强制覆盖本地修改
            
        Returns:
            dict: 更新结果
        """
        return self._plugin_controller.update_plugin(plugin_name, force=force)

    def update_all_plugins(self, python_path: Optional[str] = None, max_workers: Optional[int] = None):
        """
        一键更新所有插件
        
        Args:
            python_path: Python 可执行文件路径（可选）
            max_workers: Git 并发数（可选）
        
        Returns:
            dict: 更新结果
        """
        return self._plugin_controller.update_all_plugins(python_path, max_workers)

    def get_update_info(self, plugin_name: str):
        """获取更新信息"""
        return self._plugin_controller.get_update_info(plugin_name)

    def switch_plugin_branch(
        self, 
        plugin_name: str, 
        branch: str,
        commit_hash: str = None,
        commit_date: str = None
    ):
        """
        切换插件分支
        
        Args:
            plugin_name: 插件名称
            branch: 分支名
            commit_hash: 分支的 commit hash（可选）
            commit_date: 分支的 commit date（可选）
        """
        return self._plugin_controller.switch_branch(plugin_name, branch, commit_hash, commit_date)

    def get_plugin_branches(self, plugin_name: str):
        """获取插件分支列表"""
        return self._plugin_controller.get_branches(plugin_name)

    def uninstall_plugin(self, plugin_name: str):
        """卸载插件"""
        return self._plugin_controller.uninstall_plugin(plugin_name)

    def open_plugin_folder(self, plugin_name: str):
        """打开插件文件夹"""
        return self._plugin_controller.open_plugin_folder(plugin_name)

    def detect_plugin_conflicts(self):
        """检测插件依赖冲突"""
        return self._plugin_controller.detect_conflicts()
    
    def toggle_plugin_enabled(self, plugin_name: str, enabled: bool):
        """切换插件启用/禁用状态"""
        return self._plugin_controller.toggle_plugin_enabled(plugin_name, enabled)
    
    def check_git_permissions(self):
        """检查 Git 权限"""
        return self._plugin_controller.check_git_permissions()
    
    def fix_git_permissions(self):
        """修复 Git 权限"""
        return self._plugin_controller.fix_git_permissions()
    
    def set_plugin_remote_url(self, plugin_name: str, remote_url: str) -> Dict:
        """
        设置插件的远端地址
        
        当插件目录未配置远端地址时，用户可以通过此 API 手动设置远端地址。
        设置成功后会自动尝试 fetch 验证连接。
        
        Args:
            plugin_name: 插件名称
            remote_url: 远端仓库地址
            
        Returns:
            dict: {
                "success": bool,
                "message": str,  # 成功消息
                "error": str    # 错误消息（失败时）
            }
        """
        return self._plugin_controller.set_plugin_remote_url(plugin_name, remote_url)
    
    def switch_plugin_version(self, plugin_name: str, commit_hash: str, commit_date: str = None, behind_commits: int = None, force: bool = False) -> Dict:
        """
        切换插件版本（增强版 - 支持进度回调、备份和依赖检测）
        
        Args:
            plugin_name: 插件名称
            commit_hash: 目标提交哈希值
            commit_date: 提交日期（可选，前端已获取）
            behind_commits: 落后提交数（可选，前端已计算）
            force: 是否强制覆盖本地修改
            
        Returns:
            dict: {
                "success": bool,
                "message": str,
                "plugin": dict  # 更新后的插件信息（成功时）
            }
        """
        try:
            if not plugin_name or not isinstance(plugin_name, str):
                return {
                    "success": False,
                    "message": "插件名称无效"
                }
            
            if not commit_hash or not isinstance(commit_hash, str):
                return {
                    "success": False,
                    "message": "提交哈希值无效"
                }
            
            if len(commit_hash) < 7 or not all(c in '0123456789abcdefABCDEF' for c in commit_hash):
                return {
                    "success": False,
                    "message": "提交哈希值格式无效"
                }
            
            logger.info(f"[API] 开始切换插件版本: {plugin_name} -> {commit_hash}")
            
            result = self._plugin_controller.switch_plugin_version(
                plugin_name,
                commit_hash,
                commit_date=commit_date,
                behind_commits=behind_commits,
                force=force
            )
            
            if result.get('success'):
                logger.info(f"[API] 插件版本切换成功: {plugin_name}")
            else:
                logger.error(f"[API] 插件版本切换失败: {plugin_name}, 错误: {result.get('error') or result.get('message')}")
            
            return result
            
        except Exception as e:
            logger.error(f"[API] 切换插件版本时发生异常: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return {
                "success": False,
                "message": f"切换版本失败: {str(e)}"
            }

    def get_plugin_note(self, plugin_name: str):
        """
        获取插件备注
        
        Args:
            plugin_name: 插件名称（支持带 .disabled 后缀）
            
        Returns:
            dict: {
                "success": bool,
                "note": str or None
            }
        """
        try:
            from backend.src.core.plugin.plugin_notes import get_plugin_note
            note = get_plugin_note(plugin_name)
            return {
                "success": True,
                "note": note
            }
        except Exception as e:
            logger.error(f"[API] 获取插件备注失败: {str(e)}")
            return {
                "success": False,
                "note": None,
                "error": str(e)
            }

    def save_plugin_note(self, plugin_name: str, note: str):
        """
        保存插件备注
        
        Args:
            plugin_name: 插件名称（支持带 .disabled 后缀）
            note: 备注内容（空字符串表示删除备注）
            
        Returns:
            dict: {
                "success": bool,
                "message": str
            }
        """
        try:
            from backend.src.core.plugin.plugin_notes import save_plugin_note
            result = save_plugin_note(plugin_name, note or "")
            if result:
                return {
                    "success": True,
                    "message": "备注保存成功"
                }
            else:
                return {
                    "success": False,
                    "message": "备注保存失败"
                }
        except Exception as e:
            logger.error(f"[API] 保存插件备注失败: {str(e)}")
            return {
                "success": False,
                "message": f"保存备注失败: {str(e)}"
            }

    def get_all_plugin_notes(self):
        """
        获取所有插件备注
        
        Returns:
            dict: {
                "success": bool,
                "notes": dict  # { plugin_id: note_content }
            }
        """
        try:
            from backend.src.core.plugin.plugin_notes import get_all_plugin_notes
            notes = get_all_plugin_notes()
            return {
                "success": True,
                "notes": notes
            }
        except Exception as e:
            logger.error(f"[API] 获取所有插件备注失败: {str(e)}")
            return {
                "success": False,
                "notes": {},
                "error": str(e)
            }

    # ==================== 插件市场管理 API ====================

    def marketplace_get_plugins(self, use_cache: bool = True):
        """
        获取插件市场的插件列表
        
        Args:
            use_cache: 是否使用缓存
            
        Returns:
            dict: 插件列表响应
        """
        return self._marketplace_controller.get_plugins(use_cache)

    def marketplace_get_recommended_plugins(self, use_cache: bool = True):
        """
        获取推荐插件列表
        
        Args:
            use_cache: 是否使用缓存
            
        Returns:
            dict: 推荐插件列表响应
        """
        return self._marketplace_controller.get_recommended_plugins(use_cache)

    def marketplace_search_plugins(self, keyword: str):
        """
        搜索插件市场中的插件
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            dict: 搜索结果
        """
        return self._marketplace_controller.search_plugins(keyword)

    def marketplace_refresh_plugins(self):
        """
        刷新插件市场列表（清除缓存）
        
        Returns:
            dict: 刷新结果
        """
        return self._marketplace_controller.refresh_plugins()

    def marketplace_install_plugin(self, github_url: str, auto_install_deps: bool = True):
        """
        从插件市场安装插件
        
        Args:
            github_url: GitHub 仓库地址
            auto_install_deps: 是否自动安装依赖
            
        Returns:
            dict: 安装结果
        """
        return self._marketplace_controller.install_plugin(github_url, auto_install_deps)

    def marketplace_check_dependencies(self, github_url: str):
        """
        检查插件依赖冲突
        
        Args:
            github_url: GitHub 仓库地址
            
        Returns:
            dict: 依赖冲突检查结果
        """
        return self._marketplace_controller.check_dependencies(github_url)

    def marketplace_get_install_progress(self, task_id: str):
        """
        获取插件安装进度
        
        Args:
            task_id: 任务 ID
            
        Returns:
            dict: 安装进度信息
        """
        return self._marketplace_controller.get_install_progress(task_id)

    def marketplace_cancel_installation(self, task_id: str):
        """
        取消正在进行的插件安装任务
        
        Args:
            task_id: 任务 ID
            
        Returns:
            dict: 取消结果
        """
        return self._marketplace_controller.cancel_installation(task_id)
    
    def marketplace_get_installed_plugins_status(self):
        """
        获取当前环境下已安装插件的状态
        
        Returns:
            dict: {
                'success': bool,
                'installed_plugins': [plugin_name1, plugin_name2, ...],
                'error': str (如果失败)
            }
        """
        return self._marketplace_controller.get_installed_plugins_status()


    # ========== AI 助手 API ==========
    
    def ai_create_topic(self, name: str = "新对话"):
        """
        创建新话题
        
        Args:
            name: 话题名称，默认为"新对话"
            
        Returns:
            dict: 操作结果
        """
        return self._ai_controller.ai_create_topic(name)
    
    def ai_get_topics(self):
        """
        获取所有话题
        
        Returns:
            dict: 话题列表
        """
        return self._ai_controller.ai_get_topics()
    
    def ai_delete_topic(self, topic_id: str):
        """
        删除话题
        
        Args:
            topic_id: 话题 ID
            
        Returns:
            dict: 操作结果
        """
        return self._ai_controller.ai_delete_topic(topic_id)
    
    def ai_rename_topic(self, topic_id: str, name: str):
        """
        重命名话题
        
        Args:
            topic_id: 话题 ID
            name: 新名称
            
        Returns:
            dict: 操作结果
        """
        return self._ai_controller.ai_rename_topic(topic_id, name)
    
    def ai_send_message_with_config(self, topic_id: str, content: str, config_id: str, deep_thinking: bool = False, web_search_enabled: bool = False, system_prompt: str = None, files: list = None):
        """
        使用指定配置发送消息并开始流式响应
        
        Args:
            topic_id: 话题 ID
            content: 用户消息内容
            config_id: API 配置 ID
            deep_thinking: 是否启用深度思考（默认 False）
            web_search_enabled: 是否启用联网搜索（默认 False）
            system_prompt: 系统提示词（可选）
            files: 文件列表（可选）
            
        Returns:
            dict: 操作结果
        """
        return self._ai_controller.ai_send_message_with_config(topic_id, content, config_id, deep_thinking, web_search_enabled, system_prompt, files)
    
    def ai_get_messages(self, topic_id: str, limit: int = 100, offset: int = 0):
        """
        获取话题的消息列表
        
        Args:
            topic_id: 话题 ID
            limit: 返回的最大消息数
            offset: 偏移量（用于分页）
            
        Returns:
            dict: 消息列表
        """
        return self._ai_controller.ai_get_messages(topic_id, limit, offset)
    
    def ai_clear_messages(self, topic_id: str):
        """
        清空话题的所有消息
        
        Args:
            topic_id: 话题 ID
            
        Returns:
            dict: 操作结果
        """
        return self._ai_controller.ai_clear_messages(topic_id)
    
    def ai_test_connection(self, provider: str, config: dict):
        """
        测试服务商连接
        
        Args:
            provider: 服务商名称
            config: 服务商配置
            
        Returns:
            dict: 测试结果
        """
        return self._ai_controller.ai_test_connection(provider, config)
    
    def ai_get_search_config(self):
        """
        获取搜索配置
        
        Returns:
            dict: 搜索配置
        """
        return self._ai_controller.ai_get_search_config()
    
    def ai_update_search_config(self, config: dict):
        """
        更新搜索配置
        
        Args:
            config: 搜索配置
            
        Returns:
            dict: 操作结果
        """
        return self._ai_controller.ai_update_search_config(config)
    
    def ai_test_search_connection(self, provider: str, config: dict):
        """
        测试搜索引擎连接
        
        Args:
            provider: 搜索引擎名称（duckduckgo/google）
            config: 搜索引擎配置
            
        Returns:
            dict: 测试结果
        """
        return self._ai_controller.ai_test_search_connection(provider, config)
    
    def ai_stop_generation(self, topic_id: str):
        """
        停止当前话题的 AI 生成
        
        Args:
            topic_id: 话题 ID
            
        Returns:
            dict: 操作结果
        """
        return self._ai_controller.ai_stop_generation(topic_id)
    
    # ========== AI 多配置管理 API ==========
    
    def ai_list_configs(self):
        """
        获取所有 API 配置列表
        
        Returns:
            dict: 配置列表
        """
        return self._ai_controller.ai_list_configs()
    
    def ai_get_config_detail(self, config_id: str):
        """
        获取配置详情
        
        Args:
            config_id: 配置 ID
            
        Returns:
            dict: 配置详情
        """
        return self._ai_controller.ai_get_config_detail(config_id)
    
    def ai_create_config(self, config: dict):
        """
        创建新配置
        
        Args:
            config: 配置数据
            
        Returns:
            dict: 操作结果（包含新配置 ID）
        """
        return self._ai_controller.ai_create_config(config)
    
    def ai_update_config(self, config_id: str, config: dict):
        """
        更新配置
        
        Args:
            config_id: 配置 ID
            config: 配置数据
            
        Returns:
            dict: 操作结果
        """
        return self._ai_controller.ai_update_config(config_id, config)
    
    def ai_delete_config(self, config_id: str):
        """
        删除配置
        
        Args:
            config_id: 配置 ID
            
        Returns:
            dict: 操作结果
        """
        return self._ai_controller.ai_delete_config(config_id)
    
    def ai_set_default_config(self, config_id: str):
        """
        设置默认配置
        
        Args:
            config_id: 配置 ID
            
        Returns:
            dict: 操作结果
        """
        return self._ai_controller.ai_set_default_config(config_id)
    
    def ai_test_config(self, config_id: str):
        """
        测试配置连接
        
        Args:
            config_id: 配置 ID
            
        Returns:
            dict: 测试结果
        """
        return self._ai_controller.ai_test_config(config_id)
    
    def ai_get_available_models(self, provider: str, config: dict):
        """
        获取服务商的可用模型列表
        
        Args:
            provider: 服务商名称
            config: 服务商配置
            
        Returns:
            dict: 模型列表
        """
        return self._ai_controller.ai_get_available_models(provider, config)

    # ========== 模型选择器 API ==========
    
    def ai_get_default_config(self):
        """
        获取默认配置 ID
        
        Returns:
            dict: 默认配置 ID
        """
        return self._ai_controller.ai_get_default_config()
    
    def ai_set_topic_config(self, topic_id: str, config_id: str):
        """
        设置对话的激活配置
        
        Args:
            topic_id: 对话 ID
            config_id: API 配置 ID
            
        Returns:
            dict: 操作结果
        """
        return self._ai_controller.ai_set_topic_config(topic_id, config_id)
    
    def ai_get_topic_config(self, topic_id: str):
        """
        获取对话的激活配置
        
        Args:
            topic_id: 对话 ID
            
        Returns:
            dict: 配置 ID
        """
        return self._ai_controller.ai_get_topic_config(topic_id)
    
    def ai_export_chat(self, topic_id: str, format: str = "json"):
        """
        导出聊天记录
        
        Args:
            topic_id: 话题 ID
            format: 导出格式，支持 "json" 或 "markdown"
            
        Returns:
            dict: 导出结果
        """
        return self._ai_controller.ai_export_chat(topic_id, format)

    # ========== 系统提示词管理 API ==========
    
    def ai_get_system_prompts(self):
        """
        获取所有系统提示词预设
        
        Returns:
            dict: {
                "success": bool,
                "presets": List[dict],
                "error_message": str
            }
        """
        return self._ai_controller.ai_get_system_prompts()
    
    def ai_create_system_prompt(self, name: str, content: str):
        """
        创建新的系统提示词预设
        
        Args:
            name: 预设名称
            content: 提示词内容
            
        Returns:
            dict: {
                "success": bool,
                "preset": dict,
                "error_message": str
            }
        """
        return self._ai_controller.ai_create_system_prompt(name, content)
    
    def ai_update_system_prompt(self, preset_id: str, name: str = None, content: str = None):
        """
        更新现有系统提示词预设
        
        Args:
            preset_id: 预设ID
            name: 新名称（可选）
            content: 新内容（可选）
            
        Returns:
            dict: {
                "success": bool,
                "error_message": str
            }
        """
        return self._ai_controller.ai_update_system_prompt(preset_id, name, content)
    
    def ai_delete_system_prompt(self, preset_id: str):
        """
        删除系统提示词预设
        
        Args:
            preset_id: 预设ID
            
        Returns:
            dict: {
                "success": bool,
                "error_message": str
            }
        """
        return self._ai_controller.ai_delete_system_prompt(preset_id)
    
    def ai_set_active_system_prompt(self, topic_id: str, preset_id: str = None):
        """
        设置对话的激活系统提示词预设
        
        Args:
            topic_id: 对话ID
            preset_id: 预设ID（None表示"无"）
            
        Returns:
            dict: {
                "success": bool,
                "error_message": str
            }
        """
        return self._ai_controller.ai_set_active_system_prompt(topic_id, preset_id)
    
    def ai_get_active_system_prompt(self, topic_id: str):
        """
        获取对话的激活系统提示词预设
        
        Args:
            topic_id: 对话ID
            
        Returns:
            dict: {
                "success": bool,
                "preset_id": str | None,
                "error_message": str
            }
        """
        return self._ai_controller.ai_get_active_system_prompt(topic_id)
    
    def ai_process_file(self, file_data: str, file_name: str, file_type: str, file_size: int):
        """
        处理上传的文件
        
        Args:
            file_data: Base64编码的文件数据
            file_name: 文件名
            file_type: MIME类型
            file_size: 文件大小（字节）
            
        Returns:
            dict: {
                "success": bool,
                "file_id": str,
                "processed_data": dict,
                "error_message": str
            }
        """
        return self._ai_controller.ai_process_file(file_data, file_name, file_type, file_size)

    # ========== 依赖管理 API ==========
    
    def dependency_detect_cuda_version(self):
        """
        检测系统 CUDA 版本
        
        Returns:
            dict: {
                "success": bool,
                "cuda_version": str | None,
                "error_message": str (可选)
            }
        """
        return self._dependency_controller.detect_cuda_version()
    
    def dependency_fetch_pytorch_versions(self, cuda_version: str):
        """
        获取 PyTorch 可用版本列表
        
        Args:
            cuda_version: CUDA 版本
            
        Returns:
            dict: {
                "success": bool,
                "versions": list[str],
                "error_message": str (可选)
            }
        """
        return self._dependency_controller.fetch_pytorch_versions(cuda_version)
    
    def dependency_install_pytorch(self, version: str, cuda_version: str, mirror_source: str = 'official'):
        """
        安装 PyTorch
        
        Args:
            version: PyTorch 版本
            cuda_version: CUDA 版本
            mirror_source: 镜像源 ('auto', 'official', 'tuna', 'bfsu', 'aliyun', 'tencent')
            
        Returns:
            dict: {
                "success": bool,
                "log_file": str,
                "error_message": str (可选)
            }
        """
        return self._dependency_controller.install_pytorch(version, cuda_version, mirror_source)
    
    def dependency_search_package(self, package_name: str, mirror_source: str = 'official'):
        """
        搜索 PyPI 包信息
        
        Args:
            package_name: 包名
            mirror_source: 镜像源 ('auto', 'official', 'tuna', 'bfsu', 'aliyun', 'tencent')
            
        Returns:
            dict: {
                "success": bool,
                "package_info": dict,
                "error_message": str (可选)
            }
        """
        return self._dependency_controller.search_package(package_name, mirror_source)
    
    def dependency_get_installed_version(self, package_name: str):
        """
        获取已安装包的版本
        
        Args:
            package_name: 包名
            
        Returns:
            dict: {
                "success": bool,
                "version": str | None,
                "installed": bool,
                "error_message": str (可选)
            }
        """
        return self._dependency_controller.get_installed_version(package_name)
    
    def dependency_fetch_package_versions(self, package_name: str, mirror_source: str = 'official'):
        """
        获取包的所有版本
        
        Args:
            package_name: 包名
            mirror_source: 镜像源 ('auto', 'official', 'tuna', 'bfsu', 'aliyun', 'tencent')
            
        Returns:
            dict: {
                "success": bool,
                "versions": list[str],
                "error_message": str (可选)
            }
        """
        return self._dependency_controller.fetch_package_versions(package_name, mirror_source)
    
    def dependency_install_package(self, package_name: str, version: str, mode: str, mirror_source: str = 'official'):
        """
        安装包
        
        Args:
            package_name: 包名
            version: 版本
            mode: 安装模式 ('dry-run' 或 'install')
            mirror_source: 镜像源 ('auto', 'official', 'tuna', 'bfsu', 'aliyun', 'tencent')
            
        Returns:
            dict: {
                "success": bool,
                "log_file": str,
                "error_message": str (可选)
            }
        """
        return self._dependency_controller.install_package(package_name, version, mode, mirror_source)
    
    def dependency_uninstall_package(self, package_name: str):
        """
        卸载包
        
        Args:
            package_name: 包名
            
        Returns:
            dict: {
                "success": bool,
                "log_file": str,
                "error_message": str (可选)
            }
        """
        return self._dependency_controller.uninstall_package(package_name)
    
    def dependency_install_from_requirements(self, file_path: str, mode: str, mirror_source: str = 'official'):
        """
        从 requirements.txt 安装依赖
        
        Args:
            file_path: requirements.txt 文件路径
            mode: 安装模式 ('dry-run' 或 'install')
            mirror_source: 镜像源 ('auto', 'official', 'tuna', 'bfsu', 'aliyun', 'tencent')
            
        Returns:
            dict: {
                "success": bool,
                "log_file": str,
                "error_message": str (可选)
            }
        """
        return self._dependency_controller.install_from_requirements(file_path, mode, mirror_source)
    
    def dependency_select_file(self, file_types: str = 'all'):
        """
        打开文件选择对话框
        
        Args:
            file_types: 文件类型过滤 ('requirements', 'whl', 'all')
            
        Returns:
            dict: {
                "success": bool,
                "file_path": str,
                "file_type": str,
                "error_message": str (可选)
            }
        """
        return self._dependency_controller.select_file(file_types)
    
    def dependency_analyze_requirements_file(self, file_path: str):
        """
        分析 requirements.txt 文件中的依赖
        
        Args:
            file_path: requirements.txt 文件路径
            
        Returns:
            dict: {
                "success": bool,
                "data": {
                    "total": int,
                    "installed": int,
                    "not_installed": int,
                    "conflicts": int,
                    "dependencies": [...]
                },
                "error_message": str (可选)
            }
        """
        return self._dependency_controller.analyze_requirements_file(file_path)
    
    def dependency_install_whl(self, file_path: str):
        """
        安装 .whl 文件
        
        Args:
            file_path: .whl 文件路径
            
        Returns:
            dict: {
                "success": bool,
                "log_file": str,
                "error_message": str (可选)
            }
        """
        return self._dependency_controller.install_whl(file_path)
    
    def dependency_open_terminal(self):
        """
        打开终端并设置环境变量
        
        Returns:
            dict: {
                "success": bool,
                "error_message": str (可选)
            }
        """
        return self._dependency_controller.open_terminal()
    
    def dependency_detect_environment(self):
        """
        检测环境信息
        
        Returns:
            dict: {
                "success": bool,
                "env_info": dict,
                "error_message": str (可选)
            }
        """
        return self._dependency_controller.detect_environment()
    
    def dependency_analyze_logs_with_ai(self, logs: str, api_config_id: str = None):
        """
        使用 AI 分析日志
        
        Args:
            logs: 日志内容
            api_config_id: API 配置 ID（可选，如果为 None 则使用默认配置）
        
        Returns:
            dict: {
                "success": bool,
                "topic_id": str,  # 创建的话题 ID
                "error_message": str (可选)
            }
            
        注意：此方法会创建一个新话题并发送消息，流式响应通过 window.evaluate_js 发送到前端
        """
        return self._dependency_controller.analyze_logs_with_ai(logs, api_config_id)
    
    def dependency_scan_dependencies(self):
        """
        扫描 ComfyUI 核心和所有插件的依赖
        
        Returns:
            dict: {
                "success": bool,
                "data": {
                    "core": list,
                    "plugins": dict
                },
                "error_message": str (可选)
            }
        """
        return self._dependency_controller.scan_dependencies()
    
    def dependency_check_package_status(self, package_name: str):
        """
        检查单个包的安装状态
        
        Args:
            package_name: 包名
            
        Returns:
            dict: {
                "success": bool,
                "data": {
                    "installed": bool,
                    "version": str | None,
                    "location": str | None
                },
                "error_message": str (可选)
            }
        """
        return self._dependency_controller.check_package_status(package_name)
    
    def dependency_check_all_status(self, packages: list):
        """
        批量检查包的安装状态
        
        Args:
            packages: 包名列表
            
        Returns:
            dict: {
                "success": bool,
                "data": dict,
                "error_message": str (可选)
            }
        """
        return self._dependency_controller.check_all_status(packages)
    
    def dependency_get_plugins(self):
        """
        获取所有插件列表
        
        Returns:
            dict: {
                "success": bool,
                "data": list,
                "error_message": str (可选)
            }
        """
        return self._dependency_controller.get_plugins()
    
    def dependency_check_pipdeptree(self):
        """
        检查 pipdeptree 是否已安装
        
        Returns:
            dict: {
                "success": bool,
                "installed": bool,
                "version": str | None,
                "error_message": str (可选)
            }
        """
        return self._dependency_controller.check_pipdeptree()
    
    def dependency_install_pipdeptree(self):
        """
        安装 pipdeptree 工具
        
        Returns:
            dict: {
                "success": bool,
                "message": str,
                "error_message": str (可选)
            }
        """
        return self._dependency_controller.install_pipdeptree()
    def dependency_analyze_dependencies(self):
        """
        分析当前环境的依赖树和冲突
        
        Returns:
            dict: {
                "success": bool,
                "data": dict | None,
                "error_message": str (可选)
            }
        """
        return self._dependency_controller.analyze_dependencies()
    
    def dependency_fix_conflict(self, conflict_data: dict, mirror_source: str = 'official'):
        """
        修复单个依赖冲突
        
        Args:
            conflict_data: 冲突数据
            mirror_source: 镜像源
            
        Returns:
            dict: {
                "success": bool,
                "message": str,
                "error_message": str (可选)
            }
        """
        return self._dependency_controller.fix_conflict(conflict_data, mirror_source)
    
    def dependency_export_analysis_report(self, format: str, tree_data: list, conflicts_data: list):
        """
        导出依赖分析报告
        
        Args:
            format: 导出格式 ('json' 或 'markdown')
            tree_data: 依赖树数据
            conflicts_data: 冲突数据
            
        Returns:
            dict: {
                "success": bool,
                "file_path": str | None,
                "error_message": str (可选)
            }
        """
        return self._dependency_controller.export_analysis_report(format, tree_data, conflicts_data)


    # ========== 救援模式 API ==========

    def rescue_check_process(self):
        """
        检查 ComfyUI 进程是否正在运行

        Returns:
            dict: {"running": bool}
        """
        # 确保进程管理器已初始化并注入
        self.__init_process_manager()
        return self._rescue_controller.rescue_check_process()

    def rescue_create_snapshot(self, name: str, backup_option: str, include_git: bool, note: str):
        """
        创建环境快照

        Args:
            name: 快照名称（1-50 字符）
            backup_option: 备份选项 "deps_only" | "plugins_only" | "all"
            include_git: 是否保留插件 .git 目录
            note: 备注信息（0-500 字符）

        Returns:
            dict: {success, snapshot_info, error_message}
        """
        return self._rescue_controller.rescue_create_snapshot(name, backup_option, include_git, note)

    def rescue_list_snapshots(self):
        """
        列出当前环境的所有快照

        Returns:
            dict: {success, snapshots[], error_message}
        """
        return self._rescue_controller.rescue_list_snapshots()

    def rescue_delete_snapshot(self, snapshot_path: str):
        """
        删除指定的快照文件

        Args:
            snapshot_path: 快照 zip 文件的路径

        Returns:
            dict: {success, error_message}
        """
        return self._rescue_controller.rescue_delete_snapshot(snapshot_path)

    def rescue_update_snapshot(self, snapshot_path: str, name: str, note: str):
        """
        更新快照元数据（name 和 note）

        Args:
            snapshot_path: 快照 zip 文件路径
            name: 新的快照名称（1-50 字符）
            note: 新的备注信息（0-500 字符）

        Returns:
            dict: {success, snapshot_info, error_message}
        """
        return self._rescue_controller.rescue_update_snapshot(snapshot_path, name, note)

    def rescue_compute_diff(self, snapshot_path: str):
        """
        计算当前环境与快照之间的差异

        Args:
            snapshot_path: 快照 zip 文件的路径

        Returns:
            dict: {success, diff_result, error_message}
        """
        return self._rescue_controller.rescue_compute_diff(snapshot_path)

    def rescue_smart_rollback(self, snapshot_path: str):
        """
        执行智能回滚（基于差异对比）

        Args:
            snapshot_path: 快照 zip 文件的路径

        Returns:
            dict: {success, report: {totalItems, succeeded, failed, failures[]}, error_message}
        """
        return self._rescue_controller.rescue_smart_rollback(snapshot_path)

    def rescue_direct_restore(self, snapshot_path: str, restore_mode: str):
        """
        执行直接恢复（覆盖式）

        Args:
            snapshot_path: 快照 zip 文件的路径
            restore_mode: 恢复模式 "deps_only" | "plugins_only" | "all"

        Returns:
            dict: {success, error_message}
        """
        return self._rescue_controller.rescue_direct_restore(snapshot_path, restore_mode)


    # ========== 工作流配置 API ==========

    def workflow_get_config(self):
        """
        获取工作流配置
        
        Returns:
            dict: {
                "success": bool,
                "config": dict
            }
        """
        return self._workflow_config_manager.get_config()

    def workflow_update_config(self, updates: dict):
        """
        更新工作流配置
        
        Args:
            updates: 要更新的配置项
            
        Returns:
            dict: {
                "success": bool,
                "config": dict,
                "message": str (可选)
            }
        """
        result = self._workflow_config_manager.update_config(updates)
        if result.get("success"):
            self._workflow_controller.reset_initialization()
        return result

    def workflow_set_env_path(self, env_id: str, path: str):
        """
        设置指定环境的工作流目录
        
        Args:
            env_id: 环境 ID
            path: 工作流目录路径
            
        Returns:
            dict: {"success": bool, "message": str}
        """
        result = self._workflow_config_manager.set_env_path(env_id, path)
        if result.get("success"):
            current_env = self._environment_controller.manager.get_current_environment()
            if current_env and current_env.id == env_id:
                self._workflow_controller.reset_initialization()
        return result

    def workflow_set_global_path(self, path: str):
        """
        设置全局工作流目录
        
        Args:
            path: 全局工作流目录路径
            
        Returns:
            dict: {"success": bool, "message": str}
        """
        result = self._workflow_config_manager.set_global_path(path)
        if result.get("success"):
            self._workflow_controller.reset_initialization()
        return result

    def workflow_set_use_global_path(self, use_global: bool):
        """
        设置是否使用全局工作流目录
        
        Args:
            use_global: 是否使用全局目录
            
        Returns:
            dict: {"success": bool, "message": str}
        """
        result = self._workflow_config_manager.set_use_global_path(use_global)
        if result.get("success"):
            self._workflow_controller.reset_initialization()
        return result

    def workflow_remove_env_path(self, env_id: str):
        """
        移除指定环境的工作流目录配置
        
        Args:
            env_id: 环境 ID
            
        Returns:
            dict: {"success": bool, "message": str}
        """
        return self._workflow_config_manager.remove_env_path(env_id)

    def workflow_initialize_all_env_paths(self):
        """
        初始化所有环境的工作流目录配置
        
        Returns:
            dict: {"success": bool, "message": str}
        """
        env_result = self._environment_controller.get_environments()
        environments = env_result.get("environments", [])
        return self._workflow_config_manager.initialize_all_env_paths(environments)


    # ========== LoRA 管理 API ==========

    def lora_get_config(self):
        """
        获取 LoRA 完整配置
        
        Returns:
            dict: {
                "success": bool,
                "config": dict,
                "message": str (可选)
            }
        """
        return self._lora_config_manager.get_config()
    
    def lora_update_config(self, updates: dict):
        """
        更新 LoRA 配置
        
        Args:
            updates: 要更新的配置项
            
        Returns:
            dict: {
                "success": bool,
                "config": dict,
                "message": str (可选)
            }
        """
        return self._lora_config_manager.update_config(updates)
    
    def lora_reset_config(self):
        """
        重置 LoRA 配置为默认值
        
        Returns:
            dict: {
                "success": bool,
                "message": str
            }
        """
        return self._lora_config_manager.reset_config()
    
    def lora_get_civitai_config(self):
        """
        获取 Civitai 配置
        
        Returns:
            dict: {
                "success": bool,
                "config": dict,
                "message": str (可选)
            }
        """
        return self._lora_config_manager.get_civitai_config()
    
    def lora_update_civitai_config(self, updates: dict):
        """
        更新 Civitai 配置
        
        Args:
            updates: 要更新的配置项（api_key, enabled, auto_sync, sync_interval_hours）
            
        Returns:
            dict: {
                "success": bool,
                "config": dict,
                "message": str (可选)
            }
        """
        return self._lora_config_manager.update_civitai_config(updates)
    
    def lora_set_civitai_api_key(self, api_key: str):
        """
        设置 Civitai API Key
        
        Args:
            api_key: API Key 字符串
            
        Returns:
            dict: {
                "success": bool,
                "message": str
            }
        """
        return self._lora_config_manager.set_civitai_api_key(api_key)
    
    def lora_get_scan_paths(self):
        """
        获取扫描路径列表
        
        Returns:
            dict: {
                "success": bool,
                "paths": list,
                "message": str (可选)
            }
        """
        return self._lora_config_manager.get_scan_paths()
    
    def lora_add_scan_path(self, path: str, name: str = None, category: str = None):
        """
        添加扫描路径
        
        Args:
            path: 文件夹路径
            name: 路径名称（可选）
            category: 分类（可选）
            
        Returns:
            dict: {
                "success": bool,
                "path": dict,
                "message": str
            }
        """
        return self._lora_config_manager.add_scan_path(path, name, category)
    
    def lora_update_scan_path(self, path_id: str, updates: dict):
        """
        更新扫描路径
        
        Args:
            path_id: 路径 ID
            updates: 要更新的字段
            
        Returns:
            dict: {
                "success": bool,
                "message": str
            }
        """
        return self._lora_config_manager.update_scan_path(path_id, updates)
    
    def lora_remove_scan_path(self, path_id: str):
        """
        删除扫描路径
        
        Args:
            path_id: 路径 ID
            
        Returns:
            dict: {
                "success": bool,
                "message": str
            }
        """
        return self._lora_config_manager.remove_scan_path(path_id)
    
    def lora_get_categories(self):
        """
        获取分类列表
        
        Returns:
            dict: {
                "success": bool,
                "categories": list,
                "message": str (可选)
            }
        """
        return self._lora_config_manager.get_categories()
    
    def lora_add_category(self, name: str, id: str = None):
        """
        添加分类
        
        Args:
            name: 分类名称
            id: 分类 ID（可选，默认使用 name 的小写形式）
            
        Returns:
            dict: {
                "success": bool,
                "category": dict,
                "message": str
            }
        """
        return self._lora_config_manager.add_category(name, id)
    
    def lora_update_category(self, category_id: str, updates: dict):
        """
        更新分类
        
        Args:
            category_id: 分类 ID
            updates: 要更新的字段
            
        Returns:
            dict: {
                "success": bool,
                "message": str
            }
        """
        return self._lora_config_manager.update_category(category_id, updates)
    
    def lora_remove_category(self, category_id: str):
        """
        删除分类
        
        Args:
            category_id: 分类 ID
            
        Returns:
            dict: {
                "success": bool,
                "message": str
            }
        """
        return self._lora_config_manager.remove_category(category_id)
    
    def lora_get_display_config(self):
        """
        获取显示配置
        
        Returns:
            dict: {
                "success": bool,
                "config": dict,
                "message": str (可选)
            }
        """
        return self._lora_config_manager.get_display_config()
    
    def lora_update_display_config(self, updates: dict):
        """
        更新显示配置
        
        Args:
            updates: 要更新的配置项
            
        Returns:
            dict: {
                "success": bool,
                "config": dict,
                "message": str (可选)
            }
        """
        return self._lora_config_manager.update_display_config(updates)
    
    def lora_sync_models(self):
        """
        同步本地 LoRA 模型（增量更新）
        
        扫描配置的路径，更新模型列表数据。
        
        Returns:
            dict: {
                "success": bool,
                "result": {
                    "added": int,
                    "updated": int,
                    "removed": int,
                    "unchanged": int
                },
                "total": int,
                "models": list
            }
        """
        from backend.src.core.lora import LoraScanner
        
        config_result = self._lora_config_manager.get_scan_paths()
        scan_paths = config_result.get("paths", [])
        
        scanner = LoraScanner()
        return scanner.sync_models(scan_paths)
    
    def lora_pull_from_civitai(self, full: bool = False):
        """
        从 Civitai 拉取模型信息
        
        根据模型文件的哈希值从 Civitai API 获取模型信息并更新本地数据。
        
        Args:
            full: 是否全量拉取（True=重新计算所有hash，False=仅处理is_local为None的模型）
        
        Returns:
            dict: {
                "success": bool,
                "message": str,
                "updated": int
            }
        """
        from backend.src.core.lora import LoraScanner
        
        logger.info(f"[API] lora_pull_from_civitai 调用, full={full}")
        
        scanner = LoraScanner()
        stop_progress = [False]
        
        def progress_callback(stage, current, total, message, model_data=None):
            if stop_progress[0]:
                return
            if self._window:
                try:
                    import json
                    model_json = json.dumps(model_data, ensure_ascii=False) if model_data else 'null'
                    logger.debug(f"[API] 发送进度: stage={stage}, current={current}, total={total}, has_model_data={model_data is not None}")
                    js_code = f"""
                    if (window.__loraPullProgress) {{
                        window.__loraPullProgress({{
                            stage: '{stage}',
                            current: {current},
                            total: {total},
                            message: '{message.replace("'", "\\'")}',
                            modelData: {model_json}
                        }});
                    }}
                    """
                    self._window.evaluate_js(js_code)
                except Exception as e:
                    logger.warning(f"[API] 发送进度失败，停止后续更新: {str(e)}")
                    stop_progress[0] = True
        
        try:
            return scanner.pull_from_civitai(full=full, progress_callback=progress_callback)
        except Exception as e:
            logger.warning(f"[API] 拉取操作异常: {str(e)}")
            return {
                "success": False,
                "message": f"拉取操作异常: {str(e)}"
            }
    
    def lora_stop_pull(self):
        """
        停止从 Civitai 拉取模型信息
        
        Returns:
            dict: {
                "success": bool,
                "message": str
            }
        """
        from backend.src.core.lora import LoraScanner
        LoraScanner.stop_pull()
        return {
            "success": True,
            "message": "已发送停止信号"
        }
    
    def lora_get_pull_status(self):
        """
        获取当前拉取状态
        
        Returns:
            dict: {
                "success": bool,
                "pulling": bool,
                "stopping": bool,
                "progress": {
                    "stage": str,
                    "current": int,
                    "total": int,
                    "message": str,
                    "modelData": dict | null
                } | null
            }
        """
        from backend.src.core.lora import LoraScanner
        return {
            "success": True,
            "pulling": LoraScanner.is_pulling(),
            "stopping": LoraScanner.is_stopping(),
            "progress": LoraScanner.get_pull_progress()
        }
    
    def lora_get_models(self):
        """
        获取所有 LoRA 模型数据
        
        Returns:
            dict: {
                "success": bool,
                "count": int,
                "models": list
            }
        """
        from backend.src.core.lora import LoraScanner
        
        scanner = LoraScanner()
        return scanner.get_models()
    
    def lora_update_model(self, model_id: str, updates: dict):
        """
        更新单个模型的信息
        
        Args:
            model_id: 模型 ID
            updates: 要更新的字段（如 tags, trigger_words, preview_url, notes 等）
            
        Returns:
            dict: {
                "success": bool,
                "message": str,
                "model": dict (可选)
            }
        """
        from backend.src.core.lora import LoraScanner
        
        scanner = LoraScanner()
        return scanner.update_model(model_id, updates)
    
    def lora_batch_update_folder(self, model_ids: list, folder_id: str):
        """
        批量更新模型的 folder 字段
        
        Args:
            model_ids: 模型 ID 列表
            folder_id: 目标文件夹 ID（空字符串表示移除分组）
            
        Returns:
            dict: {
                "success": bool,
                "message": str,
                "updated_count": int
            }
        """
        from backend.src.core.lora import LoraScanner
        
        scanner = LoraScanner()
        return scanner.batch_update_folder(model_ids, folder_id)
    
    def lora_delete_model(self, model_id: str):
        """
        从列表中删除模型（不删除实际文件）
        
        Args:
            model_id: 模型 ID
            
        Returns:
            dict: {
                "success": bool,
                "message": str
            }
        """
        from backend.src.core.lora import LoraScanner
        
        scanner = LoraScanner()
        return scanner.delete_model(model_id)
    
    def lora_rename_model(self, model_id: str, new_name: str):
        """
        重命名模型（修改文件名 + 更新 models.json）
        
        Args:
            model_id: 模型 ID
            new_name: 新的模型名称（不含后缀）
            
        Returns:
            dict: {
                "success": bool,
                "message": str,
                "model": dict (可选),
                "old_path": str (可选),
                "new_path": str (可选)
            }
        """
        from backend.src.core.lora import LoraScanner
        
        scanner = LoraScanner()
        return scanner.rename_model(model_id, new_name)
    
    def lora_get_folders(self):
        """
        获取所有文件夹列表（用于左侧目录树）
        
        Returns:
            dict: {
                "success": bool,
                "folders": list
            }
        """
        from backend.src.core.lora import LoraScanner
        
        scanner = LoraScanner()
        return scanner.get_folders()
    
    def lora_get_categories_with_count(self):
        """
        获取分类及其模型数量
        
        Returns:
            dict: {
                "success": bool,
                "categories": dict  # {"category_id": count, ...}
            }
        """
        from backend.src.core.lora import LoraScanner
        
        scanner = LoraScanner()
        return scanner.get_categories_with_count()
    
    def lora_get_folder_structure(self):
        """
        获取文件夹结构（用于左侧导航树）
        
        Returns:
            dict: {
                "success": bool,
                "folders": list  # 文件夹树结构
            }
        """
        from backend.src.core.lora import LoraScanner
        
        scanner = LoraScanner()
        return scanner.get_folder_structure()
    
    def lora_sync_folder_structure(self):
        """
        同步文件夹结构
        
        Returns:
            dict: {
                "success": bool,
                "folders": list
            }
        """
        from backend.src.core.lora import LoraScanner
        
        config_result = self._lora_config_manager.get_scan_paths()
        scan_paths = config_result.get("paths", [])
        
        scanner = LoraScanner()
        return scanner.sync_folder_structure(scan_paths)
    
    def lora_create_folder(self, scan_path_id: str, folder_name: str, parent_folder_id: str = None):
        """
        在指定扫描路径下创建文件夹
        
        Args:
            scan_path_id: 扫描路径 ID（或路径本身）
            folder_name: 新文件夹名称
            parent_folder_id: 父文件夹 ID（可选）
            
        Returns:
            dict: {
                "success": bool,
                "message": str,
                "folder": dict (可选)
            }
        """
        from backend.src.core.lora import LoraScanner
        
        scanner = LoraScanner()
        result = scanner.create_folder(scan_path_id, folder_name, parent_folder_id)
        
        if result.get("success"):
            config_result = self._lora_config_manager.get_scan_paths()
            scan_paths = config_result.get("paths", [])
            scanner.sync_folder_structure(scan_paths)
        
        return result
    
    def lora_update_folder(self, folder_id: str, new_name: str = None, new_parent_id: str = None):
        """
        更新文件夹（重命名和/或移动）
        
        Args:
            folder_id: 文件夹 ID（相对路径）
            new_name: 新名称（可选）
            new_parent_id: 新父文件夹 ID（可选，空字符串表示移动到根目录）
            
        Returns:
            dict: {
                "success": bool,
                "message": str,
                "folder": dict (可选)
            }
        """
        from backend.src.core.lora import LoraScanner
        
        scanner = LoraScanner()
        result = scanner.update_folder(folder_id, new_name, new_parent_id)
        
        if result.get("success"):
            config_result = self._lora_config_manager.get_scan_paths()
            scan_paths = config_result.get("paths", [])
            scanner.sync_folder_structure(scan_paths)
        
        return result
    
    def lora_delete_folder(self, folder_id: str):
        """
        删除文件夹（仅支持空文件夹）
        
        Args:
            folder_id: 文件夹 ID（相对路径）
            
        Returns:
            dict: {
                "success": bool,
                "message": str
            }
        """
        from backend.src.core.lora import LoraScanner
        
        scanner = LoraScanner()
        result = scanner.delete_folder(folder_id)
        
        if result.get("success"):
            config_result = self._lora_config_manager.get_scan_paths()
            scan_paths = config_result.get("paths", [])
            scanner.sync_folder_structure(scan_paths)
        
        return result
    
    def lora_upload_preview(self, model_id: str, file_data: list, filename: str):
        """
        上传模型预览图/视频（支持多个，追加模式）
        
        Args:
            model_id: 模型 ID
            file_data: 文件数据（列表形式，会被转换为 bytes）
            filename: 原始文件名
            
        Returns:
            dict: {
                "success": bool,
                "message": str,
                "filename": str (可选)
            }
        """
        from backend.src.core.lora import LoraScanner
        
        scanner = LoraScanner()
        file_bytes = bytes(file_data)
        return scanner.save_preview(model_id, file_bytes, filename)
    
    def lora_get_preview_list(self, model_id: str):
        """
        获取模型预览图文件列表
        
        Args:
            model_id: 模型 ID
            
        Returns:
            dict: {
                "success": bool,
                "files": list[str]
            }
        """
        from backend.src.core.lora import LoraScanner
        
        scanner = LoraScanner()
        files = scanner.get_preview_list(model_id)
        return {
            "success": True,
            "files": files
        }
    
    def lora_delete_preview(self, model_id: str, filename: str = None):
        """
        删除模型预览图
        
        Args:
            model_id: 模型 ID
            filename: 文件名（可选，不指定则删除全部）
            
        Returns:
            dict: {
                "success": bool,
                "message": str
            }
        """
        from backend.src.core.lora import LoraScanner
        
        scanner = LoraScanner()
        return scanner.delete_preview(model_id, filename)

    def lora_batch_export_previews(self, model_ids: list):
        """
        批量导出预览图到模型文件所在目录

        Args:
            model_ids: 模型 ID 列表

        Returns:
            dict: {
                "success": bool,
                "exported_count": int,
                "skipped_count": int,
                "failed_count": int,
                "details": list
            }
        """
        try:
            from backend.src.core.lora import LoraScanner

            scanner = LoraScanner()
            return scanner.batch_export_previews(model_ids)
        except Exception as e:
            logger.error(f"[API] 批量导出预览图异常: {e}")
            return {
                "success": False,
                "exported_count": 0,
                "skipped_count": 0,
                "failed_count": 0,
                "details": [],
                "message": f"批量导出失败: {str(e)}"
            }

    # ========== 提示词库 API ==========

    def prompt_get_all(self):
        """
        获取所有提示词
        
        Returns:
            dict: {
                "success": bool,
                "prompts": list[dict]
            }
        """
        return self._prompt_library_controller.prompt_get_all()
    
    def prompt_create(
        self,
        name: str,
        positive_prompt: str,
        category_id: str = "",
        negative_prompt: str = "",
        preview_image: str = "",
        remark: str = "",
        tags: list = None
    ):
        """
        创建新提示词
        
        Args:
            name: 配方名称
            positive_prompt: 正向提示词
            category_id: 所属分类ID
            negative_prompt: 反向提示词
            preview_image: 预览图路径
            remark: 使用备注
            tags: 标签数组
            
        Returns:
            dict: {
                "success": bool,
                "prompt": dict | None,
                "error_message": str (可选)
            }
        """
        return self._prompt_library_controller.prompt_create(
            name, positive_prompt, category_id, negative_prompt, preview_image, remark, tags
        )
    
    def prompt_update(
        self,
        prompt_id: str,
        name: str = None,
        positive_prompt: str = None,
        category_id: str = None,
        negative_prompt: str = None,
        preview_image: str = None,
        remark: str = None,
        tags: list = None
    ):
        """
        更新提示词
        
        Args:
            prompt_id: 提示词ID
            其他参数为可选更新字段
            
        Returns:
            dict: {
                "success": bool,
                "error_message": str (可选)
            }
        """
        return self._prompt_library_controller.prompt_update(
            prompt_id, name, positive_prompt, category_id, negative_prompt, preview_image, remark, tags
        )
    
    def prompt_delete(self, prompt_id: str):
        """
        删除提示词
        
        Args:
            prompt_id: 提示词ID
            
        Returns:
            dict: {
                "success": bool,
                "error_message": str (可选)
            }
        """
        return self._prompt_library_controller.prompt_delete(prompt_id)
    
    def prompt_batch_delete(self, prompt_ids: list):
        """
        批量删除提示词
        
        Args:
            prompt_ids: 提示词ID列表
            
        Returns:
            dict: {
                "success": bool,
                "deleted_count": int
            }
        """
        return self._prompt_library_controller.prompt_batch_delete(prompt_ids)
    
    def prompt_batch_move(self, prompt_ids: list, category_id: str):
        """
        批量移动提示词到指定分类
        
        Args:
            prompt_ids: 提示词ID列表
            category_id: 目标分类ID
            
        Returns:
            dict: {
                "success": bool,
                "moved_count": int
            }
        """
        return self._prompt_library_controller.prompt_batch_move(prompt_ids, category_id)
    
    def prompt_toggle_favorite(self, prompt_id: str):
        """
        切换提示词收藏状态
        
        Args:
            prompt_id: 提示词ID
            
        Returns:
            dict: {
                "success": bool,
                "is_favorite": bool
            }
        """
        return self._prompt_library_controller.prompt_toggle_favorite(prompt_id)
    
    def prompt_upload_image(self, file_data: list, filename: str = None):
        """
        上传预览图片
        
        Args:
            file_data: Base64 编码的图片数据（列表形式）
            filename: 原始文件名
            
        Returns:
            dict: {
                "success": bool,
                "image_path": str,
                "error_message": str (可选)
            }
        """
        # 将列表转换为字符串
        file_data_str = ''.join(chr(b) for b in file_data) if isinstance(file_data, list) else file_data
        return self._prompt_library_controller.prompt_upload_image(file_data_str, filename)
    
    def category_get_all(self):
        """
        获取所有分类
        
        Returns:
            dict: {
                "success": bool,
                "categories": list[dict]
            }
        """
        return self._prompt_library_controller.category_get_all()
    
    def category_create(self, name: str, icon: str = "folder", parent_id: str = None):
        """
        创建新分类
        
        Args:
            name: 分类名称
            icon: 图标名称
            parent_id: 父分类ID
            
        Returns:
            dict: {
                "success": bool,
                "category": dict | None,
                "error_message": str (可选)
            }
        """
        return self._prompt_library_controller.category_create(name, icon, parent_id)
    
    def category_update(self, category_id: str, name: str = None, icon: str = None, sort_order: int = None):
        """
        更新分类
        
        Args:
            category_id: 分类ID
            其他参数为可选更新字段
            
        Returns:
            dict: {
                "success": bool,
                "error_message": str (可选)
            }
        """
        return self._prompt_library_controller.category_update(category_id, name, icon, sort_order)
    
    def category_delete(self, category_id: str):
        """
        删除分类
        
        Args:
            category_id: 分类ID
            
        Returns:
            dict: {
                "success": bool,
                "error_message": str (可选)
            }
        """
        return self._prompt_library_controller.category_delete(category_id)
    
    def prompt_export(self, prompt_ids: list = None):
        """
        导出提示词
        
        Args:
            prompt_ids: 要导出的提示词ID列表，为空则导出全部
            
        Returns:
            dict: {
                "success": bool,
                "data": dict
            }
        """
        return self._prompt_library_controller.prompt_export(prompt_ids)
    
    def prompt_import(self, data: dict, merge: bool = True):
        """
        导入提示词
        
        Args:
            data: 导入的数据
            merge: 是否合并模式
            
        Returns:
            dict: {
                "success": bool,
                "imported_count": int,
                "message": str
            }
        """
        return self._prompt_library_controller.prompt_import(data, merge)
    
    # ==================== 工作流管理 API ====================
    
    def get_workflows(self) -> dict:
        """
        获取工作流列表
        
        Returns:
            dict: {"success": bool, "workflows": list}
        """
        try:
            workflows = self._workflow_controller.get_workflows()
            return {"success": True, "workflows": workflows}
        except Exception as e:
            logger.error(f"获取工作流列表失败：{e}")
            return {"success": False, "error": str(e)}
    
    def get_workflow(self, filename: str) -> dict:
        """
        获取单个工作流详情
        
        Args:
            filename: 工作流文件名（相对路径）
            
        Returns:
            dict: {"success": bool, "workflow": dict}
        """
        try:
            workflow = self._workflow_controller.get_workflow(filename)
            if workflow:
                return {"success": True, "workflow": workflow}
            else:
                return {"success": False, "error": f"工作流不存在：{filename}"}
        except Exception as e:
            logger.error(f"获取工作流失败：{e}")
            return {"success": False, "error": str(e)}
    
    def delete_workflow(self, filename: str) -> dict:
        """
        删除工作流
        
        Args:
            filename: 工作流文件名（相对路径）
            
        Returns:
            dict: {"success": bool, "error": str}
        """
        try:
            result = self._workflow_controller.delete_workflow(filename)
            return {"success": True} if result else {"success": False, "error": "删除失败"}
        except Exception as e:
            logger.error(f"删除工作流失败：{e}")
            return {"success": False, "error": str(e)}
    
    def import_workflow(self, file_content: str, filename: str = None) -> dict:
        """
        导入工作流
        
        Args:
            file_content: 工作流 JSON 内容
            filename: 可选的文件名
            
        Returns:
            dict: {"success": bool, "workflow": dict, "error": str}
        """
        try:
            workflow = self._workflow_controller.import_workflow(file_content, filename)
            return {"success": True, "workflow": workflow} if workflow else {"success": False, "error": "导入失败"}
        except Exception as e:
            logger.error(f"导入工作流失败：{e}")
            return {"success": False, "error": str(e)}
    
    def export_workflow(self, filename: str) -> dict:
        """
        导出工作流
        
        Args:
            filename: 工作流文件名（相对路径）
            
        Returns:
            dict: {"success": bool, "content": str, "filename": str, "error": str}
        """
        try:
            content = self._workflow_controller.export_workflow(filename)
            if content:
                return {"success": True, "content": content, "filename": filename}
            else:
                return {"success": False, "error": "导出失败"}
        except Exception as e:
            logger.error(f"导出工作流失败：{e}")
            return {"success": False, "error": str(e)}
    
    def update_workflow_info(self, filename: str, info: dict) -> dict:
        """
        更新工作流信息
        
        Args:
            filename: 工作流文件名（相对路径）
            info: 更新信息（description, tags）
            
        Returns:
            dict: {"success": bool, "workflow": dict, "error": str}
        """
        try:
            # controller 返回 {"success": True, "workflow": dict}，直接透传即可
            result = self._workflow_controller.update_workflow_info(filename, info)
            return result if result else {"success": False, "error": "更新失败"}
        except Exception as e:
            logger.error(f"更新工作流信息失败：{e}")
            return {"success": False, "error": str(e)}
    
    def toggle_favorite(self, filename: str) -> dict:
        """
        切换收藏状态
        
        Args:
            filename: 工作流文件名（相对路径）
            
        Returns:
            dict: {"success": bool, "isFavorite": bool, "error": str}
        """
        try:
            is_favorite = self._workflow_controller.toggle_favorite(filename)
            return {"success": True, "isFavorite": is_favorite}
        except Exception as e:
            logger.error(f"切换收藏状态失败：{e}")
            return {"success": False, "error": str(e)}
    
    def get_workflow_folders(self) -> dict:
        """
        获取文件夹列表
        
        Returns:
            dict: {"success": bool, "folders": list}
        """
        try:
            folders = self._workflow_controller.get_folders()
            return {"success": True, "folders": folders}
        except Exception as e:
            logger.error(f"获取文件夹列表失败：{e}")
            return {"success": False, "error": str(e)}
    
    def create_workflow_folder(self, name: str, parent_id: str = None) -> dict:
        """
        创建文件夹
        
        Args:
            name: 文件夹名称
            parent_id: 父文件夹 ID
            
        Returns:
            dict: {"success": bool, "folder": dict, "error": str}
        """
        try:
            result = self._workflow_controller.create_folder(name, parent_id)
            if result.get("success"):
                return {"success": True, "folder": result.get("folder")}
            return {"success": False, "error": result.get("error", "创建失败")}
        except Exception as e:
            logger.error(f"创建文件夹失败：{e}")
            return {"success": False, "error": str(e)}
    
    def update_workflow_folder(self, folder_id: str, updates: dict) -> dict:
        """
        更新文件夹
        
        Args:
            folder_id: 文件夹 ID
            updates: 更新内容
            
        Returns:
            dict: {"success": bool, "folder": dict, "error": str}
        """
        try:
            result = self._workflow_controller.update_folder(folder_id, updates)
            if result.get("success"):
                return {"success": True, "folder": result.get("folder")}
            return {"success": False, "error": result.get("error", "更新失败")}
        except Exception as e:
            logger.error(f"更新文件夹失败：{e}")
            return {"success": False, "error": str(e)}
    
    def delete_workflow_folder(self, folder_id: str) -> dict:
        """
        删除文件夹
        
        Args:
            folder_id: 文件夹 ID
            
        Returns:
            dict: {"success": bool, "error": str}
        """
        try:
            result = self._workflow_controller.delete_folder(folder_id)
            if result.get("success"):
                return {"success": True}
            return {"success": False, "error": result.get("error", "删除失败")}
        except Exception as e:
            logger.error(f"删除文件夹失败：{e}")
            return {"success": False, "error": str(e)}
    
    def move_workflow_to_folder(self, filename: str, folder_id: str = None) -> dict:
        """
        移动工作流到文件夹
        
        Args:
            filename: 工作流文件名（相对路径）
            folder_id: 目标文件夹 ID（None 表示移到根目录）
            
        Returns:
            dict: {"success": bool, "workflow": dict, "error": str}
        """
        try:
            result = self._workflow_controller.move_to_folder(filename, folder_id)
            if result.get("success"):
                return {"success": True, "workflow": result.get("workflow")}
            return {"success": False, "error": result.get("error", "移动失败")}
        except Exception as e:
            logger.error(f"移动工作流失败：{e}")
            return {"success": False, "error": str(e)}
    
    def batch_move_workflows_to_folder(self, filenames: list, folder_id: str = None) -> dict:
        """
        批量移动工作流到文件夹
        
        Args:
            filenames: 工作流文件名列表（相对路径）
            folder_id: 目标文件夹 ID（None 表示移到根目录）
            
        Returns:
            dict: {"success": bool, "moved_count": int, "errors": list}
        """
        try:
            result = self._workflow_controller.batch_move_to_folder(filenames, folder_id)
            return result
        except Exception as e:
            logger.error(f"批量移动工作流失败：{e}")
            return {"success": False, "error": str(e), "moved_count": 0, "errors": []}
    
    def batch_toggle_workflow_favorite(self, filenames: list) -> dict:
        """
        批量切换工作流收藏状态
        
        Args:
            filenames: 工作流文件名列表
            
        Returns:
            dict: {"success": bool, "results": dict}
        """
        try:
            result = self._workflow_controller.batch_toggle_favorite(filenames)
            return result
        except Exception as e:
            logger.error(f"批量切换收藏失败：{e}")
            return {"success": False, "error": str(e), "results": {}}
    
    def batch_delete_workflows(self, filenames: list) -> dict:
        """
        批量删除工作流
        
        Args:
            filenames: 工作流文件名列表（相对路径）
            
        Returns:
            dict: {"success": bool, "deleted_count": int, "errors": list}
        """
        try:
            result = self._workflow_controller.batch_delete_workflows(filenames)
            return result
        except Exception as e:
            logger.error(f"批量删除工作流失败：{e}")
            return {"success": False, "error": str(e), "deleted_count": 0, "errors": []}
    
    def check_plugins_status(self, github_urls: list) -> dict:
        """
        检查插件安装状态
        
        Args:
            github_urls: 插件的 GitHub URL 列表
            
        Returns:
            dict: {"success": bool, "status": dict, "error": str}
        """
        try:
            result = self._workflow_controller.check_plugins_status(github_urls)
            # workflow_controller 已经返回了正确格式，直接返回
            return result
        except Exception as e:
            logger.error(f"检查插件状态失败：{e}")
            return {"success": False, "error": str(e)}
    
    def upload_workflow_preview(self, filename: str, image_data: str) -> dict:
        """
        上传预览图
        
        Args:
            filename: 工作流文件名（相对路径）
            image_data: Base64 编码的图片数据
            
        Returns:
            dict: {"success": bool, "previewPath": str, "error": str}
        """
        try:
            result = self._workflow_controller.upload_preview(filename, image_data)
            return result
        except Exception as e:
            logger.error(f"上传预览图失败：{e}")
            return {"success": False, "error": str(e)}
    
    def delete_workflow_preview(self, filename: str, preview_index: int) -> dict:
        """
        删除预览图
        
        Args:
            filename: 工作流文件名（相对路径）
            preview_index: 预览图索引
            
        Returns:
            dict: {"success": bool, "error": str}
        """
        try:
            result = self._workflow_controller.delete_preview(filename, preview_index)
            return result
        except Exception as e:
            logger.error(f"删除预览图失败：{e}")
            return {"success": False, "error": str(e)}
    
    def initialize_node_type_map_async(self) -> dict:
        """
        异步初始化节点类型映射表
        
        在后台线程中初始化，不阻塞主线程。
        如果缓存有效，不会重复请求远程数据。
        
        Returns:
            dict: {"success": bool, "message": str, "error": str}
        """
        try:
            import threading
            
            def _init_in_background():
                try:
                    from backend.src.utils.node_mapper import node_mapper
                    
                    if not node_mapper._plugin_info:
                        node_mapper.initialize()
                    
                    # 如果有当前环境，扫描本地插件
                    if self._workflow_controller and self._workflow_controller._environment_manager:
                        current_env = self._workflow_controller._environment_manager.get_current_environment()
                        if current_env and current_env.path:
                            from pathlib import Path
                            custom_nodes_path = Path(current_env.path) / "custom_nodes"
                            if custom_nodes_path.exists():
                                node_mapper.scan_local_plugins(str(custom_nodes_path))
                                logger.info(f"[initialize_node_type_map_async] 扫描本地插件完成: {len(node_mapper._local_plugins)} 个")
                    
                    logger.info("[initialize_node_type_map_async] 后台初始化完成")
                    
                except Exception as e:
                    logger.error(f"[initialize_node_type_map_async] 后台初始化失败: {e}")
            
            thread = threading.Thread(target=_init_in_background, daemon=True)
            thread.start()
            
            return {"success": True, "message": "初始化已在后台启动"}
            
        except Exception as e:
            logger.error(f"启动后台初始化失败: {e}")
            return {"success": False, "error": str(e)}
    
    def get_node_type_map(self) -> dict:
        """
        获取节点类型到插件的映射表
        
        用于前端工作流解析时识别节点所属插件。
        本方法只返回缓存数据，不扫描本地插件。
        本地插件扫描由 initialize_node_type_map_async 在后台完成。
        
        Returns:
            dict: {
                "success": bool,
                "data": {
                    "preemption_map": {node_type: plugin_id},
                    "rext_map": {node_type: [plugin_ids]},
                    "patterns": [(pattern, plugin_id)],
                    "plugin_info": {plugin_id: {name, github_url, node_count}},
                    "local_plugins": {github_url: {name, github_url, enabled}},
                    "timestamp": float,
                    "stats": {preemption_count, rext_count, pattern_count, plugin_count, local_plugin_count}
                },
                "error": str
            }
        """
        try:
            from backend.src.utils.node_mapper import node_mapper
            
            if not node_mapper._plugin_info:
                node_mapper.initialize()
            
            data = node_mapper.get_cache_data()
            return {"success": True, "data": data}
            
        except Exception as e:
            logger.error(f"获取节点类型映射表失败：{e}")
            return {"success": False, "error": str(e)}
    
    def refresh_node_type_map(self) -> dict:
        """
        刷新节点类型到插件的映射表
        
        从远程获取最新的节点映射数据并更新缓存
        
        Returns:
            dict: {
                "success": bool,
                "data": {...},
                "error": str
            }
        """
        try:
            from backend.src.utils.node_mapper import node_mapper
            
            success = node_mapper.refresh()
            if success:
                data = node_mapper.get_cache_data()
                return {"success": True, "data": data}
            else:
                return {"success": False, "error": "刷新失败"}
                
        except Exception as e:
            logger.error(f"刷新节点类型映射表失败：{e}")
            return {"success": False, "error": str(e)}
    
    def scan_local_nodes(self, force: bool = False) -> dict:
        """
        扫描本地节点
        
        扫描当前 ComfyUI 环境的 custom_nodes 目录，识别所有 V1/V3/前端节点
        
        Args:
            force: 是否强制重新扫描（忽略缓存）
            
        Returns:
            dict: {
                "success": bool,
                "pluginCount": int,
                "nodeCount": int,
                "v1Count": int,
                "v3Count": int,
                "frontendCount": int,
                "elapsedSeconds": float,
                "error": str
            }
        """
        return self._workflow_controller.scan_local_nodes(force)
    
    def get_local_node_map(self) -> dict:
        """
        获取本地节点映射表
        
        返回本地扫描生成的节点到插件的映射表
        
        Returns:
            dict: {
                "success": bool,
                "data": {
                    "version": int,
                    "timestamp": float,
                    "comfyuiPath": str,
                    "nodes": {node_type: {nodeType, githubUrl, pluginName}},
                    "plugins": {github_url: {githubUrl, v1Count, v3Count, frontendCount}}
                },
                "error": str
            }
        """
        return self._workflow_controller.get_local_node_map()
    
    def get_local_scan_status(self) -> dict:
        """
        获取本地扫描状态
        
        Returns:
            dict: {
                "success": bool,
                "initialized": bool,
                "hasCache": bool,
                "needsRescan": bool,
                "comfyuiPath": str,
                "error": str
            }
        """
        return self._workflow_controller.get_local_scan_status()

    def gallery_get_assets(self) -> dict:
        """获取资产列表"""
        return self._gallery_controller.gallery_get_assets()

    def gallery_get_asset(self, asset_id: str) -> dict:
        """获取单个资产详情"""
        return self._gallery_controller.gallery_get_asset(asset_id)

    def gallery_delete_asset(self, asset_id: str) -> dict:
        """删除资产（移动到系统回收站）"""
        return self._gallery_controller.gallery_delete_asset(asset_id)

    def gallery_batch_delete(self, asset_ids: list[str]) -> dict:
        """批量删除资产"""
        return self._gallery_controller.gallery_batch_delete(asset_ids)

    def gallery_toggle_favorite(self, asset_id: str) -> dict:
        """切换收藏状态"""
        return self._gallery_controller.gallery_toggle_favorite(asset_id)

    def gallery_batch_favorite(self, asset_ids: list[str], favorite: bool) -> dict:
        """批量设置收藏状态"""
        return self._gallery_controller.gallery_batch_favorite(asset_ids, favorite)

    def gallery_get_settings(self) -> dict:
        """获取设置"""
        return self._gallery_controller.gallery_get_settings()

    def gallery_save_settings(self, library_path: str = None) -> dict:
        """保存设置"""
        return self._gallery_controller.gallery_save_settings(library_path)

    def gallery_scan(self, library_path: str = None) -> dict:
        """扫描资产库目录"""
        return self._gallery_controller.gallery_scan(library_path)

    def gallery_incremental_scan(self, library_path: str = None) -> dict:
        """增量扫描资产库目录"""
        return self._gallery_controller.gallery_incremental_scan(library_path)

    def gallery_get_workflow(self, asset_id: str) -> dict:
        """获取资产的工作流 JSON"""
        return self._gallery_controller.gallery_get_workflow(asset_id)

    def gallery_export_workflow(self, asset_id: str) -> dict:
        """
        导出工作流到工作流库
        
        导出到当前环境的工作流库目录（ComfyUI/user/default/workflows）
        """
        try:
            result = self._gallery_controller.gallery_get_workflow(asset_id)
            if not result.get("success"):
                return result
            
            workflow = result.get("workflow")
            if not workflow:
                return {"success": False, "error_message": "工作流数据为空"}
            
            from backend.src.gallery.storage import gallery_storage
            asset = gallery_storage.get_asset_by_id(asset_id)
            if not asset:
                return {"success": False, "error_message": "资产不存在"}
            
            import json
            workflow_content = json.dumps(workflow, ensure_ascii=False, indent=2)
            
            from pathlib import Path
            filename = f"{Path(asset.filename).stem}.json"
            
            import_result = self._workflow_controller.import_workflow(workflow_content, filename)
            
            if import_result.get("success"):
                workflow_info = import_result.get("workflow", {})
                return {
                    "success": True,
                    "workflow_path": workflow_info.get("id"),
                    "workflow_name": workflow_info.get("name")
                }
            else:
                return {
                    "success": False,
                    "error_message": import_result.get("error", "导入工作流失败")
                }
                
        except Exception as e:
            logger.error(f"[API] 导出工作流到工作流库失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_export_workflow_to_path(self, asset_id: str, save_path: str) -> dict:
        """导出工作流到指定路径"""
        return self._gallery_controller.gallery_export_workflow_to_path(asset_id, save_path)

    def gallery_export_to_prompt_library(self, asset_id: str) -> dict:
        """导出资产到提示词库"""
        return self._gallery_controller.gallery_export_to_prompt_library(asset_id)

    def gallery_open_location(self, asset_id: str) -> dict:
        """打开文件所在位置"""
        return self._gallery_controller.gallery_open_location(asset_id)

    def gallery_move_to_category(self, asset_ids: list[str], category_id: str = None) -> dict:
        """批量移动资产到分类"""
        return self._gallery_controller.gallery_move_to_category(asset_ids, category_id)

    def gallery_import(self, paths: list[str]) -> dict:
        """导入资产（文件/文件夹）"""
        return self._gallery_controller.gallery_import(paths)

    def gallery_export_zip(self, asset_ids: list[str]) -> dict:
        """导出选中资产为 ZIP"""
        return self._gallery_controller.gallery_export_zip(asset_ids)

    def gallery_get_categories(self) -> dict:
        """获取分类列表"""
        return self._gallery_controller.gallery_get_categories()

    def gallery_create_category(self, name: str, parent_id: str = None) -> dict:
        """创建分类"""
        return self._gallery_controller.gallery_create_category(name, parent_id)

    def gallery_update_category(self, category_id: str, name: str = None) -> dict:
        """更新分类"""
        return self._gallery_controller.gallery_update_category(category_id, name)

    def gallery_delete_category(self, category_id: str, cascade: bool = True) -> dict:
        """删除分类"""
        return self._gallery_controller.gallery_delete_category(category_id, cascade)

    def gallery_get_thumbnail(self, asset_id: str):
        """获取资产缩略图（返回 Flask Response）"""
        return self._gallery_controller.gallery_get_thumbnail(asset_id)

    def gallery_get_asset_file(self, asset_id: str):
        """获取资产原图文件（返回 Flask Response）"""
        return self._gallery_controller.gallery_get_asset_file(asset_id)

    def gallery_get_nsfw_status(self) -> dict:
        """获取 NSFW 分级状态"""
        return self._gallery_controller.gallery_get_nsfw_status()

    def gallery_set_nsfw_enabled(self, enabled: bool) -> dict:
        """设置 NSFW 自动分级开关"""
        return self._gallery_controller.gallery_set_nsfw_enabled(enabled)

    def gallery_set_nsfw_threshold(self, threshold: float) -> dict:
        """设置 NSFW 分级阈值"""
        return self._gallery_controller.gallery_set_nsfw_threshold(threshold)

    def gallery_set_nsfw_auto_blur(self, enabled: bool) -> dict:
        """设置 NSFW 自动模糊开关"""
        return self._gallery_controller.gallery_set_nsfw_auto_blur(enabled)

    def gallery_classify_all_images(self) -> dict:
        """对所有图片进行 NSFW 分级"""
        return self._gallery_controller.gallery_classify_all_images()

    def gallery_pause_nsfw_scan(self) -> dict:
        """暂停 NSFW 扫描"""
        return self._gallery_controller.gallery_pause_nsfw_scan()

    def gallery_resume_nsfw_scan(self) -> dict:
        """恢复 NSFW 扫描"""
        return self._gallery_controller.gallery_resume_nsfw_scan()

    def gallery_cancel_nsfw_scan(self) -> dict:
        """取消 NSFW 扫描"""
        return self._gallery_controller.gallery_cancel_nsfw_scan()

    def gallery_start_background_scan(self, library_path: str = None) -> dict:
        """启动后台扫描"""
        return self._gallery_controller.gallery_start_background_scan(library_path)

    def gallery_get_scan_status(self) -> dict:
        """获取扫描状态"""
        return self._gallery_controller.gallery_get_scan_status()

    def gallery_stop_scan(self) -> dict:
        """停止扫描"""
        return self._gallery_controller.gallery_stop_scan()

    def gallery_update_preview_blurred(self, asset_id: str, blurred: bool) -> dict:
        """更新资产的模糊预览状态"""
        return self._gallery_controller.gallery_update_preview_blurred(asset_id, blurred)

    def gallery_update_asset_info(
        self,
        asset_id: str,
        filename: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        rating: Optional[int] = None
    ) -> dict:
        """更新资产的基本信息（文件名、备注、标签、评分）"""
        return self._gallery_controller.gallery_update_asset_info(asset_id, filename, description, tags, rating)

    def gallery_push_image_to_comfyui(self, asset_id: str) -> dict:
        """推送图片到 ComfyUI 的 LoadImage 节点"""
        return self._gallery_controller.gallery_push_image_to_comfyui(asset_id)
