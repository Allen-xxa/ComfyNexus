"""
DuckDuckGo搜索实现

使用ddgs库实现免费的网络搜索。
"""

import asyncio
import logging
import time
from typing import List
from ddgs import DDGS

from .base_search import (
    BaseSearch,
    SearchResult,
    SearchError,
    SearchTimeoutError
)
from .proxy_resolver import resolve_proxy

logger = logging.getLogger(__name__)


class DuckDuckGoSearch(BaseSearch):
    """DuckDuckGo搜索实现
    
    特点：
    - 完全免费，无需API Key
    - 无请求限制
    - 隐私友好
    """
    
    def _validate_config(self) -> None:
        """验证配置
        
        DuckDuckGo不需要特殊配置
        """
        pass
    
    async def search(
        self, 
        query: str, 
        max_results: int = 5,
        timeout: int = 10
    ) -> List[SearchResult]:
        """执行DuckDuckGo搜索
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数量
            timeout: 超时时间（秒）
            
        Returns:
            搜索结果列表
            
        Raises:
            SearchTimeoutError: 搜索超时
            SearchError: 搜索失败
        """
        try:
            logger.info(f"[DuckDuckGo] 开始搜索: query={query}, max_results={max_results}")
            
            # 在线程池中执行同步搜索
            loop = asyncio.get_event_loop()
            results = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    self._sync_search,
                    query,
                    max_results
                ),
                timeout=timeout
            )
            
            logger.info(f"[DuckDuckGo] 搜索完成: 返回{len(results)}条结果")
            return results
            
        except asyncio.TimeoutError:
            error_msg = f"搜索超时（{timeout}秒）"
            logger.warning(f"[DuckDuckGo] {error_msg}")
            raise SearchTimeoutError(error_msg)
        except Exception as e:
            error_msg = f"搜索失败: {str(e)}"
            logger.error(f"[DuckDuckGo] {error_msg}", exc_info=True)
            raise SearchError(error_msg)
    
    def _sync_search(self, query: str, max_results: int) -> List[SearchResult]:
        """同步搜索方法
        
        在线程池中执行，避免阻塞事件循环。
        
        Args:
            query: 搜索关键词
            max_results: 最大结果数量
            
        Returns:
            搜索结果列表
        """
        # ddgs 9.x 的搜索后端包含 startpage 等站点，境内直连会超时，
        # 必须复用应用/系统代理，否则一律报 operation timed out
        proxy = resolve_proxy(self.config.get("proxy"))
        if proxy:
            logger.info(f"[DuckDuckGo] 使用代理: {proxy}")
        else:
            logger.warning("[DuckDuckGo] 未检测到可用代理，境内网络下可能超时")

        with DDGS(proxy=proxy or None) as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            return [
                SearchResult(
                    title=r.get('title', ''),
                    url=r.get('href', ''),
                    snippet=r.get('body', ''),
                    source='duckduckgo'
                )
                for r in results
            ]
    
    async def test_connection(self) -> tuple[bool, str, float]:
        """测试DuckDuckGo连接
        
        Returns:
            (成功标志, 消息, 延迟毫秒)
        """
        try:
            start_time = time.time()
            
            # 执行一个简单的测试搜索
            results = await self.search("test", max_results=1, timeout=5)
            
            latency = int((time.time() - start_time) * 1000)  # 转换为毫秒（整数）
            
            if results:
                return True, "连接成功", latency
            else:
                return False, "搜索返回空结果", 0.0
                
        except Exception as e:
            logger.error(f"[DuckDuckGo] 测试连接失败: {e}")
            return False, f"连接失败: {str(e)}", 0.0
