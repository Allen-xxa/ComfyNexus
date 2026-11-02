"""
资产库数据模型
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class AssetCategory:
    """资产分类"""
    id: str
    name: str
    is_system: bool = False
    parent_id: Optional[str] = None
    sort_order: int = 0
    folder_path: Optional[str] = None

    def to_dict(self) -> dict:
        result = {
            "id": self.id,
            "name": self.name,
            "isSystem": self.is_system,
            "parentId": self.parent_id,
            "sortOrder": self.sort_order
        }
        if self.folder_path is not None:
            result["folderPath"] = self.folder_path
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "AssetCategory":
        return cls(
            id=data["id"],
            name=data["name"],
            is_system=data.get("isSystem", False),
            parent_id=data.get("parentId"),
            sort_order=data.get("sortOrder", 0),
            folder_path=data.get("folderPath")
        )


@dataclass
class Asset:
    """资产（图片或视频）"""
    id: str
    filename: str
    file_path: str
    asset_type: str
    width: int
    height: int
    size: int
    created_at: str
    is_favorite: bool = False
    category_id: Optional[str] = None
    thumbnail_path: Optional[str] = None
    has_workflow: bool = False
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    model: Optional[str] = None
    sampler: Optional[str] = None
    scheduler: Optional[str] = None
    steps: Optional[int] = None
    cfg: Optional[float] = None
    seed: Optional[int] = None
    duration: Optional[float] = None
    nsfw_score: Optional[float] = None
    nsfw_label: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    description: Optional[str] = None
    preview_blurred: bool = False
    rating: int = 0

    def to_dict(self) -> dict:
        result = {
            "id": self.id,
            "filename": self.filename,
            "filePath": self.file_path,
            "type": self.asset_type,
            "width": self.width,
            "height": self.height,
            "size": self.size,
            "createdAt": self.created_at,
            "isFavorite": self.is_favorite,
            "categoryId": self.category_id,
            "thumbnailPath": self.thumbnail_path,
            "hasWorkflow": self.has_workflow
        }
        if self.prompt is not None:
            result["prompt"] = self.prompt
        if self.negative_prompt is not None:
            result["negativePrompt"] = self.negative_prompt
        if self.model is not None:
            result["model"] = self.model
        if self.sampler is not None:
            result["sampler"] = self.sampler
        if self.steps is not None:
            if self.steps == self.steps and self.steps != float('inf') and self.steps != float('-inf'):
                result["steps"] = self.steps
        if self.cfg is not None:
            if self.cfg == self.cfg and self.cfg != float('inf') and self.cfg != float('-inf'):
                result["cfg"] = self.cfg
        if self.seed is not None:
            if self.seed == self.seed and self.seed != float('inf') and self.seed != float('-inf'):
                result["seed"] = self.seed
        if self.duration is not None:
            if self.duration == self.duration and self.duration != float('inf') and self.duration != float('-inf'):
                result["duration"] = self.duration
        if self.nsfw_score is not None:
            result["nsfwScore"] = self.nsfw_score
        if self.nsfw_label is not None:
            result["nsfwLabel"] = self.nsfw_label
        if self.tags:
            result["tags"] = self.tags
        if self.description is not None:
            result["description"] = self.description
        result["previewBlurred"] = self.preview_blurred
        result["rating"] = self.rating
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Asset":
        return cls(
            id=data["id"],
            filename=data["filename"],
            file_path=data["filePath"],
            asset_type=data["type"],
            width=data["width"],
            height=data["height"],
            size=data["size"],
            created_at=data["createdAt"],
            is_favorite=data.get("isFavorite", False),
            category_id=data.get("categoryId"),
            thumbnail_path=data.get("thumbnailPath"),
            has_workflow=data.get("hasWorkflow", False),
            prompt=data.get("prompt"),
            negative_prompt=data.get("negativePrompt"),
            model=data.get("model"),
            sampler=data.get("sampler"),
            scheduler=data.get("scheduler"),
            steps=data.get("steps"),
            cfg=data.get("cfg"),
            seed=data.get("seed"),
            duration=data.get("duration"),
            nsfw_score=data.get("nsfwScore"),
            nsfw_label=data.get("nsfwLabel"),
            tags=data.get("tags", []),
            description=data.get("description"),
            preview_blurred=data.get("previewBlurred", False),
            rating=data.get("rating", 0)
        )


@dataclass
class ScanProgress:
    """扫描进度"""
    stage: str  # 'scanning' | 'done'
    current: int
    total: int
    message: str
    asset_data: Optional[dict] = None

    def to_dict(self) -> dict:
        result = {
            "stage": self.stage,
            "current": self.current,
            "total": self.total,
            "message": self.message
        }
        if self.asset_data is not None:
            result["assetData"] = self.asset_data
        return result


@dataclass
class GallerySettings:
    """资产库设置"""
    library_path: str = ""
    last_scan_time: Optional[str] = None
    nsfw_auto_classify: bool = False
    nsfw_threshold: float = 0.6
    nsfw_auto_blur: bool = True

    def to_dict(self) -> dict:
        return {
            "libraryPath": self.library_path,
            "lastScanTime": self.last_scan_time,
            "nsfwAutoClassify": self.nsfw_auto_classify,
            "nsfwThreshold": self.nsfw_threshold,
            "nsfwAutoBlur": self.nsfw_auto_blur
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GallerySettings":
        return cls(
            library_path=data.get("libraryPath", ""),
            last_scan_time=data.get("lastScanTime"),
            nsfw_auto_classify=data.get("nsfwAutoClassify", False),
            nsfw_threshold=data.get("nsfwThreshold", 0.6),
            nsfw_auto_blur=data.get("nsfwAutoBlur", True)
        )


@dataclass
class GalleryData:
    """资产库完整数据"""
    version: str = "1.0"
    settings: GallerySettings = field(default_factory=GallerySettings)
    categories: list[AssetCategory] = field(default_factory=list)
    assets: list[Asset] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "settings": self.settings.to_dict(),
            "categories": [c.to_dict() for c in self.categories],
            "assets": [a.to_dict() for a in self.assets]
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GalleryData":
        settings = GallerySettings.from_dict(data.get("settings", {}))
        categories = [AssetCategory.from_dict(c) for c in data.get("categories", [])]
        assets = [Asset.from_dict(a) for a in data.get("assets", [])]
        return cls(
            version=data.get("version", "1.0"),
            settings=settings,
            categories=categories,
            assets=assets
        )
