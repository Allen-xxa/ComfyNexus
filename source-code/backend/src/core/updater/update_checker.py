"""
版本检查器
通过 raw 镜像源获取 version.json 检查最新版本
"""

import requests
from typing import Dict, Optional, Tuple
from pathlib import Path

from backend.src.utils.logger import app_logger as logger


class UpdateChecker:
    """版本检查器"""
    
    VERSION_JSON_URL = "https://raw.githubusercontent.com/qiqStrong/ComfyNexus/main/version.json"
    REQUEST_TIMEOUT = 15
    
    def __init__(self, settings_manager=None):
        self._current_version = self._get_current_version()
        self._settings_manager = settings_manager
        self._dev_token = None
        self._dev_repo_owner = None
        self._dev_repo_name = None
        self._version_json_url = self.VERSION_JSON_URL
        self._load_dev_config()
    
    def _get_proxies(self) -> Optional[Dict]:
        try:
            if not self._settings_manager:
                from backend.src.core.settings_manager import SettingsManager
                self._settings_manager = SettingsManager()

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
            logger.dev(f"[UpdateChecker] 使用代理: {proxy_url}")

            return {
                "http": proxy_url,
                "https": proxy_url
            }
        except Exception as e:
            logger.dev(f"[UpdateChecker] 获取代理配置失败: {e}")
            return None
    
    def _load_dev_config(self):
        """
        从 dev 文件加载开发配置
        
        支持格式: https://<token>@github.com/<owner>/<repo>
        例如: https://ghp_xxxx@github.com/qiqStrong/ComfyNexus_VM
        """
        try:
            from backend.src.utils.paths import get_dev_update_source_file
            dev_file = get_dev_update_source_file()
            
            if not dev_file.exists():
                return
            
            content = dev_file.read_text(encoding='utf-8').strip()
            if not content:
                return
            
            if '@github.com/' in content:
                if content.startswith('https://') and '@github.com/' in content:
                    token_part = content.split('://')[1].split('@')[0]
                    self._dev_token = token_part
                    
                    repo_path = content.split('@github.com/')[1].strip('/')
                    parts = repo_path.split('/')
                    if len(parts) >= 2:
                        owner, repo = parts[0], parts[1]
                        self._dev_repo_owner = owner
                        self._dev_repo_name = repo
                        self._version_json_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/version.json"
                        logger.info(f"[UpdateChecker] 使用开发模式更新源: {self._version_json_url}")
                    else:
                        logger.warning(f"[UpdateChecker] dev 文件格式无效，无法解析仓库路径: {content}")
                else:
                    logger.warning(f"[UpdateChecker] dev 文件格式无效: {content}")
            else:
                logger.warning(f"[UpdateChecker] dev 文件格式无效，需要带 Token 的 URL: {content}")
                
        except Exception as e:
            logger.warning(f"[UpdateChecker] 读取 dev 文件失败: {e}")
    
    def _get_current_version(self) -> str:
        try:
            from backend.src.utils.paths import get_version_file
            version_file = get_version_file()
            if version_file.exists():
                content = version_file.read_text(encoding='utf-8')
                for line in content.splitlines():
                    if line.startswith('__version__'):
                        return line.split('=')[1].strip().strip('"').strip("'")
        except Exception as e:
            logger.warning(f"[UpdateChecker] 读取版本文件失败: {e}")
        
        return "RC_0.0.0"
    
    def check_update(self) -> Dict:
        """
        检查是否有新版本
        
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
                "file_hash": str,  # SHA256 hash
                "error": str  # 可选
            }
        """
        try:
            logger.info(f"[UpdateChecker] 开始检查更新，当前版本: {self._current_version}")
            
            version_info = self._fetch_version_info()
            
            if not version_info:
                return {
                    "success": False,
                    "has_update": False,
                    "current_version": self._current_version,
                    "error": "无法获取版本信息"
                }
            
            latest_version = version_info.get("version", "")
            download_url = version_info.get("download_url", "")
            release_notes = version_info.get("release_notes", "")
            published_at = version_info.get("published_at", "")
            file_size = version_info.get("file_size", 0)
            file_hash = version_info.get("file_hash", "")
            
            if not download_url:
                return {
                    "success": False,
                    "has_update": False,
                    "current_version": self._current_version,
                    "error": "未找到 Windows 版本下载链接"
                }
            
            has_update = self._compare_versions(self._current_version, latest_version) < 0
            
            logger.info(f"[UpdateChecker] 检查完成: latest={latest_version}, has_update={has_update}")
            
            return {
                "success": True,
                "has_update": has_update,
                "current_version": self._current_version,
                "latest_version": latest_version,
                "download_url": download_url,
                "asset_id": None,
                "release_notes": release_notes,
                "published_at": published_at,
                "file_size": file_size,
                "file_hash": file_hash
            }
            
        except requests.exceptions.Timeout:
            logger.error("[UpdateChecker] 请求超时")
            return {
                "success": False,
                "has_update": False,
                "current_version": self._current_version,
                "error": "网络请求超时，请稍后重试"
            }
        except requests.exceptions.ConnectionError:
            logger.error("[UpdateChecker] 网络连接失败")
            return {
                "success": False,
                "has_update": False,
                "current_version": self._current_version,
                "error": "网络连接失败，请检查网络设置"
            }
        except Exception as e:
            logger.error(f"[UpdateChecker] 检查更新失败: {e}")
            return {
                "success": False,
                "has_update": False,
                "current_version": self._current_version,
                "error": f"检查更新失败: {str(e)}"
            }
    
    def _fetch_version_info(self) -> Optional[Dict]:
        """
        获取版本信息
        
        通过 raw 镜像源获取 version.json
        
        Returns:
            版本信息字典，失败返回 None
        """
        try:
            request_url = self._version_json_url
            
            try:
                from backend.src.utils.github_mirror import github_mirror_manager
                if github_mirror_manager.is_enabled():
                    mirror = github_mirror_manager.get_mirror_for_type("raw")
                    if mirror:
                        request_url, _ = github_mirror_manager.transform_url(
                            self._version_json_url, "raw"
                        )
                        logger.dev(f"[UpdateChecker] 使用 raw 镜像源: {mirror}")
            except Exception as e:
                logger.dev(f"[UpdateChecker] 获取镜像设置失败: {e}")
            
            headers = {
                "Accept": "application/json",
                "User-Agent": "ComfyNexus-UpdateChecker"
            }
            
            logger.dev(f"[UpdateChecker] 请求版本信息: {request_url}")
            
            proxies = self._get_proxies()
            
            response = requests.get(
                request_url,
                headers=headers,
                timeout=self.REQUEST_TIMEOUT,
                proxies=proxies
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"[UpdateChecker] 获取版本信息失败，状态码: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"[UpdateChecker] 获取版本信息失败: {e}")
            return None
    
    def _compare_versions(self, current: str, latest: str) -> int:
        """
        比较版本号
        
        版本格式: RC_0.6.0 或 v0.6.0
        正式版本(v前缀或无前缀) > 同版本号的 RC 版本
        
        Args:
            current: 当前版本号
            latest: 最新版本号
            
        Returns:
            -1: current < latest (有更新)
             0: current == latest (无更新)
             1: current > latest (当前版本更高)
        """
        def parse_version(v: str) -> Tuple[Tuple[int, ...], bool]:
            """
            解析版本号
            
            Returns:
                (版本号元组, 是否为正式版)
                正式版为 True，RC 版为 False
            """
            v_lower = v.lower()
            is_stable = True
            
            if v_lower.startswith('rc_'):
                is_stable = False
                v = v[3:]
            elif v_lower.startswith('v'):
                v = v[1:]
            
            parts = v.split('.')
            result = []
            for p in parts:
                p = p.strip()
                if p.isdigit():
                    result.append(int(p))
                else:
                    try:
                        num = ''.join(c for c in p if c.isdigit())
                        result.append(int(num) if num else 0)
                    except (ValueError, TypeError):
                        result.append(0)
            while len(result) < 3:
                result.append(0)
            
            return (tuple(result[:3]), is_stable)
        
        try:
            current_tuple, current_is_stable = parse_version(current)
            latest_tuple, latest_is_stable = parse_version(latest)
            
            if current_tuple < latest_tuple:
                return -1
            elif current_tuple > latest_tuple:
                return 1
            
            if not current_is_stable and latest_is_stable:
                return -1
            elif current_is_stable and not latest_is_stable:
                return 1
            
            return 0
        except Exception as e:
            logger.warning(f"[UpdateChecker] 版本比较失败: {e}")
            return 0
    
    @property
    def current_version(self) -> str:
        """获取当前版本号"""
        return self._current_version
    
    @property
    def version_json_url(self) -> str:
        """获取当前使用的 version.json URL"""
        return self._version_json_url
    
    @property
    def dev_token(self) -> Optional[str]:
        """获取从 dev 文件提取的 Token"""
        return self._dev_token
    
    @property
    def dev_repo_owner(self) -> Optional[str]:
        """获取从 dev 文件提取的仓库所有者"""
        return self._dev_repo_owner
    
    @property
    def dev_repo_name(self) -> Optional[str]:
        """获取从 dev 文件提取的仓库名称"""
        return self._dev_repo_name
