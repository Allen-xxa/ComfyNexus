"""
ComfyNexus GUI 更新器

使用 webview 创建美观的更新界面
支持单例运行、完整备份、自升级
"""

import sys
import os
import re
import time
import zipfile
import shutil
import subprocess
import threading
import base64
import logging
import traceback
import tempfile

# 必须在 import webview 之前初始化 .NET 8 coreclr 运行时
if sys.platform == "win32":
    def _init_coreclr_for_updater():
        """更新器专用的 coreclr 初始化（独立打包，不依赖 backend 模块）"""
        import json
        import urllib.request
        import ssl
        import pythonnet
        if pythonnet._LOADED:
            return

        # 生成 runtimeconfig.json
        config = {
            "runtimeOptions": {
                "tfm": "net8.0",
                "framework": {
                    "name": "Microsoft.WindowsDesktop.App",
                    "version": "8.0.0"
                },
                "configProperties": {
                    "System.Reflection.Metadata.MetadataUpdater.IsSupported": False
                }
            }
        }
        config_dir = os.path.join(tempfile.gettempdir(), "ComfyNexus")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "updater.runtimeconfig.json")
        with open(config_path, "w") as f:
            json.dump(config, f)

        def _find_dotnet():
            # 0. FULL 模式：runtime/dotnet8/（exe 同级目录）
            if getattr(sys, 'frozen', False):
                runtime_dotnet = os.path.join(os.path.dirname(sys.executable), "runtime", "dotnet8")
                if os.path.isdir(runtime_dotnet) and os.path.isdir(os.path.join(runtime_dotnet, "shared")):
                    return runtime_dotnet
            # 1. 打包环境：同级目录
            if getattr(sys, 'frozen', False):
                bundled = os.path.join(sys._MEIPASS, "dotnet8")
                if os.path.isdir(bundled):
                    return bundled
            # 2. 系统安装
            system = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "dotnet")
            desktop_app = os.path.join(system, "shared", "Microsoft.WindowsDesktop.App")
            if os.path.isdir(desktop_app):
                for d in os.listdir(desktop_app):
                    if d.startswith("8."):
                        return system
            return None

        dotnet_root = _find_dotnet()

        # 找不到则自动下载安装
        if dotnet_root is None:
            print("[Updater] .NET 8 Desktop Runtime not found, auto-installing...")
            url = "https://aka.ms/dotnet/8.0/windowsdesktop-runtime-win-x64.exe"
            installer = os.path.join(config_dir, "dotnet8-runtime.exe")
            try:
                ctx = ssl.create_default_context()
                req = urllib.request.Request(url, headers={"User-Agent": "ComfyNexus/1.0"})
                with urllib.request.urlopen(req, context=ctx, timeout=300) as resp:
                    with open(installer, "wb") as f:
                        while True:
                            chunk = resp.read(256 * 1024)
                            if not chunk:
                                break
                            f.write(chunk)
                subprocess.run([installer, "/install", "/quiet", "/norestart"],
                               capture_output=True, timeout=300)
                print("[Updater] .NET 8 installed")
            except Exception as e:
                print(f"[Updater] Auto-install failed: {e}")
            finally:
                if os.path.exists(installer):
                    try:
                        os.unlink(installer)
                    except Exception:
                        pass
            dotnet_root = _find_dotnet()

        if dotnet_root is None:
            raise RuntimeError("Cannot find .NET 8 Runtime for updater")

        pythonnet.load("coreclr", runtime_config=config_path, dotnet_root=dotnet_root)

        # 预加载 .NET 8 下需要显式引用的程序集
        import clr
        for asm in ["Microsoft.Win32.SystemEvents", "System.Drawing.Primitives",
                     "System.Drawing.Common", "System.ComponentModel.Primitives"]:
            try:
                clr.AddReference(asm)
            except Exception:
                pass

        # 替换 WebView2 DLL
        try:
            import webview.util as wv_util
            _orig = wv_util.interop_dll_path
            if getattr(sys, 'frozen', False):
                nc_dir = os.path.join(sys._MEIPASS, "webview2_netcore")
            else:
                nc_dir = os.path.join(os.path.dirname(__file__), "..", "lib", "webview2_netcore")
            nc_dir = os.path.abspath(nc_dir)
            if os.path.isdir(nc_dir):
                def _patched(name):
                    if name in ("Microsoft.Web.WebView2.Core.dll", "Microsoft.Web.WebView2.WinForms.dll"):
                        p = os.path.join(nc_dir, name)
                        if os.path.exists(p):
                            return p
                    return _orig(name)
                wv_util.interop_dll_path = _patched
        except ImportError:
            pass

        # patch winforms OpenFolderDialog 兼容性
        try:
            import webview
            from pathlib import Path
            wf_path = Path(webview.__file__).parent / "platforms" / "winforms.py"
            if wf_path.exists():
                src = wf_path.read_text(encoding="utf-8")
                if "FileDialogNative+IFileDialog" in src and "PATCHED_FOR_DOTNET8" not in src:
                    marker = "class OpenFolderDialog:"
                    if marker in src:
                        idx = src.index(marker)
                        rest = src[idx:]
                        lines = rest.split('\n')
                        end = len(lines)
                        for i, ln in enumerate(lines[1:], 1):
                            s = ln.strip()
                            if ln and not ln[0].isspace() and s and not s.startswith('#'):
                                end = i
                                break
                        repl = "class OpenFolderDialog:  # PATCHED_FOR_DOTNET8\n    foldersFilter = 'Folders|\\\\n'\n    @classmethod\n    def show(cls, parent=None, initialDirectory=None, allow_multiple=False, title=None):\n        import System.Windows.Forms as WF\n        d = WF.FolderBrowserDialog()\n        if initialDirectory: d.SelectedPath = initialDirectory\n        if title: d.Description = title\n        r = d.ShowDialog()\n        return (d.SelectedPath,) if r == WF.DialogResult.OK else None\n\n"
                        wf_path.write_text(src[:idx] + repl + '\n'.join(lines[end:]), encoding="utf-8")
        except Exception:
            pass

    _init_coreclr_for_updater()

import webview
import ctypes
from pathlib import Path
from typing import Optional, List
from datetime import datetime

BACKUP_EXCLUDE_PATTERNS = [
    'temp',
    'cache',
    'runtime',
]

BACKUP_EXCLUDE_PREFIXES = [
    'backend/MinGit-',  # 旧位置（打包在 _internal 中）
    'tools/mingit',     # 新位置（exe 同级目录）
]

