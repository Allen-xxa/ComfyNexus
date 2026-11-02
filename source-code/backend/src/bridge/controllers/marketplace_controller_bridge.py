"""
插件市场控制器桥接层

连接前端和后端的插件市场控制器，提供统一的 API 接口。
"""

from typing import Dict, Optional
from pathlib import Path

from backend.src.core.marketplace.marketplace_controller import MarketplaceController
from backend.src.utils.logger import app_logger as logger


class MarketplaceControllerBridge:
    """
    插件市场控制器桥接层
    
    职责：
    1. 初始化 MarketplaceController
    2. 管理窗口引用
    3. 提供前端 API 方法
    4. 统一响应格式
    """
    
    def __init__(self, environment_manager, settings_manager=None):
        """
        初始化桥接器
        
        Args:
            environment_manager: 环境管理器实例
            settings_manager: 设置管理器实例（用于获取 GitHub API Token）
        """
        self.environment_manager = environment_manager
        self._settings_manager = settings_manager
        self._window = None
        
        # 初始化插件市场控制器
        self.controller = MarketplaceController(
            environment_manager=environment_manager,
            settings_manager=settings_manager
        )
        
        logger.info("插件市场控制器桥接层已初始化")
    
    def set_window(self, window):
        """
        设置窗口引用
        
        Args:
            window: pywebview 窗口对象
        """
        self._window = window
    
    # ==================== 前端 API 方法 ====================
    
    def get_plugins(self, use_cache: bool = True) -> Dict:
        """
        获取插件列表
        
        Args:
            use_cache: 是否使用缓存
            
        Returns:
            dict: {
                'success': bool,
                'plugins': [Plugin.to_dict(), ...],
                'total': int,
                'error': str (如果失败)
            }
        """
        try:
            logger.info(f"[Bridge] 获取插件列表，use_cache={use_cache}")
            result = self.controller.get_plugins(use_cache=use_cache)
            return result
        except Exception as e:
            logger.error(f"[Bridge] 获取插件列表失败: {e}")
            logger.exception("详细错误信息")
            return {
                'success': False,
                'plugins': [],
                'total': 0,
                'error': str(e)
            }
    
    def get_recommended_plugins(self, use_cache: bool = True) -> Dict:
        """
        获取推荐插件列表
        
        Args:
            use_cache: 是否使用缓存
            
        Returns:
            dict: {
                'success': bool,
                'plugins': [Plugin.to_dict(), ...],
                'total': int,
                'error': str (如果失败)
            }
        """
        try:
            logger.info(f"[Bridge] 获取推荐插件列表，use_cache={use_cache}")
            result = self.controller.get_recommended_plugins(use_cache=use_cache)
            return result
        except Exception as e:
            logger.error(f"[Bridge] 获取推荐插件列表失败: {e}")
            logger.exception("详细错误信息")
            return {
                'success': False,
                'plugins': [],
                'total': 0,
                'error': str(e)
            }
    
    def search_plugins(self, keyword: str) -> Dict:
        """
        搜索插件
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            dict: {
                'success': bool,
                'plugins': [Plugin.to_dict(), ...],
                'total': int,
                'keyword': str,
                'error': str (如果失败)
            }
        """
        try:
            logger.info(f"[Bridge] 搜索插件，关键词: {keyword}")
            result = self.controller.search_plugins(keyword=keyword)
            return result
        except Exception as e:
            logger.error(f"[Bridge] 搜索插件失败: {e}")
            logger.exception("详细错误信息")
            return {
                'success': False,
                'plugins': [],
                'total': 0,
                'keyword': keyword,
                'error': str(e)
            }
    
    def refresh_plugins(self) -> Dict:
        """
        刷新插件列表（拉取最新数据，失败时保留本地缓存）
        
        Returns:
            dict: {
                'success': bool,
                'message': str,
                'plugins': [Plugin.to_dict(), ...],
                'total': int,
                'source': 'cache' | 'network',
                'stale': bool,
                'cached_at': float,
                'warning': str (可选),
                'error': str (如果失败)
            }
        """
        try:
            logger.info("[Bridge] 刷新插件列表")
            result = self.controller.refresh_plugins()
            return result
        except Exception as e:
            logger.error(f"[Bridge] 刷新插件列表失败: {e}")
            logger.exception("详细错误信息")
            return {
                'success': False,
                'plugins': [],
                'total': 0,
                'error': str(e)
            }
    
    def install_plugin(
        self,
        github_url: str,
        auto_install_deps: bool = True
    ) -> Dict:
        """
        安装插件
        
        Args:
            github_url: GitHub 仓库地址
            auto_install_deps: 是否自动安装依赖
            
        Returns:
            dict: {
                'success': bool,
                'task_id': str,
                'message': str,
                'log_path': str,
                'error': str (如果失败),
                'partial_success': bool (部分成功标志)
            }
        """
        try:
            logger.info(f"[Bridge] 安装插件: {github_url}, auto_install_deps={auto_install_deps}")
            
            # 定义进度回调函数（如果需要实时更新前端）
            def progress_callback(progress_data: Dict):
                """
                进度回调函数
                
                Args:
                    progress_data: 进度数据字典
                """
                # 如果有窗口引用，可以通过 evaluate_js 发送事件到前端
                if self._window:
                    try:
                        # 将进度数据发送到前端
                        # 前端可以监听这个事件来更新 UI
                        import json
                        js_code = f"window.dispatchEvent(new CustomEvent('plugin-install-progress', {{detail: {json.dumps(progress_data)}}}));"
                        self._window.evaluate_js(js_code)
                    except Exception as e:
                        logger.warning(f"[Bridge] 发送进度事件失败: {e}")
            
            # 调用控制器安装插件
            result = self.controller.install_plugin(
                github_url=github_url,
                auto_install_deps=auto_install_deps,
                progress_callback=progress_callback
            )
            
            # 添加详细日志
            logger.info(f"[Bridge] 安装插件返回结果: success={result.get('success')}, task_id={result.get('task_id')}")
            logger.info(f"[Bridge] 完整返回结果: {result}")
            
            return result
        except Exception as e:
            logger.error(f"[Bridge] 安装插件失败: {e}")
            logger.exception("详细错误信息")
            return {
                'success': False,
                'error': str(e)
            }
    
    def check_dependencies(self, github_url: str) -> Dict:
        """
        检查插件依赖冲突
        
        Args:
            github_url: GitHub 仓库地址
            
        Returns:
            dict: {
                'success': bool,
                'has_conflicts': bool,
                'conflicts': [DependencyConflict.to_dict(), ...],
                'error': str (如果失败)
            }
        """
        try:
            logger.info(f"[Bridge] 检查依赖冲突: {github_url}")
            result = self.controller.check_dependencies(github_url=github_url)
            return result
        except Exception as e:
            logger.error(f"[Bridge] 检查依赖冲突失败: {e}")
            logger.exception("详细错误信息")
            return {
                'success': False,
                'has_conflicts': False,
                'conflicts': [],
                'error': str(e)
            }
    
    def get_install_progress(self, task_id: str) -> Dict:
        """
        获取安装进度
        
        Args:
            task_id: 任务 ID
            
        Returns:
            dict: {
                'success': bool,
                'progress': dict,  # 任务进度信息
                'error': str (如果失败)
            }
        """
        try:
            logger.debug(f"[Bridge] 获取安装进度: {task_id}")
            result = self.controller.get_install_progress(task_id=task_id)
            return result
        except Exception as e:
            logger.error(f"[Bridge] 获取安装进度失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def cancel_installation(self, task_id: str) -> Dict:
        """
        取消正在进行的安装任务
        
        Args:
            task_id: 任务 ID
            
        Returns:
            dict: {
                'success': bool,
                'message': str,
                'error': str (如果失败)
            }
        """
        try:
            logger.info(f"[Bridge] 取消安装任务: {task_id}")
            result = self.controller.cancel_installation(task_id=task_id)
            return result
        except Exception as e:
            logger.error(f"[Bridge] 取消安装任务失败: {e}")
            logger.exception("详细错误信息")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_installed_plugins_status(self) -> Dict:
        """
        获取当前环境下已安装插件的状态
        
        Returns:
            dict: {
                'success': bool,
                'installed_plugins': [plugin_name1, plugin_name2, ...],
                'error': str (如果失败)
            }
        """
        try:
            logger.info("[Bridge] 获取已安装插件状态")
            result = self.controller.get_installed_plugins_status()
            return result
        except Exception as e:
            logger.error(f"[Bridge] 获取已安装插件状态失败: {e}")
            logger.exception("详细错误信息")
            return {
                'success': False,
                'installed_plugins': [],
                'error': str(e)
            }
