"""
ComfyNexus 主应用入口
"""

import sys
import os
import time
import threading
import logging
from pathlib import Path


def safe_print(text):
    """
    安全的打印函数，处理 Windows 控制台的编码问题
    
    在打包后的环境中，Windows 控制台可能使用 GBK 编码，
    无法正确显示 emoji 等 Unicode 字符。
    此函数会先替换 emoji 为文本，然后再打印。
    """
    # Emoji 映射表（与 logger.py 中的 SafeStreamHandler 保持一致）
    emoji_map = {
        '🚀': '[启动]',
        '💾': '[数据]',
        '📁': '[目录]',
        '🌐': '[文件]',
        '🔗': '[地址]',
        '🔌': '[端口]',
        '📡': '[API]',
        '🖥️': '[屏幕]',
        '📍': '[位置]',
        '📐': '[尺寸]',
        '✅': '[成功]',
        '⚠️': '[警告]',
        '❌': '[错误]',
        '🔍': '[调试]',
        '🎯': '[目标]',
        '📝': '[记录]',
    }
    
    # 先替换 emoji 为文本
    safe_text = text
    for emoji, replacement in emoji_map.items():
        safe_text = safe_text.replace(emoji, replacement)
    
    # 尝试打印
    try:
        print(safe_text)
    except UnicodeEncodeError:
        # 如果还有其他无法编码的字符，使用 errors='replace' 替换
        encoding = sys.stdout.encoding or 'utf-8'
        safe_text = safe_text.encode(encoding, errors='replace').decode(encoding)
        print(safe_text)


# ========== 开发调试开关 ==========
# 设置为 True 可在开发环境中模拟打包后的行为
SIMULATE_FROZEN = True
# ==================================

# 处理 PyInstaller 打包的路径
if getattr(sys, 'frozen', False):
    # 在 PyInstaller 打包的 exe 中
    # _MEIPASS 是 PyInstaller 解压临时文件的目录
    if hasattr(sys, '_MEIPASS'):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(sys.executable).parent
elif SIMULATE_FROZEN:
    # 模拟打包环境：使用项目根目录（与开发环境相同的路径）
    base_path = Path(__file__).parent.parent
else:
    # 在开发环境中
    base_path = Path(__file__).parent.parent

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(base_path))

# ========== FULL 运行时模式检测 ==========
# 如果应用根目录存在 runtime/ 目录，优先使用内置的完整运行时
# 用户只需将 runtime 包解压到应用根目录即可启用 FULL 模式
_runtime_dir = base_path.parent / "runtime" if getattr(sys, 'frozen', False) else base_path / "runtime"
if not _runtime_dir.exists() and getattr(sys, 'frozen', False):
    _runtime_dir = Path(sys.executable).parent / "runtime"

if _runtime_dir.exists():
    safe_print(f"[启动] 检测到 FULL 运行时: {_runtime_dir}")

    _webview2_fixed = _runtime_dir / "webview2"
    _webview2_valid = False
    if _webview2_fixed.exists():
        _webview2_required_files = [
            "msedge.dll",
            "msedge_elf.dll",
            "vk_swiftshader.dll",
        ]
        _missing_files = [f for f in _webview2_required_files if not (_webview2_fixed / f).exists()]
        if _missing_files:
            safe_print(f"[警告] WebView2 Fixed Version 文件不完整，缺少: {', '.join(_missing_files)}")
            safe_print("[警告] 将回退到系统 WebView2 Runtime（如果可用）")
        else:
            _webview2_valid = True
            os.environ['WEBVIEW2_BROWSER_EXECUTABLE_FOLDER'] = str(_webview2_fixed)
            safe_print(f"[启动] WebView2 Fixed Version: {_webview2_fixed}")

    _vcruntime_dir = _runtime_dir / "vcruntime"
    if _vcruntime_dir.exists():
        try:
            os.add_dll_directory(str(_vcruntime_dir))
        except OSError:
            os.environ['PATH'] = str(_vcruntime_dir) + os.pathsep + os.environ.get('PATH', '')
        safe_print(f"[启动] VC++ Runtime: {_vcruntime_dir}")

    os.environ['COMFYNEXUS_FULL_MODE'] = '1'
    os.environ['COMFYNEXUS_RUNTIME_DIR'] = str(_runtime_dir)
else:
    os.environ.pop('COMFYNEXUS_FULL_MODE', None)
    os.environ.pop('COMFYNEXUS_RUNTIME_DIR', None)
    _webview2_valid = False
# ==========================================

# 启动预检：检测所有外部依赖，缺失时弹窗引导安装
if sys.platform == "win32":
    from backend.src.utils.preflight import run_preflight
    run_preflight()

# 必须在 import webview 之前初始化 .NET 8 coreclr 运行时
# pywebview 的 import 链会触发 pythonnet 的 CLR 加载
if sys.platform == "win32":
    from backend.src.utils.dotnet_runtime import init_dotnet
    init_dotnet()

# 抑制 pywebview 框架日志（在 import webview 之前设置）
os.environ['PYWEBVIEW_LOG'] = 'WARNING'

import webview

if _webview2_valid:
    webview.settings['WEBVIEW2_RUNTIME_PATH'] = str(_webview2_fixed)
    safe_print(f"[启动] WebView2 Runtime Path (pywebview): {_webview2_fixed}")

# 根据 GPU 设置 patch edgechromium.py 注入 --disable-gpu 参数
# 必须在 import webview 之后，因为需要定位 edgechromium.py 文件路径
if sys.platform == "win32":
    from backend.src.utils.dotnet_runtime import _patch_gpu_args
    # 读取用户硬件加速设置，默认 True
    _hardware_acc = True
    try:
        from backend.src.core.settings_manager import SettingsManager
        _sm = SettingsManager()
        _cfg = _sm.load_config()
        _hardware_acc = _cfg.get('general', {}).get('hardwareAcceleration', True)
    except Exception:
        pass
    _patch_gpu_args(hardware_acceleration=_hardware_acc)

# 设置 Git 环境变量（在导入其他模块之前）
from backend.src.utils.git_manager import GitManager, git_manager

_git_manager = GitManager()

_migrated, _migration_msg = _git_manager.migrate_from_old_location()
if _migrated and "迁移成功" in _migration_msg:
    safe_print(f"[迁移] {_migration_msg}")

setup_git_environment = _git_manager.setup_environment

# 先导入 asyncio 等标准库（让它们正常初始化）
import asyncio

