"""
系统设置读取工具
统一处理 DB 配置读取 + 敏感字段自动解密。
"""
from sqlalchemy.orm import Session

from app.core.encryption import decrypt_value, is_api_key_field
from app.models.database import Settings


def _is_sensitive_setting_key(key: str) -> bool:
    """判断配置项是否属于需要解密的敏感字段。"""
    k = (key or "").lower()
    return (
        is_api_key_field(key)
        or "access_key" in k
        or "secret_key" in k
        or k.endswith("_token")
    )


def get_setting_value(db: Session, key: str, default: str = "") -> str:
    """
    从数据库读取配置值。
    - 不存在时返回 default
    - 敏感字段自动尝试解密（兼容旧明文值）
    """
    row = db.query(Settings).filter(Settings.key == key).first()
    if not row or not row.value:
        return default

    value = row.value
    if _is_sensitive_setting_key(key):
        value = decrypt_value(value)
    return value

