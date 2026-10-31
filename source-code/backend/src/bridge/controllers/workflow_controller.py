"""
工作流管理控制器

管理工作流的读取、写入、元数据、文件夹等功能
"""

import json
import uuid
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from backend.src.core.workflow.models import (
    Workflow,
    WorkflowMetadata,
    WorkflowFolder,
    WorkflowMetadataStore,
    PluginDependency,
)
from backend.src.core.workflow.parser import WorkflowParser
from backend.src.utils.logger import app_logger as logger
from backend.src.utils.error_codes import WorkflowErrorCode


class WorkflowController:
    """工作流管理控制器"""

    def __init__(self, environment_manager=None, plugin_controller=None, workflow_config_manager=None):
        """
        初始化工作流控制器
        
        Args:
            environment_manager: 环境管理器（用于获取 ComfyUI 路径）
            plugin_controller: 插件控制器（用于检查插件安装状态）
            workflow_config_manager: 工作流配置管理器（用于读取自定义工作流目录）
        """
        self._environment_manager = environment_manager
        self._plugin_controller = plugin_controller
        self._workflow_config_manager = workflow_config_manager
        
        self._workflows_dir: Optional[Path] = None
        self._data_dir: Optional[Path] = None
        self._metadata_path: Optional[Path] = None
        self._images_dir: Optional[Path] = None
        self._metadata: Optional[WorkflowMetadataStore] = None
        self._initialized = False

    def initialize(self) -> bool:
        """
        初始化控制器
        
        Returns:
            是否初始化成功
        """
        try:
            if not self._environment_manager:
                logger.warning("环境管理器未设置，工作流控制器无法初始化")
                return False
            
            current_env = self._environment_manager.get_current_environment()
            if not current_env:
                logger.warning("当前环境未设置，工作流控制器无法初始化")
                return False
            
            comfyui_path = current_env.path
            if not comfyui_path:
                logger.warning("ComfyUI 路径未设置，工作流控制器无法初始化")
                return False
            
            env_id = current_env.id
            
            comfyui_path = Path(comfyui_path)

            env_type = current_env.env_type
            if env_type == "desktop" and current_env.desktop_data_path:
                base_path = Path(current_env.desktop_data_path)
                default_workflows_dir = base_path / "user" / "default" / "workflows"
            else:
                default_workflows_dir = comfyui_path / "user" / "default" / "workflows"

            custom_dir = None
            use_global = False
            if self._workflow_config_manager:
                try:
                    config = self._workflow_config_manager.load_config()
                    env_paths = config.get("env_paths", {})
                    if env_id not in env_paths:
                        env_paths[env_id] = str(default_workflows_dir)
                        config["env_paths"] = env_paths
                        self._workflow_config_manager.save_config(config)
                    use_global = config.get("use_global_path", False)
                    if use_global:
                        custom_dir = config.get("global_path", "") or None
                    else:
                        custom_dir = env_paths.get(env_id, None)
                except Exception as e:
                    logger.warning(f"读取工作流配置失败，使用默认路径: {e}")

            if custom_dir:
                self._workflows_dir = Path(custom_dir)
                self._workflows_dir.mkdir(parents=True, exist_ok=True)
                logger.info(f"使用自定义工作流目录: {self._workflows_dir}")
            else:
                self._workflows_dir = default_workflows_dir
            
            from backend.src.utils.paths import get_data_dir
            self._data_dir = get_data_dir() / "workflows"
            self._data_dir.mkdir(parents=True, exist_ok=True)

            if use_global:
                self._metadata_path = self._data_dir / "_global_metadata.json"
            else:
                self._metadata_path = self._data_dir / f"{env_id}_metadata.json"
            self._images_dir = self._data_dir / "images"
            self._images_dir.mkdir(parents=True, exist_ok=True)
            
            self._metadata = self._load_metadata()
            self._sync_folders_from_filesystem()
            
            self._initialized = True
            logger.info(f"工作流控制器初始化成功，环境: {env_id}, 工作流目录: {self._workflows_dir}")
            return True
            
        except Exception as e:
            logger.error(f"工作流控制器初始化失败: {e}")
            return False

    def _ensure_initialized(self) -> bool:
        """确保控制器已初始化"""
        if not self._initialized:
            return self.initialize()
        return True

    def reset_initialization(self):
        """
        重置初始化状态
        
        用于环境切换后重新初始化，确保读取新环境的工作流目录和元数据
        """
        logger.info("重置工作流控制器初始化状态")
        self._initialized = False
        self._workflows_dir = None
        self._data_dir = None
        self._metadata_path = None
        self._images_dir = None
        self._metadata = None

    def _load_metadata(self) -> WorkflowMetadataStore:
        """加载元数据"""
        if self._metadata_path and self._metadata_path.exists():
            try:
                content = self._metadata_path.read_text(encoding="utf-8")
                data = json.loads(content)
                return WorkflowMetadataStore.from_dict(data)
            except Exception as e:
                logger.error(f"加载元数据失败: {e}")
        return WorkflowMetadataStore()

    def _sync_folders_from_filesystem(self):
        """
        从文件系统同步文件夹结构
        
        扫描 workflows 目录下的所有子目录，完全重建文件夹列表
        文件夹 ID 基于相对路径生成，格式为 "folder:{relative_path}"
        注意：此方法只更新 folders 列表，不会覆盖 workflows 数据
        """
        if not self._workflows_dir or not self._workflows_dir.exists():
            return
        
        new_folders = []
        
        for dir_path in self._workflows_dir.rglob("*"):
            if dir_path.is_dir():
                rel_path = dir_path.relative_to(self._workflows_dir)
                rel_path_str = str(rel_path).replace("\\", "/")
                
                folder_id = f"folder:{rel_path_str}"
                folder_name = dir_path.name
                parent_rel = str(rel_path.parent).replace("\\", "/")
                parent_id = f"folder:{parent_rel}" if parent_rel != "." else None
                
                now = datetime.now().isoformat()
                new_folder = WorkflowFolder(
                    id=folder_id,
                    name=folder_name,
                    parent_id=parent_id,
                    created_at=now,
                    updated_at=now,
                )
                new_folders.append(new_folder)
        
        old_folder_count = len(self._metadata.folders)
        self._metadata.folders = new_folders
        
        if len(new_folders) != old_folder_count:
            logger.info(f"文件夹同步: {old_folder_count} -> {len(new_folders)} 个目录")
            self._save_metadata()

    def _save_metadata(self) -> bool:
        """保存元数据"""
        if not self._metadata_path or not self._metadata:
            return False
        try:
            content = json.dumps(self._metadata.to_dict(), ensure_ascii=False, indent=2)
            self._metadata_path.write_text(content, encoding="utf-8")
            return True
        except Exception as e:
            logger.error(f"保存元数据失败: {e}")
            return False

    def _cleanup_metadata(self):
        """清理不存在的工作流元数据"""
        if not self._workflows_dir or not self._metadata:
            return
        
        existing_files = set()
        for file_path in self._workflows_dir.glob("**/*.json"):
            if file_path.is_file():
                rel_path = file_path.relative_to(self._workflows_dir)
                existing_files.add(str(rel_path).replace("\\", "/"))
        
        to_remove = [k for k in self._metadata.workflows.keys() if k not in existing_files]
        for key in to_remove:
            del self._metadata.workflows[key]
        
        if to_remove:
            self._save_metadata()
            logger.info(f"清理了 {len(to_remove)} 个无效的工作流元数据")

    def get_workflows(self) -> List[Dict[str, Any]]:
        """
        获取所有工作流列表
        
        Returns:
            工作流字典列表
        """
        if not self._ensure_initialized():
            return []
        
        if not self._workflows_dir or not self._workflows_dir.exists():
            logger.warning(f"工作流目录不存在: {self._workflows_dir}")
            return []
        
        self._cleanup_metadata()
        self._sync_folders_from_filesystem()
        
        workflows = []
        for file_path in self._workflows_dir.glob("**/*.json"):
            if file_path.is_file():
                workflow = self._load_workflow_file(file_path)
                if workflow:
                    workflows.append(workflow)
        
        workflows.sort(key=lambda x: x.get("updatedAt", ""), reverse=True)
        return workflows

    def _load_workflow_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        加载单个工作流文件
        
        Args:
            file_path: 工作流文件路径
            
        Returns:
            工作流字典，失败返回 None
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            data = json.loads(content)
            
            # 工作流目录里可能混入非工作流 JSON（如预设列表、配置片段），
            # 顶层不是字典时直接跳过，避免整条加载链路抛异常并刷屏 ERROR 日志
            if not isinstance(data, dict):
                logger.warning(
                    f"跳过非工作流 JSON: {file_path.name}（顶层类型 {type(data).__name__}）"
                )
                return None
            
            rel_path = file_path.relative_to(self._workflows_dir)
            filename = str(rel_path).replace("\\", "/")
            
            logger.debug(f"加载工作流: {filename}")
            
            metadata = self._metadata.workflows.get(filename, WorkflowMetadata())
            
            logger.debug(f"工作流 {filename} 的 previews: {metadata.previews}")
            
            need_save = False
            if not metadata.name:
                default_name = Path(filename).stem
                metadata.name = default_name
                need_save = True
            
            parent_dir = str(rel_path.parent).replace("\\", "/")
            auto_folder_id = f"folder:{parent_dir}" if parent_dir != "." else None
            if metadata.folder_id != auto_folder_id:
                metadata.folder_id = auto_folder_id
                need_save = True
            
            stat = file_path.stat()
            created_at = datetime.fromtimestamp(stat.st_ctime).isoformat()
            updated_at = datetime.fromtimestamp(stat.st_mtime).isoformat()
            
            if need_save:
                self._metadata.workflows[filename] = metadata
                self._save_metadata()
            
            return {
                "id": filename,
                "name": metadata.name,
                "description": metadata.description or "",
                "preview": metadata.previews[0] if metadata.previews else None,
                "previews": metadata.previews or [],
                "nodes": WorkflowParser.extract_node_count(data),
                "tags": metadata.tags or [],
                "isFavorite": metadata.is_favorite,
                "folderId": metadata.folder_id,
                "rawData": data,
                "createdAt": created_at,
                "updatedAt": updated_at,
            }
        except Exception as e:
            logger.error(f"加载工作流失败: {file_path}, {e}")
            return None

    def get_workflow(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        获取单个工作流详情
        
        Args:
            filename: 工作流文件名（相对路径）
            
        Returns:
            工作流字典，不存在返回 None
        """
        if not self._ensure_initialized():
            return None
        
        if not self._workflows_dir:
            return None
        
        file_path = self._workflows_dir / filename
        if not file_path.exists():
            return None
        
        return self._load_workflow_file(file_path)

    def delete_workflow(self, filename: str) -> Dict[str, Any]:
        """
        删除工作流
        
        同时删除 ComfyUI 目录下的文件和预览图
        
        Args:
            filename: 工作流文件名（相对路径）
            
        Returns:
            操作结果
        """
        if not self._ensure_initialized():
            return {"success": False, "error_code": WorkflowErrorCode.CONTROLLER_NOT_INITIALIZED, "error": "控制器未初始化"}
        
        if not self._workflows_dir:
            return {"success": False, "error_code": WorkflowErrorCode.WORKFLOW_DIRECTORY_NOT_SET, "error": "工作流目录未设置"}
        
        file_path = self._workflows_dir / filename
        if not file_path.exists():
            return {"success": False, "error_code": WorkflowErrorCode.WORKFLOW_NOT_FOUND, "error": "工作流不存在"}
        
        try:
            file_path.unlink()
            logger.info(f"删除工作流文件: {file_path}")
            
            if filename in self._metadata.workflows:
                metadata = self._metadata.workflows[filename]
                
                if self._images_dir and metadata.previews:
                    for preview_path in metadata.previews:
                        if preview_path.startswith('images/'):
                            preview_file = self._images_dir / preview_path.replace('images/', '')
                            if preview_file.exists():
                                preview_file.unlink()
                                logger.info(f"删除预览图文件: {preview_file}")
                
                del self._metadata.workflows[filename]
                self._save_metadata()
            
            return {"success": True}
            
        except Exception as e:
            logger.error(f"删除工作流失败: {e}")
            return {"success": False, "error": str(e)}

    def import_workflow(self, file_content: str, filename: Optional[str] = None) -> Dict[str, Any]:
        """
        导入工作流
        
        Args:
            file_content: 工作流 JSON 内容
            filename: 可选的文件名
            
        Returns:
            导入结果，包含工作流信息
        """
        if not self._ensure_initialized():
            return {"success": False, "error_code": WorkflowErrorCode.CONTROLLER_NOT_INITIALIZED, "error": "控制器未初始化"}
        
        if not self._workflows_dir:
            return {"success": False, "error_code": WorkflowErrorCode.WORKFLOW_DIRECTORY_NOT_SET, "error": "工作流目录未设置"}
        
        is_valid, error = WorkflowParser.validate_workflow_json(file_content)
        if not is_valid:
            return {"success": False, "error": error}
        
        try:
            data = json.loads(file_content)
            
            if not filename:
                workflow_name = WorkflowParser.get_workflow_name(data, "workflow")
                filename = f"{workflow_name}.json"
            
            filename = self._sanitize_filename(filename)
            
            file_path = self._workflows_dir / filename
            if file_path.exists():
                base = file_path.stem
                ext = file_path.suffix
                counter = 1
                while file_path.exists():
                    filename = f"{base}_{counter}{ext}"
                    file_path = self._workflows_dir / filename
                    counter += 1
            
            file_path.write_text(file_content, encoding="utf-8")
            
            metadata = self._metadata.workflows.get(filename, WorkflowMetadata())
            
            self._metadata.workflows[filename] = metadata
            self._save_metadata()
            
            workflow = self._load_workflow_file(file_path)
            
            return {
                "success": True,
                "workflow": workflow,
            }
            
        except Exception as e:
            logger.error(f"导入工作流失败: {e}")
            return {"success": False, "error": str(e)}

    def export_workflow(self, filename: str) -> Dict[str, Any]:
        """
        导出工作流
        
        Args:
            filename: 工作流文件名（相对路径）
            
        Returns:
            导出结果，包含 JSON 内容
        """
        if not self._ensure_initialized():
            return {"success": False, "error_code": WorkflowErrorCode.CONTROLLER_NOT_INITIALIZED, "error": "控制器未初始化"}
        
        if not self._workflows_dir:
            return {"success": False, "error_code": WorkflowErrorCode.WORKFLOW_DIRECTORY_NOT_SET, "error": "工作流目录未设置"}
        
        file_path = self._workflows_dir / filename
        if not file_path.exists():
            return {"success": False, "error_code": WorkflowErrorCode.WORKFLOW_NOT_FOUND, "error": "工作流不存在"}
        
        try:
            content = file_path.read_text(encoding="utf-8")
            return {
                "success": True,
                "content": content,
                "filename": filename,
            }
        except Exception as e:
            logger.error(f"导出工作流失败: {e}")
            return {"success": False, "error": str(e)}

    def update_workflow_info(self, filename: str, info: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新工作流信息
        
        Args:
            filename: 工作流文件名（相对路径）
            info: 更新信息（name, description, tags）
            
        Returns:
            更新后的工作流信息
        """
        if not self._ensure_initialized():
            return {"success": False, "error_code": WorkflowErrorCode.CONTROLLER_NOT_INITIALIZED, "error": "控制器未初始化"}
        
        if filename not in self._metadata.workflows:
            self._metadata.workflows[filename] = WorkflowMetadata()
        
        metadata = self._metadata.workflows[filename]
        
        if "name" in info:
            metadata.name = info["name"]
        if "description" in info:
            metadata.description = info["description"]
        if "tags" in info:
            metadata.tags = info["tags"]
        
        self._save_metadata()
        
        workflow = self.get_workflow(filename)
        return {"success": True, "workflow": workflow}

    def toggle_favorite(self, filename: str) -> Dict[str, Any]:
        """
        切换收藏状态
        
        Args:
            filename: 工作流文件名（相对路径）
            
        Returns:
            操作结果，包含新的收藏状态
        """
        if not self._ensure_initialized():
            return {"success": False, "error_code": WorkflowErrorCode.CONTROLLER_NOT_INITIALIZED, "error": "控制器未初始化"}
        
        if filename not in self._metadata.workflows:
            self._metadata.workflows[filename] = WorkflowMetadata()
        
        metadata = self._metadata.workflows[filename]
        metadata.is_favorite = not metadata.is_favorite
        
        self._save_metadata()
        
        return {"success": True, "isFavorite": metadata.is_favorite}

    def get_folders(self) -> List[Dict[str, Any]]:
        """
        获取所有文件夹
        
        Returns:
            文件夹列表
        """
        if not self._ensure_initialized():
            return []
        
        self._sync_folders_from_filesystem()
        
        return [f.to_dict() for f in self._metadata.folders]

    def create_folder(self, name: str, parent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        创建文件夹（实际创建文件系统目录）
        
        Args:
            name: 文件夹名称
            parent_id: 父文件夹 ID（格式为 "folder:{relative_path}"）
            
        Returns:
            创建的文件夹信息
        """
        if not self._ensure_initialized():
            return {"success": False, "error_code": WorkflowErrorCode.CONTROLLER_NOT_INITIALIZED, "error": "控制器未初始化"}
        
        if not self._workflows_dir:
            return {"success": False, "error_code": WorkflowErrorCode.WORKFLOW_DIRECTORY_NOT_SET, "error": "工作流目录未设置"}
        
        import re
        safe_name = re.sub(r'[<>:"/\\|?*]', "_", name)
        safe_name = safe_name.strip("._")
        if not safe_name:
            return {"success": False, "error_code": WorkflowErrorCode.INVALID_FOLDER_NAME, "error": "无效的文件夹名称"}
        
        if parent_id and parent_id.startswith("folder:"):
            parent_path = parent_id[7:].replace("\\", "/")
            target_dir = self._workflows_dir / parent_path / safe_name
        else:
            target_dir = self._workflows_dir / safe_name
        
        if target_dir.exists():
            return {"success": False, "error_code": WorkflowErrorCode.FOLDER_ALREADY_EXISTS, "error": "文件夹已存在"}
        
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            
            rel_path = target_dir.relative_to(self._workflows_dir)
            rel_path_str = str(rel_path).replace("\\", "/")
            folder_id = f"folder:{rel_path_str}"
            
            now = datetime.now().isoformat()
            folder = WorkflowFolder(
                id=folder_id,
                name=safe_name,
                parent_id=parent_id,
                created_at=now,
                updated_at=now,
            )
            
            self._metadata.folders.append(folder)
            self._save_metadata()
            
            logger.info(f"创建文件夹: {target_dir}")
            return {"success": True, "folder": folder.to_dict()}
            
        except Exception as e:
            logger.error(f"创建文件夹失败: {e}")
            return {"success": False, "error": str(e)}

    def update_folder(self, folder_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新文件夹（支持重命名和移动）
        
        Args:
            folder_id: 文件夹 ID（格式为 "folder:{relative_path}"）
            updates: 更新内容（支持 name 和 parentId）
            
        Returns:
            更新后的文件夹信息
        """
        if not self._ensure_initialized():
            return {"success": False, "error_code": WorkflowErrorCode.CONTROLLER_NOT_INITIALIZED, "error": "控制器未初始化"}
        
        if not self._workflows_dir:
            return {"success": False, "error_code": WorkflowErrorCode.WORKFLOW_DIRECTORY_NOT_SET, "error": "工作流目录未设置"}
        
        if not folder_id or not folder_id.startswith("folder:"):
            return {"success": False, "error_code": WorkflowErrorCode.INVALID_FOLDER_ID, "error": "无效的文件夹 ID"}
        
        if "name" not in updates and "parentId" not in updates:
            return {"success": False, "error_code": WorkflowErrorCode.NO_UPDATES_PROVIDED, "error": "没有要更新的内容"}
        
        folder_path = folder_id[7:].replace("\\", "/")
        source_dir = self._workflows_dir / folder_path
        
        if not source_dir.exists():
            return {"success": False, "error_code": WorkflowErrorCode.FOLDER_NOT_FOUND_IN_FILESYSTEM, "error": "文件夹不存在于文件系统"}
        
        import re
        new_name = updates.get("name")
        new_parent_id = updates.get("parentId")
        
        if new_name:
            safe_name = re.sub(r'[<>:"/\\|?*]', "_", new_name)
            safe_name = safe_name.strip("._")
            if not safe_name:
                return {"success": False, "error_code": WorkflowErrorCode.INVALID_FOLDER_NAME, "error": "无效的文件夹名称"}
        else:
            safe_name = source_dir.name
        
        if new_parent_id is not None:
            if new_parent_id == "" or new_parent_id == "root":
                target_parent = self._workflows_dir
            elif new_parent_id.startswith("folder:"):
                parent_path = new_parent_id[7:].replace("\\", "/")
                target_parent = self._workflows_dir / parent_path
                if not target_parent.exists():
                    return {"success": False, "error_code": WorkflowErrorCode.PARENT_FOLDER_NOT_FOUND, "error": "目标父文件夹不存在"}
            else:
                target_parent = self._workflows_dir / new_parent_id
                if not target_parent.exists():
                    return {"success": False, "error_code": WorkflowErrorCode.PARENT_FOLDER_NOT_FOUND, "error": "目标父文件夹不存在"}
        else:
            target_parent = source_dir.parent
        
        target_dir = target_parent / safe_name
        
        if target_dir.exists() and target_dir != source_dir:
            return {"success": False, "error_code": WorkflowErrorCode.FOLDER_ALREADY_EXISTS_SAME_NAME, "error": "目标位置已存在同名文件夹"}
        
        try:
            if source_dir != target_dir:
                import shutil
                target_dir.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source_dir), str(target_dir))
                
                new_folder_id = f"folder:{str(target_dir.relative_to(self._workflows_dir)).replace(chr(92), '/')}"
                
                for i, folder in enumerate(self._metadata.folders):
                    if folder.id == folder_id:
                        folder.id = new_folder_id
                        folder.name = safe_name
                        if new_parent_id is not None:
                            folder.parent_id = new_parent_id if new_parent_id and new_parent_id != "root" else None
                        folder.updated_at = datetime.now().isoformat()
                        self._metadata.folders[i] = folder
                    elif folder.id and folder.id.startswith(f"{folder_id}/"):
                        folder.id = folder.id.replace(folder_id, new_folder_id, 1)
                        if folder.parent_id == folder_id:
                            folder.parent_id = new_folder_id
                        self._metadata.folders[i] = folder
                
                for filename in list(self._metadata.workflows.keys()):
                    metadata = self._metadata.workflows[filename]
                    if metadata.folder_id and metadata.folder_id.startswith(f"{folder_id}/"):
                        metadata.folder_id = metadata.folder_id.replace(folder_id, new_folder_id, 1)
                    elif metadata.folder_id == folder_id:
                        metadata.folder_id = new_folder_id
                    
                    if filename.startswith(f"{folder_path}/"):
                        old_path = self._workflows_dir / filename
                        new_rel_path = filename.replace(f"{folder_path}/", f"{str(target_dir.relative_to(self._workflows_dir)).replace(chr(92), '/')}/", 1)
                        new_path = self._workflows_dir / new_rel_path
                        
                        if old_path.exists() and old_path != new_path:
                            new_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.move(str(old_path), str(new_path))
                            self._metadata.workflows[new_rel_path] = self._metadata.workflows.pop(filename)
                
                self._save_metadata()
                logger.info(f"更新文件夹: {folder_path} -> {str(target_dir.relative_to(self._workflows_dir))}")
                
                updated_folder = next((f for f in self._metadata.folders if f.id == new_folder_id), None)
                return {"success": True, "folder": updated_folder.to_dict() if updated_folder else None}
            else:
                for i, folder in enumerate(self._metadata.folders):
                    if folder.id == folder_id:
                        folder.name = safe_name
                        if new_parent_id is not None:
                            folder.parent_id = new_parent_id if new_parent_id and new_parent_id != "root" else None
                        folder.updated_at = datetime.now().isoformat()
                        self._metadata.folders[i] = folder
                        self._save_metadata()
                        return {"success": True, "folder": folder.to_dict()}
                
                return {"success": False, "error": "文件夹不存在"}
                
        except Exception as e:
            logger.error(f"更新文件夹失败: {e}")
            return {"success": False, "error": str(e)}

    def delete_folder(self, folder_id: str) -> Dict[str, Any]:
        """
        删除文件夹（仅删除空目录）
        
        Args:
            folder_id: 文件夹 ID（格式为 "folder:{relative_path}"）
            
        Returns:
            操作结果
        """
        if not self._ensure_initialized():
            return {"success": False, "error": "控制器未初始化"}
        
        if not self._workflows_dir:
            return {"success": False, "error": "工作流目录未设置"}
        
        if not folder_id or not folder_id.startswith("folder:"):
            return {"success": False, "error": "无效的文件夹 ID"}
        
        folder_path = folder_id[7:].replace("\\", "/")
        target_dir = self._workflows_dir / folder_path
        
        if not target_dir.exists():
            self._metadata.folders = [f for f in self._metadata.folders if f.id != folder_id]
            self._save_metadata()
            return {"success": True, "message": "文件夹已不存在于文件系统"}
        
        try:
            has_files = any(target_dir.rglob("*.json"))
            if has_files:
                return {"success": False, "error": "文件夹不为空，请先移动或删除其中的工作流"}
            
            target_dir.rmdir()
            
            self._metadata.folders = [f for f in self._metadata.folders if f.id != folder_id]
            
            for filename, metadata in self._metadata.workflows.items():
                if metadata.folder_id == folder_id:
                    metadata.folder_id = None
            
            self._save_metadata()
            
            logger.info(f"删除文件夹: {target_dir}")
            return {"success": True}
            
        except OSError as e:
            if "not empty" in str(e).lower() or "非空" in str(e):
                return {"success": False, "error": "文件夹不为空，请先移动或删除其中的工作流"}
            logger.error(f"删除文件夹失败: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"删除文件夹失败: {e}")
            return {"success": False, "error": str(e)}

    def move_to_folder(self, filename: str, folder_id: Optional[str]) -> Dict[str, Any]:
        """
        移动工作流到文件夹（实际移动文件）
        
        Args:
            filename: 工作流文件名（相对路径）
            folder_id: 目标文件夹 ID（格式为 "folder:{relative_path}"，None 表示移到根目录）
            
        Returns:
            操作结果
        """
        if not self._ensure_initialized():
            return {"success": False, "error": "控制器未初始化"}
        
        if not self._workflows_dir:
            return {"success": False, "error": "工作流目录未设置"}
        
        source_path = self._workflows_dir / filename
        if not source_path.exists():
            return {"success": False, "error": "工作流不存在"}
        
        if folder_id and folder_id.startswith("folder:"):
            target_folder = folder_id[7:].replace("\\", "/")
            target_dir = self._workflows_dir / target_folder
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / source_path.name
        else:
            target_dir = self._workflows_dir
            target_path = self._workflows_dir / source_path.name
        
        if target_path.exists() and target_path != source_path:
            base = target_path.stem
            ext = target_path.suffix
            counter = 1
            while target_path.exists():
                target_path = target_dir / f"{base}_{counter}{ext}"
                counter += 1
        
        try:
            if source_path != target_path:
                import shutil
                shutil.move(str(source_path), str(target_path))
                
                new_filename = str(target_path.relative_to(self._workflows_dir)).replace("\\", "/")
                
                if filename in self._metadata.workflows:
                    self._metadata.workflows[new_filename] = self._metadata.workflows.pop(filename)
                
                if new_filename not in self._metadata.workflows:
                    self._metadata.workflows[new_filename] = WorkflowMetadata()
                
                self._metadata.workflows[new_filename].folder_id = folder_id
                self._save_metadata()
                
                logger.info(f"移动工作流: {filename} -> {new_filename}")
                workflow = self._load_workflow_file(target_path)
            else:
                if filename not in self._metadata.workflows:
                    self._metadata.workflows[filename] = WorkflowMetadata()
                self._metadata.workflows[filename].folder_id = folder_id
                self._save_metadata()
                workflow = self.get_workflow(filename)
            
            return {"success": True, "workflow": workflow}
            
        except Exception as e:
            logger.error(f"移动工作流失败: {e}")
            return {"success": False, "error": str(e)}

    def _get_github_url_from_git(self, plugin_path: Path) -> Optional[str]:
        """
        从 .git/config 获取 GitHub URL
        
        Args:
            plugin_path: 插件目录路径
            
        Returns:
            GitHub URL，未找到返回 None
        """
        import configparser
        
        git_config_path = plugin_path / '.git' / 'config'
        if not git_config_path.exists():
            return None
        
        try:
            config = configparser.ConfigParser(strict=False)
            config.read(git_config_path)
            
            for section in config.sections():
                if section.startswith('remote '):
                    url = config.get(section, 'url', fallback=None)
                    if url:
                        url = url.strip()
                        if url.endswith('.git'):
                            url = url[:-4]
                        url = url.replace('git@github.com:', 'https://github.com/')
                        return url.rstrip('/')
        except Exception as e:
            logger.debug(f"读取 git config 失败: {plugin_path}, {e}")
        
        return None

    def check_plugins_status(self, plugins: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        检查插件安装状态
        
        直接扫描 custom_nodes 目录，通过目录名和 GitHub URL 双重匹配
        
        Args:
            plugins: 插件列表，每项包含 {githubUrl: string, name: string}
            
        Returns:
            插件状态字典 {plugin_name: status}
        """
        if not self._ensure_initialized():
            return {"success": False, "error": "控制器未初始化"}
        
        try:
            if not self._environment_manager:
                logger.warning("[check_plugins_status] 环境管理器未设置")
                return {p.get('name', ''): "unknown" for p in plugins}
            
            current_env = self._environment_manager.get_current_environment()
            if not current_env:
                logger.warning("[check_plugins_status] 当前环境未设置")
                return {p.get('name', ''): "unknown" for p in plugins}
            
            comfyui_path = current_env.path
            if not comfyui_path:
                logger.warning("[check_plugins_status] ComfyUI 路径未设置")
                return {p.get('name', ''): "unknown" for p in plugins}
            
            # 收集所有 custom_nodes 路径（主路径 + 外置路径）
            custom_nodes_paths = [Path(comfyui_path) / "custom_nodes"]
            if hasattr(current_env, 'model_path_configs'):
                for config in current_env.model_path_configs:
                    cn_rel = config.paths.get("custom_nodes") or config.paths.get("customNodes")
                    if cn_rel:
                        ext_path = Path(config.base_path) / cn_rel
                        if ext_path.exists() and ext_path not in custom_nodes_paths:
                            custom_nodes_paths.append(ext_path)
            
            installed_plugins = {}
            disabled_plugins = set()
            
            # 遍历所有 custom_nodes 路径
            for custom_nodes_path in custom_nodes_paths:
                if not custom_nodes_path.exists():
                    continue
                
                for item in custom_nodes_path.iterdir():
                    if item.name in ('__pycache__', '.disabled'):
                        continue
                    
                    if item.is_dir():
                        if item.name.endswith('.disabled'):
                            plugin_name = item.name[:-9]
                            if plugin_name not in disabled_plugins:
                                disabled_plugins.add(plugin_name)
                        else:
                            github_url = self._get_github_url_from_git(item)
                            if item.name not in installed_plugins:
                                installed_plugins[item.name] = {
                                    'github_url': github_url,
                                    'enabled': True
                                }
                            if github_url and github_url not in installed_plugins:
                                installed_plugins[github_url] = {
                                    'name': item.name,
                                    'enabled': True
                                }
                
                # 检查 .disabled 目录
                disabled_dir = custom_nodes_path / '.disabled'
                if disabled_dir.exists():
                    for item in disabled_dir.iterdir():
                        if item.is_dir() and item.name not in ('__pycache__',):
                            if item.name not in disabled_plugins:
                                disabled_plugins.add(item.name)
                                github_url = self._get_github_url_from_git(item)
                                if github_url and github_url not in installed_plugins:
                                    installed_plugins[github_url] = {
                                        'name': item.name,
                                        'enabled': False
                                    }
            
            logger.info(f"[check_plugins_status] 扫描完成: 已安装 {len([k for k, v in installed_plugins.items() if v.get('enabled', True)])} 个, 已禁用 {len(disabled_plugins)} 个")
            
            result = {}
            for plugin in plugins:
                plugin_name = plugin.get('name', '')
                github_url = plugin.get('githubUrl', '')
                
                if github_url:
                    github_url = github_url.strip()
                    if github_url.endswith('.git'):
                        github_url = github_url[:-4]
                    github_url = github_url.replace('git@github.com:', 'https://github.com/')
                    github_url = github_url.rstrip('/')
                
                status = 'missing'
                
                if plugin_name in installed_plugins:
                    info = installed_plugins[plugin_name]
                    status = 'installed' if info.get('enabled', True) else 'disabled'
                elif plugin_name in disabled_plugins:
                    status = 'disabled'
                elif github_url and github_url in installed_plugins:
                    info = installed_plugins[github_url]
                    status = 'installed' if info.get('enabled', True) else 'disabled'
                else:
                    if plugin_name:
                        for installed_name in list(installed_plugins.keys()):
                            if installed_name.startswith('http'):
                                continue
                            if plugin_name.lower() == installed_name.lower():
                                info = installed_plugins[installed_name]
                                status = 'installed' if info.get('enabled', True) else 'disabled'
                                break
                
                result[plugin_name] = status
                logger.debug(f"[check_plugins_status] 插件: {plugin_name}, githubUrl: {github_url}, 状态: {status}")
            
            return {"success": True, "status": result}
            
        except Exception as e:
            logger.error(f"检查插件状态失败: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def upload_preview(self, filename: str, image_data: str) -> Dict[str, Any]:
        """
        上传预览图
        
        Args:
            filename: 工作流文件名（相对路径）
            image_data: Base64 编码的图片数据
            
        Returns:
            操作结果
        """
        if not self._ensure_initialized():
            return {"success": False, "error": "控制器未初始化"}
        
        try:
            import base64
            import hashlib
            from pathlib import Path
            
            logger.info(f"上传预览图请求: filename={filename}")
            logger.debug(f"当前元数据中的工作流 keys: {list(self._metadata.workflows.keys())[:5]}...")
            
            # 确保 images 目录存在
            if not self._images_dir:
                return {"success": False, "error": "图片目录未设置"}
            
            self._images_dir.mkdir(parents=True, exist_ok=True)
            
            # 解析 base64 数据
            if image_data.startswith('data:'):
                header, image_data = image_data.split(',', 1)
            
            # 生成唯一文件名
            file_hash = hashlib.md5(f"{filename}_{len(image_data)}".encode()).hexdigest()[:12]
            output_filename = f"{file_hash}_upload.png"
            output_path = self._images_dir / output_filename
            
            # 解码并保存图片
            image_bytes = base64.b64decode(image_data)
            output_path.write_bytes(image_bytes)
            
            logger.info(f"预览图已保存: {output_path}")
            
            # 更新元数据
            if filename not in self._metadata.workflows:
                logger.info(f"工作流 {filename} 不在元数据中，创建新条目")
                self._metadata.workflows[filename] = WorkflowMetadata()
            else:
                logger.info(f"工作流 {filename} 已存在，当前 previews: {self._metadata.workflows[filename].previews}")
            
            metadata = self._metadata.workflows[filename]
            preview_path = f"images/{output_filename}"
            metadata.previews.append(preview_path)
            
            logger.info(f"更新后 previews: {metadata.previews}")
            
            save_result = self._save_metadata()
            logger.info(f"元数据保存结果: {save_result}")
            
            # 验证保存成功
            self._metadata = self._load_metadata()
            if filename in self._metadata.workflows:
                saved_previews = self._metadata.workflows[filename].previews
                if preview_path in saved_previews:
                    logger.info(f"验证成功: previews={saved_previews}")
                else:
                    logger.error(f"验证失败: 期望 {preview_path} 在 {saved_previews} 中")
            else:
                logger.error(f"验证失败: {filename} 不在元数据中")
            
            return {"success": True, "previewPath": preview_path}
            
        except Exception as e:
            logger.error(f"上传预览图失败: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def delete_preview(self, filename: str, preview_index: int) -> Dict[str, Any]:
        """
        删除预览图
        
        Args:
            filename: 工作流文件名（相对路径）
            preview_index: 预览图索引
            
        Returns:
            操作结果
        """
        if not self._ensure_initialized():
            return {"success": False, "error": "控制器未初始化"}
        
        if filename not in self._metadata.workflows:
            return {"success": False, "error": "工作流元数据不存在"}
        
        try:
            metadata = self._metadata.workflows[filename]
            
            if preview_index < 0 or preview_index >= len(metadata.previews):
                return {"success": False, "error": "预览图索引无效"}
            
            preview_path = metadata.previews[preview_index]
            
            # 删除文件
            if preview_path.startswith('images/'):
                file_path = self._images_dir / preview_path.replace('images/', '')
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"删除预览图文件: {file_path}")
            
            # 从元数据中移除
            metadata.previews.pop(preview_index)
            self._save_metadata()
            
            return {"success": True}
            
        except Exception as e:
            logger.error(f"删除预览图失败: {e}")
            return {"success": False, "error": str(e)}

    def _sanitize_filename(self, filename: str) -> str:
        """
        清理文件名，移除非法字符
        
        Args:
            filename: 原始文件名
            
        Returns:
            清理后的文件名
        """
        import re
        filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
        filename = re.sub(r'_+', "_", filename)
        filename = filename.strip("._")
        return filename

    def batch_move_to_folder(self, filenames: List[str], folder_id: Optional[str]) -> Dict[str, Any]:
        """
        批量移动工作流到文件夹
        
        Args:
            filenames: 工作流文件名列表（相对路径）
            folder_id: 目标文件夹 ID（格式为 "folder:{relative_path}"，None 表示移到根目录）
            
        Returns:
            dict: {"success": bool, "moved_count": int, "errors": list}
        """
        if not self._ensure_initialized():
            return {"success": False, "error": "控制器未初始化", "moved_count": 0, "errors": []}
        
        if not self._workflows_dir:
            return {"success": False, "error": "工作流目录未设置", "moved_count": 0, "errors": []}
        
        moved_count = 0
        errors = []
        
        for filename in filenames:
            result = self.move_to_folder(filename, folder_id)
            if result.get("success"):
                moved_count += 1
            else:
                errors.append({"filename": filename, "error": result.get("error", "移动失败")})
        
        return {
            "success": moved_count > 0,
            "moved_count": moved_count,
            "errors": errors
        }

    def batch_toggle_favorite(self, filenames: List[str]) -> Dict[str, Any]:
        """
        批量切换收藏状态
        
        Args:
            filenames: 工作流文件名列表
            
        Returns:
            dict: {"success": bool, "results": dict}
        """
        if not self._ensure_initialized():
            return {"success": False, "error": "控制器未初始化", "results": {}}
        
        results = {}
        success_count = 0
        
        for filename in filenames:
            result = self.toggle_favorite(filename)
            if result.get("success"):
                results[filename] = result.get("isFavorite", False)
                success_count += 1
            else:
                results[filename] = {"error": result.get("error", "切换失败")}
        
        return {
            "success": success_count > 0,
            "results": results
        }

    def batch_delete_workflows(self, filenames: List[str]) -> Dict[str, Any]:
        """
        批量删除工作流
        
        Args:
            filenames: 工作流文件名列表（相对路径）
            
        Returns:
            dict: {"success": bool, "deleted_count": int, "errors": list}
        """
        if not self._ensure_initialized():
            return {"success": False, "error": "控制器未初始化", "deleted_count": 0, "errors": []}
        
        if not self._workflows_dir:
            return {"success": False, "error": "工作流目录未设置", "deleted_count": 0, "errors": []}
        
        deleted_count = 0
        errors = []
        
        for filename in filenames:
            result = self.delete_workflow(filename)
            if result.get("success"):
                deleted_count += 1
            else:
                errors.append({"filename": filename, "error": result.get("error", "删除失败")})
        
        return {
            "success": deleted_count > 0,
            "deleted_count": deleted_count,
            "errors": errors
        }
    
    def scan_local_nodes(self, force: bool = False) -> Dict[str, Any]:
        """
        扫描本地节点
        
        Args:
            force: 是否强制重新扫描
            
        Returns:
            扫描结果
        """
        if not self._environment_manager:
            return {"success": False, "error": "环境管理器未设置"}
        
        current_env = self._environment_manager.get_current_environment()
        if not current_env or not current_env.path:
            return {"success": False, "error": "当前环境未设置"}
        
        try:
            from backend.src.utils.node_mapper import node_mapper
            
            node_mapper.set_comfyui_path(current_env.path)
            result = node_mapper.scan_local_nodes(force=force)
            
            return result
            
        except Exception as e:
            logger.error(f"扫描本地节点失败: {e}")
            return {"success": False, "error": str(e)}
    
    def get_local_node_map(self) -> Dict[str, Any]:
        """
        获取本地节点映射表
        
        如果缓存不存在或需要重新扫描，会自动触发扫描
        
        Returns:
            本地节点映射表
        """
        if not self._environment_manager:
            return {"success": False, "error": "环境管理器未设置"}
        
        current_env = self._environment_manager.get_current_environment()
        if not current_env or not current_env.path:
            return {"success": False, "error": "当前环境未设置"}
        
        try:
            from backend.src.utils.node_mapper import node_mapper
            
            node_mapper.set_comfyui_path(current_env.path)
            
            # 检查是否需要重新扫描
            status = node_mapper.get_local_scan_status()
            needs_rescan = status.get("needsRescan", True)
            has_cache = status.get("hasCache", False)
            
            # 如果需要重新扫描或缓存不存在，自动触发扫描
            if needs_rescan or not has_cache:
                logger.info("检测到需要重新扫描本地节点，正在自动扫描...")
                scan_result = node_mapper.scan_local_nodes(force=not has_cache)
                if not scan_result.get("success"):
                    logger.warning(f"自动扫描失败: {scan_result.get('error')}")
            
            node_map = node_mapper.get_local_node_map()
            
            if node_map:
                return {"success": True, "data": node_map}
            else:
                return {"success": False, "error": "本地节点映射表不存在"}
                
        except Exception as e:
            logger.error(f"获取本地节点映射表失败: {e}")
            return {"success": False, "error": str(e)}
    
    def get_local_scan_status(self) -> Dict[str, Any]:
        """
        获取本地扫描状态
        
        Returns:
            扫描状态
        """
        if not self._environment_manager:
            return {"success": False, "error": "环境管理器未设置", "initialized": False}
        
        current_env = self._environment_manager.get_current_environment()
        if not current_env or not current_env.path:
            return {"success": False, "error": "当前环境未设置", "initialized": False}
        
        try:
            from backend.src.utils.node_mapper import node_mapper
            
            node_mapper.set_comfyui_path(current_env.path)
            status = node_mapper.get_local_scan_status()
            
            return {"success": True, **status}
                
        except Exception as e:
            logger.error(f"获取本地扫描状态失败: {e}")
            return {"success": False, "error": str(e), "initialized": False}
