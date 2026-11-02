"""
插件数据获取器

负责从不同数据源获取插件信息：
- GitHub 统计数据（https://raw.githubusercontent.com/Comfy-Org/ComfyUI-Manager/refs/heads/main/github-stats.json）
- 自定义节点列表（https://raw.githubusercontent.com/Comfy-Org/ComfyUI-Manager/refs/heads/main/custom-node-list.json）
- 节点映射表（https://raw.githubusercontent.com/Comfy-Org/ComfyUI-Manager/refs/heads/main/extension-node-map.json）

实现三数据源合并策略和数据映射功能。
"""

import requests
import json
import time
from typing import Optional, List, Dict, Tuple
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from .logger import marketplace_logger
from .constants import (
    GITHUB_STATS_URL,
    CUSTOM_NODE_LIST_URL,
    NODE_MAP_URL,
    COMFYUI_API_URL,
    REQUEST_TIMEOUT,
    ERROR_NETWORK_FAILED,
    ERROR_DATA_PARSE_FAILED,
    NODE_TYPE_MAP_CACHE_FILE,
    get_cache_dir
)


class PluginDataFetcher:
    """
    插件数据获取器
    
    从三个数据源获取插件数据并合并：
    1. GitHub 统计数据（包含下载量和星标）
    2. 自定义节点列表（包含插件基本信息）
    3. 节点映射表（包含节点数量）
    
    实现三数据源合并策略，全量获取所有插件数据。
    """
    
    def __init__(self, cache_dir: Optional[Path] = None, settings_manager=None):
        """
        初始化数据获取器

        Args:
            cache_dir: 缓存目录路径（预留参数，当前未使用）
            settings_manager: 设置管理器，用于获取 GitHub API Token
        """
        self._cache_dir = cache_dir
        self._settings_manager = settings_manager
        self.node_map: Optional[Dict[str, int]] = None
        self.github_stats: Optional[Dict[str, Dict]] = None
        self.custom_node_list: Optional[List[Dict]] = None
        self.comfyui_api_data: Optional[List[Dict]] = None
        self._node_type_map: Optional[Dict[str, str]] = None
        self._plugin_info_map: Dict[str, Dict] = {}
        marketplace_logger.debug("插件数据获取器已初始化")
    
    def _get_proxy_candidates(self) -> List[Optional[str]]:
        """
        获取代理候选列表（应用代理 → 系统代理 → 直连）

        VPN 客户端开启"系统代理"时只写注册表、不设环境变量，
        requests 默认读不到，必须显式兜底，否则应用内请求全部超时。
        """
        try:
            if not self._settings_manager:
                from backend.src.core.settings_manager import SettingsManager
                self._settings_manager = SettingsManager()
            from backend.src.utils.proxy_helper import get_proxy_candidates
            return get_proxy_candidates(self._settings_manager)
        except Exception as e:
            marketplace_logger.debug(f"[PluginDataFetcher] 解析代理链路失败: {e}")
            return [None]

    def _http_get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = REQUEST_TIMEOUT,
    ) -> requests.Response:
        """
        带链路回退的 GET 请求

        依次尝试 应用代理 → 系统代理 → 直连，返回第一个成功（2xx）的响应。
        全部失败时抛出最后一次的异常。
        """
        candidates = self._get_proxy_candidates()
        last_error: Optional[Exception] = None

        for proxy_url in candidates:
            proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
            try:
                response = requests.get(
                    url,
                    timeout=timeout,
                    headers=headers,
                    proxies=proxies,
                )
                response.raise_for_status()
                if proxy_url:
                    marketplace_logger.debug(
                        f"[PluginDataFetcher] 经代理 {proxy_url} 请求成功: {url}"
                    )
                return response
            except Exception as e:
                last_error = e
                if proxy_url:
                    marketplace_logger.warning(
                        f"[PluginDataFetcher] 经代理 {proxy_url} 请求失败，尝试下一条链路: {e}"
                    )

        if last_error is None:
            last_error = RuntimeError(f"没有可用的网络链路: {url}")
        raise last_error
    
    def _get_github_headers(self) -> Dict[str, str]:
        """
        获取 GitHub API 请求头，包含认证信息
        
        Returns:
            请求头字典
        """
        headers = {
            'User-Agent': 'ComfyNexus/1.0',
            'Accept': 'application/json'
        }
        
        if self._settings_manager:
            token = self._settings_manager.get_github_api_token()
            if token:
                headers['Authorization'] = f'token {token}'
                marketplace_logger.debug("[PluginDataFetcher] 使用 GitHub API Token 进行认证")
        
        return headers
    
    def _apply_mirror_to_url(self, url: str, url_type: str = "raw") -> tuple:
        """
        应用镜像加速到 URL
        
        Args:
            url: 原始 URL
            url_type: URL 类型
            
        Returns:
            (transformed_url, extra_headers)
        """
        try:
            from backend.src.utils.github_mirror import github_mirror_manager
            if github_mirror_manager.is_enabled():
                return github_mirror_manager.transform_url(url, url_type)
        except Exception:
            pass
        return url, {}
    
    def _fetch_github_stats(self) -> Optional[Dict[str, Dict]]:
        """
        从 GitHub 统计数据获取下载量和星标信息
        
        发送 HTTP GET 请求到 ComfyUI-Manager 的 GitHub raw URL，获取插件统计数据。
        数据格式：
        {
            "https://github.com/user/repo": {
                "stars": 100,
                "downloads": 1000
            }
        }
        
        Returns:
            {repository_url: stats} 字典，失败时返回 None
        """
        try:
            url, mirror_headers = self._apply_mirror_to_url(GITHUB_STATS_URL, "raw")
            marketplace_logger.debug(f"正在从 GitHub 统计数据获取插件信息: {url}")
            
            headers = self._get_github_headers()
            headers.update(mirror_headers)
            
            response = self._http_get(url, headers=headers)
            
            data = response.json()
            
            if isinstance(data, dict):
                marketplace_logger.debug(f"成功获取 GitHub 统计数据，共 {len(data)} 个插件")
                return data
            else:
                marketplace_logger.error(
                    f"GitHub 统计数据返回格式错误：期望字典，实际为 {type(data).__name__}"
                )
                return None
            
        except requests.exceptions.Timeout:
            marketplace_logger.warning(
                f"GitHub 统计数据请求超时（{REQUEST_TIMEOUT}秒）: {GITHUB_STATS_URL}"
            )
            return None
            
        except requests.exceptions.ConnectionError as e:
            marketplace_logger.warning(f"GitHub 统计数据连接失败: {e}")
            return None
            
        except requests.exceptions.HTTPError as e:
            marketplace_logger.warning(
                f"GitHub 统计数据 HTTP 错误: {e.response.status_code} - {e}"
            )
            return None
            
        except requests.exceptions.RequestException as e:
            marketplace_logger.error(f"GitHub 统计数据请求失败: {e}")
            return None
            
        except ValueError as e:
            marketplace_logger.error(f"GitHub 统计数据 JSON 解析失败: {e}")
            return None
            
        except Exception as e:
            marketplace_logger.error(f"获取 GitHub 统计数据时发生未知错误: {e}")
            return None
    
    def _fetch_custom_node_list(self) -> Optional[List[Dict]]:
        """
        从自定义节点列表获取插件基本信息
        
        发送 HTTP GET 请求到 ComfyUI-Manager 的 GitHub raw URL，获取插件列表数据。
        
        Returns:
            插件数据列表（原始格式）或 None（请求失败）
        """
        try:
            url, mirror_headers = self._apply_mirror_to_url(CUSTOM_NODE_LIST_URL, "raw")
            marketplace_logger.debug(f"正在从自定义节点列表获取插件数据: {url}")
            
            headers = self._get_github_headers()
            headers.update(mirror_headers)
            
            response = self._http_get(url, headers=headers)
            
            data = response.json()
            
            if isinstance(data, list):
                marketplace_logger.debug(f"成功从自定义节点列表获取 {len(data)} 个插件")
                return data
            elif isinstance(data, dict):
                for key in ['custom_nodes', 'nodes', 'plugins', 'data', 'items']:
                    if key in data and isinstance(data[key], list):
                        marketplace_logger.debug(f"从自定义节点列表响应的 '{key}' 字段提取到 {len(data[key])} 个插件")
                        return data[key]
                
                marketplace_logger.error(
                    f"自定义节点列表返回字典格式，但未找到插件列表字段。可用键: {list(data.keys())}"
                )
                return None
            else:
                marketplace_logger.error(
                    f"自定义节点列表返回的数据格式错误：期望列表或字典，实际为 {type(data).__name__}"
                )
                return None
            
        except requests.exceptions.Timeout:
            marketplace_logger.warning(
                f"自定义节点列表请求超时（{REQUEST_TIMEOUT}秒）: {CUSTOM_NODE_LIST_URL}"
            )
            return None
            
        except requests.exceptions.ConnectionError as e:
            marketplace_logger.warning(f"自定义节点列表连接失败: {e}")
            return None
            
        except requests.exceptions.HTTPError as e:
            marketplace_logger.warning(
                f"自定义节点列表 HTTP 错误: {e.response.status_code} - {e}"
            )
            return None
            
        except requests.exceptions.RequestException as e:
            marketplace_logger.error(f"自定义节点列表请求失败: {e}")
            return None
            
        except ValueError as e:
            marketplace_logger.error(f"自定义节点列表 JSON 解析失败: {e}")
            return None
            
        except Exception as e:
            marketplace_logger.error(f"从自定义节点列表获取数据时发生未知错误: {e}")
            return None
    
    def _fetch_node_map(self) -> Optional[Dict[str, int]]:
        """
        从 ComfyUI-Manager 获取节点映射表
        
        节点映射表的结构：
        {
            "https://github.com/user/repo": [
                ["Node1", "Node2", ...],  # 节点列表
                {"title_aux": "..."}       # 元数据
            ]
        }
        
        Returns:
            {repository_url: node_count} 字典，失败时返回 None
        """
        try:
            url, mirror_headers = self._apply_mirror_to_url(NODE_MAP_URL, "raw")
            marketplace_logger.debug(f"正在从 ComfyUI-Manager 获取节点映射表: {url}")
            
            headers = self._get_github_headers()
            headers.update(mirror_headers)
            
            response = self._http_get(url, headers=headers)
            
            # 解析 JSON 响应
            data = response.json()
            
            # 构建 {repository_url: node_count} 映射
            node_map = {}
            for repo_url, value in data.items():
                if isinstance(value, list) and len(value) > 0:
                    # value[0] 是节点列表数组
                    node_list = value[0]
                    if isinstance(node_list, list):
                        node_count = len(node_list)
                        # 标准化键：转小写，移除 .git 后缀
                        repo_key = repo_url.lower().strip()
                        if repo_key.endswith('.git'):
                            repo_key = repo_key[:-4]
                        node_map[repo_key] = node_count
            
            marketplace_logger.debug(f"成功获取节点映射表，共 {len(node_map)} 个插件")
            return node_map
            
        except requests.exceptions.Timeout:
            marketplace_logger.warning(
                f"节点映射表请求超时（{REQUEST_TIMEOUT}秒）: {NODE_MAP_URL}"
            )
            return None
            
        except requests.exceptions.ConnectionError as e:
            marketplace_logger.warning(f"节点映射表连接失败: {e}")
            return None
            
        except requests.exceptions.HTTPError as e:
            marketplace_logger.warning(
                f"节点映射表 HTTP 错误: {e.response.status_code} - {e}"
            )
            return None
            
        except requests.exceptions.RequestException as e:
            marketplace_logger.error(f"节点映射表请求失败: {e}")
            return None
            
        except ValueError as e:
            # JSON 解析错误
            marketplace_logger.error(f"节点映射表 JSON 解析失败: {e}")
            return None
            
        except Exception as e:
            marketplace_logger.error(f"获取节点映射表时发生未知错误: {e}")
            return None
    def _fetch_comfyui_api(self) -> Optional[List[Dict]]:
        """
        从 ComfyNexus 维护的 GitHub 数据源获取插件数据

        数据源为 ComfyNexus 通过 GitHub Action 定期从 ComfyUI 官方 API 拉取的 JSON 文件，
        避免直接访问官方 API 导致的限流问题。

        Returns:
            插件数据列表（原始格式）或 None（请求失败）
        """
        try:
            url, mirror_headers = self._apply_mirror_to_url(COMFYUI_API_URL, "raw")
            marketplace_logger.debug(f"正在从 ComfyNexus 数据源获取插件数据: {url}")
            
            headers = self._get_github_headers()
            headers.update(mirror_headers)
            
            response = self._http_get(url, headers=headers)
            
            data = response.json()
            
            if isinstance(data, list):
                marketplace_logger.debug(f"成功获取 {len(data)} 个插件数据")
                return data
            elif isinstance(data, dict):
                nodes = data.get('nodes', [])
                if nodes:
                    marketplace_logger.debug(f"成功获取 {len(nodes)} 个插件数据")
                    return nodes
                else:
                    marketplace_logger.warning("数据格式错误：未找到 nodes 字段")
                    return None
            else:
                marketplace_logger.warning(f"数据格式错误：期望列表或字典，实际为 {type(data)}")
                return None

        except Exception as e:
            marketplace_logger.error(f"从 ComfyNexus 数据源获取数据失败: {e}")
            return None
    
    def _get_github_stats(self, repository: str) -> Dict:
        """
        根据仓库地址获取GitHub统计数据
        
        Args:
            repository: 插件的 GitHub 仓库地址
            
        Returns:
            包含 stars、downloads 和 last_update 的字典，未找到时返回默认值
        """
        if self.github_stats is None:
            self.github_stats = self._fetch_github_stats()
            if self.github_stats is None:
                self.github_stats = {}
            else:
                # 调试：输出第一个统计数据示例
                if self.github_stats:
                    first_key = next(iter(self.github_stats))
                    first_value = self.github_stats[first_key]
                    marketplace_logger.debug(
                        f"GitHub统计数据示例 - {first_key}: {first_value}"
                    )
        
        repo_normalized = repository.lower().strip()
        if repo_normalized.endswith('.git'):
            repo_normalized = repo_normalized[:-4]
        
        if repo_normalized in self.github_stats:
            stats = self.github_stats[repo_normalized]
            result = {
                'stars': stats.get('stars', 0),
                'downloads': stats.get('downloads', 0),
                'last_update': stats.get('last_update', '')
            }
            # 调试：输出找到的统计数据
            marketplace_logger.debug(
                f"找到GitHub统计数据: {repository} -> stars={result['stars']}, "
                f"downloads={result['downloads']}, last_update={result['last_update']}"
            )
            return result
        
        if not repo_normalized.startswith('http'):
            repo_with_https = f"https://{repo_normalized}"
            if repo_with_https in self.github_stats:
                stats = self.github_stats[repo_with_https]
                result = {
                    'stars': stats.get('stars', 0),
                    'downloads': stats.get('downloads', 0),
                    'last_update': stats.get('last_update', '')
                }
                # 调试：输出找到的统计数据
                marketplace_logger.debug(
                    f"找到GitHub统计数据（添加https）: {repository} -> stars={result['stars']}, "
                    f"downloads={result['downloads']}, last_update={result['last_update']}"
                )
                return result
        
        # 未找到统计数据
        marketplace_logger.debug(f"未找到GitHub统计数据: {repository}")
        return {'stars': 0, 'downloads': 0, 'last_update': ''}

    def _get_node_count(self, repository: str) -> int:
        """
        根据仓库地址获取节点数量
        
        Args:
            repository: 插件的 GitHub 仓库地址
            
        Returns:
            节点数量，未找到时返回 0
        """
        # 懒加载节点映射表
        if self.node_map is None:
            self.node_map = self._fetch_node_map()
            if self.node_map is None:
                self.node_map = {}  # 设置为空字典，避免重复请求
        
        # 标准化仓库地址（移除 .git 后缀，统一为 https://）
        repo_normalized = repository.lower().strip()
        if repo_normalized.endswith('.git'):
            repo_normalized = repo_normalized[:-4]
        
        # 尝试直接匹配
        if repo_normalized in self.node_map:
            node_count = self.node_map[repo_normalized]
            marketplace_logger.debug(f"找到节点数量: {repository} -> {node_count}")
            return node_count
        
        # 尝试添加 https:// 前缀匹配
        if not repo_normalized.startswith('http'):
            repo_with_https = f"https://{repo_normalized}"
            if repo_with_https in self.node_map:
                node_count = self.node_map[repo_with_https]
                marketplace_logger.debug(f"找到节点数量（添加https）: {repository} -> {node_count}")
                return node_count
        
        # 未找到，记录日志
        marketplace_logger.debug(f"未找到节点数量: {repository}")
        return 0
    def _normalize_repository_url(self, url: str) -> str:
        """
        标准化仓库 URL，用于去重比对

        Args:
            url: 原始仓库 URL

        Returns:
            标准化后的 URL（小写，移除 .git 后缀，统一 https://）
        """
        if not url:
            return ""

        # 转小写并去除首尾空格
        normalized = url.lower().strip()

        # 移除 .git 后缀
        if normalized.endswith('.git'):
            normalized = normalized[:-4]

        # 确保以 https:// 开头
        if not normalized.startswith('http'):
            normalized = f"https://{normalized}"

        return normalized

    def _map_api_data_to_standard_format(self, api_item: Dict) -> Optional[Dict]:
        """
        将 ComfyUI API 数据映射到标准格式

        Args:
            api_item: API 返回的单个插件数据

        Returns:
            标准格式的插件数据，或 None（数据无效）
        """
        try:
            # 尝试提取仓库地址（可能的字段名）
            repository = (
                api_item.get('repository') or
                api_item.get('repo') or
                api_item.get('github_url') or
                api_item.get('url') or
                api_item.get('reference') or
                ''
            )

            if not repository:
                marketplace_logger.debug(f"API 数据缺少仓库地址，跳过: {api_item.get('name', 'Unknown')}")
                return None

            # 提取其他字段，确保类型安全
            # 处理 name 字段（可能是字符串或对象）
            name_raw = api_item.get('name') or api_item.get('title')
            if isinstance(name_raw, dict):
                # 如果 name 是字典，尝试提取常见的字段
                name = str(name_raw.get('en') or name_raw.get('zh') or name_raw.get('default') or '未知插件')
            elif name_raw:
                name = str(name_raw)
            else:
                name = '未知插件'
            
            description = str(api_item.get('description') or api_item.get('desc') or '暂无描述')
            
            # 处理 author 字段（可能是字符串或对象）
            author_raw = api_item.get('author') or api_item.get('publisher')
            if isinstance(author_raw, dict):
                # 如果 author 是字典，尝试提取 name 或 id 字段
                author = str(author_raw.get('name') or author_raw.get('id') or '')
            elif author_raw:
                author = str(author_raw)
            else:
                author = ''
            
            # 从 GitHub 统计数据获取星标数和下载量
            github_stats = self._get_github_stats(repository)
            
            # 优先使用 API 数据的 github_stars，如果没有则使用 GitHub 统计数据
            try:
                stars = int(api_item.get('github_stars') or 0) or github_stats.get('stars', 0)
            except (ValueError, TypeError):
                stars = github_stats.get('stars', 0)
            
            try:
                downloads = int(api_item.get('downloads') or 0) or github_stats.get('downloads', 0)
            except (ValueError, TypeError):
                downloads = github_stats.get('downloads', 0)
            
            # 节点数：从节点映射表获取（API 数据中没有此字段）
            node_count = self._get_node_count(repository)
            
            # 更新时间：优先使用 latest_version.createdAt，其次 created_at，最后使用 GitHub 统计数据
            latest_version = api_item.get('latest_version')
            if latest_version and isinstance(latest_version, dict):
                updated_at = str(latest_version.get('createdAt', '') or api_item.get('created_at', '') or github_stats.get('last_update', '') or '')
            else:
                updated_at = str(api_item.get('created_at', '') or github_stats.get('last_update', '') or '')
            
            # 确保 tags 是列表
            tags = api_item.get('tags') or []
            if not isinstance(tags, list):
                tags = []

            return {
                'name': name,
                'description': description,
                'repository': str(repository),
                'version_tag': '未知版本',
                'updated_at': updated_at,
                'node_count': node_count,
                'author': author,
                'stars': stars,
                'downloads': downloads,
                'tags': tags,
                'is_installed': False,
                'source': 'api'  # 标记数据来源
            }

        except Exception as e:
            marketplace_logger.warning(f"映射 API 数据时发生错误，跳过该项: {e}")
            return None

    def _merge_two_data_sources(
        self,
        local_plugins: List[Dict],
        api_plugins: Optional[List[Dict]]
    ) -> List[Dict]:
        """
        合并本地数据和 API 数据，去重并排序

        合并策略：
        1. 使用 repository URL 作为唯一标识
        2. API 数据优先级更高（覆盖本地数据）
        3. 按星标数倒序排序

        Args:
            local_plugins: 本地数据（三数据源合并后）
            api_plugins: API 数据（原始格式）

        Returns:
            合并去重后的插件列表
        """
        marketplace_logger.debug("=" * 80)
        marketplace_logger.debug("开始合并本地数据和 API 数据")
        marketplace_logger.debug(f"输入 - 本地插件数: {len(local_plugins)}, API 插件数: {len(api_plugins) if api_plugins else 0}")

        # 使用字典进行去重，key 为标准化的 repository URL
        merged_dict: Dict[str, Dict] = {}

        # 1. 先添加本地数据
        for plugin in local_plugins:
            repo_key = self._normalize_repository_url(plugin.get('repository', ''))
            if repo_key:
                plugin['source'] = 'local'
                merged_dict[repo_key] = plugin

        marketplace_logger.debug(f"步骤1完成 - 本地数据: {len(merged_dict)} 个插件")

        # 2. 处理 API 数据
        if api_plugins:
            # 预先加载 GitHub 统计数据（避免在映射每个插件时重复加载）
            if self.github_stats is None:
                marketplace_logger.debug("预加载 GitHub 统计数据...")
                self.github_stats = self._fetch_github_stats()
                if self.github_stats is None:
                    self.github_stats = {}
                    marketplace_logger.warning("GitHub 统计数据加载失败，API 插件将缺少星标和更新时间")
                else:
                    marketplace_logger.debug(f"GitHub 统计数据加载成功，共 {len(self.github_stats)} 个插件")
            
            # 预先加载节点映射表
            if self.node_map is None:
                marketplace_logger.debug("预加载节点映射表...")
                self.node_map = self._fetch_node_map()
                if self.node_map is None:
                    self.node_map = {}
                    marketplace_logger.warning("节点映射表加载失败，API 插件将缺少节点数量")
                else:
                    marketplace_logger.debug(f"节点映射表加载成功，共 {len(self.node_map)} 个插件")
            api_count = 0
            override_count = 0
            api_skipped = 0

            for api_item in api_plugins:
                # 映射到标准格式
                mapped_item = self._map_api_data_to_standard_format(api_item)

                if mapped_item:
                    repo_key = self._normalize_repository_url(mapped_item.get('repository', ''))

                    if repo_key:
                        # API 数据覆盖本地数据
                        if repo_key in merged_dict:
                            override_count += 1
                            marketplace_logger.debug(f"API 数据覆盖本地数据: {mapped_item['name']}")

                        merged_dict[repo_key] = mapped_item
                        api_count += 1
                    else:
                        api_skipped += 1
                else:
                    api_skipped += 1

            marketplace_logger.debug(
                f"步骤2完成 - API 数据: {api_count} 个有效插件，覆盖 {override_count} 个本地数据，跳过 {api_skipped} 个无效数据"
            )
        else:
            marketplace_logger.warning("API 数据为空，仅使用本地数据")

        # 3. 转换为列表并过滤屏蔽插件
        merged_list = list(merged_dict.values())
        
        # 屏蔽列表（不区分大小写）
        blocked_plugins = {'comfyui', 'comfyui-manager'}
        
        # 过滤掉屏蔽的插件
        filtered_list = []
        prompt_assistant = None
        blocked_count = 0
        
        for plugin in merged_list:
            plugin_name = str(plugin.get('name', '')).lower().strip()
            
            # 检查是否在屏蔽列表中
            if plugin_name in blocked_plugins:
                blocked_count += 1
                marketplace_logger.debug(f"屏蔽插件: {plugin.get('name')}")
                continue
            
            # 特殊处理：Prompt Assistant 置顶
            if plugin_name == 'prompt assistant':
                prompt_assistant = plugin
                marketplace_logger.debug(f"找到 Prompt Assistant 插件，将置顶显示")
            else:
                filtered_list.append(plugin)
        
        # 按星标数排序
        filtered_list.sort(key=lambda x: x.get('stars', 0), reverse=True)
        
        # 如果找到 Prompt Assistant，将其放在第一位
        if prompt_assistant:
            filtered_list.insert(0, prompt_assistant)
        
        marketplace_logger.debug(
            f"数据合并完成 - 最终结果: {len(filtered_list)} 个插件"
            f"（已屏蔽 {blocked_count} 个，Prompt Assistant 置顶，其余按星标数排序）"
        )
        marketplace_logger.debug("=" * 80)

        return filtered_list
    
    def _merge_and_map_data(self, custom_node_list: List[Dict]) -> List[Dict]:
        """
        合并三个数据源并映射到统一格式
        
        将自定义节点列表、GitHub统计数据和节点映射表合并到统一的插件数据结构。
        
        Args:
            custom_node_list: 自定义节点列表数据
            
        Returns:
            映射后的统一格式数据列表
        """
        marketplace_logger.debug(f"开始合并三个数据源，共 {len(custom_node_list)} 个插件")
        
        mapped_data = []
        skipped_count = 0
        skipped_names = []
        
        for idx, item in enumerate(custom_node_list):
            try:
                repository = item.get('reference', '')
                if not repository and 'files' in item and len(item['files']) > 0:
                    repository = item['files'][0]
                
                if not repository:
                    skipped_count += 1
                    plugin_name = item.get('title', '未知插件')
                    skipped_names.append(plugin_name)
                    marketplace_logger.debug(f"跳过插件（缺少 repository）: {plugin_name}")
                    continue
                
                node_count = self._get_node_count(repository)
                github_stats = self._get_github_stats(repository)
                
                # 调试：输出第一个插件的完整数据
                if idx == 0:
                    marketplace_logger.info(
                        f"第一个插件数据示例 - "
                        f"name={item.get('title')}, "
                        f"repository={repository}, "
                        f"github_stats={github_stats}"
                    )
                
                # 确保所有字段都是正确的类型
                # 处理 name 字段（可能是字符串或对象）
                name_raw = item.get('title')
                if isinstance(name_raw, dict):
                    # 如果 name 是字典，尝试提取常见的字段
                    name = str(name_raw.get('en') or name_raw.get('zh') or name_raw.get('default') or '未知插件')
                elif name_raw:
                    name = str(name_raw)
                else:
                    name = '未知插件'
                
                description = str(item.get('description', '暂无描述'))
                author = str(item.get('author', ''))
                updated_at = str(github_stats.get('last_update', ''))
                
                # 确保数字类型
                try:
                    stars = int(github_stats.get('stars', 0))
                except (ValueError, TypeError):
                    stars = 0
                
                try:
                    downloads = int(github_stats.get('downloads', 0))
                except (ValueError, TypeError):
                    downloads = 0
                
                try:
                    node_count = int(node_count)
                except (ValueError, TypeError):
                    node_count = 0
                
                # 确保 tags 是列表
                tags = item.get('tags', [])
                if not isinstance(tags, list):
                    tags = []
                
                mapped_item = {
                    'name': name,
                    'description': description,
                    'repository': str(repository),
                    'version_tag': '未知版本',
                    'updated_at': updated_at,
                    'node_count': node_count,
                    'author': author,
                    'stars': stars,
                    'downloads': downloads,
                    'tags': tags,
                    'is_installed': False
                }
                
                # 调试：输出第一个映射后的数据
                if idx == 0:
                    marketplace_logger.info(
                        f"第一个映射后的数据 - "
                        f"name={mapped_item['name']}, "
                        f"updated_at={mapped_item['updated_at']}, "
                        f"stars={mapped_item['stars']}"
                    )
                
                mapped_data.append(mapped_item)
                
            except Exception as e:
                marketplace_logger.warning(
                    f"合并数据项时发生错误，跳过该项: {e}, 插件名: {item.get('title', '未知')}"
                )
                continue
        
        marketplace_logger.debug(
            f"成功合并三个数据源，共 {len(mapped_data)} 个插件，跳过 {skipped_count} 个（缺少 repository）"
        )
        
        if skipped_count > 0 and skipped_count <= 10:
            marketplace_logger.debug(f"跳过的插件列表: {', '.join(skipped_names)}")
        elif skipped_count > 10:
            marketplace_logger.debug(f"跳过的插件列表（前10个）: {', '.join(skipped_names[:10])}")
        
        # 屏蔽列表（不区分大小写）
        blocked_plugins = {'comfyui', 'comfyui-manager'}
        
        # 过滤掉屏蔽的插件
        filtered_data = []
        prompt_assistant = None
        blocked_count = 0
        
        for plugin in mapped_data:
            plugin_name = str(plugin.get('name', '')).lower().strip()
            
            # 检查是否在屏蔽列表中
            if plugin_name in blocked_plugins:
                blocked_count += 1
                marketplace_logger.debug(f"屏蔽插件: {plugin.get('name')}")
                continue
            
            # 特殊处理：Prompt Assistant 置顶
            if plugin_name == 'prompt assistant':
                prompt_assistant = plugin
                marketplace_logger.debug(f"找到 Prompt Assistant 插件，将置顶显示")
            else:
                filtered_data.append(plugin)
        
        # 按星标数排序
        filtered_data.sort(key=lambda x: x.get('stars', 0), reverse=True)
        
        # 如果找到 Prompt Assistant，将其放在第一位
        if prompt_assistant:
            filtered_data.insert(0, prompt_assistant)
        
        marketplace_logger.debug(
            f"已屏蔽 {blocked_count} 个插件，Prompt Assistant 置顶，其余按星标数排序"
        )
        
        return filtered_data
    
    def fetch_plugins(self, force_refresh: bool = False) -> List[Dict]:
        """
        获取插件列表（双数据源合并策略）

        实现双数据源合并策略：
        1. 获取本地数据（三数据源合并：自定义节点列表 + GitHub 统计 + 节点映射）
        2. 获取 ComfyUI 官方 API 数据（最准确）
        3. 合并两个数据源，API 数据优先
        4. 去重（使用 repository URL）
        5. 按星标数倒序排序

        Args:
            force_refresh: 是否强制刷新（清除实例缓存）

        实现细节：
        - 并行获取两个数据源
        - API 数据失败时降级到仅使用本地数据
        - 记录所有尝试和失败的日志
        - 映射数据到统一格式

        Returns:
            插件数据列表（统一格式），失败时返回空列表
        """
        marketplace_logger.debug("=" * 80)
        marketplace_logger.debug(f"开始获取插件列表（双数据源合并策略），force_refresh={force_refresh}")

        # 如果强制刷新，清除实例缓存
        if force_refresh:
            marketplace_logger.debug("强制刷新：清除实例缓存")
            self.github_stats = None
            self.custom_node_list = None
            self.node_map = None
            self.comfyui_api_data = None

        # 1. 获取本地数据（三数据源合并）
        marketplace_logger.debug("步骤1: 获取本地数据（custom-node-list.json）")
        custom_node_list = self._fetch_custom_node_list()

        if custom_node_list is None:
            marketplace_logger.error("本地数据获取失败")
            local_plugins = []
        else:
            marketplace_logger.debug(f"成功获取本地数据，原始数据共 {len(custom_node_list)} 个插件")
            local_plugins = self._merge_and_map_data(custom_node_list)
            marketplace_logger.debug(f"本地数据映射完成，有效插件 {len(local_plugins)} 个")

        # 2. 获取 ComfyUI API 数据
        marketplace_logger.debug("步骤2: 获取 ComfyUI API 数据")
        api_plugins = self._fetch_comfyui_api()

        if api_plugins is None:
            marketplace_logger.warning("API 数据获取失败，仅使用本地数据")
        else:
            marketplace_logger.debug(f"成功获取 API 数据，原始数据共 {len(api_plugins)} 个插件")

        # 3. 合并两个数据源
        marketplace_logger.debug("步骤3: 合并两个数据源")
        if not local_plugins and not api_plugins:
            marketplace_logger.error("所有数据源均获取失败，返回空列表")
            return []

        merged_plugins = self._merge_two_data_sources(local_plugins, api_plugins)

        marketplace_logger.debug(
            f"插件列表获取完成，最终返回 {len(merged_plugins)} 个插件"
        )
        marketplace_logger.debug("=" * 80)

        return merged_plugins
    
    def _fetch_full_node_map(self) -> Optional[Dict[str, List[str]]]:
        """
        从 ComfyUI-Manager 获取完整的节点映射表（包含节点列表）
        
        节点映射表的结构：
        {
            "https://github.com/user/repo": [
                ["Node1", "Node2", ...],  # 节点列表
                {"title_aux": "..."}       # 元数据
            ]
        }
        
        Returns:
            {repository_url: [node_type1, node_type2, ...]} 字典，失败时返回 None
        """
        try:
            marketplace_logger.debug(f"正在从 ComfyUI-Manager 获取完整节点映射表: {NODE_MAP_URL}")
            
            response = self._http_get(NODE_MAP_URL, headers=self._get_github_headers())
            
            data = response.json()
            
            full_node_map = {}
            for repo_url, value in data.items():
                if isinstance(value, list) and len(value) > 0:
                    node_list = value[0]
                    if isinstance(node_list, list):
                        repo_key = repo_url.lower().strip()
                        if repo_key.endswith('.git'):
                            repo_key = repo_key[:-4]
                        full_node_map[repo_key] = node_list
            
            marketplace_logger.debug(f"成功获取完整节点映射表，共 {len(full_node_map)} 个插件")
            return full_node_map
            
        except Exception as e:
            marketplace_logger.error(f"获取完整节点映射表时发生错误: {e}")
            return None
    
    def build_node_type_map(self, cache_path: Optional[Path] = None) -> Dict[str, str]:
        """
        构建节点类型到插件ID的反向映射表
        
        Args:
            cache_path: 缓存文件路径（可选）
            
        Returns:
            {node_type: plugin_id} 字典
        """
        marketplace_logger.info("开始构建节点类型到插件的映射表...")
        
        full_node_map = self._fetch_full_node_map()
        if not full_node_map:
            marketplace_logger.warning("获取完整节点映射表失败，返回空映射")
            return {}
        
        node_to_plugin: Dict[str, str] = {}
        plugin_info: Dict[str, Dict] = {}
        
        # 1. 首先添加 ComfyUI Core 的节点（从 extension-node-map.json 中提取）
        comfy_core_url = "https://github.com/comfyanonymous/comfyui"  # 小写，与 _fetch_full_node_map 保持一致
        comfy_core_nodes = full_node_map.get(comfy_core_url, [])
        if comfy_core_nodes:
            node_types = comfy_core_nodes[0] if isinstance(comfy_core_nodes, list) and len(comfy_core_nodes) > 0 else []
            for node_type in node_types:
                if node_type and isinstance(node_type, str):
                    node_to_plugin[node_type] = "comfy-core"
                    node_to_plugin[node_type.lower()] = "comfy-core"
            marketplace_logger.info(f"添加 ComfyUI Core 节点：{len(node_types)} 个")
        
        # 2. 添加第三方插件节点
        for repo_url, node_types in full_node_map.items():
            # 跳过 ComfyUI Core（已处理）
            if 'comfyanonymous/comfyui' in repo_url.lower():
                continue
            
            plugin_ids = self._extract_all_plugin_ids(repo_url)
            primary_id = plugin_ids[0] if plugin_ids else self._extract_plugin_id(repo_url)
            
            plugin_info[primary_id] = {
                "name": self._extract_plugin_name(repo_url),
                "github_url": repo_url
            }
            
            for node_type in node_types:
                if node_type and isinstance(node_type, str):
                    # 跳过已经被标记为 comfy-core 的节点（优先级更高）
                    if node_type in node_to_plugin and node_to_plugin[node_type] == "comfy-core":
                        continue
                    if node_type.lower() in node_to_plugin and node_to_plugin[node_type.lower()] == "comfy-core":
                        continue
                    node_to_plugin[node_type] = primary_id
                    node_to_plugin[node_type.lower()] = primary_id
        
        marketplace_logger.info(
            f"节点类型映射表构建完成: {len(node_to_plugin)} 个节点类型, {len(plugin_info)} 个插件"
        )
        
        if cache_path:
            self._save_node_type_map_cache(cache_path, node_to_plugin, plugin_info)
        
        self._node_type_map = node_to_plugin
        self._plugin_info_map = plugin_info
        
        return node_to_plugin
    
    def _extract_all_plugin_ids(self, repo_url: str) -> List[str]:
        """
        从仓库URL提取多种格式的插件ID
        
        Args:
            repo_url: 仓库URL
            
        Returns:
            [标准化ID, 仓库名, 作者+仓库名, ...]
        """
        repo_url_lower = repo_url.lower().strip()
        if repo_url_lower.endswith('.git'):
            repo_url_lower = repo_url_lower[:-4]
        
        ids = []
        
        if 'comfyanonymous/comfyui' in repo_url_lower:
            return ['comfy-core']
        
        parts = repo_url_lower.rstrip('/').split('/')
        if len(parts) >= 1:
            repo_name = parts[-1]
            ids.append(repo_name)
            ids.append(repo_name.lower())
            normalized_repo = repo_name.replace('-', '').replace('_', '').lower()
            ids.append(normalized_repo)
        
        if len(parts) >= 2:
            author = parts[-2]
            repo_name = parts[-1] if len(parts) >= 1 else ''
            combined = f"{author}{repo_name}".replace('-', '').replace('_', '').lower()
            ids.append(combined)
        
        return ids
    
    def _extract_plugin_id(self, repo_url: str) -> str:
        """
        从仓库URL提取插件ID
        
        Args:
            repo_url: 仓库URL
            
        Returns:
            插件ID（标准化格式）
        """
        repo_url = repo_url.lower().strip()
        if repo_url.endswith('.git'):
            repo_url = repo_url[:-4]
        
        if 'comfyanonymous/comfyui' in repo_url:
            return 'comfy-core'
        
        parts = repo_url.rstrip('/').split('/')
        if len(parts) >= 2:
            repo_name = parts[-1]
            author = parts[-2] if len(parts) >= 2 else ''
            plugin_id = f"{author}{repo_name}".replace('-', '').replace('_', '').lower()
            return plugin_id
        
        return repo_url.split('/')[-1].replace('-', '').replace('_', '').lower()
    
    def _extract_plugin_name(self, repo_url: str) -> str:
        """
        从仓库URL提取插件名称
        
        Args:
            repo_url: 仓库URL
            
        Returns:
            插件名称
        """
        repo_url = repo_url.strip()
        if repo_url.endswith('.git'):
            repo_url = repo_url[:-4]
        
        if 'comfyanonymous/comfyui' in repo_url.lower():
            return 'ComfyUI Core'
        
        parts = repo_url.rstrip('/').split('/')
        if len(parts) >= 1:
            return parts[-1]
        
        return 'Unknown Plugin'
    
    def _save_node_type_map_cache(
        self, 
        cache_path: Path, 
        node_to_plugin: Dict[str, str], 
        plugin_info: Dict[str, Dict]
    ) -> None:
        """
        保存节点类型映射表到缓存文件
        
        Args:
            cache_path: 缓存文件路径
            node_to_plugin: 节点类型到插件的映射
            plugin_info: 插件信息字典
        """
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            cache_data = {
                "timestamp": time.time(),
                "node_to_plugin": node_to_plugin,
                "plugin_info": plugin_info
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            marketplace_logger.info(f"节点类型映射表已保存到: {cache_path}")
            
        except Exception as e:
            marketplace_logger.error(f"保存节点类型映射表失败: {e}")
    
    def load_node_type_map_cache(self, cache_path: Path) -> Optional[Dict[str, str]]:
        """
        从缓存文件加载节点类型映射表
        
        Args:
            cache_path: 缓存文件路径
            
        Returns:
            节点类型到插件的映射字典，失败时返回 None
        """
        try:
            if not cache_path.exists():
                marketplace_logger.debug(f"缓存文件不存在: {cache_path}")
                return None
            
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            node_to_plugin = cache_data.get('node_to_plugin', {})
            plugin_info = cache_data.get('plugin_info', {})
            
            self._node_type_map = node_to_plugin
            self._plugin_info_map = plugin_info
            
            marketplace_logger.info(
                f"从缓存加载节点类型映射表: {len(node_to_plugin)} 个节点类型"
            )
            
            return node_to_plugin
            
        except Exception as e:
            marketplace_logger.error(f"加载节点类型映射表缓存失败: {e}")
            return None
    
    def get_plugin_by_node_type(self, node_type: str) -> Optional[str]:
        """
        根据节点类型获取插件ID
        
        Args:
            node_type: 节点类型
            
        Returns:
            插件ID，未找到时返回 None
        """
        if self._node_type_map is None:
            return None
        
        return self._node_type_map.get(node_type)
    
    def get_plugin_info(self, plugin_id: str) -> Optional[Dict]:
        """
        获取插件信息
        
        Args:
            plugin_id: 插件ID
            
        Returns:
            插件信息字典，未找到时返回 None
        """
        return self._plugin_info_map.get(plugin_id)
