"""
模块配置管理器
负责读取、写入和验证模块配置文件
"""

import json
from pathlib import Path
from typing import Dict, Optional

from ..config.config_migrator import ConfigMigrator
from backend.src.utils.logger import app_logger as logger


class ModuleConfigManager(ConfigMigrator):
    """模块配置管理器"""
    
    CURRENT_VERSION = "1.0.0"
    CONFIG_FILENAME = "modules.json"
    
    def __init__(self):
        from backend.src.utils.paths import get_config_dir
        config_dir = get_config_dir()
        super().__init__(config_dir)
    
    def get_default_config(self) -> Dict:
        """
        获取默认配置（基础模式，只启用已开发的模块）
        
        Returns:
            Dict: 默认配置对象
        """
        return {
            "version": self.CURRENT_VERSION,
            "preset": "basic",
            "modules": {
                "home": {"enabled": True, "order": 1},
                "workspace": {"enabled": True, "order": 2},
                "terminal": {"enabled": True, "order": 3},
                "version-manage": {"enabled": True, "order": 4},
                "plugin-manage": {"enabled": True, "order": 5},
                "plugin-market": {"enabled": True, "order": 6},  # 插件市场已开发
                "dependency-manage": {"enabled": True, "order": 7},  # 依赖管理已开发
                "model-manage": {"enabled": True, "order": 8},  # LoRA管理已开发
                "ai-assistant": {"enabled": True, "order": 9},  # AI 助手默认打开
                "workflow-manage": {"enabled": True, "order": 10},
                "prompt-manage": {"enabled": True, "order": 11},
                "output-gallery": {"enabled": True, "order": 12},
                "monitor-center": {"enabled": True, "order": 13},
                "env-manage": {"enabled": True, "order": 14},  # 环境管理默认打开
                "system-settings": {"enabled": True, "order": 15},
                "about": {"enabled": True, "order": 16}
            },
            "ui": {
                "theme": "dark",
                "language": "zh-CN"
            }
        }
    
    @property
    def config_dir_str(self) -> str:
        """
        配置目录路径（字符串格式）
        
        Returns:
            str: 配置目录的字符串路径
        """
        return str(self.config_dir)
    
    @property
    def config_file_str(self) -> str:
        """
        配置文件路径（字符串格式）
        
        Returns:
            str: 配置文件的字符串路径
        """
        return str(self.config_file)
    
    def reset_config(self) -> bool:
        """
        重置模块配置为默认值（保留其他设置如主题、语言等）
        
        Returns:
            bool: 重置是否成功
        """
        try:
            # 加载当前配置
            current_config = self.load_config()
            
            # 获取默认的模块配置
            default_config = self.get_default_config()
            
            # 只重置模块部分，保留 UI 设置
            current_config['modules'] = default_config['modules']
            current_config['preset'] = default_config['preset']
            
            # 保存修改后的配置
            return self.save_config(current_config)
        except Exception as e:
            logger.error(f"重置模块配置失败: {e}")
            return False
