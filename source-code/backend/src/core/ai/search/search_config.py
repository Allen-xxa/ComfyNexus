"""
搜索配置管理

管理搜索配置的读取、保存、验证。
"""

import copy
import json
import logging
from pathlib import Path
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)


class SearchConfig:
    """搜索配置管理器"""
    
    # 默认配置
    DEFAULT_CONFIG = {
        "enabled": True,
        "provider": "duckduckgo",
        "max_results": 5,
        "timeout": 10,
        "providers": {
            "duckduckgo": {
                "enabled": True
            },
            "google": {
                "enabled": False,
                "api_key": "",
                "search_engine_id": ""
            },
            "tavily": {
                "enabled": False,
                "api_key": "",
                "search_depth": "basic"
            }
        }
    }
    
    def __init__(self, config_file: Path = None):
        """初始化配置管理器
        
        Args:
            config_file: 配置文件路径（可选）
        """
        if config_file is None:
            # 使用绝对路径
            from backend.src.utils.paths import get_config_dir
            config_file = get_config_dir() / "search_config.json"
        
        self.config_file = config_file
        self._ensure_config_exists()
    
    def _ensure_config_exists(self) -> None:
        """确保配置文件存在"""
        if not self.config_file.exists():
            logger.info(f"配置文件不存在，创建默认配置: {self.config_file}")
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            self.save(self.DEFAULT_CONFIG)
    
    def load(self) -> Dict[str, Any]:
        """加载配置

        会把新增 provider 的默认值合并进来，避免旧配置文件缺少字段
        导致前端读取 providers.tavily 时报错。

        Returns:
            配置字典
        """
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.debug(f"配置加载成功: {self.config_file}")
                return self._merge_defaults(config)
        except Exception as e:
            logger.error(f"加载搜索配置失败: {e}", exc_info=True)
            logger.info("使用默认配置")
            return copy.deepcopy(self.DEFAULT_CONFIG)

    def _merge_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """把默认配置合并进已加载的配置"""
        merged = copy.deepcopy(self.DEFAULT_CONFIG)
        merged.update({k: v for k, v in config.items() if k != 'providers'})

        existing = config.get('providers') or {}
        providers = merged.get('providers', {})
        for name, defaults in self.DEFAULT_CONFIG['providers'].items():
            providers[name] = {**defaults, **(existing.get(name) or {})}
        # 保留用户自行添加的其他 provider
        for name, value in existing.items():
            if name not in providers:
                providers[name] = value
        merged['providers'] = providers
        return merged
    
    def save(self, config: Dict[str, Any]) -> bool:
        """保存配置
        
        Args:
            config: 配置字典
            
        Returns:
            是否保存成功
        """
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            logger.info(f"配置保存成功: {self.config_file}")
            return True
        except Exception as e:
            logger.error(f"保存搜索配置失败: {e}", exc_info=True)
            return False
    
    def validate(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        """验证配置
        
        Args:
            config: 配置字典
            
        Returns:
            (是否有效, 错误信息)
        """
        # 验证必需字段
        required_fields = ['enabled', 'provider', 'max_results', 'timeout', 'providers']
        for field in required_fields:
            if field not in config:
                return False, f"缺少必需字段: {field}"
        
        # 验证provider
        if config['provider'] not in ['duckduckgo', 'google', 'tavily']:
            return False, f"无效的搜索引擎: {config['provider']}"
        
        # 验证max_results
        if not isinstance(config['max_results'], int) or config['max_results'] < 1 or config['max_results'] > 10:
            return False, "max_results必须在1-10之间"
        
        # 验证timeout
        if not isinstance(config['timeout'], int) or config['timeout'] < 5 or config['timeout'] > 30:
            return False, "timeout必须在5-30秒之间"
        
        # 验证Google配置
        if config['provider'] == 'google':
            google_config = config.get('providers', {}).get('google', {})
            if not google_config.get('api_key'):
                return False, "Google搜索需要API Key"
            if not google_config.get('search_engine_id'):
                return False, "Google搜索需要Search Engine ID"
        
        # 验证 Tavily 配置
        if config['provider'] == 'tavily':
            tavily_config = config.get('providers', {}).get('tavily', {})
            if not tavily_config.get('api_key'):
                return False, "Tavily搜索需要API Key"
        
        return True, "配置有效"
    
    def get_provider_config(self, provider: str) -> Dict[str, Any]:
        """获取指定搜索引擎的配置
        
        Args:
            provider: 搜索引擎名称
            
        Returns:
            搜索引擎配置
        """
        config = self.load()
        return config.get('providers', {}).get(provider, {})
