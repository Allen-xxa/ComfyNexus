"""
提示词库管理服务

负责提示词配方的持久化存储和管理。
"""

import json
import uuid
import base64
import imghdr
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
import threading

from .models import Prompt, Category, Metadata
from backend.src.utils.paths import get_prompt_data_dir, get_prompt_images_dir
from backend.src.utils.logger import app_logger as logger


# 生成参数字段：与资产库(Asset)一一对应，用于复现一次生成
_INT_PARAM_FIELDS = ('steps', 'seed', 'width', 'height')
_FLOAT_PARAM_FIELDS = ('cfg', 'duration')
_STR_PARAM_FIELDS = (
    'model',
    'sampler',
    'scheduler',
    'asset_type',
    'source_asset_id',
    # 来源工作流：资产文件名 + 已导出的 JSON 路径（未导出为空）
    'workflow_name',
    'workflow_path',
)

# 合理的取值范围，防止脏数据写入
_INT_PARAM_LIMITS = {
    'steps': (1, 10000),
    'seed': (0, 2 ** 63 - 1),
    'width': (1, 32768),
    'height': (1, 32768),
}
_FLOAT_PARAM_LIMITS = {
    'cfg': (0.0, 100.0),
    'duration': (0.0, 86400.0),
}


def _extract_generation_params(data: Dict[str, Any]) -> Dict[str, Any]:
    """从请求数据里取出生成参数，只保留出现过的字段。

    None 与空字符串视为"清空"，会被写成默认值（数值为 None，字符串为 ""）。
    数值超出合理范围时直接丢弃，避免脏数据污染库。
    """
    params: Dict[str, Any] = {}

    for field in _STR_PARAM_FIELDS:
        if field in data:
            value = data[field]
            params[field] = (str(value).strip() if value is not None else "")

    for field in _INT_PARAM_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if value is None or value == "":
            params[field] = None
            continue
        if isinstance(value, bool):
            raise ValueError(f"参数 {field} 必须是数字")
        if isinstance(value, int):
            # 直接取整，避免 float 转换丢失 int64 精度（如随机种子）
            number = value
        else:
            try:
                number = int(value)
            except (TypeError, ValueError):
                try:
                    number = int(float(value))
                except (TypeError, ValueError):
                    raise ValueError(f"参数 {field} 必须是数字")
        low, high = _INT_PARAM_LIMITS[field]
        params[field] = number if low <= number <= high else None

    for field in _FLOAT_PARAM_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if value is None or value == "":
            params[field] = None
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"参数 {field} 必须是数字")
        low, high = _FLOAT_PARAM_LIMITS[field]
        params[field] = round(number, 4) if low <= number <= high else None

    return params


def _default_generation_params() -> Dict[str, Any]:
    """生成参数字段的默认值，用于旧数据补齐"""
    params: Dict[str, Any] = {field: "" for field in _STR_PARAM_FIELDS}
    params.update({field: None for field in _INT_PARAM_FIELDS})
    params.update({field: None for field in _FLOAT_PARAM_FIELDS})
    return params


