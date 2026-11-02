"""
依赖管理控制器
用于处理前端的依赖管理请求
"""

from typing import Dict, Optional, List
import subprocess
import json
import platform
import uuid
import os
import sys
import re
import shlex
from pathlib import Path
from datetime import datetime

from ...utils.logger import app_logger as logger
from ...utils.path_serializer import serialize_response
from ...utils.python_command import PythonCommandBuilder
from ...utils.subprocess_utils import popen_powershell, get_creation_flags
from ...core.ai_analyzer import AIAnalyzer
from ...core.plugin.dependency_manager import DependencyManager


def _validate_package_name(package_name: str) -> bool:
    """
    验证包名格式，防止命令注入
    
    符合 PEP 508 规范的包名:
    - 以字母或数字开头
    - 只包含字母、数字、下划线、连字符、点
    - 长度限制在 1-200 字符
    
    Args:
        package_name: 要验证的包名
        
    Returns:
        是否为有效的包名格式
    """
    if not package_name or not isinstance(package_name, str):
        return False
    
    if len(package_name) > 200:
        return False
    
    pattern = r'^[A-Za-z0-9][A-Za-z0-9._-]*$'
    return bool(re.match(pattern, package_name))


def _sanitize_for_powershell(text: str) -> str:
    """
    清理字符串中的特殊字符，防止 PowerShell 命令注入
    
    移除或转义可能导致命令注入的字符：
    - 引号
    - 分号
    - 反引号
    - 美元符号
    - 换行符
    
    Args:
        text: 要清理的文本
        
    Returns:
        清理后的安全文本
    """
    if not text:
        return ""
    
    dangerous_chars = ['"', "'", ';', '`', '$', '\n', '\r', '\x00']
    sanitized = text
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, '')
    
    return sanitized.strip()


def _sanitize_path_for_display(path: str) -> str:
    """
    清理路径字符串用于显示，移除敏感信息
    
    Args:
        path: 原始路径
        
    Returns:
        清理后的安全路径
    """
    if not path:
        return ""
    
    return _sanitize_for_powershell(str(path))


def _escape_for_powershell(text: str) -> str:
    """
    转义 PowerShell 字符串中的特殊字符
    
    在 PowerShell 中，双引号字符串内的特殊字符需要用反引号转义：
    - `"` → `` `" ``
    - `$` → `` `$ ``
    - ``` ` ``` → `` `` ``
    
    Args:
        text: 要转义的文本
        
    Returns:
        转义后的安全文本
    """
    if not text:
        return ""
    
    text = text.replace('`', '``')
    text = text.replace('"', '`"')
    text = text.replace('$', '`$')
    
    return text


def _validate_file_path(file_path: str, allowed_dirs: Optional[List[str]] = None) -> tuple:
    """
    验证文件路径是否安全
    
    检查路径是否为有效的文件，并防止访问系统敏感目录。
    
    Args:
        file_path: 要验证的文件路径
        allowed_dirs: 保留参数，向后兼容
        
    Returns:
        tuple: (is_valid: bool, error_message: Optional[str])
    """
    if not file_path:
        return False, "文件路径不能为空"
    
    try:
        path = Path(file_path).resolve()
        
        if not path.exists():
            return False, "文件不存在"
        
        if not path.is_file():
            return False, "指定路径不是文件"
        
        path_str = str(path).lower()
        
        dangerous_patterns = ['../', '..\\', '/etc/', '/root/', '\\windows\\', '\\system32\\']
        for pattern in dangerous_patterns:
            if pattern in path_str:
                return False, "文件路径包含不允许的字符"
        
        return True, None
        
    except Exception as e:
        return False, f"路径验证失败: {str(e)}"


# 镜像源配置
MIRROR_SOURCES = {
    'official': {
        'pypi': 'https://pypi.org',
        'pip_index': 'https://pypi.org/simple'
    },
    'tuna': {
        'pypi': 'https://pypi.tuna.tsinghua.edu.cn',
        'pip_index': 'https://pypi.tuna.tsinghua.edu.cn/simple'
    },
    'bfsu': {
        'pypi': 'https://mirrors.bfsu.edu.cn',
        'pip_index': 'https://mirrors.bfsu.edu.cn/pypi/web/simple'
    },
    'aliyun': {
        'pypi': 'https://mirrors.aliyun.com',
        'pip_index': 'https://mirrors.aliyun.com/pypi/simple'
    },
    'tencent': {
        'pypi': 'https://mirrors.cloud.tencent.com',
        'pip_index': 'https://mirrors.cloud.tencent.com/pypi/simple'
    }
}


def _get_pypi_mirror_config(mirror_source: str) -> dict:
    """获取 PyPI 镜像源配置，支持 auto 模式自动调度"""
    logger.dev(f"[PyPI Mirror] 请求镜像源配置: {mirror_source}")
    
    if mirror_source == 'auto':
        try:
            from backend.src.utils.pypi_mirror import pypi_mirror_manager
            if pypi_mirror_manager.is_enabled():
                source_name = pypi_mirror_manager.get_current_source_name()
                source = pypi_mirror_manager.get_current_source()
                if source:
                    logger.dev(f"[PyPI Mirror] Auto 模式 -> 镜像加速已启用，使用: {source_name}")
                    logger.dev(f"[PyPI Mirror] pip index URL: {source['pip_index']}")
                    return {
                        'pypi': source['pypi'],
                        'pip_index': source['pip_index'],
                    }
                else:
                    logger.dev(f"[PyPI Mirror] Auto 模式 -> 镜像加速已启用但无可用源，回退到 tuna")
            else:
                logger.dev(f"[PyPI Mirror] Auto 模式 -> 镜像加速未启用，回退到 tuna")
        except Exception as e:
            logger.dev(f"[PyPI Mirror] Auto 模式 -> 获取镜像配置异常: {e}，回退到 tuna")
        return MIRROR_SOURCES['tuna']
    
    config = MIRROR_SOURCES.get(mirror_source, MIRROR_SOURCES['official'])
    logger.dev(f"[PyPI Mirror] 使用指定镜像源: {mirror_source}")
    logger.dev(f"[PyPI Mirror] pip index URL: {config['pip_index']}")
    return config


