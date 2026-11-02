"""
插件市场常量定义

定义插件市场功能所需的所有常量
"""

from pathlib import Path
import sys


# ============================================================================
# 数据源 URL
# ============================================================================

# ComfyUI-Manager GitHub 统计数据（包含下载量和星标）
GITHUB_STATS_URL = "https://raw.githubusercontent.com/Comfy-Org/ComfyUI-Manager/refs/heads/main/github-stats.json"

# ComfyUI-Manager 自定义节点列表
CUSTOM_NODE_LIST_URL = "https://raw.githubusercontent.com/Comfy-Org/ComfyUI-Manager/refs/heads/main/custom-node-list.json"

# ComfyUI-Manager 节点映射表（用于获取节点数量）
NODE_MAP_URL = "https://raw.githubusercontent.com/Comfy-Org/ComfyUI-Manager/refs/heads/main/extension-node-map.json"

# ComfyUI 官方 API 数据（由 ComfyNexus 通过 GitHub Action 定期拉取）
COMFYUI_API_URL = "https://raw.githubusercontent.com/qiqStrong/ComfyNexus/main/comfyui_api_nodes.json"


# ============================================================================
# 缓存配置
# ============================================================================

# 缓存有效期（秒）
CACHE_DURATION = 24 * 60 * 60  # 24 小时

# 缓存文件名
PLUGINS_CACHE_FILE = "plugins_cache.json"
RECOMMENDED_CACHE_FILE = "recommended_cache.json"
NODE_TYPE_MAP_CACHE_FILE = "node_type_map.json"


# ============================================================================
# 网络配置
# ============================================================================

# 网络请求超时时间（秒）
REQUEST_TIMEOUT = 10

# 最大重试次数（总尝试次数 = 1 次初始尝试 + MAX_RETRIES 次重试）
MAX_RETRIES = 2  # 1 次初始尝试 + 1 次重试 = 总共 2 次尝试


# ============================================================================
# 安装配置
# ============================================================================

# Git 克隆深度（已废弃 - 现在使用完整克隆）
# 完整克隆可以保留完整的 Git 历史记录，支持版本管理、更新检测、回滚等功能
# GIT_CLONE_DEPTH = 1  # 旧的浅克隆配置

# 日志文件名前缀
LOG_FILE_PREFIX = "plugin_install"


# ============================================================================
# 路径配置
# ============================================================================

def get_project_root() -> Path:
    """
    获取项目根目录
    
    Returns:
        项目根目录路径
    """
    from backend.src.utils.paths import get_project_root as _get_project_root
    return _get_project_root()


def get_cache_dir() -> Path:
    """
    获取缓存目录
    
    Returns:
        缓存目录路径
    """
    from backend.src.utils.paths import get_cache_dir as _get_cache_dir
    return _get_cache_dir("marketplace")


def get_config_dir() -> Path:
    """
    获取配置目录
    
    Returns:
        配置目录路径
    """
    from backend.src.utils.paths import get_config_dir as _get_config_dir
    return _get_config_dir()


def get_logs_dir() -> Path:
    """
    获取日志目录
    
    Returns:
        日志目录路径
    """
    from backend.src.utils.paths import get_log_dir
    return get_log_dir()


def get_recommended_plugins_file() -> Path:
    """
    获取推荐插件配置文件路径
    
    Returns:
        推荐插件配置文件路径
    """
    return get_config_dir() / "recommended_plugins.txt"


def get_settings_file() -> Path:
    """
    获取设置文件路径
    
    Returns:
        设置文件路径
    """
    return get_config_dir() / "settings.json"


# ============================================================================
# 分页配置
# ============================================================================

# 每页显示的插件数量
PLUGINS_PER_PAGE = 30

# 插件卡片网格列数
GRID_COLUMNS_LARGE = 5   # 大屏幕（>= 1200px）
GRID_COLUMNS_MEDIUM = 4  # 中等屏幕（900px - 1200px）
GRID_COLUMNS_SMALL = 3   # 小屏幕（< 900px）


# ============================================================================
# 性能配置
# ============================================================================

# 搜索防抖延迟（毫秒）
SEARCH_DEBOUNCE_MS = 300

# 滚动加载延迟（毫秒）
SCROLL_LOAD_DELAY_MS = 500

# 虚拟滚动缓冲区大小（额外渲染的项目数）
VIRTUAL_SCROLL_BUFFER = 10


# ============================================================================
# 错误消息
# ============================================================================

ERROR_NETWORK_FAILED = "网络连接失败，请检查网络设置"
ERROR_DATA_PARSE_FAILED = "数据格式错误，请稍后重试"
ERROR_GIT_CLONE_FAILED = "Git 克隆失败"
ERROR_PIP_INSTALL_FAILED = "依赖安装失败"
ERROR_ENV_NOT_CONFIGURED = "请先配置 ComfyUI 环境"
ERROR_DISK_SPACE_INSUFFICIENT = "磁盘空间不足，无法安装插件"
ERROR_INVALID_GITHUB_URL = "无效的 GitHub 地址"
ERROR_PATH_TRAVERSAL = "检测到路径遍历攻击"
ERROR_COMMAND_INJECTION = "检测到命令注入攻击"


# ============================================================================
# 成功消息
# ============================================================================

SUCCESS_PLUGIN_INSTALLED = "插件安装成功"
SUCCESS_CACHE_CLEARED = "缓存已清除"
SUCCESS_SETTINGS_SAVED = "设置已保存"
