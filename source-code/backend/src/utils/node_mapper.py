"""
节点映射工具类

参考 ComfyUI-Manager 的实现，提供准确的节点到插件的映射功能：
1. builtin_nodes - ComfyUI 内置节点（包括前端节点）
2. preemption_map - 内置节点优先映射
3. rext_map - 节点到插件的反向映射
4. nodename_pattern - 正则模式匹配
5. 本地 custom_nodes 扫描 - 检查插件安装状态

关键设计：使用 GitHub URL 作为唯一插件标识符（与 ComfyUI-Manager 一致）
"""

import json
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from backend.src.utils.paths import get_data_dir, get_cache_dir
from backend.src.utils.logger import app_logger as logger


EXTENSION_NODE_MAP_URL = "https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/extension-node-map.json"
COMFYREGISTRY_API_URL = "https://raw.githubusercontent.com/qiqStrong/ComfyNexus/main/comfyui_api_nodes.json"
CACHE_FILE_NAME = "extension_node_map.json"
CACHE_DURATION = 24 * 60 * 60
CACHE_VERSION = 4

COMFY_CORE_URL = "https://github.com/comfyanonymous/ComfyUI"
BUILTIN_NODES_FILE = "core_nodes.json"


@dataclass
class PluginInfo:
    """插件信息"""
    github_url: str
    name: str
    nodes: List[str] = field(default_factory=list)
    nodename_pattern: Optional[str] = None
    preemptions: List[str] = field(default_factory=list)


@dataclass
class BuiltinNodeInfo:
    """内置节点信息"""
    node_type: str
    category: str
    display_name: str
    description: str = ""


@dataclass
class NodeMappingResult:
    """节点映射结果"""
    github_url: str
    plugin_name: str
    is_builtin: bool = False
    is_frontend: bool = False
    category: str = ""


def normalize_github_url(url: str) -> str:
    """
    标准化 GitHub URL
    
    Args:
        url: 原始 URL
        
    Returns:
        标准化后的 URL，如果不是有效 URL 则返回空字符串
    """
    if not url:
        return ""
    
    url = url.strip()
    
    # 移除可能存在的反引号包裹（Markdown 格式）
    if url.startswith('`') and url.endswith('`'):
        url = url[1:-1]
    
    url = url.strip()
    
    # 移除末尾的逗号
    if url.endswith(','):
        url = url[:-1]
    
    url = url.strip()
    
    # 检查是否是完整的 URL
    if url.startswith('http://') or url.startswith('https://'):
        # 已经是完整 URL，进行标准化
        if url.endswith('.git'):
            url = url[:-4]
        
        url = url.replace('git@github.com:', 'https://github.com/')
        
        return url.rstrip('/')
    
    # 检查是否是 git@ 格式
    if url.startswith('git@'):
        url = url.replace('git@github.com:', 'https://github.com/')
        if url.endswith('.git'):
            url = url[:-4]
        return url.rstrip('/')
    
    # 不是完整的 URL，返回空字符串表示需要通过其他方式查找
    return ""


