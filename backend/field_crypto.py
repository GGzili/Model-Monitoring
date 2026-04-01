"""
敏感文本字段的静态加密（Fernet）。未设置 MONITOR_FERNET_KEY 时以明文写入（启动会打警告）。
密钥生成：python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError as e:  # pragma: no cover
    raise ImportError("需要 cryptography 包（已随 paramiko 引入）") from e

_PREFIX = "ENCv1:"
_fernet: Optional[Fernet] = None


def init_field_crypto() -> None:
    global _fernet
    _fernet = None
    key = os.environ.get("MONITOR_FERNET_KEY", "").strip()
    if not key:
        log.warning(
            "MONITOR_FERNET_KEY 未设置：模型连接信息、SSH 等将以明文写入 SQLite。"
            "生产环境请设置 Fernet 密钥。"
        )
        return
    try:
        _fernet = Fernet(key.encode("ascii"))
    except Exception as e:
        raise RuntimeError(f"MONITOR_FERNET_KEY 无效（须为 Fernet.generate_key() 输出）: {e}") from e


def encryption_enabled() -> bool:
    return _fernet is not None


def encrypt_field(val: Any) -> str:
    if val is None:
        return ""
    s = str(val)
    if not s:
        return ""
    if s.startswith(_PREFIX):
        return s
    if _fernet is None:
        return s
    return _PREFIX + _fernet.encrypt(s.encode("utf-8")).decode("ascii")


def decrypt_field(val: Any) -> str:
    if val is None:
        return ""
    s = str(val)
    if not s.startswith(_PREFIX):
        return s
    if _fernet is None:
        raise RuntimeError(
            "数据库中存在加密字段，但未设置 MONITOR_FERNET_KEY，无法解密。请配置与加密时相同的密钥。"
        )
    try:
        return _fernet.decrypt(s[len(_PREFIX) :].encode("ascii")).decode("utf-8")
    except InvalidToken as e:
        raise RuntimeError("解密失败：密钥与写入时不一致或数据已损坏") from e


ENCRYPTED_TEXT_FIELDS = frozenset(
    {
        "name",
        "model_api_name",
        "host",
        "host_b",
        "container",
        "container_b",
        "exec_cmd",
        "exec_cmd_b",
        "ssh_user",
        "ssh_password",
    }
)


def encrypt_row(d: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(d)
    for k in ENCRYPTED_TEXT_FIELDS:
        if k in out:
            out[k] = encrypt_field(out[k])
    return out


def decrypt_row(d: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(d)
    for k in ENCRYPTED_TEXT_FIELDS:
        if k in out:
            out[k] = decrypt_field(out[k])
    return out
