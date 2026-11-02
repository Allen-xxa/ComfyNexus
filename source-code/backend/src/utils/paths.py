"""
路径管理工具模块

提供统一的路径管理功能，确保所有模块使用一致的路径配置。
支持开发环境和生产环境的路径切换。

Author: ComfyNexus 开发团队
Date: 2026-02-09
"""

import sys
import os
from pathlib import Path
from typing import Optional


def get_project_root() -> Path:
    """
    获取项目根目录（运行时数据目录）
    
    Returns:
        Path: 项目根目录的绝对路径
        
    说明：
        - 开发环境：返回项目根目录（backend 的父目录）
        - 打包环境：返回可执行文件所在目录（exe 同级目录）
        
    注意：
        此函数返回的是运行时数据目录，用于存储 logs、config、data、cache 等
        用户数据。不要用于访问打包在 _internal 中的只读资源。
    """
    if getattr(sys, 'frozen', False):
        # 打包后的生产环境：返回 exe 所在目录
        return Path(sys.executable).parent
    else:
        # 开发环境：backend/src/utils/paths.py -> 项目根目录
        return Path(__file__).parent.parent.parent.parent


def get_internal_dir() -> Path:
    """
    获取内部资源目录（打包环境专用）
    
    Returns:
        Path: 内部资源目录的绝对路径
        
    说明：
        - 开发环境：返回项目根目录（与 get_project_root() 相同）
        - 打包环境：返回 _internal 目录（PyInstaller 解压目录）
        
    用途：
        用于访问打包在 _internal 中的只读资源，如：
        - dist/（前端构建文件）
        - backend/（后端代码）
        - VERSION 文件等
    """
    if getattr(sys, 'frozen', False):
        # 打包后的生产环境
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller 临时解压目录
            return Path(sys._MEIPASS)
        else:
            # 其他打包方式
            return Path(sys.executable).parent
    else:
        # 开发环境：与项目根目录相同
        return Path(__file__).parent.parent.parent.parent


def get_data_dir(subdir: Optional[str] = None) -> Path:
    """
    获取数据目录
    
    Args:
        subdir: 子目录名称（可选）
        
    Returns:
        Path: 数据目录的绝对路径
        
    Example:
        >>> get_data_dir()  # 返回 <项目根>/data
        >>> get_data_dir("ai_assistant")  # 返回 <项目根>/data/ai_assistant
    """
    data_dir = get_project_root() / "data"
    
    if subdir:
        data_dir = data_dir / subdir
    
    # 确保目录存在
    data_dir.mkdir(parents=True, exist_ok=True)
    
    return data_dir


def get_cache_dir(subdir: Optional[str] = None) -> Path:
    """
    获取缓存目录
    
    Args:
        subdir: 子目录名称（可选）
        
    Returns:
        Path: 缓存目录的绝对路径
        
    Example:
        >>> get_cache_dir()  # 返回 <项目根>/cache
        >>> get_cache_dir("ai_models")  # 返回 <项目根>/cache/ai_models
    """
    cache_dir = get_project_root() / "cache"
    
    if subdir:
        cache_dir = cache_dir / subdir
    
    # 确保目录存在
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    return cache_dir


def get_update_cache_dir() -> Path:
    """
    获取更新缓存目录（用于存储下载的更新包）
    
    Returns:
        Path: 更新缓存目录的绝对路径
        
    说明：
        - 开发环境：<项目根>/cache/updates
        - 打包环境：<exe同级>/cache/updates
        
    用途：
        - 存储下载的更新包（.zip 文件）
        - 存储部分下载文件（.downloading 后缀）
        - 存储下载元数据（.meta 文件）
    """
    update_cache_dir = get_cache_dir("updates")
    update_cache_dir.mkdir(parents=True, exist_ok=True)
    return update_cache_dir


def get_log_dir(subdir: Optional[str] = None) -> Path:
    """
    获取日志目录
    
    Args:
        subdir: 子目录名称（可选）
        
    Returns:
        Path: 日志目录的绝对路径
        
    Example:
        >>> get_log_dir()  # 返回 <项目根>/logs
        >>> get_log_dir("comfyui")  # 返回 <项目根>/logs/comfyui
    """
    log_dir = get_project_root() / "logs"
    
    if subdir:
        log_dir = log_dir / subdir
    
    # 确保目录存在
    log_dir.mkdir(parents=True, exist_ok=True)
    
    return log_dir