class NodeMapper:
    """
    节点映射器
    
    实现与 ComfyUI-Manager 一致的节点匹配逻辑：
    1. 内置节点检查
    2. 本地映射表匹配（V1/V3/前端节点）
    3. preemption_map 优先匹配（内置节点和优先级覆盖）
    4. rext_map 精确匹配
    5. nodename_pattern 正则匹配
    
    使用 GitHub URL 作为唯一插件标识符
    """
    
    _instance: Optional['NodeMapper'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._preemption_map: Dict[str, str] = {}
        self._rext_map: Dict[str, List[str]] = {}
        self._patterns: List[Tuple[str, str]] = []
        self._plugin_info: Dict[str, PluginInfo] = {}
        self._cache_path: Path = get_cache_dir("marketplace") / CACHE_FILE_NAME
        self._last_update_time: float = 0
        self._local_plugins: Dict[str, Dict[str, Any]] = {}
        self._builtin_nodes: Dict[str, BuiltinNodeInfo] = {}
        self._cnr_id_map: Dict[str, str] = {}
        
        self._local_node_map: Optional[Any] = None
        self._local_scanner: Optional[Any] = None
        self._comfyui_path: Optional[str] = None
        
        # 扫描锁，防止并发扫描
        self._is_scanning = False
        
        self._initialized = True
        
        self._load_builtin_nodes()
        
        logger.debug("NodeMapper 初始化完成")
    
    def initialize(self, force_refresh: bool = False) -> bool:
        """
        初始化映射表
        
        Args:
            force_refresh: 是否强制刷新
            
        Returns:
            是否初始化成功
        """
        if not force_refresh and self._load_from_cache():
            logger.info("从缓存加载节点映射表成功")
            return True
        
        return self.refresh()
    
    def _load_builtin_nodes(self) -> None:
        """
        从 data/core_nodes.json 加载内置节点列表
        """
        builtin_nodes_path = get_data_dir() / BUILTIN_NODES_FILE
        
        if not builtin_nodes_path.exists():
            logger.warning(f"内置节点文件不存在: {builtin_nodes_path}")
            return
        
        try:
            with open(builtin_nodes_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            nodes_data = data.get('nodes', {})
            for node_type, info in nodes_data.items():
                category = info.get('category', 'core')
                display_name = info.get('display_name', node_type)
                description = info.get('description', '')
                
                self._builtin_nodes[node_type] = BuiltinNodeInfo(
                    node_type=node_type,
                    category=category,
                    display_name=display_name,
                    description=description
                )
            
            logger.info(f"加载内置节点: {len(self._builtin_nodes)} 个")
            
        except Exception as e:
            logger.error(f"加载内置节点失败: {e}")
    
    def refresh(self) -> bool:
        """
        刷新映射表（从远程获取最新数据）
        
        数据源：
        1. ComfyUI-Manager extension-node-map.json（节点映射）
        2. ComfyRegistry API（插件元数据）
        
        Returns:
            是否刷新成功
        """
        try:
            logger.info("开始刷新节点映射表...")
            
            extension_map = self._fetch_extension_node_map()
            comfyregistry_data = self._fetch_comfyregistry_api()
            
            if extension_map:
                self._build_maps(extension_map)
                
                if comfyregistry_data:
                    self._merge_comfyregistry_data(comfyregistry_data)
                
                self._save_to_cache()
                self._last_update_time = time.time()
                logger.info(
                    f"节点映射表刷新成功: "
                    f"preemption={len(self._preemption_map)}, "
                    f"rext={len(self._rext_map)}, "
                    f"patterns={len(self._patterns)}, "
                    f"plugins={len(self._plugin_info)}"
                )
                return True
            else:
                logger.warning("节点映射表刷新失败")
                return False
                
        except Exception as e:
            logger.error(f"刷新节点映射表时发生错误: {e}")
            return False
    
    def _fetch_extension_node_map(self) -> Optional[Dict[str, Any]]:
        """
        从 ComfyUI-Manager 获取 extension-node-map.json
        
        如果启用了镜像加速，使用镜像 URL 获取。
        
        Returns:
            extension-node-map.json 数据，失败返回 None
        """
        try:
            import requests
            
            url = EXTENSION_NODE_MAP_URL
            headers = {'User-Agent': 'ComfyNexus/1.0'}
            verify_ssl = True
            
            try:
                from backend.src.utils.github_mirror import github_mirror_manager
                if github_mirror_manager.is_enabled():
                    mirror_url, mirror_headers = github_mirror_manager.transform_url(url, "raw")
                    url = mirror_url
                    headers.update(mirror_headers)
                    settings = github_mirror_manager._load_settings()
                    verify_ssl = settings.get("verifySSL", True)
            except Exception:
                pass
            
            logger.debug(f"正在获取 extension-node-map.json: {url}")
            
            response = requests.get(
                url,
                timeout=30,
                headers=headers,
                verify=verify_ssl
            )
            
            response.raise_for_status()
            data = response.json()
            
            logger.debug(f"成功获取 extension-node-map.json，共 {len(data)} 个插件")
            return data
            
        except Exception as e:
            logger.error(f"获取 extension-node-map.json 失败: {e}")
            return None
    
    def _fetch_comfyregistry_api(self) -> Optional[List[Dict[str, Any]]]:
        """
        从 ComfyRegistry API 获取插件数据
        
        如果启用了镜像加速，使用镜像 URL 获取。
        
        Returns:
            插件列表，失败返回 None
        """
        try:
            import requests
            
            url = COMFYREGISTRY_API_URL
            headers = {'User-Agent': 'ComfyNexus/1.0'}
            verify_ssl = True
            
            try:
                from backend.src.utils.github_mirror import github_mirror_manager
                if github_mirror_manager.is_enabled():
                    mirror_url, mirror_headers = github_mirror_manager.transform_url(url, "raw")
                    url = mirror_url
                    headers.update(mirror_headers)
                    settings = github_mirror_manager._load_settings()
                    verify_ssl = settings.get("verifySSL", True)
            except Exception:
                pass
            
            logger.debug(f"正在获取 ComfyRegistry API: {url}")
            
            response = requests.get(
                url,
                timeout=60,
                headers=headers,
                verify=verify_ssl
            )
            
            response.raise_for_status()
            data = response.json()
            
            logger.debug(f"成功获取 ComfyRegistry API，共 {len(data)} 个插件")
            return data
            
        except Exception as e:
            logger.error(f"获取 ComfyRegistry API 失败: {e}")
            return None
    
    def _build_maps(self, extension_map: Dict[str, Any]) -> None:
        """
        构建映射表
        
        参考 ComfyUI-Manager 的 extract_nodes_from_workflow 逻辑：
        - preemption_map: 内置节点和优先级覆盖（值为 GitHub URL）
        - rext_map: 节点到 GitHub URL 列表的反向映射
        - patterns: 正则模式到 GitHub URL 的映射
        
        Args:
            extension_map: extension-node-map.json 数据
        """
        self._preemption_map.clear()
        self._rext_map.clear()
        self._patterns.clear()
        self._plugin_info.clear()
        
        for repo_url, value in extension_map.items():
            if not isinstance(value, list) or len(value) < 2:
                continue
            
            node_list = value[0] if isinstance(value[0], list) else []
            metadata = value[1] if isinstance(value[1], dict) else {}
            
            normalized_url = normalize_github_url(repo_url)
            if not normalized_url:
                continue
            
            plugin_name = self._extract_plugin_name(repo_url, metadata)
            
            self._plugin_info[normalized_url] = PluginInfo(
                github_url=normalized_url,
                name=plugin_name,
                nodes=node_list,
                nodename_pattern=metadata.get('nodename_pattern'),
                preemptions=metadata.get('preemptions', [])
            )
            
            if normalized_url == COMFY_CORE_URL:
                for node_type in node_list:
                    if node_type and isinstance(node_type, str):
                        self._preemption_map[node_type] = normalized_url
            else:
                for node_type in node_list:
                    if node_type and isinstance(node_type, str):
                        if node_type not in self._rext_map:
                            self._rext_map[node_type] = []
                        if normalized_url not in self._rext_map[node_type]:
                            self._rext_map[node_type].append(normalized_url)
                
                preemptions = metadata.get('preemptions', [])
                for node_type in preemptions:
                    if node_type and isinstance(node_type, str):
                        self._preemption_map[node_type] = normalized_url
                
                pattern = metadata.get('nodename_pattern')
                if pattern:
                    self._patterns.append((pattern, normalized_url))
        
        logger.debug(
            f"映射表构建完成: "
            f"preemption_map={len(self._preemption_map)}, "
            f"rext_map={len(self._rext_map)}, "
            f"patterns={len(self._patterns)}"
        )
    
    def _extract_plugin_name(self, repo_url: str, metadata: Dict[str, Any]) -> str:
        """
        提取插件名称
        
        Args:
            repo_url: 仓库 URL
            metadata: 插件元数据
            
        Returns:
            插件名称
        """
        if 'title_aux' in metadata:
            return metadata['title_aux']
        
        url = normalize_github_url(repo_url)
        
        if url == COMFY_CORE_URL:
            return 'ComfyUI Core'
        
        parts = url.rstrip('/').split('/')
        if len(parts) >= 1:
            return parts[-1]
        
        return 'Unknown Plugin'
    
    def _merge_comfyregistry_data(self, registry_data: List[Dict[str, Any]]) -> None:
        """
        合并 ComfyRegistry API 数据到插件信息
        
        ComfyRegistry 提供更丰富的插件元数据：
        - id: ComfyRegistry ID（如 "prompt-assistant"）
        - downloads: 下载量
        - github_stars: GitHub 星数
        - rating: 评分
        - description: 描述
        - tags: 标签
        - latest_version: 最新版本信息
        
        关键：建立 cnr_id → GitHub URL 的映射，用于工作流解析
        
        Args:
            registry_data: ComfyRegistry API 返回的插件列表
        """
        merged_count = 0
        
        for plugin in registry_data:
            cnr_id = plugin.get('id', '')
            repo_url = plugin.get('repository', '')
            
            if not repo_url:
                continue
            
            normalized_url = normalize_github_url(repo_url)
            if not normalized_url:
                continue
            
            if cnr_id:
                self._cnr_id_map[cnr_id] = normalized_url
            
            if normalized_url in self._plugin_info:
                existing_info = self._plugin_info[normalized_url]
                existing_info.name = plugin.get('name', existing_info.name)
                merged_count += 1
            else:
                self._plugin_info[normalized_url] = PluginInfo(
                    github_url=normalized_url,
                    name=plugin.get('name', 'Unknown'),
                    nodes=[],
                    nodename_pattern=None,
                    preemptions=[]
                )
                merged_count += 1
        
        logger.debug(f"合并 ComfyRegistry 数据完成: {merged_count} 个插件, cnr_id 映射: {len(self._cnr_id_map)} 个")
    
    def _load_from_cache(self) -> bool:
        """
        从缓存加载映射表
        
        Returns:
            是否加载成功
        """
        try:
            if not self._cache_path.exists():
                logger.debug(f"缓存文件不存在: {self._cache_path}")
                return False
            
            with open(self._cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            cache_version = cache_data.get('version', 1)
            if cache_version < CACHE_VERSION:
                logger.debug(f"缓存版本过旧: {cache_version} < {CACHE_VERSION}")
                return False
            
            timestamp = cache_data.get('timestamp', 0)
            if time.time() - timestamp > CACHE_DURATION:
                logger.debug("缓存已过期")
                return False
            
            self._preemption_map = cache_data.get('preemption_map', {})
            self._rext_map = cache_data.get('rext_map', {})
            self._patterns = cache_data.get('patterns', [])
            self._cnr_id_map = cache_data.get('cnr_id_map', {})
            
            plugin_info_data = cache_data.get('plugin_info', {})
            self._plugin_info = {}
            for url, info in plugin_info_data.items():
                self._plugin_info[url] = PluginInfo(
                    github_url=info.get('github_url', url),
                    name=info.get('name', ''),
                    nodes=info.get('nodes', []),
                    nodename_pattern=info.get('nodename_pattern'),
                    preemptions=info.get('preemptions', [])
                )
            
            self._last_update_time = timestamp
            
            logger.debug(
                f"从缓存加载映射表: "
                f"preemption={len(self._preemption_map)}, "
                f"rext={len(self._rext_map)}, "
                f"patterns={len(self._patterns)}"
            )
            return True
            
        except Exception as e:
            logger.error(f"加载缓存失败: {e}")
            return False
    
    def _save_to_cache(self) -> None:
        """
        保存映射表到缓存
        """
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            plugin_info_data = {}
            for url, info in self._plugin_info.items():
                plugin_info_data[url] = {
                    'github_url': info.github_url,
                    'name': info.name,
                    'nodes': info.nodes,
                    'nodename_pattern': info.nodename_pattern,
                    'preemptions': info.preemptions
                }
            
            cache_data = {
                'version': CACHE_VERSION,
                'timestamp': time.time(),
                'preemption_map': self._preemption_map,
                'rext_map': self._rext_map,
                'patterns': self._patterns,
                'plugin_info': plugin_info_data,
                'cnr_id_map': self._cnr_id_map,
            }
            
            with open(self._cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"映射表已保存到缓存: {self._cache_path}")
            
        except Exception as e:
            logger.error(f"保存缓存失败: {e}")
    
    def resolve_node(self, node_type: str) -> NodeMappingResult:
        """
        解析节点类型到插件
        
        匹配逻辑：
        1. 首先检查内置节点（包括前端节点）
        2. 然后检查 preemption_map（优先级覆盖）
        3. 然后检查 rext_map（精确匹配）
        4. 最后尝试正则模式匹配
        
        Args:
            node_type: 节点类型
            
        Returns:
            NodeMappingResult 对象，包含 GitHub URL
        """
        builtin_info = self._builtin_nodes.get(node_type)
        if builtin_info:
            is_frontend = builtin_info.category == 'frontend'
            return NodeMappingResult(
                github_url=COMFY_CORE_URL,
                plugin_name='ComfyUI Core',
                is_builtin=True,
                is_frontend=is_frontend,
                category=builtin_info.category
            )
        
        github_url = self._preemption_map.get(node_type)
        if github_url:
            info = self._plugin_info.get(github_url)
            return NodeMappingResult(
                github_url=github_url,
                plugin_name=info.name if info else self._get_name_from_url(github_url),
                is_builtin=(github_url == COMFY_CORE_URL)
            )
        
        github_urls = self._rext_map.get(node_type)
        if github_urls:
            github_url = github_urls[0]
            info = self._plugin_info.get(github_url)
            return NodeMappingResult(
                github_url=github_url,
                plugin_name=info.name if info else self._get_name_from_url(github_url),
                is_builtin=False
            )
        
        for pattern, github_url in self._patterns:
            try:
                if re.search(pattern, node_type):
                    info = self._plugin_info.get(github_url)
                    return NodeMappingResult(
                        github_url=github_url,
                        plugin_name=info.name if info else self._get_name_from_url(github_url),
                        is_builtin=False
                    )
            except re.error:
                continue
        
        return NodeMappingResult(
            github_url='',
            plugin_name='Unknown',
            is_builtin=False
        )
    
    def resolve_cnr_id(self, cnr_id: str) -> Optional[str]:
        """
        通过 ComfyRegistry ID 解析 GitHub URL
        
        工作流中的节点可能包含 cnr_id 属性（如 "prompt-assistant"），
        通过此方法可以找到对应的 GitHub URL。
        
        Args:
            cnr_id: ComfyRegistry ID
            
        Returns:
            GitHub URL，未找到返回 None
        """
        if cnr_id == 'comfy-core':
            return COMFY_CORE_URL
        
        return self._cnr_id_map.get(cnr_id)
    
    def _get_name_from_url(self, github_url: str) -> str:
        """
        从 GitHub URL 提取插件名称
        
        Args:
            github_url: GitHub URL
            
        Returns:
            插件名称
        """
        if github_url == COMFY_CORE_URL:
            return 'ComfyUI Core'
        
        parts = github_url.rstrip('/').split('/')
        if len(parts) >= 1:
            return parts[-1]
        
        return 'Unknown Plugin'
    
    def get_plugin_info(self, github_url: str) -> Optional[PluginInfo]:
        """
        获取插件信息
        
        Args:
            github_url: 插件的 GitHub URL
            
        Returns:
            PluginInfo 对象，未找到返回 None
        """
        normalized = normalize_github_url(github_url)
        return self._plugin_info.get(normalized)
    
    def scan_local_plugins(self, custom_nodes_path: str) -> Dict[str, Dict[str, Any]]:
        """
        扫描本地 custom_nodes 目录，获取已安装插件列表
        
        Args:
            custom_nodes_path: custom_nodes 目录路径
            
        Returns:
            {github_url: {name, path, enabled}} 字典
        """
        logger.info(f"[scan_local_plugins] 开始扫描，路径: {custom_nodes_path}")
        logger.info(f"[scan_local_plugins] 扫描前 _local_plugins 数量: {len(self._local_plugins)}")
        
        self._local_plugins.clear()
        
        custom_nodes_dir = Path(custom_nodes_path)
        if not custom_nodes_dir.exists():
            logger.warning(f"[scan_local_plugins] custom_nodes 目录不存在: {custom_nodes_path}")
            return {}
        
        scanned_dirs = 0
        for item in custom_nodes_dir.iterdir():
            if item.name in ('__pycache__', '.disabled'):
                continue
            
            if item.is_dir():
                scanned_dirs += 1
                is_disabled = item.name.endswith('.disabled')
                plugin_name = item.name.replace('.disabled', '')
                
                github_url = self._get_github_url_from_git(item)
                
                if github_url:
                    normalized_url = normalize_github_url(github_url)
                    self._local_plugins[normalized_url] = {
                        'name': plugin_name,
                        'path': str(item),
                        'enabled': not is_disabled,
                        'github_url': normalized_url
                    }
                    logger.debug(f"[scan_local_plugins] 发现插件: {plugin_name} -> {normalized_url}")
                else:
                    fallback_url = f"local://{plugin_name}"
                    self._local_plugins[fallback_url] = {
                        'name': plugin_name,
                        'path': str(item),
                        'enabled': not is_disabled,
                        'github_url': ''
                    }
                    logger.debug(f"[scan_local_plugins] 发现本地插件(无git): {plugin_name}")
        
        disabled_dir = custom_nodes_dir / '.disabled'
        if disabled_dir.exists():
            logger.info(f"[scan_local_plugins] 扫描 .disabled 目录")
            for item in disabled_dir.iterdir():
                if item.name in ('__pycache__',):
                    continue
                
                if item.is_dir():
                    scanned_dirs += 1
                    plugin_name = item.name
                    github_url = self._get_github_url_from_git(item)
                    
                    if github_url:
                        normalized_url = normalize_github_url(github_url)
                        self._local_plugins[normalized_url] = {
                            'name': plugin_name,
                            'path': str(item),
                            'enabled': False,
                            'github_url': normalized_url
                        }
                    else:
                        fallback_url = f"local://{plugin_name}"
                        self._local_plugins[fallback_url] = {
                            'name': plugin_name,
                            'path': str(item),
                            'enabled': False,
                            'github_url': ''
                        }
        
        logger.info(f"[scan_local_plugins] 扫描完成: 扫描了 {scanned_dirs} 个目录，发现 {len(self._local_plugins)} 个插件")
        return self._local_plugins
    
    def _get_github_url_from_git(self, plugin_path: Path) -> Optional[str]:
        """
        从 .git/config 获取 GitHub URL
        
        Args:
            plugin_path: 插件目录路径
            
        Returns:
            GitHub URL，未找到返回 None
        """
        import configparser
        
        git_config_path = plugin_path / '.git' / 'config'
        if not git_config_path.exists():
            return None
        
        try:
            config = configparser.ConfigParser(strict=False)
            config.read(git_config_path)
            
            for section in config.sections():
                if section.startswith('remote '):
                    url = config.get(section, 'url', fallback=None)
                    if url:
                        return normalize_github_url(url)
        except Exception as e:
            logger.debug(f"读取 git config 失败: {plugin_path}, {e}")
        
        return None
    
    def check_plugin_status(self, github_url: str, plugin_name: str = None) -> str:
        """
        检查插件安装状态
        
        Args:
            github_url: 插件的 GitHub URL
            plugin_name: 插件名称（用于查找本地插件）
            
        Returns:
            状态: 'installed' | 'disabled' | 'missing' | 'unknown'
        """
        normalized = normalize_github_url(github_url)
        
        # ComfyUI Core 是内置的，始终显示为已安装
        if normalized == COMFY_CORE_URL:
            logger.debug(f"[check_plugin_status] ComfyUI Core 内置，返回 installed")
            return 'installed'
        
        if not self._local_plugins:
            logger.debug(f"[check_plugin_status] _local_plugins 为空，返回 missing（未找到插件）")
            return 'missing'
        
        logger.debug(f"[check_plugin_status] _local_plugins 包含 {len(self._local_plugins)} 个插件")
        logger.debug(f"[check_plugin_status] 查找: github_url={normalized}, plugin_name={plugin_name}")
        
        # 优先通过 GitHub URL 查找
        if normalized and normalized in self._local_plugins:
            logger.debug(f"[check_plugin_status] GitHub URL 精确匹配: {normalized}")
            return 'installed' if self._local_plugins[normalized]['enabled'] else 'disabled'
        
        # 如果 GitHub URL 为空，通过 plugin_name 查找本地插件
        if plugin_name:
            for url, info in self._local_plugins.items():
                if info.get('name') == plugin_name:
                    logger.debug(f"[check_plugin_status] 通过 plugin_name 匹配: {plugin_name}")
                    return 'installed' if info['enabled'] else 'disabled'
        
        # 尝试精确匹配（忽略 .git 后缀）
        if normalized:
            normalized_stripped = normalized.rstrip('.git')
            for url, info in self._local_plugins.items():
                url_stripped = url.rstrip('.git')
                if normalized_stripped == url_stripped:
                    logger.debug(f"[check_plugin_status] 去除.git后匹配: {normalized_stripped}")
                    return 'installed' if info['enabled'] else 'disabled'
        
        logger.debug(f"[check_plugin_status] 未找到匹配，返回 missing")
        return 'missing'
    
    def get_all_plugins_status(self) -> Dict[str, str]:
        """
        获取所有插件的安装状态
        
        Returns:
            {github_url: status} 字典
        """
        return {
            github_url: self.check_plugin_status(github_url)
            for github_url in self._plugin_info
        }
    
    def get_cache_data(self) -> Dict[str, Any]:
        """
        获取缓存数据（用于前端 API）
        
        Returns:
            包含映射表信息的字典
        """
        return {
            "preemption_map": self._preemption_map,
            "rext_map": self._rext_map,
            "patterns": self._patterns,
            "plugin_info": {
                url: {
                    'name': info.name,
                    'github_url': info.github_url,
                    'node_count': len(info.nodes)
                }
                for url, info in self._plugin_info.items()
            },
            "builtin_nodes": {
                node_type: {
                    'category': info.category,
                    'display_name': info.display_name,
                    'description': info.description
                }
                for node_type, info in self._builtin_nodes.items()
            },
            "local_plugins": {
                url: {
                    'name': info['name'],
                    'github_url': info['github_url'],
                    'enabled': info['enabled']
                }
                for url, info in self._local_plugins.items()
                if not url.startswith('local://')
            },
            "timestamp": self._last_update_time,
            "cnr_id_map": self._cnr_id_map,
            "stats": {
                "preemption_count": len(self._preemption_map),
                "rext_count": len(self._rext_map),
                "pattern_count": len(self._patterns),
                "plugin_count": len(self._plugin_info),
                "local_plugin_count": len(self._local_plugins),
                "builtin_node_count": len(self._builtin_nodes),
                "cnr_id_count": len(self._cnr_id_map)
            }
        }
    
    def set_comfyui_path(self, comfyui_path: str) -> None:
        """
        设置 ComfyUI 路径并初始化本地扫描器
        
        Args:
            comfyui_path: ComfyUI 根目录路径
        """
        self._comfyui_path = comfyui_path
        self._init_local_scanner()
    
    def _init_local_scanner(self) -> None:
        """初始化本地节点扫描器"""
        if not self._comfyui_path:
            return
        
        try:
            from backend.src.core.workflow.local_node_scanner import LocalNodeScanner
            self._local_scanner = LocalNodeScanner(self._comfyui_path)
            logger.debug(f"本地节点扫描器初始化完成: {self._comfyui_path}")
        except Exception as e:
            logger.error(f"初始化本地节点扫描器失败: {e}")
            self._local_scanner = None
    
    def scan_local_nodes(self, force: bool = False) -> Dict[str, Any]:
        """
        扫描本地节点
        
        Args:
            force: 是否强制重新扫描
            
        Returns:
            扫描结果字典
        """
        # 检查是否正在扫描
        if self._is_scanning:
            logger.info("已有扫描任务在进行中，跳过重复扫描")
            # 返回已有的缓存结果
            if self._local_node_map:
                return {
                    "success": True,
                    "from_cache": True,
                    "pluginCount": len(self._local_node_map.plugins) if self._local_node_map else 0,
                    "nodeCount": len(self._local_node_map.nodes) if self._local_node_map else 0
                }
            return {"success": False, "error": "扫描进行中"}
        
        if not self._local_scanner:
            return {
                "success": False,
                "error": "本地扫描器未初始化，请先设置 ComfyUI 路径"
            }
        
        self._is_scanning = True
        
        try:
            node_map, result = self._local_scanner.scan(force=force)
            self._local_node_map = node_map
            
            return {
                "success": result.success,
                "pluginCount": result.plugin_count,
                "nodeCount": result.node_count,
                "v1Count": result.v1_count,
                "v3Count": result.v3_count,
                "frontendCount": result.frontend_count,
                "elapsedSeconds": result.elapsed_seconds,
                "error": result.error
            }
        except Exception as e:
            logger.error(f"扫描本地节点失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            self._is_scanning = False
    
    def get_local_node_map(self) -> Optional[Dict[str, Any]]:
        """
        获取本地节点映射表
        
        Returns:
            本地节点映射表字典
        """
        if self._local_node_map:
            return self._local_node_map.to_dict()
        
        if self._local_scanner:
            cached = self._local_scanner.get_cached()
            if cached:
                self._local_node_map = cached
                return cached.to_dict()
        
        return None
    
    def resolve_node_with_local(self, node_type: str) -> NodeMappingResult:
        """
        解析节点类型到插件（优先使用本地映射表）
        
        匹配逻辑：
        1. 首先检查内置节点
        2. 然后检查本地映射表（V1/V3/前端节点）
        3. 然后检查 preemption_map（优先级覆盖）
        4. 然后检查 rext_map（精确匹配）
        5. 最后尝试正则模式匹配
        
        Args:
            node_type: 节点类型
            
        Returns:
            NodeMappingResult 对象
        """
        builtin_info = self._builtin_nodes.get(node_type)
        if builtin_info:
            is_frontend = builtin_info.category == 'frontend'
            return NodeMappingResult(
                github_url=COMFY_CORE_URL,
                plugin_name='ComfyUI Core',
                is_builtin=True,
                is_frontend=is_frontend,
                category=builtin_info.category
            )
        
        if self._local_node_map:
            local_info = self._local_node_map.nodes.get(node_type)
            if local_info:
                return NodeMappingResult(
                    github_url=local_info.github_url,
                    plugin_name=local_info.plugin_name,
                    is_builtin=False,
                    is_frontend=(local_info.node_type == 'frontend')
                )
        
        return self.resolve_node(node_type)
    
    def get_local_scan_status(self) -> Dict[str, Any]:
        """
        获取本地扫描状态
        
        Returns:
            状态字典
        """
        if not self._local_scanner:
            return {
                "initialized": False,
                "hasCache": False,
                "needsRescan": True,
                "comfyuiPath": self._comfyui_path
            }
        
        return {
            "initialized": True,
            "hasCache": self._local_scanner.get_cached() is not None,
            "needsRescan": self._local_scanner.cache_manager.needs_rescan(),
            "comfyuiPath": self._comfyui_path
        }


node_mapper = NodeMapper()
