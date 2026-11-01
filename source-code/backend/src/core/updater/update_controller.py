"""
更新控制器
用于暴露给前端的更新 API
"""

import os
import re
import sys
import subprocess
import threading
from typing import Dict, Optional, Callable
from pathlib import Path

from .update_checker import UpdateChecker
from .update_downloader import UpdateDownloader
from backend.src.utils.logger import app_logger as logger

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _is_valid_sha256(value) -> bool:
    """判断是否为 64 位十六进制 SHA256 字符串"""
    return isinstance(value, str) and bool(_SHA256_RE.match(value))


class UpdateController:
    """更新控制器"""
    
    def __init__(self, settings_manager=None):
        """初始化更新控制器"""
        self._checker = UpdateChecker(settings_manager)
        self._downloader = UpdateDownloader(settings_manager=settings_manager)
        self._settings_manager = settings_manager
        self._update_info: Optional[Dict] = None
        self._download_progress: Dict = {
            "downloaded": 0,
            "total": 0,
            "percentage": 0
        }
        self._window = None
    
    def set_window(self, window):
        """设置窗口引用"""
        self._window = window
    
    def check_for_update(self) -> Dict:
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
                "file_hash": str,
                "error": str  # 可选
            }
        """
        logger.info("[UpdateController] 检查更新...")
        
        result = self._checker.check_update()
        
        if result.get("success") and result.get("has_update"):
            self._update_info = result
        
        return result
    
    def check_local_update(self) -> Dict:
        """
        检查本地是否已有可用的更新包
        
        Returns:
            {
                "success": bool,
                "has_local_file": bool,
                "hash_match": bool,
                "file_path": str,
                "file_size": int,
                "partial_download": {
                    "has_partial": bool,
                    "downloaded_size": int,
                    "total_size": int,
                    "percentage": int
                },
                "error": str  # 可选
            }
        """
        try:
            if not self._update_info:
                return {
                    "success": False,
                    "has_local_file": False,
                    "hash_match": False,
                    "file_path": "",
                    "file_size": 0,
                    "partial_download": None,
                    "error": "没有可用的更新信息，请先检查更新"
                }
            
            download_url = self._update_info.get("download_url", "")
            file_hash = self._update_info.get("file_hash")
            file_size = self._update_info.get("file_size", 0)
            latest_version = self._update_info.get("latest_version", "")
            
            filename = download_url.split("/")[-1]
            if not filename.endswith(".zip"):
                filename = f"ComfyNexus-{latest_version}-win64.zip"
            
            local_check = self._downloader.check_local_file(file_hash, filename)
            
            partial_info = self._downloader.get_partial_download_info(
                filename, latest_version, file_hash or ""
            )
            
            result = {
                "success": True,
                "has_local_file": local_check["exists"],
                "hash_match": local_check["hash_match"],
                "file_path": local_check["file_path"],
                "file_size": local_check["file_size"],
                "partial_download": None
            }
            
            if partial_info["has_partial"]:
                result["partial_download"] = {
                    "has_partial": True,
                    "downloaded_size": partial_info["downloaded_size"],
                    "total_size": partial_info["total_size"],
                    "percentage": partial_info["percentage"],
                    "version_match": partial_info["version_match"],
                    "hash_match": partial_info["hash_match"]
                }
            
            logger.info(f"[UpdateController] 本地检查完成: has_local={result['has_local_file']}, hash_match={result['hash_match']}, has_partial={partial_info['has_partial']}")
            
            return result
            
        except Exception as e:
            logger.error(f"[UpdateController] 检查本地更新失败: {e}")
            return {
                "success": False,
                "has_local_file": False,
                "hash_match": False,
                "file_path": "",
                "file_size": 0,
                "partial_download": None,
                "error": f"检查本地更新失败: {str(e)}"
            }
    
    def download_update(self) -> Dict:
        """
        下载更新包
        
        Returns:
            {
                "success": bool,
                "zip_path": str,
                "error": str,
                "from_local": bool,
                "resumed": bool
            }
        """
        if not self._update_info:
            return {
                "success": False,
                "error": "没有可用的更新信息，请先检查更新"
            }
        
        download_url = self._update_info.get("download_url")
        file_size = self._update_info.get("file_size", 0)
        file_hash = self._update_info.get("file_hash")
        latest_version = self._update_info.get("latest_version", "")
        
        if not download_url:
            return {
                "success": False,
                "error": "下载链接不可用"
            }

        # 安装包会以更新器进程身份落盘并解压，完整性校验不能是可选项。
        # 官方通道（没配置 dev 更新源）必须带 64 位 SHA256；缺少或格式不对直接拒绝下载。
        # 开发通道允许缺省（自建仓库的 version.json 可能还没算 hash），但一旦提供同样会校验。
        is_dev_channel = bool(self._checker.dev_token)
        if not _is_valid_sha256(file_hash):
            if not is_dev_channel:
                logger.error(
                    f"[UpdateController] 官方通道更新信息缺少有效 file_hash，拒绝下载: {file_hash!r}"
                )
                return {
                    "success": False,
                    "zip_path": "",
                    "error": "更新信息缺少有效的 SHA256 校验值，已拒绝下载。请稍后重试或联系发布者",
                    "from_local": False,
                    "resumed": False,
                }
            logger.warning(
                "[UpdateController] 开发通道未提供有效 file_hash，本次跳过完整性校验"
            )
        
        logger.info(f"[UpdateController] 开始下载更新: {download_url}")
        if file_hash:
            logger.info(f"[UpdateController] 将进行 SHA256 校验: {file_hash[:16]}...")
        
        dev_token = self._checker.dev_token
        asset_id = self._update_info.get("asset_id")
        repo_owner = self._checker.dev_repo_owner
        repo_name = self._checker.dev_repo_name
        
        if dev_token:
            logger.info(f"[UpdateController] 检测到 dev Token: {dev_token[:8]}...")
        else:
            logger.info("[UpdateController] 未检测到 dev Token")
        
        def progress_callback(downloaded: int, total: int):
            self._download_progress = {
                "downloaded": downloaded,
                "total": total,
                "percentage": int(downloaded / total * 100) if total > 0 else 0
            }
            
            if self._window:
                try:
                    self._window.evaluate_js(
                        f"window.__updateProgress && window.__updateProgress({downloaded}, {total})"
                    )
                except Exception as e:
                    logger.debug(f"[UpdateController] 进度回调失败: {e}")
        
        result = self._downloader.download(
            download_url, 
            file_size=file_size,
            file_hash=file_hash,
            progress_callback=progress_callback,
            dev_token=dev_token,
            asset_id=asset_id,
            repo_owner=repo_owner,
            repo_name=repo_name,
            version=latest_version
        )
        
        return result
    
    def get_download_progress(self) -> Dict:
        """
        获取下载进度
        
        Returns:
            {
                "downloaded": int,
                "total": int,
                "percentage": int
            }
        """
        return self._download_progress
    
    def apply_update(self) -> Dict:
        """
        应用更新（启动更新器并退出主程序）
        
        Returns:
            {
                "success": bool,
                "message": str
            }
        """
        zip_path = self._downloader.downloaded_path
        
        if not zip_path or not os.path.exists(zip_path):
            logger.error("[UpdateController] 更新包不存在")
            return {
                "success": False,
                "message": "更新包不存在，请先下载更新"
            }
        
        try:
            from backend.src.utils.paths import get_project_root
            base_path = get_project_root()
            
            target_dir = base_path
            main_exe = base_path / "ComfyNexus.exe"
            updater_exe = base_path / "ComfyNexusUpdater_v1.0.exe"
            old_updater_exe = base_path / "Updater.exe"
            
            if not updater_exe.exists() and old_updater_exe.exists():
                updater_exe = old_updater_exe
            
            logger.info(f"[UpdateController] 基础路径: {base_path}")
            logger.info(f"[UpdateController] 更新包: {zip_path}")
            logger.info(f"[UpdateController] 目标目录: {target_dir}")
            logger.info(f"[UpdateController] 主程序: {main_exe}")
            logger.info(f"[UpdateController] 更新器: {updater_exe}")
            
            if not updater_exe.exists():
                logger.error(f"[UpdateController] 更新器不存在: {updater_exe}")
                return {
                    "success": False,
                    "message": "更新器程序不存在，请重新安装应用"
                }
            
            if not main_exe.exists():
                logger.warning(f"[UpdateController] 主程序不存在: {main_exe}")
            
            cmd = [str(updater_exe), str(zip_path), str(target_dir), str(main_exe)]
            logger.info(f"[UpdateController] 启动命令: {' '.join(cmd)}")
            
            subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            
            logger.info("[UpdateController] 更新器已启动，准备退出主程序")
            
            def delayed_exit():
                import time
                import os
                time.sleep(2)
                logger.info("[UpdateController] 正在退出主程序...")
                
                # 先销毁悬浮窗
                try:
                    from backend.src.ui.floating_window import floating_window_manager
                    if floating_window_manager:
                        floating_window_manager.destroy()
                        logger.info("[UpdateController] 悬浮窗已销毁")
                except Exception as e:
                    logger.warning(f"[UpdateController] 销毁悬浮窗失败: {e}")
                
                # 再销毁主窗口
                if self._window:
                    try:
                        self._window.destroy()
                    except Exception as e:
                        logger.warning(f"[UpdateController] 关闭窗口失败: {e}")
                
                # 强制退出进程（pywebview 事件循环可能还在跑）
                time.sleep(1)
                logger.info("[UpdateController] 强制退出进程")
                os._exit(0)
            
            threading.Thread(target=delayed_exit, daemon=True).start()
            
            return {
                "success": True,
                "message": "正在启动更新器..."
            }
            
        except Exception as e:
            logger.error(f"[UpdateController] 应用更新失败: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "message": f"应用更新失败: {str(e)}"
            }
    
    def cancel_download(self) -> Dict:
        """
        取消下载
        
        Returns:
            {
                "success": bool,
                "message": str
            }
        """
        if self._downloader.is_downloading:
            self._downloader.cancel_download()
            return {
                "success": True,
                "message": "已取消下载"
            }
        
        return {
            "success": False,
            "message": "没有正在进行的下载"
        }
    
    def clear_download_cache(self) -> Dict:
        """
        清理下载缓存
        
        Returns:
            {
                "success": bool,
                "message": str
            }
        """
        try:
            current_version = self._checker.current_version
            self._downloader.cleanup_old_cache(current_version)
            return {
                "success": True,
                "message": "已清理旧版本缓存"
            }
        except Exception as e:
            logger.error(f"[UpdateController] 清理缓存失败: {e}")
            return {
                "success": False,
                "message": f"清理缓存失败: {str(e)}"
            }
    
    def cleanup(self):
        """清理临时文件"""
        self._downloader.cleanup()
    
    @property
    def current_version(self) -> str:
        """获取当前版本号"""
        return self._checker.current_version
    
    @property
    def update_info(self) -> Optional[Dict]:
        """获取更新信息"""
        return self._update_info
