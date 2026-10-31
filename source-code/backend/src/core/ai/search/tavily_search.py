"""Tavily 搜索实现

Tavily 是面向 AI 应用的搜索 API，返回结果已做正文抽取，适合直接喂给模型。
接口文档：https://docs.tavily.com/documentation/api-reference/endpoint/search
"""

import asyncio
import logging
import time
from typing import List

import aiohttp

from .base_search import (
    BaseSearch,
    SearchResult,
    SearchError,
    SearchTimeoutError,
)
from .proxy_resolver import resolve_proxy

logger = logging.getLogger(__name__)

TAVILY_ENDPOINT = "https://api.tavily.com/search"


class TavilySearch(BaseSearch):
    """Tavily 搜索实现

    特点：
    - 面向 AI 的结果摘要，正文已抽取
    - 需要 API Key（免费额度每月 1000 次）
    - 境内需代理
    """

    def _validate_config(self) -> None:
        if not self.config.get("api_key"):
            raise SearchError("Tavily 搜索需要 API Key")

    async def search(
        self,
        query: str,
        max_results: int = 5,
        timeout: int = 10,
    ) -> List[SearchResult]:
        api_key = self.config.get("api_key")
        if not api_key:
            raise SearchError("Tavily 搜索需要 API Key")

        proxy = resolve_proxy(self.config.get("proxy"))
        payload = {
            "query": query,
            "max_results": max_results,
            "search_depth": self.config.get("search_depth") or "basic",
            "include_answer": False,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        logger.info(f"[Tavily] 开始搜索: query={query}, max_results={max_results}")

        try:
            client_timeout = aiohttp.ClientTimeout(total=timeout)
            async with aiohttp.ClientSession(timeout=client_timeout) as session:
                async with session.post(
                    TAVILY_ENDPOINT, json=payload, headers=headers, proxy=proxy or None
                ) as response:
                    if response.status == 401:
                        raise SearchError("Tavily API Key 无效或已过期")
                    if response.status == 429:
                        raise SearchError("Tavily 请求超出配额限制")
                    if response.status != 200:
                        text = await response.text()
                        raise SearchError(f"Tavily 返回 {response.status}: {text[:200]}")
                    data = await response.json()

        except asyncio.TimeoutError:
            error_msg = f"搜索超时（{timeout}秒）"
            logger.warning(f"[Tavily] {error_msg}")
            raise SearchTimeoutError(error_msg)
        except SearchError:
            raise
        except aiohttp.ClientError as e:
            raise SearchError(f"网络请求失败: {e}") from e
        except Exception as e:
            logger.error(f"[Tavily] 搜索失败: {e}", exc_info=True)
            raise SearchError(f"搜索失败: {e}") from e

        results = [
            SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", ""),
                source="tavily",
            )
            for item in (data.get("results") or [])
        ]
        logger.info(f"[Tavily] 搜索完成: 返回{len(results)}条结果")
        return results

    async def test_connection(self) -> tuple[bool, str, float]:
        try:
            start_time = time.time()
            results = await self.search("test", max_results=1, timeout=10)
            latency = int((time.time() - start_time) * 1000)
            if results:
                return True, "连接成功", latency
            return False, "搜索返回空结果", 0.0
        except Exception as e:
            logger.error(f"[Tavily] 测试连接失败: {e}")
            return False, f"连接失败: {e}", 0.0
