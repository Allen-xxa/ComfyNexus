"""
模型路径管理器模块

该模块负责管理 ComfyUI 的模型路径配置，包括：
- 添加、更新、删除模型路径配置
- 验证模型路径配置
- 生成 extra_model_paths.yaml 文件
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import yaml

from .types import ModelPathConfig
from ...utils.logger import app_logger as logger

# 写入 YAML 时置于首行的归属标记。
# 只有带该标记的文件才被认为是本应用生成的，允许在「无配置」时清理；
# 用户手工维护的 extra_model_paths.yaml 不含此标记，任何情况下都不会被自动删除。
YAML_OWNERSHIP_MARKER = "# 本文件由 ComfyNexus 自动生成，界面配置变更时会被覆盖"



class ModelPathManager:
    """模型路径管理器"""
    
    def __init__(self, environment_manager=None):
        """
        初始化模型路径管理器
        
        Args:
            environment_manager: EnvironmentManager 实例（用于获取和更新环境）
        """
        self.environment_manager = environment_manager
    
    def _get_environment(self, env_id: str):
        """
        获取环境对象
        
        Args:
            env_id: 环境 ID
            
        Returns:
            Environment 对象或 None
        """
        if not self.environment_manager:
            return None
        return self.environment_manager.config_manager.get_environment(env_id)
    
    def validate_config(self, env_id: str, config: ModelPathConfig, is_update: bool = False, old_name: str = None) -> Tuple[bool, Optional[str]]:
        """
        验证模型路径配置
        
        Args:
            env_id: 环境 ID
            config: 模型路径配置对象
            is_update: 是否为更新操作
            old_name: 更新操作时的旧名称
            
        Returns:
            (是否有效, 错误信息)
        """
        if not config.name or not config.name.strip():
            return False, "配置名称不能为空"
        
        if not config.base_path or not config.base_path.strip():
            return False, "基础路径不能为空"
        
        if not os.path.exists(config.base_path):
            return False, f"基础路径不存在: {config.base_path}"
        
        if not os.path.isdir(config.base_path):
            return False, f"基础路径不是有效目录: {config.base_path}"
        
        environment = self._get_environment(env_id)
        if environment:
            for existing_config in environment.model_path_configs:
                if is_update and old_name and existing_config.name == old_name:
                    continue
                
                if existing_config.name == config.name:
                    return False, f"配置名称 '{config.name}' 已存在"
        
        return True, None
    
    def add_config(self, env_id: str, config: ModelPathConfig) -> dict:
        """
        添加模型路径配置
        
        Args:
            env_id: 环境 ID
            config: 模型路径配置对象
            
        Returns:
            操作结果字典
        """
        if not self.environment_manager:
            return {
                "success": False,
                "error_code": "MANAGER_NOT_INITIALIZED",
                "error_message": "EnvironmentManager 未初始化"
            }
        
        is_valid, error_message = self.validate_config(env_id, config)
        if not is_valid:
            return {
                "success": False,
                "error_code": "VALIDATION_FAILED",
                "error_message": error_message
            }
        
        environment = self._get_environment(env_id)
        if not environment:
            return {
                "success": False,
                "error_code": "ENVIRONMENT_NOT_FOUND",
                "error_message": f"环境 '{env_id}' 不存在"
            }
        
        environment.model_path_configs.append(config)
        
        result = self.environment_manager.update_environment(env_id, environment.to_dict())
        
        if result.get("success"):
            yaml_result = self.generate_yaml(env_id)
            if not yaml_result.get("success"):
                logger.warning(f"警告: YAML 文件生成失败: {yaml_result.get('error_message')}")
        
        return result
    
    def update_config(self, env_id: str, config_name: str, config: ModelPathConfig) -> dict:
        """
        更新模型路径配置
        
        Args:
            env_id: 环境 ID
            config_name: 要更新的配置名称
            config: 新的模型路径配置对象
            
        Returns:
            操作结果字典
        """
        if not self.environment_manager:
            return {
                "success": False,
                "error_code": "MANAGER_NOT_INITIALIZED",
                "error_message": "EnvironmentManager 未初始化"
            }
        
        is_valid, error_message = self.validate_config(env_id, config, is_update=True, old_name=config_name)
        if not is_valid:
            return {
                "success": False,
                "error_code": "VALIDATION_FAILED",
                "error_message": error_message
            }
        
        environment = self._get_environment(env_id)
        if not environment:
            return {
                "success": False,
                "error_code": "ENVIRONMENT_NOT_FOUND",
                "error_message": f"环境 '{env_id}' 不存在"
            }
        
        found = False
        for i, existing_config in enumerate(environment.model_path_configs):
            if existing_config.name == config_name:
                environment.model_path_configs[i] = config
                found = True
                break
        
        if not found:
            return {
                "success": False,
                "error_code": "CONFIG_NOT_FOUND",
                "error_message": f"配置 '{config_name}' 不存在"
            }
        
        result = self.environment_manager.update_environment(env_id, environment.to_dict())
        
        if result.get("success"):
            yaml_result = self.generate_yaml(env_id)
            if not yaml_result.get("success"):
                logger.warning(f"警告: YAML 文件生成失败: {yaml_result.get('error_message')}")
        
        return result
    
    def delete_config(self, env_id: str, config_name: str) -> dict:
        """
        删除模型路径配置
        
        Args:
            env_id: 环境 ID
            config_name: 要删除的配置名称
            
        Returns:
            操作结果字典
        """
        if not self.environment_manager:
            return {
                "success": False,
                "error_code": "MANAGER_NOT_INITIALIZED",
                "error_message": "EnvironmentManager 未初始化"
            }
        
        environment = self._get_environment(env_id)
        if not environment:
            return {
                "success": False,
                "error_code": "ENVIRONMENT_NOT_FOUND",
                "error_message": f"环境 '{env_id}' 不存在"
            }
        
        found = False
        for i, existing_config in enumerate(environment.model_path_configs):
            if existing_config.name == config_name:
                environment.model_path_configs.pop(i)
                found = True
                break
        
        if not found:
            return {
                "success": False,
                "error_code": "CONFIG_NOT_FOUND",
                "error_message": f"配置 '{config_name}' 不存在"
            }
        
        result = self.environment_manager.update_environment(env_id, environment.to_dict())
        
        if result.get("success"):
            yaml_result = self.generate_yaml(env_id)
            if not yaml_result.get("success"):
                logger.warning(f"警告: YAML 文件生成失败: {yaml_result.get('error_message')}")
        
        return result
    
    def _is_generated_by_app(self, yaml_path: Path) -> bool:
        """
        判断 extra_model_paths.yaml 是否由本应用生成

        通过首行归属标记识别。无法读取或标记不匹配时一律视为用户文件，
        宁可保留也不误删。

        Args:
            yaml_path: YAML 文件路径

        Returns:
            bool: 是否为本应用生成
        """
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
            return first_line == YAML_OWNERSHIP_MARKER
        except Exception as e:
            logger.warning(f"读取 YAML 归属标记失败，按用户文件处理: {e}")
            return False

    def generate_yaml(self, env_id: str) -> dict:
        """
        生成 extra_model_paths.yaml 文件
        
        Args:
            env_id: 环境 ID
            
        Returns:
            操作结果字典
        """
        if not self.environment_manager:
            return {
                "success": False,
                "error_code": "MANAGER_NOT_INITIALIZED",
                "error_message": "EnvironmentManager 未初始化"
            }
        
        environment = self._get_environment(env_id)
        if not environment:
            return {
                "success": False,
                "error_code": "ENVIRONMENT_NOT_FOUND",
                "error_message": f"环境 '{env_id}' 不存在"
            }
        
        if not environment.model_path_configs:
            yaml_path = Path(environment.config.general.comfyui_path) / "extra_model_paths.yaml"
            if yaml_path.exists():
                # 关键保护：该文件可能是用户手工维护的，绝不能因为界面里没配置就静默删除。
                # 仅当文件首行带有本应用的生成标记时，才视为可安全清理的产物。
                if not self._is_generated_by_app(yaml_path):
                    logger.warning(
                        f"当前环境未配置模型路径，检测到手工维护的 YAML，已保留不做改动: {yaml_path}"
                    )
                    return {
                        "success": True,
                        "skipped": True,
                        "preserved": True,
                        "message": f"没有模型路径配置，已保留现有 YAML 文件: {yaml_path}"
                    }

                try:
                    yaml_path.unlink()
                except Exception as e:
                    return {
                        "success": False,
                        "error_code": "FILE_DELETE_FAILED",
                        "error_message": f"删除 YAML 文件失败: {str(e)}"
                    }

                return {
                    "success": True,
                    "skipped": True,
                    "message": "没有模型路径配置，已删除本应用生成的 YAML 文件"
                }

            return {
                "success": True,
                "skipped": True,
                "message": "没有模型路径配置，且不存在 YAML 文件，无需生成"
            }
        
        # 字段名映射：前端驼峰命名 -> ComfyUI 下划线命名
        field_mapping = {
            "checkpoints": "checkpoints",
            "clip": "clip",
            "clipVision": "clip_vision",
            "configs": "configs",
            "controlnet": "controlnet",
            "diffusionModels": "diffusion_models",
            "embeddings": "embeddings",
            "loras": "loras",
            "upscaleModels": "upscale_models",
            "vae": "vae",
            "gligen": "gligen",
            "hypernetworks": "hypernetworks",
            "customNodes": "custom_nodes",
            "styleModels": "style_models",
            "diffusers": "diffusers",
            "vaeApprox": "vae_approx",
            "t2iAdapter": "t2i_adapter",
            "latentUpscaleModels": "latent_upscale_models",
            "photomaker": "photomaker",
            "classifiers": "classifiers",
            "modelPatches": "model_patches",
            "audioEncoders": "audio_encoders",
            "frameInterpolation": "frame_interpolation",
        }
        
        yaml_data = {}
        for config in environment.model_path_configs:
            yaml_data[config.name] = {
                "base_path": config.base_path
            }
            for model_type, path in config.paths.items():
                # 映射字段名
                comfyui_field = field_mapping.get(model_type, model_type)
                yaml_data[config.name][comfyui_field] = path
        
        yaml_path = Path(environment.config.general.comfyui_path) / "extra_model_paths.yaml"
        try:
            with open(yaml_path, 'w', encoding='utf-8') as f:
                # 首行写入归属标记，使后续「无配置」场景可以安全区分本应用产物与用户手写文件
                f.write(YAML_OWNERSHIP_MARKER + "\n")
                yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            
            return {
                "success": True,
                "message": f"YAML 文件已生成: {yaml_path}"
            }
        except Exception as e:
            return {
                "success": False,
                "error_code": "FILE_WRITE_FAILED",
                "error_message": f"写入 YAML 文件失败: {str(e)}"
            }
