"""
AI 服务商密钥的本机存储与加解密

历史问题：API Key 曾使用写在源码里的固定 Fernet 密钥加密
（`_ENCRYPTION_KEY = b'ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg='`）。
该常量已进入版本历史，任何拿到仓库的人都等于拿到密钥，"加密"只剩编码作用。

本模块改为**每台安装独立生成、保存在运行数据目录**的密钥：

- 密钥位置：``get_data_dir()/secrets/ai_fernet.key``（即开发环境的 ``source-code/data/secrets/``、
  打包环境的 ``<exe 同级>/data/secrets/``）
- 首次使用时 ``Fernet.generate_key()`` 生成，**原子写入**（临时文件 + ``os.replace``），
  权限尽力收敛到当前用户（Windows 用 ``icacls`` 断开继承并只授权当前用户，POSIX 用 ``0o600``）
- 解密顺序：本机密钥 → 历史共享密钥（仅用于迁移）。用历史密钥能解开时返回
  ``reencrypt_required=True``，由 ``ConfigManager`` 用新密钥重新落库；迁移是幂等的
- 对外只应暴露掩码：``mask_api_key()``

注意：历史共享密钥保留在此处**只是为了让用户已有配置不丢**，它不提供任何保密性。
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Optional, Tuple

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

#: 加密值在数据库中携带的前缀，用于区分"已加密"与"历史明文"
ENCRYPTED_PREFIX = "encrypted:"

#: **仅供迁移使用**的历史硬编码密钥。它在 git 历史中是公开的，不具备保密性；
#: 迁移完成后可以连同 `LEGACY_TOKEN_TTL` 一起删除。
LEGACY_KEY = b"ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg="

_KEY_FILENAME = "ai_fernet.key"
_lock = threading.RLock()
_cipher_cache: Optional[Fernet] = None
_key_path_override: Optional[Path] = None


class SecretKeyError(RuntimeError):
    """密钥不可用/不可读写时抛出"""


def set_key_path_for_testing(path: Optional[Path]) -> None:
    """测试用：覆盖密钥文件路径；传 None 恢复默认。同时清空缓存的 cipher。"""
    global _key_path_override, _cipher_cache
    with _lock:
        _key_path_override = path
        _cipher_cache = None


def get_key_path() -> Path:
    """返回本机 Fernet 密钥文件路径（不创建文件）。"""
    if _key_path_override is not None:
        return _key_path_override
    from backend.src.utils.paths import get_data_dir

    return get_data_dir("secrets") / _KEY_FILENAME


def _restrict_permissions(path: Path) -> None:
    """尽力把文件权限收敛到当前用户；失败只告警，不影响功能。"""
    # POSIX：直接 0600
    if os.name == "posix":
        try:
            os.chmod(path, 0o600)
            return
        except OSError as exc:  # pragma: no cover - 依赖平台
            logger.warning("[密钥] chmod 0600 失败: %s", exc)
            return

    if os.name != "nt":  # pragma: no cover
        return

    user = os.environ.get("USERNAME") or os.environ.get("USER")
    if not user:
        logger.warning("[密钥] 无法确定当前用户名，跳过 ACL 设置")
        return
    domain = os.environ.get("USERDOMAIN")
    principal = f"{domain}\\{user}" if domain and domain.upper() != user.upper() else user

    # /inheritance:r 断开继承，/grant:r 只保留显式授权
    cmd = [
        "icacls",
        str(path),
        "/inheritance:r",
        "/grant:r",
        f"{principal}:F",
    ]
    try:
        result = subprocess.run(  # noqa: S603 - 固定参数，无 shell
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if result.returncode != 0:
            logger.warning(
                "[密钥] icacls 设置失败（退出码 %s）: %s",
                result.returncode,
                (result.stderr or result.stdout or "").strip()[:200],
            )
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover
        logger.warning("[密钥] 调用 icacls 出错，跳过 ACL: %s", exc)


def _read_key(path: Path) -> Optional[bytes]:
    try:
        raw = path.read_bytes().strip()
    except FileNotFoundError:
        return None
    if not raw:
        logger.error("[密钥] 密钥文件为空: %s", path)
        raise SecretKeyError(f"密钥文件损坏（空文件）: {path}")
    try:
        # Fernet 密钥是 urlsafe base64（含 - 和 _），直接交给 Fernet 校验格式最可靠
        Fernet(raw)
    except (ValueError, TypeError) as exc:
        logger.error("[密钥] 密钥文件不是合法 Fernet key: %s", exc)
        raise SecretKeyError(f"密钥文件损坏: {path}") from exc
    return raw


def _write_key_atomic(path: Path, key: bytes) -> bool:
    """原子创建密钥文件。返回 True 表示本次真正写入；False 表示已存在（竞争下的另一方胜出）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".ai_fernet.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(key)
            fh.flush()
            os.fsync(fh.fileno())
        _restrict_permissions(tmp_path)
        try:
            # os.replace 在 Windows/POSIX 上都是原子覆盖；先确认目标不存在以免覆盖用户密钥
            if path.exists():
                return False
            os.replace(tmp_path, path)
        except FileNotFoundError:
            return False
        _restrict_permissions(path)
        return True
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:  # pragma: no cover
                pass


