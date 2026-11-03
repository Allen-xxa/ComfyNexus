"""
资产库存储服务
负责 assets.json 的读写操作
"""

import json
import uuid
import shutil
import threading
from pathlib import Path
from typing import Optional
from datetime import datetime

from backend.src.utils.paths import get_data_dir
from backend.src.utils.logger import app_logger as logger
from .models import GalleryData, GallerySettings, AssetCategory, Asset


class GalleryStorage:
    """资产库存储服务"""

    def __init__(self):
        self._data_dir = get_data_dir() / "gallery"
        self._assets_file = self._data_dir / "assets.json"
        self._thumbnails_dir = self._data_dir / "thumbnails"
        self._data: Optional[GalleryData] = None
        self._lock = threading.Lock()

    def _ensure_dirs(self):
        """确保目录存在"""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._thumbnails_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> GalleryData:
        """加载资产库数据"""
        if self._data is not None:
            return self._data

        with self._lock:
            # 双重检查：拿到锁后再检查一次，避免重复加载
            if self._data is not None:
                return self._data

            self._ensure_dirs()

            if self._assets_file.exists():
                try:
                    with open(self._assets_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self._data = GalleryData.from_dict(data)
                    logger.info(f"[GalleryStorage] 加载资产库数据: {len(self._data.assets)} 个资产, {len(self._data.categories)} 个分类")
                except Exception as e:
                    logger.error(f"[GalleryStorage] 加载资产库数据失败: {e}")
                    self._data = self._create_default_data()
            else:
                logger.info("[GalleryStorage] 资产库数据文件不存在，创建默认数据")
                self._data = self._create_default_data()
                self.save()

            return self._data

    def save(self) -> bool:
        """保存资产库数据"""
        if self._data is None:
            return False

        self._ensure_dirs()

        try:
            with open(self._assets_file, "w", encoding="utf-8") as f:
                json.dump(self._data.to_dict(), f, ensure_ascii=False, indent=2)
            logger.info("[GalleryStorage] 保存资产库数据成功")
            return True
        except Exception as e:
            logger.error(f"[GalleryStorage] 保存资产库数据失败: {e}")
            return False

    def _create_default_data(self) -> GalleryData:
        """创建默认数据"""
        return GalleryData(
            version="1.0",
            settings=GallerySettings(library_path=""),
            categories=[
                AssetCategory(id="all", name="全部", is_system=True, sort_order=0),
                AssetCategory(id="favorites", name="收藏", is_system=True, sort_order=1),
            ],
            assets=[]
        )

    def get_settings(self) -> GallerySettings:
        """获取设置"""
        data = self.load()
        return data.settings

    def update_settings(self, library_path: Optional[str] = None, last_scan_time: Optional[str] = None) -> bool:
        """更新设置"""
        data = self.load()
        if library_path is not None:
            data.settings.library_path = library_path
        if last_scan_time is not None:
            data.settings.last_scan_time = last_scan_time
        else:
            data.settings.last_scan_time = datetime.now().isoformat()
        return self.save()

    def update_nsfw_settings(
        self,
        nsfw_auto_classify: Optional[bool] = None,
        nsfw_threshold: Optional[float] = None,
        nsfw_auto_blur: Optional[bool] = None
    ) -> bool:
        """更新 NSFW 分级设置"""
        data = self.load()
        if nsfw_auto_classify is not None:
            data.settings.nsfw_auto_classify = nsfw_auto_classify
        if nsfw_threshold is not None:
            data.settings.nsfw_threshold = nsfw_threshold
        if nsfw_auto_blur is not None:
            data.settings.nsfw_auto_blur = nsfw_auto_blur
        return self.save()

    def clear_all_data(self) -> bool:
        """清空所有资产和分类数据（保留设置和系统分类）"""
        data = self.load()
        data.assets = []
        data.categories = [c for c in data.categories if c.is_system]
        # logger.info("[GalleryStorage] 已清空资产和分类数据")
        return self.save()

    def update_asset_nsfw(
        self,
        asset_id: str,
        nsfw_score: Optional[float] = None,
        nsfw_label: Optional[str] = None,
        tags: Optional[list[str]] = None
    ) -> Optional[Asset]:
        """更新单个资产的 NSFW 分级结果"""
        data = self.load()
        for asset in data.assets:
            if asset.id == asset_id:
                if nsfw_score is not None:
                    asset.nsfw_score = nsfw_score
                if nsfw_label is not None:
                    asset.nsfw_label = nsfw_label
                if tags is not None:
                    asset.tags = tags
                self.save()
                return asset
        return None

    def batch_update_nsfw_labels(
        self,
        updates: list[dict]
    ) -> int:
        """
        批量更新资产的 NSFW 分级结果
        
        Args:
            updates: 更新列表，每项包含 {"asset_id": str, "nsfw_score": float, "nsfw_label": str, "tags": list}
            
        Returns:
            更新成功的资产数量
        """
        data = self.load()
        asset_map = {a.id: a for a in data.assets}
        count = 0
        
        for update in updates:
            asset_id = update.get("asset_id")
            if asset_id and asset_id in asset_map:
                asset = asset_map[asset_id]
                if "nsfw_score" in update:
                    asset.nsfw_score = update["nsfw_score"]
                if "nsfw_label" in update:
                    asset.nsfw_label = update["nsfw_label"]
                if "tags" in update:
                    asset.tags = update["tags"]
                count += 1
        
        if count > 0:
            self.save()
        return count

    def get_categories(self) -> list[AssetCategory]:
        """获取分类列表"""
        data = self.load()
        return data.categories

    def add_category(self, name: str, parent_id: Optional[str] = None, folder_path: Optional[str] = None) -> AssetCategory:
        """添加分类"""
        data = self.load()
        category = AssetCategory(
            id=f"cat-{uuid.uuid4().hex[:8]}",
            name=name,
            is_system=False,
            parent_id=parent_id,
            sort_order=len([c for c in data.categories if not c.is_system]),
            folder_path=folder_path
        )
        data.categories.append(category)
        self.save()
        return category

    def update_category(
        self,
        category_id: str,
        name: Optional[str] = None,
        folder_path: Optional[str] = None,
        parent_id: Optional[str] = None
    ) -> Optional[AssetCategory]:
        """更新分类"""
        data = self.load()
        for category in data.categories:
            if category.id == category_id:
                if name is not None:
                    category.name = name
                if folder_path is not None:
                    category.folder_path = folder_path
                if parent_id is not None:
                    category.parent_id = parent_id or None
                self.save()
                return category
        return None

    def relocate_category(
        self,
        category_id: str,
        new_folder_path: str,
        new_parent_id: Optional[str],
        new_name: Optional[str] = None
    ) -> dict:
        """
        分类换了物理位置之后，重写整棵子树的记账路径。

        调用方负责磁盘目录已经移动到位；这里只改 assets.json，并且只在最后落盘一次
        （逐个 update_asset 会把整个 JSON 重写 N 遍）。

        Args:
            category_id: 被移动/重命名的分类
            new_folder_path: 移动后的相对路径，用 "/" 分隔；None 表示该分类没有物理目录
            new_parent_id: 新的父分类 ID，"" 或 None 表示移到根级
            new_name: 新的显示名（重命名时传入）

        Returns:
            {
                "success": bool,
                "moved_categories": int,
                "moved_assets": int,
                "error_message": str  # 仅失败时
            }
        """
        data = self.load()
        try:
            category = next((c for c in data.categories if c.id == category_id), None)
            if not category:
                return {"success": False, "error_message": "分类不存在", "moved_categories": 0, "moved_assets": 0}

            old_folder_path = category.folder_path
            library_path = data.settings.library_path

            affected_ids = [category_id]
            if old_folder_path:
                prefix = f"{old_folder_path}/"
                for other in data.categories:
                    if other.folder_path and other.folder_path.startswith(prefix):
                        affected_ids.append(other.id)
            affected_set = set(affected_ids)

            moved_categories = 0
            if new_folder_path is not None and old_folder_path:
                new_prefix = f"{new_folder_path}/"
                for other in data.categories:
                    if other.id == category_id:
                        other.folder_path = new_folder_path
                        other.parent_id = new_parent_id or None
                        if new_name is not None:
                            other.name = new_name
                        moved_categories += 1
                    elif other.folder_path and other.folder_path.startswith(f"{old_folder_path}/"):
                        other.folder_path = new_prefix + other.folder_path[len(prefix):]
                        moved_categories += 1
            else:
                category.parent_id = new_parent_id or None
                if new_name is not None:
                    category.name = new_name
                moved_categories = 1

            moved_assets = 0
            moved_asset_paths: list[dict] = []
            if old_folder_path and new_folder_path and library_path:
                old_dir = Path(library_path) / old_folder_path
                new_dir = Path(library_path) / new_folder_path
                for asset in data.assets:
                    if asset.category_id not in affected_set:
                        continue
                    try:
                        rel = Path(asset.file_path).relative_to(old_dir)
                    except ValueError:
                        continue
                    asset.file_path = str(new_dir / rel)
                    moved_assets += 1
                    moved_asset_paths.append({"id": asset.id, "filePath": asset.file_path})

            self.save()
            return {
                "success": True,
                "moved_categories": moved_categories,
                "moved_assets": moved_assets,
                "asset_paths": moved_asset_paths
            }
        except Exception as e:
            logger.error(f"[GalleryStorage] 重定位分类失败: {e}")
            self._data = None
            return {"success": False, "error_message": str(e), "moved_categories": 0, "moved_assets": 0}

    def get_category_by_id(self, category_id: str) -> Optional[AssetCategory]:
        """根据 ID 获取分类"""
        data = self.load()
        for category in data.categories:
            if category.id == category_id:
                return category
        return None

    def get_category_by_folder_path(self, folder_path: str) -> Optional[AssetCategory]:
        """根据文件夹路径获取分类"""
        data = self.load()
        for category in data.categories:
            if category.folder_path == folder_path:
                return category
        return None

    def delete_category(self, category_id: str) -> bool:
        """删除分类"""
        data = self.load()
        for i, category in enumerate(data.categories):
            if category.id == category_id and not category.is_system:
                data.categories.pop(i)
                for asset in data.assets:
                    if asset.category_id == category_id:
                        asset.category_id = None
                self.save()
                return True
        return False

    def remove_category_promote_children(
        self,
        category_id: str,
        new_parent_id: Optional[str],
        new_prefix: str,
        library_path: Optional[str],
        assets_target_category_id: Optional[str] = None
    ) -> dict:
        """
        删除一个分类，但保留它的子分类：子分类整体上浮一级，直属资产跟着文件一起归到上级分类。

        调用方已经把磁盘目录内容上移；这里把 assets.json 对上新的层级，只落盘一次。

        Returns:
            {"success": bool, "removed_categories": int, "reparented_children": int,
             "orphaned_assets": int, "moved_assets": int, "error_message": str}
        """
        data = self.load()
        try:
            category = next((c for c in data.categories if c.id == category_id), None)
            if not category:
                return {"success": False, "error_message": "分类不存在"}

            removed_folder_path = category.folder_path
            old_ids = {category_id}

            moved_assets = 0
            moved_asset_paths: list[dict] = []
            if removed_folder_path:
                old_full = f"{removed_folder_path}/"
                prefix = f"{new_prefix}/" if new_prefix else ""
                for other in data.categories:
                    if other.folder_path and other.folder_path.startswith(old_full):
                        other.folder_path = prefix + other.folder_path[len(old_full):]
                if library_path:
                    old_dir = Path(library_path) / removed_folder_path
                    new_dir = Path(library_path) / new_prefix if new_prefix else Path(library_path)
                    for asset in data.assets:
                        try:
                            rel = Path(asset.file_path).relative_to(old_dir)
                        except ValueError:
                            continue
                        asset.file_path = str(new_dir / rel)
                        moved_assets += 1
                        moved_asset_paths.append({"id": asset.id, "filePath": asset.file_path})

            orphaned_assets = 0
            for asset in data.assets:
                if asset.category_id == category_id:
                    asset.category_id = assets_target_category_id
                    orphaned_assets += 1
                    moved_asset_paths.append({
                        "id": asset.id,
                        "filePath": asset.file_path,
                        "categoryId": assets_target_category_id
                    })

            reparented_children = 0
            for other in data.categories:
                if other.parent_id == category_id:
                    other.parent_id = new_parent_id
                    reparented_children += 1

            data.categories = [c for c in data.categories if c.id not in old_ids]
            self.save()
            return {
                "success": True,
                "removed_categories": 1,
                "reparented_children": reparented_children,
                "orphaned_assets": orphaned_assets,
                "moved_assets": moved_assets,
                "asset_paths": moved_asset_paths
            }
        except Exception as e:
            logger.error(f"[GalleryStorage] 删除分类并上浮子分类失败: {e}")
            return {"success": False, "error_message": str(e)}

    def get_category_content_info(self, category_id: str) -> dict:
        """获取分类内容信息（资产数量、子分类ID列表）"""
        data = self.load()
        
        asset_count = sum(1 for a in data.assets if a.category_id == category_id)
        child_ids = [c.id for c in data.categories if c.parent_id == category_id]
        
        return {
            "asset_count": asset_count,
            "child_ids": child_ids,
            "child_count": len(child_ids)
        }

    def get_assets(self) -> list[Asset]:
        """获取资产列表"""
        data = self.load()
        return data.assets

    def get_asset_by_id(self, asset_id: str) -> Optional[Asset]:
        """根据 ID 获取资产"""
        data = self.load()
        for asset in data.assets:
            if asset.id == asset_id:
                return asset
        return None

    def add_asset(self, asset: Asset) -> bool:
        """添加资产"""
        data = self.load()
        data.assets.append(asset)
        return self.save()

    def update_asset(self, asset_id: str, **kwargs) -> Optional[Asset]:
        """更新资产"""
        data = self.load()
        for asset in data.assets:
            if asset.id == asset_id:
                for key, value in kwargs.items():
                    if hasattr(asset, key):
                        setattr(asset, key, value)
                self.save()
                return asset
        return None

    def delete_asset(self, asset_id: str) -> bool:
        """删除资产（从数据中移除）"""
        data = self.load()
        for i, asset in enumerate(data.assets):
            if asset.id == asset_id:
                data.assets.pop(i)
                self.save()
                return True
        return False

    def toggle_favorite(self, asset_id: str) -> Optional[bool]:
        """切换收藏状态"""
        data = self.load()
        for asset in data.assets:
            if asset.id == asset_id:
                asset.is_favorite = not asset.is_favorite
                self.save()
                return asset.is_favorite
        return None

    def update_asset_preview_blurred(self, asset_id: str, blurred: bool) -> Optional[Asset]:
        """更新资产的模糊预览状态"""
        data = self.load()
        for asset in data.assets:
            if asset.id == asset_id:
                asset.preview_blurred = blurred
                self.save()
                return asset
        return None

    def update_asset_info(
        self,
        asset_id: str,
        filename: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        rating: Optional[int] = None
    ) -> Optional[Asset]:
        """更新资产的基本信息（文件名、备注、标签、评分）"""
        data = self.load()
        for asset in data.assets:
            if asset.id == asset_id:
                if filename is not None:
                    import os
                    old_path = asset.file_path
                    dir_path = os.path.dirname(old_path)
                    ext = os.path.splitext(old_path)[1]
                    new_path = os.path.join(dir_path, filename + ext)
                    
                    if os.path.exists(old_path) and not os.path.exists(new_path):
                        try:
                            os.rename(old_path, new_path)
                            asset.filename = filename + ext
                            asset.file_path = new_path
                        except Exception as e:
                            logger.error(f"[GalleryStorage] 重命名文件失败: {e}")
                            return None
                
                if description is not None:
                    asset.description = description
                
                if tags is not None:
                    asset.tags = tags
                
                if rating is not None:
                    asset.rating = max(0, min(5, rating))
                
                self.save()
                return asset
        return None

    def batch_toggle_favorite(self, asset_ids: list[str], favorite: bool) -> int:
        """批量设置收藏状态"""
        data = self.load()
        count = 0
        for asset in data.assets:
            if asset.id in asset_ids:
                asset.is_favorite = favorite
                count += 1
        if count > 0:
            self.save()
        return count

    def batch_delete_assets(self, asset_ids: list[str]) -> int:
        """批量删除资产"""
        data = self.load()
        original_count = len(data.assets)
        data.assets = [a for a in data.assets if a.id not in asset_ids]
        deleted_count = original_count - len(data.assets)
        if deleted_count > 0:
            self.save()
        return deleted_count

    def move_assets_to_category(self, asset_ids: list[str], category_id: Optional[str]) -> int:
        """批量移动资产到分类"""
        data = self.load()
        count = 0
        for asset in data.assets:
            if asset.id in asset_ids:
                asset.category_id = category_id
                count += 1
        if count > 0:
            self.save()
        return count

    @property
    def data_dir(self) -> Path:
        """获取数据目录"""
        return self._data_dir

    @property
    def thumbnails_dir(self) -> Path:
        """获取缩略图目录"""
        return self._thumbnails_dir


gallery_storage = GalleryStorage()