# 现在应用 subprocess monkey patch（在标准库导入完成后，业务模块导入之前）
import subprocess
import platform

_original_run = subprocess.run
_original_Popen = subprocess.Popen

def _patched_run(*args, **kwargs):
    if platform.system() == "Windows" and 'creationflags' not in kwargs:
        if hasattr(subprocess, 'CREATE_NO_WINDOW'):
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
    return _original_run(*args, **kwargs)

def _patched_Popen(*args, **kwargs):
    if platform.system() == "Windows" and 'creationflags' not in kwargs:
        if hasattr(subprocess, 'CREATE_NO_WINDOW'):
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
    return _original_Popen(*args, **kwargs)

subprocess.run = _patched_run
subprocess.Popen = _patched_Popen

from backend.src.bridge.api import Api
from backend.src.utils.http_server import create_server
from backend.src.utils.logger import setup_logger
from backend.src.core.settings_manager import SettingsManager


def cleanup_old_updater(logger):
    """
    清理旧版本更新器并迁移救援快照（一次性迁移）
    
    1. 删除旧的 Updater.exe
    2. 将旧的 _internal/backup/ 目录迁移到 exe 同级目录的 backup/
    """
    import shutil
    
    try:
        if getattr(sys, 'frozen', False):
            app_dir = Path(sys.executable).parent
            internal_dir = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else app_dir / '_internal'
        else:
            app_dir = Path(__file__).parent.parent
            internal_dir = app_dir
        
        old_updater = app_dir / 'Updater.exe'
        
        logger.info(f"[迁移] 检查目录: app_dir={app_dir}")
        logger.info(f"[迁移] 检查旧更新器: {old_updater}, 存在={old_updater.exists()}")
        
        if old_updater.exists():
            deleted = False
            for attempt in range(3):
                try:
                    old_updater.unlink()
                    logger.info(f"[迁移] 已删除旧版本更新器: {old_updater}")
                    deleted = True
                    break
                except PermissionError as e:
                    if attempt < 2:
                        logger.info(f"[迁移] 删除失败(权限)，等待重试... ({attempt + 1}/3)")
                        import time
                        time.sleep(1)
                    else:
                        logger.warning(f"[迁移] 删除旧版本更新器失败(权限): {e}")
                        logger.warning(f"[迁移] 请手动删除: {old_updater}")
                except Exception as e:
                    logger.warning(f"[迁移] 删除旧版本更新器失败: {e}")
                    break
        
        old_backup_dir = internal_dir / 'backup'
        new_backup_dir = app_dir / 'backup'
        
        logger.info(f"[迁移] 检查救援快照: {old_backup_dir}, 存在={old_backup_dir.exists()}")
        
        if old_backup_dir.exists() and old_backup_dir.is_dir():
            if old_backup_dir != new_backup_dir:
                try:
                    if new_backup_dir.exists():
                        for item in old_backup_dir.iterdir():
                            dest = new_backup_dir / item.name
                            if item.is_dir():
                                shutil.copytree(item, dest, dirs_exist_ok=True)
                            else:
                                shutil.copy2(item, dest)
                        logger.info(f"[迁移] 已合并救援快照: {old_backup_dir} -> {new_backup_dir}")
                    else:
                        shutil.move(str(old_backup_dir), str(new_backup_dir))
                        logger.info(f"[迁移] 已迁移救援快照: {old_backup_dir} -> {new_backup_dir}")
                except Exception as e:
                    logger.warning(f"[迁移] 迁移救援快照失败: {e}")
    except Exception as e:
        logger.warning(f"[迁移] 检查旧版本文件失败: {e}")


def migrate_from_internal(logger):
    """
    从 _internal 目录迁移数据到 exe 同级目录（一次性迁移）
    
    迁移 cache、data、logs、lora_data、temp 等目录
    以及 backend/config 下的配置文件
    """
    try:
        if not getattr(sys, 'frozen', False):
            return
        
        app_dir = Path(sys.executable).parent
        internal_dir = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else app_dir / '_internal'
        
        migration_marker = app_dir / ".migration_completed"
        if migration_marker.exists():
            return
        
        migrated = False
        import shutil
        
        def is_empty_dir(path: Path) -> bool:
            if not path.exists():
                return True
            if not path.is_dir():
                return False
            return not any(path.iterdir())
        
        dirs_to_migrate = ['cache', 'data', 'logs', 'lora_data', 'temp']
        
        for dir_name in dirs_to_migrate:
            old_path = internal_dir / dir_name
            new_path = app_dir / dir_name
            
            if old_path.exists() and old_path.is_dir() and not is_empty_dir(old_path):
                if is_empty_dir(new_path):
                    try:
                        if new_path.exists():
                            new_path.rmdir()
                        shutil.move(str(old_path), str(new_path))
                        logger.info(f"[迁移] 已迁移 {dir_name}")
                        migrated = True
                    except Exception as e:
                        logger.warning(f"[迁移] 迁移 {dir_name} 失败: {e}")
                else:
                    try:
                        for item in old_path.iterdir():
                            dest = new_path / item.name
                            if not dest.exists():
                                shutil.move(str(item), str(dest))
                        logger.info(f"[迁移] 已合并 {dir_name}")
                        migrated = True
                    except Exception as e:
                        logger.warning(f"[迁移] 合并 {dir_name} 失败: {e}")
        
        old_config_dir = internal_dir / "backend" / "config"
        new_config_dir = app_dir / "config"
        
        if old_config_dir.exists() and old_config_dir.is_dir():
            config_files = ['settings.json', 'default_config.json', 'lora_config.json', 
                           'environments.json', 'preset_index.json']
            config_dirs = ['plugins', 'presets', 'backups']
            
            for file_name in config_files:
                old_file = old_config_dir / file_name
                new_file = new_config_dir / file_name
                
                if old_file.exists() and not new_file.exists():
                    try:
                        new_config_dir.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(str(old_file), str(new_file))
                        logger.info(f"[迁移] 已迁移配置文件: {file_name}")
                        migrated = True
                    except Exception as e:
                        logger.warning(f"[迁移] 迁移 {file_name} 失败: {e}")
            
            for dir_name in config_dirs:
                old_subdir = old_config_dir / dir_name
                new_subdir = new_config_dir / dir_name
                
                if old_subdir.exists() and old_subdir.is_dir() and not is_empty_dir(old_subdir):
                    if is_empty_dir(new_subdir):
                        try:
                            if new_subdir.exists():
                                new_subdir.rmdir()
                            shutil.copytree(str(old_subdir), str(new_subdir))
                            logger.info(f"[迁移] 已迁移配置目录: {dir_name}")
                            migrated = True
                        except Exception as e:
                            logger.warning(f"[迁移] 迁移 {dir_name} 失败: {e}")
                    else:
                        try:
                            for item in old_subdir.iterdir():
                                dest = new_subdir / item.name
                                if not dest.exists():
                                    if item.is_dir():
                                        shutil.copytree(str(item), str(dest))
                                    else:
                                        shutil.copy2(str(item), str(dest))
                            logger.info(f"[迁移] 已合并配置目录: {dir_name}")
                            migrated = True
                        except Exception as e:
                            logger.warning(f"[迁移] 合并 {dir_name} 失败: {e}")
        
        if migrated:
            migration_marker.write_text("completed", encoding='utf-8')
            logger.info("[迁移] 数据迁移完成")
    
    except Exception as e:
        logger.warning(f"[迁移] 迁移过程出错: {e}")


