"""
ComfyUI Release 更新日志服务
从多个数据源获取并合并 Release 信息
"""

import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime

import requests

from ..utils.logger import app_logger as logger


@dataclass
class ReleaseInfo:
    """Release 信息"""
    version: str
    name: str = ""
    published_at: str = ""
    release_notes_html: str = ""
    url: str = ""
    source: str = ""

    def to_dict(self) -> Dict:
        return {
            "version": self.version,
            "name": self.name,
            "publishedAt": self.published_at,
            "releaseNotesHtml": self.release_notes_html,
            "url": self.url,
            "source": self.source
        }


class ReleaseNotesService:
    """ComfyUI Release 更新日志服务"""
    
    JSON_DATA_URL = "https://raw.githubusercontent.com/qiqStrong/ComfyNexus/refs/heads/main/comfyui_releases.json"
    ATOM_FEED_URL = "https://github.com/Comfy-Org/ComfyUI/releases.atom"
    GITHUB_RELEASE_URL_TEMPLATE = "https://github.com/Comfy-Org/ComfyUI/releases/tag/{version}"
    
    CACHE_TTL = 3600
    REQUEST_TIMEOUT = 15
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if ReleaseNotesService._initialized:
            return
        
        self._cache: Dict[str, ReleaseInfo] = {}
        self._cache_timestamp: float = 0
        self._proxy_config: Optional[Dict] = None
        ReleaseNotesService._initialized = True
    
    def set_proxy_config(self, proxy_config: Optional[Dict]):
        """
        设置代理配置
        
        Args:
            proxy_config: 代理配置字典，如 {"http_proxy": "...", "https_proxy": "..."}
        """
        self._proxy_config = proxy_config
        self._clear_cache()
    
    def _clear_cache(self):
        """清除缓存"""
        self._cache = {}
        self._cache_timestamp = 0
    
    def _get_proxies(self) -> Optional[Dict]:
        """获取代理配置（requests 格式）"""
        if not self._proxy_config:
            return None
        
        http_proxy = self._proxy_config.get("http_proxy", "")
        https_proxy = self._proxy_config.get("https_proxy", "")
        
        if not http_proxy and not https_proxy:
            return None
        
        return {
            "http": http_proxy,
            "https": https_proxy
        }
    
    def get_release_notes(self, version_tags: List[str]) -> Dict[str, ReleaseInfo]:
        """
        获取指定版本的更新日志
        
        Args:
            version_tags: 版本标签列表，如 ["v0.18.1", "v0.18.0"]
            
        Returns:
            {版本号: ReleaseInfo} 字典
        """
        current_time = time.time()
        
        if current_time - self._cache_timestamp > self.CACHE_TTL:
            logger.debug("[ReleaseNotesService] 缓存过期，重新获取数据")
            self._fetch_and_merge_sources()
        
        result = {}
        for tag in version_tags:
            normalized_tag = self._normalize_version(tag)
            if normalized_tag in self._cache:
                result[tag] = self._cache[normalized_tag]
        
        return result
    
    def get_all_release_notes(self) -> Dict[str, ReleaseInfo]:
        """
        获取所有版本的更新日志
        
        Returns:
            {版本号: ReleaseInfo} 字典
        """
        current_time = time.time()
        
        if current_time - self._cache_timestamp > self.CACHE_TTL:
            logger.debug("[ReleaseNotesService] 缓存过期，重新获取数据")
            self._fetch_and_merge_sources()
        
        return self._cache.copy()
    
    def _fetch_and_merge_sources(self):
        """从两个数据源获取数据并合并"""
        json_data = []
        atom_data = []
        
        try:
            json_data = self._fetch_from_json()
            logger.debug(f"[ReleaseNotesService] 从 JSON 数据源获取了 {len(json_data)} 条记录")
        except Exception as e:
            logger.warning(f"[ReleaseNotesService] 获取 JSON 数据源失败: {e}")
        
        try:
            atom_data = self._fetch_from_atom()
            logger.debug(f"[ReleaseNotesService] 从 Atom Feed 获取了 {len(atom_data)} 条记录")
        except Exception as e:
            logger.warning(f"[ReleaseNotesService] 获取 Atom Feed 失败: {e}")
        
        self._cache = self._merge_sources(json_data, atom_data)
        self._cache_timestamp = time.time()
        
        logger.info(f"[ReleaseNotesService] 合并后共 {len(self._cache)} 条版本记录")
    
    def _fetch_from_json(self) -> List[ReleaseInfo]:
        """从 JSON 数据源获取"""
        proxies = self._get_proxies()
        
        url = self.JSON_DATA_URL
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
                logger.dev(f"[ReleaseNotesService] 使用 raw 镜像源获取 JSON 数据, verify_ssl={verify_ssl}")
        except Exception as e:
            logger.dev(f"[ReleaseNotesService] 获取镜像设置失败: {e}")
        
        response = requests.get(
            url,
            headers=headers,
            timeout=self.REQUEST_TIMEOUT,
            proxies=proxies,
            verify=verify_ssl
        )
        response.raise_for_status()
        
        data = response.json()
        
        result = []
        for item in data:
            tag_name = item.get("tag_name", "")
            if not tag_name:
                continue
            
            normalized_tag = self._normalize_version(tag_name)
            
            release_info = ReleaseInfo(
                version=normalized_tag,
                name=item.get("name", tag_name),
                published_at=item.get("date", ""),
                release_notes_html=item.get("content", ""),
                url=self.GITHUB_RELEASE_URL_TEMPLATE.format(version=tag_name),
                source="json"
            )
            result.append(release_info)
        
        return result
    
    def _fetch_from_atom(self) -> List[ReleaseInfo]:
        """从 Atom Feed 获取"""
        proxies = self._get_proxies()
        
        url = self.ATOM_FEED_URL
        headers = {'User-Agent': 'ComfyNexus/1.0'}
        verify_ssl = True
        
        try:
            from backend.src.utils.github_mirror import github_mirror_manager
            if github_mirror_manager.is_enabled():
                mirror_url, mirror_headers = github_mirror_manager.transform_url(url, "github")
                url = mirror_url
                headers.update(mirror_headers)
                settings = github_mirror_manager._load_settings()
                verify_ssl = settings.get("verifySSL", True)
                logger.dev(f"[ReleaseNotesService] 使用 github 镜像源获取 Atom Feed, verify_ssl={verify_ssl}")
        except Exception as e:
            logger.dev(f"[ReleaseNotesService] 获取镜像设置失败: {e}")
        
        response = requests.get(
            url,
            headers=headers,
            timeout=self.REQUEST_TIMEOUT,
            proxies=proxies,
            verify=verify_ssl
        )
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        
        result = []
        for entry in root.findall('atom:entry', ns):
            title_elem = entry.find('atom:title', ns)
            updated_elem = entry.find('atom:updated', ns)
            content_elem = entry.find('atom:content', ns)
            link_elem = entry.find('atom:link', ns)
            
            if title_elem is None:
                continue
            
            tag_name = title_elem.text or ""
            if not tag_name:
                continue
            
            normalized_tag = self._normalize_version(tag_name)
            
            release_info = ReleaseInfo(
                version=normalized_tag,
                name=tag_name,
                published_at=updated_elem.text if updated_elem is not None else "",
                release_notes_html=content_elem.text if content_elem is not None else "",
                url=link_elem.get('href', '') if link_elem is not None else "",
                source="atom"
            )
            result.append(release_info)
        
        return result
    
    def _merge_sources(self, json_data: List[ReleaseInfo], atom_data: List[ReleaseInfo]) -> Dict[str, ReleaseInfo]:
        """合并两个数据源，去重"""
        merged: Dict[str, ReleaseInfo] = {}
        
        for release in json_data:
            merged[release.version] = release
        
        for release in atom_data:
            if release.version not in merged:
                merged[release.version] = release
            else:
                existing = merged[release.version]
                if not existing.release_notes_html and release.release_notes_html:
                    existing.release_notes_html = release.release_notes_html
                    existing.source = "merged"
                if not existing.url and release.url:
                    existing.url = release.url
        
        return merged
    
    def _normalize_version(self, version: str) -> str:
        """
        标准化版本号
        
        Args:
            version: 原始版本号，如 "v0.18.1" 或 "0.18.1"
            
        Returns:
            标准化后的版本号，如 "v0.18.1"
        """
        version = version.strip()
        if not version:
            return version
        
        if version.startswith('v'):
            return version.lower()
        
        return f"v{version}".lower()