def get_config_dir(subdir: Optional[str] = None) -> Path:
    """
    获取配置目录
    
    Args:
        subdir: 子目录名称（可选）
        
    Returns:
        Path: 配置目录的绝对路径
        
    说明：
        - 开发环境：<项目根>/backend/config
        - 打包环境：<exe同级>/config
        
    Example:
        >>> get_config_dir()  # 返回配置目录
        >>> get_config_dir("presets")  # 返回配置目录/presets
    """
    if getattr(sys, 'frozen', False):
        # 打包环境：配置文件在 exe 同级的 config 目录
        config_dir = get_project_root() / "config"
    else:
        # 开发环境：配置文件在 backend/config
        config_dir = get_project_root() / "backend" / "config"
    
    if subdir:
        config_dir = config_dir / subdir
    
    # 确保目录存在
    config_dir.mkdir(parents=True, exist_ok=True)
    
    return config_dir


def get_user_data_dir() -> Path:
    """
    获取用户数据目录（系统级）
    
    Returns:
        Path: 用户数据目录的绝对路径
        
    说明：
        - Windows: %APPDATA%/ComfyNexus
        - Linux: ~/.local/share/ComfyNexus
        - macOS: ~/Library/Application Support/ComfyNexus
        
    注意：
        此函数返回系统级用户数据目录，适合存储用户配置和数据。
        当前项目使用项目根目录存储数据，此函数保留用于未来扩展。
    """
    if os.name == 'nt':  # Windows
        base = Path(os.environ.get('APPDATA', Path.home()))
    elif sys.platform == 'darwin':  # macOS
        base = Path.home() / "Library" / "Application Support"
    else:  # Linux
        base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / ".local" / "share"))
    
    user_data_dir = base / "ComfyNexus"
    user_data_dir.mkdir(parents=True, exist_ok=True)
    
    return user_data_dir


def get_version_file() -> Path:
    """
    获取版本文件路径
    
    Returns:
        Path: 版本文件的绝对路径
        
    说明：
        - 开发环境：<项目根>/comfy_nexus_version.py
        - 打包环境：<_internal>/comfy_nexus_version.py
        
    Example:
        >>> version_file = get_version_file()
        >>> content = version_file.read_text(encoding='utf-8')
    """
    if getattr(sys, 'frozen', False):
        # 打包环境：版本文件在 _internal 目录
        return get_internal_dir() / "comfy_nexus_version.py"
    else:
        # 开发环境：版本文件在项目根目录
        return get_project_root() / "comfy_nexus_version.py"


def get_dev_update_source_file() -> Path:
    """
    获取开发模式更新源文件路径
    
    Returns:
        Path: dev 文件的绝对路径
        
    说明：
        - 开发环境：<项目根>/dev
        - 打包环境：<exe同级>/dev
        
    用途：
        用于测试更新功能，文件内容为自定义仓库地址
        格式: https://<token>@github.com/<owner>/<repo>
        例如: https://ghp_xxxx@github.com/qiqStrong/ComfyNexus_VM
    """
    return get_project_root() / "dev"


def get_settings_file() -> Path:
    """
    获取 settings.json 文件路径
    
    Returns:
        Path: settings.json 文件的绝对路径
        
    Example:
        >>> settings_file = get_settings_file()
        >>> with open(settings_file, 'r', encoding='utf-8') as f:
        ...     config = json.load(f)
    """
    return get_config_dir() / "settings.json"


def get_default_config_file() -> Path:
    """
    获取 default_config.json 文件路径
    
    Returns:
        Path: default_config.json 文件的绝对路径
        
    Example:
        >>> config_file = get_default_config_file()
        >>> with open(config_file, 'r', encoding='utf-8') as f:
        ...     config = json.load(f)
    """
    return get_config_dir() / "default_config.json"


def get_database_file(db_name: str = "ai_assistant.db") -> Path:
    """
    获取数据库文件路径
    
    Args:
        db_name: 数据库文件名，默认为 "ai_assistant.db"
        
    Returns:
        Path: 数据库文件的绝对路径
        
    Example:
        >>> db_file = get_database_file()
        >>> conn = sqlite3.connect(db_file)
    """
    return get_data_dir() / db_name


def get_prompt_data_dir(subdir: Optional[str] = None) -> Path:
    """
    获取提示词库数据目录
    
    Args:
        subdir: 子目录名称（可选）
        
    Returns:
        Path: data/prompt/ 目录的绝对路径
        
    Example:
        >>> get_prompt_data_dir()  # 返回 <项目根>/data/prompt
        >>> get_prompt_data_dir("images")  # 返回 <项目根>/data/prompt/images
    """
    prompt_dir = get_data_dir() / "prompt"
    
    if subdir:
        prompt_dir = prompt_dir / subdir
    
    # 确保目录存在
    prompt_dir.mkdir(parents=True, exist_ok=True)
    
    return prompt_dir


