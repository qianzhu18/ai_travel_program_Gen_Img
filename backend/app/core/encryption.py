"""
API Key 加密存储工具
使用 Fernet 对称加密
"""
from cryptography.fernet import Fernet
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# 密钥文件路径
BASE_DIR = Path(__file__).resolve().parent.parent.parent
SECRET_KEY_PATH = BASE_DIR / "data" / ".secret_key"


def _get_or_create_key() -> bytes:
    """获取或生成加密密钥"""
    SECRET_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SECRET_KEY_PATH.exists():
        return SECRET_KEY_PATH.read_bytes().strip()
    key = Fernet.generate_key()
    SECRET_KEY_PATH.write_bytes(key)
    logger.info("已生成新的加密密钥")
    return key


_fernet = Fernet(_get_or_create_key())


def encrypt_value(plaintext: str) -> str:
    """加密明文，返回密文字符串"""
    if not plaintext:
        return ""
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """解密密文，返回明文字符串"""
    if not ciphertext:
        return ""
    try:
        return _fernet.decrypt(ciphertext.encode()).decode()
    except Exception:
        # 如果解密失败（可能是未加密的旧数据），原样返回
        return ciphertext


def mask_value(plaintext: str) -> str:
    """将明文掩码显示，仅保留最后4位"""
    if not plaintext or len(plaintext) <= 4:
        return "****"
    return "****" + plaintext[-4:]


def is_api_key_field(key: str) -> bool:
    """判断配置项是否为 API Key 类字段"""
    key_lower = key.lower()
    return (
        "api_key" in key_lower
        or "access_key_id" in key_lower
        or "secret_access_key" in key_lower
        or "secret_key" in key_lower
    )
