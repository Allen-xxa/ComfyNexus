"""
AI 配置管理模块

负责 AI 配置的保存、读取和 API Key 加密。
支持多配置模式。

API Key 的密钥由 `backend.src.core.ai.secret_store` 提供：每台安装一个随机生成的
本机密钥，保存在运行数据目录（`data/secrets/ai_fernet.key`），不再使用写在源码里的固定密钥。
历史数据由 `_migrate_api_keys()` 在首次使用时用新密钥重加密（幂等，且有数据库备份）。
"""

import json
import logging
from typing import Optional, List
from datetime import datetime
from backend.src.core.ai import database
from backend.src.core.ai import secret_store
from backend.src.core.ai.database import get_db_connection
from backend.src.core.ai.models import APIConfigEntity

logger = logging.getLogger(__name__)

# 迁移只需在进程生命周期内执行一次
_MIGRATION_DONE = False


class ConfigManager:
    """
    配置管理器
    
    负责 AI 配置的持久化和 API Key 加密。
    """

    def __init__(self):
        # 首次使用时把"历史密钥加密 / 明文"的 API Key 迁移到本机密钥
        global _MIGRATION_DONE
        if not _MIGRATION_DONE:
            _MIGRATION_DONE = True
            try:
                self._migrate_api_keys()
            except Exception as exc:  # 迁移失败不阻断功能：解密侧仍有历史密钥兜底
                logger.error("[配置管理] API Key 迁移失败（不影响使用）: %s", exc)

    # ========== 密钥迁移 ==========

    def _migrate_api_keys(self) -> dict:
        """
        把 api_configs 中由历史共享密钥加密（或明文存放）的 API Key 重新用本机密钥加密。

        幂等：已经用本机密钥加密的行不会被改写，重复调用不产生变化。
        安全：首次真正需要改写前，先把数据库文件复制为 `ai_assistant.db.bak_prekey_<时间戳>`。

        Returns:
            dict: {"scanned": int, "migrated": int, "failed": int, "backup": Optional[str]}
        """
        result = {"scanned": 0, "migrated": 0, "failed": 0, "backup": None}

        with get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT id, api_key FROM api_configs")
                rows = cursor.fetchall()
            except Exception as exc:  # 表还不存在等场景
                logger.info("[配置管理] 跳过 API Key 迁移（读取失败）: %s", exc)
                return result

        for row in rows:
            stored = dict(row).get("api_key") or ""
            if not stored:
                continue
            result["scanned"] += 1
            try:
                plaintext, needs_rewrite = secret_store.decrypt_secret(stored)
            except secret_store.SecretKeyError as exc:
                result["failed"] += 1
                logger.warning("[配置管理] 无法解密配置 %s，保持原值: %s", row["id"], exc)
                continue
            if not needs_rewrite:
                continue

            if result["backup"] is None:
                result["backup"] = self._backup_database_file()

            new_stored = secret_store.encrypt_secret(plaintext)
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE api_configs SET api_key = ? WHERE id = ?",
                    (new_stored, row["id"]),
                )
                conn.commit()
            result["migrated"] += 1

        if result["migrated"] or result["failed"]:
            logger.info(
                "[配置管理] API Key 迁移完成: 扫描 %s，重加密 %s，失败 %s，备份 %s",
                result["scanned"],
                result["migrated"],
                result["failed"],
                result["backup"] or "未需要",
            )
        return result

    @staticmethod
    def _backup_database_file() -> Optional[str]:
        """迁移前备份数据库文件；失败只告警。"""
        import shutil

        db_path = database.DB_PATH
        if not db_path.exists():
            logger.warning("[配置管理] 数据库文件不存在，跳过备份: %s", db_path)
            return None
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = db_path.with_name(f"{db_path.name}.bak_prekey_{stamp}")
        try:
            shutil.copy2(db_path, backup_path)
            return str(backup_path)
        except OSError as exc:
            logger.error("[配置管理] 数据库备份失败: %s", exc)
            return None

    # ========== 多配置管理方法 ==========
    
    def list_configs(self) -> List[APIConfigEntity]:
        """
        获取所有 API 配置列表
        
        Returns:
            List[APIConfigEntity]: 配置实体列表
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM api_configs
                    ORDER BY updated_at DESC
                """)
                rows = cursor.fetchall()
            
            configs = []
            for row in rows:
                # 转换为字典
                config_dict = dict(row)
                
                # 解析 JSON 字段
                config_dict["models"] = json.loads(config_dict["models"])
                if config_dict["extra"]:
                    config_dict["extra"] = json.loads(config_dict["extra"])
                else:
                    config_dict["extra"] = {}
                
                # 转换布尔值
                config_dict["is_default"] = bool(config_dict["is_default"])
                config_dict["use_system_proxy"] = bool(config_dict.get("use_system_proxy", 0))
                
                # 解密 API Key
                if config_dict["api_key"]:
                    config_dict["api_key"] = self._decrypt_api_key_for_read(
                        config_dict["api_key"]
                    )
                
                # 创建配置实体
                config = APIConfigEntity.from_dict(config_dict)
                configs.append(config)
            
            return configs
        except Exception as e:
            print(f"获取配置列表失败: {e}")
            return []
    
    def get_config_by_id(self, config_id: str) -> Optional[APIConfigEntity]:
        """
        根据 ID 获取配置
        
        Args:
            config_id: 配置 ID
            
        Returns:
            Optional[APIConfigEntity]: 配置实体，不存在则返回 None
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM api_configs WHERE id = ?
                """, (config_id,))
                row = cursor.fetchone()
            
            if row is None:
                return None
            
            # 转换为字典
            config_dict = dict(row)
            
            # 解析 JSON 字段
            config_dict["models"] = json.loads(config_dict["models"])
            if config_dict["extra"]:
                config_dict["extra"] = json.loads(config_dict["extra"])
            else:
                config_dict["extra"] = {}
            
            # 转换布尔值
            config_dict["is_default"] = bool(config_dict["is_default"])
            config_dict["use_system_proxy"] = bool(config_dict.get("use_system_proxy", 0))
            
            # 解密 API Key
            if config_dict["api_key"]:
                config_dict["api_key"] = self._decrypt_api_key_for_read(
                    config_dict["api_key"]
                )
            
            # 创建配置实体
            return APIConfigEntity.from_dict(config_dict)
        except Exception as e:
            print(f"获取配置失败: {e}")
            return None
    
    def create_config(self, config: APIConfigEntity, require_api_key: bool = True) -> str:
        """
        创建新配置
        
        Args:
            config: 配置实体
            require_api_key: 是否强制要求 API Key（仅导入其它设备配置时为 False）
            
        Returns:
            str: 新创建的配置 ID
            
        Raises:
            ValueError: 配置验证失败时抛出
        """
        # 验证配置
        config.validate(require_api_key=require_api_key)
        
        try:
            # 加密 API Key
            encrypted_api_key = self._encrypt_single_api_key(config.api_key)
            
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO api_configs (
                        id, alias, provider, api_key, base_url, model, models,
                        extra, is_default, status, last_tested_at, last_test_latency,
                        usage_count, use_system_proxy, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    config.id,
                    config.alias,
                    config.provider,
                    encrypted_api_key,
                    config.base_url,
                    config.model,
                    json.dumps(config.models, ensure_ascii=False),
                    json.dumps(config.extra, ensure_ascii=False) if config.extra else None,
                    1 if config.is_default else 0,
                    config.status,
                    config.last_tested_at,
                    config.last_test_latency,
                    config.usage_count,
                    1 if config.use_system_proxy else 0,
                    config.created_at,
                    config.updated_at
                ))
                conn.commit()
            
            return config.id
        except Exception as e:
            print(f"创建配置失败: {e}")
            raise
    
    def update_config(self, config_id: str, config: APIConfigEntity) -> bool:
        """
        更新配置
        
        Args:
            config_id: 配置 ID
            config: 配置实体
            
        Returns:
            bool: 更新是否成功
            
        Raises:
            ValueError: 配置验证失败时抛出
        """
        # 验证配置
        config.validate()
        
        try:
            # 加密 API Key
            encrypted_api_key = self._encrypt_single_api_key(config.api_key)
            
            # 更新时间戳
            config.updated_at = datetime.now().isoformat()
            
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE api_configs SET
                        alias = ?,
                        provider = ?,
                        api_key = ?,
                        base_url = ?,
                        model = ?,
                        models = ?,
                        extra = ?,
                        is_default = ?,
                        status = ?,
                        last_tested_at = ?,
                        last_test_latency = ?,
                        usage_count = ?,
                        use_system_proxy = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (
                    config.alias,
                    config.provider,
                    encrypted_api_key,
                    config.base_url,
                    config.model,
                    json.dumps(config.models, ensure_ascii=False),
                    json.dumps(config.extra, ensure_ascii=False) if config.extra else None,
                    1 if config.is_default else 0,
                    config.status,
                    config.last_tested_at,
                    config.last_test_latency,
                    config.usage_count,
                    1 if config.use_system_proxy else 0,
                    config.updated_at,
                    config_id
                ))
                conn.commit()
            
            return cursor.rowcount > 0
        except Exception as e:
            print(f"更新配置失败: {e}")
            return False
    
    def delete_config(self, config_id: str) -> bool:
        """
        删除配置
        
        Args:
            config_id: 配置 ID
            
        Returns:
            bool: 删除是否成功
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM api_configs WHERE id = ?
                """, (config_id,))
                conn.commit()
            
            return cursor.rowcount > 0
        except Exception as e:
            print(f"删除配置失败: {e}")
            return False
    
    def _encrypt_single_api_key(self, api_key: str) -> str:
        """
        加密单个 API Key
        
        Args:
            api_key: 明文 API Key
            
        Returns:
            str: 加密后的 API Key（带 encrypted: 前缀）
        
        Note:
            密钥来自本机密钥文件 `data/secrets/ai_fernet.key`（首次运行自动生成），
            不再是源码里的固定常量，见 `secret_store` 模块说明。
        """
        return secret_store.encrypt_secret(api_key)
    
    def _decrypt_single_api_key(self, encrypted_api_key: str) -> str:
        """
        解密单个 API Key
        
        Args:
            encrypted_api_key: 加密的 API Key（带 encrypted: 前缀）
            
        Returns:
            str: 明文 API Key
        
        Note:
            - 本机密钥能解开 → 直接返回
            - 只有历史共享密钥能解开 → 返回明文（`_migrate_api_keys()` 负责改成新密文）
            - 没有前缀的历史明文 → 原样返回（向后兼容，迁移时会补加密）
            - 两种密钥都解不开 → 抛出 SecretKeyError
        """
        plaintext, _needs_rewrite = secret_store.decrypt_secret(encrypted_api_key)
        return plaintext

    def _decrypt_api_key_for_read(self, encrypted_api_key: str) -> str:
        """
        读取路径的容错解密：解不开时返回空串，而不是让整次读取失败。

        Args:
            encrypted_api_key: 数据库中保存的 API Key 原文（可能带 encrypted: 前缀）

        Returns:
            str: 明文 API Key；无法解密时返回 ""

        Note:
            `list_configs()` / `get_config_by_id()` / `get_default_config()` 都走这里。
            若某行的密钥解不开（例如本机 `data/secrets/ai_fernet.key` 被删除或更换），
            返回空串会让 `to_masked_dict()` 给出 `has_api_key=False`，界面提示重新填写；
            旧实现会让 `list_configs()` 直接返回空列表，整个配置页变成空白。
        """
        try:
            return self._decrypt_single_api_key(encrypted_api_key)
        except secret_store.SecretKeyError as exc:
            logger.warning(
                "[配置管理] API Key 无法解密，已按未配置处理（需要重新填写）: %s", exc
            )
            return ""

    def _normalize_imported_api_key(self, config_dict: dict, errors: List[str]) -> bool:
        """
        把导入 JSON 里的 `api_key` 还原成明文，供 `create_config()` 用本机密钥重新加密

        Args:
            config_dict: 单条导入配置（原地修改其 api_key 字段）
            errors: 导入错误列表（原地追加用户可见提示）

        Returns:
            bool: 密钥是否可用（False 表示已清空，需要用户重新填写）

        Note:
            - 明文（历史导出文件/手工编辑）：原样保留
            - 本机密钥或历史密钥可解的密文：解密成明文，避免"密文再套一层密文"
            - 解不开（来自另一台设备的导出文件）：清空密钥，其余字段照常导入并提示重新填写
        """
        stored = config_dict.get("api_key") or ""
        if not isinstance(stored, str):
            config_dict["api_key"] = ""
            return False
        if not stored or not stored.startswith(secret_store.ENCRYPTED_PREFIX):
            return True

        try:
            plaintext, _ = secret_store.decrypt_secret(stored)
        except secret_store.SecretKeyError:
            config_dict["api_key"] = ""
            alias = config_dict.get("alias") or config_dict.get("id") or "unknown"
            errors.append(
                f"配置 {alias} 的 API Key 无法解密（可能来自另一台设备的导出文件），"
                "其余设置已导入，请重新填写 API Key"
            )
            return False

        config_dict["api_key"] = plaintext
        return True
    
    def set_default_config(self, config_id: str) -> bool:
        """
        设置默认配置
        
        Args:
            config_id: 配置 ID
            
        Returns:
            bool: 设置是否成功
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # 首先清除所有默认配置标记
                cursor.execute("""
                    UPDATE api_configs SET is_default = 0
                """)
                
                # 设置指定配置为默认
                cursor.execute("""
                    UPDATE api_configs SET is_default = 1
                    WHERE id = ?
                """, (config_id,))
                
                conn.commit()
            
            return cursor.rowcount > 0
        except Exception as e:
            print(f"设置默认配置失败: {e}")
            return False
    
    def get_default_config(self) -> Optional[APIConfigEntity]:
        """
        获取默认配置
        
        Returns:
            Optional[APIConfigEntity]: 默认配置实体，不存在则返回 None
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM api_configs WHERE is_default = 1
                """)
                row = cursor.fetchone()
            
            if row is None:
                return None
            
            # 转换为字典
            config_dict = dict(row)
            
            # 解析 JSON 字段
            config_dict["models"] = json.loads(config_dict["models"])
            if config_dict["extra"]:
                config_dict["extra"] = json.loads(config_dict["extra"])
            else:
                config_dict["extra"] = {}
            
            # 转换布尔值
            config_dict["is_default"] = bool(config_dict["is_default"])
            config_dict["use_system_proxy"] = bool(config_dict.get("use_system_proxy", 0))
            
            # 解密 API Key
            if config_dict["api_key"]:
                config_dict["api_key"] = self._decrypt_api_key_for_read(
                    config_dict["api_key"]
                )
            
            # 创建配置实体
            return APIConfigEntity.from_dict(config_dict)
        except Exception as e:
            print(f"获取默认配置失败: {e}")
            return None
    
    def increment_usage_count(self, config_id: str) -> bool:
        """
        增加配置使用计数
        
        Args:
            config_id: 配置 ID
            
        Returns:
            bool: 更新是否成功
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE api_configs 
                    SET usage_count = usage_count + 1,
                        updated_at = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), config_id))
                conn.commit()
            
            return cursor.rowcount > 0
        except Exception as e:
            print(f"增加使用计数失败: {e}")
            return False
    
    def update_test_status(
        self, 
        config_id: str, 
        status: str, 
        latency: Optional[float] = None
    ) -> bool:
        """
        更新配置测试状态
        
        Args:
            config_id: 配置 ID
            status: 状态（"available" | "unavailable"）
            latency: 响应延迟（毫秒）
            
        Returns:
            bool: 更新是否成功
        """
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE api_configs 
                    SET status = ?,
                        last_tested_at = ?,
                        last_test_latency = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (
                    status,
                    datetime.now().isoformat(),
                    latency,
                    datetime.now().isoformat(),
                    config_id
                ))
                conn.commit()
            
            return cursor.rowcount > 0
        except Exception as e:
            print(f"更新测试状态失败: {e}")
            return False
    
    def export_configs(self, config_ids: Optional[List[str]] = None) -> str:
        """
        导出配置为 JSON 格式
        
        Args:
            config_ids: 要导出的配置 ID 列表，None 表示导出所有配置
            
        Returns:
            str: JSON 格式的配置数据
            
        Note:
            导出文件里的 `api_key` 用**本机** `data/secrets/ai_fernet.key` 加密，
            因此只能导回同一台机器的同一个安装；换机导入时密钥无法解密，
            `import_configs()` 会清空该字段并在 errors 中提示用户重新填写。
            
        验证需求：10.1, 10.2
        """
        try:
            # 获取要导出的配置
            if config_ids is None:
                configs = self.list_configs()
            else:
                configs = [
                    self.get_config_by_id(config_id) 
                    for config_id in config_ids
                ]
                # 过滤掉不存在的配置
                configs = [c for c in configs if c is not None]
            
            # 转换为字典列表
            export_data = []
            for config in configs:
                config_dict = config.to_dict()
                
                # 加密 API Key（确保导出时 API Key 是加密的）
                if config_dict["api_key"]:
                    config_dict["api_key"] = self._encrypt_single_api_key(
                        config_dict["api_key"]
                    )
                
                export_data.append(config_dict)
            
            # 构建导出结构
            export_structure = {
                "version": "1.0",
                "exported_at": datetime.now().isoformat(),
                "configs": export_data
            }
            
            # 转换为 JSON
            return json.dumps(export_structure, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"导出配置失败: {e}")
            raise
    
    def import_configs(
        self, 
        import_json: str, 
        conflict_strategy: str = "skip"
    ) -> dict:
        """
        从 JSON 导入配置
        
        Args:
            import_json: JSON 格式的配置数据
            conflict_strategy: 冲突处理策略（"skip" 跳过, "overwrite" 覆盖）
            
        Returns:
            dict: 导入结果 {
                "success": bool,
                "imported": int,  # 成功导入的数量
                "skipped": int,   # 跳过的数量
                "errors": List[str]  # 错误信息列表
            }
        
        Note:
            导入的 `api_key` 会先解密再用本机密钥重新加密（见 `_normalize_imported_api_key()`），
            避免出现"密文再套一层密文"。解不开（例如来自另一台设备的导出文件）时，
            该配置的其余字段照常导入，但密钥清空并在 `errors` 中提示用户重新填写。
            
        验证需求：10.3, 10.4
        """
        result = {
            "success": False,
            "imported": 0,
            "skipped": 0,
            "errors": []
        }
        
        try:
            # 解析 JSON
            try:
                import_data = json.loads(import_json)
            except json.JSONDecodeError as e:
                result["errors"].append(f"JSON 格式无效: {str(e)}")
                return result
            
            # 验证导入数据格式
            if not isinstance(import_data, dict):
                result["errors"].append("导入数据格式错误：应为对象")
                return result
            
            if "configs" not in import_data:
                result["errors"].append("导入数据缺少 configs 字段")
                return result
            
            if not isinstance(import_data["configs"], list):
                result["errors"].append("configs 字段应为数组")
                return result
            
            # 获取现有配置 ID 列表
            existing_configs = self.list_configs()
            existing_ids = {config.id for config in existing_configs}
            
            # 导入每个配置
            for config_dict in import_data["configs"]:
                try:
                    # 检查必填字段
                    required_fields = ["id", "alias", "provider", "model"]
                    for field in required_fields:
                        if field not in config_dict:
                            result["errors"].append(
                                f"配置缺少必填字段: {field}"
                            )
                            result["skipped"] += 1
                            continue
                    
                    config_id = config_dict["id"]
                    
                    # 处理冲突
                    if config_id in existing_ids:
                        if conflict_strategy == "skip":
                            result["skipped"] += 1
                            continue
                        elif conflict_strategy == "overwrite":
                            # 删除现有配置
                            self.delete_config(config_id)
                    
                    # API Key 归一化：导出文件里存的是密文，先还原成明文，
                    # 再由 create_config() 用本机密钥重新加密（否则会二次加密）
                    api_key_usable = self._normalize_imported_api_key(
                        config_dict, result["errors"]
                    )
                    
                    # 创建配置实体
                    config = APIConfigEntity.from_dict(config_dict)
                    
                    # 验证配置（密钥解不开时允许先导入，用户补填后可用）
                    config.validate(require_api_key=api_key_usable)
                    
                    # 创建配置
                    self.create_config(config, require_api_key=api_key_usable)
                    result["imported"] += 1
                    
                except ValueError as e:
                    result["errors"].append(f"配置验证失败 ({config_dict.get('alias', 'unknown')}): {str(e)}")
                    result["skipped"] += 1
                except Exception as e:
                    result["errors"].append(f"导入配置失败 ({config_dict.get('alias', 'unknown')}): {str(e)}")
                    result["skipped"] += 1
            
            result["success"] = result["imported"] > 0
            return result
            
        except Exception as e:
            result["errors"].append(f"导入过程异常: {str(e)}")
            return result

