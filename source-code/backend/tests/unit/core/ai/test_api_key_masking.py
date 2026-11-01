"""AI 配置密钥不落前端 / 不二次加密 的回归测试

覆盖整改点：
- `ai_list_configs` / `ai_get_config_detail` 只返回 `api_key_masked` + `has_api_key`
- 前端回传掩码或留空时，`ai_update_config` 保持数据库里的原密钥
- 测试连接/拉取模型按 `config_id` 由后端补齐真实密钥
- 历史密钥（硬编码 Fernet key）加密的数据迁移到本机密钥，幂等且先备份数据库
- 导出→导入同机往返不会出现"密文再套密文"；异机导入清空密钥但保留其余设置
- 单行密钥解不开时只影响该行（空密钥 + has_api_key=False），不再让整张列表读取失败
"""

import sqlite3
import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

_BACKEND_DIR = Path(__file__).resolve().parents[4]
_SOURCE_ROOT = _BACKEND_DIR.parent
for _p in (str(_BACKEND_DIR), str(_SOURCE_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.src.core.ai import config_manager as config_manager_module  # noqa: E402
from backend.src.core.ai import database, secret_store  # noqa: E402
from backend.src.core.ai.config_manager import ConfigManager  # noqa: E402
from backend.src.core.ai.models import APIConfigEntity  # noqa: E402

SECRET = "sk-real-key-0123456789abcdef"


@pytest.fixture
def temp_ai_db(tmp_path, monkeypatch):
    """临时数据库 + 临时本机密钥，并关闭自动迁移（迁移用例单独触发）。"""
    key_path = tmp_path / "secrets" / "ai_fernet.key"
    db_path = tmp_path / "ai_assistant.db"

    secret_store.set_key_path_for_testing(key_path)
    monkeypatch.setattr(database, "DB_PATH", db_path)
    # 迁移只需在进程内跑一次，测试里默认关掉，避免干扰用例
    monkeypatch.setattr(config_manager_module, "_MIGRATION_DONE", True)

    database.init_database()
    try:
        yield db_path
    finally:
        secret_store.set_key_path_for_testing(None)
        secret_store.reset_cipher_cache()


def make_controller():
    """构造只带 config_manager 的控制器实例（跳过 pywebview/默认配置等重初始化）。"""
    from backend.src.bridge.controllers.ai_controller import AIController

    controller = AIController.__new__(AIController)
    controller.window = None
    controller.config_manager = ConfigManager()
    return controller


def insert_raw_key(db_path: Path, config_id: str, stored_value: str, alias: str = "历史配置") -> None:
    """直接写库，模拟旧版本遗留的 api_key 存储形态。"""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO api_configs (
                id, alias, provider, api_key, base_url, model, models, extra,
                is_default, status, usage_count, use_system_proxy, created_at, updated_at
            ) VALUES (?, ?, 'openai', ?, 'https://api.openai.com/v1', 'gpt-4', '[]', NULL,
                      0, 'untested', 0, 0, '2024-01-01T00:00:00', '2024-01-01T00:00:00')
            """,
            (config_id, alias, stored_value),
        )
        conn.commit()
    finally:
        conn.close()


def read_raw_key(db_path: Path, config_id: str) -> str:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT api_key FROM api_configs WHERE id = ?", (config_id,)).fetchone()
        return row[0] if row else ""
    finally:
        conn.close()


def run_migration_once() -> dict:
    """直接执行一次迁移，绕开 __init__ 的"进程内只跑一次"开关。"""
    manager = ConfigManager.__new__(ConfigManager)
    return manager._migrate_api_keys()


# ==================== 迁移 ====================


def test_历史密钥密文迁移为本机密钥密文(temp_ai_db):
    legacy = f"{secret_store.ENCRYPTED_PREFIX}{Fernet(secret_store.LEGACY_KEY).encrypt(SECRET.encode()).decode()}"
    insert_raw_key(temp_ai_db, "cfg-legacy", legacy)

    result = run_migration_once()

    assert result["migrated"] == 1
    assert result["failed"] == 0
    stored = read_raw_key(temp_ai_db, "cfg-legacy")
    assert stored.startswith(secret_store.ENCRYPTED_PREFIX)
    # 迁移后由本机密钥解密，不再要求重写
    assert secret_store.decrypt_secret(stored) == (SECRET, False)


def test_迁移是幂等的且只备份一次(temp_ai_db):
    legacy = f"{secret_store.ENCRYPTED_PREFIX}{Fernet(secret_store.LEGACY_KEY).encrypt(SECRET.encode()).decode()}"
    insert_raw_key(temp_ai_db, "cfg-idem", legacy)

    first = run_migration_once()
    backups_after_first = sorted(temp_ai_db.parent.glob("ai_assistant.db.bak_prekey_*"))
    second = run_migration_once()
    backups_after_second = sorted(temp_ai_db.parent.glob("ai_assistant.db.bak_prekey_*"))

    assert first["migrated"] == 1
    assert first["backup"] is not None
    assert len(backups_after_first) == 1
    assert second["migrated"] == 0
    assert len(backups_after_second) == 1
    # 备份文件内容仍是迁移前的原始密文
    conn = sqlite3.connect(backups_after_first[0])
    try:
        backup_value = conn.execute(
            "SELECT api_key FROM api_configs WHERE id = 'cfg-idem'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert backup_value == legacy


def test_明文历史值被补加密(temp_ai_db):
    insert_raw_key(temp_ai_db, "cfg-plain", SECRET)

    result = run_migration_once()

    assert result["migrated"] == 1
    assert read_raw_key(temp_ai_db, "cfg-plain") != SECRET
    assert secret_store.decrypt_secret(read_raw_key(temp_ai_db, "cfg-plain"))[0] == SECRET


def test_解不开的行保持原值不丢数据(temp_ai_db):
    broken = f"{secret_store.ENCRYPTED_PREFIX}{Fernet.generate_key().decode()}"
    insert_raw_key(temp_ai_db, "cfg-broken", broken)

    result = run_migration_once()

    assert result["failed"] == 1
    assert result["migrated"] == 0
    assert read_raw_key(temp_ai_db, "cfg-broken") == broken


def test_迁移失败不阻断配置读取(temp_ai_db, monkeypatch):
    insert_raw_key(temp_ai_db, "cfg-broken", f"{secret_store.ENCRYPTED_PREFIX}zzzz")
    monkeypatch.setattr(config_manager_module, "_MIGRATION_DONE", False)

    manager = ConfigManager()  # __init__ 内部吞掉异常，仅记日志

    # 迁移没跑成也不能让配置页空白：该行按"未配置密钥"返回，其余字段照常可读
    configs = manager.list_configs()

    assert [c.id for c in configs] == ["cfg-broken"]
    assert configs[0].api_key == ""
    assert configs[0].alias == "历史配置"


# ==================== 对外接口只回掩码 ====================


def test_创建后列表与详情不回传明文密钥(temp_ai_db):
    controller = make_controller()
    created = controller.ai_create_config(
        {
            "alias": "主力账号",
            "provider": "openai",
            "api_key": SECRET,
            "model": "gpt-4",
        }
    )
    assert created["success"] is True
    config_id = created["config_id"]

    listed = controller.ai_list_configs()
    assert listed["success"] is True
    item = listed["configs"][0]
    assert "api_key" not in item
    assert item["api_key_masked"] == secret_store.mask_api_key(SECRET)
    assert item["has_api_key"] is True
    assert SECRET not in str(listed)

    detail = controller.ai_get_config_detail(config_id)
    assert "api_key" not in detail["config"]
    assert detail["config"]["has_api_key"] is True
    assert SECRET not in str(detail)


def test_无密钥配置的掩码字段(temp_ai_db):
    controller = make_controller()
    controller.ai_create_config(
        {"alias": "本地模型", "provider": "ollama", "api_key": "", "model": "qwen2"}
    )

    item = controller.ai_list_configs()["configs"][0]

    assert item["api_key_masked"] == ""
    assert item["has_api_key"] is False


def test_更新时掩码与留空都保持原密钥(temp_ai_db):
    controller = make_controller()
    config_id = controller.ai_create_config(
        {"alias": "待更新", "provider": "openai", "api_key": SECRET, "model": "gpt-4"}
    )["config_id"]

    mask = secret_store.mask_api_key(SECRET)
    for payload in ({"api_key": mask, "alias": "沿用掩码"}, {"api_key": "", "alias": "留空沿用"}):
        assert controller.ai_update_config(config_id, payload)["success"] is True
        assert controller.config_manager.get_config_by_id(config_id).api_key == SECRET


def test_更新时下发新密钥才覆盖原密钥(temp_ai_db):
    controller = make_controller()
    config_id = controller.ai_create_config(
        {"alias": "换密钥", "provider": "openai", "api_key": SECRET, "model": "gpt-4"}
    )["config_id"]

    new_key = "sk-brand-new-key-987654"
    assert controller.ai_update_config(config_id, {"api_key": new_key})["success"] is True

    assert controller.config_manager.get_config_by_id(config_id).api_key == new_key


def test_按config_id补齐真实密钥供测试连接使用(temp_ai_db):
    controller = make_controller()
    config_id = controller.ai_create_config(
        {"alias": "补齐", "provider": "openai", "api_key": SECRET, "model": "gpt-4"}
    )["config_id"]

    mask = secret_store.mask_api_key(SECRET)
    hydrated = controller._hydrate_api_key_from_store({"config_id": config_id, "api_key": mask})
    assert hydrated["api_key"] == SECRET

    # 没带 config_id 时不做任何猜测
    untouched = controller._hydrate_api_key_from_store({"api_key": mask})
    assert untouched["api_key"] == mask

    # 表单里用户新输了密钥，则尊重表单值
    typed = controller._hydrate_api_key_from_store(
        {"config_id": config_id, "api_key": "sk-typed-by-user-1"}
    )
    assert typed["api_key"] == "sk-typed-by-user-1"


# ==================== 导出 / 导入 ====================


def test_导出导入同机往返不会二次加密(temp_ai_db):
    controller = make_controller()
    controller.ai_create_config(
        {"alias": "导出源", "provider": "openai", "api_key": SECRET, "model": "gpt-4"}
    )
    exported = controller.config_manager.export_configs()

    # 换一台"机器"（同密钥、空库）导入：不能出现密文再套密文
    for row in controller.config_manager.list_configs():
        controller.config_manager.delete_config(row.id)

    result = controller.config_manager.import_configs(exported, conflict_strategy="overwrite")

    assert result["imported"] == 1
    assert controller.config_manager.list_configs()[0].api_key == SECRET


def test_异机导入时清空无法解密的密钥并提示用户(temp_ai_db, tmp_path, monkeypatch):
    controller = make_controller()
    controller.ai_create_config(
        {"alias": "异机配置", "provider": "openai", "api_key": SECRET, "model": "gpt-4"}
    )
    exported = controller.config_manager.export_configs()
    controller.config_manager.delete_config(
        controller.config_manager.list_configs()[0].id
    )

    # 换成本机没有的新密钥（模拟导出文件被拿到另一台设备）
    secret_store.reset_cipher_cache()
    secret_store.set_key_path_for_testing(tmp_path / "other_machine" / "ai_fernet.key")
    monkeypatch.setattr(config_manager_module, "_MIGRATION_DONE", True)

    result = ConfigManager().import_configs(exported, conflict_strategy="overwrite")

    assert result["imported"] == 1
    imported = ConfigManager().list_configs()[0]
    assert imported.api_key == ""
    assert any("无法解密" in msg for msg in result["errors"])


def test_to_masked_dict字段契约(temp_ai_db):
    entity = APIConfigEntity.create(
        alias="契约", provider="openai", api_key=SECRET, model="gpt-4"
    )

    masked = entity.to_masked_dict()

    assert "api_key" not in masked
    assert masked["api_key_masked"] == secret_store.mask_api_key(SECRET)
    assert masked["has_api_key"] is True
    assert SECRET not in str(masked)


def _foreign_ciphertext() -> str:
    """用一把既不是本机密钥、也不是历史共享密钥的 Fernet key 造出解不开的密文。"""
    token = Fernet(Fernet.generate_key()).encrypt(SECRET.encode("utf-8"))
    return f"{secret_store.ENCRYPTED_PREFIX}{token.decode('utf-8')}"


def test_单行密钥解不开时列表读取不被整表拖垮(temp_ai_db):
    db_path = temp_ai_db
    manager = ConfigManager()
    good = manager.create_config(
        APIConfigEntity.create(
            alias="可用配置", provider="openai", api_key=SECRET, model="gpt-4"
        )
    )
    insert_raw_key(db_path, "broken-row", _foreign_ciphertext(), alias="密钥丢失的配置")

    configs = manager.list_configs()

    # 旧实现：任一行解密失败 -> list_configs() 返回 []，配置页整个空白
    assert len(configs) == 2
    by_id = {c.id: c for c in configs}
    assert by_id[good].api_key == SECRET
    assert by_id["broken-row"].api_key == ""
    assert SECRET not in str(by_id["broken-row"])


def test_单行密钥解不开时详情返回空密钥而非None(temp_ai_db):
    insert_raw_key(temp_ai_db, "broken-row", _foreign_ciphertext())
    # 同时把它设为默认配置，覆盖 get_default_config() 的解密路径
    conn = sqlite3.connect(temp_ai_db)
    conn.execute("UPDATE api_configs SET is_default = 1 WHERE id = 'broken-row'")
    conn.commit()
    conn.close()
    manager = ConfigManager()

    entity = manager.get_config_by_id("broken-row")
    default = manager.get_default_config()

    assert entity is not None
    assert entity.api_key == ""
    assert default is not None
    assert default.id == "broken-row"
    assert default.api_key == ""


def test_解不开密钥的行在桥接层标记为未配置(temp_ai_db):
    controller = make_controller()
    controller.ai_create_config(
        {"alias": "可用配置", "provider": "openai", "api_key": SECRET, "model": "gpt-4"}
    )
    insert_raw_key(temp_ai_db, "broken-row", _foreign_ciphertext(), alias="密钥丢失的配置")

    result = controller.ai_list_configs()

    assert result["success"] is True
    assert len(result["configs"]) == 2
    broken = next(c for c in result["configs"] if c["id"] == "broken-row")
    assert broken["has_api_key"] is False
    assert broken["api_key_masked"] == ""
    detail = controller.ai_get_config_detail("broken-row")
    assert detail["config"]["has_api_key"] is False
    assert SECRET not in str(result) + str(detail)
