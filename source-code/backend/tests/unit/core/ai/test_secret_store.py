"""本机 AI 密钥存储（secret_store）单元测试

覆盖：
- 每台安装生成互不相同的本机密钥，并以原子方式落盘
- 已存在的密钥文件不会被覆盖（含并发创建路径）
- 解密顺序：本机密钥 → 历史共享密钥（需重加密）→ 历史明文（需加密）
- 两种密钥都解不开时抛出 SecretKeyError
- 掩码格式与"掩码值识别"（前端回传掩码时不得覆盖已保存密钥）
- 权限收敛为尽力而为：不支持时只告警，不影响可用性
"""

import base64
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

_BACKEND_DIR = Path(__file__).resolve().parents[4]
_SOURCE_ROOT = _BACKEND_DIR.parent
for _p in (str(_BACKEND_DIR), str(_SOURCE_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.src.core.ai import secret_store  # noqa: E402
from backend.src.core.ai.secret_store import SecretKeyError  # noqa: E402


@pytest.fixture
def isolated_key(tmp_path):
    """把密钥文件指向临时目录，测试结束后恢复默认路径。"""
    key_path = tmp_path / "ai_fernet.key"
    secret_store.set_key_path_for_testing(key_path)
    try:
        yield key_path
    finally:
        secret_store.set_key_path_for_testing(None)
        secret_store.reset_cipher_cache()


def test_首次使用生成本机密钥并落盘(isolated_key):
    key = secret_store.load_or_create_key()

    assert isolated_key.exists()
    assert isolated_key.read_bytes().strip() == key
    # 生成的是合法 Fernet 密钥（urlsafe base64，解码后 32 字节）
    Fernet(key)
    assert len(base64.urlsafe_b64decode(key)) == 32


def test_不同安装目录生成的密钥互不相同(tmp_path):
    keys = []
    for name in ("install_a", "install_b"):
        key_path = tmp_path / name / "ai_fernet.key"
        secret_store.set_key_path_for_testing(key_path)
        try:
            keys.append(secret_store.load_or_create_key())
        finally:
            secret_store.set_key_path_for_testing(None)
            secret_store.reset_cipher_cache()

    assert keys[0] != keys[1]


def test_已有密钥文件不会被覆盖(isolated_key):
    original = Fernet.generate_key()
    isolated_key.write_bytes(original)

    assert secret_store.load_or_create_key() == original
    assert isolated_key.read_bytes() == original


def test_原子写入不残留临时文件(isolated_key):
    secret_store.load_or_create_key()

    leftovers = [p.name for p in isolated_key.parent.iterdir() if p != isolated_key]
    assert leftovers == []


def test_并发创建时复用先落盘的密钥(isolated_key, monkeypatch):
    """写入前发现目标已存在时，放弃自己的密钥改用磁盘上的密钥。"""
    raced = Fernet.generate_key()
    isolated_key.write_bytes(raced)

    real_read = secret_store._read_key
    state = {"first": True}

    def flaky_read(path):
        # 第一次"读"模拟并发窗口：文件看起来还不存在
        if state["first"]:
            state["first"] = False
            return None
        return real_read(path)

    monkeypatch.setattr(secret_store, "_read_key", flaky_read)

    assert secret_store.load_or_create_key() == raced
    assert isolated_key.read_bytes() == raced


def test_空密钥文件报错(isolated_key):
    isolated_key.write_bytes(b"")

    with pytest.raises(SecretKeyError):
        secret_store.load_or_create_key()


def test_损坏密钥文件报错(isolated_key):
    isolated_key.write_text("这不是 base64 编码的密钥\n", encoding="utf-8")

    with pytest.raises(SecretKeyError):
        secret_store.load_or_create_key()


def test_加解密带前缀往返(isolated_key):
    token = secret_store.encrypt_secret("sk-secret-value")

    assert token.startswith(secret_store.ENCRYPTED_PREFIX)
    assert secret_store.decrypt_secret(token) == ("sk-secret-value", False)


def test_空串不加密(isolated_key):
    assert secret_store.encrypt_secret("") == ""
    assert secret_store.decrypt_secret("") == ("", False)


def test_历史共享密钥密文可解密并要求重加密(isolated_key):
    legacy_token = Fernet(secret_store.LEGACY_KEY).encrypt(b"sk-old-style")
    stored = f"{secret_store.ENCRYPTED_PREFIX}{legacy_token.decode()}"

    plaintext, needs_rewrite = secret_store.decrypt_secret(stored)
    assert plaintext == "sk-old-style"
    assert needs_rewrite is True

    # 用本机密钥重写后不再要求重加密（迁移幂等）
    migrated = secret_store.encrypt_secret(plaintext)
    assert secret_store.decrypt_secret(migrated) == ("sk-old-style", False)


def test_历史明文值视为需要加密落库(isolated_key):
    assert secret_store.decrypt_secret("sk-plain-old") == ("sk-plain-old", True)


def test_两种密钥都解不开时报错(isolated_key):
    broken = f"{secret_store.ENCRYPTED_PREFIX}{Fernet.generate_key().decode()}"

    with pytest.raises(SecretKeyError):
        secret_store.decrypt_secret(broken)


def test_换密钥后旧数据解密失败并给出可操作提示(isolated_key):
    before = secret_store.encrypt_secret("sk-before-key-swap")

    secret_store.set_key_path_for_testing(isolated_key.parent / "other" / "ai_fernet.key")
    try:
        with pytest.raises(SecretKeyError) as exc_info:
            secret_store.decrypt_secret(before)
        assert "ai_fernet.key" in str(exc_info.value)
    finally:
        secret_store.set_key_path_for_testing(isolated_key)


def test_掩码只保留首尾字符():
    long_key = "sk-1234567890abcdefghijklmn"
    masked = secret_store.mask_api_key(long_key)

    assert masked == "sk-******klmn"
    assert long_key not in masked
    assert masked.count("*") == 6


def test_短密钥与空密钥的掩码():
    assert secret_store.mask_api_key("") == ""
    # 8 位及以内全掩码；超过 8 位保留前 3 后 4
    assert secret_store.mask_api_key("sk-123") == "*" * len("sk-123")
    assert secret_store.mask_api_key("abcdefgh") == "*" * 8
    assert secret_store.mask_api_key("abcdefghi") == "abc******fghi"


def test_识别前端回传的掩码值():
    key = "sk-1234567890abcdefghijklmn"

    assert secret_store.is_masked_value(secret_store.mask_api_key(key), key) is True
    # 用户确实改动过密钥时不能误判为掩码
    assert secret_store.is_masked_value("sk-brand-new-key", key) is False
    # 空值交由"留空表示不修改"分支处理
    assert secret_store.is_masked_value("", key) is False
    # 形如掩码但没有对应原值时同样视为掩码
    assert secret_store.is_masked_value("sk-******zzzz", "") is True


@pytest.mark.skipif(os.name != "nt", reason="Windows ACL 专项用例")
def test_windows_acl尽力收敛到当前用户(isolated_key):
    secret_store.load_or_create_key()

    if shutil.which("icacls") is None:
        pytest.skip("环境缺少 icacls")

    result = subprocess.run(
        ["icacls", str(isolated_key)],
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stdout or "").lower()
    user = (os.environ.get("USERNAME") or os.environ.get("USER") or "").lower()

    assert result.returncode == 0
    # 授权主体里不应再出现 Everyone / 已验证用户（继承被断开）
    assert "everyone" not in output
    assert "authenticated users" not in output
    if user:
        assert user in output
