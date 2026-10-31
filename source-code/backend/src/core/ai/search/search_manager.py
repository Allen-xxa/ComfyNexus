"""
搜索管理器

统一管理所有搜索引擎，提供搜索、配置、测试接口。
"""

import logging
from typing import List, Dict, Any, Tuple, Optional

from .base_search import BaseSearch, SearchResult, SearchError
from .duckduckgo_search import DuckDuckGoSearch
from .google_search import GoogleSearch
from .tavily_search import TavilySearch
from .search_config import SearchConfig

logger = logging.getLogger(__name__)


class SearchManager:
    """搜索管理器
    
    负责：
    - 管理所有搜索引擎实例
    - 根据配置选择搜索引擎
    - 提供统一的搜索接口
    - 管理配置
    """
    
    def __init__(self):
        """初始化搜索管理器"""
        self.config_manager = SearchConfig()
        self._providers: Dict[str, BaseSearch] = {}
        self._init_providers()
    
    def _init_providers(self) -> None:
        """初始化搜索引擎
        
        根据配置初始化可用的搜索引擎实例。
        """
        config = self.config_manager.load()
        
        # 初始化DuckDuckGo（始终可用）
        try:
            self._providers['duckduckgo'] = DuckDuckGoSearch({})
            logger.info("DuckDuckGo搜索引擎已初始化")
        except Exception as e:
            logger.error(f"初始化DuckDuckGo失败: {e}")
        
        # 初始化Google（如果配置了）
        google_config = config.get('providers', {}).get('google', {})
        if google_config.get('enabled') and google_config.get('api_key') and google_config.get('search_engine_id'):
            try:
                self._providers['google'] = GoogleSearch(google_config)
                logger.info("Google搜索引擎已初始化")
            except Exception as e:
                logger.error(f"初始化Google失败: {e}")
        
        # 初始化 Tavily（如果配置了 API Key）
        tavily_config = config.get('providers', {}).get('tavily', {})
        if tavily_config.get('api_key'):
            try:
                self._providers['tavily'] = TavilySearch(tavily_config)
                logger.info("Tavily搜索引擎已初始化")
            except Exception as e:
                logger.error(f"初始化Tavily失败: {e}")
    
    async def search(
        self, 
        query: str, 
        provider: Optional[str] = None,
        max_results: Optional[int] = None,
        timeout: Optional[int] = None
    ) -> List[SearchResult]:
        """执行搜索
        
        Args:
            query: 搜索关键词
            provider: 搜索引擎（可选，默认使用配置中的）
            max_results: 最大结果数（可选，默认使用配置中的）
            timeout: 超时时间（可选，默认使用配置中的）
            
        Returns:
            搜索结果列表
            
        Raises:
            SearchError: 搜索失败时抛出
        """
        config = self.config_manager.load()
        
        # 确定使用的搜索引擎
        provider = provider or config['provider']
        max_results = max_results or config['max_results']
        timeout = timeout or config['timeout']
        
        # 获取搜索引擎实例
        search_engine = self._providers.get(provider)
        if not search_engine:
            raise SearchError(f"搜索引擎未初始化: {provider}")
        
        # 执行搜索
        logger.info(f"[搜索管理器] 执行搜索: query={query}, provider={provider}, max_results={max_results}")
        try:
            results = await search_engine.search(query, max_results, timeout)
            logger.info(f"[搜索管理器] 搜索完成: 返回{len(results)}条结果")
            return results
        except Exception as e:
            logger.error(f"[搜索管理器] 搜索失败: {e}")
            raise
    
    def get_config(self) -> Dict[str, Any]:
        """获取配置
        
        Returns:
            配置字典
        """
        return self.config_manager.load()
    
    def update_config(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        """更新配置
        
        Args:
            config: 新配置
            
        Returns:
            (是否成功, 消息)
        """
        # 验证配置
        valid, message = self.config_manager.validate(config)
        if not valid:
            logger.warning(f"配置验证失败: {message}")
            return False, message
        
        # 保存配置
        success = self.config_manager.save(config)
        if success:
            # 重新初始化搜索引擎
            self._init_providers()
            logger.info("配置已更新，搜索引擎已重新初始化")
            return True, "配置已更新"
        else:
            return False, "保存配置失败"
    
    async def test_provider(
        self, 
        provider: str, 
        config: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str, float]:
        """测试搜索引擎连接
        
        Args:
            provider: 搜索引擎名称
            config: 搜索引擎配置（可选，用于测试新配置）
            
        Returns:
            (成功标志, 消息, 延迟毫秒)
        """
        try:
            # 创建临时搜索引擎实例
            if provider == 'duckduckgo':
                engine = DuckDuckGoSearch({})
            elif provider == 'google':
                if not config:
                    return False, "需要提供Google配置", 0.0
                engine = GoogleSearch(config)
            elif provider == 'tavily':
                if not config or not config.get('api_key'):
                    return False, "Tavily搜索需要API Key", 0.0
                engine = TavilySearch(config)
            else:
                return False, f"未知的搜索引擎: {provider}", 0.0
            
            # 测试连接
            logger.info(f"[搜索管理器] 测试连接: provider={provider}")
            result = await engine.test_connection()
            logger.info(f"[搜索管理器] 测试结果: {result}")
            return result
            
        except Exception as e:
            logger.error(f"[搜索管理器] 测试连接失败: {e}")
            return False, str(e), 0.0
    
    def is_provider_available(self, provider: str) -> bool:
        """检查搜索引擎是否可用
        
        Args:
            provider: 搜索引擎名称
            
        Returns:
            是否可用
        """
        return provider in self._providers