class DependencyController:
    """依赖管理控制器"""
    
    PYTORCH_MAPPING_URL = "https://raw.githubusercontent.com/qiqStrong/ComfyNexus/refs/heads/main/pytorch_mapping.json"
    _pytorch_mapping_cache = None
    _pytorch_mapping_cache_time = None
    _pytorch_mapping_cache_ttl = 86400
    
    def __init__(self, environment_manager=None):
        """
        初始化控制器
        
        Args:
            environment_manager: 环境管理器实例
        """
        self.environment_manager = environment_manager
        self._window = None
        self.ai_analyzer = AIAnalyzer()
    
    def set_window(self, window):
        """设置 pywebview 窗口引用"""
        self._window = window
        self.ai_analyzer.set_window(window)
    
    def _fetch_pytorch_version_mapping(self) -> Optional[Dict]:
        """
        获取 PyTorch 版本映射表
        
        优先使用缓存（24小时有效期），缓存失效或不存在时从远程获取。
        
        Returns:
            dict: 版本映射表，格式为 {"torch版本": {"torchvision": "x.x.x", "torchaudio": "x.x.x"}}
            None: 获取失败时返回 None
        """
        import time
        import urllib.request
        import urllib.error
        
        current_time = time.time()
        cls = self.__class__
        
        if (cls._pytorch_mapping_cache is not None and 
            cls._pytorch_mapping_cache_time is not None and
            current_time - cls._pytorch_mapping_cache_time < cls._pytorch_mapping_cache_ttl):
            logger.debug("[DependencyController] 使用缓存的 PyTorch 版本映射表")
            return cls._pytorch_mapping_cache
        
        try:
            url = cls.PYTORCH_MAPPING_URL
            request_headers = {'User-Agent': 'ComfyNexus/1.0'}
            verify_ssl = True
            
            try:
                from backend.src.utils.github_mirror import github_mirror_manager
                if github_mirror_manager.is_enabled():
                    mirror_url, mirror_headers = github_mirror_manager.transform_url(url, "raw")
                    url = mirror_url
                    request_headers.update(mirror_headers)
                    settings = github_mirror_manager._load_settings()
                    verify_ssl = settings.get("verifySSL", True)
            except Exception:
                pass
            
            logger.info(f"[DependencyController] 正在获取 PyTorch 版本映射表: {url}")
            
            request = urllib.request.Request(
                url,
                headers=request_headers
            )
            
            ssl_context = None
            if not verify_ssl:
                import ssl
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = 0
            
            with urllib.request.urlopen(request, timeout=10, context=ssl_context) as response:
                data = response.read().decode('utf-8')
                mapping = json.loads(data)
                
                cls._pytorch_mapping_cache = mapping
                cls._pytorch_mapping_cache_time = current_time
                
                logger.info(f"[DependencyController] 成功获取 PyTorch 版本映射表，共 {len(mapping)} 个版本")
                return mapping
                
        except urllib.error.URLError as e:
            logger.warning(f"[DependencyController] 获取 PyTorch 版本映射表失败（网络错误）: {str(e)}")
        except urllib.error.HTTPError as e:
            logger.warning(f"[DependencyController] 获取 PyTorch 版本映射表失败（HTTP {e.code}）: {str(e)}")
        except json.JSONDecodeError as e:
            logger.warning(f"[DependencyController] 解析 PyTorch 版本映射表失败: {str(e)}")
        except Exception as e:
            logger.warning(f"[DependencyController] 获取 PyTorch 版本映射表时发生未知错误: {str(e)}")
        
        return None
    
    @classmethod
    def _get_compatible_versions(cls, torch_version: str) -> Optional[Dict[str, str]]:
        """
        智能推导 torchvision 和 torchaudio 的版本号
        
        三级策略：
        1. 精确匹配：直接在映射表中找到
        2. 同级推导：基于同系列 .0 版本推导
        3. 终极兜底：使用祖传公式（vision 次版本号 = torch 次版本号 + 15）
        
        Args:
            torch_version: torch 版本号（可能包含 CUDA 后缀，如 "2.9.0+cu128"）
            
        Returns:
            dict: {"torchvision": "x.x.x", "torchaudio": "x.x.x", "match_type": "exact|derived|formula"} 或 None
        """
        if cls._pytorch_mapping_cache is None:
            return None
        
        pure_version = torch_version.split('+')[0]
        
        if pure_version in cls._pytorch_mapping_cache:
            result = cls._pytorch_mapping_cache[pure_version].copy()
            result['match_type'] = 'exact'
            return result
        
        parts = pure_version.split('.')
        if len(parts) >= 2:
            major, minor = parts[0], parts[1]
            patch = parts[2] if len(parts) > 2 else "0"
            
            base_version = f"{major}.{minor}.0"
            if base_version in cls._pytorch_mapping_cache:
                base_mapping = cls._pytorch_mapping_cache[base_version]
                base_vision = base_mapping.get("torchvision", "")
                
                vision_parts = base_vision.split('.')
                if len(vision_parts) >= 3:
                    vision_parts[2] = patch
                    
                return {
                    "torchvision": ".".join(vision_parts),
                    "torchaudio": pure_version,
                    "match_type": "derived"
                }
            
            if major == "2":
                try:
                    vision_minor = int(minor) + 15
                    return {
                        "torchvision": f"0.{vision_minor}.{patch}",
                        "torchaudio": pure_version,
                        "match_type": "formula"
                    }
                except ValueError:
                    pass
        
        return None
    
    def _push_log(self, level: str, message: str, source: str = 'pip') -> str:
        """
        推送日志到前端
        
        Args:
            level: 日志级别 (INFO/WARNING/ERROR/SUCCESS)
            message: 日志消息
            source: 日志来源 (pip/system)
            
        Returns:
            日志ID
        """
        log_id = str(uuid.uuid4())
        log = {
            'id': log_id,
            'timestamp': datetime.now().isoformat(),  # 使用 ISO 格式
            'level': level.lower(),
            'source': source,
            'message': message.strip()
        }
        
        # 通过 pywebview 推送到前端
        if self._window:
            try:
                js_code = f'window.onDependencyLog && window.onDependencyLog({json.dumps(log)})'
                self._window.evaluate_js(js_code)
            except Exception as e:
                logger.warning(f'推送依赖日志失败: {e}')
        
        return log_id
    
    def _extract_error_message(self, output_lines: list, package_name: str) -> str:
        """
        从 pip 输出中提取错误信息
        
        Args:
            output_lines: pip 命令的输出行列表
            package_name: 包名
            
        Returns:
            友好的错误信息（已清理内部路径）
        """
        error_patterns = [
            ('Could not find a version', f'找不到包 {package_name} 的指定版本'),
            ('No matching distribution found', f'找不到包 {package_name}'),
            ('ERROR: Could not find', f'找不到包 {package_name}'),
            ('Connection error', '网络连接失败'),
            ('Read timed out', '网络超时'),
            ('SSLError', 'SSL 证书验证失败'),
            ('Permission denied', '权限不足'),
            ('Requirement already satisfied', '包已安装'),
            ('incompatible', '版本不兼容'),
            ('conflict', '依赖冲突'),
        ]
        
        for line in reversed(output_lines):
            line_lower = line.lower()
            
            for pattern, friendly_msg in error_patterns:
                if pattern.lower() in line_lower:
                    return friendly_msg
            
            if 'error:' in line_lower:
                error_text = line.split('ERROR:', 1)[-1].strip()
                if error_text:
                    cleaned_text = self._sanitize_error_message(error_text)
                    return cleaned_text[:100]
        
        return '安装失败，请查看日志了解详情'
    
    def _sanitize_error_message(self, message: str) -> str:
        """
        清理错误消息中的敏感信息和内部路径
        
        Args:
            message: 原始错误消息
            
        Returns:
            清理后的安全错误消息
        """
        import re
        
        sanitized = message
        
        path_pattern = r'[A-Za-z]:\\[^\s:]+|/home/[^\s/]+|/Users/[^\s/]+|/root/[^\s/]+'
        sanitized = re.sub(path_pattern, '[路径]', sanitized)
        
        user_pattern = r'\\Users\\[^\\]+'
        sanitized = re.sub(user_pattern, '[用户目录]', sanitized)
        
        temp_pattern = r'\\AppData\\Local\\Temp[^\s]*'
        sanitized = re.sub(temp_pattern, '[临时目录]', sanitized, flags=re.IGNORECASE)
        
        if len(sanitized) > 150:
            sanitized = sanitized[:150] + '...'
        
        return sanitized
    
    def _push_operation_start(self, operation_type: str, target: str):
        """
        推送操作开始的分割符日志
        
        Args:
            operation_type: 操作类型（如：安装、卸载、扫描等）
            target: 操作目标（如：包名、文件名等）
        """
        separator = '-' * 70
        header = f" 正在{operation_type} {target} "
        formatted_header = header.center(70, '-')
        self._push_log('INFO', '', 'system')
        self._push_log('INFO', separator, 'system')
        self._push_log('INFO', formatted_header, 'system')
        self._push_log('INFO', separator, 'system')
    
    def _push_operation_end(self, success: bool, message: str):
        """
        推送操作结束的分割符日志
        
        Args:
            success: 是否成功
            message: 结束消息
        """
        separator = '-' * 70
        icon = '✅' if success else '❌'
        self._push_log('INFO', '', 'system')
        self._push_log('SUCCESS' if success else 'ERROR', f'{icon} {message}', 'system')
        self._push_log('INFO', separator, 'system')
        self._push_log('INFO', '', 'system')
    
    def _push_analysis_log(self, file_path: str, dependencies: list, stats: dict):
        """
        推送依赖分析的格式化日志
        
        Args:
            file_path: 文件路径
            dependencies: 依赖列表
            stats: 统计信息
        """
        from pathlib import Path
        
        file_name = Path(file_path).name
        
        self._push_operation_start('分析', f'{file_name} 依赖列表')
        
        for dep in dependencies:
            name = dep['name']
            required = dep['required_version']
            installed = dep['installed_version']
            status = dep['status']
            
            if status == 'installed':
                emoji = '✅'
                status_text = '[已安装]'
                log_message = f'{emoji} {status_text} 📦 {name} {required}'
            elif status == 'not_installed':
                emoji = '❌'
                status_text = '[未安装]'
                log_message = f'{emoji} {status_text} 📦 {name} {required}'
            else:
                emoji = '⚠️'
                status_text = '[包冲突]'
                log_message = f'{emoji} {status_text} 📦 {name} {installed} (要求: {required}, 已安装: {installed})'
            
            self._push_log('INFO', log_message, 'system')
        
        self._push_log('INFO', '', 'system')
        self._push_log('INFO', '📊 依赖分析报告', 'system')
        self._push_log('INFO', '━' * 70, 'system')
        self._push_log('INFO', f'📦 总依赖数: {stats["total"]}', 'system')
        self._push_log('INFO', f'✅ 已安装: {stats["installed"]}', 'system')
        self._push_log('INFO', f'❌ 未安装: {stats["not_installed"]}', 'system')
        self._push_log('INFO', f'⚠️ 版本冲突: {stats["conflicts"]}', 'system')
        self._push_log('INFO', '━' * 70, 'system')
        
        if stats['conflicts'] > 0:
            conflict_names = [dep['name'] for dep in dependencies if dep['status'] == 'version_mismatch']
            conflict_names_formatted = '，'.join([f'[{name}]' for name in conflict_names])
            self._push_log('INFO', '', 'system')
            self._push_log('INFO', f'💡 {conflict_names_formatted} 版本冲突，继续安装将会升级/降级到清单需求的版本', 'system')
        
        if stats['not_installed'] > 0:
            not_installed_deps = [dep for dep in dependencies if dep['status'] == 'not_installed']
            self._push_log('INFO', '', 'system')
            self._push_log('INFO', '📋 未安装依赖清单', 'system')
            self._push_log('INFO', '━' * 70, 'system')
            for dep in not_installed_deps:
                name = dep['name']
                required = dep['required_version']
                if required == '(任意版本)':
                    self._push_log('INFO', f'  • [[orange:{name}]]', 'system')
                else:
                    self._push_log('INFO', f'  • [[orange:{name}]] ([[orange:{required}]])', 'system')
            self._push_log('INFO', '━' * 70, 'system')
        
        self._push_log('INFO', '', 'system')
        self._push_operation_end(True, '分析完成')
    
    def _get_current_env(self) -> Optional[Dict]:
        """
        获取当前选中的环境配置
        
        Returns:
            环境配置字典（扁平化结构），如果未选中或获取失败则返回 None
            返回格式：
            {
                "id": "环境ID",
                "name": "环境名称",
                "path": "ComfyUI路径",
                "pythonPath": "Python路径",
                "pipPath": "pip路径",
                "comfyuiPath": "ComfyUI路径",
                "modelPathConfigs": [...],
                ...
            }
        """
        if not self.environment_manager:
            logger.error("[DependencyController] 环境管理器未初始化")
            return None
        
        try:
            # 获取当前环境 ID
            logger.debug(f"[DependencyController] 开始获取当前环境 ID，environment_manager 类型: {type(self.environment_manager)}")
            current_env_id = self.environment_manager.get_current_environment_id()
            logger.debug(f"[DependencyController] 获取到的当前环境 ID: {current_env_id}")
            
            if not current_env_id:
                logger.warning("[DependencyController] 未选中任何环境")
                return None
            
            # 获取环境配置
            logger.debug(f"[DependencyController] 开始获取环境配置: {current_env_id}")
            env_config = self.environment_manager.get_environment(current_env_id)
            logger.debug(f"[DependencyController] 获取到的环境配置: success={env_config.get('success') if env_config else None}")
            
            if not env_config or not env_config.get("success"):
                logger.error(f"[DependencyController] 获取环境配置失败: {current_env_id}, env_config={env_config}")
                return None
            
            environment = env_config.get("environment")
            if not environment:
                logger.error(f"[DependencyController] 环境数据为空: {current_env_id}")
                return None
            
            # 提取配置信息并扁平化
            # 注意：get_environment 返回的结构中 general 直接在根级别，不是在 config 下
            general = environment.get("general", {})
            
            # 构造扁平化的环境配置
            flattened_env = {
                "id": environment.get("id"),
                "name": environment.get("name"),
                "alias": environment.get("alias"),
                "path": environment.get("path"),
                "pythonPath": general.get("pythonPath"),
                "pipPath": general.get("pipPath"),
                "comfyuiPath": general.get("comfyuiPath"),
                "gitPath": general.get("gitPath"),
                "modelPathConfigs": environment.get("modelPathConfigs", []),
            }
            
            logger.debug(f"[DependencyController] 成功获取环境配置，环境名称: {flattened_env.get('name')}, Python路径: {flattened_env.get('pythonPath')}")
            return flattened_env
        except Exception as e:
            logger.error(f"[DependencyController] 获取当前环境失败: {str(e)}", exc_info=True)
            return None

    def _get_custom_nodes_paths(self, comfyui_path: Path, env: Dict) -> List[Path]:
        """
        收集所有 custom_nodes 路径（主路径 + 外置路径）
        
        从环境的 modelPathConfigs 中提取外置 custom_nodes 目录路径，
        与主 custom_nodes 目录合并。
        
        Args:
            comfyui_path: ComfyUI 安装路径
            env: 环境配置字典（扁平化结构）
            
        Returns:
            Path 列表，第一个为主路径，后续为外置路径
        """
        paths = [comfyui_path / "custom_nodes"]
        
        model_path_configs = env.get("modelPathConfigs", [])
        logger.info(f"[DependencyController] modelPathConfigs 数量: {len(model_path_configs)}")
        for config in model_path_configs:
            if not isinstance(config, dict):
                continue
            config_paths = config.get("paths", {})
            cn_rel = config_paths.get("custom_nodes") or config_paths.get("customNodes")
            logger.debug(f"[DependencyController] 检查配置: name={config.get('name')}, basePath={config.get('basePath')}, custom_nodes={cn_rel}")
            if cn_rel:
                base_path = config.get("basePath") or config.get("base_path", "")
                if base_path:
                    ext_path = Path(base_path) / cn_rel
                    if ext_path.exists() and ext_path not in paths:
                        paths.append(ext_path)
                        logger.info(f"[DependencyController] 发现外置插件目录: {ext_path}")
                    elif not ext_path.exists():
                        logger.warning(f"[DependencyController] 外置插件目录不存在: {ext_path}")
        
        logger.info(f"[DependencyController] 最终 custom_nodes 路径: {paths}")
        return paths
    
    @serialize_response
    def detect_cuda_version(self) -> Dict:
        """
        检测系统 CUDA 版本并返回常用版本列表
        
        优先使用 nvcc --version 获取实际安装的 CUDA 版本，
        如果 nvcc 不可用，则使用 nvidia-smi 获取驱动支持的版本
        
        Returns:
            dict: {
                "success": bool,
                "cuda_version": str | None,  # 当前系统安装的版本，例如 "12.1", "11.8", None 表示未安装
                "available_versions": list[str],  # 常用 CUDA 版本列表
                "error_message": str (可选)
            }
        """
        try:
            logger.info("[DependencyController] 开始检测 CUDA 版本 [VERSION: 2.0 - 优先使用 nvcc]")
            
            # 常用 CUDA 版本列表（从新到旧）
            available_versions = [
                "13.1",
                "13.0",
                "12.8",
                "12.6",
                "12.4",
                "12.1",
                "11.8",
                "CPU"
            ]
            
            # 优先尝试通过 nvcc 检测（实际安装的 CUDA 版本）
            try:
                result = subprocess.run(
                    ['nvcc', '--version'],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=get_creation_flags()
                )
                
                if result.returncode == 0:
                    import re
                    # 匹配 "release X.Y" 模式
                    match = re.search(r'release\s+(\d+\.\d+)', result.stdout, re.IGNORECASE)
                    if match:
                        cuda_version = match.group(1)
                        logger.info(f"[DependencyController] 通过 nvcc 检测到 CUDA 版本: {cuda_version}")
                        return {
                            "success": True,
                            "cuda_version": cuda_version,
                            "available_versions": available_versions
                        }
                    
                    # 备用模式: "VX.Y.Z"
                    match = re.search(r'V(\d+\.\d+)\.\d+', result.stdout)
                    if match:
                        cuda_version = match.group(1)
                        logger.info(f"[DependencyController] 通过 nvcc 检测到 CUDA 版本: {cuda_version}")
                        return {
                            "success": True,
                            "cuda_version": cuda_version,
                            "available_versions": available_versions
                        }
            except (FileNotFoundError, subprocess.TimeoutExpired):
                logger.debug("[DependencyController] nvcc 未找到，尝试使用 nvidia-smi")
            
            # 如果 nvcc 失败，尝试通过 nvidia-smi 检测（驱动支持的版本）
            try:
                result = subprocess.run(
                    ['nvidia-smi'],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=get_creation_flags()
                )
                
                if result.returncode == 0:
                    # 解析输出获取 CUDA 版本
                    import re
                    match = re.search(r'CUDA Version:\s*(\d+\.\d+)', result.stdout)
                    if match:
                        cuda_version = match.group(1)
                        logger.info(f"[DependencyController] 通过 nvidia-smi 检测到 CUDA 驱动版本: {cuda_version}")
                        return {
                            "success": True,
                            "cuda_version": cuda_version,
                            "available_versions": available_versions
                        }
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
            
            # 未检测到 CUDA
            logger.info("[DependencyController] 未检测到 CUDA")
            return {
                "success": True,
                "cuda_version": None,
                "available_versions": available_versions
            }
        
        except Exception as e:
            logger.error(f"[DependencyController] 检测 CUDA 版本失败: {str(e)}", exc_info=True)
            # 即使检测失败，也返回可用版本列表
            available_versions = [
                "13.1", "13.0", "12.8", "12.6", "12.4", "12.1", "11.8", "CPU"
            ]
            return {
                "success": False,
                "cuda_version": None,
                "available_versions": available_versions,
                "error_message": f"检测 CUDA 版本失败: {str(e)}"
            }

    @serialize_response
    def fetch_pytorch_versions(self, cuda_version: str) -> Dict:
        """
        获取 PyTorch 可用版本列表
        
        Args:
            cuda_version: CUDA 版本，例如 "12.1", "11.8", 或 "cpu"
            
        Returns:
            dict: {
                "success": bool,
                "versions": list[str],  # PyTorch 版本列表
                "error_message": str (可选)
            }
        """
        try:
            logger.info(f"[DependencyController] 查询 PyTorch 版本，CUDA: {cuda_version}")
            
            # 获取当前环境
            env = self._get_current_env()
            if not env:
                return {
                    "success": False,
                    "versions": [],
                    "error_message": "未选中环境或环境配置无效"
                }
            
            python_path = env.get("pythonPath")
            if not python_path:
                return {
                    "success": False,
                    "versions": [],
                    "error_message": "Python 路径未配置"
                }
            
            # 构造 index-url
            if cuda_version and cuda_version.lower() != "cpu":
                # 移除小数点，例如 "12.1" -> "cu121"
                cuda_ver = cuda_version.replace(".", "")
                index_url = f"https://download.pytorch.org/whl/cu{cuda_ver}"
            else:
                index_url = "https://download.pytorch.org/whl/cpu"
            
            builder = PythonCommandBuilder(python_path)
            cmd = builder.pip_index_versions('torch', index_url=index_url)
            
            logger.debug(f"[DependencyController] 执行命令: {' '.join(cmd)}")
            
            result = builder.run(cmd, timeout=30, use_proxy=True)
            
            if result.returncode != 0:
                logger.error(f"[DependencyController] pip index versions 失败: {result.stderr}")
                return {
                    "success": False,
                    "versions": [],
                    "error_message": f"查询 PyTorch 版本失败: {result.stderr}"
                }
            
            # 解析输出
            import re
            versions = []
            # pip index versions 的输出格式：
            # torch (2.1.0)
            # Available versions: 2.1.0, 2.0.1, 2.0.0, ...
            # 我们只需要解析 "Available versions:" 这一行
            for line in result.stdout.split('\n'):
                if 'Available versions:' in line:
                    # 提取版本号列表
                    version_str = line.split('Available versions:')[1].strip()
                    # 分割并清理版本号
                    version_list = [v.strip() for v in version_str.split(',')]
                    versions = [v for v in version_list if v and re.match(r'^\d+\.\d+\.\d+', v)]
                    break
            
            # 如果没有找到 "Available versions:" 行，尝试其他解析方式
            if not versions:
                logger.warning("[DependencyController] 未找到 'Available versions:' 行，尝试备用解析方式")
                seen = set()
                for line in result.stdout.split('\n'):
                    # 匹配版本号，例如 "2.1.0", "2.0.1+cu118"
                    match = re.search(r'(\d+\.\d+\.\d+(?:\+\w+)?)', line)
                    if match:
                        version = match.group(1)
                        if version not in seen:
                            seen.add(version)
                            versions.append(version)
            
            logger.info(f"[DependencyController] 找到 {len(versions)} 个 PyTorch 版本")
            logger.debug(f"[DependencyController] 版本列表: {versions[:10]}")  # 只记录前10个
            
            return {
                "success": True,
                "versions": versions
            }
        
        except Exception as e:
            logger.error(f"[DependencyController] 查询 PyTorch 版本失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "versions": [],
                "error_message": f"查询 PyTorch 版本失败: {str(e)}"
            }

    @serialize_response
    def install_pytorch(self, version: str, cuda_version: str, mirror_source: str = 'official') -> Dict:
        """
        安装 PyTorch
        
        Args:
            version: PyTorch 版本
            cuda_version: CUDA 版本
            mirror_source: 镜像源 ('auto', 'official', 'tuna', 'bfsu', 'aliyun', 'tencent')
            
        Returns:
            dict: {
                "success": bool,
                "log_file": str,  # 日志文件路径
                "error_message": str (可选)
            }
        """
        try:
            from datetime import datetime
            import sys
            
            logger.info(f"[DependencyController] 安装 PyTorch {version}, CUDA: {cuda_version}, 镜像源: {mirror_source}")
            
            # 获取当前环境
            env = self._get_current_env()
            if not env:
                return {
                    "success": False,
                    "error_message": "未选中环境或环境配置无效"
                }
            
            python_path = env.get("pythonPath")
            if not python_path:
                return {
                    "success": False,
                    "error_message": "Python 路径未配置"
                }
            
            from backend.src.utils.paths import get_project_root
            project_root = get_project_root()
            
            # 创建日志目录
            log_dir = project_root / "logs" / "dependencies"
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成日志文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = log_dir / f"pytorch_install_{timestamp}.log"
            
            # 构造 index-url（PyTorch 有自己的索引）
            resolved_mirror = mirror_source
            if mirror_source == 'auto':
                try:
                    from backend.src.utils.pypi_mirror import pypi_mirror_manager
                    if pypi_mirror_manager.is_enabled():
                        resolved_mirror = pypi_mirror_manager.get_current_source_name()
                        logger.dev(f"[PyPI Mirror] PyTorch 安装 Auto 模式 -> 使用镜像: {resolved_mirror}")
                    else:
                        resolved_mirror = 'tuna'
                        logger.dev(f"[PyPI Mirror] PyTorch 安装 Auto 模式 -> 镜像加速未启用，回退到 tuna")
                except Exception as e:
                    resolved_mirror = 'tuna'
                    logger.dev(f"[PyPI Mirror] PyTorch 安装 Auto 模式 -> 异常: {e}，回退到 tuna")

            if cuda_version and cuda_version.lower() != "cpu":
                cuda_ver = cuda_version.replace(".", "")
                if resolved_mirror == 'tuna':
                    index_url = f"https://mirrors.tuna.tsinghua.edu.cn/pytorch/whl/cu{cuda_ver}"
                    logger.dev(f"[PyPI Mirror] PyTorch CUDA 版本使用清华镜像: {index_url}")
                else:
                    index_url = f"https://download.pytorch.org/whl/cu{cuda_ver}"
                    if resolved_mirror != 'official':
                        logger.warning(f"[DependencyController] 镜像源 {resolved_mirror} 不支持 PyTorch，使用官方源")
                        logger.dev(f"[PyPI Mirror] PyTorch CUDA 版本镜像 {resolved_mirror} 不支持，使用官方源: {index_url}")
                    else:
                        logger.dev(f"[PyPI Mirror] PyTorch CUDA 版本使用官方源: {index_url}")
            else:
                if resolved_mirror == 'tuna':
                    index_url = "https://mirrors.tuna.tsinghua.edu.cn/pytorch/whl/cpu"
                    logger.dev(f"[PyPI Mirror] PyTorch CPU 版本使用清华镜像: {index_url}")
                else:
                    index_url = "https://download.pytorch.org/whl/cpu"
                    if resolved_mirror != 'official':
                        logger.warning(f"[DependencyController] 镜像源 {resolved_mirror} 不支持 PyTorch，使用官方源")
                        logger.dev(f"[PyPI Mirror] PyTorch CPU 版本镜像 {resolved_mirror} 不支持，使用官方源: {index_url}")
                    else:
                        logger.dev(f"[PyPI Mirror] PyTorch CPU 版本使用官方源: {index_url}")
            
            builder = PythonCommandBuilder(python_path)
            
            self._push_operation_start('安装', f'PyTorch {version}')
            
            packages_to_uninstall = ['torch', 'torchvision', 'torchaudio']
            
            with open(log_file, 'w', encoding='utf-8') as log_f:
                log_f.write(f"=== PyTorch 安装日志 ===\n")
                log_f.write(f"版本: {version}\n")
                log_f.write(f"CUDA: {cuda_version}\n")
                log_f.write(f"镜像源: {mirror_source}\n")
                log_f.write(f"Python: {builder.python_exe}\n")
                log_f.write(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_f.write(f"{'=' * 80}\n\n")
                
                log_f.write(f"--- 第一步：卸载旧版本 ---\n")
                log_f.flush()
                
                uninstall_failed = False
                for pkg in packages_to_uninstall:
                    uninstall_cmd = builder.pip_uninstall(pkg, yes=True)
                    log_f.write(f"卸载 {pkg}: {' '.join(uninstall_cmd)}\n")
                    log_f.flush()
                    logger.info(f"[DependencyController] 卸载 {pkg}: {' '.join(uninstall_cmd)}")
                    
                    try:
                        with builder.safe_popen(uninstall_cmd, use_proxy=True) as uninstall_process:
                            for line in uninstall_process.stdout:
                                log_f.write(line)
                                log_f.flush()
                                if line.strip():
                                    self._push_log('INFO', line.strip(), 'pip')
                            uninstall_return_code = uninstall_process.wait()
                            if uninstall_return_code != 0:
                                log_f.write(f"卸载 {pkg} 返回码: {uninstall_return_code} (可能未安装，忽略)\n")
                    except Exception as e:
                        log_f.write(f"卸载 {pkg} 异常: {str(e)} (忽略)\n")
                        logger.warning(f"[DependencyController] 卸载 {pkg} 时出现异常: {str(e)}")
                
                log_f.write(f"\n--- 第二步：安装新版本 ---\n")
                log_f.flush()
                
                mapping = self._fetch_pytorch_version_mapping()
                compatible_versions = self._get_compatible_versions(version) if mapping else None
                
                if compatible_versions:
                    tv_version = compatible_versions.get('torchvision')
                    ta_version = compatible_versions.get('torchaudio')
                    match_type = compatible_versions.get('match_type', 'unknown')
                    
                    match_type_labels = {
                        'exact': '精确匹配',
                        'derived': '同级推导',
                        'formula': '公式推导'
                    }
                    match_label = match_type_labels.get(match_type, match_type)
                    
                    if tv_version and ta_version:
                        log_f.write(f"版本映射（{match_label}）: torch={version}, torchvision={tv_version}, torchaudio={ta_version}\n")
                        logger.info(f"[DependencyController] 版本映射（{match_label}）: torch={version}, torchvision={tv_version}, torchaudio={ta_version}")
                        
                        cmd = builder.pip_install(
                            f'torch=={version}',
                            extra_args=[
                                f'torchvision=={tv_version}',
                                f'torchaudio=={ta_version}',
                                '--index-url', index_url
                            ]
                        )
                    else:
                        logger.warning(f"[DependencyController] 版本映射中缺少 torchvision 或 torchaudio，使用默认安装")
                        cmd = builder.pip_install(f'torch=={version}', extra_args=['torchvision', 'torchaudio', '--index-url', index_url])
                else:
                    logger.warning(f"[DependencyController] 未找到 torch {version} 的版本映射，使用默认安装")
                    cmd = builder.pip_install(f'torch=={version}', extra_args=['torchvision', 'torchaudio', '--index-url', index_url])
                
                log_f.write(f"安装命令: {' '.join(cmd)}\n\n")
                log_f.flush()
                logger.info(f"[DependencyController] 执行安装命令: {' '.join(cmd)}")
                logger.info(f"[DependencyController] 日志文件: {log_file}")
                
                with builder.safe_popen(cmd, use_proxy=True) as process:
                    for line in process.stdout:
                        log_f.write(line)
                        log_f.flush()
                        
                        if line.strip():
                            self._push_log('INFO', line.strip(), 'pip')
                    
                    return_code = process.wait()
                
                log_f.write(f"\n{'=' * 80}\n")
                log_f.write(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_f.write(f"返回码: {return_code}\n")
                log_f.write(f"状态: {'成功' if return_code == 0 else '失败'}\n")
            
            if return_code == 0:
                logger.info(f"[DependencyController] PyTorch 安装成功")
                self._push_operation_end(True, f'PyTorch {version} 安装成功')
                self._push_log('INFO', f'日志已保存到: {log_file}', 'system')
                return {
                    "success": True,
                    "log_file": str(log_file)
                }
            else:
                logger.error(f"[DependencyController] PyTorch 安装失败，返回码: {return_code}")
                self._push_operation_end(False, f'PyTorch {version} 安装失败')
                self._push_log('INFO', f'日志已保存到: {log_file}', 'system')
                return {
                    "success": False,
                    "log_file": str(log_file),
                    "error_message": f"安装失败，返回码: {return_code}"
                }
        
        except Exception as e:
            logger.error(f"[DependencyController] 安装 PyTorch 失败: {str(e)}", exc_info=True)
            self._push_operation_end(False, f'PyTorch 安装失败: {str(e)}')
            return {
                "success": False,
                "error_message": f"安装 PyTorch 失败: {str(e)}"
            }

    @serialize_response
    def search_package(self, package_name: str, mirror_source: str = 'official') -> Dict:
        """
        搜索 PyPI 包信息
        
        Args:
            package_name: 包名
            mirror_source: 镜像源 ('auto', 'official', 'tuna', 'bfsu', 'aliyun', 'tencent')
            
        Returns:
            dict: {
                "success": bool,
                "package_info": dict,  # 包信息
                "error_message": str (可选)
            }
        """
        try:
            import requests
            
            logger.info(f"[DependencyController] 搜索包: {package_name}, 镜像源: {mirror_source}")
            
            url = f"https://pypi.org/pypi/{package_name}/json"
            
            try:
                response = requests.get(url, timeout=10)
                
                if response.status_code != 200:
                    return {
                        "success": False,
                        "package_info": {},
                        "error_message": f"包 '{package_name}' 不存在或网络错误"
                    }
                
                data = response.json()
                info = data.get("info", {})
                
                package_info = {
                    "name": info.get("name", package_name),
                    "latest_version": info.get("version", ""),
                    "description": info.get("summary", ""),
                    "author": info.get("author", ""),
                    "homepage": info.get("home_page", "")
                }
                
                logger.info(f"[DependencyController] 找到包: {package_info['name']} v{package_info['latest_version']}")
                
                return {
                    "success": True,
                    "package_info": package_info
                }
            
            except requests.exceptions.Timeout:
                return {
                    "success": False,
                    "package_info": {},
                    "error_message": f"网络连接超时，请检查网络设置或尝试切换镜像源"
                }
            except requests.exceptions.ConnectionError:
                return {
                    "success": False,
                    "package_info": {},
                    "error_message": f"网络连接失败，请检查网络设置或尝试切换镜像源"
                }
            except requests.exceptions.HTTPError as e:
                return {
                    "success": False,
                    "package_info": {},
                    "error_message": f"网络请求失败(HTTP错误)，请检查网络设置或尝试切换镜像源"
                }
            except requests.exceptions.RequestException as e:
                return {
                    "success": False,
                    "package_info": {},
                    "error_message": f"网络请求失败，请检查网络设置或尝试切换镜像源"
                }
        
        except Exception as e:
            logger.error(f"[DependencyController] 搜索包失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "package_info": {},
                "error_message": f"搜索包失败: {str(e)}"
            }
    
    @serialize_response
    def get_installed_version(self, package_name: str) -> Dict:
        """
        获取已安装包的版本
        
        Args:
            package_name: 包名
            
        Returns:
            dict: {
                "success": bool,
                "version": str | None,  # 已安装的版本，未安装则为 None
                "installed": bool,  # 是否已安装
                "error_message": str (可选)
            }
        """
        try:
            logger.info(f"[DependencyController] 获取已安装包版本: {package_name}")
            
            # 获取当前环境
            env = self._get_current_env()
            if not env:
                return {
                    "success": False,
                    "version": None,
                    "installed": False,
                    "error_message": "未选中环境或环境配置无效"
                }
            
            python_path = env.get("pythonPath")
            if not python_path:
                return {
                    "success": False,
                    "version": None,
                    "installed": False,
                    "error_message": "Python 路径未配置"
                }
            
            builder = PythonCommandBuilder(python_path)
            cmd = builder.pip_show(package_name)
            result = builder.run(cmd, timeout=30, use_proxy=True)
            
            if result.returncode != 0:
                logger.info(f"[DependencyController] 包 '{package_name}' 未安装")
                logger.debug(f"[DependencyController] 返回码: {result.returncode}")
                logger.debug(f"[DependencyController] stderr: {result.stderr}")
                return {
                    "success": True,
                    "version": None,
                    "installed": False
                }
            
            output = result.stdout
            version_line = None
            for line in output.split('\n'):
                if line.startswith('Version:'):
                    version_line = line
                    break
            
            if version_line:
                version = version_line.split(':', 1)[1].strip()
                logger.info(f"[DependencyController] 包 '{package_name}' 已安装，版本: {version}")
                return {
                    "success": True,
                    "version": version,
                    "installed": True
                }
            else:
                logger.warning(f"[DependencyController] 无法解析包 '{package_name}' 的版本信息")
                return {
                    "success": True,
                    "version": None,
                    "installed": True
                }
        
        except Exception as e:
            logger.error(f"[DependencyController] 获取已安装包版本失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "version": None,
                "installed": False,
                "error_message": f"获取包版本失败: {str(e)}"
            }
    
    @serialize_response
    def fetch_package_versions(self, package_name: str, mirror_source: str = 'official') -> Dict:
        """
        获取包的所有版本
        
        Args:
            package_name: 包名
            mirror_source: 镜像源 ('auto', 'official', 'tuna', 'bfsu', 'aliyun', 'tencent')
            
        Returns:
            dict: {
                "success": bool,
                "versions": list[str],  # 版本列表（降序）
                "error_message": str (可选)
            }
        """
        try:
            import requests
            from packaging import version
            
            logger.info(f"[DependencyController] 获取包版本: {package_name}, 镜像源: {mirror_source}")
            
            url = f"https://pypi.org/pypi/{package_name}/json"
            
            try:
                response = requests.get(url, timeout=10)
                
                if response.status_code != 200:
                    return {
                        "success": False,
                        "versions": [],
                        "error_message": f"包 '{package_name}' 不存在或网络错误"
                    }
                
                data = response.json()
                releases = data.get("releases", {})
                
                # 提取所有版本号并排序（降序）
                versions = list(releases.keys())
                try:
                    versions.sort(key=lambda v: version.parse(v), reverse=True)
                except (ValueError, TypeError):
                    # 如果版本解析失败，使用字符串排序
                    versions.sort(reverse=True)
                
                logger.info(f"[DependencyController] 找到 {len(versions)} 个版本")
                
                return {
                    "success": True,
                    "versions": versions
                }
            
            except requests.exceptions.Timeout:
                return {
                    "success": False,
                    "versions": [],
                    "error_message": f"网络连接超时，请检查网络设置或尝试切换镜像源"
                }
            except requests.exceptions.ConnectionError:
                return {
                    "success": False,
                    "versions": [],
                    "error_message": f"网络连接失败，请检查网络设置或尝试切换镜像源"
                }
            except requests.exceptions.HTTPError as e:
                return {
                    "success": False,
                    "versions": [],
                    "error_message": f"网络请求失败(HTTP错误)，请检查网络设置或尝试切换镜像源"
                }
            except requests.exceptions.RequestException as e:
                return {
                    "success": False,
                    "versions": [],
                    "error_message": f"网络请求失败，请检查网络设置或尝试切换镜像源"
                }
        
        except Exception as e:
            logger.error(f"[DependencyController] 获取包版本失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "versions": [],
                "error_message": f"获取包版本失败: {str(e)}"
            }

    @serialize_response
    def install_package(self, package_name: str, version: str, mode: str, mirror_source: str = 'official') -> Dict:
        """
        安装包
        
        Args:
            package_name: 包名
            version: 版本
            mode: 安装模式 ('dry-run' 或 'install')
            mirror_source: 镜像源 ('auto', 'official', 'tuna', 'bfsu', 'aliyun', 'tencent')
            
        Returns:
            dict: {
                "success": bool,
                "log_file": str,  # 日志文件路径
                "error_message": str (可选)
            }
        """
        try:
            from datetime import datetime
            import sys
            
            logger.info(f"[DependencyController] 安装包: {package_name}=={version}, 模式: {mode}, 镜像源: {mirror_source}")
            
            if not _validate_package_name(package_name):
                return {
                    "success": False,
                    "error_message": f"无效的包名格式: {package_name}"
                }
            
            env = self._get_current_env()
            if not env:
                return {
                    "success": False,
                    "error_message": "未选中环境或环境配置无效"
                }
            
            python_path = env.get("pythonPath")
            if not python_path:
                return {
                    "success": False,
                    "error_message": "Python 路径未配置"
                }
            
            from backend.src.utils.paths import get_project_root
            project_root = get_project_root()
            
            log_dir = project_root / "logs" / "dependencies"
            log_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = log_dir / f"install_{package_name}_{timestamp}.log"
            
            mirror_config = _get_pypi_mirror_config(mirror_source)
            pip_index = mirror_config['pip_index']
            
            builder = PythonCommandBuilder(python_path)
            
            extra_args = []
            if mirror_source != 'official':
                extra_args.extend(['-i', pip_index])
                logger.dev(f"[PyPI Mirror] pip install 使用镜像: {pip_index}")
            else:
                logger.dev(f"[PyPI Mirror] pip install 使用官方源")
            if mode == 'dry-run':
                extra_args.append('--dry-run')
            
            cmd = builder.pip_install(package_name, version=f'=={version}', extra_args=extra_args)
            
            logger.info(f"[DependencyController] 执行命令: {' '.join(cmd)}")
            logger.info(f"[DependencyController] 日志文件: {log_file}")
            
            self._push_operation_start('安装', f'{package_name}=={version}')
            
            return_code = -1
            output_lines = []
            
            with open(log_file, 'w', encoding='utf-8') as log_f:
                log_f.write(f"=== 包安装日志 ===\n")
                log_f.write(f"包名: {package_name}\n")
                log_f.write(f"版本: {version}\n")
                log_f.write(f"模式: {mode}\n")
                log_f.write(f"镜像源: {mirror_source}\n")
                log_f.write(f"Python: {builder.python_exe}\n")
                log_f.write(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_f.write(f"执行命令: {' '.join(cmd)}\n")
                log_f.write(f"{'=' * 80}\n\n")
                log_f.flush()
                
                with builder.safe_popen(cmd, use_proxy=True) as process:
                    for line in process.stdout:
                        log_f.write(line)
                        log_f.flush()
                        output_lines.append(line.strip())
                        if line.strip():
                            self._push_log('INFO', line.strip(), 'pip')
                    
                    return_code = process.wait()
                
                log_f.write(f"\n{'=' * 80}\n")
                log_f.write(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_f.write(f"返回码: {return_code}\n")
                log_f.write(f"状态: {'成功' if return_code == 0 else '失败'}\n")
            
            if return_code == 0:
                logger.info(f"[DependencyController] 包安装成功: {package_name}")
                self._push_operation_end(True, f'{package_name}=={version} 安装成功')
                self._push_log('INFO', f'日志已保存到: {log_file}', 'system')
                return {
                    "success": True,
                    "log_file": str(log_file)
                }
            else:
                # 从输出中提取错误信息
                error_message = self._extract_error_message(output_lines, package_name)
                
                logger.error(f"[DependencyController] 包安装失败: {package_name}, 错误: {error_message}")
                self._push_operation_end(False, f'{package_name}=={version} 安装失败')
                self._push_log('INFO', f'日志已保存到: {log_file}', 'system')
                return {
                    "success": False,
                    "log_file": str(log_file),
                    "error_message": error_message
                }
        
        except Exception as e:
            logger.error(f"[DependencyController] 安装包失败: {str(e)}", exc_info=True)
            self._push_operation_end(False, f'{package_name} 安装失败: {str(e)}')
            return {
                "success": False,
                "error_message": f"安装包失败: {str(e)}"
            }

    @serialize_response
    def uninstall_package(self, package_name: str) -> Dict:
        """
        卸载包
        
        Args:
            package_name: 包名
            
        Returns:
            dict: {
                "success": bool,
                "log_file": str,  # 日志文件路径
                "error_message": str (可选)
            }
        """
        try:
            from datetime import datetime
            import sys
            
            logger.info(f"[DependencyController] 卸载包: {package_name}")
            
            if not _validate_package_name(package_name):
                return {
                    "success": False,
                    "error_message": f"无效的包名格式: {package_name}"
                }
            
            env = self._get_current_env()
            if not env:
                return {
                    "success": False,
                    "error_message": "未选中环境或环境配置无效"
                }
            
            python_path = env.get("pythonPath")
            if not python_path:
                return {
                    "success": False,
                    "error_message": "Python 路径未配置"
                }
            
            from backend.src.utils.paths import get_project_root
            project_root = get_project_root()
            
            log_dir = project_root / "logs" / "dependencies"
            log_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = log_dir / f"uninstall_{package_name}_{timestamp}.log"
            
            builder = PythonCommandBuilder(python_path)
            cmd = builder.pip_uninstall(package_name)
            
            logger.info(f"[DependencyController] 执行命令: {' '.join(cmd)}")
            logger.info(f"[DependencyController] 日志文件: {log_file}")
            
            self._push_operation_start('卸载', package_name)
            
            return_code = -1
            
            with open(log_file, 'w', encoding='utf-8') as log_f:
                log_f.write(f"=== 包卸载日志 ===\n")
                log_f.write(f"包名: {package_name}\n")
                log_f.write(f"Python: {builder.python_exe}\n")
                log_f.write(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_f.write(f"执行命令: {' '.join(cmd)}\n")
                log_f.write(f"{'=' * 80}\n\n")
                log_f.flush()
                
                with builder.safe_popen(cmd, use_proxy=True) as process:
                    for line in process.stdout:
                        log_f.write(line)
                        log_f.flush()
                        if line.strip():
                            self._push_log('INFO', line.strip(), 'pip')
                    
                    return_code = process.wait()
                
                log_f.write(f"\n{'=' * 80}\n")
                log_f.write(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_f.write(f"返回码: {return_code}\n")
                log_f.write(f"状态: {'成功' if return_code == 0 else '失败'}\n")
            
            if return_code == 0:
                logger.info(f"[DependencyController] 包卸载成功: {package_name}")
                self._push_operation_end(True, f'{package_name} 卸载成功')
                self._push_log('INFO', f'日志已保存到: {log_file}', 'system')
                return {
                    "success": True,
                    "log_file": str(log_file)
                }
            else:
                logger.error(f"[DependencyController] 包卸载失败: {package_name}, 返回码: {return_code}")
                self._push_operation_end(False, f'{package_name} 卸载失败')
                self._push_log('INFO', f'日志已保存到: {log_file}', 'system')
                return {
                    "success": False,
                    "log_file": str(log_file),
                    "error_message": f"卸载失败，返回码: {return_code}"
                }
        
        except Exception as e:
            logger.error(f"[DependencyController] 卸载包失败: {str(e)}", exc_info=True)
            self._push_operation_end(False, f'{package_name} 卸载失败: {str(e)}')
            return {
                "success": False,
                "error_message": f"卸载包失败: {str(e)}"
            }

    @serialize_response
    def install_from_requirements(self, file_path: str, mode: str, mirror_source: str = 'official') -> Dict:
        """
        从 requirements.txt 安装依赖
        
        Args:
            file_path: requirements.txt 文件路径
            mode: 安装模式 ('dry-run' 或 'install')
            mirror_source: 镜像源 ('auto', 'official', 'tuna', 'bfsu', 'aliyun', 'tencent')
            
        Returns:
            dict: {
                "success": bool,
                "log_file": str,  # 日志文件路径
                "error_message": str (可选)
            }
        """
        try:
            from datetime import datetime
            import sys
            
            logger.info(f"[DependencyController] 从 requirements.txt 安装: {file_path}, 模式: {mode}, 镜像源: {mirror_source}")
            
            is_valid, error_msg = _validate_file_path(file_path)
            if not is_valid:
                return {
                    "success": False,
                    "error_message": error_msg
                }
            
            req_file = Path(file_path)
            
            # 获取当前环境
            env = self._get_current_env()
            if not env:
                return {
                    "success": False,
                    "error_message": "未选中环境或环境配置无效"
                }
            
            python_path = env.get("pythonPath")
            if not python_path:
                return {
                    "success": False,
                    "error_message": "Python 路径未配置"
                }
            
            from backend.src.utils.paths import get_project_root
            project_root = get_project_root()
            
            # 创建日志目录
            log_dir = project_root / "logs" / "dependencies"
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成日志文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = log_dir / f"requirements_{timestamp}.log"
            
            # 获取镜像源配置
            mirror_config = _get_pypi_mirror_config(mirror_source)
            pip_index = mirror_config['pip_index']
            
            builder = PythonCommandBuilder(python_path)
            
            extra_args = []
            if mirror_source != 'official':
                extra_args.extend(['-i', pip_index])
                logger.dev(f"[PyPI Mirror] pip install -r 使用镜像: {pip_index}")
            else:
                logger.dev(f"[PyPI Mirror] pip install -r 使用官方源")
            if mode == 'dry-run':
                extra_args.append('--dry-run')
            
            cmd = builder.pip_install_requirements(req_file, extra_args=extra_args)
            
            logger.info(f"[DependencyController] 执行命令: {' '.join(cmd)}")
            logger.info(f"[DependencyController] 日志文件: {log_file}")
            
            mode_text = '模拟安装' if mode == 'dry-run' else '安装'
            self._push_operation_start(f'{mode_text}依赖', str(req_file.name))
            
            with open(log_file, 'w', encoding='utf-8') as log_f:
                log_f.write(f"=== Requirements 安装日志 ===\n")
                log_f.write(f"文件: {file_path}\n")
                log_f.write(f"模式: {mode}\n")
                log_f.write(f"镜像源: {mirror_source}\n")
                log_f.write(f"Python: {builder.python_exe}\n")
                log_f.write(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_f.write(f"执行命令: {' '.join(cmd)}\n")
                log_f.write(f"{'=' * 80}\n\n")
                log_f.flush()
                
                with builder.safe_popen(cmd, use_proxy=True) as process:
                    for line in process.stdout:
                        log_f.write(line)
                        log_f.flush()
                        line_stripped = line.strip()
                        if line_stripped:
                            self._push_log('INFO', line_stripped, 'pip')
                    
                    return_code = process.wait()
                
                log_f.write(f"\n{'=' * 80}\n")
                log_f.write(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_f.write(f"返回码: {return_code}\n")
                log_f.write(f"状态: {'成功' if return_code == 0 else '失败'}\n")
            
            if return_code == 0:
                logger.info("[DependencyController] Requirements 安装成功")
                self._push_operation_end(True, f'{mode_text}成功')
                self._push_log('INFO', f'日志已保存到: {log_file}', 'system')
                return {
                    "success": True,
                    "log_file": str(log_file)
                }
            else:
                logger.error(f"[DependencyController] Requirements 安装失败，返回码: {return_code}")
                self._push_operation_end(False, f'{mode_text}失败')
                self._push_log('INFO', f'日志已保存到: {log_file}', 'system')
                return {
                    "success": False,
                    "log_file": str(log_file),
                    "error_message": f"安装失败，返回码: {return_code}"
                }
        
        except Exception as e:
            logger.error(f"[DependencyController] Requirements 安装失败: {str(e)}", exc_info=True)
            self._push_operation_end(False, f'{mode_text}失败: {str(e)}')
            return {
                "success": False,
                "error_message": f"安装失败: {str(e)}"
            }
    
    @serialize_response
    def open_terminal(self) -> Dict:
        """
        打开终端并设置环境变量
        
        Returns:
            dict: {
                "success": bool,
                "error_message": str (可选)
            }
        """
        try:
            logger.info("[DependencyController] 打开终端")
            
            env = self._get_current_env()
            if not env:
                return {
                    "success": False,
                    "error_message": "未选中环境或环境配置无效"
                }
            
            python_path = env.get("pythonPath")
            comfyui_path = env.get("comfyuiPath")
            env_name = env.get("name", "ComfyUI")
            
            if not python_path:
                return {
                    "success": False,
                    "error_message": "Python 路径未配置"
                }
            
            python_exe = Path(python_path)
            if python_exe.is_file():
                python_dir = python_exe.parent
            else:
                python_dir = python_exe
            
            work_dir = comfyui_path if comfyui_path else str(python_dir)
            
            safe_env_name = _escape_for_powershell(_sanitize_for_powershell(env_name))
            safe_python_dir = _escape_for_powershell(_sanitize_path_for_display(str(python_dir)))
            safe_work_dir = _escape_for_powershell(_sanitize_path_for_display(str(work_dir)))
            
            ps_cmd = f'$env:PATH = "{safe_python_dir};$env:PATH"; '
            ps_cmd += f'$host.UI.RawUI.WindowTitle = "{safe_env_name} - Terminal"; '
            ps_cmd += f'cd "{safe_work_dir}"; '
            ps_cmd += f'Write-Host "环境已加载: {safe_env_name}" -ForegroundColor Green; '
            ps_cmd += f'Write-Host "Python: {safe_python_dir}" -ForegroundColor Cyan'
            
            popen_powershell(ps_cmd, new_console=True)
            
            logger.info("[DependencyController] 终端已打开")
            return {
                "success": True
            }
        
        except Exception as e:
            logger.error(f"[DependencyController] 打开终端失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error_message": f"打开终端失败: {str(e)}"
            }

    @serialize_response
    def detect_environment(self) -> Dict:
        """
        检测环境信息
        
        Returns:
            dict: {
                "success": bool,
                "env_info": dict,  # 环境信息
                "error_message": str (可选)
            }
        """
        try:
            logger.info("[DependencyController] 开始检测环境信息")
            
            # 获取当前环境
            env = self._get_current_env()
            if not env:
                return {
                    "success": False,
                    "env_info": {},
                    "error_message": "未选中环境或环境配置无效"
                }
            
            python_path = env.get("pythonPath")
            if not python_path:
                return {
                    "success": False,
                    "env_info": {},
                    "error_message": "Python 路径未配置"
                }
            
            env_info = {
                "windows_version": self._get_windows_version(),
                "gpu": self._get_gpu_info(),
                "cpu": self._get_cpu_info(),
                "python": self._get_python_info(python_path),
                "cuda": self._get_cuda_info(),
                "dependencies": self._get_dependency_versions(python_path)
            }
            
            logger.info("[DependencyController] 环境信息检测完成")
            return {
                "success": True,
                "env_info": env_info
            }
        
        except Exception as e:
            logger.error(f"[DependencyController] 检测环境信息失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "env_info": {},
                "error_message": f"检测环境信息失败: {str(e)}"
            }
    
    def _get_windows_version(self) -> str:
        """获取 Windows 版本"""
        try:
            return platform.platform()
        except (OSError, RuntimeError):
            return "未知"
    
    def _get_gpu_info(self) -> Dict:
        """获取 GPU 信息"""
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=get_creation_flags()
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if lines:
                    parts = lines[0].split(',')
                    return {
                        "model": parts[0].strip() if len(parts) > 0 else "未知",
                        "vram": parts[1].strip() if len(parts) > 1 else "未知"
                    }
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError, subprocess.SubprocessError):
            pass
        
        return {"model": "未检测到", "vram": "N/A"}
    
    def _get_cpu_info(self) -> Dict:
        """
        获取 CPU 信息
        
        使用 WMI 查询获取准确的 CPU 型号，避免 platform.processor() 的不准确问题
        """
        try:
            import psutil
            
            # 尝试使用 WMI 获取准确的 CPU 型号
            cpu_model = None
            try:
                result = subprocess_utils.run_powershell_command(
                    '(Get-CimInstance -ClassName Win32_Processor).Name',
                    timeout=5
                )
                
                if result.returncode == 0:
                    cpu_model = result.stdout.strip()
                    logger.debug(f"[DependencyController] 通过 WMI 获取 CPU 型号: {cpu_model}")
            except Exception as e:
                logger.debug(f"[DependencyController] WMI 查询失败: {e}")
            
            # 如果 WMI 查询失败，使用 platform.processor() 作为备用
            if not cpu_model:
                cpu_model = platform.processor()
                logger.debug(f"[DependencyController] 通过 platform.processor() 获取 CPU 型号: {cpu_model}")
            
            ram_total = psutil.virtual_memory().total / (1024 ** 3)  # GB
            
            return {
                "model": cpu_model if cpu_model else "未知",
                "ram": f"{ram_total:.1f} GB"
            }
        except Exception as e:
            logger.error(f"[DependencyController] 获取 CPU 信息失败: {e}")
            return {"model": "未知", "ram": "未知"}
    
    def _get_python_info(self, python_path: str) -> Dict:
        """获取 Python 信息"""
        try:
            builder = PythonCommandBuilder(python_path)
            
            python_version = "未知"
            try:
                cmd = [str(builder.python_exe), '--version']
                result = builder.run(cmd, timeout=5, use_proxy=False)
                if result.returncode == 0:
                    python_version = result.stdout.strip().replace('Python ', '')
            except Exception:
                pass
            
            pip_version = "未知"
            try:
                cmd = [str(builder.python_exe), '-m', 'pip', '--version']
                result = builder.run(cmd, timeout=5, use_proxy=False)
                if result.returncode == 0:
                    pip_output = result.stdout.strip()
                    if pip_output.startswith('pip '):
                        pip_version = pip_output.split()[1]
            except Exception:
                pass

            return {
                "version": python_version,
                "path": str(builder.python_exe),
                "pip_version": pip_version
            }
        except Exception:
            pass

        return {"version": "未知", "path": str(python_path), "pip_version": "未知"}

    
    def _get_cuda_info(self) -> Dict:
        """
        获取 CUDA 信息
        
        优先使用 nvcc --version 获取实际安装的 CUDA 版本，
        如果 nvcc 不可用，则使用 nvidia-smi 获取驱动支持的版本
        """
        try:
            # 优先尝试 nvcc --version（实际安装的 CUDA 版本）
            result = subprocess.run(
                ['nvcc', '--version'],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=get_creation_flags()
            )
            
            if result.returncode == 0:
                import re
                # 匹配 "release X.Y" 模式
                match = re.search(r'release\s+(\d+\.\d+)', result.stdout, re.IGNORECASE)
                if match:
                    cuda_version = match.group(1)
                    logger.debug(f"[DependencyController] 通过 nvcc 检测到 CUDA 版本: {cuda_version}")
                    return {"version": cuda_version}
                
                # 备用模式: "VX.Y.Z"
                match = re.search(r'V(\d+\.\d+)\.\d+', result.stdout)
                if match:
                    cuda_version = match.group(1)
                    logger.debug(f"[DependencyController] 通过 nvcc 检测到 CUDA 版本: {cuda_version}")
                    return {"version": cuda_version}
        except FileNotFoundError:
            logger.debug("[DependencyController] nvcc 未找到，尝试使用 nvidia-smi")
        except Exception as e:
            logger.debug(f"[DependencyController] nvcc 检测失败: {e}")
        
        # 如果 nvcc 不可用，尝试 nvidia-smi（驱动支持的版本）
        try:
            result = subprocess.run(
                ['nvidia-smi'],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=get_creation_flags()
            )
            
            if result.returncode == 0:
                import re
                match = re.search(r'CUDA Version:\s*(\d+\.\d+)', result.stdout)
                if match:
                    cuda_version = match.group(1)
                    logger.debug(f"[DependencyController] 通过 nvidia-smi 检测到 CUDA 驱动版本: {cuda_version}")
                    return {"version": cuda_version}
        except Exception as e:
            logger.debug(f"[DependencyController] nvidia-smi 检测失败: {e}")
        
        return {"version": "未安装"}
    
    def _get_dependency_versions(self, python_path: str) -> Dict:
        """获取核心依赖版本"""
        try:
            builder = PythonCommandBuilder(python_path)
            cmd = builder.pip_list()
            result = builder.run(cmd, timeout=30, use_proxy=False)
            
            if result.returncode == 0:
                packages = json.loads(result.stdout)
                
                dependencies = {}
                key_packages = {
                    'torch': 'pytorch',
                    'torchvision': 'torchvision',
                    'transformers': 'transformer',
                    'numpy': 'numpy',
                    'pillow': 'pillow',
                    'flash-attn': 'flashAttn',
                    'flash_attn': 'flashAttn',
                    'sageattention': 'sageAttention',
                    'xformers': 'xformers'
                }
                
                for pkg in packages:
                    pkg_name = pkg['name'].lower()
                    if pkg_name in key_packages:
                        frontend_name = key_packages[pkg_name]
                        dependencies[frontend_name] = pkg['version']
                
                for pip_name, frontend_name in key_packages.items():
                    if frontend_name not in dependencies:
                        dependencies[frontend_name] = "N/A"
                
                logger.debug(f"[DependencyController] 依赖版本: {dependencies}")
                return dependencies
        except Exception as e:
            logger.error(f"[DependencyController] 获取依赖版本失败: {str(e)}")
        
        return {
            "pytorch": "N/A",
            "torchvision": "N/A",
            "transformer": "N/A",
            "numpy": "N/A",
            "pillow": "N/A",
            "flashAttn": "N/A",
            "sageAttention": "N/A",
            "xformers": "N/A"
        }
    
    def analyze_logs_with_ai(self, logs: str, api_config_id: str = None) -> Dict:
        """
        使用 AI 分析日志
        
        Args:
            logs: 日志内容
            api_config_id: API 配置 ID（可选，如果为 None 则使用默认配置）
            
        Returns:
            dict: {
                "success": bool,
                "topic_id": str,  # 创建的话题 ID
                "error_message": str (可选)
            }
            
        注意：此方法会创建一个新话题并发送消息，流式响应通过 window.evaluate_js 发送到前端
        """
        return self.ai_analyzer.analyze_logs(logs, api_config_id)
    
    @serialize_response
    def select_file(self, file_types: str = 'all') -> Dict:
        """
        打开文件选择对话框
        
        Args:
            file_types: 文件类型过滤 ('requirements', 'whl', 'all')
            
        Returns:
            dict: {
                "success": bool,
                "file_path": str,  # 选中的文件路径
                "file_type": str,  # 文件类型 ('requirements' 或 'whl')
                "error_message": str (可选)
            }
        """
        try:
            import webview
            
            logger.info(f"[DependencyController] 打开文件选择对话框，类型: {file_types}")
            
            if not self._window:
                return {
                    "success": False,
                    "error_message": "窗口未初始化"
                }
            
            # 根据类型设置文件过滤（Requirements Files 放在第一位作为默认）
            file_filter = []
            if file_types == 'requirements' or file_types == 'all':
                file_filter.append('Requirements Files (*.txt)')
            if file_types == 'whl' or file_types == 'all':
                file_filter.append('Wheel Files (*.whl)')
            if file_types == 'all':
                file_filter.append('All Files (*.*)')
            
            # 打开文件选择对话框
            default_directory = os.path.expanduser('~')
            result = self._window.create_file_dialog(
                dialog_type=webview.FileDialog.OPEN,
                directory=default_directory,
                allow_multiple=False,
                file_types=tuple(file_filter) if file_filter else ()
            )
            
            if not result or len(result) == 0:
                logger.info("[DependencyController] 用户取消了文件选择")
                return {
                    "success": False,
                    "error_message": "用户取消了文件选择"
                }
            
            file_path = result[0]
            logger.info(f"[DependencyController] 用户选择了文件: {file_path}")
            
            # 判断文件类型
            file_path_obj = Path(file_path)
            if file_path_obj.suffix.lower() == '.whl':
                file_type = 'whl'
            else:
                # 默认当作 requirements 文件处理
                file_type = 'requirements'
            
            return {
                "success": True,
                "file_path": str(file_path),
                "file_type": file_type
            }
        
        except Exception as e:
            logger.error(f"[DependencyController] 文件选择失败: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error_message": f"文件选择失败: {str(e)}"
            }
    
    @serialize_response
    def analyze_requirements_file(self, file_path: str) -> Dict:
        """
        分析 requirements.txt 文件中的依赖
        并与当前环境已安装的包进行对比
        
        Args:
            file_path: requirements.txt 文件路径
            
        Returns:
            dict: {
                "success": bool,
                "data": {
                    "total": int,
                    "installed": int,
                    "not_installed": int,
                    "conflicts": int,
                    "dependencies": [
                        {
                            "name": str,
                            "required_version": str,
                            "installed_version": str | None,
                            "status": str
                        }
                    ]
                },
                "error_message": str (可选)
            }
        """
        try:
            from packaging.specifiers import SpecifierSet
            from packaging.version import parse as parse_version
            
            logger.info(f"[DependencyController] 分析 requirements 文件: {file_path}")
            
            env = self._get_current_env()
            if not env:
                error_msg = "未选中环境或环境配置无效"
                logger.error(f"[DependencyController] {error_msg}")
                return {
                    "success": False,
                    "error_message": error_msg
                }
            
            python_path = env.get("pythonPath")
            if not python_path:
                error_msg = "Python 路径未配置"
                logger.error(f"[DependencyController] {error_msg}")
                return {
                    "success": False,
                    "error_message": error_msg
                }
            
            python_exe = Path(python_path)
            if python_exe.is_dir():
                python_exe = python_exe / "python.exe"
            
            if not python_exe.exists():
                error_msg = f"Python 可执行文件不存在: {python_exe}"
                logger.error(f"[DependencyController] {error_msg}")
                return {
                    "success": False,
                    "error_message": error_msg
                }
            
            req_file = Path(file_path)
            if not req_file.exists():
                error_msg = f"文件不存在: {file_path}"
                logger.error(f"[DependencyController] {error_msg}")
                return {
                    "success": False,
                    "error_message": error_msg
                }
            
            required_packages = self._parse_requirements_for_analysis(req_file)
            if not required_packages:
                error_msg = "文件中没有找到有效的依赖"
                logger.warning(f"[DependencyController] {error_msg}")
                return {
                    "success": False,
                    "error_message": error_msg
                }
            
            installed_packages = self._get_installed_packages(str(python_exe))
            
            dependencies = []
            stats = {
                "total": len(required_packages),
                "installed": 0,
                "not_installed": 0,
                "conflicts": 0
            }
            
            for pkg_name, version_spec in required_packages.items():
                pkg_name_lower = pkg_name.lower()
                installed_version = None
                status = "not_installed"
                
                for installed_name, installed_ver in installed_packages.items():
                    if installed_name.lower() == pkg_name_lower:
                        installed_version = installed_ver
                        break
                
                if installed_version:
                    installed_version_clean = installed_version
                    if '+' in installed_version_clean:
                        installed_version_clean = installed_version_clean.split('+')[0]
                    
                    if version_spec:
                        try:
                            spec = SpecifierSet(version_spec)
                            if parse_version(installed_version_clean) in spec:
                                status = "installed"
                                stats["installed"] += 1
                            else:
                                status = "version_mismatch"
                                stats["conflicts"] += 1
                        except Exception:
                            status = "installed"
                            stats["installed"] += 1
                    else:
                        status = "installed"
                        stats["installed"] += 1
                else:
                    status = "not_installed"
                    stats["not_installed"] += 1
                
                dependencies.append({
                    "name": pkg_name,
                    "required_version": version_spec if version_spec else "(任意版本)",
                    "installed_version": installed_version,
                    "status": status
                })
            
            self._push_analysis_log(file_path, dependencies, stats)
            
            logger.info(f"[DependencyController] 分析完成: 总数={stats['total']}, 已安装={stats['installed']}, 未安装={stats['not_installed']}, 冲突={stats['conflicts']}")
            
            return {
                "success": True,
                "data": {
                    "total": stats["total"],
                    "installed": stats["installed"],
                    "not_installed": stats["not_installed"],
                    "conflicts": stats["conflicts"],
                    "dependencies": dependencies
                }
            }
        
        except Exception as e:
            error_msg = f"分析依赖文件失败: {str(e)}"
            logger.error(f"[DependencyController] {error_msg}", exc_info=True)
            return {
                "success": False,
                "error_message": error_msg
            }
    
    def _parse_requirements_for_analysis(self, file_path: Path) -> Dict[str, str]:
        """
        解析 requirements.txt 文件用于分析
        复用 PluginScanner 的解析逻辑，支持完整格式
        
        Args:
            file_path: 文件路径
            
        Returns:
            dict: {标准化包名: 版本要求}
        """
        packages = {}
        
        try:
            from backend.src.core.plugin.plugin_scanner import PluginScanner
            scanner = PluginScanner()
            
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if line.startswith('-'):
                        continue
                    
                    dep = scanner._parse_dependency_line(line)
                    if dep:
                        if dep.environment_marker and not dep.marker_match:
                            continue
                        if dep.package.startswith('git+'):
                            continue
                        
                        pkg_name = dep.package.lower().replace('-', '_')
                        packages[pkg_name] = dep.version
        
        except Exception as e:
            logger.error(f"[DependencyController] 解析 requirements 文件失败: {str(e)}")
        
        return packages
    
    def _get_installed_packages(self, python_exe: str) -> Dict[str, str]:
        """
        获取已安装的包列表
        使用与 DependencyChecker 相同的包名标准化方式
        
        Args:
            python_exe: Python 可执行文件路径
            
        Returns:
            dict: {标准化包名: 版本}
        """
        packages = {}
        
        try:
            cmd = [python_exe, '-m', 'pip', 'list', '--format=json']
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=get_creation_flags()
            )
            
            if result.returncode == 0:
                pkg_list = json.loads(result.stdout)
                for pkg in pkg_list:
                    pkg_name = pkg['name'].lower().replace('-', '_')
                    packages[pkg_name] = pkg['version']
            else:
                logger.error(f"[DependencyController] pip list 执行失败: {result.stderr}")
        
        except Exception as e:
            logger.error(f"[DependencyController] 获取已安装包列表失败: {str(e)}")
        
        return packages
    
    @serialize_response
    def install_whl(self, file_path: str) -> Dict:
        """
        安装 .whl 文件
        
        Args:
            file_path: .whl 文件路径
            
        Returns:
            dict: {
                "success": bool,
                "log_file": str,  # 日志文件路径
                "error_message": str (可选)
            }
        """
        try:
            from datetime import datetime
            import sys
            
            logger.info(f"[DependencyController] 安装 whl 文件: {file_path}")
            
            # 检查文件是否存在
            whl_file = Path(file_path)
            if not whl_file.exists():
                return {
                    "success": False,
                    "error_message": f"文件不存在: {file_path}"
                }
            
            if whl_file.suffix.lower() != '.whl':
                return {
                    "success": False,
                    "error_message": f"不是有效的 .whl 文件: {file_path}"
                }
            
            # 获取当前环境
            env = self._get_current_env()
            if not env:
                return {
                    "success": False,
                    "error_message": "未选中环境或环境配置无效"
                }
            
            python_path = env.get("pythonPath")
            if not python_path:
                return {
                    "success": False,
                    "error_message": "Python 路径未配置"
                }
            
            from backend.src.utils.paths import get_project_root
            project_root = get_project_root()
            
            # 创建日志目录
            log_dir = project_root / "logs" / "dependencies"
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成日志文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = log_dir / f"whl_install_{timestamp}.log"
            
            builder = PythonCommandBuilder(python_path)
            
            # 获取 PyPI 镜像配置
            whl_index_url = None
            try:
                from backend.src.utils.pypi_mirror import pypi_mirror_manager
                if pypi_mirror_manager.is_enabled():
                    source = pypi_mirror_manager.get_current_source()
                    if source:
                        whl_index_url = source.get('pip_index')
                        logger.dev(f"[PyPI Mirror] WHL 安装使用镜像: {whl_index_url}")
                else:
                    logger.dev(f"[PyPI Mirror] WHL 安装镜像加速未启用，使用官方源")
            except Exception as e:
                logger.dev(f"[PyPI Mirror] 获取镜像配置失败: {e}，使用官方源")
            
            cmd = builder.pip_install(str(whl_file), index_url=whl_index_url)
            
            logger.info(f"[DependencyController] 执行命令: {' '.join(cmd)}")
            logger.info(f"[DependencyController] 日志文件: {log_file}")
            
            self._push_operation_start('安装', whl_file.name)
            
            with open(log_file, 'w', encoding='utf-8') as log_f:
                log_f.write(f"=== WHL 安装日志 ===\n")
                log_f.write(f"文件: {file_path}\n")
                log_f.write(f"Python: {builder.python_exe}\n")
                log_f.write(f"PyPI 镜像源: {whl_index_url if whl_index_url else '官方源 (pypi.org)'}\n")
                log_f.write(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_f.write(f"执行命令: {' '.join(cmd)}\n")
                log_f.write(f"{'=' * 80}\n\n")
                log_f.flush()
                
                with builder.safe_popen(cmd, use_proxy=True) as process:
                    for line in process.stdout:
                        log_f.write(line)
                        log_f.flush()
                        line_stripped = line.strip()
                        if line_stripped:
                            self._push_log('INFO', line_stripped, 'pip')
                    
                    return_code = process.wait()
                
                log_f.write(f"\n{'=' * 80}\n")
                log_f.write(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_f.write(f"返回码: {return_code}\n")
                log_f.write(f"状态: {'成功' if return_code == 0 else '失败'}\n")
            
            if return_code == 0:
                logger.info("[DependencyController] WHL 安装成功")
                self._push_operation_end(True, f'{whl_file.name} 安装成功')
                self._push_log('INFO', f'日志已保存到: {log_file}', 'system')
                return {
                    "success": True,
                    "log_file": str(log_file)
                }
            else:
                logger.error(f"[DependencyController] WHL 安装失败，返回码: {return_code}")
                self._push_operation_end(False, f'{whl_file.name} 安装失败')
                self._push_log('INFO', f'日志已保存到: {log_file}', 'system')
                return {
                    "success": False,
                    "log_file": str(log_file),
                    "error_message": f"安装失败，返回码: {return_code}"
                }
        
        except Exception as e:
            logger.error(f"[DependencyController] WHL 安装失败: {str(e)}", exc_info=True)
            self._push_operation_end(False, f'WHL 安装失败: {str(e)}')
            return {
                "success": False,
                "error_message": f"安装失败: {str(e)}"
            }

    @serialize_response
    def scan_dependencies(self) -> Dict:
        """
        扫描 ComfyUI 核心和所有插件的依赖
        
        Returns:
            dict: {
                "success": bool,
                "data": {
                    "core": [
                        {
                            "package_name": str,
                            "version_spec": str,
                            "source": "core",
                            "source_file": str
                        }
                    ],
                    "plugins": {
                        "plugin_name": [
                            {
                                "package_name": str,
                                "version_spec": str,
                                "source": str,
                                "source_file": str
                            }
                        ]
                    }
                },
                "error_message": str (可选)
            }
        """
        try:
            logger.info("[DependencyController] 开始扫描依赖")
            self._push_operation_start('扫描', 'ComfyUI 依赖')
            
            # 获取当前环境配置
            env = self._get_current_env()
            if not env:
                error_msg = "未选中环境或环境配置无效"
                logger.error(f"[DependencyController] {error_msg}")
                self._push_operation_end(False, error_msg)
                return {
                    "success": False,
                    "error_message": error_msg
                }
            
            comfyui_path = env.get("comfyuiPath")
            if not comfyui_path:
                error_msg = "ComfyUI 路径未配置"
                logger.error(f"[DependencyController] {error_msg}")
                self._push_operation_end(False, error_msg)
                return {
                    "success": False,
                    "error_message": error_msg
                }
            
            comfyui_path = Path(comfyui_path)
            if not comfyui_path.exists():
                error_msg = f"ComfyUI 路径不存在: {comfyui_path}"
                logger.error(f"[DependencyController] {error_msg}")
                self._push_operation_end(False, error_msg)
                return {
                    "success": False,
                    "error_message": error_msg
                }
            
            result = {
                "core": [],
                "plugins": {}
            }
            
            # 扫描核心依赖
            core_requirements = comfyui_path / "requirements.txt"
            if core_requirements.exists():
                logger.info(f"[DependencyController] 扫描核心依赖: {core_requirements}")
                self._push_log('info', f'扫描核心依赖: {core_requirements}', 'system')
                try:
                    core_deps = self._parse_requirements_file(core_requirements, "core")
                    result["core"] = core_deps
                    logger.info(f"[DependencyController] 核心依赖数量: {len(core_deps)}")
                except Exception as e:
                    logger.error(f"[DependencyController] 解析核心依赖失败: {str(e)}")
                    self._push_log('warning', f'解析核心依赖失败: {str(e)}', 'system')
            else:
                logger.warning(f"[DependencyController] 核心 requirements.txt 不存在: {core_requirements}")
                self._push_log('warning', f'核心 requirements.txt 不存在', 'system')
            
            # 扫描插件依赖（主路径 + 外置路径）
            custom_nodes_paths = self._get_custom_nodes_paths(comfyui_path, env)
            scanned_plugins = set()
            
            for custom_nodes_path in custom_nodes_paths:
                if not custom_nodes_path.exists() or not custom_nodes_path.is_dir():
                    logger.warning(f"[DependencyController] 插件目录不存在: {custom_nodes_path}")
                    continue
                
                logger.info(f"[DependencyController] 扫描插件目录: {custom_nodes_path}")
                self._push_log('info', f'扫描插件目录: {custom_nodes_path}', 'system')
                
                for plugin_dir in custom_nodes_path.iterdir():
                    if not plugin_dir.is_dir():
                        continue
                    
                    plugin_name = plugin_dir.name
                    
                    # 跳过已扫描的插件（外置目录优先级低于主目录，已扫描则跳过）
                    if plugin_name in scanned_plugins:
                        continue
                    scanned_plugins.add(plugin_name)
                    
                    plugin_requirements = plugin_dir / "requirements.txt"
                    
                    if plugin_requirements.exists():
                        logger.info(f"[DependencyController] 扫描插件依赖: {plugin_name}")
                        try:
                            plugin_deps = self._parse_requirements_file(plugin_requirements, plugin_name)
                            if plugin_deps:
                                result["plugins"][plugin_name] = plugin_deps
                                logger.info(f"[DependencyController] 插件 {plugin_name} 依赖数量: {len(plugin_deps)}")
                        except Exception as e:
                            logger.error(f"[DependencyController] 解析插件 {plugin_name} 依赖失败: {str(e)}")
                            self._push_log('warning', f'解析插件 {plugin_name} 依赖失败: {str(e)}', 'system')
            
            total_plugins = len(result["plugins"])
            total_deps = len(result["core"]) + sum(len(deps) for deps in result["plugins"].values())
            
            logger.info(f"[DependencyController] 扫描完成，核心依赖: {len(result['core'])}, 插件: {total_plugins}, 总依赖: {total_deps}")
            self._push_operation_end(True, f'扫描完成：核心依赖 {len(result["core"])} 个，插件 {total_plugins} 个，总依赖 {total_deps} 个')
            
            return {
                "success": True,
                "data": result
            }
            
        except Exception as e:
            error_msg = f"扫描依赖失败: {str(e)}"
            logger.error(f"[DependencyController] {error_msg}", exc_info=True)
            self._push_operation_end(False, error_msg)
            return {
                "success": False,
                "error_message": error_msg
            }
    
    def _parse_requirements_file(self, file_path: Path, source: str) -> list:
        """
        解析 requirements.txt 文件
        使用 PluginScanner 的解析逻辑，支持特殊格式
        
        Args:
            file_path: requirements.txt 文件路径
            source: 来源（"core" 或插件名）
            
        Returns:
            list: 依赖列表
        """
        dependencies = []
        
        try:
            # 使用 PluginScanner 的解析逻辑
            from backend.src.core.plugin.plugin_scanner import PluginScanner
            scanner = PluginScanner()
            
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    # 移除空白
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    # 跳过特殊标记（如 -e, -r, --extra-index-url 等）
                    if line.startswith('-') or line.startswith('--'):
                        continue
                    
                    # 使用 PluginScanner 的解析方法
                    try:
                        dep = scanner._parse_dependency_line(line)
                        if dep:
                            # 转换为字典格式
                            dep_dict = {
                                "package_name": dep.package,
                                "version_spec": dep.version,
                                "source": source,
                                "source_file": str(file_path)
                            }
                            
                            # 如果有 pip 选项，也保存
                            if hasattr(dep, 'pip_options') and dep.pip_options:
                                dep_dict["pip_options"] = dep.pip_options
                            
                            # 如果有环境标记，也保存
                            if hasattr(dep, 'environment_marker') and dep.environment_marker:
                                dep_dict["environment_marker"] = dep.environment_marker
                                dep_dict["marker_match"] = dep.marker_match
                            
                            dependencies.append(dep_dict)
                    except Exception as e:
                        logger.warning(f"[DependencyController] 解析依赖行失败 (行 {line_num}): {line}, 错误: {str(e)}")
                        continue
        
        except Exception as e:
            logger.error(f"[DependencyController] 读取文件失败: {file_path}, 错误: {str(e)}")
            raise
        
        return dependencies
    
    def check_package_status(self, package_name: str) -> Dict:
            """
            检查单个包的安装状态

            Args:
                package_name: 包名

            Returns:
                dict: {
                    "success": bool,
                    "data": {
                        "installed": bool,
                        "version": str | None,
                        "location": str | None
                    },
                    "error_message": str (可选)
                }
            """
            try:
                logger.info(f"[DependencyController] 检查包状态: {package_name}")

                # 获取当前环境配置
                env = self._get_current_env()
                if not env:
                    error_msg = "未选中环境或环境配置无效"
                    logger.error(f"[DependencyController] {error_msg}")
                    return {
                        "success": False,
                        "error_message": error_msg
                    }

                python_path = env.get("pythonPath")
                if not python_path:
                    error_msg = "Python 路径未配置"
                    logger.error(f"[DependencyController] {error_msg}")
                    return {
                        "success": False,
                        "error_message": error_msg
                    }

                builder = PythonCommandBuilder(python_path)
                cmd = builder.pip_show(package_name)
                result = builder.run(cmd, timeout=30, use_proxy=True)

                if result.returncode == 0:
                    output = result.stdout
                    version = None
                    location = None

                    for line in output.split('\n'):
                        if line.startswith('Version:'):
                            version = line.split(':', 1)[1].strip()
                        elif line.startswith('Location:'):
                            location = line.split(':', 1)[1].strip()

                    logger.info(f"[DependencyController] 包 {package_name} 已安装，版本: {version}")
                    return {
                        "success": True,
                        "data": {
                            "installed": True,
                            "version": version,
                            "location": location
                        }
                    }
                else:
                    logger.info(f"[DependencyController] 包 {package_name} 未安装")
                    return {
                        "success": True,
                        "data": {
                            "installed": False,
                            "version": None,
                            "location": None
                        }
                    }

            except Exception as e:
                error_msg = f"检查包 {package_name} 状态失败: {str(e)}"
                logger.error(f"[DependencyController] {error_msg}", exc_info=True)
                return {
                    "success": False,
                    "error_message": error_msg
                }

    
    @serialize_response
    def check_all_status(self, packages: list) -> Dict:
        """
        批量检查包的安装状态
        使用 pip list 一次性获取所有已安装的包，提高效率
        
        Args:
            packages: 包名列表
            
        Returns:
            dict: {
                "success": bool,
                "data": {
                    "package_name": {
                        "installed": bool,
                        "version": str | None
                    }
                },
                "error_message": str (可选)
            }
        """
        try:
            logger.info(f"[DependencyController] 批量检查包状态，数量: {len(packages)}")
            
            if not packages:
                return {
                    "success": True,
                    "data": {}
                }
            
            # 获取当前环境配置
            env = self._get_current_env()
            if not env:
                error_msg = "未选中环境或环境配置无效"
                logger.error(f"[DependencyController] {error_msg}")
                return {
                    "success": False,
                    "error_message": error_msg
                }
            
            python_path = env.get("pythonPath")
            if not python_path:
                error_msg = "Python 路径未配置"
                logger.error(f"[DependencyController] {error_msg}")
                return {
                    "success": False,
                    "error_message": error_msg
                }
            
            builder = PythonCommandBuilder(python_path)
            cmd = builder.pip_list()
            
            logger.debug(f"[DependencyController] 执行命令: {' '.join(cmd)}")
            result_cmd = builder.run(cmd, timeout=60, use_proxy=True)
            
            if result_cmd.returncode != 0:
                error_msg = f"执行 pip list 失败: {result_cmd.stderr}"
                logger.error(f"[DependencyController] {error_msg}")
                return {
                    "success": False,
                    "error_message": error_msg
                }
            
            # 解析 JSON 输出，构建已安装包的字典
            # 使用与 DependencyManager 一致的规范化逻辑
            import json
            
            def normalize_package_name(name: str) -> str:
                """规范化包名，与 DependencyManager._normalize_package_name 一致"""
                base_name = name.split('[')[0].strip() if '[' in name else name
                return base_name.lower().replace('_', '-')
            
            def normalize_version(version: str) -> str:
                """规范化版本号，去除本地版本标识符"""
                if '+' in version:
                    return version.split('+')[0]
                return version
            
            installed_packages = {}
            try:
                packages_list = json.loads(result_cmd.stdout)
                for pkg in packages_list:
                    pkg_name = pkg.get("name", "")
                    pkg_version = pkg.get("version", "")
                    if pkg_name:
                        normalized_name = normalize_package_name(pkg_name)
                        installed_packages[normalized_name] = pkg_version
                
                logger.debug(f"[DependencyController] 获取到 {len(packages_list)} 个已安装的包")
            except json.JSONDecodeError as e:
                error_msg = f"解析 pip list 输出失败: {str(e)}"
                logger.error(f"[DependencyController] {error_msg}")
                return {
                    "success": False,
                    "error_message": error_msg
                }
            
            # 批量匹配包状态
            result = {}
            for package_name in packages:
                normalized_name = normalize_package_name(package_name)
                if normalized_name in installed_packages:
                    result[package_name] = {
                        "installed": True,
                        "version": normalize_version(installed_packages[normalized_name])
                    }
                else:
                    result[package_name] = {
                        "installed": False,
                        "version": None
                    }
            
            installed_count = sum(1 for v in result.values() if v['installed'])
            logger.info(f"[DependencyController] 批量检查完成，已安装: {installed_count}/{len(packages)}")
            
            return {
                "success": True,
                "data": result
            }
        
        except subprocess.TimeoutExpired:
            error_msg = "执行 pip list 超时"
            logger.error(f"[DependencyController] {error_msg}")
            return {
                "success": False,
                "error_message": error_msg
            }
        except Exception as e:
            error_msg = f"批量检查包状态失败: {str(e)}"
            logger.error(f"[DependencyController] {error_msg}", exc_info=True)
            return {
                "success": False,
                "error_message": error_msg
            }
    
    @serialize_response
    def get_plugins(self) -> Dict:
        """
        获取所有插件列表
        
        Returns:
            dict: {
                "success": bool,
                "data": [
                    {
                        "name": str,
                        "path": str,
                        "has_requirements": bool,
                        "dependency_count": int
                    }
                ],
                "error_message": str (可选)
            }
        """
        try:
            logger.info("[DependencyController] 获取插件列表")
            
            # 获取当前环境配置
            env = self._get_current_env()
            if not env:
                error_msg = "未选中环境或环境配置无效"
                logger.error(f"[DependencyController] {error_msg}")
                return {
                    "success": False,
                    "error_message": error_msg
                }
            
            comfyui_path = env.get("comfyuiPath")
            if not comfyui_path:
                error_msg = "ComfyUI 路径未配置"
                logger.error(f"[DependencyController] {error_msg}")
                return {
                    "success": False,
                    "error_message": error_msg
                }
            
            comfyui_path = Path(comfyui_path)
            
            # 收集所有 custom_nodes 路径（主路径 + 外置路径）
            custom_nodes_paths = self._get_custom_nodes_paths(comfyui_path, env)
            
            EXCLUDED_PLUGIN_DIRS = {
                '__pycache__',      # Python 缓存
            }
            
            plugins = []
            scanned_plugins = set()
            
            for custom_nodes_path in custom_nodes_paths:
                if not custom_nodes_path.exists() or not custom_nodes_path.is_dir():
                    logger.warning(f"[DependencyController] 插件目录不存在: {custom_nodes_path}")
                    continue
                
                for plugin_dir in custom_nodes_path.iterdir():
                    if not plugin_dir.is_dir():
                        continue
                    
                    plugin_name = plugin_dir.name
                    
                    # 过滤特殊目录
                    if plugin_name in EXCLUDED_PLUGIN_DIRS or plugin_name.startswith('.'):
                        continue
                    
                    # 跳过已扫描的插件（主路径优先）
                    if plugin_name in scanned_plugins:
                        continue
                    scanned_plugins.add(plugin_name)
                    
                    plugin_requirements = plugin_dir / "requirements.txt"
                    has_requirements = plugin_requirements.exists()
                    dependency_count = 0
                    
                    if has_requirements:
                        try:
                            deps = self._parse_requirements_file(plugin_requirements, plugin_name)
                            dependency_count = len(deps)
                        except Exception as e:
                            logger.warning(f"[DependencyController] 解析插件 {plugin_name} 依赖失败: {str(e)}")
                    
                    plugins.append({
                        "name": plugin_name,
                        "path": str(plugin_dir),
                        "has_requirements": has_requirements,
                        "dependency_count": dependency_count
                    })
            
            # 按名称排序
            plugins.sort(key=lambda x: x["name"].lower())
            
            logger.info(f"[DependencyController] 获取插件列表完成，数量: {len(plugins)}")
            
            return {
                "success": True,
                "data": plugins
            }
        
        except Exception as e:
            error_msg = f"获取插件列表失败: {str(e)}"
            logger.error(f"[DependencyController] {error_msg}", exc_info=True)
            return {
                "success": False,
                "error_message": error_msg
            }
    
    @serialize_response
    def analyze_dependencies(self) -> Dict:
        """
        分析当前环境的依赖树和冲突
        
        协调 DependencyAnalyzer 和 ConflictDetector，获取依赖树数据并检测冲突。
        
        Returns:
            dict: {
                "success": bool,
                "data": dict | None,  # 分析结果（成功时）
                    {
                        "tree": list,  # 依赖树（DependencyNode 列表）
                        "conflicts": list,  # 冲突列表（ConflictInfo 列表）
                        "stats": dict  # 统计信息
                            {
                                "total_packages": int,
                                "total_conflicts": int,
                                "max_depth": int
                            }
                    }
                "error_message": str (可选)
            }
        """
        try:
            logger.info("[DependencyController] 开始分析依赖树和冲突")
            self._push_operation_start('分析', '依赖树')
            
            # 1. 检查当前环境是否有效
            env = self._get_current_env()
            if not env:
                error_msg = "未选中环境或环境配置无效，请先在环境管理中选择一个环境"
                logger.error(f"[DependencyController] {error_msg}")
                self._push_operation_end(False, error_msg)
                return {
                    "success": False,
                    "data": None,
                    "error_message": error_msg
                }
            
            python_path = env.get("pythonPath")
            if not python_path:
                error_msg = "Python 路径未配置"
                logger.error(f"[DependencyController] {error_msg}")
                self._push_operation_end(False, error_msg)
                return {
                    "success": False,
                    "data": None,
                    "error_message": error_msg
                }
            
            # 构造 python.exe 完整路径
            python_exe = Path(python_path)
            if python_exe.is_dir():
                python_exe = python_exe / "python.exe"
            
            if not python_exe.exists():
                error_msg = f"Python 可执行文件不存在: {python_exe}"
                logger.error(f"[DependencyController] {error_msg}")
                self._push_operation_end(False, error_msg)
                return {
                    "success": False,
                    "data": None,
                    "error_message": error_msg
                }
            
            # 2. 检查 pipdeptree 是否已安装，如果未安装则自动安装
            from ...core.dependency.dependency_analyzer import DependencyAnalyzer
            analyzer = DependencyAnalyzer(str(python_exe))
            
            logger.info("[DependencyController] 检查 pipdeptree 工具...")
            
            if not analyzer.check_pipdeptree_installed():
                logger.info("[DependencyController] pipdeptree 未安装，开始自动安装...")
                
                # 自动静默安装 pipdeptree
                install_result = analyzer.install_pipdeptree()
                
                if not install_result.get('success'):
                    error_msg = f"自动安装 pipdeptree 失败: {install_result.get('error_message', '未知错误')}"
                    logger.error(f"[DependencyController] {error_msg}")
                    self._push_operation_end(False, error_msg)
                    self._push_log('INFO', '提示：可以手动点击"安装 pipdeptree"按钮重试', 'system')
                    return {
                        "success": False,
                        "data": None,
                        "error_message": error_msg
                    }
                
                logger.info("[DependencyController] pipdeptree 安装成功")
            
            # 3. 调用 DependencyAnalyzer.get_dependency_tree() 获取依赖树
            self._push_log('INFO', '正在获取依赖树数据...', 'system')
            logger.info("[DependencyController] 调用 DependencyAnalyzer.get_dependency_tree()")
            
            tree_result = analyzer.get_dependency_tree(timeout=30)
            
            if not tree_result.get('success'):
                error_msg = tree_result.get('error_message', '获取依赖树失败')
                logger.error(f"[DependencyController] 获取依赖树失败: {error_msg}")
                self._push_operation_end(False, f'获取依赖树失败: {error_msg}')
                return {
                    "success": False,
                    "data": None,
                    "error_message": error_msg
                }
            
            tree_data = tree_result.get('tree', [])
            tree_stats = tree_result.get('stats', {})
            warnings = tree_result.get('warnings', '')
            
            logger.info(f"[DependencyController] 依赖树获取成功，包总数: {tree_stats.get('total_packages', 0)}")
            self._push_log('SUCCESS', f"依赖树获取成功，共 {tree_stats.get('total_packages', 0)} 个包", 'system')
            
            # 如果有警告信息（来自 pipdeptree 的 stderr），显示给用户
            if warnings:
                logger.warning(f"[DependencyController] pipdeptree 警告: {warnings[:500]}")
                # 解析警告信息并显示
                warning_lines = warnings.strip().split('\n')
                for line in warning_lines[:10]:  # 只显示前 10 行警告
                    if line.strip():
                        self._push_log('WARNING', line.strip(), 'pipdeptree')
            
            # 4. 调用 ConflictDetector.detect_conflicts() 检测冲突
            self._push_log('INFO', '正在检测依赖冲突...', 'system')
            logger.info("[DependencyController] 调用 ConflictDetector.detect_conflicts()")
            
            from ...core.dependency.conflict_detector import ConflictDetector
            from ...core.dependency.models import DependencyNode
            
            # 将字典列表转换为 DependencyNode 对象列表
            def dict_to_node(node_dict: Dict) -> DependencyNode:
                """将字典转换为 DependencyNode 对象"""
                node = DependencyNode(
                    id=node_dict['id'],
                    package_name=node_dict['packageName'],
                    installed_version=node_dict['installedVersion'],
                    required_version=node_dict.get('requiredVersion'),
                    depth=node_dict['depth'],
                    parent_id=node_dict.get('parentId')
                )
                
                # 递归转换子依赖
                for dep_dict in node_dict.get('dependencies', []):
                    child_node = dict_to_node(dep_dict)
                    node.dependencies.append(child_node)
                
                return node
            
            tree_nodes = [dict_to_node(node_dict) for node_dict in tree_data]
            
            detector = ConflictDetector()
            
            # 优先使用 pipdeptree 警告信息中的冲突（更准确）
            # 如果没有警告信息，才使用树分析的冲突
            if warnings:
                logger.info(f"[DependencyController] 警告信息长度: {len(warnings)} 字符")
                logger.debug(f"[DependencyController] 警告信息内容:\n{warnings[:1000]}")
                
                # 只使用警告信息中的冲突
                conflicts = detector.parse_pipdeptree_warnings(warnings)
                logger.info(f"[DependencyController] 从 pipdeptree 警告中解析出 {len(conflicts)} 个冲突")
                
                # 打印每个冲突的详细信息
                for i, conflict in enumerate(conflicts, 1):
                    logger.debug(f"[DependencyController] 冲突 #{i}: {conflict.package_name} (来源: {conflict.source}, 类型: {conflict.type})")
                
                # 合并相同包的冲突
                # 去重策略：
                # 1. 对于 version_mismatch: 包名 + 类型 + 已安装版本
                # 2. 对于 missing_dependency: 包名 + 类型
                # 3. 对于 circular_dependency: 包名 + 类型
                conflict_map = {}
                
                for conflict in conflicts:
                    if conflict.type == 'missing_dependency':
                        # 缺失依赖：只用包名作为 key
                        key = f"{conflict.package_name}|missing"
                    elif conflict.type == 'version_mismatch':
                        # 版本不匹配：包名 + 类型 + 已安装版本
                        key = f"{conflict.package_name}|version_mismatch|{conflict.installed_version}"
                    else:
                        # 其他类型（如循环依赖）：包名 + 类型
                        key = f"{conflict.package_name}|{conflict.type}"
                    
                    if key not in conflict_map:
                        conflict_map[key] = {
                            'conflict': conflict,
                            'sources': [conflict.source],
                            'requirements': [conflict.required_version] if conflict.required_version else []
                        }
                    else:
                        # 合并来源和版本要求
                        existing = conflict_map[key]
                        if conflict.source not in existing['sources']:
                            existing['sources'].append(conflict.source)
                        if conflict.required_version and conflict.required_version not in existing['requirements']:
                            existing['requirements'].append(conflict.required_version)
                
                # 更新冲突对象的来源和描述
                conflicts = []
                for key, data in conflict_map.items():
                    conflict = data['conflict']
                    sources = data['sources']
                    requirements = data['requirements']
                    
                    # 调试日志
                    logger.debug(f"[DependencyController] 处理冲突: {conflict.package_name}")
                    logger.debug(f"[DependencyController]   来源: {sources}")
                    logger.debug(f"[DependencyController]   版本要求: {requirements}")
                    logger.debug(f"[DependencyController]   要求数量: {len(requirements)}")
                    
                    # 更新来源
                    conflict.source = ', '.join(sources)
                    
                    # 对于 missing_dependency，合并版本要求
                    if conflict.type == 'missing_dependency':
                        # 过滤掉 'Any' 和空值
                        valid_reqs = [r for r in requirements if r and r not in ['Any', '?', 'none']]
                        
                        if len(valid_reqs) > 1:
                            # 多个版本要求，需要合并
                            strictest_req = self._get_strictest_requirement(valid_reqs)
                            
                            # 检查是否存在版本冲突
                            if strictest_req.startswith('冲突！'):
                                # 版本要求互相冲突，提升严重程度
                                conflict.severity = 'critical'
                                merged_req = ', '.join(valid_reqs)
                                conflict.required_version = merged_req
                                conflict.description = f"包 {conflict.source} 对 {conflict.package_name} 的版本要求互相冲突 ({merged_req})，无法同时满足"
                                conflict.suggestion = f"版本要求冲突：{strictest_req}。需要手动解决依赖冲突，可能需要升级或更换某些依赖包"
                            elif strictest_req:
                                # 使用合并后的版本要求
                                conflict.required_version = strictest_req
                                conflict.description = f"包 {conflict.source} 依赖 {conflict.package_name}{strictest_req}，但该包未安装"
                                conflict.suggestion = f"运行 'pip install {conflict.package_name}{strictest_req}' 安装缺失的依赖"
                        elif len(valid_reqs) == 1:
                            # 只有一个版本要求，直接使用
                            conflict.required_version = valid_reqs[0]
                            conflict.description = f"包 {conflict.source} 依赖 {conflict.package_name}{valid_reqs[0]}，但该包未安装"
                            conflict.suggestion = f"运行 'pip install {conflict.package_name}{valid_reqs[0]}' 安装缺失的依赖"
                        else:
                            conflict.description = f"包 {conflict.source} 依赖 {conflict.package_name}，但该包未安装"
                    
                    # 对于 version_mismatch，合并版本要求并更新描述
                    elif conflict.type == 'version_mismatch':
                        # 过滤掉空值
                        valid_reqs = [r for r in requirements if r]
                        
                        if len(valid_reqs) > 1:
                            # 多个版本要求，需要合并
                            strictest_req = self._get_strictest_requirement(valid_reqs)
                            
                            # 检查是否存在版本冲突
                            if strictest_req.startswith('冲突！'):
                                # 版本要求互相冲突，提升严重程度
                                conflict.severity = 'critical'
                                merged_req = ', '.join(valid_reqs)
                                conflict.required_version = merged_req
                                conflict.description = f"包 {conflict.source} 对 {conflict.package_name} 的版本要求互相冲突 ({merged_req})，当前安装的是 {conflict.installed_version}"
                                conflict.suggestion = f"版本要求冲突：{strictest_req}。需要手动解决依赖冲突，可能需要升级或更换某些依赖包"
                            elif strictest_req:
                                # 使用合并后的版本要求
                                conflict.required_version = strictest_req
                                conflict.description = f"包 {conflict.source} 要求 {conflict.package_name}{strictest_req}，但当前安装的是 {conflict.installed_version}"
                                conflict.suggestion = f"运行 'pip install --upgrade {conflict.package_name}{strictest_req}' 升级到兼容版本"
                        elif len(valid_reqs) == 1:
                            # 只有一个版本要求，直接使用
                            conflict.required_version = valid_reqs[0]
                            conflict.description = f"包 {conflict.source} 要求 {conflict.package_name}{valid_reqs[0]}，但当前安装的是 {conflict.installed_version}"
                            conflict.suggestion = f"运行 'pip install --upgrade {conflict.package_name}{valid_reqs[0]}' 升级到兼容版本"
                        else:
                            # 没有版本要求，使用原始描述
                            conflict.description = f"包 {conflict.source} 要求 {conflict.package_name}{conflict.required_version}，但当前安装的是 {conflict.installed_version}"
                    
                    conflicts.append(conflict)
                
                logger.info(f"[DependencyController] 去重和合并后剩余 {len(conflicts)} 个冲突")
            else:
                # 没有警告信息，使用树分析的冲突作为后备
                logger.info("[DependencyController] 没有 pipdeptree 警告信息，使用树分析检测冲突")
                conflicts = detector.detect_conflicts(tree_nodes)
                logger.info(f"[DependencyController] 从依赖树中检测到 {len(conflicts)} 个冲突")
            
            # 将 ConflictInfo 对象转换为字典
            conflicts_data = [conflict.to_dict() for conflict in conflicts]
            
            logger.info(f"[DependencyController] 冲突检测完成，发现 {len(conflicts)} 个冲突")
            logger.info(f"[DependencyController] 冲突数据长度: {len(conflicts_data)}")
            
            # 打印前几个冲突的包名
            if conflicts_data:
                package_names = [c['packageName'] for c in conflicts_data[:5]]
                logger.info(f"[DependencyController] 前5个冲突包名: {package_names}")
            
            if conflicts:
                self._push_log('WARNING', f"检测到 {len(conflicts)} 个依赖冲突", 'system')
            else:
                self._push_log('SUCCESS', "未检测到依赖冲突", 'system')
            
            # 5. 返回结构化的分析结果
            result_data = {
                'tree': tree_data,
                'conflicts': conflicts_data,
                'stats': {
                    'total_packages': tree_stats.get('total_packages', 0),
                    'total_conflicts': len(conflicts),
                    'max_depth': tree_stats.get('max_depth', 0)
                }
            }
            
            logger.info("[DependencyController] 依赖分析完成")
            self._push_operation_end(True, f'依赖分析完成，共 {tree_stats.get("total_packages", 0)} 个包')
            
            return {
                "success": True,
                "data": result_data
            }
        
        except Exception as e:
            error_msg = f"分析依赖时出错: {str(e)}"
            logger.error(f"[DependencyController] {error_msg}", exc_info=True)
            self._push_operation_end(False, error_msg)
            return {
                "success": False,
                "data": None,
                "error_message": error_msg
            }
    
    @serialize_response
    def check_pipdeptree(self) -> Dict:
        """
        检查 pipdeptree 是否已安装
        
        Returns:
            dict: {
                "success": bool,
                "installed": bool,  # pipdeptree 是否已安装
                "version": str | None,  # pipdeptree 版本（如果已安装）
                "error_message": str (可选)
            }
        """
        try:
            logger.info("[DependencyController] 检查 pipdeptree 是否已安装")
            
            # 获取当前环境
            env = self._get_current_env()
            if not env:
                error_msg = "未选中环境或环境配置无效"
                logger.error(f"[DependencyController] {error_msg}")
                return {
                    "success": False,
                    "installed": False,
                    "version": None,
                    "error_message": error_msg
                }
            
            python_path = env.get("pythonPath")
            if not python_path:
                error_msg = "Python 路径未配置"
                logger.error(f"[DependencyController] {error_msg}")
                return {
                    "success": False,
                    "installed": False,
                    "version": None,
                    "error_message": error_msg
                }
            
            builder = PythonCommandBuilder(python_path)
            
            from ...core.dependency.dependency_analyzer import DependencyAnalyzer
            analyzer = DependencyAnalyzer(str(builder.python_exe))
            
            is_installed = analyzer.check_pipdeptree_installed()
            
            if is_installed:
                try:
                    cmd = builder.pip_show('pipdeptree')
                    result = builder.run(cmd, timeout=10, use_proxy=True)
                    
                    if result.returncode == 0:
                        version_match = re.search(r'Version: (.+)', result.stdout)
                        version = version_match.group(1) if version_match else 'unknown'
                        
                        logger.info(f"[DependencyController] pipdeptree 已安装，版本: {version}")
                        return {
                            "success": True,
                            "installed": True,
                            "version": version
                        }
                except Exception as e:
                    logger.warning(f"[DependencyController] 获取 pipdeptree 版本失败: {str(e)}")
                    return {
                        "success": True,
                        "installed": True,
                        "version": None
                    }
            
            logger.info("[DependencyController] pipdeptree 未安装")
            return {
                "success": True,
                "installed": False,
                "version": None
            }
        
        except Exception as e:
            error_msg = f"检查 pipdeptree 时出错: {str(e)}"
            logger.error(f"[DependencyController] {error_msg}", exc_info=True)
            return {
                "success": False,
                "installed": False,
                "version": None,
                "error_message": error_msg
            }
    
    @serialize_response
    def install_pipdeptree(self) -> Dict:
        """
        安装 pipdeptree 工具
        
        自动在当前环境中安装 pipdeptree 工具，用于依赖树分析。
        
        Returns:
            dict: {
                "success": bool,
                "message": str,  # 成功消息（仅在成功时）
                "error_message": str (可选)
            }
        """
        try:
            logger.info("[DependencyController] 开始安装 pipdeptree")
            
            # 获取当前环境
            env = self._get_current_env()
            if not env:
                error_msg = "未选中环境或环境配置无效"
                logger.error(f"[DependencyController] {error_msg}")
                self._push_operation_start('安装', 'pipdeptree')
                self._push_operation_end(False, error_msg)
                return {
                    "success": False,
                    "message": "",
                    "error_message": error_msg
                }
            
            python_path = env.get("pythonPath")
            if not python_path:
                error_msg = "Python 路径未配置"
                logger.error(f"[DependencyController] {error_msg}")
                self._push_operation_start('安装', 'pipdeptree')
                self._push_operation_end(False, error_msg)
                return {
                    "success": False,
                    "message": "",
                    "error_message": error_msg
                }
            
            # 构造 python.exe 完整路径
            python_exe = Path(python_path)
            if python_exe.is_dir():
                python_exe = python_exe / "python.exe"
            
            # 使用 DependencyAnalyzer 安装 pipdeptree
            from ...core.dependency.dependency_analyzer import DependencyAnalyzer
            analyzer = DependencyAnalyzer(str(python_exe))
            
            # 推送开始安装的日志
            self._push_operation_start('安装', 'pipdeptree')
            
            # 执行安装
            result = analyzer.install_pipdeptree()
            
            if result['success']:
                logger.info("[DependencyController] pipdeptree 安装成功")
                self._push_operation_end(True, 'pipdeptree 安装成功')
                return {
                    "success": True,
                    "message": result.get('message', 'pipdeptree 安装成功')
                }
            else:
                error_msg = result.get('error_message', '安装失败')
                logger.error(f"[DependencyController] pipdeptree 安装失败: {error_msg}")
                self._push_operation_end(False, f'pipdeptree 安装失败: {error_msg}')
                return {
                    "success": False,
                    "message": "",
                    "error_message": error_msg
                }
        
        except Exception as e:
            error_msg = f"安装 pipdeptree 时出错: {str(e)}"
            logger.error(f"[DependencyController] {error_msg}", exc_info=True)
            self._push_operation_end(False, error_msg)
            return {
                "success": False,
                "message": "",
                "error_message": error_msg
            }

    @serialize_response
    def export_analysis_report(self, format: str, tree: List[Dict], conflicts: List[Dict]) -> Dict:
        """
        导出依赖分析报告
        
        将依赖树和冲突信息导出为 JSON 或 Markdown 格式的文件。
        
        Args:
            format: 导出格式 ('json' 或 'markdown')
            tree: 依赖树数据（字典列表）
            conflicts: 冲突信息列表（字典列表）
        
        Returns:
            dict: {
                "success": bool,
                "file_path": str | None,  # 保存的文件路径（成功时）
                "content": str | None,  # 文件内容（成功时）
                "error_message": str (可选)
            }
        """
        try:
            logger.info(f"[DependencyController] 开始导出分析报告，格式: {format}")
            
            # 验证格式参数
            if format not in ['json', 'markdown']:
                error_msg = f"不支持的导出格式: {format}，仅支持 'json' 或 'markdown'"
                logger.error(f"[DependencyController] {error_msg}")
                return {
                    "success": False,
                    "file_path": None,
                    "content": None,
                    "error_message": error_msg
                }
            
            # 生成带时间戳的文件名
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'dependency_analysis_{timestamp}.{format if format == "json" else "md"}'
            
            # 获取当前环境信息（用于报告标题）
            env = self._get_current_env()
            env_name = env.get('name', '未知环境') if env else '未知环境'
            
            # 生成内容
            if format == 'json':
                content = self._generate_json_report(tree, conflicts, timestamp, env_name)
            else:  # markdown
                content = self._generate_markdown_report(tree, conflicts, timestamp, env_name)
            
            # 使用 pywebview 的文件保存对话框
            if self.window:
                try:
                    import webview
                    
                    default_directory = os.path.expanduser('~')
                    file_path = self.window.create_file_dialog(
                        dialog_type=webview.SAVE_DIALOG,
                        directory=default_directory,
                        save_filename=filename,
                        file_types=(
                            'JSON Files (*.json)' if format == 'json' else 'Markdown Files (*.md)',
                        )
                    )
                    
                    if not file_path:
                        logger.info("[DependencyController] 用户取消了文件保存")
                        return {
                            "success": False,
                            "file_path": None,
                            "content": None,
                            "error_message": "用户取消了文件保存"
                        }
                    
                    # 如果返回的是列表，取第一个元素
                    if isinstance(file_path, list):
                        file_path = file_path[0] if file_path else None
                    
                    if not file_path:
                        return {
                            "success": False,
                            "file_path": None,
                            "content": None,
                            "error_message": "未选择保存位置"
                        }
                    
                    # 写入文件
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    logger.info(f"[DependencyController] 报告已保存到: {file_path}")
                    self._push_log('SUCCESS', f'分析报告已导出到: {file_path}', 'system')
                    
                    return {
                        "success": True,
                        "file_path": str(file_path),
                        "content": content
                    }
                    
                except PermissionError as e:
                    error_msg = "没有权限写入文件，请选择其他位置"
                    logger.error(f"[DependencyController] {error_msg}: {str(e)}")
                    return {
                        "success": False,
                        "file_path": None,
                        "content": None,
                        "error_message": error_msg
                    }
                except OSError as e:
                    if 'No space left' in str(e):
                        error_msg = "磁盘空间不足，无法保存文件"
                    else:
                        error_msg = f"保存文件时出错: {str(e)}"
                    logger.error(f"[DependencyController] {error_msg}", exc_info=True)
                    return {
                        "success": False,
                        "file_path": None,
                        "content": None,
                        "error_message": error_msg
                    }
                except Exception as e:
                    error_msg = f"保存文件时出错: {str(e)}"
                    logger.error(f"[DependencyController] {error_msg}", exc_info=True)
                    return {
                        "success": False,
                        "file_path": None,
                        "content": None,
                        "error_message": error_msg
                    }
            else:
                # 如果没有 window 对象，返回内容但不保存文件
                logger.warning("[DependencyController] window 对象未设置，无法打开文件对话框")
                return {
                    "success": True,
                    "file_path": None,
                    "content": content
                }
        
        except Exception as e:
            error_msg = f"导出报告时出错: {str(e)}"
            logger.error(f"[DependencyController] {error_msg}", exc_info=True)
            self._push_log('ERROR', error_msg, 'system')
            return {
                "success": False,
                "file_path": None,
                "content": None,
                "error_message": error_msg
            }
    
    def _generate_json_report(self, tree: List[Dict], conflicts: List[Dict], 
                             timestamp: str, env_name: str) -> str:
        """
        生成 JSON 格式的分析报告
        
        Args:
            tree: 依赖树数据
            conflicts: 冲突信息列表
            timestamp: 时间戳
            env_name: 环境名称
        
        Returns:
            str: JSON 格式的报告内容
        """
        import json
        
        report = {
            'metadata': {
                'environment': env_name,
                'timestamp': timestamp,
                'format_version': '1.0'
            },
            'tree': tree,
            'conflicts': conflicts,
            'statistics': {
                'total_packages': self._count_packages(tree),
                'total_conflicts': len(conflicts),
                'conflict_by_severity': self._count_conflicts_by_severity(conflicts)
            }
        }
        
        return json.dumps(report, indent=2, ensure_ascii=False)
    
    def _generate_markdown_report(self, tree: List[Dict], conflicts: List[Dict],
                                  timestamp: str, env_name: str) -> str:
        """
        生成 Markdown 格式的分析报告
        
        Args:
            tree: 依赖树数据
            conflicts: 冲突信息列表
            timestamp: 时间戳
            env_name: 环境名称
        
        Returns:
            str: Markdown 格式的报告内容
        """
        from datetime import datetime
        
        # 格式化时间戳为可读格式
        try:
            dt = datetime.strptime(timestamp, '%Y%m%d_%H%M%S')
            readable_time = dt.strftime('%Y年%m月%d日 %H:%M:%S')
        except (ValueError, TypeError):
            readable_time = timestamp
        
        lines = []
        lines.append(f"# 依赖分析报告\n")
        lines.append(f"**环境**: {env_name}\n")
        lines.append(f"**生成时间**: {readable_time}\n")
        lines.append(f"---\n")
        
        # 统计信息
        total_packages = self._count_packages(tree)
        total_conflicts = len(conflicts)
        conflict_by_severity = self._count_conflicts_by_severity(conflicts)
        
        lines.append(f"## 统计摘要\n")
        lines.append(f"- **总包数**: {total_packages}\n")
        lines.append(f"- **冲突总数**: {total_conflicts}\n")
        
        if conflict_by_severity:
            lines.append(f"  - 严重 (Critical): {conflict_by_severity.get('critical', 0)}\n")
            lines.append(f"  - 警告 (Warning): {conflict_by_severity.get('warning', 0)}\n")
            lines.append(f"  - 信息 (Info): {conflict_by_severity.get('info', 0)}\n")
        
        lines.append(f"\n")
        
        # 冲突详情
        if conflicts:
            lines.append(f"## 冲突详情\n")
            
            # 按严重程度分组
            for severity in ['critical', 'warning', 'info']:
                severity_conflicts = [c for c in conflicts if c.get('severity') == severity]
                if not severity_conflicts:
                    continue
                
                severity_label = {
                    'critical': '🔴 严重',
                    'warning': '⚠️ 警告',
                    'info': 'ℹ️ 信息'
                }.get(severity, severity)
                
                lines.append(f"### {severity_label}\n")
                
                for conflict in severity_conflicts:
                    package_name = conflict.get('packageName', '未知包')
                    conflict_type = conflict.get('type', 'unknown')
                    description = conflict.get('description', '无描述')
                    suggestion = conflict.get('suggestion', '无建议')
                    
                    type_icon = {
                        'version_mismatch': '📦',
                        'circular_dependency': '🔄',
                        'missing_dependency': '❌'
                    }.get(conflict_type, '❓')
                    
                    lines.append(f"#### {type_icon} {package_name}\n")
                    lines.append(f"- **类型**: {conflict_type}\n")
                    lines.append(f"- **描述**: {description}\n")
                    lines.append(f"- **建议**: {suggestion}\n")
                    lines.append(f"\n")
        else:
            lines.append(f"## 冲突详情\n")
            lines.append(f"✅ 未检测到依赖冲突\n\n")
        
        # 依赖树概览
        lines.append(f"## 依赖树概览\n")
        lines.append(f"以下是顶层依赖包列表：\n\n")
        
        for node in tree:
            package_name = node.get('packageName', '未知包')
            installed_version = node.get('installedVersion', '未知版本')
            has_conflict = node.get('hasConflict', False)
            conflict_icon = '⚠️' if has_conflict else '✓'
            
            lines.append(f"- {conflict_icon} **{package_name}** ({installed_version})\n")
        
        lines.append(f"\n---\n")
        lines.append(f"*此报告由 ComfyNexus 依赖管理模块自动生成*\n")
        
        return ''.join(lines)
    
    def _count_packages(self, tree: List[Dict]) -> int:
        """
        递归统计依赖树中的包总数
        
        Args:
            tree: 依赖树数据
        
        Returns:
            int: 包总数
        """
        count = len(tree)
        for node in tree:
            dependencies = node.get('dependencies', [])
            if dependencies:
                count += self._count_packages(dependencies)
        return count
    
    def _count_conflicts_by_severity(self, conflicts: List[Dict]) -> Dict[str, int]:
        """
        按严重程度统计冲突数量
        
        Args:
            conflicts: 冲突信息列表
        
        Returns:
            dict: 按严重程度分组的冲突数量
        """
        result = {'critical': 0, 'warning': 0, 'info': 0}
        for conflict in conflicts:
            severity = conflict.get('severity', 'info')
            if severity in result:
                result[severity] += 1
        return result
    
    def _get_strictest_requirement(self, requirements: List[str]) -> str:
        """
        从多个版本要求中选择最严格的一个，或检测明显的冲突
        
        只检测明显的逻辑冲突，其他情况智能合并要求。
        
        明显冲突的情况：
        - 多个不同的 == 要求（如 ==1.0 和 ==2.0）
        - == 版本不满足 >= 或 > 的最小要求
        - == 版本不满足 <= 或 < 的最大要求
        
        智能合并规则：
        - 多个 >= 要求：选择最大的版本（如 ['>=1.10.0', '>=2.0.0'] -> '>=2.0.0'）
        - 多个 > 要求：选择最大的版本
        - 多个 <= 要求：选择最小的版本
        - 多个 < 要求：选择最小的版本
        - 混合要求：保留所有不同类型的要求（如 ['>=1.0.0', '<3.0.0'] -> '>=1.0.0,<3.0.0'）
        
        例如：
        - ['>=1.10.0', '>=2.0.0'] -> '>=2.0.0'
        - ['>=1.0.0', '==2.0.0'] -> '==2.0.0'
        - ['>=2.0.0', '==1.0.0'] -> '冲突！(==1.0.0 不满足 >=2.0.0)'
        - ['>=1.0.0', '<3.0.0'] -> '>=1.0.0,<3.0.0'
        - ['>=1.17,<2.0.0', '>=1.17,<2.0', '>=1.17'] -> '>=1.17,<2.0'
        
        Args:
            requirements: 版本要求列表
        
        Returns:
            str: 最严格的版本要求，或冲突提示
        """
        if not requirements:
            return ''
        
        if len(requirements) == 1:
            return requirements[0]
        
        try:
            from packaging.specifiers import SpecifierSet, Specifier
            from packaging.version import parse as parse_version
            
            # 尝试合并所有要求
            combined = ','.join(requirements)
            spec_set = SpecifierSet(combined)
            
            # 提取所有 == 要求
            eq_versions = []
            for req in requirements:
                req = req.strip()
                if req.startswith('=='):
                    try:
                        ver_str = req[2:].strip()
                        eq_versions.append(parse_version(ver_str))
                    except (ValueError, TypeError):
                        pass
            
            # 检测冲突 1: 多个不同的 == 要求
            if len(eq_versions) > 1:
                unique_versions = set(str(v) for v in eq_versions)
                if len(unique_versions) > 1:
                    logger.warning(f"版本要求冲突: 要求多个不同的精确版本 {unique_versions}")
                    return f"冲突！(要求多个不同的精确版本: {', '.join(unique_versions)})"
            
            # 检测冲突 2: == 版本是否满足其他要求
            if eq_versions:
                eq_ver = eq_versions[0]
                
                # 检查是否满足所有其他要求
                for req in requirements:
                    req = req.strip()
                    if req.startswith('=='):
                        continue
                    
                    try:
                        # 解析单个要求
                        single_spec = SpecifierSet(req)
                        if eq_ver not in single_spec:
                            logger.warning(f"版本要求冲突: =={eq_ver} 不满足 {req}")
                            return f"冲突！(=={eq_ver} 不满足 {req})"
                    except (ValueError, TypeError):
                        pass
            
            # 智能简化：对于同类型的要求，选择最严格的
            # 分类所有 specifier
            ge_specs = []  # >=
            gt_specs = []  # >
            le_specs = []  # <=
            lt_specs = []  # <
            eq_specs = []  # ==
            ne_specs = []  # !=
            other_specs = []  # 其他（如 ~=）
            
            for spec in spec_set:
                if spec.operator == '>=':
                    ge_specs.append(spec)
                elif spec.operator == '>':
                    gt_specs.append(spec)
                elif spec.operator == '<=':
                    le_specs.append(spec)
                elif spec.operator == '<':
                    lt_specs.append(spec)
                elif spec.operator == '==':
                    eq_specs.append(spec)
                elif spec.operator == '!=':
                    ne_specs.append(spec)
                else:
                    other_specs.append(spec)
            
            # 简化同类型的要求
            simplified_specs = []
            
            # >= 要求：选择最大的版本
            if ge_specs:
                max_spec = max(ge_specs, key=lambda s: parse_version(s.version))
                simplified_specs.append(str(max_spec))
            
            # > 要求：选择最大的版本
            if gt_specs:
                max_spec = max(gt_specs, key=lambda s: parse_version(s.version))
                simplified_specs.append(str(max_spec))
            
            # <= 要求：选择最小的版本
            if le_specs:
                min_spec = min(le_specs, key=lambda s: parse_version(s.version))
                simplified_specs.append(str(min_spec))
            
            # < 要求：选择最小的版本
            if lt_specs:
                min_spec = min(lt_specs, key=lambda s: parse_version(s.version))
                simplified_specs.append(str(min_spec))
            
            # == 要求：保留（已经检查过冲突）
            if eq_specs:
                simplified_specs.extend(str(s) for s in eq_specs)
            
            # != 要求：保留所有
            if ne_specs:
                simplified_specs.extend(str(s) for s in ne_specs)
            
            # 其他要求：保留所有
            if other_specs:
                simplified_specs.extend(str(s) for s in other_specs)
            
            # 合并简化后的要求
            result = ','.join(simplified_specs)
            logger.debug(f"合并版本要求 {requirements} -> {result}")
            return result
        
        except Exception as e:
            logger.debug(f"合并版本要求时出错 {requirements}: {str(e)}")
            
            # 如果合并失败，返回第一个要求
            return requirements[0]

    @serialize_response
    def fix_conflict(self, conflict_data: Dict, mirror_source: str = 'official') -> Dict:
        """
        修复单个依赖冲突
        
        根据冲突类型自动选择修复策略：
        - missing_dependency: 安装缺失的包
        - version_mismatch: 升级/降级到兼容版本
        
        Args:
            conflict_data: 冲突信息字典
                {
                    "id": str,
                    "type": str,  # 'missing_dependency' | 'version_mismatch' | 'circular_dependency'
                    "packageName": str,
                    "installedVersion": str,
                    "requiredVersion": str,
                    "source": str
                }
            mirror_source: 镜像源 ('auto', 'official', 'tuna', 'bfsu', 'aliyun', 'tencent')
            
        Returns:
            dict: {
                "success": bool,
                "message": str,
                "command": str,  # 执行的命令
                "log_file": str (可选),  # 日志文件路径
                "error_message": str (可选)
            }
        """
        try:
            conflict_type = conflict_data.get('type')
            package_name = conflict_data.get('packageName')
            required_version = conflict_data.get('requiredVersion', '')
            
            logger.info(f"[DependencyController] 开始修复冲突: {package_name} ({conflict_type})")
            
            # 获取当前环境
            env = self._get_current_env()
            if not env:
                return {
                    "success": False,
                    "error_message": "未选中环境或环境配置无效"
                }
            
            python_path = env.get("pythonPath")
            if not python_path:
                return {
                    "success": False,
                    "error_message": "Python 路径未配置"
                }
            
            builder = PythonCommandBuilder(python_path)
            
            mirror_config = _get_pypi_mirror_config(mirror_source)
            pip_index = mirror_config['pip_index']
            
            if mirror_source != 'official':
                logger.dev(f"[PyPI Mirror] 依赖修复使用镜像: {pip_index}")
            else:
                logger.dev(f"[PyPI Mirror] 依赖修复使用官方源")
            
            if conflict_type == 'missing_dependency':
                if required_version and required_version not in ['Any', '?', 'none']:
                    version_spec = required_version.strip()
                    cmd = builder.pip_install(package_name, version=version_spec, extra_args=['-i', pip_index] if mirror_source != 'official' else None)
                else:
                    cmd = builder.pip_install(package_name, extra_args=['-i', pip_index] if mirror_source != 'official' else None)
                
                action = '安装'
            
            elif conflict_type == 'version_mismatch':
                if required_version and required_version not in ['Any', '?', 'none']:
                    version_spec = required_version.strip()
                    cmd = builder.pip_install(package_name, version=version_spec, extra_args=['--upgrade', '-i', pip_index] if mirror_source != 'official' else ['--upgrade'])
                else:
                    cmd = builder.pip_install(package_name, extra_args=['--upgrade', '-i', pip_index] if mirror_source != 'official' else ['--upgrade'])
                
                action = '升级'
            
            elif conflict_type == 'circular_dependency':
                return {
                    "success": False,
                    "error_message": "循环依赖无法自动修复，需要手动调整包结构"
                }
            
            else:
                return {
                    "success": False,
                    "error_message": f"不支持的冲突类型: {conflict_type}"
                }
            
            command_str = ' '.join(cmd)
            logger.info(f"[DependencyController] 执行修复命令: {command_str}")
            
            self._push_operation_start(action, package_name)
            
            from backend.src.utils.paths import get_project_root
            project_root = get_project_root()
            
            log_dir = project_root / "logs" / "dependencies"
            log_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = log_dir / f"fix_{package_name}_{timestamp}.log"
            
            with open(log_file, 'w', encoding='utf-8') as log_f:
                log_f.write(f"=== 冲突修复日志 ===\n")
                log_f.write(f"包名: {package_name}\n")
                log_f.write(f"冲突类型: {conflict_type}\n")
                log_f.write(f"要求版本: {required_version}\n")
                log_f.write(f"操作: {action}\n")
                log_f.write(f"镜像源: {mirror_source}\n")
                log_f.write(f"Python: {builder.python_exe}\n")
                log_f.write(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_f.write(f"执行命令: {command_str}\n")
                log_f.write(f"{'=' * 80}\n\n")
                log_f.flush()
                
                with builder.safe_popen(cmd, use_proxy=True) as process:
                    for line in process.stdout:
                        log_f.write(line)
                        log_f.flush()
                        if line.strip():
                            self._push_log('INFO', line.strip(), 'pip')
                    
                    return_code = process.wait()
                
                log_f.write(f"\n{'=' * 80}\n")
                log_f.write(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_f.write(f"返回码: {return_code}\n")
                log_f.write(f"状态: {'成功' if return_code == 0 else '失败'}\n")
            
            if return_code == 0:
                logger.info(f"[DependencyController] 冲突修复成功: {package_name}")
                self._push_operation_end(True, f'{package_name} {action}成功')
                
                return {
                    "success": True,
                    "message": f'{package_name} {action}成功',
                    "command": command_str,
                    "log_file": str(log_file)
                }
            else:
                logger.error(f"[DependencyController] 冲突修复失败: {package_name}, 返回码: {return_code}")
                self._push_operation_end(False, f'{package_name} {action}失败')
                
                return {
                    "success": False,
                    "message": f'{package_name} {action}失败',
                    "command": command_str,
                    "log_file": str(log_file),
                    "error_message": f"{action}失败，返回码: {return_code}，请查看日志了解详情"
                }
        
        except Exception as e:
            error_msg = f"修复冲突时出错: {str(e)}"
            logger.error(f"[DependencyController] {error_msg}", exc_info=True)
            self._push_operation_end(False, error_msg)
            
            return {
                "success": False,
                "error_message": error_msg
            }
