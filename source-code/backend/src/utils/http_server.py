"""
自定义HTTP服务器

用于提供前端静态文件服务，替代pywebview的内置http_server

安全边界（第一阶段整改 Phase 1.2）：
- 只监听回环地址（`find_available_port` 与 `_run_server` 都绑定 127.0.0.1）。
- CORS 只放行本机来源，不再对所有站点开放（默认 `CORS(app)` 会回
  `Access-Control-Allow-Origin: *`，等于允许用户浏览器里任意网页读取本机文件）。
- 所有以 URL 片段拼接文件路径的路由都必须先经过 `_resolve_within()` 收敛到
  预期目录内，越界（绝对路径、盘符、`..`、反斜杠、NUL、软链接逃逸）一律 404，
  且响应体不回显入参与绝对路径。
"""

import os
import re
import socket
import threading
from pathlib import Path
from typing import Optional
from flask import Flask, send_from_directory, send_file, request, Response
from flask_cors import CORS
from werkzeug.exceptions import NotFound
from werkzeug.serving import make_server

from .logger import app_logger as logger


# 允许携带跨域头的来源：只有本机回环地址上的 pywebview 窗口需要访问本服务。
# 端口是运行时自动分配的，所以端口号用正则匹配，协议固定 http。
ALLOWED_CORS_ORIGINS = [
    re.compile(r"^http://(?:127\.0\.0\.1|localhost)(?::\d{1,5})?$"),
]

# 本服务只为本机的 pywebview 窗口提供文件，绝不监听对外网卡。
# 绑定、探端口、拼 URL 三处统一用它，避免哪个角落漏改成 0.0.0.0。
LOOPBACK_HOST = "127.0.0.1"

# 404 响应体固定用这句文案：不回显请求片段，避免泄露本机绝对路径结构
NOT_FOUND_BODY = "Not Found"

# 500 响应体同样固定：异常文本里常带绝对路径
INTERNAL_ERROR_BODY = "Internal Server Error"

# Windows 盘符前缀（`C:` / `d:`）：出现在 URL 片段里就是绝对路径注入
_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")


def _resolve_within(base_dir: Path, unsafe_relative: str) -> Optional[Path]:
    """
    把 URL 中取来的相对路径解析到 ``base_dir`` **内部**的安全路径。

    Args:
        base_dir: 允许访问的根目录
        unsafe_relative: 来自 URL 的相对路径（可能含 `a/b` 形式的多级目录）

    Returns:
        Optional[Path]: 位于 base_dir 内的绝对路径；任何越界迹象都返回 None

    拒绝规则（命中任意一条即返回 None）：
    - 空串、含 NUL（``\\x00``）
    - 含反斜杠：Windows 上 ``Path('E:/a') / '..\\..\\x'`` 会把 ``\\`` 当分隔符，
      是真实的穿越通道，因此整串拒绝（合法静态资源名不需要反斜杠）
    - 以前导斜杠或盘符（``C:`` 等）开头：``Path(base) / 'C:/Windows/win.ini'``
      在 Windows 上会**直接替换**成那个绝对路径，等于任意文件读
    - 含 URL 解码后出现的 ``.`` / ``..`` 段（``%2e%2e%2f`` 在路由前已被解码）
    - 含空段（``a//b``）——正常请求不会出现，直接拒绝以免歧义
    - 解析（``resolve``，含软链接展开）后不落在 base_dir 内：覆盖软链接指向目录外
    """
    if not unsafe_relative or "\x00" in unsafe_relative:
        return None
    if "\\" in unsafe_relative:
        return None
    if unsafe_relative.startswith("/") or _DRIVE_PREFIX.match(unsafe_relative):
        return None

    segments = unsafe_relative.split("/")
    if any(segment in ("", ".", "..") for segment in segments):
        return None

    try:
        base = Path(base_dir).resolve()
        candidate = (base / Path(*segments)).resolve()
    except (OSError, ValueError) as exc:  # 非法路径/权限异常一律视为不可达
        logger.warning(f"[HTTP Server] 路径解析失败，按 404 处理: {exc}")
        return None

    if not candidate.is_relative_to(base):
        return None
    return candidate


def find_available_port(start_port: int = 5000, max_attempts: int = 100) -> int:
    """
    查找可用端口
    
    Args:
        start_port: 起始端口
        max_attempts: 最大尝试次数
    
    Returns:
        可用端口号
    
    Raises:
        RuntimeError: 如果找不到可用端口
    """
    for port in range(start_port, start_port + max_attempts):
        try:
            # 尝试绑定端口
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((LOOPBACK_HOST, port))
                logger.info(f"找到可用端口: {port}")
                return port
        except OSError:
            # 端口被占用，继续尝试下一个
            continue
    
    raise RuntimeError(f"无法在 {start_port}-{start_port + max_attempts} 范围内找到可用端口")