MUTEX_NAME = "Global\\ComfyNexus_Updater_SingleInstance"

EXPECTED_ROOT = "ComfyNexus"

# ========== 解压安全边界 ==========
# 更新包来自网络，必须当成不可信输入：
# - 成员名可能是 `../../x` / `C:/Windows/x` / `a\b`，直接与 target_dir 拼接会写到应用目录外
# - 成员声明的解压体积可能被伪造成极小（zip bomb）
MAX_SINGLE_FILE_BYTES = 1 * 1024 * 1024 * 1024    # 单文件 1 GiB
MAX_TOTAL_EXTRACT_BYTES = 8 * 1024 * 1024 * 1024  # 解压总量 8 GiB
MAX_ARCHIVE_MEMBERS = 50000                       # 成员数量上限

_DRIVE_PREFIX_RE = re.compile(r"^[A-Za-z]:")


def _member_relative_path(member: str, root_folder: Optional[str]) -> Optional[str]:
    """
    把 zip 成员名转换成相对 target_dir 的安全相对路径。

    Args:
        member: zip 内的成员名（可能带 `ComfyNexus/` 前缀）
        root_folder: 已识别出的包根目录名，命中则剥离

    Returns:
        Optional[str]: 以 `/` 分隔的相对路径；不安全时返回 None

    不安全判定与主程序 `_resolve_within` 一致：NUL、反斜杠、前导 `/`、盘符前缀、
    `.`/`..`/空段都拒绝（正常更新包里不会出现）。
    """
    if not member or "\x00" in member:
        return None
    if "\\" in member:
        return None
    if member.startswith("/") or _DRIVE_PREFIX_RE.match(member):
        return None

    relative = member
    if root_folder and member == root_folder:
        # 名为根目录但不是目录项的成员，剥离后会为空，直接跳过
        return None
    if root_folder and member.startswith(root_folder + "/"):
        relative = member[len(root_folder) + 1:]
    if not relative:
        return None

    segments = relative.split("/")
    if any(segment in ("", ".", "..") for segment in segments):
        return None
    return relative


def _safe_extract_target(target_dir: Path, relative: str) -> Optional[Path]:
    """
    把相对路径落到 target_dir 内部；解析（含软链接）后越界返回 None。
    """
    try:
        base = target_dir.resolve()
        candidate = (base / Path(*relative.split("/"))).resolve()
    except (OSError, ValueError):
        return None
    if not candidate.is_relative_to(base):
        return None
    return candidate


g_mutex_handle = None