class PromptLibraryService:
    """
    提示词库管理服务
    
    负责提示词配方的持久化和管理。
    """
    
    DATA_VERSION = "1.0"
    MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
    ALLOWED_IMAGE_FORMATS = {'jpg', 'jpeg', 'png', 'webp'}
    
    def __init__(self):
        """
        初始化服务
        
        使用 get_prompt_data_dir() 获取数据目录
        使用 get_prompt_images_dir() 获取图片目录
        """
        self.data_dir = get_prompt_data_dir()
        self.images_dir = get_prompt_images_dir()
        self.prompts_file = self.data_dir / "prompts.json"
        self.categories_file = self.data_dir / "categories.json"
        self.metadata_file = self.data_dir / "metadata.json"
        self._lock = threading.Lock()
        self._ensure_files_exist()
    
    def _ensure_files_exist(self) -> None:
        """确保数据文件存在，不存在则创建"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        
        if not self.prompts_file.exists():
            self._save_prompts([])
        
        if not self.categories_file.exists():
            self._save_categories(self._get_default_categories())
        
        if not self.metadata_file.exists():
            self._save_metadata(self._get_default_metadata())
    
    def _load_prompts(self) -> List[Dict]:
        """
        从JSON文件加载提示词列表
        
        Returns:
            List[Dict]: 提示词列表
        """
        try:
            with open(self.prompts_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('prompts', [])
        except json.JSONDecodeError as e:
            logger.error(f'JSON解析错误: {e}')
            return []
        except IOError as e:
            logger.error(f'文件读取错误: {e}')
            return []
    
    def _save_prompts(self, prompts: List[Dict]) -> None:
        """
        保存提示词列表到JSON文件
        
        Args:
            prompts: 提示词列表
        """
        try:
            data = {'version': self.DATA_VERSION, 'prompts': prompts}
            with open(self.prompts_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.error(f'文件写入错误: {e}')
            raise
    
    def _load_categories(self) -> List[Dict]:
        """
        从JSON文件加载分类列表
        
        Returns:
            List[Dict]: 分类列表
        """
        try:
            with open(self.categories_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('categories', [])
        except json.JSONDecodeError as e:
            logger.error(f'JSON解析错误: {e}')
            return []
        except IOError as e:
            logger.error(f'文件读取错误: {e}')
            return []
    
    def _save_categories(self, categories: List[Dict]) -> None:
        """
        保存分类列表到JSON文件
        
        Args:
            categories: 分类列表
        """
        try:
            data = {'version': self.DATA_VERSION, 'categories': categories}
            with open(self.categories_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.error(f'文件写入错误: {e}')
            raise
    
    def _load_metadata(self) -> Dict:
        """
        从JSON文件加载元数据
        
        Returns:
            Dict: 元数据
        """
        try:
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f'JSON解析错误: {e}')
            return self._get_default_metadata()
        except IOError as e:
            logger.error(f'文件读取错误: {e}')
            return self._get_default_metadata()
    
    def _save_metadata(self, metadata: Dict) -> None:
        """
        保存元数据到JSON文件
        
        Args:
            metadata: 元数据
        """
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        except IOError as e:
            logger.error(f'文件写入错误: {e}')
            raise
    
    def _get_default_categories(self) -> List[Dict]:
        """
        获取默认分类
        
        Returns:
            List[Dict]: 默认分类列表
        """
        return [
            {
                'id': 'all',
                'name': '全部',
                'icon': 'layers',
                'parent_id': None,
                'sort_order': 0,
                'is_system': True,
            },
            {
                'id': 'favorites',
                'name': '收藏',
                'icon': 'star',
                'parent_id': None,
                'sort_order': 1,
                'is_system': True,
            },
        ]
    
    def _get_default_metadata(self) -> Dict:
        """
        获取默认元数据
        
        Returns:
            Dict: 默认元数据
        """
        now = datetime.now().isoformat()
        return {
            'version': '1.0.0',
            'created_at': now,
            'updated_at': now,
            'stats': {
                'total_prompts': 0,
                'total_categories': 2,
                'total_usage': 0,
            },
            'settings': {
                'default_category_id': 'all',
                'auto_backup': True,
                'backup_interval_days': 7,
            },
        }
    
    def _update_metadata_stats(self) -> None:
        """更新元数据统计信息"""
        metadata = self._load_metadata()
        prompts = self._load_prompts()
        categories = self._load_categories()
        
        metadata['stats']['total_prompts'] = len(prompts)
        metadata['stats']['total_categories'] = len(categories)
        metadata['stats']['total_usage'] = sum(p.get('usage_count', 0) for p in prompts)
        metadata['updated_at'] = datetime.now().isoformat()
        
        self._save_metadata(metadata)
    
    def get_all_prompts(self) -> List[Dict]:
        """
        获取所有提示词
        
        Returns:
            List[Dict]: 提示词列表
        """
        with self._lock:
            return self._load_prompts()
    
    def create_prompt(self, data: Dict[str, Any], allow_empty_positive: bool = False) -> Dict:
        """
        创建提示词
        
        Args:
            data: 提示词数据
            allow_empty_positive: 允许正向提示词为空。
                仅用于"从资产库导入"场景——资产可能没解析到提示词，
                但模型/采样器等参数仍有保存价值。
            
        Returns:
            Dict: 新创建的提示词
            
        Raises:
            ValueError: 验证失败时抛出
        """
        name = data.get('name', '').strip()
        positive_prompt = data.get('positive_prompt', '').strip()
        category_id = data.get('category_id', '').strip()
        
        if not name:
            raise ValueError("提示词名称不能为空")
        
        if len(name) > 100:
            raise ValueError("提示词名称不能超过100个字符")
        
        if not positive_prompt and not allow_empty_positive:
            raise ValueError("正向提示词不能为空")
        
        if len(positive_prompt) > 10000:
            raise ValueError("正向提示词不能超过10000个字符")
        
        if not category_id:
            raise ValueError("必须选择分类")
        
        categories = self._load_categories()
        valid_category_ids = {c['id'] for c in categories}
        if category_id not in valid_category_ids:
            raise ValueError("指定的分类不存在")
        
        negative_prompt = data.get('negative_prompt', '').strip()
        if len(negative_prompt) > 10000:
            raise ValueError("反向提示词不能超过10000个字符")
        
        remark = data.get('remark', '').strip()
        if len(remark) > 500:
            raise ValueError("备注不能超过500个字符")
        
        tags = data.get('tags', [])
        if len(tags) > 10:
            raise ValueError("标签数量不能超过10个")
        
        for tag in tags:
            if len(tag) > 50:
                raise ValueError("标签长度不能超过50个字符")
        
        generation_params = _extract_generation_params(data)
        
        with self._lock:
            prompts = self._load_prompts()
            
            for prompt in prompts:
                if prompt['name'] == name:
                    raise ValueError("提示词名称已存在")
            
            now = datetime.now().isoformat()
            new_prompt = {
                'id': str(uuid.uuid4()),
                'name': name,
                'positive_prompt': positive_prompt,
                'negative_prompt': negative_prompt,
                'preview_image': data.get('preview_image', ''),
                'remark': remark,
                'category_id': category_id,
                'tags': tags,
                'is_favorite': False,
                'usage_count': 0,
                'created_at': now,
                'updated_at': now,
            }
            new_prompt.update(_default_generation_params())
            new_prompt.update(generation_params)
            
            prompts.append(new_prompt)
            self._save_prompts(prompts)
            self._update_metadata_stats()
            
            logger.info(f"创建提示词成功: {name}")
            return new_prompt
    
    def update_prompt(self, prompt_id: str, data: Dict[str, Any]) -> bool:
        """
        更新提示词
        
        Args:
            prompt_id: 提示词ID
            data: 更新数据
            
        Returns:
            bool: 更新是否成功
            
        Raises:
            ValueError: 验证失败时抛出
        """
        with self._lock:
            prompts = self._load_prompts()
            
            prompt_found = False
            for prompt in prompts:
                if prompt['id'] == prompt_id:
                    prompt_found = True
                    
                    if 'name' in data:
                        name = data['name'].strip()
                        if not name:
                            raise ValueError("提示词名称不能为空")
                        if len(name) > 100:
                            raise ValueError("提示词名称不能超过100个字符")
                        
                        for other in prompts:
                            if other['id'] != prompt_id and other['name'] == name:
                                raise ValueError("提示词名称已存在")
                        prompt['name'] = name
                    
                    if 'positive_prompt' in data:
                        # 更新允许正向提示词为空：从资产库导入的"参数配方"可能
                        # 没有解析到提示词，用户只想改参数/标签时不应被拦住
                        positive_prompt = data['positive_prompt'].strip()
                        if len(positive_prompt) > 10000:
                            raise ValueError("正向提示词不能超过10000个字符")
                        prompt['positive_prompt'] = positive_prompt
                    
                    if 'negative_prompt' in data:
                        negative_prompt = data['negative_prompt'].strip()
                        if len(negative_prompt) > 10000:
                            raise ValueError("反向提示词不能超过10000个字符")
                        prompt['negative_prompt'] = negative_prompt
                    
                    if 'preview_image' in data:
                        prompt['preview_image'] = data['preview_image']
                    
                    if 'remark' in data:
                        remark = data['remark'].strip()
                        if len(remark) > 500:
                            raise ValueError("备注不能超过500个字符")
                        prompt['remark'] = remark
                    
                    if 'category_id' in data:
                        category_id = data['category_id'].strip()
                        if not category_id:
                            raise ValueError("必须选择分类")
                        
                        categories = self._load_categories()
                        valid_category_ids = {c['id'] for c in categories}
                        if category_id not in valid_category_ids:
                            raise ValueError("指定的分类不存在")
                        
                        prompt['category_id'] = category_id
                    
                    if 'tags' in data:
                        tags = data['tags']
                        if len(tags) > 10:
                            raise ValueError("标签数量不能超过10个")
                        for tag in tags:
                            if len(tag) > 50:
                                raise ValueError("标签长度不能超过50个字符")
                        prompt['tags'] = tags
                    
                    generation_params = _extract_generation_params(data)
                    if generation_params:
                        prompt.update(generation_params)
                    
                    prompt['updated_at'] = datetime.now().isoformat()
                    break
            
            if not prompt_found:
                return False
            
            self._save_prompts(prompts)
            self._update_metadata_stats()
            
            logger.info(f"更新提示词成功: {prompt_id}")
            return True
    
    def delete_prompt(self, prompt_id: str) -> bool:
        """
        删除提示词
        
        Args:
            prompt_id: 提示词ID
            
        Returns:
            bool: 删除是否成功
        """
        with self._lock:
            prompts = self._load_prompts()
            
            original_length = len(prompts)
            prompts = [p for p in prompts if p['id'] != prompt_id]
            
            if len(prompts) == original_length:
                return False
            
            self._save_prompts(prompts)
            self._update_metadata_stats()
            
            logger.info(f"删除提示词成功: {prompt_id}")
            return True
    
    def batch_delete_prompts(self, ids: List[str]) -> int:
        """
        批量删除提示词
        
        Args:
            ids: 提示词ID列表
            
        Returns:
            int: 删除的数量
        """
        with self._lock:
            prompts = self._load_prompts()
            
            original_length = len(prompts)
            prompts = [p for p in prompts if p['id'] not in ids]
            deleted_count = original_length - len(prompts)
            
            if deleted_count > 0:
                self._save_prompts(prompts)
                self._update_metadata_stats()
                logger.info(f"批量删除提示词成功: {deleted_count} 条")
            
            return deleted_count
    
    def batch_move_prompts(self, ids: List[str], category_id: str) -> int:
        """
        批量移动提示词到指定分类
        
        Args:
            ids: 提示词ID列表
            category_id: 目标分类ID
            
        Returns:
            int: 移动的数量
            
        Raises:
            ValueError: 目标分类无效时抛出
        """
        virtual_category_ids = {'all', 'favorites'}
        if category_id in virtual_category_ids:
            raise ValueError("不能移动到虚拟分类")
        
        with self._lock:
            categories = self._load_categories()
            valid_category_ids = {c['id'] for c in categories}
            if category_id not in valid_category_ids:
                raise ValueError("目标分类不存在")
            
            prompts = self._load_prompts()
            
            moved_count = 0
            for prompt in prompts:
                if prompt['id'] in ids:
                    prompt['category_id'] = category_id
                    prompt['updated_at'] = datetime.now().isoformat()
                    moved_count += 1
            
            if moved_count > 0:
                self._save_prompts(prompts)
                logger.info(f"批量移动提示词成功: {moved_count} 条到分类 {category_id}")
            
            return moved_count
    
    def toggle_favorite(self, prompt_id: str) -> Optional[bool]:
        """
        切换收藏状态
        
        Args:
            prompt_id: 提示词ID
            
        Returns:
            Optional[bool]: 新的收藏状态，不存在则返回None
        """
        with self._lock:
            prompts = self._load_prompts()
            
            for prompt in prompts:
                if prompt['id'] == prompt_id:
                    prompt['is_favorite'] = not prompt['is_favorite']
                    prompt['updated_at'] = datetime.now().isoformat()
                    self._save_prompts(prompts)
                    
                    status = "收藏" if prompt['is_favorite'] else "取消收藏"
                    logger.info(f"{status}提示词成功: {prompt_id}")
                    return prompt['is_favorite']
            
            return None
    
    def increment_usage(self, prompt_id: str) -> bool:
        """
        增加使用次数
        
        Args:
            prompt_id: 提示词ID
            
        Returns:
            bool: 是否成功
        """
        with self._lock:
            prompts = self._load_prompts()
            
            for prompt in prompts:
                if prompt['id'] == prompt_id:
                    prompt['usage_count'] = prompt.get('usage_count', 0) + 1
                    prompt['updated_at'] = datetime.now().isoformat()
                    self._save_prompts(prompts)
                    self._update_metadata_stats()
                    return True
            
            return False
    
    def get_all_categories(self) -> List[Dict]:
        """
        获取所有分类
        
        将扁平分类结构转换为嵌套结构，前端期望的格式：
        [
            {
                "id": "all",
                "name": "全部",
                "icon": "layers",
                "parent_id": null,
                "sort_order": 0,
                "is_system": true,
                "children": []
            },
            ...
        ]
        
        Returns:
            List[Dict]: 嵌套分类列表
        """
        with self._lock:
            categories = self._load_categories()
            return self._build_category_tree(categories)
    
    def _build_category_tree(self, categories: List[Dict]) -> List[Dict]:
        """
        将扁平分类列表构建为嵌套树结构
        
        Args:
            categories: 扁平分类列表
            
        Returns:
            List[Dict]: 嵌套分类树
        """
        category_map = {c['id']: {**c, 'children': []} for c in categories}
        
        root_categories = []
        
        for category in category_map.values():
            parent_id = category.get('parent_id')
            if parent_id and parent_id in category_map:
                category_map[parent_id]['children'].append(category)
            else:
                root_categories.append(category)
        
        def sort_categories(cats: List[Dict]) -> List[Dict]:
            sorted_cats = sorted(cats, key=lambda c: c.get('sort_order', 0))
            for cat in sorted_cats:
                if cat.get('children'):
                    cat['children'] = sort_categories(cat['children'])
            return sorted_cats
        
        return sort_categories(root_categories)
    
    def create_category(self, data: Dict[str, Any]) -> Dict:
        """
        创建分类
        
        Args:
            data: 分类数据
            
        Returns:
            Dict: 新创建的分类
            
        Raises:
            ValueError: 验证失败时抛出
        """
        name = data.get('name', '').strip()
        
        if not name:
            raise ValueError("分类名称不能为空")
        
        if len(name) > 50:
            raise ValueError("分类名称不能超过50个字符")
        
        with self._lock:
            categories = self._load_categories()
            
            for category in categories:
                if category['name'] == name:
                    raise ValueError("分类名称已存在")
            
            parent_id = data.get('parent_id')
            if parent_id:
                parent = next((c for c in categories if c['id'] == parent_id), None)
                if not parent:
                    raise ValueError("父分类不存在")
                if parent.get('is_system', False) or parent.get('parent_id'):
                    raise ValueError("只支持两级分类，父分类必须是用户自建的顶级分类")
            
            max_order = max(
                (c['sort_order'] for c in categories if c.get('parent_id') == parent_id),
                default=-1
            )
            
            new_category = {
                'id': str(uuid.uuid4()),
                'name': name,
                'icon': data.get('icon', 'folder'),
                'parent_id': parent_id,
                'sort_order': max_order + 1,
                'is_system': False,
            }
            
            categories.append(new_category)
            self._save_categories(categories)
            self._update_metadata_stats()
            
            logger.info(f"创建分类成功: {name}")
            return new_category
    
    def update_category(self, category_id: str, data: Dict[str, Any]) -> bool:
        """
        更新分类
        
        Args:
            category_id: 分类ID
            data: 更新数据
            
        Returns:
            bool: 更新是否成功
            
        Raises:
            ValueError: 验证失败时抛出
        """
        with self._lock:
            categories = self._load_categories()
            
            category_found = False
            for category in categories:
                if category['id'] == category_id:
                    category_found = True
                    
                    if 'name' in data:
                        name = data['name'].strip()
                        if not name:
                            raise ValueError("分类名称不能为空")
                        if len(name) > 50:
                            raise ValueError("分类名称不能超过50个字符")
                        
                        for other in categories:
                            if other['id'] != category_id and other['name'] == name:
                                raise ValueError("分类名称已存在")
                        category['name'] = name
                    
                    if 'icon' in data:
                        category['icon'] = data['icon']
                    
                    if 'sort_order' in data:
                        category['sort_order'] = data['sort_order']
                    
                    break
            
            if not category_found:
                return False
            
            self._save_categories(categories)
            logger.info(f"更新分类成功: {category_id}")
            return True
    
    def move_category(self, category_id: str, new_parent_id: Optional[str], new_index: int) -> None:
        """
        移动分类：换父级和/或同级排序，移动后重排受影响分组的 sort_order
        
        Args:
            category_id: 要移动的分类ID
            new_parent_id: 目标父分类ID，None 表示移到顶级
            new_index: 在目标同级列表（不含被移动项）中的插入位置
            
        Raises:
            ValueError: 校验失败时抛出
        """
        virtual_ids = {'all', 'favorites'}
        with self._lock:
            categories = self._load_categories()
            by_id = {c['id']: c for c in categories}
            
            if category_id not in by_id:
                raise ValueError("分类不存在")
            moving = by_id[category_id]
            if moving.get('is_system', False) or category_id in virtual_ids:
                raise ValueError("系统分类不能移动")
            
            if new_parent_id:
                if new_parent_id == category_id:
                    raise ValueError("不能移动到自身分类下")
                parent = by_id.get(new_parent_id)
                if not parent:
                    raise ValueError("目标父分类不存在")
                if parent.get('is_system', False) or new_parent_id in virtual_ids:
                    raise ValueError("不能移动到系统分类下")
                if parent.get('parent_id'):
                    raise ValueError("只支持两级分类，不能移动到子分类下")
                if any(c.get('parent_id') == category_id for c in categories):
                    raise ValueError("该分类下存在子分类，不能移动到其他分类下")
            
            siblings = [
                c for c in categories
                if c.get('parent_id') == new_parent_id
                and c['id'] != category_id
                and not c.get('is_system', False)
            ]
            siblings.sort(key=lambda c: c.get('sort_order', 0))
            index = max(0, min(new_index, len(siblings)))
            siblings.insert(index, moving)
            
            base = 0
            if new_parent_id is None:
                system_orders = [
                    c.get('sort_order', 0) for c in categories
                    if c.get('parent_id') is None and c.get('is_system', False)
                ]
                base = (max(system_orders) + 1) if system_orders else 0
            
            for pos, c in enumerate(siblings):
                c['parent_id'] = new_parent_id
                c['sort_order'] = base + pos
            
            self._save_categories(categories)
            logger.info(f"移动分类成功: {category_id} -> parent={new_parent_id}, index={index}")
    
    def delete_category(self, category_id: str) -> bool:
        """
        删除分类
        
        Args:
            category_id: 分类ID
            
        Returns:
            bool: 删除是否成功
            
        Raises:
            ValueError: 尝试删除系统分类时抛出
        """
        with self._lock:
            categories = self._load_categories()
            
            category_to_delete = None
            for category in categories:
                if category['id'] == category_id:
                    if category.get('is_system', False):
                        raise ValueError("系统分类不能删除")
                    category_to_delete = category
                    break
            
            if not category_to_delete:
                return False
            
            has_children = any(
                c.get('parent_id') == category_id for c in categories
            )
            if has_children:
                raise ValueError("该分类下存在子分类，请先删除子分类")
            
            prompts = self._load_prompts()
            prompt_count = sum(1 for p in prompts if p['category_id'] == category_id)
            if prompt_count > 0:
                raise ValueError(f"该分类下存在 {prompt_count} 个提示词，请先删除或迁移到其他分类")
            
            categories = [c for c in categories if c['id'] != category_id]
            self._save_categories(categories)
            
            self._update_metadata_stats()
            logger.info(f"删除分类成功: {category_id}")
            return True
    
    def save_image(self, file_data: str, filename: str) -> str:
        """
        保存图片
        
        Args:
            file_data: Base64编码的图片数据
            filename: 原始文件名
            
        Returns:
            str: 保存后的图片路径（local://images/{filename}格式）
            
        Raises:
            ValueError: 验证失败时抛出
        """
        try:
            if ',' in file_data:
                file_data = file_data.split(',')[1]
            
            image_bytes = base64.b64decode(file_data)
            
            if len(image_bytes) > self.MAX_IMAGE_SIZE:
                raise ValueError(f"图片大小不能超过{self.MAX_IMAGE_SIZE // (1024*1024)}MB")
            
            image_format = imghdr.what(None, h=image_bytes)
            if image_format not in self.ALLOWED_IMAGE_FORMATS:
                raise ValueError(f"不支持的图片格式，仅支持: {', '.join(self.ALLOWED_IMAGE_FORMATS)}")
            
            import os
            name, _ = os.path.splitext(filename)
            unique_filename = f"{name}_{uuid.uuid4().hex[:8]}.{image_format}"
            
            image_path = self.images_dir / unique_filename
            with open(image_path, 'wb') as f:
                f.write(image_bytes)
            
            logger.info(f"保存图片成功: {unique_filename}")
            return f"local://images/{unique_filename}"
            
        except Exception as e:
            logger.error(f"保存图片失败: {e}")
            raise ValueError(f"保存图片失败: {str(e)}")
    
    def get_image_path(self, image_url: str) -> Optional[Path]:
        """
        获取图片的实际文件路径
        
        Args:
            image_url: 图片URL（local://images/{filename}格式）
            
        Returns:
            Optional[Path]: 图片文件路径，不存在则返回None
        """
        if not image_url.startswith('local://images/'):
            return None
        
        filename = image_url.replace('local://images/', '')
        
        if '..' in filename or filename.startswith('/') or filename.startswith('\\'):
            logger.warning(f"检测到路径穿越攻击尝试: {filename}")
            return None
        
        image_path = self.images_dir / filename
        
        try:
            resolved_path = image_path.resolve()
            resolved_dir = self.images_dir.resolve()
            resolved_path.relative_to(resolved_dir)
        except (ValueError, OSError) as e:
            logger.warning(f"图片路径验证失败: {e}")
            return None
        
        if image_path.exists():
            return image_path
        
        return None
    
    def export_prompts(self, prompt_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        导出提示词
        
        Args:
            prompt_ids: 要导出的提示词ID列表，为空则导出全部
            
        Returns:
            Dict: 导出的数据
        """
        with self._lock:
            prompts = self._load_prompts()
            categories = self._load_categories()
            
            if prompt_ids:
                prompts = [p for p in prompts if p['id'] in prompt_ids]
            
            return {
                'version': self.DATA_VERSION,
                'exported_at': datetime.now().isoformat(),
                'prompts': prompts,
                'categories': [c for c in categories if not c.get('is_system', False)]
            }
    
    def import_prompts(self, data: Dict[str, Any], merge: bool = True) -> Dict[str, Any]:
        """
        导入提示词和分类
        
        Args:
            data: 导入的数据，包含 prompts 和 categories
            merge: 是否合并模式（True为追加，False为覆盖）
            
        Returns:
            Dict: 导入结果
        """
        imported_prompts = data.get('prompts', [])
        imported_categories = data.get('categories', [])
        
        if not imported_prompts:
            return {
                'success': True,
                'imported_count': 0,
                'imported_categories': 0,
                'message': '没有可导入的提示词'
            }
        
        with self._lock:
            existing_categories = self._load_categories()
            existing_prompts = self._load_prompts() if merge else []
            existing_names = {p['name'] for p in existing_prompts}
            
            existing_category_ids = {c['id'] for c in existing_categories}
            existing_category_names = {c['name']: c['id'] for c in existing_categories}
            
            category_id_mapping: Dict[str, str] = {}
            imported_category_count = 0
            
            for category in imported_categories:
                cat_id = category.get('id', '')
                cat_name = category.get('name', '').strip()
                
                if not cat_id or not cat_name:
                    continue
                
                if cat_id in existing_category_ids:
                    category_id_mapping[cat_id] = cat_id
                    logger.debug(f"分类 ID 已存在，跳过: {cat_id}")
                    continue
                
                if cat_name in existing_category_names:
                    existing_id = existing_category_names[cat_name]
                    category_id_mapping[cat_id] = existing_id
                    logger.debug(f"分类名称已存在，合并到现有分类: {cat_name} -> {existing_id}")
                    continue
                
                new_cat_id = str(uuid.uuid4())
                now = datetime.now().isoformat()
                new_category = {
                    'id': new_cat_id,
                    'name': cat_name,
                    'icon': category.get('icon', 'folder'),
                    'parent_id': category.get('parent_id'),
                    'sort_order': category.get('sort_order', len(existing_categories)),
                    'is_system': False
                }
                existing_categories.append(new_category)
                existing_category_ids.add(new_cat_id)
                existing_category_names[cat_name] = new_cat_id
                category_id_mapping[cat_id] = new_cat_id
                imported_category_count += 1
                logger.debug(f"创建新分类: {cat_name} ({new_cat_id})")
            
            imported_count = 0
            skipped_count = 0
            
            for prompt in imported_prompts:
                name = prompt.get('name', '').strip()
                
                if not name:
                    skipped_count += 1
                    continue
                
                if name in existing_names:
                    name = f"{name} (导入)"
                
                original_category_id = prompt.get('category_id', '')
                final_category_id = ''
                
                if original_category_id:
                    if original_category_id in category_id_mapping:
                        final_category_id = category_id_mapping[original_category_id]
                    elif original_category_id in existing_category_ids:
                        final_category_id = original_category_id
                    else:
                        new_cat_id = str(uuid.uuid4())
                        new_category = {
                            'id': new_cat_id,
                            'name': f"导入分类",
                            'icon': 'folder',
                            'parent_id': None,
                            'sort_order': len(existing_categories),
                            'is_system': False
                        }
                        existing_categories.append(new_category)
                        existing_category_ids.add(new_cat_id)
                        final_category_id = new_cat_id
                        imported_category_count += 1
                        logger.debug(f"为提示词 '{name}' 创建新分类: {new_cat_id}")
                
                now = datetime.now().isoformat()
                new_prompt = {
                    'id': str(uuid.uuid4()),
                    'name': name,
                    'positive_prompt': prompt.get('positive_prompt', ''),
                    'negative_prompt': prompt.get('negative_prompt', ''),
                    'preview_image': prompt.get('preview_image', ''),
                    'remark': prompt.get('remark', ''),
                    'category_id': final_category_id,
                    'tags': prompt.get('tags', []),
                    'is_favorite': False,
                    'usage_count': 0,
                    'created_at': now,
                    'updated_at': now,
                }
                
                existing_prompts.append(new_prompt)
                existing_names.add(name)
                imported_count += 1
            
            self._save_categories(existing_categories)
            self._save_prompts(existing_prompts)
            self._update_metadata_stats()
            
            logger.info(f"导入完成: {imported_count} 条提示词, {imported_category_count} 个分类, 跳过 {skipped_count} 条")
            
            message = f'成功导入 {imported_count} 条提示词'
            if imported_category_count > 0:
                message += f'，{imported_category_count} 个分类'
            
            return {
                'success': True,
                'imported_count': imported_count,
                'imported_categories': imported_category_count,
                'skipped_count': skipped_count,
                'message': message
            }