def create_server(static_dir: Path, port: int = None) -> 'StaticFileServer':
    """
    创建静态文件服务器
    
    Args:
        static_dir: 静态文件目录（前端构建输出目录）
        port: 服务器端口（如果为 None，则自动查找可用端口）
    
    Returns:
        StaticFileServer 实例
    """
    return StaticFileServer(static_dir, port)


class StaticFileServer:
    """静态文件服务器"""
    
    def __init__(self, static_dir: Path, port: int = None):
        """
        初始化静态文件服务器
        
        Args:
            static_dir: 静态文件目录（前端构建输出目录）
            port: 服务器端口（如果为 None，则自动查找可用端口）
        """
        self.static_dir = Path(static_dir)
        
        # 如果未指定端口，自动查找可用端口
        if port is None:
            self.port = find_available_port()
        else:
            self.port = port
            
        self.app = Flask(__name__)
        self.server = None
        self.server_thread = None
        self.is_running = False
        
        # 只对回环地址来源放行跨域读取（原来是 CORS(self.app) → Access-Control-Allow-Origin: *）
        CORS(
            self.app,
            resources={r"/*": {"origins": ALLOWED_CORS_ORIGINS}},
            supports_credentials=False,
        )
        
        # 配置Flask
        self.app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # 禁用缓存（开发模式)
        
        # 设置路由
        self._setup_routes()
        
        logger.info(f"[HTTP Server] 初始化完成")
        logger.info(f"[HTTP Server] 静态文件目录: {static_dir}")
    
    def _setup_routes(self):
        """设置路由"""
        
        # ========== 鷻加静态文件路由 ==========
        
        @self.app.route('/lora/preview/<model_id>/<filename>')
        def lora_preview(model_id, filename):
            """LoRA 预览图路由"""
            try:
                from backend.src.utils.paths import get_project_root

                preview_root = Path(get_project_root()) / "lora_data" / "preview"
                # model_id 与 filename 都来自 URL，拼接前必须收敛到 preview_root 内
                file_path = _resolve_within(preview_root, f"{model_id}/{filename}")

                if file_path is None or not file_path.is_file():
                    logger.warning(
                        f"[Lora Preview] 拒绝或找不到预览图: model_id={model_id!r}, "
                        f"filename={filename!r}"
                    )
                    return NOT_FOUND_BODY, 404
                
                ext = file_path.suffix.lower()
                mime_types = {
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.png': 'image/png',
                    '.gif': 'image/gif',
                    '.webp': 'image/webp',
                    '.mp4': 'video/mp4',
                    '.webm': 'video/webm',
                    '.mov': 'video/quicktime'
                }
                mimetype = mime_types.get(ext, 'application/octet-stream')
                
                return send_file(str(file_path), mimetype=mimetype)
            except Exception as e:
                logger.error(f"[Lora Preview] 提供预览图失败: {e}")
                return INTERNAL_ERROR_BODY, 500
        
        @self.app.route('/prompt/images/<filename>')
        def prompt_image(filename):
            """提示词库预览图路由"""
            try:
                from backend.src.utils.paths import get_prompt_images_dir
                
                images_dir = get_prompt_images_dir()
                file_path = _resolve_within(images_dir, filename)

                if file_path is None or not file_path.is_file():
                    logger.warning(
                        f"[Prompt Image] 拒绝或找不到预览图: filename={filename!r}"
                    )
                    return NOT_FOUND_BODY, 404
                
                ext = file_path.suffix.lower()
                mime_types = {
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.png': 'image/png',
                    '.gif': 'image/gif',
                    '.webp': 'image/webp'
                }
                mimetype = mime_types.get(ext, 'application/octet-stream')
                
                return send_file(str(file_path), mimetype=mimetype)
            except Exception as e:
                logger.error(f"[Prompt Image] 提供预览图失败: {e}")
                return INTERNAL_ERROR_BODY, 500
        
        @self.app.route('/gallery/thumbnail/<asset_id>')
        def gallery_thumbnail(asset_id):
            """资产库缩略图路由"""
            try:
                from backend.src.gallery.controller import gallery_controller
                response = gallery_controller.gallery_get_thumbnail(asset_id)
                if response:
                    return response
                else:
                    logger.warning(f"[Gallery Thumbnail] 无法获取缩略图: {asset_id}")
                    return NOT_FOUND_BODY, 404
            except Exception as e:
                logger.error(f"[Gallery Thumbnail] 提供缩略图失败: {e}")
                return INTERNAL_ERROR_BODY, 500
        
        @self.app.route('/gallery/asset/<asset_id>')
        def gallery_asset(asset_id):
            """资产库原图路由"""
            try:
                from backend.src.gallery.controller import gallery_controller
                response = gallery_controller.gallery_get_asset_file(asset_id)
                if response:
                    return response
                else:
                    logger.warning(f"[Gallery Asset] 无法获取原图: {asset_id}")
                    return NOT_FOUND_BODY, 404
            except Exception as e:
                logger.error(f"[Gallery Asset] 提供原图失败: {e}")
                return INTERNAL_ERROR_BODY, 500
        
        @self.app.route('/images/<filename>')
        def workflow_preview_image(filename):
            """工作流预览图路由"""
            try:
                from backend.src.utils.paths import get_data_dir
                
                images_dir = get_data_dir() / "workflows" / "images"
                file_path = _resolve_within(images_dir, filename)

                if file_path is None or not file_path.is_file():
                    logger.warning(
                        f"[Workflow Preview] 拒绝或找不到预览图: filename={filename!r}"
                    )
                    return NOT_FOUND_BODY, 404
                
                ext = file_path.suffix.lower()
                mime_types = {
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.png': 'image/png',
                    '.gif': 'image/gif',
                    '.webp': 'image/webp'
                }
                mimetype = mime_types.get(ext, 'application/octet-stream')
                
                return send_file(str(file_path), mimetype=mimetype)
            except Exception as e:
                logger.error(f"[Workflow Preview] 提供预览图失败: {e}")
                return INTERNAL_ERROR_BODY, 500
        
        @self.app.route('/')
        def index():
            """首页路由"""
            try:
                index_path = self.static_dir / 'index.html'
                if not index_path.is_file():
                    logger.error(f"index.html not found at {index_path}")
                    return NOT_FOUND_BODY, 404
                
                return send_file(str(index_path))
            except Exception as e:
                logger.error(f"Error serving index.html: {e}")
                return INTERNAL_ERROR_BODY, 500
        
        @self.app.route('/<path:path>')
        def static_files(path):
            """静态文件路由（只允许 static_dir 目录内部的真实文件）"""
            try:
                # 尝试直接返回文件；越界（绝对路径/盘符/.. /反斜杠/NUL/软链接外逸）为 None
                file_path = _resolve_within(self.static_dir, path)

                if file_path is None:
                    logger.warning(f"[Static] 拒绝越界路径请求: {path!r}")
                    return NOT_FOUND_BODY, 404

                if file_path.is_file():
                    return send_file(str(file_path))
                
                # 如果文件不存在,检查是否是 JS/TS 文件请求
                # 这些文件不应该返回 index.html,而应该返回 404
                # 避免 MIME 类型错误
                if path.endswith(('.js', '.ts', '.jsx', '.tsx', '.mjs', '.cjs')):
                    logger.warning(f"[Static] JS/TS 文件不存在,返回 404: {path}")
                    return NOT_FOUND_BODY, 404
                
                # 如果文件不存在,返回index.html(支持前端路由)
                # 这对于React Router等前端路由框架很重要
                index_path = _resolve_within(self.static_dir, 'index.html')
                if index_path is not None and index_path.is_file():
                    return send_file(str(index_path))
                
                return NOT_FOUND_BODY, 404
                
            except Exception as e:
                logger.error(f"Error serving {path}: {e}")
                return INTERNAL_ERROR_BODY, 500
        
        @self.app.errorhandler(404)
        def not_found(e):
            """404错误处理 - 返回index.html支持前端路由"""
            try:
                index_path = self.static_dir / 'index.html'
                if index_path.exists():
                    return send_file(str(index_path))
                return "404 Not Found", 404
            except Exception as ex:
                logger.error(f"Error in 404 handler: {ex}")
                return "404 Not Found", 404
        
        @self.app.errorhandler(500)
        def internal_error(e):
            """500错误处理（异常详情只进日志，响应体不回显路径或内部信息）"""
            logger.error(f"Internal server error: {e}")
            return INTERNAL_ERROR_BODY, 500
    
    def start(self):
        """启动服务器"""
        if self.is_running:
            logger.warning("[HTTP Server] 服务器已在运行")
            return
        
        self.is_running = True
        self._start_error = None
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        logger.info(f"[HTTP Server] 服务器线程已启动，端口: {self.port}")
    
    def _run_server(self):
        """运行 Flask 服务器"""
        try:
            import logging
            werkzeug_logger = logging.getLogger('werkzeug')
            werkzeug_logger.setLevel(logging.WARNING)
            
            self.server = make_server(LOOPBACK_HOST, self.port, self.app, threaded=True)
            logger.info(f"[HTTP Server] make_server 绑定成功，开始监听端口: {self.port}")
            self.server.serve_forever()
        except Exception as e:
            self._start_error = str(e)
            logger.error(f"[HTTP Server] 服务器错误: {e}")
            self.is_running = False
    
    def stop(self):
        """停止服务器"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self.server:
            self.server.shutdown()
            self.server = None
        
        if self.server_thread:
            self.server_thread.join(timeout=2)
            self.server_thread = None
        
        logger.info("[HTTP Server] 服务器已停止")
    
    def get_url(self) -> str:
        """获取服务器 URL（始终是回环地址；本服务不对外网卡暴露）"""
        return f"http://{LOOPBACK_HOST}:{self.port}"
