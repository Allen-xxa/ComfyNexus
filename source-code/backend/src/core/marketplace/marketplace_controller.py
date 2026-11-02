"""
插件市场控制器

核心控制器，整合所有插件市场功能模块：
- 插件数据获取（PluginDataFetcher）
- 缓存管理（CacheManager）
- 安装引擎（InstallationEngine）
- 依赖检测（DependencyChecker）

提供统一的 API 接口供桥接层调用。
"""

import os
import platform
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Callable

from .models import Plugin, PluginMarketplaceConfig
from .data_fetcher import PluginDataFetcher
from .cache_manager import CacheManager
from .installation_engine import InstallationEngine
from .dependency_checker import DependencyChecker
from .logger import marketplace_logger as logger
from .constants import (
    get_cache_dir,
    get_config_dir,
    get_recommended_plugins_file,
    ERROR_ENV_NOT_CONFIGURED,
    ERROR_INVALID_GITHUB_URL,
    ERROR_NETWORK_FAILED,
    ERROR_PATH_TRAVERSAL,
    SUCCESS_PLUGIN_INSTALLED,
    SUCCESS_CACHE_CLEARED
)


class MarketplaceController:
    """
    插件市场核心控制器
    
    职责：
    1. 协调各个功能模块
    2. 管理插件列表和推荐列表
    3. 处理插件安装流程
    4. 检查安装状态
    5. 提供统一的错误处理
    """
    
    def __init__(
        self,
        environment_manager,
        cache_dir: Optional[Path] = None,
        config_dir: Optional[Path] = None,
        settings_manager=None
    ):
        """
        初始化插件市场控制器
        
        Args:
            environment_manager: 环境管理器实例
            cache_dir: 缓存目录路径（可选，默认使用标准路径）
            config_dir: 配置目录路径（可选，默认使用标准路径）
            settings_manager: 设置管理器实例（用于获取 GitHub API Token）
        """
        self.env_manager = environment_manager
        self._settings_manager = settings_manager
        
        # 使用私有属性存储 Path 对象，避免 pywebview 序列化错误
        self._cache_dir = cache_dir or get_cache_dir()
        self._config_dir = config_dir or get_config_dir()
        
        # 提供字符串属性供外部使用（pywebview 可以序列化字符串）
        self.cache_dir_str = str(self._cache_dir)
        self.config_dir_str = str(self._config_dir)
        
        # 初始化各个功能模块（使用私有 Path 对象）
        self.data_fetcher = PluginDataFetcher(self._cache_dir, settings_manager)
        self.cache_manager = CacheManager(
            self._cache_dir,
            ttl_seconds=self._read_cache_ttl_seconds(),
        )
        self.install_engine = InstallationEngine()
        self.dependency_checker = DependencyChecker()
        
        logger.info(f"插件市场控制器已初始化，缓存目录: {self._cache_dir}")
    
    def _read_cache_ttl_seconds(self) -> Optional[int]:
        """
        从设置读取插件市场缓存有效期
        
        设置项：cache.marketplaceCacheTtlHours（小时），缺省时回落到常量 CACHE_DURATION。
        
        Returns:
            秒数，读取失败时返回 None（由 CacheManager 使用默认值）
        """
        try:
            if not self._settings_manager:
                from ..settings_manager import SettingsManager
                self._settings_manager = SettingsManager()
            result = self._settings_manager.get_settings()
            if not result.get("success"):
                return None
            hours = ((result.get("settings") or {}).get("cache") or {}).get(
                "marketplaceCacheTtlHours"
            )
            if isinstance(hours, (int, float)) and not isinstance(hours, bool) and hours > 0:
                return int(hours * 3600)
        except Exception as e:
            logger.debug(f"[MarketplaceController] 读取缓存有效期失败: {e}")
        return None
    
    def _get_proxy_config(self) -> Optional[Dict]:
        """
        获取代理配置（供 git / pip 子进程使用）

        应用内未配置代理时会回退到系统代理，这样开了 VPN 的用户
        装插件、拉依赖也能走代理，而不是直连超时。

        Returns:
            dict: {"http_proxy": ..., "https_proxy": ..., "HTTP_PROXY": ..., "HTTPS_PROXY": ...}
            None: 没有可用代理
        """
        try:
            from backend.src.utils.proxy_helper import get_proxy_candidates
            candidates = get_proxy_candidates(self._settings_manager)
            proxy_url = next((url for url in candidates if url), None)

            if not proxy_url:
                return None

            logger.info(f"[MarketplaceController] 使用代理: {proxy_url}")

            return {
                "http_proxy": proxy_url,
                "https_proxy": proxy_url,
                "HTTP_PROXY": proxy_url,
                "HTTPS_PROXY": proxy_url
            }
        except Exception as e:
            logger.error(f"[MarketplaceController] 获取代理配置失败: {e}")
            return None
    
    def _get_requests_proxies(self) -> Optional[Dict]:
        """requests 用的 proxies 参数，解析顺序见 utils.proxy_helper"""
        try:
            from backend.src.utils.proxy_helper import get_proxy_candidates
            candidates = get_proxy_candidates(self._settings_manager)
            proxy_url = next((url for url in candidates if url), None)
            if not proxy_url:
                return None
            return {"http": proxy_url, "https": proxy_url}
        except Exception:
            return None
    
    def _validate_github_url(self, url: str) -> bool:
        """
        验证 GitHub URL 的安全性
        
        支持原始 GitHub URL 和镜像地址，只允许 HTTPS 协议，防止命令注入攻击
        
        Args:
            url: GitHub 仓库地址（原始或镜像地址）
            
        Returns:
            是否为有效的 GitHub URL
        """
        # 必须是 HTTPS 协议
        if not url.startswith("https://"):
            logger.warning(f"无效的 GitHub URL（非 HTTPS）: {url}")
            return False
        
        # 必须包含 github.com/ 路径（支持原始地址和镜像地址）
        if "github.com/" not in url:
            logger.warning(f"无效的 GitHub URL（不包含 github.com）: {url}")
            return False
        
        # 防止命令注入：检查是否包含特殊字符
        dangerous_chars = [';', '&', '|', '`', '$', '(', ')', '<', '>', '\n', '\r']
        if any(char in url for char in dangerous_chars):
            logger.warning(f"检测到潜在的命令注入攻击: {url}")
            return False
        
        return True
    
    def _validate_target_path(self, target: Path, base: Path) -> bool:
        """
        验证目标路径的安全性
        
        防止路径遍历攻击，确保目标路径在 base 目录内
        
        Args:
            target: 目标路径
            base: 基础目录
            
        Returns:
            是否为安全的路径
        """
        try:
            target.resolve().relative_to(base.resolve())
            return True
        except ValueError:
            logger.warning(f"检测到路径遍历攻击: target={target}, base={base}")
            return False

    def _check_plugin_installed(self, plugin_name: str, custom_nodes_paths: List[Path]) -> tuple:
        """
        检查插件是否已安装（支持多路径）
        
        在所有 custom_nodes 路径中查找插件，主路径优先。
        
        Args:
            plugin_name: 插件名称
            custom_nodes_paths: custom_nodes 目录路径列表
            
        Returns:
            (is_installed, install_status) 元组
            - is_installed: 是否已安装（包括已禁用）
            - install_status: 安装状态 ('not_installed', 'installed', 'disabled')
        """
        for custom_nodes_path in custom_nodes_paths:
            plugin_dir = custom_nodes_path / plugin_name
            disabled_dir = custom_nodes_path / f"{plugin_name}.disabled"
            
            if plugin_dir.exists() and plugin_dir.is_dir():
                return True, 'installed'
            
            if disabled_dir.exists() and disabled_dir.is_dir():
                return True, 'disabled'
        
        return False, 'not_installed'
    
    def get_plugins(self, use_cache: bool = True, allow_stale: bool = True) -> Dict:
        """
        获取插件列表
        
        流程（缓存优先）：
        1. use_cache=True 时先读本地缓存，过期了也照样返回（标记 stale=True），
           由前端先把列表渲染出来，再后台调 refresh_plugins 拉新数据
        2. 没有缓存才走网络
        3. 网络失败但有旧缓存时，返回旧缓存而不是空列表
        
        Args:
            use_cache: 是否允许读缓存
            allow_stale: 缓存过期时是否仍然返回（默认 True）
            
        Returns:
            结果字典：
            {
                'success': bool,
                'plugins': [Plugin.to_dict(), ...],
                'total': int,
                'source': 'cache' | 'network',
                'stale': bool,          # 数据是否来自过期缓存
                'cached_at': float,     # 缓存写入时间戳（秒）
                'warning': str (可选),
                'error': str (如果失败)
            }
        """
        try:
            logger.info(f"获取插件列表，use_cache={use_cache}, allow_stale={allow_stale}")
            
            plugins_data = None
            source = "network"
            stale = False
            cached_at = 0.0
            
            # 1. 优先读缓存（含过期缓存）
            if use_cache:
                meta = self.cache_manager.get_plugins_cache_meta()
                if meta.get('exists'):
                    plugins_data = self.cache_manager.get_plugins_cache(allow_stale=allow_stale)
                    if plugins_data:
                        source = "cache"
                        cached_at = float(meta.get('timestamp') or 0.0)
                        stale = not meta.get('is_fresh', False)
                        if stale:
                            logger.info(
                                f"使用过期缓存先展示: {len(plugins_data)} 个插件, "
                                f"已缓存 {meta.get('age_seconds', 0) / 3600:.1f} 小时"
                            )
            
            # 2. 没有缓存才走网络
            if not plugins_data:
                logger.info("从数据源获取插件列表")
                # 当不使用缓存时，强制刷新数据获取器的实例缓存
                plugins_data = self.data_fetcher.fetch_plugins(force_refresh=not use_cache)
                
                if not plugins_data:
                    # 网络失败：有旧缓存就先用旧缓存，别让用户看空白页
                    fallback = self.cache_manager.get_plugins_cache(allow_stale=True)
                    if fallback:
                        meta = self.cache_manager.get_plugins_cache_meta()
                        logger.warning("数据源获取失败，回退到本地缓存展示")
                        self._attach_install_status(fallback)
                        return {
                            'success': True,
                            'plugins': fallback,
                            'total': len(fallback),
                            'source': 'cache',
                            'stale': True,
                            'cached_at': float(meta.get('timestamp') or 0.0),
                            'warning': ERROR_NETWORK_FAILED,
                        }
                    
                    logger.error("数据源获取失败，且没有可用缓存")
                    return {
                        'success': False,
                        'plugins': [],
                        'total': 0,
                        'source': 'network',
                        'stale': False,
                        'cached_at': 0.0,
                        'error': ERROR_NETWORK_FAILED,
                    }
                
                # 更新缓存
                self.cache_manager.set_plugins_cache(plugins_data)
                meta = self.cache_manager.get_plugins_cache_meta()
                cached_at = float(meta.get('timestamp') or 0.0)
            
            # 3. 注入安装状态
            self._attach_install_status(plugins_data)
            
            logger.info(f"成功获取插件列表: {len(plugins_data)} 个插件（来源: {source}）")
            
            return {
                'success': True,
                'plugins': plugins_data,
                'total': len(plugins_data),
                'source': source,
                'stale': stale,
                'cached_at': cached_at,
            }
            
        except Exception as e:
            logger.error(f"获取插件列表失败: {e}")
            logger.exception("详细错误信息")
            return {
                'success': False,
                'plugins': [],
                'total': 0,
                'source': 'network',
                'stale': False,
                'cached_at': 0.0,
                'error': str(e)
            }

    def _attach_install_status(self, plugins_data: List[Dict]) -> None:
        """
        为每个插件就地写入 is_installed / install_status
        
        Args:
            plugins_data: 插件字典列表（会被原地修改）
        """
        # 获取当前环境的 custom_nodes 路径（主路径 + 外置路径）
        current_env = self.env_manager.get_current_environment()
        custom_nodes_paths = []
        
        if current_env:
            comfyui_path = Path(current_env.config.general.comfyui_path)
            custom_nodes_paths = [comfyui_path / "custom_nodes"]
            # 收集外置 custom_nodes 路径
            if hasattr(current_env, 'model_path_configs'):
                for config in current_env.model_path_configs:
                    cn_rel = config.paths.get("custom_nodes") or config.paths.get("customNodes")
                    if cn_rel:
                        ext_path = Path(config.base_path) / cn_rel
                        if ext_path.exists() and ext_path not in custom_nodes_paths:
                            custom_nodes_paths.append(ext_path)
        
        for plugin_dict in plugins_data:
            if custom_nodes_paths:
                # 从仓库 URL 提取插件名称
                repo_url = plugin_dict.get('repository', '')
                if repo_url:
                    plugin_name = repo_url.rstrip('/').split('/')[-1]
                    if plugin_name.endswith('.git'):
                        plugin_name = plugin_name[:-4]
                    
                    is_installed, install_status = self._check_plugin_installed(
                        plugin_name,
                        custom_nodes_paths
                    )
                    plugin_dict['is_installed'] = is_installed
                    plugin_dict['install_status'] = install_status
                else:
                    plugin_dict['is_installed'] = False
                    plugin_dict['install_status'] = 'not_installed'
            else:
                plugin_dict['is_installed'] = False
                plugin_dict['install_status'] = 'not_installed'
    
    def _parse_recommended_config(self) -> List[Dict]:
        """
        解析推荐插件配置文件
        
        配置文件格式：
        - 每行一个插件
        - 格式1：插件名:GitHub地址
        - 格式2：插件名（无地址，需要从插件库搜索）
        
        Args:
            无
            
        Returns:
            推荐插件配置列表，每项包含 name 和 url（可选）
        """
        config_file = get_recommended_plugins_file()
        
        if not config_file.exists():
            logger.warning(f"推荐插件配置文件不存在: {config_file}")
            return []
        
        recommended_configs = []
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                # 去除首尾空白
                line = line.strip()
                
                # 跳过空行和注释行
                if not line or line.startswith('#'):
                    continue
                
                # 解析配置行
                if ':' in line:
                    # 格式1：插件名:GitHub地址
                    parts = line.split(':', 1)
                    plugin_name = parts[0].strip()
                    github_url = parts[1].strip()
                    
                    recommended_configs.append({
                        'name': plugin_name,
                        'url': github_url
                    })
                else:
                    # 格式2：仅插件名
                    plugin_name = line.strip()
                    
                    recommended_configs.append({
                        'name': plugin_name,
                        'url': None
                    })
            
            logger.info(f"成功解析推荐插件配置: {len(recommended_configs)} 个插件")
            return recommended_configs
            
        except Exception as e:
            logger.error(f"解析推荐插件配置文件失败: {e}")
            return []
    
    def _search_plugin_by_name(self, plugin_name: str, plugins_data: List[Dict]) -> Optional[Dict]:
        """
        从插件列表中搜索指定名称的插件
        
        Args:
            plugin_name: 插件名称
            plugins_data: 插件列表数据
            
        Returns:
            匹配的插件数据，如果未找到返回 None
        """
        # 不区分大小写搜索
        plugin_name_lower = plugin_name.lower()
        
        for plugin in plugins_data:
            # 检查插件名称是否匹配
            if plugin.get('name', '').lower() == plugin_name_lower:
                return plugin
            
            # 检查仓库地址是否包含插件名称
            repo = plugin.get('repository', '')
            if repo:
                repo_name = repo.rstrip('/').split('/')[-1]
                if repo_name.endswith('.git'):
                    repo_name = repo_name[:-4]
                
                if repo_name.lower() == plugin_name_lower:
                    return plugin
        
        return None
    
    def get_recommended_plugins(self, use_cache: bool = True) -> Dict:
        """
        获取推荐插件列表
        
        流程：
        1. 如果 use_cache=True 且缓存有效，返回缓存数据
        2. 否则解析推荐插件配置文件
        3. 对于缺失 GitHub 地址的插件，从插件库搜索
        4. 检查每个插件的安装状态
        5. 更新缓存
        6. 返回推荐插件列表
        
        Args:
            use_cache: 是否使用缓存
            
        Returns:
            结果字典：
            {
                'success': bool,
                'plugins': [Plugin.to_dict(), ...],
                'total': int,
                'error': str (如果失败)
            }
        """
        try:
            logger.info(f"获取推荐插件列表，use_cache={use_cache}")
            
            # 尝试从缓存加载
            recommended_data = None
            if use_cache:
                recommended_data = self.cache_manager.get_recommended_cache()
                if recommended_data:
                    logger.info(f"从缓存加载推荐插件列表: {len(recommended_data)} 个插件")
            
            # 如果缓存无效或不使用缓存，重新构建推荐列表
            if not recommended_data:
                logger.info("构建推荐插件列表")
                
                # 解析推荐配置文件
                recommended_configs = self._parse_recommended_config()
                
                if not recommended_configs:
                    logger.warning("推荐配置为空")
                    return {
                        'success': True,
                        'plugins': [],
                        'total': 0
                    }
                
                # 获取完整的插件列表（用于搜索）
                all_plugins_result = self.get_plugins(use_cache=True)
                if not all_plugins_result['success']:
                    logger.error("获取插件库失败，无法构建推荐列表")
                    return {
                        'success': False,
                        'plugins': [],
                        'total': 0,
                        'error': '获取插件库失败'
                    }
                
                all_plugins = all_plugins_result['plugins']
                
                # 构建推荐插件列表
                recommended_data = []
                
                for config in recommended_configs:
                    plugin_name = config['name']
                    github_url = config['url']
                    
                    if github_url:
                        # 如果配置中有 GitHub 地址，直接使用
                        # 尝试从插件库中找到匹配的插件（获取完整信息）
                        plugin_dict = self._search_plugin_by_name(plugin_name, all_plugins)
                        
                        if plugin_dict:
                            # 使用插件库中的完整信息
                            recommended_data.append(plugin_dict)
                        else:
                            # 插件库中没有，创建基本信息
                            recommended_data.append({
                                'name': plugin_name,
                                'description': '推荐插件',
                                'repository': github_url,
                                'version_tag': '未知版本',
                                'updated_at': '',
                                'node_count': 0,
                                'is_installed': False,
                                'author': '',
                                'stars': 0,
                                'downloads': 0,
                                'tags': []
                            })
                    else:
                        # 如果配置中没有 GitHub 地址，从插件库搜索
                        plugin_dict = self._search_plugin_by_name(plugin_name, all_plugins)
                        
                        if plugin_dict:
                            recommended_data.append(plugin_dict)
                        else:
                            logger.warning(f"推荐插件未在插件库中找到: {plugin_name}")
                
                # 更新缓存
                if recommended_data:
                    self.cache_manager.set_recommended_cache(recommended_data)
            
            # 获取当前环境的 custom_nodes 路径（主路径 + 外置路径）
            current_env = self.env_manager.get_current_environment()
            custom_nodes_paths = []
            
            if current_env:
                comfyui_path = Path(current_env.config.general.comfyui_path)
                custom_nodes_paths = [comfyui_path / "custom_nodes"]
                # 收集外置 custom_nodes 路径
                if hasattr(current_env, 'model_path_configs'):
                    for config in current_env.model_path_configs:
                        cn_rel = config.paths.get("custom_nodes") or config.paths.get("customNodes")
                        if cn_rel:
                            ext_path = Path(config.base_path) / cn_rel
                            if ext_path.exists() and ext_path not in custom_nodes_paths:
                                custom_nodes_paths.append(ext_path)
            
            # 检查每个插件的安装状态
            for plugin_dict in recommended_data:
                if custom_nodes_paths:
                    repo_url = plugin_dict.get('repository', '')
                    if repo_url:
                        plugin_name = repo_url.rstrip('/').split('/')[-1]
                        if plugin_name.endswith('.git'):
                            plugin_name = plugin_name[:-4]
                        
                        is_installed, install_status = self._check_plugin_installed(
                            plugin_name,
                            custom_nodes_paths
                        )
                        plugin_dict['is_installed'] = is_installed
                        plugin_dict['install_status'] = install_status
                    else:
                        plugin_dict['is_installed'] = False
                        plugin_dict['install_status'] = 'not_installed'
                else:
                    plugin_dict['is_installed'] = False
                    plugin_dict['install_status'] = 'not_installed'
            
            logger.info(f"成功获取推荐插件列表: {len(recommended_data)} 个插件")
            
            return {
                'success': True,
                'plugins': recommended_data,
                'total': len(recommended_data)
            }
            
        except Exception as e:
            logger.error(f"获取推荐插件列表失败: {e}")
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
        
        在插件列表中搜索名称或简介包含关键词的插件（不区分大小写）
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            结果字典：
            {
                'success': bool,
                'plugins': [Plugin.to_dict(), ...],
                'total': int,
                'keyword': str,
                'error': str (如果失败)
            }
        """
        try:
            logger.info(f"搜索插件，关键词: {keyword}")
            
            # 获取完整的插件列表
            all_plugins_result = self.get_plugins(use_cache=True)
            
            if not all_plugins_result['success']:
                return {
                    'success': False,
                    'plugins': [],
                    'total': 0,
                    'keyword': keyword,
                    'error': '获取插件列表失败'
                }
            
            all_plugins = all_plugins_result['plugins']
            
            # 如果关键词为空，返回全部插件
            if not keyword or not keyword.strip():
                logger.info("关键词为空，返回全部插件")
                return {
                    'success': True,
                    'plugins': all_plugins,
                    'total': len(all_plugins),
                    'keyword': keyword
                }
            
            # 过滤插件（不区分大小写）
            keyword_lower = keyword.strip().lower()
            filtered_plugins = []
            
            for plugin in all_plugins:
                name = plugin.get('name', '').lower()
                description = plugin.get('description', '').lower()
                
                # 检查名称或简介是否包含关键词
                if keyword_lower in name or keyword_lower in description:
                    filtered_plugins.append(plugin)
            
            logger.info(f"搜索完成，找到 {len(filtered_plugins)} 个匹配的插件")
            
            return {
                'success': True,
                'plugins': filtered_plugins,
                'total': len(filtered_plugins),
                'keyword': keyword
            }
            
        except Exception as e:
            logger.error(f"搜索插件失败: {e}")
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
        刷新插件列表（后台拉取最新数据）
        
        注意：先拉数据、成功后再覆盖缓存。旧实现是先清缓存再拉，
        网络一失败本地数据就没了，用户只能看到空列表。
        
        Returns:
            结果字典，结构同 get_plugins，另加 message
        """
        try:
            logger.info("刷新插件列表，拉取最新数据")
            
            fresh = self.data_fetcher.fetch_plugins(force_refresh=True)
            
            if not fresh:
                # 拉取失败：保留旧缓存，把旧数据返回给前端
                meta = self.cache_manager.get_plugins_cache_meta()
                fallback = self.cache_manager.get_plugins_cache(allow_stale=True) or []
                logger.warning("刷新失败，保留本地缓存")
                self._attach_install_status(fallback)
                return {
                    'success': True,
                    'plugins': fallback,
                    'total': len(fallback),
                    'source': 'cache',
                    'stale': True,
                    'cached_at': float(meta.get('timestamp') or 0.0),
                    'warning': ERROR_NETWORK_FAILED,
                    'message': ERROR_NETWORK_FAILED,
                }
            
            self.cache_manager.set_plugins_cache(fresh)
            meta = self.cache_manager.get_plugins_cache_meta()
            self._attach_install_status(fresh)
            
            logger.info(f"插件列表刷新成功: {len(fresh)} 个插件")
            return {
                'success': True,
                'plugins': fresh,
                'total': len(fresh),
                'source': 'network',
                'stale': False,
                'cached_at': float(meta.get('timestamp') or 0.0),
                'message': SUCCESS_CACHE_CLEARED,
            }
            
        except Exception as e:
            logger.error(f"刷新插件列表失败: {e}")
            logger.exception("详细错误信息")
            return {
                'success': False,
                'plugins': [],
                'total': 0,
                'source': 'network',
                'stale': False,
                'cached_at': 0.0,
                'error': str(e)
            }

    def install_plugin(
        self,
        github_url: str,
        auto_install_deps: bool = True,
        progress_callback: Optional[Callable[[Dict], None]] = None
    ) -> Dict:
        """
        安装插件
        
        流程：
        1. 验证 GitHub URL 安全性
        2. 获取当前环境信息
        3. 验证目标路径安全性
        4. 检查是否有正在进行的安装任务
        5. 调用安装引擎执行安装
        
        Args:
            github_url: GitHub 仓库地址
            auto_install_deps: 是否自动安装依赖
            progress_callback: 进度回调函数
            
        Returns:
            结果字典：
            {
                'success': bool,
                'task_id': str,
                'message': str,
                'log_path': str,
                'error': str (如果失败),
                'partial_success': bool (部分成功标志)
            }
        """
        try:
            logger.info(f"开始安装插件: {github_url}, auto_install_deps={auto_install_deps}")
            
            # 1. 验证 GitHub URL
            if not self._validate_github_url(github_url):
                return {
                    'success': False,
                    'error': ERROR_INVALID_GITHUB_URL
                }
            
            # 2. 获取当前环境
            current_env = self.env_manager.get_current_environment()
            
            if not current_env:
                logger.error("当前环境未配置")
                return {
                    'success': False,
                    'error': ERROR_ENV_NOT_CONFIGURED
                }
            
            # 获取环境路径
            comfyui_path = Path(current_env.config.general.comfyui_path)
            python_path = Path(current_env.config.general.python_path)
            custom_nodes_path = comfyui_path / "custom_nodes"
            
            # 确保 custom_nodes 目录存在
            custom_nodes_path.mkdir(parents=True, exist_ok=True)
            
            # 3. 验证目标路径安全性
            if not self._validate_target_path(custom_nodes_path, comfyui_path):
                return {
                    'success': False,
                    'error': ERROR_PATH_TRAVERSAL
                }
            
            # 4. 检查是否有正在进行的安装任务
            if self.install_engine.has_active_installation():
                active_task_id = self.install_engine.get_active_task_id()
                logger.warning(f"已有正在进行的安装任务: {active_task_id}")
                return {
                    'success': False,
                    'error': '已有正在进行的安装任务，请等待完成后再试'
                }
            
            # 5. 调用安装引擎执行安装（异步）
            from .installation_engine_async_patch import install_plugin_async
            result = install_plugin_async(
                engine=self.install_engine,
                github_url=github_url,
                target_dir=custom_nodes_path,
                python_path=python_path,
                auto_install_deps=auto_install_deps,
                progress_callback=progress_callback
            )
            
            # 注意：这里不清除缓存，因为安装是异步的
            # 安装完成后，前端会调用 get_installed_plugins_status() 更新安装状态
            
            return result
            
        except Exception as e:
            logger.error(f"安装插件失败: {e}")
            logger.exception("详细错误信息")
            return {
                'success': False,
                'error': str(e)
            }

    def _parse_github_url(self, github_url: str) -> tuple:
        """
        解析 GitHub URL，提取 owner 和 repo
        
        Args:
            github_url: GitHub 仓库地址
            
        Returns:
            (owner, repo) 元组
        """
        # 移除 .git 后缀
        url = github_url.rstrip('/').replace('.git', '')
        
        # 提取 owner 和 repo
        # https://github.com/owner/repo
        parts = url.split('/')
        if len(parts) >= 5:
            owner = parts[-2]
            repo = parts[-1]
            return owner, repo
        
        raise ValueError(f"无法解析 GitHub URL: {github_url}")
    
    def _fetch_requirements_from_github(self, github_url: str) -> Optional[str]:
        """
        从 GitHub 直接获取 requirements.txt 文件内容
        
        策略：
        1. 尝试 main 分支
        2. 尝试 master 分支
        3. 调用 GitHub API 获取默认分支
        4. 回退到 Git Clone 方案
        
        如果启用了镜像加速，使用镜像 URL 获取。
        
        Args:
            github_url: GitHub 仓库地址
            
        Returns:
            requirements.txt 文件内容，如果不存在返回 None
        """
        import requests
        
        try:
            owner, repo = self._parse_github_url(github_url)
            logger.info(f"从 GitHub 获取 requirements.txt: {owner}/{repo}")
            
            branches_to_try = ['main', 'master']
            
            for branch in branches_to_try:
                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/requirements.txt"
                
                try:
                    from backend.src.utils.github_mirror import github_mirror_manager
                    verify_ssl = True
                    if github_mirror_manager.is_enabled():
                        mirror_url, mirror_headers = github_mirror_manager.transform_url(raw_url, "raw")
                        raw_url = mirror_url
                        request_headers = {'User-Agent': 'ComfyNexus/1.0'}
                        request_headers.update(mirror_headers)
                        settings = github_mirror_manager._load_settings()
                        verify_ssl = settings.get("verifySSL", True)
                    else:
                        request_headers = {}
                        verify_ssl = True
                except Exception:
                    request_headers = {}
                    verify_ssl = True
                
                logger.debug(f"尝试获取: {raw_url}")
                
                try:
                    proxies = self._get_requests_proxies()
                    response = requests.get(raw_url, timeout=10, headers=request_headers, verify=verify_ssl, proxies=proxies)
                    
                    if response.status_code == 200:
                        logger.info(f"成功从 {branch} 分支获取 requirements.txt")
                        return response.text
                    elif response.status_code == 404:
                        logger.debug(f"{branch} 分支不存在 requirements.txt，尝试下一个分支")
                        continue
                    else:
                        logger.warning(f"获取失败，状态码: {response.status_code}")
                        continue
                        
                except requests.Timeout:
                    logger.warning(f"从 {branch} 分支获取超时")
                    continue
                except requests.RequestException as e:
                    logger.warning(f"从 {branch} 分支获取失败: {e}")
                    continue
            
            logger.info("尝试通过 GitHub API 获取默认分支")
            try:
                api_url = f"https://api.github.com/repos/{owner}/{repo}"
                api_headers = {'User-Agent': 'ComfyNexus/1.0'}
                verify_ssl = True
                
                try:
                    from backend.src.utils.github_mirror import github_mirror_manager
                    if github_mirror_manager.is_enabled():
                        mirror_url, mirror_headers = github_mirror_manager.transform_url(api_url, "api")
                        api_url = mirror_url
                        api_headers.update(mirror_headers)
                        settings = github_mirror_manager._load_settings()
                        verify_ssl = settings.get("verifySSL", True)
                        logger.debug(f"使用 API 镜像源获取默认分支, verify_ssl={verify_ssl}")
                except Exception:
                    pass
                
                proxies = self._get_requests_proxies()
                response = requests.get(api_url, timeout=10, headers=api_headers, verify=verify_ssl, proxies=proxies)
                
                if response.status_code == 200:
                    repo_info = response.json()
                    default_branch = repo_info.get('default_branch', 'main')
                    logger.info(f"默认分支: {default_branch}")
                    
                    if default_branch not in branches_to_try:
                        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{default_branch}/requirements.txt"
                        
                        try:
                            from backend.src.utils.github_mirror import github_mirror_manager
                            verify_ssl = True
                            if github_mirror_manager.is_enabled():
                                mirror_url, mirror_headers = github_mirror_manager.transform_url(raw_url, "raw")
                                raw_url = mirror_url
                                request_headers = {'User-Agent': 'ComfyNexus/1.0'}
                                request_headers.update(mirror_headers)
                                settings = github_mirror_manager._load_settings()
                                verify_ssl = settings.get("verifySSL", True)
                            else:
                                request_headers = {}
                        except Exception:
                            request_headers = {}
                            verify_ssl = True
                        
                        logger.debug(f"尝试获取: {raw_url}")
                        
                        proxies = self._get_requests_proxies()
                        response = requests.get(raw_url, timeout=10, headers=request_headers, verify=verify_ssl, proxies=proxies)
                        if response.status_code == 200:
                            logger.info(f"成功从 {default_branch} 分支获取 requirements.txt")
                            return response.text
                        
            except Exception as e:
                logger.warning(f"通过 GitHub API 获取默认分支失败: {e}")
            
            logger.info("所有方法都失败，插件可能没有 requirements.txt 文件")
            return None
            
        except Exception as e:
            logger.error(f"从 GitHub 获取 requirements.txt 失败: {e}")
            return None
    
    def _fetch_requirements_by_git_clone(self, github_url: str) -> Optional[str]:
        """
        通过 Git Clone 获取 requirements.txt（回退方案，带镜像 fallback 机制）
        
        Args:
            github_url: GitHub 仓库地址
            
        Returns:
            requirements.txt 文件内容，如果不存在返回 None
        """
        import tempfile
        import shutil
        import subprocess
        
        temp_dir = None
        
        try:
            logger.info("使用 Git Clone 回退方案获取 requirements.txt")
            
            temp_dir = Path(tempfile.mkdtemp(prefix='plugin_check_'))
            logger.debug(f"创建临时目录: {temp_dir}")
            
            plugin_name = github_url.rstrip('/').split('/')[-1]
            if plugin_name.endswith('.git'):
                plugin_name = plugin_name[:-4]
            
            plugin_temp_path = temp_dir / plugin_name
            
            from ...utils.git_config import GIT_EXECUTABLE
            
            clone_cmd = [
                str(GIT_EXECUTABLE),
                'clone',
                '--depth', '1',
                github_url,
                str(plugin_temp_path)
            ]
            
            cmd_str = ' '.join(clone_cmd)
            logger.info(f"执行 Git 命令: {cmd_str}")
            
            proxy_config = self._get_proxy_config()
            proxy_url = proxy_config.get('HTTP_PROXY', '') if proxy_config else ''
            
            if github_url.startswith("https://github.com/"):
                mirrors_to_try = self._get_git_mirror_priority_list()
            else:
                logger.info(f"[MarketplaceController] 检测到镜像地址，跳过系统镜像: {github_url}")
                mirrors_to_try = [None]
            last_error = ""
            
            for attempt, mirror in enumerate(mirrors_to_try):
                env = os.environ.copy()
                if proxy_config:
                    env.update(proxy_config)
                    if proxy_url:
                        logger.info(f"[MarketplaceController] Git 命令使用代理: {proxy_url}")
                env["GIT_TERMINAL_PROMPT"] = "0"
                
                if mirror:
                    env["GIT_CONFIG_COUNT"] = "1"
                    env["GIT_CONFIG_KEY_0"] = f"url.https://{mirror}/.insteadOf"
                    env["GIT_CONFIG_VALUE_0"] = "https://github.com/"
                    logger.info(f"[MarketplaceController] 尝试镜像 ({attempt + 1}/{len(mirrors_to_try)}): {mirror}")
                else:
                    logger.info(f"[MarketplaceController] 尝试直连 GitHub ({attempt + 1}/{len(mirrors_to_try)})")
                
                creation_flags = 0
                if platform.system() == "Windows":
                    creation_flags = subprocess.CREATE_NO_WINDOW
                
                result = subprocess.run(
                    clone_cmd,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    creationflags=creation_flags
                )
                
                if result.returncode == 0:
                    if attempt > 0:
                        logger.info(f"[MarketplaceController] 镜像 fallback 成功: {mirror or '直连 GitHub'}")
                    
                    requirements_file = plugin_temp_path / "requirements.txt"
                    
                    if not requirements_file.exists():
                        logger.info("插件没有 requirements.txt 文件")
                        return None
                    
                    with open(requirements_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    logger.info("成功通过 Git Clone 获取 requirements.txt")
                    return content
                
                last_error = result.stderr
                
                if self._is_mirror_failure(result.stderr):
                    if mirror:
                        logger.warning(f"[MarketplaceController] 镜像 {mirror} 失败: {result.stderr[:100]}")
                    
                    if plugin_temp_path.exists():
                        shutil.rmtree(plugin_temp_path, ignore_errors=True)
                    continue
                else:
                    break
            
            logger.error(f"克隆仓库失败，所有镜像源均失败: {last_error}")
            return None
            
        except Exception as e:
            logger.error(f"Git Clone 回退方案失败: {e}")
            return None
            
        finally:
            if temp_dir and temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                    logger.debug(f"已清理临时目录: {temp_dir}")
                except Exception as e:
                    logger.warning(f"清理临时目录失败: {e}")
    
    def _get_git_mirror_priority_list(self) -> List[Optional[str]]:
        """
        获取 Git 镜像优先级列表
        
        Returns:
            镜像列表，None 表示直连 GitHub
        """
        mirrors = []
        try:
            from backend.src.utils.github_mirror import github_mirror_manager
            
            if not github_mirror_manager.is_enabled():
                return [None]
            
            preset = github_mirror_manager.get_current_preset()
            if not preset:
                return [None]
            
            primary = preset.get("github")
            fallbacks = preset.get("fallback", {}).get("github", [])
            
            if primary:
                mirrors.append(primary)
            mirrors.extend(fallbacks)
            
            if None not in mirrors:
                mirrors.append(None)
            
            return list(dict.fromkeys(mirrors))
            
        except Exception as e:
            logger.dev(f"[MarketplaceController] 获取镜像优先级列表失败: {e}")
            return [None]
    
    def _is_mirror_failure(self, stderr: str) -> bool:
        """检测是否为镜像源失败"""
        if not stderr:
            return False
        failure_patterns = [
            "not found",
            "404",
            "could not resolve host",
            "connection timed out",
            "repository",
            "unable to access",
            "fatal:",
        ]
        stderr_lower = stderr.lower()
        return any(pattern in stderr_lower for pattern in failure_patterns)

    def check_dependencies(self, github_url: str) -> Dict:
        """
        检查插件依赖冲突（优化版：直接从 GitHub 获取 requirements.txt）
        
        流程：
        1. 验证 GitHub URL
        2. 获取当前环境信息
        3. 从 GitHub 直接获取 requirements.txt（HTTP 请求）
        4. 如果失败，回退到 Git Clone 方案
        5. 调用依赖检测器检查冲突
        
        性能优化：
        - 使用 HTTP 直接获取文件，速度提升 10-100 倍
        - 只下载 requirements.txt（几 KB），而不是整个仓库（几 MB）
        - 减少磁盘 I/O 和临时文件操作
        
        Args:
            github_url: GitHub 仓库地址
            
        Returns:
            结果字典：
            {
                'success': bool,
                'has_conflicts': bool,
                'conflicts': [DependencyConflict.to_dict(), ...],
                'missing': [DependencyConflict.to_dict(), ...],
                'error': str (如果失败)
            }
        """
        import tempfile
        
        try:
            logger.info(f"检查插件依赖冲突: {github_url}")
            
            # 1. 验证 GitHub URL
            if not self._validate_github_url(github_url):
                return {
                    'success': False,
                    'has_conflicts': False,
                    'conflicts': [],
                    'missing': [],
                    'error': ERROR_INVALID_GITHUB_URL
                }
            
            # 2. 获取当前环境
            current_env = self.env_manager.get_current_environment()
            
            if not current_env:
                logger.error("当前环境未配置")
                return {
                    'success': False,
                    'has_conflicts': False,
                    'conflicts': [],
                    'missing': [],
                    'error': ERROR_ENV_NOT_CONFIGURED
                }
            
            python_path = Path(current_env.config.general.python_path)
            
            # 3. 从 GitHub 直接获取 requirements.txt（优化：HTTP 请求）
            requirements_content = self._fetch_requirements_from_github(github_url)
            
            # 4. 如果 HTTP 方式失败，回退到 Git Clone
            if requirements_content is None:
                logger.warning("HTTP 方式获取失败，回退到 Git Clone 方案")
                requirements_content = self._fetch_requirements_by_git_clone(github_url)
            
            # 如果还是失败，说明插件没有 requirements.txt
            if requirements_content is None:
                logger.info("插件没有 requirements.txt 文件")
                return {
                    'success': True,
                    'has_conflicts': False,
                    'conflicts': [],
                    'missing': []
                }
            
            # 5. 将内容写入临时文件，供依赖检测器使用
            temp_file = None
            try:
                import tempfile
                temp_file = tempfile.NamedTemporaryFile(
                    mode='w',
                    encoding='utf-8',
                    suffix='.txt',
                    delete=False
                )
                temp_file.write(requirements_content)
                temp_file.close()
                
                requirements_file = Path(temp_file.name)
                
                # 6. 调用依赖检测器检查冲突
                check_result = self.dependency_checker.check_conflicts(
                    requirements_file,
                    python_path
                )
                
                return check_result
                
            finally:
                # 清理临时文件
                if temp_file:
                    try:
                        Path(temp_file.name).unlink()
                        logger.debug(f"已清理临时文件: {temp_file.name}")
                    except Exception as e:
                        logger.warning(f"清理临时文件失败: {e}")
            
        except Exception as e:
            logger.error(f"检查依赖冲突失败: {e}")
            logger.exception("详细错误信息")
            return {
                'success': False,
                'has_conflicts': False,
                'conflicts': [],
                'missing': [],
                'error': str(e)
            }
    
    def get_install_progress(self, task_id: str) -> Dict:
        """
        获取安装进度
        
        Args:
            task_id: 任务 ID
            
        Returns:
            任务进度字典，如果任务不存在返回错误
        """
        try:
            progress = self.install_engine.get_progress(task_id)
            
            if progress:
                return {
                    'success': True,
                    'progress': progress
                }
            else:
                return {
                    'success': False,
                    'error': f'任务不存在: {task_id}'
                }
                
        except Exception as e:
            logger.error(f"获取安装进度失败: {e}")
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
            结果字典：
            {
                'success': bool,
                'message': str,
                'error': str (如果失败)
            }
        """
        try:
            logger.info(f"[MarketplaceController] 取消安装任务: {task_id}")
            result = self.install_engine.cancel_installation(task_id)
            
            # 如果取消成功，刷新插件列表缓存
            if result.get('success'):
                logger.info("安装已取消，清除缓存以刷新列表")
                self.cache_manager.clear_cache()
            
            return result
            
        except Exception as e:
            logger.error(f"[MarketplaceController] 取消安装任务失败: {e}")
            logger.exception("详细错误信息")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_installed_plugins_status(self) -> Dict:
        """
        获取当前环境下已安装插件的状态
        
        返回已安装和已禁用插件的名称列表，用于前端更新安装状态
        不重新获取全量插件数据，性能更优
        
        Returns:
            结果字典：
            {
                'success': bool,
                'installed_plugins': [plugin_name1, plugin_name2, ...],  # 正常启用的插件
                'disabled_plugins': [plugin_name1, plugin_name2, ...],   # 已禁用的插件（.disabled 后缀）
                'error': str (如果失败)
            }
        """
        try:
            logger.info("[MarketplaceController] 获取已安装插件状态")
            
            # 获取当前环境的 custom_nodes 路径
            current_env = self.env_manager.get_current_environment()
            
            if not current_env:
                logger.warning("当前环境未配置")
                return {
                    'success': True,
                    'installed_plugins': [],
                    'disabled_plugins': []
                }
            
            comfyui_path = Path(current_env.config.general.comfyui_path)
            
            # 收集所有 custom_nodes 路径（主路径 + 外置路径）
            custom_nodes_paths = [comfyui_path / "custom_nodes"]
            if hasattr(current_env, 'model_path_configs'):
                for config in current_env.model_path_configs:
                    cn_rel = config.paths.get("custom_nodes") or config.paths.get("customNodes")
                    if cn_rel:
                        ext_path = Path(config.base_path) / cn_rel
                        if ext_path.exists() and ext_path not in custom_nodes_paths:
                            custom_nodes_paths.append(ext_path)
            
            installed_plugins = []
            disabled_plugins = []
            seen_names = set()
            
            # 遍历所有 custom_nodes 路径
            for custom_nodes_path in custom_nodes_paths:
                if not custom_nodes_path.exists():
                    continue
                
                for item in custom_nodes_path.iterdir():
                    if item.is_dir() and not item.name.startswith('.'):
                        if item.name.endswith('.disabled'):
                            plugin_name = item.name[:-9]
                            if plugin_name not in seen_names:
                                seen_names.add(plugin_name)
                                disabled_plugins.append(plugin_name)
                        else:
                            if item.name not in seen_names:
                                seen_names.add(item.name)
                                installed_plugins.append(item.name)
            
            logger.info(f"当前环境已安装 {len(installed_plugins)} 个插件，已禁用 {len(disabled_plugins)} 个插件")
            
            return {
                'success': True,
                'installed_plugins': installed_plugins,
                'disabled_plugins': disabled_plugins
            }
            
        except Exception as e:
            logger.error(f"[MarketplaceController] 获取已安装插件状态失败: {e}")
            logger.exception("详细错误信息")
            return {
                'success': False,
                'installed_plugins': [],
                'disabled_plugins': [],
                'error': str(e)
            }
