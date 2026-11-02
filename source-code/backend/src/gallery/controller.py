"""
资产库控制器
提供资产库相关的 API 接口
"""

import json
import uuid
import shutil
import subprocess
import platform
import zipfile
import base64
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional

from flask import send_file, Response

from backend.src.utils.logger import app_logger as logger
from backend.src.utils.paths import get_data_dir
from backend.src.core.prompt_library import PromptLibraryService
from .storage import gallery_storage
from .scanner import gallery_scanner
from .models import Asset, AssetCategory


class GalleryController:
    """资产库控制器"""

    def __init__(self):
        self._data_dir = get_data_dir() / "gallery"
        self._thumbnails_dir = self._data_dir / "thumbnails"

    def gallery_get_assets(self) -> dict:
        """
        获取资产列表

        Returns:
            {
                "success": bool,
                "assets": list[dict],
                "categories": list[dict],
                "settings": dict
            }
        """
        try:
            assets = gallery_storage.get_assets()
            categories = gallery_storage.get_categories()
            settings = gallery_storage.get_settings()

            return {
                "success": True,
                "assets": [a.to_dict() for a in assets],
                "categories": [c.to_dict() for c in categories],
                "settings": settings.to_dict()
            }
        except Exception as e:
            logger.error(f"[GalleryController] 获取资产列表失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_get_asset(self, asset_id: str) -> dict:
        """
        获取单个资产详情

        Args:
            asset_id: 资产ID

        Returns:
            {
                "success": bool,
                "asset": dict | None
            }
        """
        try:
            asset = gallery_storage.get_asset_by_id(asset_id)
            if asset:
                return {"success": True, "asset": asset.to_dict()}
            return {"success": False, "error_message": "资产不存在"}
        except Exception as e:
            logger.error(f"[GalleryController] 获取资产详情失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_delete_asset(self, asset_id: str) -> dict:
        """
        删除资产（移动到系统回收站）

        Args:
            asset_id: 资产ID

        Returns:
            {
                "success": bool,
                "error_message": str (可选)
            }
        """
        try:
            asset = gallery_storage.get_asset_by_id(asset_id)
            if not asset:
                return {"success": False, "error_message": "资产不存在"}

            file_path = Path(asset.file_path)
            if file_path.exists():
                try:
                    import send2trash
                    send2trash.send2trash(str(file_path))
                    logger.info(f"[GalleryController] 已移动到回收站: {file_path}")
                except ImportError:
                    file_path.unlink()
                    logger.warning(f"[GalleryController] send2trash 未安装，直接删除文件: {file_path}")

            if asset.thumbnail_path:
                thumbnail_full_path = self._data_dir / asset.thumbnail_path
                if thumbnail_full_path.exists():
                    thumbnail_full_path.unlink()

            gallery_storage.delete_asset(asset_id)

            return {"success": True}
        except Exception as e:
            logger.error(f"[GalleryController] 删除资产失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_batch_delete(self, asset_ids: list[str]) -> dict:
        """
        批量删除资产

        Args:
            asset_ids: 资产ID列表

        Returns:
            {
                "success": bool,
                "deleted_count": int
            }
        """
        try:
            deleted_count = 0
            for asset_id in asset_ids:
                result = self.gallery_delete_asset(asset_id)
                if result.get("success"):
                    deleted_count += 1

            return {"success": True, "deleted_count": deleted_count}
        except Exception as e:
            logger.error(f"[GalleryController] 批量删除失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_toggle_favorite(self, asset_id: str) -> dict:
        """
        切换收藏状态

        Args:
            asset_id: 资产ID

        Returns:
            {
                "success": bool,
                "is_favorite": bool
            }
        """
        try:
            is_favorite = gallery_storage.toggle_favorite(asset_id)
            if is_favorite is not None:
                return {"success": True, "is_favorite": is_favorite}
            return {"success": False, "error_message": "资产不存在"}
        except Exception as e:
            logger.error(f"[GalleryController] 切换收藏状态失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_batch_favorite(self, asset_ids: list[str], favorite: bool) -> dict:
        """
        批量设置收藏状态

        Args:
            asset_ids: 资产ID列表
            favorite: 收藏状态

        Returns:
            {
                "success": bool,
                "updated_count": int
            }
        """
        try:
            count = gallery_storage.batch_toggle_favorite(asset_ids, favorite)
            return {"success": True, "updated_count": count}
        except Exception as e:
            logger.error(f"[GalleryController] 批量收藏失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_get_settings(self) -> dict:
        """
        获取设置

        Returns:
            {
                "success": bool,
                "settings": dict
            }
        """
        try:
            settings = gallery_storage.get_settings()
            return {"success": True, "settings": settings.to_dict()}
        except Exception as e:
            logger.error(f"[GalleryController] 获取设置失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_save_settings(self, library_path: str = None) -> dict:
        """
        保存设置

        Args:
            library_path: 资产库路径

        Returns:
            {
                "success": bool
            }
        """
        try:
            gallery_storage.update_settings(library_path=library_path)
            return {"success": True}
        except Exception as e:
            logger.error(f"[GalleryController] 保存设置失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_scan(self, library_path: str = None) -> dict:
        """
        扫描资产库目录

        Args:
            library_path: 要扫描的目录路径（可选，不传则使用已配置的路径）

        Returns:
            {
                "success": bool,
                "added": int,
                "updated": int,
                "removed": int,
                "errors": list[str]
            }
        """
        try:
            if library_path is None:
                settings = gallery_storage.get_settings()
                library_path = settings.library_path

            if not library_path:
                return {"success": False, "error_message": "未配置资产库路径"}

            result = gallery_scanner.scan_library(library_path)
            result["success"] = True
            return result
        except Exception as e:
            logger.error(f"[GalleryController] 扫描失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_incremental_scan(self, library_path: str = None) -> dict:
        """
        增量扫描资产库目录

        不清空现有数据，只处理新增、修改、删除的文件

        Args:
            library_path: 要扫描的目录路径（可选，不传则使用已配置的路径）

        Returns:
            {
                "success": bool,
                "added": int,
                "updated": int,
                "removed": int,
                "errors": list[str]
            }
        """
        try:
            if library_path is None:
                settings = gallery_storage.get_settings()
                library_path = settings.library_path

            if not library_path:
                return {"success": False, "error_message": "未配置资产库路径"}

            result = gallery_scanner.scan_library_incremental(library_path)
            result["success"] = True
            return result
        except Exception as e:
            return {"success": False, "error_message": str(e)}

    def gallery_get_workflow(self, asset_id: str) -> dict:
        """
        获取资产的工作流 JSON

        Args:
            asset_id: 资产ID

        Returns:
            {
                "success": bool,
                "workflow": dict | None
            }
        """
        try:
            asset = gallery_storage.get_asset_by_id(asset_id)
            if not asset:
                return {"success": False, "error_message": "资产不存在"}

            if not asset.has_workflow:
                return {"success": False, "error_message": "该资产不包含工作流"}

            file_path = Path(asset.file_path)
            if not file_path.exists():
                return {"success": False, "error_message": "文件不存在"}

            from PIL import Image
            with Image.open(file_path) as img:
                workflow_str = img.info.get("workflow")
                if workflow_str:
                    workflow = json.loads(workflow_str)
                    return {"success": True, "workflow": workflow}

            return {"success": False, "error_message": "无法提取工作流"}
        except Exception as e:
            logger.error(f"[GalleryController] 获取工作流失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_export_workflow(self, asset_id: str) -> dict:
        """
        导出工作流到工作流库

        Args:
            asset_id: 资产ID

        Returns:
            {
                "success": bool,
                "workflow_path": str
            }
        """
        try:
            logger.info(f"[GalleryController] 开始导出工作流到工作流库: {asset_id}")
            
            result = self.gallery_get_workflow(asset_id)
            if not result.get("success"):
                logger.warning(f"[GalleryController] 获取工作流失败: {result.get('error_message')}")
                return result

            workflow = result["workflow"]
            asset = gallery_storage.get_asset_by_id(asset_id)
            if not asset:
                logger.warning(f"[GalleryController] 资产不存在: {asset_id}")
                return {"success": False, "error_message": "资产不存在"}

            workflow_dir = get_data_dir() / "workflows"
            workflow_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"[GalleryController] 工作流目录: {workflow_dir}")

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            workflow_filename = f"{Path(asset.filename).stem}_{timestamp}.json"
            workflow_path = workflow_dir / workflow_filename

            with open(workflow_path, "w", encoding="utf-8") as f:
                json.dump(workflow, f, ensure_ascii=False, indent=2)

            logger.info(f"[GalleryController] 工作流已保存到: {workflow_path}")
            return {"success": True, "workflow_path": str(workflow_path)}
        except Exception as e:
            logger.error(f"[GalleryController] 导出工作流失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_export_workflow_to_path(self, asset_id: str, save_path: str) -> dict:
        """
        导出工作流到指定路径

        Args:
            asset_id: 资产ID
            save_path: 保存路径

        Returns:
            {
                "success": bool,
                "workflow_path": str
            }
        """
        try:
            logger.info(f"[GalleryController] 开始导出工作流到指定路径: {asset_id} -> {save_path}")
            
            result = self.gallery_get_workflow(asset_id)
            if not result.get("success"):
                logger.warning(f"[GalleryController] 获取工作流失败: {result.get('error_message')}")
                return result

            workflow = result["workflow"]
            workflow_path = Path(save_path)

            workflow_path.parent.mkdir(parents=True, exist_ok=True)

            with open(workflow_path, "w", encoding="utf-8") as f:
                json.dump(workflow, f, ensure_ascii=False, indent=2)

            logger.info(f"[GalleryController] 工作流已保存到: {workflow_path}")
            return {"success": True, "workflow_path": str(workflow_path)}
        except Exception as e:
            logger.error(f"[GalleryController] 导出工作流到指定路径失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_export_to_prompt_library(self, asset_id: str, force: bool = False) -> dict:
        """
        导出资产到提示词库

        将资产导出为提示词库中的一条记录，自动填充正/反向提示词、生成参数，
        图像（视频则用缩略图）作为预览图，分类归入"未分类"。

        Args:
            asset_id: 资产ID
            force: 资产未解析到提示词时仍要导入（只保留图片和参数）

        Returns:
            {
                "success": bool,
                "error_message": str (可选，错误码或错误信息),
                "prompt": dict (可选，创建成功的提示词数据)
            }
        """
        try:
            logger.info(f"[GalleryController] 开始导出资产到提示词库: {asset_id}")

            # 1. 获取资产数据
            asset = gallery_storage.get_asset_by_id(asset_id)
            if not asset:
                return {"success": False, "error_message": "资产不存在"}

            # 2. 提取提示词
            positive_prompt = (asset.prompt or "").strip()
            negative_prompt = (asset.negative_prompt or "").strip()

            # 3. 正反向都为空，返回特殊标记让前端弹窗确认
            if not positive_prompt and not negative_prompt and not force:
                logger.info(f"[GalleryController] 资产未解析到提示词，等待用户确认: {asset_id}")
                return {
                    "success": False,
                    "error_message": "no_prompt_detected",
                    "has_workflow": True
                }

            # 正向允许为空（只有反向提示词的资产不必硬塞到正向里）

            # 4. 读取预览图源文件
            # 图片直接用原图；视频没有可用的静态帧，用扫描时生成的缩略图
            file_path = Path(asset.file_path)
            if not file_path.exists():
                return {"success": False, "error_message": "原始文件不存在"}

            preview_source = file_path
            if asset.asset_type == "video":
                thumb_rel = (asset.thumbnail_path or "").strip()
                # thumbnail_path 存的是相对 POSIX 路径，按段拆开再拼，避免依赖 os.sep
                thumb_file = (
                    gallery_storage.thumbnails_dir.parent.joinpath(*thumb_rel.split("/"))
                    if thumb_rel else None
                )
                if thumb_file and thumb_file.exists():
                    preview_source = thumb_file
                else:
                    return {
                        "success": False,
                        "error_message": "视频缺少缩略图，无法作为预览图",
                    }

            with open(preview_source, "rb") as f:
                image_bytes = f.read()

            # 超过 5MB 时自动压缩
            MAX_SIZE = 5 * 1024 * 1024
            compressed_filename = preview_source.name

            if len(image_bytes) > MAX_SIZE:
                try:
                    from PIL import Image
                    from io import BytesIO

                    with Image.open(preview_source) as img:
                        # CMYK 需先转 RGB（直接转 RGBA 颜色会失真）
                        if img.mode == 'CMYK':
                            img = img.convert('RGB')
                        elif img.mode not in ('RGB', 'RGBA'):
                            img = img.convert('RGBA')

                        # 逐步降低 quality 直到满足大小限制
                        quality = 85
                        while quality >= 60:
                            output = BytesIO()
                            try:
                                img.save(output, format='WEBP', quality=quality)
                                compressed_bytes = output.getvalue()
                            finally:
                                output.close()

                            if len(compressed_bytes) <= MAX_SIZE:
                                break
                            quality -= 5

                        if len(compressed_bytes) > MAX_SIZE:
                            return {"success": False, "error_message": "图片压缩后仍超过5MB限制，无法作为预览图"}

                        image_bytes = compressed_bytes
                        compressed_filename = f"{preview_source.stem}.webp"
                        logger.info(f"[GalleryController] 图片已压缩为 WebP (quality={quality}): "
                                   f"{len(image_bytes) / 1024:.0f}KB")

                except Exception as e:
                    logger.error(f"[GalleryController] 图片压缩失败: {e}")
                    return {"success": False, "error_message": f"图片压缩失败: {str(e)}"}

            image_base64 = base64.b64encode(image_bytes).decode("utf-8")

            # 5. 使用 PromptLibraryService 保存预览图
            prompt_service = PromptLibraryService()
            try:
                preview_image_path = prompt_service.save_image(image_base64, compressed_filename)
            except ValueError as e:
                logger.warning(f"[GalleryController] 保存预览图失败: {e}")
                # 图片格式不支持时，不设预览图，继续创建
                preview_image_path = ""

            # 6. 查找或创建"未分类"分类
            category_id = self._ensure_uncategorized_category(prompt_service)

            # 7. 生成提示词名称（文件名去扩展名，如果重名加后缀）
            base_name = file_path.stem
            prompt_name = base_name
            suffix = 1
            existing_names = self._get_existing_prompt_names(prompt_service)
            while prompt_name in existing_names:
                suffix += 1
                prompt_name = f"{base_name}_{suffix}"

            # 8. 创建提示词
            try:
                new_prompt = prompt_service.create_prompt({
                    "name": prompt_name,
                    "positive_prompt": positive_prompt,
                    "negative_prompt": negative_prompt,
                    "category_id": category_id,
                    "preview_image": preview_image_path,
                    "remark": "从资产库导入",
                    "tags": list(asset.tags or []),
                    # 生成参数：决定这条配方能否被复现
                    "model": asset.model or "",
                    "sampler": asset.sampler or "",
                    "steps": asset.steps,
                    "cfg": asset.cfg,
                    "seed": asset.seed,
                    "width": asset.width,
                    "height": asset.height,
                    "duration": asset.duration,
                    "asset_type": asset.asset_type or "",
                    "source_asset_id": asset.id,
                }, allow_empty_positive=True)
                logger.info(f"[GalleryController] 导出到提示词库成功: {prompt_name}")
                return {"success": True, "prompt": new_prompt}
            except ValueError as e:
                logger.error(f"[GalleryController] 创建提示词失败: {e}")
                return {"success": False, "error_message": str(e)}

        except Exception as e:
            logger.error(f"[GalleryController] 导出到提示词库异常: {e}")
            return {"success": False, "error_message": str(e)}

    def _ensure_uncategorized_category(self, prompt_service: PromptLibraryService) -> str:
        """
        确保提示词库中存在"未分类"分类，不存在则创建

        Args:
            prompt_service: PromptLibraryService 实例

        Returns:
            str: "未分类"分类的 ID
        """
        categories = prompt_service.get_all_categories()
        for cat in categories:
            if cat.get("name") == "未分类" and not cat.get("is_system", False):
                return cat["id"]

        # 不存在则创建
        try:
            new_category = prompt_service.create_category({
                "name": "未分类",
                "icon": "folder",
                "parent_id": None
            })
            return new_category["id"]
        except ValueError:
            # 可能并发创建导致重名，再查一次
            categories = prompt_service.get_all_categories()
            for cat in categories:
                if cat.get("name") == "未分类":
                    return cat["id"]
            raise

    def _get_existing_prompt_names(self, prompt_service: PromptLibraryService) -> set:
        """获取提示词库中已有的名称集合"""
        prompts = prompt_service.get_all_prompts()
        return {p.get("name", "") for p in prompts}

    def gallery_open_location(self, asset_id: str) -> dict:
        """
        打开文件所在位置

        Args:
            asset_id: 资产ID

        Returns:
            {
                "success": bool
            }
        """
        try:
            asset = gallery_storage.get_asset_by_id(asset_id)
            if not asset:
                return {"success": False, "error_message": "资产不存在"}

            file_path = Path(asset.file_path)
            if not file_path.exists():
                return {"success": False, "error_message": "文件不存在"}

            if platform.system() == "Windows":
                subprocess.run(["explorer", "/select,", str(file_path)])
            elif platform.system() == "Darwin":
                subprocess.run(["open", "-R", str(file_path)])
            else:
                subprocess.run(["xdg-open", str(file_path.parent)])

            return {"success": True}
        except Exception as e:
            logger.error(f"[GalleryController] 打开文件位置失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_move_to_category(self, asset_ids: list[str], category_id: str = None) -> dict:
        """
        批量移动资产到分类（同时移动物理文件）

        Args:
            asset_ids: 资产ID列表
            category_id: 目标分类ID（null 表示移除分类）

        Returns:
            {
                "success": bool,
                "moved_count": int
            }
        """
        try:
            settings = gallery_storage.get_settings()
            library_path = settings.library_path
            if not library_path:
                return {"success": False, "error_message": "未配置资产库路径"}

            target_folder = None
            if category_id:
                category = gallery_storage.get_category_by_id(category_id)
                if category and category.folder_path:
                    target_folder = Path(library_path) / category.folder_path
                    target_folder.mkdir(parents=True, exist_ok=True)

            moved_count = 0
            for asset_id in asset_ids:
                asset = gallery_storage.get_asset_by_id(asset_id)
                if not asset:
                    continue

                source_path = Path(asset.file_path)
                if not source_path.exists():
                    continue

                if target_folder:
                    dest_path = target_folder / source_path.name
                    if dest_path.exists():
                        base_name = source_path.stem
                        suffix = source_path.suffix
                        counter = 1
                        while dest_path.exists():
                            dest_path = target_folder / f"{base_name}_{counter}{suffix}"
                            counter += 1

                    shutil.move(str(source_path), str(dest_path))
                    gallery_storage.update_asset(asset_id, file_path=str(dest_path), category_id=category_id)
                else:
                    gallery_storage.update_asset(asset_id, category_id=None)

                moved_count += 1

            return {"success": True, "moved_count": moved_count}
        except Exception as e:
            logger.error(f"[GalleryController] 移动分类失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_import(self, paths: list[str]) -> dict:
        """
        导入资产（文件/文件夹）

        Args:
            paths: 文件或文件夹路径列表

        Returns:
            {
                "success": bool,
                "imported_count": int,
                "errors": list[str]
            }
        """
        try:
            settings = gallery_storage.get_settings()
            library_path = settings.library_path
            if not library_path:
                return {"success": False, "error_message": "未配置资产库路径"}

            import_folder_name = datetime.now().strftime("%Y-%m-%d") + " 已导入"
            import_folder = Path(library_path) / import_folder_name
            import_folder.mkdir(parents=True, exist_ok=True)

            SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".webm"}

            imported_count = 0
            errors = []

            for source_path_str in paths:
                source_path = Path(source_path_str)

                if source_path.is_file():
                    if source_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                        dest_path = import_folder / source_path.name
                        if dest_path.exists():
                            base_name = source_path.stem
                            suffix = source_path.suffix
                            counter = 1
                            while dest_path.exists():
                                dest_path = import_folder / f"{base_name}_{counter}{suffix}"
                                counter += 1

                        shutil.move(str(source_path), str(dest_path))

                        category = gallery_storage.get_category_by_folder_path(import_folder_name)
                        category_id = category.id if category else None

                        asset = gallery_scanner._create_asset(dest_path, category_id)
                        if asset:
                            gallery_storage.add_asset(asset)
                            imported_count += 1
                    else:
                        errors.append(f"不支持的文件格式: {source_path.name}")

                elif source_path.is_dir():
                    for file_path in source_path.rglob("*"):
                        if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                            dest_path = import_folder / file_path.name
                            if dest_path.exists():
                                base_name = file_path.stem
                                suffix = file_path.suffix
                                counter = 1
                                while dest_path.exists():
                                    dest_path = import_folder / f"{base_name}_{counter}{suffix}"
                                    counter += 1

                            shutil.move(str(file_path), str(dest_path))

                            category = gallery_storage.get_category_by_folder_path(import_folder_name)
                            category_id = category.id if category else None

                            asset = gallery_scanner._create_asset(dest_path, category_id)
                            if asset:
                                gallery_storage.add_asset(asset)
                                imported_count += 1

            if imported_count > 0 and not gallery_storage.get_category_by_folder_path(import_folder_name):
                gallery_storage.add_category(name=import_folder_name, folder_path=import_folder_name)

            return {"success": True, "imported_count": imported_count, "errors": errors}
        except Exception as e:
            logger.error(f"[GalleryController] 导入失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_export_zip(self, asset_ids: list[str]) -> dict:
        """
        导出选中资产为 ZIP

        Args:
            asset_ids: 资产ID列表

        Returns:
            {
                "success": bool,
                "zip_path": str
            }
        """
        try:
            if not asset_ids:
                return {"success": False, "error_message": "未选择资产"}

            export_dir = get_data_dir() / "exports"
            export_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_filename = f"assets_{timestamp}.zip"
            zip_path = export_dir / zip_filename

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for asset_id in asset_ids:
                    asset = gallery_storage.get_asset_by_id(asset_id)
                    if not asset:
                        continue

                    file_path = Path(asset.file_path)
                    if file_path.exists():
                        zipf.write(file_path, file_path.name)

            return {"success": True, "zip_path": str(zip_path)}
        except Exception as e:
            logger.error(f"[GalleryController] 导出 ZIP 失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_get_categories(self) -> dict:
        """
        获取分类列表

        Returns:
            {
                "success": bool,
                "categories": list[dict]
            }
        """
        try:
            categories = gallery_storage.get_categories()
            return {"success": True, "categories": [c.to_dict() for c in categories]}
        except Exception as e:
            logger.error(f"[GalleryController] 获取分类失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_create_category(self, name: str, parent_id: str = None) -> dict:
        """
        创建分类（同时创建物理文件夹）

        Args:
            name: 分类名称
            parent_id: 父分类ID

        Returns:
            {
                "success": bool,
                "category": dict
            }
        """
        try:
            settings = gallery_storage.get_settings()
            library_path = settings.library_path

            # 构建文件夹路径
            if parent_id:
                parent_category = gallery_storage.get_category_by_id(parent_id)
                if parent_category and parent_category.folder_path:
                    folder_path = f"{parent_category.folder_path}/{name}"
                else:
                    folder_path = name
            else:
                folder_path = name

            if library_path:
                folder_full_path = Path(library_path) / folder_path
                folder_full_path.mkdir(parents=True, exist_ok=True)

            category = gallery_storage.add_category(name, parent_id, folder_path)
            return {"success": True, "category": category.to_dict()}
        except Exception as e:
            logger.error(f"[GalleryController] 创建分类失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_update_category(self, category_id: str, name: str = None) -> dict:
        """
        更新分类（同时重命名物理文件夹）

        Args:
            category_id: 分类ID
            name: 新名称

        Returns:
            {
                "success": bool,
                "category": dict
            }
        """
        try:
            category = gallery_storage.get_category_by_id(category_id)
            if not category:
                return {"success": False, "error_message": "分类不存在"}

            if name and category.folder_path:
                settings = gallery_storage.get_settings()
                library_path = settings.library_path

                if library_path:
                    old_folder = Path(library_path) / category.folder_path
                    new_folder = Path(library_path) / name

                    if old_folder.exists() and old_folder != new_folder:
                        old_folder.rename(new_folder)

                        for asset in gallery_storage.get_assets():
                            if asset.category_id == category_id:
                                old_path = Path(asset.file_path)
                                if old_path.exists():
                                    new_path = new_folder / old_path.name
                                    gallery_storage.update_asset(asset.id, file_path=str(new_path))

                category = gallery_storage.update_category(category_id, name, name)

            return {"success": True, "category": category.to_dict() if category else None}
        except Exception as e:
            logger.error(f"[GalleryController] 更新分类失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_get_category_content_info(self, category_id: str) -> dict:
        """
        获取分类内容信息

        Args:
            category_id: 分类ID

        Returns:
            {
                "success": bool,
                "asset_count": int,
                "child_ids": list,
                "child_count": int
            }
        """
        try:
            info = gallery_storage.get_category_content_info(category_id)
            return {"success": True, **info}
        except Exception as e:
            logger.error(f"[GalleryController] 获取分类内容信息失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_delete_category(self, category_id: str, cascade: bool = True) -> dict:
        """
        删除分类

        Args:
            category_id: 分类ID
            cascade: 是否级联删除（包括子分类和资产）

        Returns:
            {
                "success": bool,
                "deleted_categories": int,  # 仅 cascade=True 时返回
                "deleted_assets": int       # 仅 cascade=True 时返回
            }
        """
        try:
            if cascade:
                result = gallery_storage.delete_category_cascade(category_id)
                return result
            else:
                success = gallery_storage.delete_category(category_id)
                if success:
                    return {"success": True}
                return {"success": False, "error_message": "无法删除系统分类或分类不存在"}
        except Exception as e:
            logger.error(f"[GalleryController] 删除分类失败：{e}")
            return {"success": False, "error_message": str(e)}

    def gallery_get_thumbnail(self, asset_id: str) -> Optional[Response]:
        """
        获取资产缩略图

        Args:
            asset_id: 资产 ID

        Returns:
            Flask Response 对象（缩略图文件）或 None
        """
        try:
            asset = gallery_storage.get_asset_by_id(asset_id)
            if not asset:
                logger.warning(f"[GalleryController] 资产不存在：{asset_id}")
                return None

            # 优先使用缩略图，如果没有则使用原图
            thumbnail_path = asset.thumbnail_path
            if not thumbnail_path:
                file_path = Path(asset.file_path)
            else:
                file_path = self._data_dir / thumbnail_path

            if not file_path.exists():
                logger.warning(f"[GalleryController] 文件不存在：{file_path}")
                return None

            # 根据文件扩展名确定 MIME 类型
            ext = file_path.suffix.lower()
            mimetype_map = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.webp': 'image/webp',
                '.gif': 'image/gif'
            }
            mimetype = mimetype_map.get(ext, 'image/jpeg')

            return send_file(str(file_path), mimetype=mimetype)
        except Exception as e:
            logger.error(f"[GalleryController] 获取缩略图失败：{e}")
            return None

    def gallery_get_asset_file(self, asset_id: str) -> Optional[Response]:
        """
        获取资产原图文件

        Args:
            asset_id: 资产 ID

        Returns:
            Flask Response 对象（原图文件）或 None
        """
        try:
            asset = gallery_storage.get_asset_by_id(asset_id)
            if not asset:
                logger.warning(f"[GalleryController] 资产不存在：{asset_id}")
                return None

            file_path = Path(asset.file_path)
            if not file_path.exists():
                logger.warning(f"[GalleryController] 原图文件不存在：{file_path}")
                return None

            ext = file_path.suffix.lower()
            mimetype_map = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.webp': 'image/webp',
                '.gif': 'image/gif',
                '.mp4': 'video/mp4',
                '.webm': 'video/webm'
            }
            mimetype = mimetype_map.get(ext, 'application/octet-stream')

            is_video = ext in ['.mp4', '.webm']
            
            return send_file(
                str(file_path),
                mimetype=mimetype,
                conditional=is_video
            )
        except Exception as e:
            logger.error(f"[GalleryController] 获取原图失败：{e}")
            return None

    def gallery_get_nsfw_status(self) -> dict:
        """
        获取 NSFW 分级状态

        Returns:
            {
                "success": bool,
                "model_available": bool,
                "nsfw_auto_classify": bool,
                "nsfw_threshold": float,
                "is_scanning": bool,
                "is_paused": bool
            }
        """
        try:
            from .nsfw.service import NSFWClassifyService
            
            service = NSFWClassifyService()
            settings = gallery_storage.get_settings()
            
            return {
                "success": True,
                "model_available": service.is_available(),
                "nsfw_auto_classify": settings.nsfw_auto_classify,
                "nsfw_threshold": settings.nsfw_threshold,
                "nsfw_auto_blur": settings.nsfw_auto_blur,
                "is_scanning": service.is_scanning(),
                "is_paused": service.is_paused()
            }
        except Exception as e:
            logger.error(f"[GalleryController] 获取 NSFW 状态失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_set_nsfw_enabled(self, enabled: bool) -> dict:
        """
        设置 NSFW 自动分级开关

        Args:
            enabled: 是否启用

        Returns:
            {
                "success": bool
            }
        """
        try:
            gallery_storage.update_nsfw_settings(nsfw_auto_classify=enabled)
            logger.info(f"[GalleryController] NSFW 自动分级已{'开启' if enabled else '关闭'}")
            return {"success": True}
        except Exception as e:
            logger.error(f"[GalleryController] 设置 NSFW 开关失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_set_nsfw_threshold(self, threshold: float) -> dict:
        """
        设置 NSFW 分级阈值

        Args:
            threshold: 阈值 (0.0-1.0)

        Returns:
            {
                "success": bool
            }
        """
        try:
            threshold = max(0.0, min(1.0, threshold))
            gallery_storage.update_nsfw_settings(nsfw_threshold=threshold)
            logger.info(f"[GalleryController] NSFW 阈值已设置为: {threshold}")
            return {"success": True}
        except Exception as e:
            logger.error(f"[GalleryController] 设置 NSFW 阈值失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_set_nsfw_auto_blur(self, enabled: bool) -> dict:
        """
        设置 NSFW 自动模糊开关

        Args:
            enabled: 是否启用

        Returns:
            {
                "success": bool
            }
        """
        try:
            gallery_storage.update_nsfw_settings(nsfw_auto_blur=enabled)
            logger.info(f"[GalleryController] NSFW 自动模糊已{'开启' if enabled else '关闭'}")
            return {"success": True}
        except Exception as e:
            logger.error(f"[GalleryController] 设置 NSFW 自动模糊失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_classify_all_images(self) -> dict:
        """
        对所有图片进行 NSFW 分级（全量扫描）

        Returns:
            {
                "success": bool,
                "total": int,
                "classified": int,
                "errors": list[str]
            }
        """
        try:
            from .nsfw.service import NSFWClassifyService
            
            service = NSFWClassifyService()
            
            if not service.is_available():
                return {"success": False, "error_message": "NSFW 模型不可用"}
            
            if service.is_scanning():
                return {"success": False, "error_message": "已有扫描任务在运行"}
            
            settings = gallery_storage.get_settings()
            threshold = settings.nsfw_threshold
            
            assets = gallery_storage.get_assets()
            image_assets = [a for a in assets if a.asset_type == "image"]
            
            if not image_assets:
                return {"success": True, "total": 0, "classified": 0, "errors": []}
            
            total = len(image_assets)
            classified_count = [0]
            errors = []
            
            def on_result(asset_path: str, result):
                asset = gallery_storage.get_asset_by_id(
                    next((a.id for a in image_assets if a.file_path == asset_path), None)
                )
                if asset:
                    gallery_storage.update_asset_nsfw(
                        asset.id,
                        nsfw_score=result.nsfw_score,
                        nsfw_label=result.nsfw_label,
                        tags=result.tags
                    )
                    classified_count[0] += 1
            
            def on_complete(results):
                logger.info(f"[GalleryController] NSFW 全量扫描完成: {classified_count[0]}/{total}")
            
            image_paths = [a.file_path for a in image_assets]
            
            service.start_batch_scan(
                image_paths=image_paths,
                threshold=threshold,
                result_callback=on_result,
                complete_callback=on_complete
            )
            
            return {
                "success": True,
                "total": total,
                "message": f"已开始扫描 {total} 张图片"
            }
        except Exception as e:
            logger.error(f"[GalleryController] NSFW 全量扫描失败: {e}", exc_info=True)
            return {"success": False, "error_message": str(e)}

    def gallery_pause_nsfw_scan(self) -> dict:
        """
        暂停 NSFW 扫描

        Returns:
            {
                "success": bool
            }
        """
        try:
            from .nsfw.service import NSFWClassifyService
            
            service = NSFWClassifyService()
            service.pause_scan()
            return {"success": True}
        except Exception as e:
            logger.error(f"[GalleryController] 暂停 NSFW 扫描失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_resume_nsfw_scan(self) -> dict:
        """
        恢复 NSFW 扫描

        Returns:
            {
                "success": bool
            }
        """
        try:
            from .nsfw.service import NSFWClassifyService
            
            service = NSFWClassifyService()
            service.resume_scan()
            return {"success": True}
        except Exception as e:
            logger.error(f"[GalleryController] 恢复 NSFW 扫描失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_cancel_nsfw_scan(self) -> dict:
        """
        取消 NSFW 扫描

        Returns:
            {
                "success": bool
            }
        """
        try:
            from .nsfw.service import NSFWClassifyService
            
            service = NSFWClassifyService()
            service.cancel_scan()
            return {"success": True}
        except Exception as e:
            logger.error(f"[GalleryController] 取消 NSFW 扫描失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_start_background_scan(self, library_path: str = None) -> dict:
        """
        启动后台扫描

        Args:
            library_path: 要扫描的目录路径（可选，不传则使用已配置的路径）

        Returns:
            {
                "success": bool,
                "message": str
            }
        """
        try:
            if library_path is None:
                settings = gallery_storage.get_settings()
                library_path = settings.library_path

            if not library_path:
                return {"success": False, "error_message": "未配置资产库路径"}

            result = gallery_scanner.start_background_scan(library_path)
            return result
        except Exception as e:
            logger.error(f"[GalleryController] 启动后台扫描失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_get_scan_status(self) -> dict:
        """
        获取扫描状态

        Returns:
            {
                "success": bool,
                "scanning": bool,
                "stopping": bool,
                "progress": dict | None
            }
        """
        try:
            return {
                "success": True,
                "scanning": gallery_scanner.is_scanning(),
                "stopping": gallery_scanner.is_stopping(),
                "progress": gallery_scanner.get_scan_progress()
            }
        except Exception as e:
            logger.error(f"[GalleryController] 获取扫描状态失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_stop_scan(self) -> dict:
        """
        停止扫描

        Returns:
            {
                "success": bool
            }
        """
        try:
            gallery_scanner.stop_scan()
            return {"success": True}
        except Exception as e:
            logger.error(f"[GalleryController] 停止扫描失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_update_preview_blurred(self, asset_id: str, blurred: bool) -> dict:
        """
        更新资产的模糊预览状态

        Args:
            asset_id: 资产 ID
            blurred: 是否模糊

        Returns:
            {
                "success": bool,
                "asset": dict | None
            }
        """
        try:
            asset = gallery_storage.update_asset_preview_blurred(asset_id, blurred)
            if asset:
                return {
                    "success": True,
                    "asset": asset.to_dict()
                }
            return {"success": False, "error_message": "资产不存在"}
        except Exception as e:
            logger.error(f"[GalleryController] 更新模糊预览状态失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_update_asset_info(
        self,
        asset_id: str,
        filename: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        rating: Optional[int] = None
    ) -> dict:
        """
        更新资产的基本信息

        Args:
            asset_id: 资产 ID
            filename: 新文件名（不含扩展名）
            description: 备注
            tags: 标签列表
            rating: 评分 (0-5)

        Returns:
            {
                "success": bool,
                "asset": dict | None,
                "error_message": str | None
            }
        """
        try:
            asset = gallery_storage.update_asset_info(asset_id, filename, description, tags, rating)
            if asset:
                return {
                    "success": True,
                    "asset": asset.to_dict()
                }
            return {"success": False, "error_message": "资产不存在或重命名失败"}
        except Exception as e:
            logger.error(f"[GalleryController] 更新资产信息失败: {e}")
            return {"success": False, "error_message": str(e)}

    def gallery_push_image_to_comfyui(self, asset_id: str, port: int = 8188) -> dict:
        """
        推送图片到 ComfyUI 的 LoadImage 节点

        Args:
            asset_id: 资产 ID
            port: ComfyUI 端口号

        Returns:
            {
                "success": bool,
                "filename": str,
                "error_message": str
            }
        """
        try:
            asset = gallery_storage.get_asset_by_id(asset_id)
            if not asset:
                return {"success": False, "error_message": "资产不存在"}

            file_path = Path(asset.file_path)
            if not file_path.exists():
                return {"success": False, "error_message": "文件不存在"}

            if file_path.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.webp', '.gif'}:
                return {"success": False, "error_message": "不支持的图片格式"}

            upload_url = f"http://127.0.0.1:{port}/upload/image"

            with open(file_path, 'rb') as f:
                files = {'image': (file_path.name, f, 'image/png')}
                data = {'overwrite': 'true'}
                response = requests.post(upload_url, files=files, data=data, timeout=10)

            if response.status_code == 200:
                result = response.json()
                filename = result.get('name', file_path.name)
                logger.info(f"[GalleryController] 图片已上传到 ComfyUI: {filename}")
                return {"success": True, "filename": filename}
            else:
                error_msg = f"ComfyUI 返回错误: {response.status_code}"
                logger.error(f"[GalleryController] {error_msg}")
                return {"success": False, "error_message": error_msg}

        except requests.exceptions.ConnectionError:
            return {"success": False, "error_message": "无法连接到 ComfyUI，请确认 ComfyUI 已启动"}
        except Exception as e:
            logger.error(f"[GalleryController] 推送图片到 ComfyUI 失败: {e}")
            return {"success": False, "error_message": str(e)}


gallery_controller = GalleryController()