def main():
    instance_manager = None
    
    if sys.platform == "win32":
        from backend.src.utils.single_instance import ensure_single_instance
        
        is_first, instance_manager = ensure_single_instance("ComfyNexus")
        
        if not is_first:
            safe_print("=" * 60)
            safe_print("[警告] ComfyNexus 已在运行中")
            safe_print("已激活已存在的窗口，当前实例将退出")
            safe_print("=" * 60)
            return
        
        safe_print("[启动] 单例检查通过，开始启动应用...")
    
    logger = setup_logger(
        name="ComfyNexus",
        log_dir=None,
        console=True,
        level="INFO"
    )
    
    migrate_from_internal(logger)
    cleanup_old_updater(logger)
    
    _bootstrap_completed = os.environ.get('COMFYNEXUS_BOOTSTRAP_COMPLETED') == '1'
    if not _bootstrap_completed:
        git_status = _git_manager.check_availability()
        if not git_status.available:
            logger.info(f"Git 不可用: {git_status.message}")
            logger.info("显示 Git 配置引导窗口...")
            
            from backend.src.ui.bootstrap_window import show_bootstrap_window
            
            bootstrap_result = show_bootstrap_window(_git_manager)
            if not bootstrap_result:
                logger.warning("用户取消了 Git 配置，应用将退出")
                safe_print("[取消] 用户取消了 Git 配置")
                return
            
            git_status = _git_manager.check_availability()
            if not git_status.available:
                logger.error("Git 配置失败，应用将退出")
                safe_print("[错误] Git 配置失败")
                return
            
            # 重启进程，获取干净的 pywebview 全局状态
            # pywebview 的 windows 列表是模块级全局变量，不支持在同一个进程
            # 里销毁一个窗口后再创建另一个窗口并调用 start()
            logger.info("[Bootstrap] Git 配置完成，重启进程以启动主应用...")
            safe_print("[Bootstrap] Git 配置完成，正在重启应用...")
            
            # 必须在启动新进程前释放单例锁
            # 否则新进程的 ensure_single_instance() 会检测到 Mutex 已存在而退出
            if instance_manager:
                instance_manager.release()
                instance_manager = None
                logger.info("[Bootstrap] 已释放单例锁")
            
            import subprocess as _bootstrap_sp
            cmd = [sys.executable]
            if not getattr(sys, 'frozen', False):
                cmd.append(__file__)
            os.environ['COMFYNEXUS_BOOTSTRAP_COMPLETED'] = '1'
            flags = _bootstrap_sp.CREATE_NO_WINDOW if hasattr(_bootstrap_sp, 'CREATE_NO_WINDOW') else 0
            _bootstrap_sp.Popen(cmd, creationflags=flags)
            return
    else:
        safe_print("[启动] 检测到 Bootstrap 已完成，跳过 Git 引导")
    
    try:
        safe_print("📌 [Main] 调用 _git_manager.setup_environment()...")
        import time
        time.sleep(0.5)  # 稍微暂停，让你能看清日志
        
        _git_manager.setup_environment()
        
        safe_print("📌 [Main] setup_environment 执行完成")
        time.sleep(0.5)  # 稍微暂停，让你能看清日志
        
        logger.info(f"Git 已就绪：{_git_manager._git_version or 'unknown'}")
        safe_print(f"✅ [Main] Git 已就绪：{_git_manager._git_version or 'unknown'}")
    except Exception as e:
        import traceback
        safe_print(f"❌ [Main] setup_environment 异常：{e}")
        print("=" * 60)
        print("错误详情：")
        print(traceback.format_exc())
        print("=" * 60)
        safe_print("⚠️ 错误详情已输出，应用将退出...")
        time.sleep(3)
        raise
    
    # 读取配置并更新日志级别
    try:
        settings_manager = SettingsManager()
        settings_result = settings_manager.get_settings()
        
        # 获取日志级别配置
        settings_data = None
        if settings_result.get("success") and settings_result.get("settings"):
            settings_data = settings_result["settings"]
            log_level = settings_data.get("logging", {}).get("level", "INFO").upper()
            
            # 验证日志级别是否有效（支持自定义 DEV 级别）
            valid_levels = {"DEBUG", "DEV", "INFO", "WARNING", "ERROR"}
            if log_level in valid_levels:
                from backend.src.utils.logger import DEV_LEVEL
                level_value = {
                    "DEBUG": logging.DEBUG,
                    "DEV": DEV_LEVEL,
                    "INFO": logging.INFO,
                    "WARNING": logging.WARNING,
                    "ERROR": logging.ERROR
                }.get(log_level, logging.INFO)
                
                logger.setLevel(level_value)
                for handler in logger.handlers:
                    handler.setLevel(level_value)
                logger.info(f"日志级别已更新为: {log_level}")
            else:
                print(f"[警告] 无效的日志级别: {log_level}，使用默认级别 INFO")
        else:
            print(f"[警告] 配置读取失败: success={settings_result.get('success')}")
        
        logger.info("=" * 60)
        logger.info("ComfyNexus 应用启动")
        logger.info(f"日志级别: {logger.level}")
        
        # 记录 Git 环境配置
        git_exe = _git_manager.get_git_executable()
        logger.debug(f"Git 可执行文件: {git_exe}")
        if "MinGit" in git_exe or "mingit" in git_exe.lower():
            logger.debug("使用项目内置 MinGit")
        else:
            logger.debug("使用系统 Git")
        
        logger.info("=" * 60)
    except Exception as e:
        print(f"警告: 日志系统初始化失败: {e}")
        settings_data = None
        # 即使日志系统初始化失败，应用也应该继续运行
    
    # 启用 pywebview 下载功能（必须在 webview.start() 之前设置）
    webview.settings['ALLOW_DOWNLOADS'] = True
    
    # 安全模式检查：如果上次启动失败并标记了安全模式，GPU 禁用参数
    # 会在 _patch_gpu_args() 中通过修改 pywebview 源码注入
    from backend.src.ui.webview2_diagnostic import is_safe_mode, set_safe_mode
    if is_safe_mode():
        safe_print("[启动] 检测到安全模式标记，将禁用 GPU 加速")
        logger.info("安全模式已启用，GPU 禁用参数已通过源码 patch 注入")
    
    # 配置 WebView2 用户数据文件夹（用于保存下载路径等偏好设置）
    # 使用 %LOCALAPPDATA%\ComfyNexus\webview2 避免非 ASCII 路径导致的问题
    # （如桌面路径含中文时 WebView2 初始化异常）
    # %LOCALAPPDATA% 不需要管理员权限，不会被磁盘清理工具删除
    local_app_data = os.environ.get('LOCALAPPDATA')
    if local_app_data:
        user_data_dir = Path(local_app_data) / 'ComfyNexus' / 'webview2'
    else:
        user_data_dir = base_path / 'data' / 'webview2'
    user_data_dir.mkdir(parents=True, exist_ok=True)
    os.environ['WEBVIEW2_USER_DATA_FOLDER'] = str(user_data_dir)
    
    logger.info(f"WebView2 用户数据目录: {user_data_dir}")
    safe_print(f"[数据] WebView2 数据目录: {user_data_dir}")
    
    # 获取前端构建目录
    dist_dir = base_path / "dist"
    index_html = dist_dir / "index.html"
    
    safe_print("=" * 60)
    safe_print("[启动] ComfyNexus 启动中...")
    safe_print("=" * 60)
    safe_print(f"[调试] 调试信息:")
    safe_print(f"   sys.frozen: {getattr(sys, 'frozen', False)}")
    safe_print(f"   SIMULATE_FROZEN: {SIMULATE_FROZEN}")
    safe_print(f"   运行模式: {'生产环境模拟' if SIMULATE_FROZEN and not getattr(sys, 'frozen', False) else ('生产环境' if getattr(sys, 'frozen', False) else '开发环境')}")
    safe_print(f"   sys._MEIPASS: {getattr(sys, '_MEIPASS', 'N/A')}")
    safe_print(f"   base_path: {base_path}")
    safe_print(f"   dist_dir: {dist_dir}")
    safe_print(f"   当前工作目录: {os.getcwd()}")
    safe_print(f"   index.html 存在: {index_html.exists()}")
    
    if not index_html.exists():
        safe_print("\n[错误] 前端构建文件不存在!")
        safe_print(f"   预期位置: {index_html}")
        
        # 尝试列出 base_path 的内容
        safe_print(f"\n[目录] base_path 目录内容:")
        try:
            for item in base_path.iterdir():
                safe_print(f"   - {item.name}")
        except Exception as e:
            safe_print(f"   无法列出目录: {e}")
        
        # 尝试列出 dist_dir 的内容
        if dist_dir.exists():
            safe_print(f"\n[目录] dist_dir 目录内容:")
            try:
                for item in dist_dir.iterdir():
                    safe_print(f"   - {item.name}")
            except Exception as e:
                safe_print(f"   无法列出目录: {e}")
        
        safe_print("[错误] 前端文件缺失，应用无法启动，3秒后退出...")
        time.sleep(3)
        return
    
    # 创建并启动自定义HTTP服务器（自动查找可用端口）
    http_server = create_server(dist_dir, port=None)
    http_server.start()
    
    # 轮询确认服务器就绪
    # 使用 socket 直连检测端口，避免 urllib 走系统代理导致超时
    logger.info("[轮询] 等待 HTTP 服务器就绪...")
    import socket
    _server_ready = False
    for i in range(30):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                s.connect(('127.0.0.1', http_server.port))
                _server_ready = True
                logger.info(f"[轮询] 第 {i+1} 次尝试成功，服务器端口可达")
                break
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            logger.info(f"[轮询] 第 {i+1} 次: {type(e).__name__}: {e}")
            time.sleep(0.3)
    
    if not _server_ready:
        if http_server.server_thread and not http_server.server_thread.is_alive():
            _srv_err = getattr(http_server, '_start_error', '未知')
            logger.error(f"[轮询] HTTP 服务器线程已死亡，错误: {_srv_err}")
        else:
            logger.error("[轮询] HTTP 服务器启动超时（9秒）")
        safe_print("[错误] HTTP 服务器启动失败，3秒后退出...")
        time.sleep(3)
        return
    
    safe_print(f"\n[成功] 服务器启动成功")
    safe_print(f"[目录] 前端目录: {dist_dir}")
    safe_print(f"[文件] 入口文件: {index_html}")
    safe_print(f"[地址] 服务器地址: {http_server.get_url()}")
    safe_print(f"[端口] 使用端口: {http_server.port} (自动分配)")
    safe_print("=" * 60)
    logger.info("[主窗口] HTTP 服务器就绪，开始创建窗口...")
    
    # 创建 API 实例
    api = Api()
    
    # 启动后台插件数据获取任务（用户无感知）
    try:
        from backend.src.core.marketplace.background_fetcher import BackgroundPluginFetcher
        
        # 获取插件市场控制器实例（使用私有属性）
        marketplace_controller = api._marketplace_controller
        
        # 创建并启动后台获取服务
        background_fetcher = BackgroundPluginFetcher(marketplace_controller)
        background_fetcher.start()
        
        logger.info("后台插件数据获取服务已启动")
        logger.info(f"后台获取日志文件: {background_fetcher.log_file}")
        safe_print(f"[记录] 后台获取日志: {background_fetcher.log_file}")
    except Exception as e:
        logger.warning(f"启动后台插件数据获取服务失败: {e}")
        # 不影响应用启动，继续运行
    
    # 从已读取的配置中解析窗口大小（避免重复读取配置文件）
    default_width, default_height = 1680, 1080
    if settings_data:
        logger.info(f"[窗口大小] settings_data 内容: {settings_data}")
        appearance_config = settings_data.get("appearance", {})
        logger.info(f"[窗口大小] appearance 配置: {appearance_config}")
        window_size = appearance_config.get("windowSize", "1680x1080")
        logger.info(f"[窗口大小] 读取到的 windowSize: {window_size}")
        try:
            width_str, height_str = window_size.split("x")
            default_width = int(width_str)
            default_height = int(height_str)
            safe_print(f"[尺寸] 窗口大小: {default_width}x{default_height} (从配置文件读取)")
        except (ValueError, AttributeError) as e:
            safe_print(f"[警告]  解析窗口大小失败，使用默认值: {default_width}x{default_height}")
            safe_print(f"   错误详情: {e}")
    else:
        safe_print(f"[警告]  读取配置失败，使用默认窗口大小: {default_width}x{default_height}")
    
    # 获取主显示器尺寸并计算居中位置
    try:
        import ctypes
        user32 = ctypes.windll.user32
        
        # 设置 DPI 感知，获取真实的物理分辨率
        dpi_aware_set = False
        system_dpi = 96  # 默认 DPI
        try:
            # 尝试设置进程 DPI 感知（Windows 10 1703+）
            shcore = ctypes.windll.shcore
            # PROCESS_SYSTEM_DPI_AWARE = 1 (系统 DPI 感知，兼容 pywebview 拖动)
            # PROCESS_PER_MONITOR_DPI_AWARE = 2 (每显示器 DPI 感知，会导致 pywebview 拖动时鼠标乱跑)
            shcore.SetProcessDpiAwareness(1)
            dpi_aware_set = True
            logger.debug("DPI 感知已设置 (SetProcessDpiAwareness - SYSTEM_DPI_AWARE)")
            
            # 获取系统 DPI 缩放因子
            hdc = user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
            user32.ReleaseDC(0, hdc)
            if dpi > 0:
                system_dpi = dpi
            logger.debug(f"系统 DPI: {system_dpi} (缩放比例: {system_dpi / 96:.2f})")
        except Exception as e1:
            try:
                # 降级方案：使用旧的 API（Windows Vista+）
                user32.SetProcessDPIAware()
                dpi_aware_set = True
                logger.debug("DPI 感知已设置 (SetProcessDPIAware)")
                
                # 尝试获取 DPI
                hdc = user32.GetDC(0)
                dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
                user32.ReleaseDC(0, hdc)
                if dpi > 0:
                    system_dpi = dpi
                logger.debug(f"系统 DPI: {system_dpi} (缩放比例: {system_dpi / 96:.2f})")
            except Exception as e2:
                # 两种 DPI 感知方法都失败，使用 DESKTOPHORZRES 推导真实缩放比
                logger.debug(f"[警告]  DPI 感知设置失败: {e1}, {e2}")
                try:
                    hdc = user32.GetDC(0)
                    physical_width = ctypes.windll.gdi32.GetDeviceCaps(hdc, 118)
                    user32.ReleaseDC(0, hdc)
                    virtual_width = user32.GetSystemMetrics(0)
                    if virtual_width > 0 and physical_width > 0:
                        fallback_scale = physical_width / virtual_width
                        if fallback_scale > 0.9 and fallback_scale < 5.0:
                            system_dpi = int(96 * fallback_scale)
                            dpi_aware_set = False
                            logger.debug(f"[DPI fallback] DESKTOPHORZRES 推导: physical={physical_width}, virtual={virtual_width}, scale={fallback_scale:.2f}, dpi={system_dpi}")
                        else:
                            logger.debug(f"[DPI fallback] 推导失败，scale={fallback_scale:.2f} 超出合理范围")
                except Exception as e3:
                    logger.debug(f"[DPI fallback] DESKTOPHORZRES 检测失败: {e3}")
        
        # 获取屏幕尺寸（物理像素）
        screen_width = user32.GetSystemMetrics(0)  # SM_CXSCREEN
        screen_height = user32.GetSystemMetrics(1)  # SM_CYSCREEN
        
        # 计算 DPI 缩放因子
        dpi_scale = system_dpi / 96.0
        
        logger.debug(f"屏幕尺寸（物理像素）: {screen_width}x{screen_height} (DPI感知: {dpi_aware_set})")
        logger.debug(f"DPI 缩放因子: {dpi_scale}")
        logger.debug(f"配置的窗口尺寸: {default_width}x{default_height}")
        
        api.set_dpi_scale(dpi_scale)
        
        # 确保窗口不会超出屏幕范围（留出边距）
        max_width = round(screen_width * 0.95)  # 最大宽度为屏幕的 95%
        max_height = round(screen_height * 0.95)  # 最大高度为屏幕的 95%
        
        # 如果窗口尺寸超出屏幕，自动调整
        adjusted_width = min(default_width, max_width)
        adjusted_height = min(default_height, max_height)
        
        if adjusted_width != default_width or adjusted_height != default_height:
            safe_print(f"[警告]  窗口尺寸超出屏幕范围，已自动调整:")
            safe_print(f"   原始尺寸: {default_width}x{default_height}")
            safe_print(f"   调整后: {adjusted_width}x{adjusted_height}")
            safe_print(f"   屏幕尺寸: {screen_width}x{screen_height}")
            logger.info(f"窗口尺寸已调整: {default_width}x{default_height} -> {adjusted_width}x{adjusted_height}")
            default_width = adjusted_width
            default_height = adjusted_height
        
        # 计算居中位置（使用物理像素）
        x = max(0, (screen_width - default_width) // 2)
        y = max(0, (screen_height - default_height) // 2)
        
        # 注意：pywebview 在 DPI 感知模式下可能使用逻辑像素
        # 需要将物理像素转换为逻辑像素
        # 物理像素 = 逻辑像素 * DPI 缩放因子
        # 逻辑像素 = 物理像素 / DPI 缩放因子
        logical_x = round(x / dpi_scale)
        logical_y = round(y / dpi_scale)
        logical_width = round(default_width / dpi_scale)
        logical_height = round(default_height / dpi_scale)
        
        # 详细的位置计算日志
        logger.debug(f"窗口位置计算:")
        logger.debug(f"  - 屏幕尺寸（物理）: {screen_width}x{screen_height}")
        logger.debug(f"  - 窗口尺寸（物理）: {default_width}x{default_height}")
        logger.debug(f"  - 物理位置: ({x}, {y})")
        logger.debug(f"  - 逻辑位置: ({logical_x}, {logical_y})")
        logger.debug(f"  - 逻辑尺寸: {logical_width}x{logical_height}")
        
        safe_print(f"[屏幕] 屏幕尺寸: {screen_width}x{screen_height} (DPI: {system_dpi}, 缩放: {dpi_scale:.2f}x)")
        safe_print(f"[位置] 窗口位置: ({logical_x}, {logical_y}) 逻辑像素 / ({x}, {y}) 物理像素")
        safe_print(f"[尺寸] 最终窗口尺寸: {logical_width}x{logical_height} 逻辑像素 / ({default_width}x{default_height} 物理像素)")
        logger.info(f"[窗口创建] 逻辑尺寸: {logical_width}x{logical_height}, 物理尺寸: {default_width}x{default_height}")
        
        # 如果位置是 (0, 0)，说明可能有问题
        if x == 0 and y == 0:
            logger.warning("[警告]  窗口位置计算结果为 (0, 0)，可能是窗口尺寸超出屏幕或 DPI 感知未生效")
    except Exception as e:
        # 降级方案：使用默认位置
        logical_x = 100
        logical_y = 100
        logical_width = default_width
        logical_height = default_height
        dpi_scale = 1.0
        api.set_dpi_scale(dpi_scale)
        safe_print(f"[警告]  获取屏幕尺寸失败，使用默认位置: ({logical_x}, {logical_y})")
        safe_print(f"   错误详情: {e}")
        logger.error(f"获取屏幕尺寸失败: {e}", exc_info=True)
    
    # 创建窗口（连接到自定义HTTP服务器）
    # 注意：pywebview 使用逻辑像素（在 DPI 感知模式下）
    window = webview.create_window(
        title='ComfyNexus',
        url=http_server.get_url(),  # 使用自定义服务器URL
        width=logical_width,
        height=logical_height,
        x=logical_x,  # 使用逻辑像素
        y=logical_y,  # 使用逻辑像素
        min_size=(1280, 720),
        resizable=True,
        frameless=True,
        easy_drag=False,
        background_color='#0f172a',
        js_api=api
    )
    
    # 设置窗口引用
    api.set_window(window)
    
    # 设置悬浮窗 API 引用和主窗口引用
    from backend.src.ui import floating_window_manager
    floating_window_manager.set_api(api)
    floating_window_manager.set_settings_manager(api._settings_manager)
    floating_window_manager.set_main_window(window)
    
    # 初始化系统托盘
    from backend.src.ui import system_tray_manager
    system_tray_manager.set_window(window)
    system_tray_manager.set_api(api)
    
    def tray_restore_window():
        """托盘恢复窗口回调"""
        try:
            window.show()
            logger.info("[TrayCallback] 窗口已从托盘恢复")
        except Exception as e:
            logger.error(f"[TrayCallback] 恢复窗口失败: {e}")
    
    def tray_exit_app():
        """托盘退出应用回调"""
        try:
            floating_window_manager.destroy()
            if hasattr(api, '_comfyui_process') and api._comfyui_process:
                if api._comfyui_process.is_running:
                    api._comfyui_process.stop()
            api._system_monitor_controller.close()
            system_tray_manager.destroy()
            window.destroy()
            logger.info("[TrayCallback] 应用已退出")
        except Exception as e:
            logger.error(f"[TrayCallback] 退出应用失败: {e}")
    
    def tray_start_comfyui():
        """托盘启动 ComfyUI 回调"""
        try:
            if hasattr(api, '_environment_controller') and api._environment_controller:
                env_id = api._environment_controller.manager.get_current_environment_id()
                if env_id:
                    try:
                        window.evaluate_js('window.refreshComfyUIStatus && window.refreshComfyUIStatus(true)')
                        logger.info("[TrayCallback] 已通知前端开始启动")
                    except Exception as e:
                        logger.warning(f"[TrayCallback] 通知前端失败: {e}")
                    
                    api.start_comfyui(env_id)
                    logger.info(f"[TrayCallback] ComfyUI 已启动, env_id={env_id}")
                else:
                    logger.warning("[TrayCallback] 未找到当前环境 ID，无法启动 ComfyUI")
            else:
                logger.warning("[TrayCallback] 环境控制器未初始化")
        except Exception as e:
            logger.error(f"[TrayCallback] 启动 ComfyUI 失败: {e}")
    
    def tray_stop_comfyui():
        """托盘停止 ComfyUI 回调"""
        try:
            if hasattr(api, '_comfyui_process') and api._comfyui_process:
                if api._comfyui_process.is_running:
                    api.stop_comfyui()
                    logger.info("[TrayCallback] ComfyUI 已停止")
                    try:
                        window.evaluate_js('window.refreshComfyUIStatus && window.refreshComfyUIStatus(false)')
                        logger.info("[TrayCallback] 已通知前端刷新状态")
                    except Exception as e:
                        logger.warning(f"[TrayCallback] 通知前端刷新状态失败: {e}")
        except Exception as e:
            logger.error(f"[TrayCallback] 停止 ComfyUI 失败: {e}")
    
    system_tray_manager.set_callbacks(
        on_restore=tray_restore_window,
        on_exit=tray_exit_app,
        on_start_comfyui=tray_start_comfyui,
        on_stop_comfyui=tray_stop_comfyui
    )
    
    system_tray_manager.show()
    logger.info("[Main] 托盘图标已创建")
    
    # 拦截 ALT+F4 等操作系统级别的窗口关闭事件
    # 使行为与前端 X 按钮一致：根据用户偏好最小化到托盘或退出
    _is_exiting = False
    
    def on_window_closing():
        nonlocal _is_exiting
        if _is_exiting or api._app_exit_requested:
            return True
        
        # 询问弹窗展示期间的重复关闭请求一律忽略，避免绕过询问直接退出。
        # 弹窗关闭时前端会调用 resetCloseDialogState() 复位该标志。
        if api._close_dialog_pending:
            return False
        
        try:
            result = api._settings_manager.get_settings()
            if result.get("success"):
                settings = result.get("settings", {})
                behavior = settings.get("closeBehavior", {})
                action = behavior.get("action")
                dont_ask = behavior.get("dontAskAgain", False)
                
                if dont_ask and action:
                    if action == "minimize":
                        if not system_tray_manager.is_running:
                            system_tray_manager.show()
                        window.hide()
                        return False
                    else:
                        _is_exiting = True
                        floating_window_manager.destroy()
                        if hasattr(api, '_comfyui_process') and api._comfyui_process:
                            if api._comfyui_process.is_running:
                                api._comfyui_process.stop()
                        api._system_monitor_controller.close()
                        system_tray_manager.destroy()
                        return True
            
            api._close_dialog_pending = True
            
            def _show_close_dialog():
                try:
                    window.evaluate_js('window.triggerCloseDialog && window.triggerCloseDialog()')
                except Exception as e:
                    # 弹窗触发失败时复位标志，避免后续 ALT+F4 被永久忽略
                    api._close_dialog_pending = False
                    logger.error(f"[Closing] 触发关闭确认弹窗失败: {e}")
            
            threading.Timer(0.1, _show_close_dialog).start()
            return False
        except Exception as e:
            logger.error(f"[Closing] 处理关闭事件失败: {e}")
            return True
    
    window.events.closing += on_window_closing
    
    # 设置悬浮窗上下文
    api._system_monitor_controller.set_floating_window_context(
        base_url=http_server.get_url(),
        screen_width=screen_width,
        screen_height=screen_height,
        dpi_scale=dpi_scale
    )
    
    # 延迟创建悬浮窗：仅当配置中 visible=true 时才在启动时创建
    # 避免 pywebview 的 transparent+hidden 冲突导致窗口意外显示
    floating_window_needs_show = api._system_monitor_controller._floating_window_visible
    
    safe_print(f"[API] 注册的 API: getAppInfo, closeApp, minimizeApp, maximizeApp")
    safe_print("=" * 60)
    
    # 关键设置：在调试模式下禁止自动打开开发者工具
    # 这样可以保留 F12 和右键检查，但不会自动弹出开发者工具
    webview.settings['OPEN_DEVTOOLS_IN_DEBUG'] = False
    
    # 定义窗口状态重置函数
    def reset_window_state():
        """
        重置窗口状态，防止 Windows 系统记忆导致自动最大化，并确保 frameless 样式正确应用
        
        问题1：在部分 Win11 系统中，窗口最大化后关闭应用，再次打开时窗口会以最大化状态初始化
        原因1：Windows 系统会记住应用窗口的最后状态（位置、大小、最大化状态）
        问题2：启动后偶尔出现系统标题栏
        原因2：ShowWindow(SW_RESTORE) 在还原最大化窗口时可能导致 Windows 重新应用默认窗口框架样式
               （包含 WS_CAPTION），且后续 SetWindowPos 缺少 SWP_FRAMECHANGED 标志，
               导致窗口框架未根据新样式重新计算
        解决：
          1. 仅在窗口确实被最大化时才调用 ShowWindow(SW_RESTORE)
          2. 修改样式后显式强制 frameless 样式（移除 WS_CAPTION 等标题栏样式，确保 WS_POPUP）
          3. 使用 SWP_FRAMECHANGED 强制 Windows 重新计算窗口框架
        
        注意：SetWindowPos 使用物理像素（在 DPI 感知模式下）
        """
        try:
            import ctypes
            import time
            
            user32 = ctypes.windll.user32
            
            # 重试机制：最多尝试 10 次，每次间隔 0.2 秒
            max_retries = 10
            retry_interval = 0.2
            hwnd = 0
            
            for attempt in range(max_retries):
                time.sleep(retry_interval)
                hwnd = user32.FindWindowW(None, "ComfyNexus")
                if hwnd and hwnd != 0:
                    break
            
            if hwnd and hwnd != 0:
                GWL_STYLE = -16
                WS_POPUP = 0x80000000
                WS_CAPTION = 0x00C00000
                WS_THICKFRAME = 0x00040000
                WS_SYSMENU = 0x00080000
                WS_MINIMIZEBOX = 0x00020000
                WS_MAXIMIZEBOX = 0x00010000
                SWP_FRAMECHANGED = 0x0020
                SWP_NOZORDER = 0x0004
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                SWP_SHOWWINDOW = 0x0040
                
                # 步骤1：检查窗口是否被 Windows 自动最大化
                is_maximized = bool(user32.IsZoomed(hwnd))
                logger.debug(f"[窗口重置] 窗口最大化状态: {is_maximized}")
                
                if is_maximized:
                    # 仅在窗口确实被最大化时才调用 SW_RESTORE
                    # SW_RESTORE = 9：还原窗口（如果窗口被最大化或最小化）
                    user32.ShowWindow(hwnd, 9)
                    time.sleep(0.05)
                
                # 步骤2：强制设置 frameless 窗口样式
                # 移除所有标题栏相关样式，确保 WS_POPUP 被设置，添加 WS_MINIMIZEBOX
                current_style = user32.GetWindowLongW(hwnd, GWL_STYLE)
                remove_mask = WS_CAPTION | WS_THICKFRAME | WS_SYSMENU | WS_MAXIMIZEBOX
                target_style = (current_style & ~remove_mask) | WS_POPUP | WS_MINIMIZEBOX
                user32.SetWindowLongW(hwnd, GWL_STYLE, target_style)
                logger.debug(f"[窗口重置] 窗口样式: 0x{current_style:08X} -> 0x{target_style:08X}")
                
                # 步骤3：强制刷新窗口框架（关键！缺少此步骤会导致标题栏残留）
                user32.SetWindowPos(
                    hwnd, None, 0, 0, 0, 0,
                    SWP_FRAMECHANGED | SWP_NOZORDER | SWP_NOMOVE | SWP_NOSIZE
                )
                
                # 步骤4：计算物理像素并设置窗口位置和大小
                phys_x = round(logical_x * dpi_scale)
                phys_y = round(logical_y * dpi_scale)
                phys_width = round(logical_width * dpi_scale)
                phys_height = round(logical_height * dpi_scale)
                
                user32.SetWindowPos(
                    hwnd, None, phys_x, phys_y, phys_width, phys_height,
                    SWP_NOZORDER | SWP_SHOWWINDOW
                )
                
                logger.debug(f"[窗口重置] 窗口状态已重置: ({phys_x}, {phys_y}), {phys_width}x{phys_height} (物理像素)")
                
                # 多显示器边界检查：确保窗口在当前显示器可视区域内
                try:
                    from backend.src.utils.window_bounds import check_and_fix_window_bounds
                    time.sleep(0.3)
                    check_and_fix_window_bounds(hwnd, dpi_scale)
                    logger.info("[窗口重置] 多显示器边界检查完成")
                except Exception as bounds_err:
                    logger.warning(f"[窗口重置] 边界检查失败: {bounds_err}")
                
                # 设置窗口圆角（Windows 11 DWM API）
                try:
                    dwmapi = ctypes.windll.dwmapi
                    
                    DWMWA_WINDOW_CORNER_PREFERENCE = 33
                    DWMWCP_ROUND = 2
                    
                    preference = ctypes.c_int(DWMWCP_ROUND)
                    dwmapi.DwmSetWindowAttribute(
                        hwnd,
                        DWMWA_WINDOW_CORNER_PREFERENCE,
                        ctypes.byref(preference),
                        ctypes.sizeof(preference)
                    )
                    logger.debug("[窗口圆角] 已设置窗口圆角 (DWMWCP_ROUND)")
                except Exception as corner_err:
                    logger.debug(f"[窗口圆角] 设置失败（可能是 Windows 10 或更早版本）: {corner_err}")
            else:
                logger.debug(f"[窗口重置] 无法获取窗口句柄（尝试了 {max_retries} 次），跳过状态重置")
        except Exception as e:
            logger.warning(f"[警告]  重置窗口状态失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())
    
    # 在后台线程中重置窗口状态（不阻塞主线程）
    import threading
    threading.Thread(target=reset_window_state, daemon=True).start()
    
    # 定义 webview 启动后的回调函数
    _health_check_thread = None
    
    def on_webview_ready():
        """webview 启动后创建悬浮窗（仅当配置开启时）并启动健康检查"""
        # 在 webview 完全初始化后应用 OpenFolderDialog monkey-patch
        # 必须在 webview.start() 之后调用，因为此时 forced_gui_ 和
        # WEBVIEW2_RUNTIME_PATH 才已正确设置，is_chromium 已被正确评估
        try:
            from backend.src.utils.dotnet_runtime import _apply_winforms_monkey_patches
            _apply_winforms_monkey_patches()
        except Exception as e:
            logger.warning(f"[on_webview_ready] OpenFolderDialog monkey-patch 失败: {e}")
        
        if floating_window_needs_show:
            import ctypes
            user32 = ctypes.windll.user32
            
            max_retries = 5
            main_hwnd = 0
            for attempt in range(max_retries):
                main_hwnd = user32.FindWindowW(None, "ComfyNexus")
                if main_hwnd and main_hwnd != 0:
                    break
                time.sleep(0.1)
            
            if main_hwnd and main_hwnd != 0:
                floating_window_manager.set_main_hwnd(main_hwnd)
                logger.debug(f"[on_webview_ready] 主窗口句柄: {main_hwnd}")
            else:
                logger.warning("[on_webview_ready] 无法获取主窗口句柄，悬浮窗将使用主显示器定位")
            
            floating_window_manager.create_window(
                base_url=http_server.get_url(),
                screen_width=screen_width,
                screen_height=screen_height,
                dpi_scale=dpi_scale,
                hidden=True
            )
        
        # 启动 WebView2 健康检查（非 daemon 线程，避免被主线程提前杀死）
        nonlocal _health_check_thread
        
        def health_check():
            """检查前端是否成功加载并调用了后端 API"""
            time.sleep(10)
            if api._frontend_heartbeat_received:
                logger.info("[健康检查] 前端已正常加载，WebView2 运行正常")
                if is_safe_mode():
                    set_safe_mode(False)
                    logger.info("[健康检查] 安全模式启动成功，已清除安全模式标记")
                return
            
            # 检查窗口是否已被用户手动关闭
            try:
                if window.native is not None and window.native.IsDisposed:
                    logger.info("[健康检查] 窗口已被关闭，跳过诊断")
                    return
            except Exception:
                pass
            
            logger.warning("[健康检查] 10秒内未收到前端心跳，WebView2 可能未正常初始化")
            
            try:
                window.destroy()
                time.sleep(0.5)
            except Exception:
                pass
            
            from backend.src.ui.webview2_diagnostic import show_webview2_diagnostic
            action = show_webview2_diagnostic("WebView2 控件初始化失败")
            
            if action == "safe_mode":
                set_safe_mode(True)
                logger.info("[健康检查] 用户选择安全模式，将重启应用")
                try:
                    if instance_manager:
                        instance_manager.release()
                        instance_manager = None
                    cmd = [sys.executable]
                    if not getattr(sys, 'frozen', False):
                        cmd.append(__file__)
                    subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0)
                except Exception as e2:
                    logger.error(f"[健康检查] 重启应用失败: {e2}")
        
            os._exit(0)
        
        _health_check_thread = threading.Thread(target=health_check, daemon=False)
        _health_check_thread.start()
    
    # 启动应用（不使用内置http_server）
    # private_mode=False: 启用数据持久化，localStorage 会保存到系统数据目录
    # Windows: %appdata%\pywebview | Linux: ~/.pywebview | macOS: ~/Library/Application Support/pywebview
    # debug=True: 保留调试功能（F12 和右键检查），但不会自动弹出开发者工具
    # gui='edgechromium': 强制使用 Edge WebView2 后端，避免依赖 pythonnet（winforms 后端）
    #                     pythonnet 在 PyInstaller 打包后可能出现 DLL 加载失败问题
    logger.info("[主窗口] 准备启动 WebView2 窗口...")
    safe_print("[主窗口] 正在启动 WebView2，请稍候...")
    webview.start(func=on_webview_ready, debug=True, private_mode=False, gui='edgechromium')
    logger.info("[主窗口] WebView2 窗口已关闭")
    
    # 等待健康检查线程完成（非 daemon，避免被提前杀死）
    if _health_check_thread is not None and _health_check_thread.is_alive():
        _health_check_thread.join(timeout=15)
    
    http_server.stop()
    
    # 安全清理：如果 closing handler 已处理则跳过
    if not _is_exiting:
        try:
            floating_window_manager.destroy()
        except Exception:
            pass
        try:
            if hasattr(api, '_comfyui_process') and api._comfyui_process:
                if api._comfyui_process.is_running:
                    api._comfyui_process.stop()
        except Exception:
            pass
        try:
            api._system_monitor_controller.close()
        except Exception:
            pass
        try:
            system_tray_manager.destroy()
        except Exception:
            pass
    
    if instance_manager:
        instance_manager.release()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        safe_print(f"\n[错误] 程序启动失败: {e}")
        import traceback
        traceback.print_exc()
        safe_print("\n[错误] 应用将在5秒后退出，请查看上方错误详情")
        time.sleep(5)
