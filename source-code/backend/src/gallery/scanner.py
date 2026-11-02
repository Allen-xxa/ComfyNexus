"""
资产库扫描服务
负责扫描目录、提取元数据、生成缩略图
"""

import os
import uuid
import hashlib
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

from backend.src.utils.logger import app_logger as logger
from backend.src.utils.paths import get_data_dir
from .models import Asset, AssetCategory, ScanProgress
from .storage import gallery_storage

SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".webm"}
SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS | SUPPORTED_VIDEO_EXTENSIONS


class GalleryScanner:
    """资产库扫描服务"""

    _scanning = False
    _stopping = False
    _scan_progress: Optional[ScanProgress] = None

    def __init__(self):
        self._cancelled = False
        self._thumbnails_dir = get_data_dir() / "gallery" / "thumbnails"

    @classmethod
    def is_scanning(cls) -> bool:
        """检查是否正在扫描"""
        return cls._scanning

    @classmethod
    def is_stopping(cls) -> bool:
        """检查是否正在停止"""
        return cls._stopping

    @classmethod
    def get_scan_progress(cls) -> Optional[dict]:
        """获取当前扫描进度"""
        if cls._scan_progress:
            return cls._scan_progress.to_dict()
        return None

    @classmethod
    def stop_scan(cls):
        """停止扫描操作"""
        cls._stopping = True
        cls._cancelled = True

    @classmethod
    def reset_scan_state(cls):
        """重置扫描状态"""
        cls._scanning = False
        cls._stopping = False
        cls._scan_progress = None
        cls._cancelled = False

    def cancel(self):
        """取消扫描"""
        self._cancelled = True

    def start_background_scan(self, library_path: str) -> dict:
        """
        在后台线程中启动扫描

        Args:
            library_path: 要扫描的目录路径

        Returns:
            dict: 启动结果
        """
        if GalleryScanner._scanning:
            return {
                "success": False,
                "message": "已有扫描任务在进行中"
            }

        GalleryScanner._scanning = True
        GalleryScanner._stopping = False
        GalleryScanner._scan_progress = None
        self._cancelled = False

        import threading

        def scan_thread():
            try:
                result = self.scan_library(library_path, self._internal_progress_callback)
                GalleryScanner._scan_progress = ScanProgress(
                    stage="done",
                    current=result.get("added", 0) + result.get("updated", 0) + result.get("removed", 0),
                    total=result.get("added", 0) + result.get("updated", 0) + result.get("removed", 0),
                    message=f"扫描完成: 新增 {result.get('added', 0)}, 更新 {result.get('updated', 0)}, 移除 {result.get('removed', 0)}"
                )
            except Exception as e:
                # logger.error(f"[GalleryScanner] 后台扫描失败: {e}")
                GalleryScanner._scan_progress = ScanProgress(
                    stage="done",
                    current=0,
                    total=0,
                    message=f"扫描失败: {str(e)}"
                )
            finally:
                GalleryScanner._scanning = False
                GalleryScanner._stopping = False

        thread = threading.Thread(target=scan_thread, daemon=True)
        thread.start()

        return {
            "success": True,
            "message": "扫描任务已启动"
        }

    def _internal_progress_callback(self, current: int, total: int, filename: str, asset_data: dict = None):
        """内部进度回调，更新类变量"""
        GalleryScanner._scan_progress = ScanProgress(
            stage="scanning",
            current=current,
            total=total,
            message=f"正在扫描: {filename}",
            asset_data=asset_data
        )

    def scan_library(self, library_path: str, progress_callback=None) -> dict:
        """
        扫描资产库目录

        Args:
            library_path: 要扫描的目录路径
            progress_callback: 进度回调函数 (current, total, filename)

        Returns:
            dict: 扫描结果 {
                "added": int,
                "updated": int,
                "removed": int,
                "errors": list[str]
            }
        """
        self._cancelled = False
        library_dir = Path(library_path)

        if not library_dir.exists():
            # logger.error(f"[GalleryScanner] 目录不存在: {library_path}")
            return {"added": 0, "updated": 0, "removed": 0, "errors": ["目录不存在"]}

        self._thumbnails_dir.mkdir(parents=True, exist_ok=True)

        # 清理旧数据（切换目录时需要清理之前的资产和分类）
        gallery_storage.clear_all_data()

        self._sync_categories_from_folders(library_dir)

        existing_assets = {a.file_path: a for a in gallery_storage.get_assets()}
        found_files = {}
        errors = []
        added_count = 0
        updated_count = 0

        all_files = list(self._find_media_files(library_dir))
        total_files = len(all_files)

        # logger.info(f"[GalleryScanner] 开始扫描 {library_path}, 共 {total_files} 个文件")

        for current, file_path in enumerate(all_files):
            if self._cancelled:
                    # logger.info("[GalleryScanner] 扫描已取消")
                break

            try:
                file_path_str = str(file_path)
                found_files[file_path_str] = True

                relative_dir = file_path.parent.relative_to(library_dir)
                folder_path = str(relative_dir).replace("\\", "/") if str(relative_dir) != "." else None

                category_id = None
                if folder_path:
                    category = gallery_storage.get_category_by_folder_path(folder_path)
                    if category:
                        category_id = category.id

                asset_data = None
                if file_path_str in existing_assets:
                    existing_asset = existing_assets[file_path_str]
                    if self._needs_update(existing_asset, file_path):
                        self._update_asset(existing_asset, file_path, category_id)
                        updated_count += 1
                        asset_data = existing_asset.to_dict()
                else:
                    asset = self._create_asset(file_path, category_id)
                    if asset:
                        gallery_storage.add_asset(asset)
                        added_count += 1
                        asset_data = asset.to_dict()

                if progress_callback:
                    progress_callback(current + 1, total_files, file_path.name, asset_data)
            except Exception as e:
                error_msg = f"处理文件失败 {file_path}: {e}"
                # logger.error(f"[GalleryScanner] {error_msg}")
                errors.append(error_msg)

        removed_count = 0
        for file_path_str in existing_assets:
            if file_path_str not in found_files:
                gallery_storage.delete_asset(existing_assets[file_path_str].id)
                removed_count += 1

        gallery_storage.update_settings(last_scan_time=datetime.now().isoformat())

        result = {
            "added": added_count,
            "updated": updated_count,
            "removed": removed_count,
            "errors": errors
        }

        # logger.info(f"[GalleryScanner] 扫描完成: 新增 {added_count}, 更新 {updated_count}, 移除 {removed_count}")
        return result

    def scan_library_incremental(self, library_path: str, progress_callback=None) -> dict:
        """
        增量扫描资产库目录

        不清空现有数据，只处理：
        - 新增的文件
        - ctime 或 size 变化的文件（重置所有元数据）
        - 已删除的文件

        Args:
            library_path: 要扫描的目录路径
            progress_callback: 进度回调函数 (current, total, filename)

        Returns:
            dict: 扫描结果 {
                "added": int,
                "updated": int,
                "removed": int,
                "errors": list[str]
            }
        """
        self._cancelled = False
        library_dir = Path(library_path)

        if not library_dir.exists():
            return {"added": 0, "updated": 0, "removed": 0, "errors": ["目录不存在"]}

        self._thumbnails_dir.mkdir(parents=True, exist_ok=True)

        self._sync_categories_from_folders(library_dir)

        existing_assets = {a.file_path: a for a in gallery_storage.get_assets()}
        found_files = {}
        errors = []
        added_count = 0
        updated_count = 0

        all_files = list(self._find_media_files(library_dir))
        total_files = len(all_files)

        for current, file_path in enumerate(all_files):
            if self._cancelled:
                break

            try:
                file_path_str = str(file_path)
                found_files[file_path_str] = True

                relative_dir = file_path.parent.relative_to(library_dir)
                folder_path = str(relative_dir).replace("\\", "/") if str(relative_dir) != "." else None

                category_id = None
                if folder_path:
                    category = gallery_storage.get_category_by_folder_path(folder_path)
                    if category:
                        category_id = category.id

                asset_data = None
                if file_path_str in existing_assets:
                    existing_asset = existing_assets[file_path_str]
                    if self._needs_update(existing_asset, file_path):
                        new_asset = self._create_asset(file_path, category_id)
                        if new_asset:
                            new_asset.id = existing_asset.id
                            update_dict = {
                                "filename": new_asset.filename,
                                "file_path": new_asset.file_path,
                                "asset_type": new_asset.asset_type,
                                "width": new_asset.width,
                                "height": new_asset.height,
                                "size": new_asset.size,
                                "created_at": new_asset.created_at,
                                "category_id": new_asset.category_id,
                                "thumbnail_path": new_asset.thumbnail_path,
                                "has_workflow": new_asset.has_workflow,
                                "prompt": new_asset.prompt,
                                "negative_prompt": new_asset.negative_prompt,
                                "model": new_asset.model,
                                "sampler": new_asset.sampler,
                                "steps": new_asset.steps,
                                "cfg": new_asset.cfg,
                                "seed": new_asset.seed,
                                "duration": new_asset.duration,
                                "nsfw_score": new_asset.nsfw_score,
                                "nsfw_label": new_asset.nsfw_label,
                                "tags": new_asset.tags,
                                "preview_blurred": new_asset.preview_blurred,
                            }
                            gallery_storage.update_asset(existing_asset.id, **update_dict)
                            updated_count += 1
                            asset_data = new_asset.to_dict()
                            asset_data["id"] = existing_asset.id
                else:
                    asset = self._create_asset(file_path, category_id)
                    if asset:
                        gallery_storage.add_asset(asset)
                        added_count += 1
                        asset_data = asset.to_dict()

                if progress_callback:
                    progress_callback(current + 1, total_files, file_path.name, asset_data)
            except Exception as e:
                error_msg = f"处理文件失败 {file_path}: {e}"
                errors.append(error_msg)

        removed_count = 0
        for file_path_str in existing_assets:
            if file_path_str not in found_files:
                asset = existing_assets[file_path_str]
                if asset.thumbnail_path:
                    thumbnail_full_path = self._thumbnails_dir.parent / asset.thumbnail_path
                    if thumbnail_full_path.exists():
                        thumbnail_full_path.unlink()
                gallery_storage.delete_asset(asset.id)
                removed_count += 1

        gallery_storage.update_settings(last_scan_time=datetime.now().isoformat())

        result = {
            "added": added_count,
            "updated": updated_count,
            "removed": removed_count,
            "errors": errors
        }

        return result

    def _sync_categories_from_folders(self, library_dir: Path):
        """
        从文件夹结构同步分类（递归扫描所有层级）
        子文件夹自动成为分类，支持多级嵌套
        """
        existing_categories = {c.folder_path: c for c in gallery_storage.get_categories() if c.folder_path}
        found_folder_paths = set()

        def scan_directory(current_dir: Path, relative_path: str, parent_category_id: Optional[str] = None):
            """递归扫描目录"""
            for item in current_dir.iterdir():
                if item.is_dir():
                    current_relative_path = f"{relative_path}/{item.name}" if relative_path else item.name
                    found_folder_paths.add(current_relative_path)

                    if current_relative_path not in existing_categories:
                        category = gallery_storage.add_category(
                            name=item.name,
                            parent_id=parent_category_id,
                            folder_path=current_relative_path
                        )
                    else:
                        category = existing_categories[current_relative_path]

                    scan_directory(item, current_relative_path, category.id)

        scan_directory(library_dir, "", None)

        for folder_path, category in existing_categories.items():
            if folder_path not in found_folder_paths:
                gallery_storage.delete_category(category.id)

    def _find_media_files(self, directory: Path):
        """递归查找媒体文件"""
        for root, dirs, files in os.walk(directory):
            for file in files:
                ext = Path(file).suffix.lower()
                if ext in SUPPORTED_EXTENSIONS:
                    yield Path(root) / file

    def _needs_update(self, asset: Asset, file_path: Path) -> bool:
        """检查资产是否需要更新"""
        try:
            stat = file_path.stat()
            file_ctime = datetime.fromtimestamp(stat.st_ctime).isoformat()
            file_size = stat.st_size
            return file_ctime != asset.created_at or file_size != asset.size
        except Exception:
            return False

    def _create_asset(self, file_path: Path, category_id: Optional[str] = None) -> Optional[Asset]:
        """创建资产对象"""
        try:
            stat = file_path.stat()
            ext = file_path.suffix.lower()

            asset_type = "video" if ext in SUPPORTED_VIDEO_EXTENSIONS else "image"

            width, height = self._get_dimensions(file_path, asset_type)
            duration = self._get_duration(file_path) if asset_type == "video" else None

            thumbnail_path = None
            if asset_type == "video":
                thumbnail_path = self._generate_video_thumbnail(file_path)

            asset_id = self._generate_id(file_path)

            metadata = self._extract_metadata(file_path, asset_type)

            nsfw_score = None
            nsfw_label = None
            tags = []
            preview_blurred = False
            
            if asset_type == "image":
                nsfw_result = self._classify_nsfw(str(file_path))
                if nsfw_result:
                    nsfw_score = nsfw_result.nsfw_score
                    nsfw_label = nsfw_result.nsfw_label
                    tags = nsfw_result.tags
                    settings = gallery_storage.get_settings()
                    if nsfw_label == "NSFW" and settings.nsfw_auto_blur:
                        preview_blurred = True

            asset = Asset(
                id=asset_id,
                filename=file_path.name,
                file_path=str(file_path),
                asset_type=asset_type,
                width=width,
                height=height,
                size=stat.st_size,
                created_at=datetime.fromtimestamp(stat.st_ctime).isoformat(),
                is_favorite=False,
                category_id=category_id,
                thumbnail_path=thumbnail_path,
                has_workflow=metadata.get("has_workflow", False),
                prompt=metadata.get("prompt"),
                negative_prompt=metadata.get("negative_prompt"),
                model=metadata.get("model"),
                sampler=metadata.get("sampler"),
                scheduler=metadata.get("scheduler"),
                steps=metadata.get("steps"),
                cfg=metadata.get("cfg"),
                seed=metadata.get("seed"),
                duration=duration,
                nsfw_score=nsfw_score,
                nsfw_label=nsfw_label,
                tags=tags,
                preview_blurred=preview_blurred
            )

            return asset

        except Exception as e:
            # logger.error(f"[GalleryScanner] 创建资产失败 {file_path}: {e}")
            return None

    def _update_asset(self, asset: Asset, file_path: Path, category_id: Optional[str] = None):
        """更新资产信息"""
        try:
            stat = file_path.stat()
            ext = file_path.suffix.lower()
            asset_type = "video" if ext in SUPPORTED_VIDEO_EXTENSIONS else "image"

            width, height = self._get_dimensions(file_path, asset_type)
            duration = self._get_duration(file_path) if asset_type == "video" else None

            metadata = self._extract_metadata(file_path, asset_type)

            update_data = {
                "width": width,
                "height": height,
                "size": stat.st_size,
                "has_workflow": metadata.get("has_workflow", False),
                "prompt": metadata.get("prompt"),
                "negative_prompt": metadata.get("negative_prompt"),
                "model": metadata.get("model"),
                "sampler": metadata.get("sampler"),
                "steps": metadata.get("steps"),
                "cfg": metadata.get("cfg"),
                "seed": metadata.get("seed"),
                "duration": duration
            }

            if category_id is not None:
                update_data["category_id"] = category_id

            if asset_type == "image":
                nsfw_result = self._classify_nsfw(str(file_path))
                if nsfw_result:
                    update_data["nsfw_score"] = nsfw_result.nsfw_score
                    update_data["nsfw_label"] = nsfw_result.nsfw_label
                    update_data["tags"] = nsfw_result.tags
                    settings = gallery_storage.get_settings()
                    if nsfw_result.nsfw_label == "NSFW" and settings.nsfw_auto_blur:
                        update_data["preview_blurred"] = True

            gallery_storage.update_asset(asset.id, **update_data)

        except Exception as e:
            # logger.error(f"[GalleryScanner] 更新资产失败 {file_path}: {e}")
            pass

    def _classify_nsfw(self, image_path: str):
        """
        对图片进行 NSFW 分级
        
        Args:
            image_path: 图片路径
            
        Returns:
            ClassifyResult 或 None
        """
        try:
            settings = gallery_storage.get_settings()
            if not settings.nsfw_auto_classify:
                return None
            
            from .nsfw.service import NSFWClassifyService
            service = NSFWClassifyService()
            
            if not service.is_available():
                return None
            
            return service.classify_image(image_path, settings.nsfw_threshold)
        except Exception as e:
            # logger.debug(f"[GalleryScanner] NSFW 分级失败 {image_path}: {e}")
            return None

    def _generate_id(self, file_path: Path) -> str:
        """生成资产 ID"""
        hash_input = f"{file_path}_{file_path.stat().st_mtime}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:16]

    def _get_dimensions(self, file_path: Path, asset_type: str) -> tuple[int, int]:
        """获取媒体尺寸"""
        if asset_type == "image":
            try:
                from PIL import Image
                with Image.open(file_path) as img:
                    return img.size
            except Exception:
                return (0, 0)
        else:
            try:
                import cv2
                cap = cv2.VideoCapture(str(file_path))
                ret, frame = cap.read()
                if ret:
                    height, width = frame.shape[:2]
                    cap.release()
                    return (width, height)
                cap.release()
            except Exception:
                pass
            return (0, 0)

    def _get_duration(self, file_path: Path) -> Optional[float]:
        """获取视频时长"""
        try:
            import cv2
            cap = cv2.VideoCapture(str(file_path))
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            cap.release()
            if fps > 0 and frame_count > 0:
                duration = round(frame_count / fps, 2)
                # 检查是否为有效数值
                if duration == duration and duration != float('inf') and duration != float('-inf'):
                    return duration
        except Exception:
            pass
        return None

    def _generate_video_thumbnail(self, file_path: Path) -> Optional[str]:
        """生成视频缩略图"""
        try:
            import cv2
            cap = cv2.VideoCapture(str(file_path))
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            middle_frame = frame_count // 2

            cap.set(cv2.CAP_PROP_POS_FRAMES, middle_frame)
            ret, frame = cap.read()
            cap.release()

            if ret:
                from PIL import Image

                max_size = 300
                height, width = frame.shape[:2]
                if width > height:
                    new_width = max_size
                    new_height = int(height * max_size / width)
                else:
                    new_height = max_size
                    new_width = int(width * max_size / height)

                import cv2
                frame_resized = cv2.resize(frame, (new_width, new_height))
                frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)

                img = Image.fromarray(frame_rgb)

                thumbnail_filename = f"{file_path.stem}_{hashlib.md5(str(file_path).encode()).hexdigest()[:8]}.webp"
                thumbnail_path = self._thumbnails_dir / thumbnail_filename

                img.save(thumbnail_path, "WEBP", quality=85)

                return f"thumbnails/{thumbnail_filename}"

        except Exception as e:
            # logger.warning(f"[GalleryScanner] 生成视频缩略图失败 {file_path}: {e}")
            pass

        return None

    def _extract_metadata(self, file_path: Path, asset_type: str) -> dict:
        """提取元数据"""
        metadata = {}

        if asset_type == "image" and file_path.suffix.lower() == ".png":
            try:
                from PIL import Image
                with Image.open(file_path) as img:
                    info = img.info

                    workflow = info.get("workflow")
                    prompt = info.get("prompt")

                    if workflow:
                        try:
                            import json
                            workflow_data = json.loads(workflow)
                            metadata["has_workflow"] = True
                            metadata["workflow"] = workflow_data
                            
                            positive_prompt, negative_prompt, params = self._extract_prompt_from_workflow(workflow_data)
                            if positive_prompt:
                                metadata["prompt"] = positive_prompt
                            if negative_prompt:
                                metadata["negative_prompt"] = negative_prompt
                            if params:
                                metadata.update(params)
                        except Exception:
                            pass

                    if not metadata.get("prompt") and prompt:
                        try:
                            import json
                            prompt_data = json.loads(prompt)
                            positive_prompt, negative_prompt, params = self._extract_prompt_from_comfy_format(prompt_data)
                            if positive_prompt:
                                metadata["prompt"] = positive_prompt
                            if negative_prompt:
                                metadata["negative_prompt"] = negative_prompt
                            if params:
                                metadata.update(params)
                        except Exception:
                            if not metadata.get("prompt"):
                                metadata["prompt"] = prompt

            except Exception as e:
                pass

        return metadata

    def _extract_prompt_from_comfy_format(self, prompt_data: dict) -> tuple[str | None, str | None, dict]:
        """
        从 ComfyUI 的 prompt JSON 格式中提取提示词和参数
        
        采用输入输出类型推断方式识别提示词编码节点：
        - 输入是 CLIP 类型
        - 输出是 CONDITIONING 类型
        
        Returns:
            (positive_prompt, negative_prompt, params_dict)
        """
        positive_prompts = []
        negative_prompts = []
        params = {}
        
        clip_output_nodes = self._find_clip_output_nodes(prompt_data)
        conditioning_nodes = self._find_conditioning_nodes(prompt_data)
        
        for node_id, node_data in prompt_data.items():
            if not isinstance(node_data, dict):
                continue
            
            class_type = node_data.get("class_type", "")
            inputs = node_data.get("inputs", {})
            
            text = inputs.get("text", "")
            if text and isinstance(text, str):
                clip_input = inputs.get("clip")
                if self._is_clip_input(clip_input, clip_output_nodes):
                    if node_id in conditioning_nodes:
                        is_negative = conditioning_nodes[node_id].get("is_negative", False)
                        
                        if class_type in ["CLIPTextEncodeSDXL", "CLIPTextEncodeSDXLRefiner"]:
                            text_g = inputs.get("text_g", "")
                            text_l = inputs.get("text_l", "")
                            text = f"{text_g}\n{text_l}".strip() if text_g or text_l else text
                        
                        if is_negative:
                            negative_prompts.append(text)
                        else:
                            positive_prompts.append(text)
            
            if class_type in ["KSampler", "KSamplerAdvanced", "KSamplerAdvancedEfficient"]:
                if "steps" in inputs and params.get("steps") is None:
                    params["steps"] = inputs.get("steps")
                if "cfg" in inputs and params.get("cfg") is None:
                    params["cfg"] = inputs.get("cfg")
                if "sampler_name" in inputs and params.get("sampler") is None:
                    params["sampler"] = inputs.get("sampler_name")
                if "scheduler" in inputs and params.get("scheduler") is None:
                    params["scheduler"] = inputs.get("scheduler")
                if "seed" in inputs and params.get("seed") is None:
                    seed = inputs.get("seed")
                    if isinstance(seed, (int, float)):
                        params["seed"] = int(seed)
            
            elif class_type in ["CheckpointLoaderSimple", "CheckpointLoader", "UNETLoader", "CheckpointLoaderNF4"]:
                if params.get("model") is None:
                    model_name = inputs.get("ckpt_name") or inputs.get("unet_name")
                    if model_name:
                        params["model"] = model_name

            # ---- 新式采样链（SamplerCustomAdvanced）----
            elif class_type in ["RandomNoise", "RandomNoiseNode"]:
                seed = inputs.get("noise_seed")
                if params.get("seed") is None and isinstance(seed, (int, float)):
                    params["seed"] = int(seed)

            elif class_type in ["KSamplerSelect", "KSamplerSelectNode"]:
                if params.get("sampler") is None and inputs.get("sampler_name"):
                    params["sampler"] = inputs.get("sampler_name")

            elif class_type in ["BasicScheduler", "BasicSchedulerNode"]:
                if params.get("scheduler") is None and inputs.get("scheduler"):
                    params["scheduler"] = inputs.get("scheduler")
                if params.get("steps") is None and isinstance(inputs.get("steps"), (int, float)):
                    params["steps"] = inputs.get("steps")

            elif class_type in ["CFGGuider", "DualCFGGuider"]:
                if params.get("cfg") is None and isinstance(inputs.get("cfg"), (int, float)):
                    params["cfg"] = inputs.get("cfg")
        
        positive_prompt = "\n".join([p for p in positive_prompts if p]) if positive_prompts else None
        negative_prompt = "\n".join([p for p in negative_prompts if p]) if negative_prompts else None
        
        return positive_prompt, negative_prompt, params

    def _find_clip_output_nodes(self, prompt_data: dict) -> set[str]:
        """
        找出输出 CLIP 类型的节点
        
        通过两种方式识别：
        1. 已知的 CLIP 提供者节点类型
        2. 被其他节点作为 clip 输入引用的节点
        """
        clip_output_nodes = set()
        
        known_clip_providers = [
            "CheckpointLoaderSimple", "CheckpointLoader", "UNETLoader",
            "CLIPLoader", "CLIPVisionLoader", "CheckpointLoaderNF4",
            "LoraLoader", "LoraLoaderModelOnly"
        ]
        
        for node_id, node_data in prompt_data.items():
            if not isinstance(node_data, dict):
                continue
            
            class_type = node_data.get("class_type", "")
            
            if class_type in known_clip_providers:
                clip_output_nodes.add(node_id)
        
        for other_id, other_data in prompt_data.items():
            if not isinstance(other_data, dict):
                continue
            other_inputs = other_data.get("inputs", {})
            for key, value in other_inputs.items():
                if key == "clip" and isinstance(value, list) and len(value) >= 1:
                    clip_output_nodes.add(value[0])
        
        return clip_output_nodes

    def _find_conditioning_nodes(self, prompt_data: dict) -> dict[str, dict]:
        """
        找出输出 CONDITIONING 类型的节点
        
        通过检查采样器等节点的 positive/negative 输入来判断
        
        Returns:
            {node_id: {"is_negative": bool}}
        """
        conditioning_nodes = {}
        
        for node_id, node_data in prompt_data.items():
            if not isinstance(node_data, dict):
                continue
            
            inputs = node_data.get("inputs", {})
            
            for key, value in inputs.items():
                if not isinstance(value, list) or len(value) < 1:
                    continue
                
                source_node_id = value[0]
                
                if key in ["positive"]:
                    conditioning_nodes[source_node_id] = {"is_negative": False}
                elif key == "negative":
                    conditioning_nodes[source_node_id] = {"is_negative": True}
        
        return conditioning_nodes

    def _is_clip_input(self, clip_input, clip_output_nodes: set[str]) -> bool:
        """
        检查 clip 输入是否来自 CLIP 输出节点
        
        Args:
            clip_input: 节点的 clip 输入值，可能是 None、字符串或连接引用 [node_id, output_index]
            clip_output_nodes: 已知的 CLIP 输出节点 ID 集合
            
        Returns:
            是否是有效的 CLIP 输入
        """
        if clip_input is None:
            return False
        
        if isinstance(clip_input, list) and len(clip_input) >= 1:
            return clip_input[0] in clip_output_nodes
        
        return False

    def _build_node_link_maps(self, nodes: list, links: list) -> tuple[dict, dict, dict]:
        """
        构建 Workflow 格式的节点和连接映射
        
        Args:
            nodes: 节点列表
            links: 连接列表
            
        Returns:
            (node_map, link_map, input_connection_map)
        """
        node_map = {str(n.get("id")): n for n in nodes}
        
        link_map = {}
        for link in links:
            if link and len(link) >= 6:
                link_map[link[0]] = {
                    "source_node_id": str(link[1]),
                    "source_slot": link[2],
                    "target_node_id": str(link[3]),
                    "target_slot": link[4],
                    "type": link[5]
                }
        
        input_connection_map = {}
        for link_id, link_info in link_map.items():
            key = (link_info["target_node_id"], link_info["target_slot"])
            input_connection_map[key] = {
                "link_id": link_id,
                **link_info
            }
        
        return node_map, link_map, input_connection_map

    def _find_text_in_widgets(self, widgets_values: list) -> str | None:
        """
        智能识别 widgets_values 中的文本
        
        规则：
        1. 忽略空字符串
        2. 忽略纯数字（可能是参数）
        3. 忽略布尔值
        4. 忽略 JSON 对象
        5. 忽略文件路径
        6. 优先返回看起来像提示词的文本
        
        Args:
            widgets_values: 节点的 widgets_values 列表
            
        Returns:
            识别到的文本，如果没有则返回 None
        """
        if not widgets_values:
            return None
        
        candidates = []
        
        for value in widgets_values:
            if not isinstance(value, str):
                continue
            
            text = value.strip()
            if not text:
                continue
            
            if text.lstrip('-').replace('.', '').isdigit():
                continue
            
            if text.lower() in ['true', 'false']:
                continue
            
            if text.startswith('{') and text.endswith('}'):
                continue
            
            file_extensions = ['.safetensors', '.pt', '.pth', '.bin', '.json', '.txt', '.ckpt']
            if any(text.lower().endswith(ext) for ext in file_extensions):
                continue
            
            if len(text) < 5:
                continue
            
            is_prompt = self._looks_like_prompt(text)
            candidates.append((text, is_prompt))
        
        for text, is_prompt in candidates:
            if is_prompt:
                return text
        
        if candidates:
            return candidates[0][0]
        
        return None

    def _looks_like_prompt(self, text: str) -> bool:
        """
        判断文本是否看起来像提示词
        
        Args:
            text: 待判断的文本
            
        Returns:
            是否像提示词
        """
        prompt_keywords = {
            "masterpiece", "best quality", "high quality", "detailed",
            "1girl", "1boy", "solo", "portrait", "landscape",
            "realistic", "anime", "cartoon", "painting", "sketch",
            "lighting", "background", "beautiful", "cute", "sexy",
            "score_9", "score_8", "score_7",
            "杰作", "最佳质量", "高质量", "细节",
            "女孩", "男孩", "肖像", "风景",
            "写实", "动漫", "卡通", "绘画",
        }
        
        text_lower = text.lower()
        for keyword in prompt_keywords:
            if keyword in text_lower:
                return True
        
        if text.count(",") >= 3:
            return True
        
        if text.count("\n") >= 2:
            return True
        
        return False

    def _find_set_node(self, var_name: str, node_map: dict) -> dict | None:
        """
        根据变量名找到 SetNode
        
        Args:
            var_name: 变量名
            node_map: 节点映射
            
        Returns:
            SetNode 节点数据，未找到返回 None
        """
        for node in node_map.values():
            if "SetNode" in node.get("type", ""):
                widgets = node.get("widgets_values", [])
                if widgets and widgets[0] == var_name:
                    return node
        return None

    def _find_clip_output_nodes_workflow(
        self, 
        node_map: dict, 
        input_connection_map: dict
    ) -> set[str]:
        """
        找到所有输出 CLIP 类型的节点（Workflow 格式）
        
        Args:
            node_map: 节点映射
            input_connection_map: 输入连接映射
            
        Returns:
            CLIP 输出节点 ID 集合
        """
        clip_output_nodes = set()
        
        known_clip_providers = {
            "CheckpointLoaderSimple", "CheckpointLoader", "UNETLoader",
            "CLIPLoader", "CLIPVisionLoader", "CheckpointLoaderNF4",
            "LoraLoader", "LoraLoaderModelOnly",
            "DualCLIPLoader", "TripleCLIPLoader",
            "ClipLoaderGGUF", "DualClipLoaderGGUF", "CLIPLoaderGGUF",
            "NunchakuTextEncoderLoaderV2",
        }
        
        for node_id, node in node_map.items():
            node_type = node.get("type", "")
            if node_type in known_clip_providers:
                clip_output_nodes.add(node_id)
        
        for (target_node_id, target_slot), conn in input_connection_map.items():
            target_node = node_map.get(target_node_id, {})
            inputs = target_node.get("inputs", [])
            
            if target_slot < len(inputs):
                inp_name = inputs[target_slot].get("name", "").lower()
                if inp_name == "clip":
                    source_node_id = conn.get("source_node_id", "")
                    clip_output_nodes.add(source_node_id)
        
        return clip_output_nodes

    def _find_conditioning_nodes_workflow(
        self, 
        node_map: dict, 
        input_connection_map: dict
    ) -> dict[str, dict]:
        """
        找到所有输出 CONDITIONING 类型的节点（Workflow 格式）
        
        Args:
            node_map: 节点映射
            input_connection_map: 输入连接映射
            
        Returns:
            {node_id: {"is_negative": bool}}
        """
        conditioning_nodes = {}
        
        for node_id, node in node_map.items():
            inputs = node.get("inputs", [])
            
            for i, inp in enumerate(inputs):
                inp_name = inp.get("name", "").lower()
                
                key = (node_id, i)
                if key in input_connection_map:
                    source_node_id = input_connection_map[key]["source_node_id"]
                    
                    if inp_name == "positive":
                        conditioning_nodes[source_node_id] = {"is_negative": False}
                    elif inp_name == "negative":
                        conditioning_nodes[source_node_id] = {"is_negative": True}
        
        return conditioning_nodes

    def _is_text_encode_node(
        self, 
        node: dict, 
        node_id: str,
        clip_output_nodes: set[str],
        conditioning_nodes: dict[str, dict],
        input_connection_map: dict
    ) -> bool:
        """
        判断是否是提示词编码节点
        
        条件（满足任一）：
        1. 有 CLIP 类型的输入连接 + 输出 CONDITIONING 类型
        2. 有 CLIP 输入（无论是否连接）+ 输出 CONDITIONING + 在 conditioning_nodes 中
        3. 有 CLIP 输入 + 输出 CONDITIONING + widgets_values 有文本
        4. 节点类型包含 TextEncode/TextEmbed + widgets_values 有提示词文本（支持 WanVideo 等非标准节点）
        
        Args:
            node: 节点数据
            node_id: 节点 ID
            clip_output_nodes: CLIP 输出节点集合
            conditioning_nodes: CONDITIONING 输出节点映射
            input_connection_map: 输入连接映射
            
        Returns:
            是否是提示词编码节点
        """
        node_type = node.get("type", "")
        inputs = node.get("inputs", [])
        outputs = node.get("outputs", [])
        widgets_values = node.get("widgets_values", [])
        
        has_clip_input_name = False
        has_clip_input_connected = False
        for i, inp in enumerate(inputs):
            inp_name = inp.get("name", "").lower()
            if inp_name == "clip":
                has_clip_input_name = True
                key = (node_id, i)
                if key in input_connection_map:
                    source_node_id = input_connection_map[key]["source_node_id"]
                    if source_node_id in clip_output_nodes:
                        has_clip_input_connected = True
                break
        
        if has_clip_input_name:
            has_conditioning_output = False
            for out in outputs:
                out_type = out.get("type", "")
                if out_type == "CONDITIONING":
                    has_conditioning_output = True
                    break
            
            if not has_conditioning_output:
                return False
            
            if has_clip_input_connected:
                return True
            
            if node_id in conditioning_nodes:
                return True
            
            text = self._find_text_in_widgets(widgets_values)
            if text:
                return True
        
        non_standard_text_encode_types = {
            "WanVideoTextEncode", "WanVideoTextEncodeCached",
            "CogVideoTextEncode", "CogVideoTextEncodeCombined",
            "SVDTextEncode", "AnimateDiffTextEncode",
            " HunyuanVideoTextEncode", "HunyuanVideoTextEncoder",
        }
        
        for t in non_standard_text_encode_types:
            if t.lower() in node_type.lower():
                text = self._find_text_in_widgets(widgets_values)
                if text:
                    return True
        
        return False

    def _extract_text_from_node(
        self, 
        node: dict,
        node_map: dict,
        link_map: dict,
        input_connection_map: dict,
        visited: set = None,
        depth: int = 0
    ) -> str | None:
        """
        从节点提取文本，支持递归追踪连接链
        
        Args:
            node: 当前节点
            node_map: 节点映射
            link_map: 连接映射
            input_connection_map: 输入连接映射
            visited: 已访问节点集合
            depth: 当前递归深度
            
        Returns:
            提取到的文本，未找到返回 None
        """
        if visited is None:
            visited = set()
        
        node_id = str(node.get("id", ""))
        node_type = node.get("type", "")
        
        if node_id in visited or depth > 20:
            return None
        visited.add(node_id)
        
        widgets_values = node.get("widgets_values", [])
        text = self._find_text_in_widgets(widgets_values)
        
        if text:
            return text
        
        inputs = node.get("inputs", [])
        text_input_index = None
        text_input_indices = []
        
        for i, inp in enumerate(inputs):
            inp_name = inp.get("name", "").lower()
            if inp_name in ["text", "string", "prompt", "input"]:
                text_input_index = i
                break
            if inp_name in ["text_g", "text_l"]:
                text_input_indices.append(i)
        
        if text_input_index is not None:
            key = (node_id, text_input_index)
            if key in input_connection_map:
                conn = input_connection_map[key]
                source_node_id = conn["source_node_id"]
                source_node = node_map.get(source_node_id)
                
                if source_node:
                    result = self._extract_text_from_node(
                        source_node, node_map, link_map, input_connection_map, 
                        visited, depth + 1
                    )
                    if result:
                        return result
        
        if text_input_indices:
            texts = []
            for idx in text_input_indices:
                key = (node_id, idx)
                if key in input_connection_map:
                    conn = input_connection_map[key]
                    source_node_id = conn["source_node_id"]
                    source_node = node_map.get(source_node_id)
                    
                    if source_node:
                        result = self._extract_text_from_node(
                            source_node, node_map, link_map, input_connection_map, 
                            visited, depth + 1
                        )
                        if result:
                            texts.append(result)
            
            if texts:
                return "\n".join(texts)
        
        if "GetNode" in node_type:
            var_name = widgets_values[0] if widgets_values else None
            if var_name and isinstance(var_name, str):
                set_node = self._find_set_node(var_name, node_map)
                if set_node:
                    set_node_id = str(set_node.get("id", ""))
                    set_inputs = set_node.get("inputs", [])
                    if set_inputs:
                        key = (set_node_id, 0)
                        if key in input_connection_map:
                            conn = input_connection_map[key]
                            source_node_id = conn["source_node_id"]
                            source_node = node_map.get(source_node_id)
                            
                            if source_node:
                                result = self._extract_text_from_node(
                                    source_node, node_map, link_map, input_connection_map,
                                    visited, depth + 1
                                )
                                if result:
                                    return result
        
        return None

    def _extract_text_from_non_standard_node(self, node: dict) -> tuple[str | None, str | None]:
        """
        从非标准文本编码节点提取提示词
        
        支持 WanVideoTextEncodeCached、CogVideoTextEncode 等节点，
        这些节点的 widgets_values 中同时包含正向和负向提示词。
        
        Args:
            node: 节点数据
            
        Returns:
            (positive_prompt, negative_prompt)
        """
        node_type = node.get("type", "")
        widgets_values = node.get("widgets_values", [])
        
        positive = None
        negative = None
        
        if "WanVideoTextEncode" in node_type:
            if len(widgets_values) >= 4:
                for i, v in enumerate(widgets_values):
                    if isinstance(v, str) and len(v) > 10:
                        if self._looks_like_prompt(v):
                            if positive is None:
                                positive = v
                            elif negative is None and v != positive:
                                negative = v
                                break
        
        elif "CogVideoTextEncode" in node_type:
            if len(widgets_values) >= 2:
                for v in widgets_values:
                    if isinstance(v, str) and len(v) > 10:
                        if self._looks_like_prompt(v):
                            if positive is None:
                                positive = v
                            elif negative is None and v != positive:
                                negative = v
        
        else:
            for v in widgets_values:
                if isinstance(v, str) and len(v) > 10:
                    if self._looks_like_prompt(v):
                        if positive is None:
                            positive = v
                        elif negative is None and v != positive:
                            negative = v
        
        return positive, negative

    def _extract_prompt_from_workflow(self, workflow_data: dict) -> tuple[str | None, str | None, dict]:
        """
        从 Workflow JSON 提取提示词
        
        Workflow JSON 包含完整的节点信息，包括 widgets_values，
        可以处理 PrimitiveNode、Set/Get 变量等复杂场景。
        
        Args:
            workflow_data: 完整的工作流 JSON 数据
            
        Returns:
            (positive_prompt, negative_prompt, params_dict)
        """
        positive_prompts = []
        negative_prompts = []
        params = {}
        
        nodes = workflow_data.get("nodes", [])
        links = workflow_data.get("links", [])
        
        if not nodes:
            return None, None, {}
        
        node_map, link_map, input_connection_map = self._build_node_link_maps(nodes, links)
        
        clip_output_nodes = self._find_clip_output_nodes_workflow(node_map, input_connection_map)
        conditioning_nodes = self._find_conditioning_nodes_workflow(node_map, input_connection_map)
        
        for node in nodes:
            node_id = str(node.get("id", ""))
            node_type = node.get("type", "")
            
            if not self._is_text_encode_node(
                node, node_id, clip_output_nodes, conditioning_nodes, input_connection_map
            ):
                continue
            
            non_standard_types = {
                "WanVideoTextEncode", "WanVideoTextEncodeCached",
                "CogVideoTextEncode", "CogVideoTextEncodeCombined",
            }
            
            is_non_standard = any(t.lower() in node_type.lower() for t in non_standard_types)
            
            if is_non_standard:
                positive, negative = self._extract_text_from_non_standard_node(node)
                if positive:
                    positive_prompts.append(positive)
                if negative:
                    negative_prompts.append(negative)
            else:
                text = self._extract_text_from_node(
                    node, node_map, link_map, input_connection_map
                )
                
                if text:
                    is_negative = conditioning_nodes.get(node_id, {}).get("is_negative", False)
                    if is_negative:
                        negative_prompts.append(text)
                    else:
                        positive_prompts.append(text)
        
        params = self._extract_params_from_workflow(nodes, node_map)
        
        positive_prompt = "\n".join([p for p in positive_prompts if p]) if positive_prompts else None
        negative_prompt = "\n".join([p for p in negative_prompts if p]) if negative_prompts else None
        
        return positive_prompt, negative_prompt, params

    def _extract_params_from_workflow(self, nodes: list, node_map: dict) -> dict:
        """
        从 Workflow JSON 提取采样参数
        
        Args:
            nodes: 节点列表
            node_map: 节点映射
            
        Returns:
            参数字典
        """
        params = {}
        
        for node in nodes:
            node_type = node.get("type", "")
            widgets_values = node.get("widgets_values", [])
            
            if node_type in ["KSampler", "KSamplerAdvanced", "KSamplerAdvancedEfficient"]:
                if len(widgets_values) >= 6:
                    if params.get("seed") is None and isinstance(widgets_values[0], (int, float)):
                        params["seed"] = int(widgets_values[0])
                    if params.get("steps") is None and isinstance(widgets_values[2], (int, float)):
                        params["steps"] = widgets_values[2]
                    if params.get("cfg") is None and isinstance(widgets_values[3], (int, float)):
                        params["cfg"] = widgets_values[3]
                    if params.get("sampler") is None and isinstance(widgets_values[4], str):
                        params["sampler"] = widgets_values[4]
                    # KSampler 的 widgets_values 布局是
                    # [seed, control_after_generate, steps, cfg, sampler_name, scheduler, denoise]
                    if params.get("scheduler") is None and isinstance(widgets_values[5], str):
                        params["scheduler"] = widgets_values[5]
            
            elif node_type in ["CheckpointLoaderSimple", "CheckpointLoader", "UNETLoader", "CheckpointLoaderNF4"]:
                if params.get("model") is None and widgets_values:
                    model_name = widgets_values[0] if isinstance(widgets_values[0], str) else None
                    if model_name:
                        params["model"] = model_name

            # ---- 新式采样链（SamplerCustomAdvanced）----
            # 这类工作流没有 KSampler，参数被拆到几个独立节点上
            elif node_type in ["RandomNoise", "RandomNoiseNode"]:
                if params.get("seed") is None and widgets_values and isinstance(widgets_values[0], (int, float)):
                    params["seed"] = int(widgets_values[0])

            elif node_type in ["KSamplerSelect", "KSamplerSelectNode"]:
                if params.get("sampler") is None and widgets_values and isinstance(widgets_values[0], str):
                    params["sampler"] = widgets_values[0]

            elif node_type in ["BasicScheduler", "BasicSchedulerNode"]:
                # widgets_values = [scheduler, steps, denoise]
                if len(widgets_values) >= 2:
                    if params.get("scheduler") is None and isinstance(widgets_values[0], str):
                        params["scheduler"] = widgets_values[0]
                    if params.get("steps") is None and isinstance(widgets_values[1], (int, float)):
                        params["steps"] = widgets_values[1]

            elif node_type in ["CFGGuider", "DualCFGGuider"]:
                if params.get("cfg") is None and widgets_values and isinstance(widgets_values[0], (int, float)):
                    params["cfg"] = widgets_values[0]
        
        return params


gallery_scanner = GalleryScanner()