def get_project_root() -> Path:
    """
    获取项目根目录（更新器专用）
    
    更新器是独立打包的单文件 exe，无法访问主应用的模块。
    此函数内联实现路径获取逻辑。
    
    Returns:
        Path: 项目根目录的绝对路径
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.parent.parent


def acquire_mutex() -> bool:
    """
    获取单例互斥锁
    
    Returns:
        True: 成功获取锁（首次实例）
        False: 获取失败（已有实例运行）
    """
    global g_mutex_handle
    
    try:
        kernel32 = ctypes.windll.kernel32
        
        ERROR_ALREADY_EXISTS = 183
        
        mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
        
        if mutex == 0:
            return False
        
        last_error = kernel32.GetLastError()
        
        if last_error == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(mutex)
            return False
        
        g_mutex_handle = mutex
        return True
        
    except Exception as e:
        print(f"创建互斥锁失败: {e}")
        return True


def release_mutex():
    """释放单例互斥锁"""
    global g_mutex_handle
    
    if g_mutex_handle:
        try:
            kernel32 = ctypes.windll.kernel32
            kernel32.ReleaseMutex(g_mutex_handle)
            kernel32.CloseHandle(g_mutex_handle)
            g_mutex_handle = None
        except Exception:
            pass


def setup_logger():
    """设置日志 - 使用系统临时目录避免文件占用问题"""
    try:
        log_dir = Path(tempfile.gettempdir()) / 'ComfyNexus_Updater_Logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        
        old_logs = sorted(log_dir.glob('updater_*.log'), key=lambda p: p.stat().st_mtime, reverse=True)
        for old_log in old_logs[10:]:
            try:
                old_log.unlink()
            except Exception:
                pass
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = log_dir / f'updater_{timestamp}.log'
        
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        logger = logging.getLogger('Updater')
        logger.info(f"日志文件: {log_file}")
        return logger
    except Exception as e:
        print(f"设置日志失败: {e}")
        return logging.getLogger('Updater')

logger = setup_logger()


def get_icon_base64() -> str:
    try:
        base_path = get_project_root()
        icon_path = base_path / 'dist' / 'app-icon.png'
        logger.debug(f"查找图标: {icon_path}")
        if icon_path.exists():
            with open(icon_path, 'rb') as f:
                data = base64.b64encode(f.read()).decode('utf-8')
                logger.debug(f"图标加载成功, 大小: {len(data)} bytes")
                return data
        else:
            logger.warning(f"图标文件不存在: {icon_path}")
    except Exception as e:
        logger.error(f"加载图标失败: {e}")
    return ""


def should_exclude(path: Path, target_dir: Path) -> bool:
    """
    检查路径是否应该被排除
    
    Args:
        path: 要检查的路径
        target_dir: 目标目录
        
    Returns:
        True: 应该排除
        False: 不应该排除
    """
    try:
        rel_path = path.relative_to(target_dir)
        rel_path_str = rel_path.as_posix()
        
        for pattern in BACKUP_EXCLUDE_PATTERNS:
            if rel_path_str == pattern or rel_path_str.startswith(pattern + '/'):
                return True
        
        for prefix in BACKUP_EXCLUDE_PREFIXES:
            parts = rel_path.parts
            if parts and parts[0].startswith(prefix.rstrip('-')):
                return True
            if rel_path_str.startswith(prefix):
                return True
        
        return False
    except Exception:
        return False


def count_files(directory: Path) -> int:
    """
    计算目录中的文件数量（排除指定模式）
    
    Args:
        directory: 目录路径
        
    Returns:
        文件数量
    """
    count = 0
    try:
        for item in directory.rglob('*'):
            if item.is_file() and not should_exclude(item, directory):
                count += 1
    except Exception:
        pass
    return count


class UpdaterAPI:
    """更新器 API，暴露给前端"""
    
    def __init__(self):
        self.window = None
        self._zip_path: str = ""
        self._target_dir: str = ""
        self._main_exe: str = ""
        self.backup_dir: Optional[Path] = None
        self.is_updating = False
        self.current_step = ""
        self.progress = 0
        self.progress_max = 0
        self.status = "ready"
        self.message = ""
        self.error = ""
        logger.debug("UpdaterAPI 初始化完成")
    
    def set_window(self, window):
        self.window = window
        logger.debug("窗口引用已设置")
    
    @property
    def zip_path(self) -> Path:
        return Path(self._zip_path) if self._zip_path else None
    
    @zip_path.setter
    def zip_path(self, value: Path):
        self._zip_path = str(value) if value else ""
    
    @property
    def target_dir(self) -> Path:
        return Path(self._target_dir) if self._target_dir else None
    
    @target_dir.setter
    def target_dir(self, value: Path):
        self._target_dir = str(value) if value else ""
    
    @property
    def main_exe(self) -> Path:
        return Path(self._main_exe) if self._main_exe else None
    
    @main_exe.setter
    def main_exe(self, value: Path):
        self._main_exe = str(value) if value else ""
    
    def get_status(self) -> dict:
        """获取当前状态"""
        result = {
            "status": self.status,
            "current_step": self.current_step,
            "progress": self.progress,
            "progress_max": self.progress_max,
            "message": self.message,
            "error": self.error,
        }
        return result
    
    def start_update(self) -> dict:
        """开始更新"""
        logger.info("收到开始更新请求")
        
        if self.is_updating:
            logger.warning("更新正在进行中")
            return {"success": False, "error": "更新正在进行中"}
        
        if not self._zip_path:
            logger.error("zip_path 为空")
            return {"success": False, "error": "更新包路径未设置"}
        
        zip_path = self.zip_path
        if not zip_path or not zip_path.exists():
            logger.error(f"更新包不存在: {zip_path}")
            return {"success": False, "error": f"更新包不存在"}
        
        target_dir = self.target_dir
        if not target_dir or not target_dir.exists():
            logger.error(f"目标目录不存在: {target_dir}")
            return {"success": False, "error": "目标目录不存在"}
        
        logger.info("开始更新线程")
        self.is_updating = True
        self.status = "updating"
        self.error = ""
        
        thread = threading.Thread(target=self._do_update, daemon=True)
        thread.start()
        logger.debug("更新线程已启动")
        
        return {"success": True}
    
    def close(self):
        """关闭窗口"""
        logger.info("请求关闭窗口")
        if self.window and not self.is_updating:
            self.window.destroy()
            logger.debug("窗口已销毁")
        else:
            logger.warning(f"无法关闭: window={self.window is not None}, is_updating={self.is_updating}")
    
    def _update_progress(self, step: str, message: str, progress: int = 0, progress_max: int = 0):
        """更新进度"""
        self.current_step = step
        self.message = message
        self.progress = progress
        self.progress_max = progress_max
        logger.debug(f"进度更新: step={step}, message={message}, progress={progress}/{progress_max}")
    
    def _do_update(self):
        """执行更新"""
        logger.info("=== 开始执行更新 ===")
        try:
            target_dir = self.target_dir
            zip_path = self.zip_path
            main_exe = self.main_exe
            
            total_files = count_files(target_dir)
            logger.info(f"目标目录文件数（排除后）: {total_files}")
            
            self._update_progress("waiting", "等待主程序退出...", 0, 5)
            for i in range(5, 0, -1):
                self._update_progress("waiting", f"等待主程序退出... ({i}秒)", 5 - i, 5)
                time.sleep(1)
            logger.debug("等待完成")
            
            logger.info("步骤 2/4: 备份整个目录")
            self._update_progress("backup", "备份应用目录...", 0, total_files)
            self.backup_dir = self._backup_directory(target_dir)
            logger.debug(f"备份完成: {self.backup_dir}")
            
            logger.info("步骤 3/4: 解压更新包")
            self._update_progress("extract", "解压更新包...", 0, 100)
            self._extract_update(zip_path, target_dir)
            logger.debug("解压完成")
            
            logger.info("步骤 4/4: 清理临时文件")
            self._update_progress("cleanup", "清理临时文件...", 0, 2)
            self._cleanup(zip_path)
            logger.debug("清理完成")
            
            version_file = target_dir / "_internal" / "comfy_nexus_version.py"
            if version_file.exists():
                content = version_file.read_text(encoding='utf-8')
                for line in content.splitlines():
                    if line.startswith('__version__'):
                        new_version = line.split('=')[1].strip().strip('"').strip("'")
                        logger.info(f"更新后版本: {new_version}")
                        break
            else:
                logger.error("版本文件不存在！更新可能失败")
                raise Exception("版本文件缺失，更新失败")
            
            self.status = "success"
            self.current_step = "done"
            self.message = "更新完成！"
            self.is_updating = False
            logger.info("=== 更新成功 ===")
            
        except Exception as e:
            logger.error(f"更新失败: {e}")
            logger.error(traceback.format_exc())
            self.status = "error"
            self.error = str(e)
            self.is_updating = False
            
            if self.backup_dir and self.backup_dir.exists():
                logger.info("正在回滚...")
                self._update_progress("rollback", "正在回滚...", 0, 100)
                self._restore_backup(self.backup_dir, self.target_dir)
                self.message = f"更新失败: {e}（已回滚）"
                logger.debug("回滚完成")
            else:
                self.message = f"更新失败: {e}"
    
    def _backup_directory(self, target_dir: Path) -> Optional[Path]:
        """
        备份整个目录到系统临时目录
        
        Args:
            target_dir: 要备份的目标目录
            
        Returns:
            备份目录路径，失败返回 None
        """
        try:
            timestamp = int(time.time())
            backup_base = Path(tempfile.gettempdir()) / 'ComfyNexus_Backups'
            backup_base.mkdir(parents=True, exist_ok=True)
            
            old_backups = sorted(backup_base.glob('backup_*'), key=lambda p: p.stat().st_mtime, reverse=True)
            for old_backup in old_backups[5:]:
                try:
                    shutil.rmtree(old_backup)
                    logger.debug(f"清理旧备份: {old_backup}")
                except Exception:
                    pass
            
            backup_dir = backup_base / f"backup_{timestamp}"
            backup_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"创建备份目录: {backup_dir}")
            
            copied_count = 0
            total_files = count_files(target_dir)
            
            for item in target_dir.iterdir():
                if should_exclude(item, target_dir):
                    logger.debug(f"排除: {item.name}")
                    continue
                
                dst = backup_dir / item.name
                
                try:
                    if item.is_dir():
                        for src_file in item.rglob('*'):
                            if src_file.is_file():
                                rel_path = src_file.relative_to(target_dir)
                                if should_exclude(src_file, target_dir):
                                    continue
                                
                                dst_file = backup_dir / rel_path
                                dst_file.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(src_file, dst_file)
                                copied_count += 1
                                
                                if copied_count % 100 == 0:
                                    self._update_progress("backup", f"备份中... ({copied_count}/{total_files})", copied_count, total_files)
                    else:
                        shutil.copy2(item, dst)
                        copied_count += 1
                        
                except PermissionError as pe:
                    logger.warning(f"权限错误，跳过: {item.name} - {pe}")
                    continue
                except Exception as e:
                    logger.warning(f"备份失败，跳过: {item.name} - {e}")
                    continue
            
            logger.info(f"备份完成: {copied_count} 个文件")
            self._update_progress("backup", f"备份完成 ({copied_count} 个文件)", total_files, total_files)
            
            return backup_dir
            
        except Exception as e:
            logger.error(f"备份失败: {e}")
            logger.error(traceback.format_exc())
            raise Exception(f"备份失败: {e}")
    
    def _extract_update(self, zip_path: Path, target_dir: Path):
        """解压更新包"""
        try:
            logger.debug(f"打开更新包: {zip_path}")
            with zipfile.ZipFile(zip_path, 'r') as zf:
                members = zf.namelist()
                logger.debug(f"压缩包内文件数: {len(members)}")
                
                root_folder = None
                if members:
                    root_candidates = {}
                    for m in members:
                        if m.endswith('/'):
                            continue
                        parts = m.split('/')
                        if len(parts) > 1:
                            candidate = parts[0]
                            root_candidates[candidate] = root_candidates.get(candidate, 0) + 1
                    
                    if root_candidates:
                        root_folder = max(root_candidates, key=root_candidates.get)
                        file_count = root_candidates[root_folder]
                        total_file_count = len([m for m in members if not m.endswith('/')])
                        
                        if root_folder == EXPECTED_ROOT:
                            logger.info(f"检测到根目录: {root_folder} (包含 {file_count}/{total_file_count} 个文件)")
                        else:
                            logger.warning(f"检测到意外的根目录: '{root_folder}'，尝试使用预期的根目录: '{EXPECTED_ROOT}'")
                            if EXPECTED_ROOT in root_candidates:
                                root_folder = EXPECTED_ROOT
                                file_count = root_candidates[root_folder]
                                logger.info(f"使用预期的根目录: {root_folder} (包含 {file_count}/{total_file_count} 个文件)")
                            else:
                                logger.error(f"预期的根目录 '{EXPECTED_ROOT}' 不存在于压缩包中")
                                raise Exception(f"更新包结构无效：未找到 '{EXPECTED_ROOT}' 目录")
                        
                        if file_count < total_file_count * 0.9:
                            logger.warning(f"根目录 '{root_folder}' 只包含 {file_count}/{total_file_count} 个文件，压缩包可能有结构问题")
                
                extracted_count = 0
                total_files = len(members)

                # ---- 第一遍：只做校验，不落盘 ----
                # 任何一个成员越界都直接中止，避免先写出部分文件再回滚
                infos = [info for info in zf.infolist() if not info.is_dir()]
                if len(infos) > MAX_ARCHIVE_MEMBERS:
                    raise Exception(
                        f"更新包成员数异常（{len(infos)} > {MAX_ARCHIVE_MEMBERS}），已中止解压"
                    )

                planned = []
                declared_total = 0
                for info in infos:
                    relative = _member_relative_path(info.filename, root_folder)
                    if relative is None:
                        logger.error(f"更新包含非法成员路径: {info.filename!r}")
                        raise Exception(f"更新包包含非法路径，已中止解压: {info.filename!r}")

                    target_path = _safe_extract_target(target_dir, relative)
                    if target_path is None:
                        logger.error(f"更新包成员解析后越界: {info.filename!r}")
                        raise Exception(f"更新包包含越界路径，已中止解压: {info.filename!r}")

                    declared_size = max(int(info.file_size or 0), 0)
                    if declared_size > MAX_SINGLE_FILE_BYTES:
                        raise Exception(
                            f"更新包单文件过大（{relative}），已中止解压"
                        )
                    declared_total += declared_size
                    if declared_total > MAX_TOTAL_EXTRACT_BYTES:
                        raise Exception("更新包解压总量超过上限，已中止解压")

                    planned.append((info, relative, target_path))

                # ---- 第二遍：校验通过后才真正写盘 ----
                written_total = 0
                for info, relative, target_path in planned:
                    target_path.parent.mkdir(parents=True, exist_ok=True)

                    try:
                        written = 0
                        with zf.open(info) as src, open(target_path, 'wb') as dst:
                            while True:
                                chunk = src.read(8192)
                                if not chunk:
                                    break
                                written += len(chunk)
                                written_total += len(chunk)
                                # 声明体积可以伪造，写入时再兜一次
                                if written > MAX_SINGLE_FILE_BYTES:
                                    raise Exception(
                                        f"更新包单文件解压超限: {relative}"
                                    )
                                if written_total > MAX_TOTAL_EXTRACT_BYTES:
                                    raise Exception("更新包解压总量超过上限，已中止解压")
                                dst.write(chunk)
                        extracted_count += 1
                    except PermissionError:
                        logger.warning(f"权限错误，跳过: {relative}")
                        continue
                    
                    if extracted_count % 50 == 0:
                        self._update_progress("extract", f"解压中... ({extracted_count}/{total_files})", extracted_count, total_files)
                
                logger.info(f"解压完成: {extracted_count} 个文件")
                self._update_progress("extract", f"解压完成 ({extracted_count} 个文件)", total_files, total_files)
                
        except zipfile.BadZipFile:
            logger.error("更新包文件损坏")
            raise Exception("更新包文件损坏")
        except Exception as e:
            logger.error(f"解压失败: {e}")
            logger.error(traceback.format_exc())
            raise Exception(f"解压失败: {e}")
    
    def _cleanup(self, zip_path: Path):
        """清理临时文件"""
        try:
            if zip_path and zip_path.exists():
                zip_path.unlink()
                logger.debug(f"删除更新包: {zip_path}")
            
            if self.backup_dir and self.backup_dir.exists():
                shutil.rmtree(self.backup_dir)
                logger.debug(f"删除备份目录: {self.backup_dir}")
                self.backup_dir = None
            
            self._update_progress("cleanup", "清理完成", 2, 2)
            
        except Exception as e:
            logger.warning(f"清理失败: {e}")
    
    def _restore_backup(self, backup_dir: Path, target_dir: Path):
        """从备份回滚"""
        try:
            logger.info(f"从备份恢复: {backup_dir} -> {target_dir}")
            
            for item in target_dir.iterdir():
                if should_exclude(item, target_dir):
                    continue
                
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                except Exception as e:
                    logger.warning(f"删除失败: {item} - {e}")
            
            for item in backup_dir.iterdir():
                dst = target_dir / item.name
                
                try:
                    if item.is_dir():
                        shutil.copytree(item, dst)
                    else:
                        shutil.copy2(item, dst)
                    logger.debug(f"恢复: {item.name}")
                except Exception as e:
                    logger.warning(f"恢复失败: {item.name} - {e}")
            
            logger.info("回滚完成")
            
        except Exception as e:
            logger.error(f"回滚失败: {e}")
            logger.error(traceback.format_exc())
    
    def launch_main_app(self):
        """启动主程序"""
        main_exe = self.main_exe
        logger.info(f"启动主程序：{main_exe}")
        if main_exe and main_exe.exists():
            subprocess.Popen([str(main_exe)])
            logger.debug("主程序已启动")
            
            import time
            logger.info("等待 2 秒后退出更新器...")
            time.sleep(2)
        else:
            logger.warning(f"主程序不存在：{main_exe}")
        
        if self.window:
            self.window.destroy()
    
    def get_window(self) -> dict:
        """
        获取窗口信息
        
        Returns:
            dict: 窗口位置信息
        """
        if self.window:
            return {
                "x": self.window.x,
                "y": self.window.y,
                "width": self.window.width,
                "height": self.window.height
            }
        return {"x": 0, "y": 0, "width": 480, "height": 600}
    
    def set_window_bounds(self, x: int, y: int, width: int, height: int) -> dict:
        """
        同时设置窗口的位置和大小，避免撕裂
        
        Args:
            x: X 坐标
            y: Y 坐标
            width: 宽度
            height: 高度
            
        Returns:
            dict: 操作结果
        """
        if self.window:
            width = max(350, width)
            height = max(400, height)
            
            self.window.move(int(x), int(y))
            self.window.resize(int(width), int(height))
            
        return {"success": True}


def get_html(icon_base64: str) -> str:
    """获取更新器 HTML"""
    icon_html = f'<img src="data:image/png;base64,{icon_base64}" alt="icon" style="width:100%;height:100%;object-fit:contain;">' if icon_base64 else '📦'
    
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ComfyNexus 更新器</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html, body {{ overflow: hidden; height: 100%; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e4e4e7;
            
            /* 卡片样式 - 直角 */
            background: rgba(30, 30, 46, 0.95);
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            border: 1px solid rgba(255, 255, 255, 0.1);
            
            position: relative;
            width: 100%;
            height: 100%;
            
            /* 内容布局 */
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 32px;
        }}
        .close-btn {{
            position: absolute;
            top: 12px;
            right: 12px;
            width: 28px;
            height: 28px;
            background: rgba(255, 255, 255, 0.1);
            border: none;
            border-radius: 6px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
            z-index: 10;
        }}
        .close-btn:hover {{
            background: rgba(239, 68, 68, 0.8);
        }}
        .close-btn svg {{
            width: 16px;
            height: 16px;
            color: white;
        }}
        .header {{ text-align: center; margin-bottom: 32px; }}
        .logo {{
            width: 64px; height: 64px;
            margin: 0 auto 16px;
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
            border-radius: 16px;
            display: flex; align-items: center; justify-content: center;
            font-size: 32px;
            box-shadow: 0 8px 16px rgba(99, 102, 241, 0.3);
            overflow: hidden;
        }}
        .title {{
            font-size: 24px; font-weight: 600; margin-bottom: 8px;
            background: linear-gradient(135deg, #fff 0%, #a5b4fc 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }}
        .subtitle {{ font-size: 14px; color: #71717a; }}
        .content {{ margin-bottom: 24px; }}
        .step-info {{ text-align: center; margin-bottom: 24px; }}
        .step-name {{ font-size: 16px; font-weight: 500; color: #a5b4fc; margin-bottom: 8px; }}
        .step-message {{ font-size: 14px; color: #a1a1aa; }}
        .progress-container {{ margin-bottom: 24px; }}
        .progress-bar {{ height: 8px; background: rgba(255, 255, 255, 0.1); border-radius: 4px; overflow: hidden; }}
        .progress-fill {{ height: 100%; background: linear-gradient(90deg, #6366f1 0%, #8b5cf6 100%); border-radius: 4px; transition: width 0.3s ease; }}
        .progress-text {{ text-align: center; font-size: 12px; color: #71717a; margin-top: 8px; }}
        .status-icon {{ width: 80px; height: 80px; margin: 0 auto 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 40px; }}
        .status-icon.loading {{ background: rgba(99, 102, 241, 0.2); animation: pulse 2s infinite; }}
        .status-icon.success {{ background: rgba(34, 197, 94, 0.2); }}
        .status-icon.error {{ background: rgba(239, 68, 68, 0.2); }}
        @keyframes pulse {{ 0%, 100% {{ transform: scale(1); opacity: 1; }} 50% {{ transform: scale(1.05); opacity: 0.8; }} }}
        .buttons {{ display: flex; gap: 12px; margin-top: 24px; }}
        .btn {{ padding: 12px 32px; border: none; border-radius: 8px; font-size: 14px; font-weight: 500; cursor: pointer; transition: all 0.2s ease; min-width: 100px; }}
        .btn-primary {{ background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: white; }}
        .btn-primary:hover {{ transform: translateY(-1px); box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4); }}
        .btn-primary:disabled {{ opacity: 0.5; cursor: not-allowed; transform: none; box-shadow: none; }}
        .btn-secondary {{ background: rgba(255, 255, 255, 0.1); color: #a1a1aa; }}
        .btn-secondary:hover {{ background: rgba(255, 255, 255, 0.15); color: #e4e4e7; }}
        .error-message {{ background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px; padding: 12px; margin-bottom: 16px; font-size: 13px; color: #fca5a5; text-align: center; }}
        
        /* 标题栏主容器 */
        .title-bar {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 48px;
            
            display: flex;
            justify-content: space-between;
            align-items: center;
            
            padding: 0 16px;
            box-sizing: border-box;
            z-index: 1000;
            
            -webkit-app-region: drag;
            user-select: none;
        }}
        
        /* 标题文本样式 */
        .title-text {{
            font-size: 14px;
            font-weight: 500;
            color: #e4e4e7;
        }}
        
        /* 按钮控制区：必须防劫持 */
        .window-controls {{
            -webkit-app-region: no-drag !important;
            display: flex;
            align-items: center;
        }}
        
        /* 关闭按钮基础样式 */
        #close-btn {{
            background: transparent;
            border: none;
            color: #a1a1aa;
            width: 32px;
            height: 32px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
        }}
        
        /* 关闭按钮的悬浮效果 */
        #close-btn:hover {{
            background-color: rgba(255, 60, 60, 0.8);
            color: white;
        }}
        
        /* 四角手柄基础样式与防劫持 */
        .resize-handle {{
            position: absolute;
            width: 15px;
            height: 15px;
            z-index: 9999;
            -webkit-app-region: no-drag !important;
        }}
        
        /* 定位与鼠标样式 */
        .resize-handle.nw {{ top: 0; left: 0; cursor: nwse-resize; }}
        .resize-handle.ne {{ top: 0; right: 0; cursor: nesw-resize; }}
        .resize-handle.sw {{ bottom: 0; left: 0; cursor: nesw-resize; }}
        .resize-handle.se {{ bottom: 0; right: 0; cursor: nwse-resize; }}
        
        /* body 内容下移，避免被标题栏遮挡 */
        body {{
            padding-top: 48px;
        }}
    </style>
</head>
<body>
    <div class="title-bar pywebview-drag-region">
        <div class="title-text">ComfyNexus 更新器</div>
        <div class="window-controls">
            <button id="close-btn">✕</button>
        </div>
    </div>
    
    <div class="resize-handle nw"></div>
    <div class="resize-handle ne"></div>
    <div class="resize-handle sw"></div>
    <div class="resize-handle se"></div>
    
    <div class="header">
            <div class="logo">{icon_html}</div>
            <h1 class="title">ComfyNexus 更新器</h1>
            <p class="subtitle" id="subtitle">准备更新...</p>
        </div>
        <div class="content" id="content">
            <div class="status-icon loading">📥</div>
            <div class="step-info">
                <div class="step-name">准备就绪</div>
                <div class="step-message">点击下方按钮开始更新</div>
            </div>
        </div>
        <div class="buttons" id="buttons">
            <button class="btn btn-primary" id="startBtn" disabled>开始更新</button>
            <button class="btn btn-secondary" id="cancelBtn">取消</button>
        </div>
    </div>
    
    <script>
        let statusCheckInterval = null;
        let api = null;
        
        console.log('[Updater] 脚本加载');
        
        document.addEventListener('DOMContentLoaded', function() {{
            console.log('[Updater] DOM 加载完成');
            document.getElementById('startBtn').addEventListener('click', startUpdate);
            document.getElementById('cancelBtn').addEventListener('click', closeWindow);
            document.getElementById('close-btn').addEventListener('click', closeWindow);
            setupResizeHandles();
            waitForAPI();
        }});
        
        function setupResizeHandles() {{
            const handles = document.querySelectorAll('.resize-handle');
            let isResizing = false;
            let isUpdating = false;
            let startMouseX, startMouseY;
            let startWinX, startWinY, startWidth, startHeight;
            let currentHandleType = '';

            handles.forEach(handle => {{
                handle.addEventListener('mousedown', async (e) => {{
                    if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.get_window) return;
                    
                    isResizing = true;
                    
                    if (handle.classList.contains('nw')) currentHandleType = 'nw';
                    if (handle.classList.contains('ne')) currentHandleType = 'ne';
                    if (handle.classList.contains('sw')) currentHandleType = 'sw';
                    if (handle.classList.contains('se')) currentHandleType = 'se';

                    startMouseX = e.screenX / (window.devicePixelRatio || 1);
                    startMouseY = e.screenY / (window.devicePixelRatio || 1);
                    
                    const win = await window.pywebview.api.get_window();
                    startWinX = win.x;
                    startWinY = win.y;
                    startWidth = win.width;
                    startHeight = win.height;
                    
                    e.preventDefault();
                    e.stopPropagation();
                }});
            }});

            document.addEventListener('mousemove', (e) => {{
                if (!isResizing || isUpdating) return;

                const dx = (e.screenX / (window.devicePixelRatio || 1)) - startMouseX;
                const dy = (e.screenY / (window.devicePixelRatio || 1)) - startMouseY;

                let newX = startWinX;
                let newY = startWinY;
                let newW = startWidth;
                let newH = startHeight;

                if (currentHandleType === 'se') {{
                    newW = startWidth + dx;
                    newH = startHeight + dy;
                }} else if (currentHandleType === 'sw') {{
                    newX = startWinX + dx;
                    newW = startWidth - dx;
                    newH = startHeight + dy;
                }} else if (currentHandleType === 'ne') {{
                    newY = startWinY + dy;
                    newW = startWidth + dx;
                    newH = startHeight - dy;
                }} else if (currentHandleType === 'nw') {{
                    newX = startWinX + dx;
                    newY = startWinY + dy;
                    newW = startWidth - dx;
                    newH = startHeight - dy;
                }}

                const MIN_WIDTH = 350;
                const MIN_HEIGHT = 400;

                if (newW < MIN_WIDTH) {{
                    newW = MIN_WIDTH;
                    if (currentHandleType.includes('w')) {{
                        newX = startWinX + (startWidth - MIN_WIDTH);
                    }}
                }}
                if (newH < MIN_HEIGHT) {{
                    newH = MIN_HEIGHT;
                    if (currentHandleType.includes('n')) {{
                        newY = startWinY + (startHeight - MIN_HEIGHT);
                    }}
                }}

                isUpdating = true;
                window.pywebview.api.set_window_bounds(newX, newY, newW, newH).then(() => {{
                    isUpdating = false;
                }});
            }});

            document.addEventListener('mouseup', () => {{
                isResizing = false;
                isUpdating = false;
            }});
        }}
        
        function waitForAPI() {{
            console.log('[Updater] 等待 API...');
            if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.start_update === 'function') {{
                api = window.pywebview.api;
                console.log('[Updater] API 已就绪, 方法:', Object.keys(api));
                document.getElementById('startBtn').disabled = false;
                return;
            }}
            setTimeout(waitForAPI, 100);
        }}
        
        async function checkStatus() {{
            if (!api) return;
            try {{
                const status = await api.get_status();
                console.log('[Updater] 状态:', status.status, status.current_step);
                updateUI(status);
            }} catch (e) {{
                console.error('[Updater] 获取状态失败:', e);
            }}
        }}
        
        function updateUI(status) {{
            const content = document.getElementById('content');
            const buttons = document.getElementById('buttons');
            const subtitle = document.getElementById('subtitle');
            
            const progressPercent = status.progress_max > 0 ? Math.round((status.progress / status.progress_max) * 100) : 0;
            
            switch (status.status) {{
                case 'ready':
                    subtitle.textContent = '准备开始更新';
                    content.innerHTML = '<div class="status-icon loading">📥</div><div class="step-info"><div class="step-name">准备就绪</div><div class="step-message">点击下方按钮开始更新</div></div>';
                    buttons.innerHTML = '<button class="btn btn-primary" onclick="startUpdate()">开始更新</button><button class="btn btn-secondary" onclick="closeWindow()">取消</button>';
                    break;
                    
                case 'updating':
                    subtitle.textContent = '正在更新...';
                    let stepIcon = '⚙️', stepName = status.current_step;
                    switch (status.current_step) {{
                        case 'waiting': stepIcon = '⏳'; stepName = '等待主程序退出'; break;
                        case 'backup': stepIcon = '💾'; stepName = '备份应用目录'; break;
                        case 'extract': stepIcon = '📦'; stepName = '解压更新包'; break;
                        case 'cleanup': stepIcon = '🧹'; stepName = '清理临时文件'; break;
                        case 'rollback': stepIcon = '↩️'; stepName = '正在回滚'; break;
                    }}
                    content.innerHTML = '<div class="status-icon loading">' + stepIcon + '</div><div class="step-info"><div class="step-name">' + stepName + '</div><div class="step-message">' + (status.message || '') + '</div></div><div class="progress-container"><div class="progress-bar"><div class="progress-fill" style="width: ' + progressPercent + '%"></div></div><div class="progress-text">' + progressPercent + '%</div></div>';
                    buttons.innerHTML = '<button class="btn btn-primary" disabled>更新中...</button>';
                    break;
                    
                case 'success':
                    subtitle.textContent = '更新完成';
                    content.innerHTML = '<div class="status-icon success">✅</div><div class="step-info"><div class="step-name">更新成功</div><div class="step-message">应用已更新到最新版本</div></div>';
                    buttons.innerHTML = '<button class="btn btn-primary" onclick="launchApp()">启动应用</button>';
                    if (statusCheckInterval) {{ clearInterval(statusCheckInterval); statusCheckInterval = null; }}
                    break;
                    
                case 'error':
                    subtitle.textContent = '更新失败';
                    content.innerHTML = '<div class="status-icon error">❌</div><div class="step-info"><div class="step-name">更新失败</div></div>' + (status.error ? '<div class="error-message">' + status.error + '</div>' : '');
                    buttons.innerHTML = '<button class="btn btn-primary" onclick="startUpdate()">重试</button><button class="btn btn-secondary" onclick="closeWindow()">关闭</button>';
                    if (statusCheckInterval) {{ clearInterval(statusCheckInterval); statusCheckInterval = null; }}
                    break;
            }}
        }}
        
        async function startUpdate() {{
            console.log('[Updater] 点击开始更新');
            if (!api) {{ console.error('[Updater] API 未就绪'); alert('API 未就绪，请稍后重试'); return; }}
            try {{
                console.log('[Updater] 调用 start_update');
                const result = await api.start_update();
                console.log('[Updater] start_update 结果:', result);
                if (result.success) {{
                    console.log('[Updater] 开始轮询状态');
                    statusCheckInterval = setInterval(checkStatus, 200);
                }} else {{
                    console.error('[Updater] 启动失败:', result.error);
                    alert('启动更新失败: ' + (result.error || '未知错误'));
                }}
            }} catch (e) {{
                console.error('[Updater] 异常:', e);
                alert('启动更新失败: ' + e.message);
            }}
        }}
        
        async function launchApp() {{
            console.log('[Updater] 启动应用');
            if (!api) return;
            try {{ await api.launch_main_app(); }} catch (e) {{ console.error('[Updater] 启动失败:', e); }}
        }}
        
        async function closeWindow() {{
            console.log('[Updater] 关闭窗口');
            if (!api) return;
            try {{ await api.close(); }} catch (e) {{ console.error('[Updater] 关闭失败:', e); }}
        }}
    </script>
</body>
</html>'''


def relocate_to_temp() -> bool:
    """
    将更新器重定位到临时目录运行（支持自升级）
    
    Returns:
        True: 已经是临时目录运行或重定位成功
        False: 需要退出（已启动新实例）
    """
    if not getattr(sys, 'frozen', False):
        return True
    
    current_exe = Path(sys.executable)
    
    temp_dir = Path(tempfile.gettempdir()) / 'ComfyNexus_Updater'
    temp_exe = temp_dir / 'Updater.exe'
    
    if current_exe == temp_exe:
        logger.info("已在临时目录运行")
        _cleanup_old_temp_updaters(temp_dir, temp_exe)
        return True
    
    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        _cleanup_old_temp_updaters(temp_dir, None)
        
        shutil.copy2(current_exe, temp_exe)
        logger.info(f"复制更新器到临时目录: {temp_exe}")
        
        cmd = [str(temp_exe)] + sys.argv[1:]
        logger.info(f"启动临时目录更新器: {' '.join(cmd)}")
        
        subprocess.Popen(cmd)
        
        return False
        
    except Exception as e:
        logger.error(f"重定位失败: {e}")
        return True


def _cleanup_old_temp_updaters(temp_dir: Path, current_exe: Optional[Path]):
    """
    清理旧的临时更新器文件
    
    Args:
        temp_dir: 临时目录
        current_exe: 当前运行的exe（不删除）
    """
    try:
        if not temp_dir.exists():
            return
        
        for item in temp_dir.iterdir():
            if item.is_file() and item.suffix == '.exe':
                if current_exe and item == current_exe:
                    continue
                try:
                    item.unlink()
                    logger.debug(f"清理旧临时文件: {item}")
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"清理临时目录失败: {e}")


def main():
    """更新器主函数"""
    logger.info("=" * 60)
    logger.info("ComfyNexus 更新器启动")
    logger.info("=" * 60)
    
    if not acquire_mutex():
        logger.error("已有更新器实例在运行，退出")
        time.sleep(2)
        sys.exit(1)
    
    logger.info("单例检查通过")
    
    if not relocate_to_temp():
        logger.info("已启动临时目录实例，退出当前实例")
        release_mutex()
        sys.exit(0)
    
    if len(sys.argv) < 4:
        logger.error("参数不足")
        logger.error(f"收到的参数: {sys.argv}")
        logger.error("用法: Updater.exe <zip_path> <target_dir> <main_exe>")
        
        icon_base64 = get_icon_base64()
        
        # 设置临时 WebView2 用户数据目录，避免与主应用冲突
        import tempfile
        error_webview2_dir = Path(tempfile.gettempdir()) / "ComfyNexus_updater_webview2"
        error_webview2_dir.mkdir(parents=True, exist_ok=True)
        os.environ['WEBVIEW2_USER_DATA_FOLDER'] = str(error_webview2_dir)
        
        error_html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>ComfyNexus 更新器</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html, body {{ overflow: hidden; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e4e4e7;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 20px;
            
            /* 卡片样式 - 直角 */
            background: rgba(30, 30, 46, 0.95);
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            border: 1px solid rgba(255, 255, 255, 0.1);
            
            position: relative;
            min-width: 350px;
            min-height: 280px;
        }}
        .close-btn {{
            position: absolute;
            top: 12px;
            right: 12px;
            width: 28px;
            height: 28px;
            background: rgba(255, 255, 255, 0.1);
            border: none;
            border-radius: 6px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
            z-index: 10;
        }}
        .close-btn:hover {{
            background: rgba(239, 68, 68, 0.8);
        }}
        .close-btn svg {{
            width: 16px;
            height: 16px;
            color: white;
        }}
        .container {{
            width: 100%;
            text-align: center;
        }}
        .logo {{
            width: 64px; height: 64px;
            margin: 0 auto 16px;
            background: rgba(239, 68, 68, 0.2);
            border-radius: 16px;
            display: flex; align-items: center; justify-content: center;
            font-size: 32px;
        }}
        .title {{ font-size: 20px; font-weight: 600; margin-bottom: 12px; }}
        .message {{ font-size: 14px; color: #a1a1aa; line-height: 1.6; }}
        
        /* 标题栏主容器 */
        .title-bar {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 48px;
            
            display: flex;
            justify-content: space-between;
            align-items: center;
            
            padding: 0 16px;
            box-sizing: border-box;
            z-index: 1000;
            
            -webkit-app-region: drag;
            user-select: none;
        }}
        
        .title-text {{
            font-size: 14px;
            font-weight: 500;
            color: #e4e4e7;
        }}
        
        .window-controls {{
            -webkit-app-region: no-drag !important;
            display: flex;
            align-items: center;
        }}
        
        #close-btn {{
            background: transparent;
            border: none;
            color: #a1a1aa;
            width: 32px;
            height: 32px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
        }}
        
        #close-btn:hover {{
            background-color: rgba(255, 60, 60, 0.8);
            color: white;
        }}
        
        body {{
            padding-top: 48px;
        }}
    </style>
</head>
<body>
    <div class="title-bar pywebview-drag-region">
        <div class="title-text">ComfyNexus 更新器</div>
        <div class="window-controls">
            <button id="close-btn">✕</button>
        </div>
    </div>
    
    <div class="resize-handle nw"></div>
    <div class="resize-handle ne"></div>
    <div class="resize-handle sw"></div>
    <div class="resize-handle se"></div>
    
    <div class="container">
        <div class="logo">❌</div>
        <h1 class="title">无法直接运行</h1>
        <p class="message">此程序由 ComfyNexus 主程序自动调用，<br>请勿直接运行。</p>
    </div>
    
    <script>
        // 错误窗口不需要缩放，只需要关闭功能
        document.getElementById('close-btn').addEventListener('click', () => {{
            window.close();
        }});
    </script>
</body>
</html>'''
        
        try:
            webview.create_window('ComfyNexus 更新器', html=error_html, width=420, height=320, 
                                  resizable=False, frameless=True)
            webview.start(debug=False, gui='edgechromium')
        except Exception as e:
            logger.error(f"显示错误窗口失败: {e}")
        
        release_mutex()
        sys.exit(1)
    
    zip_path = Path(sys.argv[1])
    target_dir = Path(sys.argv[2])
    main_exe = Path(sys.argv[3])
    
    logger.info(f"更新包: {zip_path}")
    logger.info(f"目标目录: {target_dir}")
    logger.info(f"主程序: {main_exe}")
    logger.info(f"更新包存在: {zip_path.exists()}")
    logger.info(f"目标目录存在: {target_dir.exists()}")
    logger.info(f"主程序存在: {main_exe.exists()}")
    
    icon_base64 = get_icon_base64()
    logger.debug(f"图标 base64 长度: {len(icon_base64)}")
    
    # 设置独立的 WebView2 用户数据目录，避免与主应用冲突
    updater_webview2_dir = target_dir / "data" / "webview2_updater"
    updater_webview2_dir.mkdir(parents=True, exist_ok=True)
    os.environ['WEBVIEW2_USER_DATA_FOLDER'] = str(updater_webview2_dir)
    logger.info(f"WebView2 用户数据目录: {updater_webview2_dir}")

    # FULL 模式：使用 runtime/webview2/ 中的 Fixed Version
    runtime_webview2 = target_dir / "runtime" / "webview2"
    if runtime_webview2.exists() and (runtime_webview2 / "msedge.dll").exists():
        os.environ['WEBVIEW2_BROWSER_EXECUTABLE_FOLDER'] = str(runtime_webview2)
        logger.info(f"WebView2 Fixed Version: {runtime_webview2}")
    
    api = UpdaterAPI()
    api.zip_path = zip_path
    api.target_dir = target_dir
    api.main_exe = main_exe
    
    logger.info("创建 webview 窗口")
    window = webview.create_window(
        'ComfyNexus 更新器',
        html=get_html(icon_base64),
        js_api=api,
        width=480,
        height=600,
        resizable=True,
        frameless=True,
        easy_drag=False,
    )
    
    api.set_window(window)
    logger.info("启动 webview")
    
    try:
        webview.start(debug=False, gui='edgechromium')
    except Exception as e:
        logger.error(f"webview 启动失败: {e}")
        logger.error(traceback.format_exc())
        raise
    finally:
        release_mutex()
    
    logger.info("更新器退出")


if __name__ == "__main__":
    main()