def get_prompt_images_dir() -> Path:
    """
    获取提示词库图片存储目录
    
    Returns:
        Path: data/prompt/images/ 目录的绝对路径
        
    Example:
        >>> get_prompt_images_dir()  # 返回 <项目根>/data/prompt/images
    """
    return get_prompt_data_dir("images")


def get_tools_dir(subdir: Optional[str] = None) -> Path:
    """
    获取工具目录
    
    Args:
        subdir: 子目录名称（可选）
        
    Returns:
        Path: 工具目录的绝对路径
        
    说明：
        - 开发环境：<项目根>/backend/（MinGit 在 backend 子目录下）
        - 打包环境：<exe同级>/tools/
        
    用途：
        用于存储外部工具，如 MinGit 等。
        
    Example:
        >>> get_tools_dir()  # 返回工具目录
        >>> get_tools_dir("mingit")  # 返回工具目录/mingit
    """
    if getattr(sys, 'frozen', False):
        tools_dir = get_project_root() / "tools"
    else:
        tools_dir = get_project_root() / "backend"
    
    if subdir:
        tools_dir = tools_dir / subdir
    
    return tools_dir


def get_mingit_dir() -> Path:
    """
    获取 MinGit 目录
    
    Returns:
        Path: MinGit 目录的绝对路径
        
    说明：
        - 开发环境：<项目根>/backend/MinGit-2.53.0-64-bit/
        - 打包环境：<exe同级>/tools/mingit/
        
    注意：
        此函数不自动创建目录，仅返回路径。
        MinGit 的存在性检查由 GitManager 负责。
    """
    if getattr(sys, 'frozen', False):
        return get_project_root() / "tools" / "mingit"
    else:
        return get_project_root() / "backend" / "MinGit-2.53.0-64-bit"


def get_old_mingit_dirs() -> list[Path]:
    """
    获取旧版 MinGit 可能存在的目录列表（用于迁移）
    
    Returns:
        list[Path]: 旧版 MinGit 目录列表
        
    说明：
        打包环境中，旧版本的 MinGit 可能存在于 _internal/backend/ 下。
        此函数返回所有可能的旧版本目录，用于迁移检测。
    """
    old_dirs = []
    
    if getattr(sys, 'frozen', False):
        internal_dir = get_internal_dir()
        old_patterns = [
            "MinGit-2.53.0-64-bit",
            "MinGit-2.52.0-64-bit",
            "MinGit-2.51.0-64-bit",
        ]
        for pattern in old_patterns:
            old_path = internal_dir / "backend" / pattern
            if old_path.exists():
                old_dirs.append(old_path)
    
    return old_dirs


def get_nsfw_model_path() -> Path:
    """
    获取 NSFW 分类模型路径
    
    Returns:
        Path: NSFW 模型文件的绝对路径
        
    说明：
        - 开发环境：<项目根>/backend/models/nsfw.onnx
        - 打包环境：<_internal>/models/nsfw.onnx
        
    用途：
        用于图片 NSFW 自动分级功能
    """
    if getattr(sys, 'frozen', False):
        return get_internal_dir() / "models" / "nsfw.onnx"
    else:
        return get_project_root() / "backend" / "models" / "nsfw.onnx"


# 便捷常量（向后兼容）
PROJECT_ROOT = get_project_root()
INTERNAL_DIR = get_internal_dir()
DATA_DIR = get_data_dir()
CACHE_DIR = get_cache_dir()
LOG_DIR = get_log_dir()
CONFIG_DIR = get_config_dir()
PROMPT_DATA_DIR = get_prompt_data_dir()
PROMPT_IMAGES_DIR = get_prompt_images_dir()
TOOLS_DIR = get_tools_dir()
MINGIT_DIR = get_mingit_dir()


if __name__ == "__main__":
    # 测试路径管理工具
    print("=" * 60)
    print("路径管理工具测试")
    print("=" * 60)
    print(f"项目根目录（运行时数据）: {get_project_root()}")
    print(f"内部资源目录: {get_internal_dir()}")
    print(f"数据目录: {get_data_dir()}")
    print(f"缓存目录: {get_cache_dir()}")
    print(f"日志目录: {get_log_dir()}")
    print(f"配置目录: {get_config_dir()}")
    print(f"用户数据目录: {get_user_data_dir()}")
    print("=" * 60)
    print(f"版本文件: {get_version_file()}")
    print(f"设置文件: {get_settings_file()}")
    print("=" * 60)
    print(f"提示词库数据目录: {get_prompt_data_dir()}")
    print(f"提示词库图片目录: {get_prompt_images_dir()}")
    print("=" * 60)
