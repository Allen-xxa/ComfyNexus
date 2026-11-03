"""
提示词库控制器

负责处理前端的提示词库相关请求，提供以下功能：
- 提示词配方管理（创建、更新、删除、批量操作）
- 分类管理（创建、更新、删除）
- 图片上传
"""

from typing import Dict, Any, List, Optional
import logging

from backend.src.core.prompt_library import PromptLibraryService


logger = logging.getLogger(__name__)


class PromptLibraryController:
    """
    提示词库控制器
    
    提供前端调用的 API 接口，协调服务层组件。
    """
    
    def __init__(self):
        """初始化控制器"""
        self.service = PromptLibraryService()
        logger.info("提示词库控制器初始化完成")
    
    # ==================== 提示词 API ====================
    
    def prompt_get_all(self) -> Dict[str, Any]:
        """
        获取所有提示词
        
        Returns:
            {
                "success": bool,
                "prompts": [
                    {
                        "id": str,
                        "name": str,
                        "positive_prompt": str,
                        "negative_prompt": str,
                        "preview_image": str,
                        "remark": str,
                        "category_id": str,
                        "tags": [str],
                        "is_favorite": bool,
                        "usage_count": int,
                        "created_at": str,
                        "updated_at": str
                    }
                ]
            }
        """
        try:
            logger.info("获取所有提示词")
            prompts = self.service.get_all_prompts()
            return {
                "success": True,
                "prompts": prompts
            }
        except Exception as e:
            logger.error(f"获取提示词列表失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def prompt_create(
        self,
        name: str,
        positive_prompt: str,
        category_id: str = "",
        negative_prompt: str = "",
        preview_image: str = "",
        remark: str = "",
        tags: List[str] = None,
        params: Dict[str, Any] = None,
        allow_empty_positive: bool = False
    ) -> Dict[str, Any]:
        """
        创建新提示词
        
        Args:
            name: 配方名称
            positive_prompt: 正向提示词
            category_id: 所属分类ID
            negative_prompt: 反向提示词
            preview_image: 预览图路径
            remark: 使用备注
            tags: 标签数组
            params: 生成参数（model / sampler / scheduler / steps / cfg /
                seed / width / height / duration / asset_type / source_asset_id）
            allow_empty_positive: 允许正向提示词为空（从资产库导入时使用）
            
        Returns:
            {
                "success": bool,
                "prompt": {...} | None,
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"创建提示词: {name}")
            
            data = {
                "name": name,
                "positive_prompt": positive_prompt,
                "category_id": category_id,
                "negative_prompt": negative_prompt,
                "preview_image": preview_image,
                "remark": remark,
                "tags": tags or []
            }
            if params:
                data.update(params)
            
            prompt = self.service.create_prompt(
                data, allow_empty_positive=allow_empty_positive
            )
            
            return {
                "success": True,
                "prompt": prompt
            }
        except ValueError as e:
            logger.warning(f"创建提示词验证失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
        except Exception as e:
            logger.error(f"创建提示词失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def prompt_update(
        self,
        prompt_id: str,
        name: str = None,
        positive_prompt: str = None,
        category_id: str = None,
        negative_prompt: str = None,
        preview_image: str = None,
        remark: str = None,
        tags: List[str] = None,
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        更新提示词
        
        Args:
            prompt_id: 提示词ID
            其他参数为可选更新字段
            params: 生成参数，传 None 的数值字段表示清空
            
        Returns:
            {
                "success": bool,
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"更新提示词: {prompt_id}")
            
            data = {}
            if name is not None:
                data["name"] = name
            if positive_prompt is not None:
                data["positive_prompt"] = positive_prompt
            if category_id is not None:
                data["category_id"] = category_id
            if negative_prompt is not None:
                data["negative_prompt"] = negative_prompt
            if preview_image is not None:
                data["preview_image"] = preview_image
            if remark is not None:
                data["remark"] = remark
            if tags is not None:
                data["tags"] = tags
            if params:
                data.update(params)
            
            success = self.service.update_prompt(prompt_id, data)
            
            if success:
                return {"success": True}
            else:
                return {
                    "success": False,
                    "error_message": "提示词不存在"
                }
        except ValueError as e:
            logger.warning(f"更新提示词验证失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
        except Exception as e:
            logger.error(f"更新提示词失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def prompt_delete(self, prompt_id: str) -> Dict[str, Any]:
        """
        删除提示词
        
        Args:
            prompt_id: 提示词ID
            
        Returns:
            {
                "success": bool,
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"删除提示词: {prompt_id}")
            success = self.service.delete_prompt(prompt_id)
            
            if success:
                return {"success": True}
            else:
                return {
                    "success": False,
                    "error_message": "提示词不存在"
                }
        except Exception as e:
            logger.error(f"删除提示词失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def prompt_batch_delete(self, prompt_ids: List[str]) -> Dict[str, Any]:
        """
        批量删除提示词
        
        Args:
            prompt_ids: 提示词ID列表
            
        Returns:
            {
                "success": bool,
                "deleted_count": int
            }
        """
        try:
            logger.info(f"批量删除提示词: {len(prompt_ids)} 个")
            count = self.service.batch_delete_prompts(prompt_ids)
            return {
                "success": True,
                "deleted_count": count
            }
        except Exception as e:
            logger.error(f"批量删除提示词失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def prompt_batch_move(
        self,
        prompt_ids: List[str],
        category_id: str
    ) -> Dict[str, Any]:
        """
        批量移动提示词到指定分类
        
        Args:
            prompt_ids: 提示词ID列表
            category_id: 目标分类ID
            
        Returns:
            {
                "success": bool,
                "moved_count": int
            }
        """
        try:
            logger.info(f"批量移动提示词: {len(prompt_ids)} 个到分类 {category_id}")
            count = self.service.batch_move_prompts(prompt_ids, category_id)
            return {
                "success": True,
                "moved_count": count
            }
        except ValueError as e:
            logger.warning(f"批量移动提示词验证失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
        except Exception as e:
            logger.error(f"批量移动提示词失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def prompt_toggle_favorite(self, prompt_id: str) -> Dict[str, Any]:
        """
        切换提示词收藏状态
        
        Args:
            prompt_id: 提示词ID
            
        Returns:
            {
                "success": bool,
                "is_favorite": bool  # 新的收藏状态
            }
        """
        try:
            logger.info(f"切换提示词收藏状态: {prompt_id}")
            is_favorite = self.service.toggle_favorite(prompt_id)
            
            if is_favorite is not None:
                return {
                    "success": True,
                    "is_favorite": is_favorite
                }
            else:
                return {
                    "success": False,
                    "error_message": "提示词不存在"
                }
        except Exception as e:
            logger.error(f"切换收藏状态失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def prompt_increment_usage(self, prompt_id: str) -> Dict[str, Any]:
        """
        增加提示词使用次数
        
        Args:
            prompt_id: 提示词ID
            
        Returns:
            {
                "success": bool
            }
        """
        try:
            logger.info(f"增加提示词使用次数: {prompt_id}")
            success = self.service.increment_usage(prompt_id)
            
            if success:
                return {"success": True}
            else:
                return {
                    "success": False,
                    "error_message": "提示词不存在"
                }
        except Exception as e:
            logger.error(f"增加使用次数失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
    
    # ==================== 分类 API ====================
    
    def category_get_all(self) -> Dict[str, Any]:
        """
        获取所有分类
        
        Returns:
            {
                "success": bool,
                "categories": [
                    {
                        "id": str,
                        "name": str,
                        "icon": str,
                        "parent_id": str | null,
                        "sort_order": int,
                        "is_system": bool,
                        "children": [...]
                    }
                ]
            }
        """
        try:
            logger.info("获取所有分类")
            categories = self.service.get_all_categories()
            return {
                "success": True,
                "categories": categories
            }
        except Exception as e:
            logger.error(f"获取分类列表失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def category_create(
        self,
        name: str,
        icon: str = "folder",
        parent_id: str = None
    ) -> Dict[str, Any]:
        """
        创建新分类
        
        Args:
            name: 分类名称
            icon: 图标名称
            parent_id: 父分类ID
            
        Returns:
            {
                "success": bool,
                "category": {...} | None,
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"创建分类: {name}")
            
            data = {
                "name": name,
                "icon": icon,
                "parent_id": parent_id
            }
            
            category = self.service.create_category(data)
            
            return {
                "success": True,
                "category": category
            }
        except ValueError as e:
            logger.warning(f"创建分类验证失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
        except Exception as e:
            logger.error(f"创建分类失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def category_update(
        self,
        category_id: str,
        name: str = None,
        icon: str = None,
        sort_order: int = None
    ) -> Dict[str, Any]:
        """
        更新分类
        
        Args:
            category_id: 分类ID
            其他参数为可选更新字段
            
        Returns:
            {
                "success": bool,
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"更新分类: {category_id}")
            
            data = {}
            if name is not None:
                data["name"] = name
            if icon is not None:
                data["icon"] = icon
            if sort_order is not None:
                data["sort_order"] = sort_order
            
            success = self.service.update_category(category_id, data)
            
            if success:
                return {"success": True}
            else:
                return {
                    "success": False,
                    "error_message": "分类不存在"
                }
        except ValueError as e:
            logger.warning(f"更新分类验证失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
        except Exception as e:
            logger.error(f"更新分类失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def category_move(
        self,
        category_id: str,
        parent_id: str = None,
        index: int = 0
    ) -> Dict[str, Any]:
        """
        移动分类（换父级和/或排序）
        
        Args:
            category_id: 分类ID
            parent_id: 目标父分类ID，None 表示顶级
            index: 目标同级中的插入位置
            
        Returns:
            {
                "success": bool,
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"移动分类: {category_id} -> parent={parent_id}, index={index}")
            self.service.move_category(category_id, parent_id, int(index))
            return {"success": True}
        except ValueError as e:
            logger.warning(f"移动分类验证失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
        except Exception as e:
            logger.error(f"移动分类失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def category_delete(self, category_id: str) -> Dict[str, Any]:
        """
        删除分类
        
        Args:
            category_id: 分类ID
            
        Returns:
            {
                "success": bool,
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"删除分类: {category_id}")
            success = self.service.delete_category(category_id)
            
            if success:
                return {"success": True}
            else:
                return {
                    "success": False,
                    "error_message": "分类不存在"
                }
        except ValueError as e:
            logger.warning(f"删除分类验证失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
        except Exception as e:
            logger.error(f"删除分类失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
    
    # ==================== 图片上传 API ====================
    
    def prompt_upload_image(self, file_data: str, filename: str = None) -> Dict[str, Any]:
        """
        上传预览图片
        
        Args:
            file_data: Base64 编码的图片数据
            filename: 原始文件名（可选，用于提取扩展名）
            
        Returns:
            {
                "success": bool,
                "image_path": str,  # 本地图片路径
                "error_message": str  # 仅在失败时
            }
        """
        try:
            logger.info(f"上传预览图片: {filename}")
            image_path = self.service.save_image(file_data, filename or "image.jpg")
            return {
                "success": True,
                "image_path": image_path
            }
        except ValueError as e:
            logger.warning(f"上传图片验证失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
        except Exception as e:
            logger.error(f"上传图片失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
    
    # ==================== 导入导出 API ====================
    
    def prompt_export(self, prompt_ids: list = None) -> Dict[str, Any]:
        """
        导出提示词
        
        Args:
            prompt_ids: 要导出的提示词ID列表，为空则导出全部
            
        Returns:
            {
                "success": bool,
                "data": dict,  # 导出的数据
                "error_message": str (可选)
            }
        """
        try:
            logger.info(f"导出提示词: {len(prompt_ids) if prompt_ids else '全部'}")
            data = self.service.export_prompts(prompt_ids)
            return {
                "success": True,
                "data": data
            }
        except Exception as e:
            logger.error(f"导出提示词失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
    
    def prompt_import(self, data: dict, merge: bool = True) -> Dict[str, Any]:
        """
        导入提示词
        
        Args:
            data: 导入的数据
            merge: 是否合并模式
            
        Returns:
            {
                "success": bool,
                "imported_count": int,
                "skipped_count": int,
                "message": str
            }
        """
        try:
            logger.info(f"导入提示词: {len(data.get('prompts', []))} 条")
            result = self.service.import_prompts(data, merge)
            return result
        except Exception as e:
            logger.error(f"导入提示词失败: {e}")
            return {
                "success": False,
                "error_message": str(e)
            }
