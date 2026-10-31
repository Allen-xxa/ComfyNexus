"""
系统设置管理器
用于管理全局系统设置
"""

import json
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

from .config.config_migrator import ConfigMigrator
from backend.src.utils.logger import app_logger as logger


class SettingsManager(ConfigMigrator):
    """系统设置管理器"""
    
    CURRENT_VERSION = "1.0.0"
    CONFIG_FILENAME = "settings.json"
    
    def __init__(self, config_dir: str = None):
        """
        初始化设置管理器
        
        Args:
            config_dir: 配置文件目录，如果为 None 则使用默认路径
        """
        if config_dir is None:
            # 使用绝对路径工具函数
            from backend.src.utils.paths import get_config_dir
            config_dir = get_config_dir()
        
        super().__init__(Path(config_dir))
    
    def get_default_config(self) -> Dict:
        """
        获取默认配置
        
        Returns:
            默认配置字典
        """
        return {
            "version": self.CURRENT_VERSION,
            "general": {
                "configMode": "preset",
                # 二次开发分支：更新源仍指向原作者仓库，开启后会自动下载覆盖本地修改，故默认关闭
                "autoUpdate": False,
                "comfyuiStartupAction": "workspace",
                "selectedBrowser": "",  # 空字符串表示使用系统默认浏览器
                "titleBarDoubleClickAction": "maximize",
                "git_concurrent_workers": 10,
                "showConsoleWindow": False,
                "lastDownloadPath": "",
                "hardwareAcceleration": True
            },
            "appearance": {
                "theme": "dark",
                "windowSize": "1680x1080",
                "titleBarStyle": "normal",
                "globalTextSelection": False
            },
            "language": {
                "current": "zh-CN"
            },
            "pluginManagement": {
                "gitConcurrency": 10,
                "hideDisabledPlugins": False  # 是否隐藏禁用的插件，默认 False
            },
            "pluginMarketplace": {
                "autoInstallDeps": True  # 是否自动安装插件依赖，默认 True
            },
            "proxy": {
                "enabled": False,
                "host": "",
                "port": ""
            },
            "warnings": {
                "devVersionWarning": True,
                "systemProxyDetected": True
            },
            "closeBehavior": {
                "action": None,
                "dontAskAgain": False
            },
            "logging": {
                "level": "INFO",
                "keepDays": 30,
                "maxFileSize": 104857600  # 100MB
            },
            "github": {
                "apiToken": "",  # GitHub Personal Access Token，用于提高 API 请求限制
                "enabled": False  # 是否启用 GitHub API Token
            },
            "git": {
                "mode": "mingit",  # Git 模式: mingit | system | custom
                "customPath": "",  # 自定义 git.exe 路径（mode=custom 时使用）
                "mingitVersion": "2.53.0",  # MinGit 版本号
                "lastChecked": ""  # 上次检查时间（ISO 格式）
            },
            "translation": {
                "provider": "google",  # 翻译提供商: google | llm
                "llmConfigId": "",  # LLM配置ID（provider为llm时使用）
                "sourceLanguage": "auto",  # 源语言（auto表示自动检测）
                "targetLanguage": "zh-CN"  # 目标语言
            },
            "versionSettings": {
                "autoTranslateChangelog": False  # 是否自动翻译更新日志，默认关闭
            },
            "cache": {
                "versionCacheTtlHours": 24,
                "versionDevCacheTtlHours": 6,
                "translationCacheTtlDays": 30,
                "pluginCacheTtlHours": 24,
                "marketplaceCacheTtlHours": 24
            },
            "githubMirror": {
                "enabled": False,
                "mode": "auto",
                "forcePreset": None,
                "customMirrors": {
                    "github": "",
                    "raw": "",
                    "release": ""
                },
                "fallbackToDirect": True,
                "timeout": 30,
                "verifySSL": True,
                "lastTested": None,
                "testResults": None,
                "currentMirror": None,
                "apiCacheTTL": 3600,
                "customProxyUrl": ""
            },
            "pypiMirror": {
                "enabled": False,
                "mode": "auto",
                "forceSource": None,
                "lastTested": None,
                "testResults": None,
                "currentSource": None,
            }
        }
    
    def get_settings(self) -> Dict:
        """
        获取所有设置
        
        Returns:
            dict: 设置字典
        """
        try:
            config = self.load_config()
            
            return {
                "success": True,
                "settings": config
            }
        except Exception as e:
            logger.error(f"[SettingsManager] 读取设置失败: {str(e)}")
            return {
                "success": False,
                "message": f"读取设置失败: {str(e)}",
                "settings": {}
            }
    
    def update_settings(self, updates: Dict) -> Dict:
        """
        更新设置
        
        Args:
            updates: 要更新的设置（部分更新）
            
        Returns:
            dict: 操作结果
        """
        try:
            # 读取当前设置
            config = self.load_config()
            
            logger.info(f"[SettingsManager] ===== 开始更新设置 =====")
            logger.info(f"[SettingsManager] 接收到的更新: {updates}")
            logger.info(f"[SettingsManager] 更新前的 general 配置: {config.get('general', {})}")
            
            # 更新设置（深度合并）
            for section, values in updates.items():
                if section in config and isinstance(config[section], dict):
                    logger.info(f"[SettingsManager] 合并 {section} 配置: {values}")
                    config[section].update(values)
                else:
                    logger.info(f"[SettingsManager] 设置 {section} 配置: {values}")
                    config[section] = values
            
            logger.info(f"[SettingsManager] 更新后的 general 配置: {config.get('general', {})}")
            logger.info(f"[SettingsManager] 完整的合并后配置: {config}")
            
            # 保存设置
            logger.info(f"[SettingsManager] 开始保存配置到文件")
            save_result = self.save_config(config)
            
            if not save_result:
                logger.error(f"[SettingsManager] 保存配置失败")
                return {
                    "success": False,
                    "message": "保存配置失败"
                }
            
            logger.info(f"[SettingsManager] 设置已成功保存到文件")
            logger.info(f"[SettingsManager] ===== 更新设置完成 =====")
            
            return {
                "success": True,
                "message": "设置已保存",
                "settings": config
            }
        except Exception as e:
            logger.error(f"[SettingsManager] 更新设置失败: {str(e)}")
            import traceback
            logger.error(f"[SettingsManager] 错误堆栈: {traceback.format_exc()}")
            return {
                "success": False,
                "message": f"更新设置失败: {str(e)}"
            }
    
    def reset_settings(self) -> Dict:
        """
        重置设置为默认值
        
        Returns:
            dict: 操作结果
        """
        try:
            # 获取默认设置并保存
            default_config = self.get_default_config()
            self.save_config(default_config)
            
            return {
                "success": True,
                "message": "设置已重置为默认值"
            }
        except Exception as e:
            logger.error(f"[SettingsManager] 重置设置失败: {str(e)}")
            return {
                "success": False,
                "message": f"重置设置失败: {str(e)}"
            }
    
    def export_settings(self) -> Dict:
        """
        导出设置（用于迁移）
        
        Returns:
            dict: 设置内容
        """
        return self.get_settings()
    
    def import_settings(self, settings_data: Dict) -> Dict:
        """
        导入设置（用于迁移）
        
        Args:
            settings_data: 设置数据
            
        Returns:
            dict: 操作结果
        """
        try:
            # 验证设置格式
            if "version" not in settings_data:
                return {
                    "success": False,
                    "message": "无效的设置格式：缺少 version 字段"
                }
            
            # 保存设置（基类会自动处理版本迁移）
            self.save_config(settings_data)
            
            return {
                "success": True,
                "message": "设置导入成功"
            }
        except Exception as e:
            logger.error(f"[SettingsManager] 导入设置失败: {str(e)}")
            return {
                "success": False,
                "message": f"导入设置失败: {str(e)}"
            }
    
    # 日志配置相关方法
    
    def get_log_level(self) -> str:
        """
        获取日志级别
        
        Returns:
            日志级别字符串 (DEBUG/INFO/DEV/WARNING/ERROR)
        """
        config = self.load_config()
        return config.get("logging", {}).get("level", "INFO")
    
    def set_log_level(self, level: str) -> Dict:
        """
        设置日志级别
        
        Args:
            level: 日志级别 (DEBUG/INFO/DEV/WARNING/ERROR)
            
        Returns:
            dict: 操作结果
        """
        # 验证日志级别
        valid_levels = {"DEBUG", "INFO", "DEV", "WARNING", "ERROR"}
        level = level.upper()
        
        if level not in valid_levels:
            return {
                "success": False,
                "message": f"无效的日志级别: {level}，有效值为: {', '.join(valid_levels)}"
            }
        
        try:
            config = self.load_config()
            
            # 确保logging配置节存在
            if "logging" not in config:
                config["logging"] = self.get_default_config()["logging"]
            
            config["logging"]["level"] = level
            self.save_config(config)
            
            return {
                "success": True,
                "message": f"日志级别已设置为: {level}"
            }
        except Exception as e:
            logger.error(f"[SettingsManager] 设置日志级别失败: {str(e)}")
            return {
                "success": False,
                "message": f"设置日志级别失败: {str(e)}"
            }
    
    def get_log_keep_days(self) -> int:
        """
        获取日志保留天数
        
        Returns:
            保留天数
        """
        config = self.load_config()
        return config.get("logging", {}).get("keepDays", 30)
    
    def get_log_max_file_size(self) -> int:
        """
        获取日志文件最大大小（字节）
        
        Returns:
            最大文件大小
        """
        config = self.load_config()
        return config.get("logging", {}).get("maxFileSize", 104857600)  # 100MB
    
    # 插件市场配置相关方法
    
    def get_marketplace_settings(self) -> Dict:
        """
        获取插件市场配置
        
        Returns:
            dict: 插件市场配置
        """
        try:
            config = self.load_config()
            marketplace_config = config.get("pluginMarketplace", {})
            
            # 确保有默认值
            if not marketplace_config:
                marketplace_config = self.get_default_config()["pluginMarketplace"]
            
            return {
                "success": True,
                "settings": marketplace_config
            }
        except Exception as e:
            logger.error(f"[SettingsManager] 读取插件市场配置失败: {str(e)}")
            return {
                "success": False,
                "message": f"读取插件市场配置失败: {str(e)}",
                "settings": {}
            }
    
    def update_marketplace_settings(self, updates: Dict) -> Dict:
        """
        更新插件市场配置
        
        Args:
            updates: 要更新的配置项
            
        Returns:
            dict: 操作结果
        """
        try:
            config = self.load_config()
            
            # 确保 pluginMarketplace 配置节存在
            if "pluginMarketplace" not in config:
                config["pluginMarketplace"] = self.get_default_config()["pluginMarketplace"]
            
            # 更新配置（深度合并）
            config["pluginMarketplace"].update(updates)
            
            logger.debug(f"[SettingsManager] 更新插件市场配置: {updates}")
            
            # 保存配置
            save_result = self.save_config(config)
            
            if not save_result:
                logger.error(f"[SettingsManager] 保存插件市场配置失败")
                return {
                    "success": False,
                    "message": "保存插件市场配置失败"
                }
            
            logger.debug(f"[SettingsManager] 插件市场配置已成功保存")
            
            return {
                "success": True,
                "message": "插件市场配置已保存",
                "settings": config["pluginMarketplace"]
            }
        except Exception as e:
            logger.error(f"[SettingsManager] 更新插件市场配置失败: {str(e)}")
            return {
                "success": False,
                "message": f"更新插件市场配置失败: {str(e)}"
            }
    
    def get_auto_install_deps(self) -> bool:
        """
        获取是否自动安装依赖的配置
        
        Returns:
            bool: 是否自动安装依赖
        """
        config = self.load_config()
        return config.get("pluginMarketplace", {}).get("autoInstallDeps", True)
    
    def set_auto_install_deps(self, enabled: bool) -> Dict:
        """
        设置是否自动安装依赖
        
        Args:
            enabled: 是否启用自动安装依赖
            
        Returns:
            dict: 操作结果
        """
        return self.update_marketplace_settings({"autoInstallDeps": enabled})
    def get_last_download_path(self) -> str:
        """
        获取上次图片下载路径
        
        该方法用于获取用户上次选择的图片下载目录。
        
        工作流程：
        1. 从配置文件读取 lastDownloadPath
        2. 如果路径为空，返回系统默认图片文件夹
        3. 如果路径不为空，直接返回（即使路径不存在）
           - 原因：tkinter.filedialog 会自动处理不存在的路径
           - 如果路径不存在，对话框会显示父目录或默认路径
           - 这样可以保留用户的路径偏好，即使目录被临时删除

        Returns:
            str: 上次下载路径，如果为空则返回系统默认图片文件夹
        """
        import os
        
        try:
            # 从配置文件加载设置
            config = self.load_config()
            last_path = config.get("general", {}).get("lastDownloadPath", "")
            
            logger.debug(f"[SettingsManager] 从配置读取 lastDownloadPath: '{last_path}'")
            
            # 如果路径为空，返回系统默认图片文件夹
            if not last_path:
                logger.debug("[SettingsManager] lastDownloadPath 为空，使用系统默认路径")
                # Windows: %USERPROFILE%\Pictures
                if os.name == 'nt':
                    last_path = os.path.join(os.path.expanduser('~'), 'Pictures')
                else:
                    # 其他系统使用用户主目录
                    last_path = os.path.expanduser('~')
                logger.info(f"[SettingsManager] 使用系统默认图片文件夹: {last_path}")
            else:
                # 路径不为空，直接返回
                # 注意：即使路径不存在，也返回它
                # tkinter.filedialog 会自动处理不存在的路径
                if os.path.exists(last_path):
                    logger.debug(f"[SettingsManager] lastDownloadPath 路径有效: {last_path}")
                else:
                    logger.debug(f"[SettingsManager] lastDownloadPath 路径不存在，但仍返回: {last_path}")
                    logger.debug("[SettingsManager] tkinter.filedialog 会自动处理不存在的路径")
            
            return last_path
        except Exception as e:
            logger.error(f"[SettingsManager] 读取 lastDownloadPath 异常: {str(e)}")
            import traceback
            logger.debug(f"[SettingsManager] 错误堆栈:\n{traceback.format_exc()}")
            # 出错时返回系统默认图片文件夹
            if os.name == 'nt':
                default_path = os.path.join(os.path.expanduser('~'), 'Pictures')
            else:
                default_path = os.path.expanduser('~')
            logger.info(f"[SettingsManager] 异常处理：返回系统默认路径: {default_path}")
            return default_path
    
    def set_last_download_path(self, path: str) -> bool:
        """
        保存上次图片下载路径
        
        该方法用于持久化保存用户选择的图片下载目录，以便下次下载时
        文件对话框能够自动定位到该目录。
        
        工作流程：
        1. 判断传入的是文件路径还是目录路径
        2. 如果是文件路径，提取目录部分
        3. 调用 update_settings() 保存到配置文件
        4. 返回保存结果
        
        Args:
            path: 文件完整路径或目录路径
            
        Returns:
            bool: 是否保存成功
        """
        import os
        
        try:
            logger.debug(f"[SettingsManager] 开始保存 lastDownloadPath: {path}")
            
            # 提取目录路径（如果传入的是文件路径）
            # 注意：这里需要区分文件路径和目录路径，因为用户可能传入完整的文件路径
            # 
            # 修复：始终提取目录部分，因为：
            # 1. 如果传入的是文件路径（例如 C:\Users\...\image.png），提取目录
            # 2. 如果传入的是目录路径（例如 C:\Users\...\Pictures），os.path.dirname() 会返回父目录
            # 3. 为了避免这个问题，我们先检查路径是否包含文件扩展名
            
            # 检查是否是文件路径（有扩展名）
            _, ext = os.path.splitext(path)
            if ext:
                # 有扩展名，说明是文件路径，提取目录
                dir_path = os.path.dirname(path)
                logger.debug(f"[SettingsManager] 从文件路径提取目录: {dir_path}")
            else:
                # 没有扩展名，可能是目录路径
                # 但也可能是没有扩展名的文件，所以我们检查路径是否存在
                if os.path.isdir(path):
                    # 确实是目录
                    dir_path = path
                    logger.debug(f"[SettingsManager] 使用目录路径: {dir_path}")
                else:
                    # 不是目录，可能是没有扩展名的文件，或者路径不存在
                    # 为了安全起见，提取父目录
                    dir_path = os.path.dirname(path) if os.path.dirname(path) else path
                    logger.debug(f"[SettingsManager] 路径不是目录，提取父目录: {dir_path}")
            
            # 验证目录是否存在（只是警告，不阻止保存）
            if not os.path.exists(dir_path):
                logger.warning(f"[SettingsManager] 目录不存在，但仍保存配置: {dir_path}")
            elif not os.path.isdir(dir_path):
                logger.warning(f"[SettingsManager] 路径不是目录，但仍保存配置: {dir_path}")
            
            # 调用 update_settings() 保存配置
            logger.debug("[SettingsManager] 调用 update_settings 保存配置")
            result = self.update_settings({
                "general": {
                    "lastDownloadPath": dir_path
                }
            })
            
            if result.get("success", False):
                logger.info(f"[SettingsManager] lastDownloadPath 保存成功: {dir_path}")
            else:
                logger.error(f"[SettingsManager] lastDownloadPath 保存失败: {result.get('message', '未知错误')}")
            
            return result.get("success", False)
        except Exception as e:
            logger.error(f"[SettingsManager] 保存 lastDownloadPath 异常: {str(e)}")
            import traceback
            logger.debug(f"[SettingsManager] 错误堆栈:\n{traceback.format_exc()}")
            return False
    
    def get_github_settings(self) -> Dict:
        """
        获取 GitHub API 配置
        
        Returns:
            dict: GitHub API 配置
        """
        try:
            config = self.load_config()
            github_config = config.get("github", {})
            
            if not github_config:
                github_config = self.get_default_config()["github"]
            
            return {
                "success": True,
                "settings": github_config
            }
        except Exception as e:
            logger.error(f"[SettingsManager] 读取 GitHub 配置失败: {str(e)}")
            return {
                "success": False,
                "message": f"读取 GitHub 配置失败: {str(e)}",
                "settings": {}
            }
    
    def update_github_settings(self, updates: Dict) -> Dict:
        """
        更新 GitHub API 配置
        
        Args:
            updates: 要更新的配置项
            
        Returns:
            dict: 操作结果
        """
        try:
            config = self.load_config()
            
            if "github" not in config:
                config["github"] = self.get_default_config()["github"]
            
            config["github"].update(updates)
            
            logger.debug(f"[SettingsManager] 更新 GitHub 配置: {updates}")
            
            save_result = self.save_config(config)
            
            if not save_result:
                logger.error(f"[SettingsManager] 保存 GitHub 配置失败")
                return {
                    "success": False,
                    "message": "保存 GitHub 配置失败"
                }
            
            logger.debug(f"[SettingsManager] GitHub 配置已成功保存")
            
            return {
                "success": True,
                "message": "GitHub 配置已保存",
                "settings": config["github"]
            }
        except Exception as e:
            logger.error(f"[SettingsManager] 更新 GitHub 配置失败: {str(e)}")
            return {
                "success": False,
                "message": f"更新 GitHub 配置失败: {str(e)}"
            }
    
    def get_github_api_token(self) -> str:
        """
        获取 GitHub API Token
        
        Returns:
            str: GitHub API Token，未配置时返回空字符串
        """
        config = self.load_config()
        github_config = config.get("github", {})
        
        if github_config.get("enabled", False):
            return github_config.get("apiToken", "")
        
        return ""
    
    def is_github_token_enabled(self) -> bool:
        """
        检查 GitHub API Token 是否启用
        
        Returns:
            bool: 是否启用 GitHub API Token
        """
        config = self.load_config()
        return config.get("github", {}).get("enabled", False)
    
    def get_git_config(self) -> Dict:
        """
        获取 Git 配置
        
        Returns:
            dict: Git 配置
        """
        try:
            config = self.load_config()
            git_config = config.get("git", {})
            
            if not git_config:
                git_config = self.get_default_config()["git"]
            
            return {
                "success": True,
                "settings": git_config
            }
        except Exception as e:
            logger.error(f"[SettingsManager] 读取 Git 配置失败: {str(e)}")
            return {
                "success": False,
                "message": f"读取 Git 配置失败: {str(e)}",
                "settings": {}
            }
    
    def update_git_config(self, updates: Dict) -> Dict:
        """
        更新 Git 配置
        
        Args:
            updates: 要更新的配置项
            
        Returns:
            dict: 操作结果
        """
        try:
            config = self.load_config()
            
            if "git" not in config:
                config["git"] = self.get_default_config()["git"]
            
            config["git"].update(updates)
            
            logger.debug(f"[SettingsManager] 更新 Git 配置: {updates}")
            
            save_result = self.save_config(config)
            
            if not save_result:
                logger.error(f"[SettingsManager] 保存 Git 配置失败")
                return {
                    "success": False,
                    "message": "保存 Git 配置失败"
                }
            
            # 清除 GitManager 缓存，强制下次重新获取
            from backend.src.utils.git_manager import git_manager
            git_manager.clear_cache()
            logger.debug(f"[SettingsManager] Git 配置已保存，缓存已清除")
            
            return {
                "success": True,
                "message": "Git 配置已保存",
                "settings": config["git"]
            }
        except Exception as e:
            logger.error(f"[SettingsManager] 更新 Git 配置失败: {str(e)}")
            return {
                "success": False,
                "message": f"更新 Git 配置失败: {str(e)}"
            }
    
    def get_git_mode(self) -> str:
        """
        获取 Git 模式
        
        Returns:
            str: Git 模式 (mingit | system | custom)
        """
        config = self.load_config()
        return config.get("git", {}).get("mode", "mingit")
    
    def set_git_mode(self, mode: str) -> Dict:
        """
        设置 Git 模式
        
        Args:
            mode: Git 模式 (mingit | system | custom)
            
        Returns:
            dict: 操作结果
        """
        valid_modes = {"mingit", "system", "custom"}
        if mode not in valid_modes:
            return {
                "success": False,
                "message": f"无效的 Git 模式: {mode}，有效值为: {', '.join(valid_modes)}"
            }
        
        return self.update_git_config({"mode": mode})
    
    def get_custom_git_path(self) -> str:
        """
        获取自定义 Git 路径
        
        Returns:
            str: 自定义 git.exe 路径
        """
        config = self.load_config()
        return config.get("git", {}).get("customPath", "")
    
    def set_custom_git_path(self, path: str) -> Dict:
        """
        设置自定义 Git 路径
        
        Args:
            path: git.exe 的完整路径
            
        Returns:
            dict: 操作结果
        """
        return self.update_git_config({
            "mode": "custom",
            "customPath": path
        })
    
    def get_floating_window_settings(self) -> Dict:
        """
        获取悬浮窗设置
        
        Returns:
            dict: 悬浮窗设置
        """
        try:
            config = self.load_config()
            floating_config = config.get("floatingWindow", {})
            
            if not floating_config:
                floating_config = {
                    "opacity": 75,
                    "visibleItems": ["cpu", "gpu", "ram", "vram", "net", "page"],
                    "itemOrder": ["cpu", "gpu", "ram", "vram", "net", "page"],
                    "visible": False
                }
            
            if "visible" not in floating_config:
                floating_config["visible"] = False
            
            return {
                "success": True,
                "settings": floating_config
            }
        except Exception as e:
            logger.error(f"[SettingsManager] 读取悬浮窗设置失败: {str(e)}")
            return {
                "success": False,
                "message": f"读取悬浮窗设置失败: {str(e)}",
                "settings": {
                    "opacity": 75,
                    "visibleItems": ["cpu", "gpu", "ram", "vram", "net"],
                    "itemOrder": ["cpu", "gpu", "ram", "vram", "net"],
                    "visible": False
                }
            }
    
    def save_floating_window_settings(self, settings: Dict) -> Dict:
        """
        保存悬浮窗设置
        
        Args:
            settings: 悬浮窗设置
            
        Returns:
            dict: 操作结果
        """
        try:
            config = self.load_config()
            config["floatingWindow"] = settings
            
            save_result = self.save_config(config)
            
            if not save_result:
                logger.error(f"[SettingsManager] 保存悬浮窗设置失败")
                return {
                    "success": False,
                    "message": "保存悬浮窗设置失败"
                }
            
            logger.debug(f"[SettingsManager] 悬浮窗设置已保存: {settings}")
            
            return {
                "success": True,
                "message": "悬浮窗设置已保存",
                "settings": settings
            }
        except Exception as e:
            logger.error(f"[SettingsManager] 保存悬浮窗设置失败: {str(e)}")
            return {
                "success": False,
                "message": f"保存悬浮窗设置失败: {str(e)}"
            }
    
    def get_floating_window_position(self) -> Dict:
        """
        获取悬浮窗位置
        
        Returns:
            dict: {"success": bool, "position": {"x": int, "y": int}}
        """
        try:
            config = self.load_config()
            position = config.get("floatingWindowPosition", {})
            
            return {
                "success": True,
                "position": position
            }
        except Exception as e:
            logger.error(f"[SettingsManager] 读取悬浮窗位置失败: {str(e)}")
            return {
                "success": False,
                "position": {}
            }
    
    def save_floating_window_position(self, x: int, y: int) -> Dict:
        """
        保存悬浮窗位置
        
        Args:
            x: X 坐标
            y: Y 坐标
            
        Returns:
            dict: 操作结果
        """
        try:
            config = self.load_config()
            config["floatingWindowPosition"] = {"x": x, "y": y}
            
            save_result = self.save_config(config)
            
            if not save_result:
                logger.error(f"[SettingsManager] 保存悬浮窗位置失败")
                return {
                    "success": False,
                    "message": "保存悬浮窗位置失败"
                }
            
            logger.debug(f"[SettingsManager] 悬浮窗位置已保存: ({x}, {y})")
            
            return {
                "success": True,
                "message": "悬浮窗位置已保存",
                "position": {"x": x, "y": y}
            }
        except Exception as e:
            logger.error(f"[SettingsManager] 保存悬浮窗位置失败: {str(e)}")
            return {
                "success": False,
                "message": f"保存悬浮窗位置失败: {str(e)}"
            }
    
    def get_translation_settings(self) -> Dict:
        """
        获取翻译设置
        
        Returns:
            dict: 翻译设置
        """
        try:
            config = self.load_config()
            translation_config = config.get("translation", {})
            
            if not translation_config:
                translation_config = self.get_default_config()["translation"]
            
            return {
                "success": True,
                "settings": translation_config
            }
        except Exception as e:
            logger.error(f"[SettingsManager] 读取翻译设置失败: {str(e)}")
            return {
                "success": False,
                "message": f"读取翻译设置失败: {str(e)}",
                "settings": {}
            }
    
    def update_translation_settings(self, updates: Dict) -> Dict:
        """
        更新翻译设置
        
        Args:
            updates: 要更新的翻译设置
            
        Returns:
            dict: 操作结果
        """
        try:
            config = self.load_config()
            
            if "translation" not in config:
                config["translation"] = self.get_default_config()["translation"]
            
            config["translation"].update(updates)
            
            logger.debug(f"[SettingsManager] 更新翻译设置: {updates}")
            
            save_result = self.save_config(config)
            
            if not save_result:
                logger.error(f"[SettingsManager] 保存翻译设置失败")
                return {
                    "success": False,
                    "message": "保存翻译设置失败"
                }
            
            logger.debug(f"[SettingsManager] 翻译设置已保存")
            
            return {
                "success": True,
                "message": "翻译设置已保存",
                "settings": config["translation"]
            }
        except Exception as e:
            logger.error(f"[SettingsManager] 更新翻译设置失败: {str(e)}")
            return {
                "success": False,
                "message": f"更新翻译设置失败: {str(e)}"
            }
    
    def get_translation_provider(self) -> str:
        """
        获取翻译提供商
        
        Returns:
            str: 翻译提供商 (google | llm)
        """
        config = self.load_config()
        return config.get("translation", {}).get("provider", "google")
    
    def get_translation_llm_config_id(self) -> str:
        """
        获取翻译使用的LLM配置ID
        
        Returns:
            str: LLM配置ID
        """
        config = self.load_config()
        return config.get("translation", {}).get("llmConfigId", "")
    
    def get_version_settings(self) -> Dict:
        """
        获取版本设置
        
        Returns:
            dict: 版本设置
        """
        try:
            config = self.load_config()
            version_settings = config.get("versionSettings", {})
            
            if not version_settings:
                version_settings = self.get_default_config()["versionSettings"]
            
            return {
                "success": True,
                "settings": version_settings
            }
        except Exception as e:
            logger.error(f"[SettingsManager] 读取版本设置失败: {str(e)}")
            return {
                "success": False,
                "message": f"读取版本设置失败: {str(e)}",
                "settings": {}
            }
    
    def update_version_settings(self, updates: Dict) -> Dict:
        """
        更新版本设置
        
        Args:
            updates: 要更新的版本设置
            
        Returns:
            dict: 操作结果
        """
        try:
            config = self.load_config()
            
            if "versionSettings" not in config:
                config["versionSettings"] = self.get_default_config()["versionSettings"]
            
            config["versionSettings"].update(updates)
            
            logger.debug(f"[SettingsManager] 更新版本设置: {updates}")
            
            save_result = self.save_config(config)
            
            if not save_result:
                logger.error(f"[SettingsManager] 保存版本设置失败")
                return {
                    "success": False,
                    "message": "保存版本设置失败"
                }
            
            logger.debug(f"[SettingsManager] 版本设置已保存")
            
            return {
                "success": True,
                "message": "版本设置已保存",
                "settings": config["versionSettings"]
            }
        except Exception as e:
            logger.error(f"[SettingsManager] 更新版本设置失败: {str(e)}")
            return {
                "success": False,
                "message": f"更新版本设置失败: {str(e)}"
            }
    
    def get_auto_translate_changelog(self) -> bool:
        """
        获取是否自动翻译更新日志
        
        Returns:
            bool: 是否自动翻译
        """
        config = self.load_config()
        return config.get("versionSettings", {}).get("autoTranslateChangelog", False)
    
    def get_github_mirror_settings(self) -> Dict:
        """
        获取 GitHub 镜像设置
        
        Returns:
            dict: GitHub 镜像设置
        """
        try:
            config = self.load_config()
            mirror_config = config.get("githubMirror", {})
            
            if not mirror_config:
                mirror_config = self.get_default_config()["githubMirror"]
            
            return {
                "success": True,
                "settings": mirror_config
            }
        except Exception as e:
            logger.error(f"[SettingsManager] 读取 GitHub 镜像设置失败: {str(e)}")
            return {
                "success": False,
                "message": f"读取 GitHub 镜像设置失败: {str(e)}",
                "settings": {}
            }
    
    def update_github_mirror_settings(self, updates: Dict) -> Dict:
        """
        更新 GitHub 镜像设置
        
        Args:
            updates: 要更新的配置项
            
        Returns:
            dict: 操作结果
        """
        try:
            config = self.load_config()
            
            if "githubMirror" not in config:
                config["githubMirror"] = self.get_default_config()["githubMirror"]
            
            config["githubMirror"].update(updates)
            
            logger.debug(f"[SettingsManager] 更新 GitHub 镜像设置: {updates}")
            
            save_result = self.save_config(config)
            
            if not save_result:
                logger.error(f"[SettingsManager] 保存 GitHub 镜像设置失败")
                return {
                    "success": False,
                    "message": "保存 GitHub 镜像设置失败"
                }
            
            logger.debug(f"[SettingsManager] GitHub 镜像设置已成功保存")
            
            return {
                "success": True,
                "message": "GitHub 镜像设置已保存",
                "settings": config["githubMirror"]
            }
        except Exception as e:
            logger.error(f"[SettingsManager] 更新 GitHub 镜像设置失败: {str(e)}")
            return {
                "success": False,
                "message": f"更新 GitHub 镜像设置失败: {str(e)}"
            }
    
    def is_github_mirror_enabled(self) -> bool:
        """
        检查 GitHub 镜像加速是否启用
        
        Returns:
            bool: 是否启用
        """
        config = self.load_config()
        return config.get("githubMirror", {}).get("enabled", False)

    def get_pypi_mirror_settings(self) -> Dict:
        """
        获取 PyPI 镜像设置

        Returns:
            dict: PyPI 镜像设置
        """
        try:
            config = self.load_config()
            mirror_config = config.get("pypiMirror", {})

            if not mirror_config:
                mirror_config = self.get_default_config()["pypiMirror"]

            return {
                "success": True,
                "settings": mirror_config
            }
        except Exception as e:
            logger.error(f"[SettingsManager] 读取 PyPI 镜像设置失败: {str(e)}")
            return {
                "success": False,
                "message": f"读取 PyPI 镜像设置失败: {str(e)}",
                "settings": {}
            }

    def update_pypi_mirror_settings(self, updates: Dict) -> Dict:
        """
        更新 PyPI 镜像设置

        Args:
            updates: 要更新的配置项

        Returns:
            dict: 操作结果
        """
        try:
            config = self.load_config()

            if "pypiMirror" not in config:
                config["pypiMirror"] = self.get_default_config()["pypiMirror"]

            config["pypiMirror"].update(updates)

            logger.debug(f"[SettingsManager] 更新 PyPI 镜像设置: {updates}")

            save_result = self.save_config(config)

            if not save_result:
                logger.error(f"[SettingsManager] 保存 PyPI 镜像设置失败")
                return {
                    "success": False,
                    "message": "保存 PyPI 镜像设置失败"
                }

            logger.debug(f"[SettingsManager] PyPI 镜像设置已成功保存")

            return {
                "success": True,
                "message": "PyPI 镜像设置已保存",
                "settings": config["pypiMirror"]
            }
        except Exception as e:
            logger.error(f"[SettingsManager] 更新 PyPI 镜像设置失败: {str(e)}")
            return {
                "success": False,
                "message": f"更新 PyPI 镜像设置失败: {str(e)}"
            }

    def is_pypi_mirror_enabled(self) -> bool:
        """
        检查 PyPI 镜像加速是否启用

        Returns:
            bool: 是否启用
        """
        config = self.load_config()
        return config.get("pypiMirror", {}).get("enabled", False)
