"""
提示词库数据模型

定义提示词配方、分类和元数据的数据结构。
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class Prompt:
    """
    提示词配方数据模型

    Attributes:
        id: UUID v4，唯一标识
        name: 配方名称，必填
        positive_prompt: 正向提示词，必填
        negative_prompt: 反向提示词，可为空
        preview_image: 预览图路径（本地路径或远程URL）
        remark: 使用备注
        category_id: 所属分类ID，必填
        tags: 标签数组
        is_favorite: 收藏状态，默认 false
        usage_count: 使用次数，默认 0
        created_at: 创建时间，ISO8601 格式
        updated_at: 更新时间，ISO8601 格式

    生成参数（用于复现，均可为空）：
        model: 基础模型 / checkpoint 文件名
        sampler: 采样器名称
        scheduler: 调度器名称
        steps: 采样步数
        cfg: CFG / 引导系数
        seed: 随机种子
        width: 输出宽度
        height: 输出高度
        duration: 视频时长（秒），仅视频资产有值
        asset_type: 来源类型 image / video
        source_asset_id: 来源资产ID，用于追溯
        workflow_name: 来源工作流标识（通常是资产文件名）
        workflow_path: 已导出的工作流 JSON 路径，未导出时为空
    """
    id: str
    name: str
    positive_prompt: str
    category_id: str
    negative_prompt: str = ""
    preview_image: str = ""
    remark: str = ""
    tags: List[str] = field(default_factory=list)
    is_favorite: bool = False
    usage_count: int = 0
    created_at: str = ""
    updated_at: str = ""

    # 生成参数
    model: str = ""
    sampler: str = ""
    scheduler: str = ""
    steps: Optional[int] = None
    cfg: Optional[float] = None
    seed: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[float] = None
    asset_type: str = ""
    source_asset_id: str = ""
    workflow_name: str = ""
    workflow_path: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'id': self.id,
            'name': self.name,
            'positive_prompt': self.positive_prompt,
            'negative_prompt': self.negative_prompt,
            'preview_image': self.preview_image,
            'remark': self.remark,
            'category_id': self.category_id,
            'tags': self.tags,
            'is_favorite': self.is_favorite,
            'usage_count': self.usage_count,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'model': self.model,
            'sampler': self.sampler,
            'scheduler': self.scheduler,
            'steps': self.steps,
            'cfg': self.cfg,
            'seed': self.seed,
            'width': self.width,
            'height': self.height,
            'duration': self.duration,
            'asset_type': self.asset_type,
            'source_asset_id': self.source_asset_id,
            'workflow_name': self.workflow_name,
            'workflow_path': self.workflow_path,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Prompt':
        """从字典创建实例（旧数据缺少参数字段时使用默认值）"""
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            positive_prompt=data.get('positive_prompt', ''),
            negative_prompt=data.get('negative_prompt', ''),
            preview_image=data.get('preview_image', ''),
            remark=data.get('remark', ''),
            category_id=data.get('category_id', ''),
            tags=data.get('tags', []),
            is_favorite=data.get('is_favorite', False),
            usage_count=data.get('usage_count', 0),
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
            model=data.get('model', '') or '',
            sampler=data.get('sampler', '') or '',
            scheduler=data.get('scheduler', '') or '',
            steps=data.get('steps'),
            cfg=data.get('cfg'),
            seed=data.get('seed'),
            width=data.get('width'),
            height=data.get('height'),
            duration=data.get('duration'),
            asset_type=data.get('asset_type', '') or '',
            source_asset_id=data.get('source_asset_id', '') or '',
            workflow_name=data.get('workflow_name', '') or '',
            workflow_path=data.get('workflow_path', '') or '',
        )


@dataclass
class Category:
    """
    分类数据模型
    
    Attributes:
        id: 分类ID
        name: 分类名称
        icon: 图标名称（Lucide icon）
        parent_id: 父分类ID，None 表示顶级分类
        sort_order: 排序权重，越小越靠前
        is_system: 是否系统分类（不可删除）
        children: 子分类列表（嵌套结构）
    """
    id: str
    name: str
    icon: str = "folder"
    parent_id: Optional[str] = None
    sort_order: int = 0
    is_system: bool = False
    children: List['Category'] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {
            'id': self.id,
            'name': self.name,
            'icon': self.icon,
            'parent_id': self.parent_id,
            'sort_order': self.sort_order,
            'is_system': self.is_system,
        }
        if self.children:
            result['children'] = [child.to_dict() for child in self.children]
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Category':
        """从字典创建实例"""
        children_data = data.get('children', [])
        children = [cls.from_dict(child) for child in children_data]
        
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            icon=data.get('icon', 'folder'),
            parent_id=data.get('parent_id'),
            sort_order=data.get('sort_order', 0),
            is_system=data.get('is_system', False),
            children=children,
        )


@dataclass
class Metadata:
    """
    元数据模型
    
    Attributes:
        version: 数据格式版本
        created_at: 库创建时间
        updated_at: 最后更新时间
        stats: 统计信息
        settings: 设置项
    """
    version: str = "1.0.0"
    created_at: str = ""
    updated_at: str = ""
    stats: Dict[str, int] = field(default_factory=lambda: {
        'total_prompts': 0,
        'total_categories': 0,
        'total_usage': 0,
    })
    settings: Dict[str, Any] = field(default_factory=lambda: {
        'default_category_id': 'all',
        'auto_backup': True,
        'backup_interval_days': 7,
    })
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'version': self.version,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'stats': self.stats,
            'settings': self.settings,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Metadata':
        """从字典创建实例"""
        return cls(
            version=data.get('version', '1.0.0'),
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
            stats=data.get('stats', {
                'total_prompts': 0,
                'total_categories': 0,
                'total_usage': 0,
            }),
            settings=data.get('settings', {
                'default_category_id': 'all',
                'auto_backup': True,
                'backup_interval_days': 7,
            }),
        )