def load_or_create_key() -> bytes:
    """读取本机密钥；不存在则生成并原子写入。"""
    path = get_key_path()
    with _lock:
        existing = _read_key(path)
        if existing is not None:
            return existing

        key = Fernet.generate_key()
        if _write_key_atomic(path, key):
            logger.info("[密钥] 已生成本机专用 AI 密钥: %s", path)
            return key

        # 并发创建：另一个进程/线程先写入了，使用它的密钥
        raced = _read_key(path)
        if raced is None:  # pragma: no cover - 极端情况
            raise SecretKeyError(f"密钥文件写入后仍不可读: {path}")
        logger.info("[密钥] 检测到并发创建的密钥，复用已有文件")
        return raced


def get_cipher() -> Fernet:
    """返回缓存的本机密钥 cipher。"""
    global _cipher_cache
    with _lock:
        if _cipher_cache is None:
            _cipher_cache = Fernet(load_or_create_key())
        return _cipher_cache


def reset_cipher_cache() -> None:
    global _cipher_cache
    with _lock:
        _cipher_cache = None


def encrypt_secret(plaintext: str) -> str:
    """加密为带 ``encrypted:`` 前缀的字符串；空串原样返回空串。"""
    if not plaintext:
        return ""
    token = get_cipher().encrypt(plaintext.encode("utf-8"))
    return f"{ENCRYPTED_PREFIX}{token.decode('utf-8')}"


def decrypt_secret(stored: str) -> Tuple[str, bool]:
    """
    解密存储值。

    Returns:
        (plaintext, reencrypt_required)
        - 本机密钥可解 → (明文, False)
        - 历史共享密钥可解 → (明文, True)  # 需要重新加密落库
        - 无 ``encrypted:`` 前缀的历史明文 → (原值, True)  # 需要加密落库
        - 空值 → ("", False)

    Raises:
        SecretKeyError: 两种密钥都解不开（密钥文件被换掉/数据损坏）
    """
    if not stored:
        return "", False
    if not stored.startswith(ENCRYPTED_PREFIX):
        return stored, True

    payload = stored[len(ENCRYPTED_PREFIX):].encode("utf-8")
    try:
        return get_cipher().decrypt(payload).decode("utf-8"), False
    except InvalidToken:
        pass
    except SecretKeyError:
        raise

    try:
        plaintext = Fernet(LEGACY_KEY).decrypt(payload).decode("utf-8")
    except InvalidToken as exc:
        raise SecretKeyError(
            "无法用本机密钥或历史密钥解密该 API Key；"
            "如果 data/secrets/ai_fernet.key 被替换过，需要在 AI 设置中重新填写密钥"
        ) from exc
    logger.info("[密钥] 该 API Key 仍由历史共享密钥加密，将用本机密钥重新写入")
    return plaintext, True


def mask_api_key(api_key: str) -> str:
    """生成可安全回传给前端的掩码：保留前 3 后 4，中间固定 6 个星号。"""
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return f"{api_key[:3]}{'*' * 6}{api_key[-4:]}"


def is_masked_value(value: str, original: str) -> bool:
    """判断前端回传的值是否只是掩码（即"用户没有改动 API Key"）。"""
    if not value:
        return False
    if "*" not in value:
        return False
    if original and value == mask_api_key(original):
        return True
    # 兜底：任何"含连续 3 个以上星号"的字符串都不是真实 API Key 的合法形态
    return bool(_MASK_SHAPE.fullmatch(value))


_MASK_SHAPE = re.compile(r"[^*\s]{0,8}\*{3,}[^*\s]{0,8}")
