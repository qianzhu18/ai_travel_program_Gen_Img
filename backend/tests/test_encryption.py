"""
Tests for app.core.encryption
"""
import pytest
from unittest.mock import patch
from pathlib import Path


class TestEncryption:
    """加密模块测试 — 动态导入以避免模块级副作用"""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, monkeypatch):
        """每个测试使用独立的临时密钥文件"""
        import importlib
        import sys

        self.key_path = tmp_path / ".secret_key"

        # Remove cached module so it re-initializes with patched path
        for mod_name in list(sys.modules):
            if "encryption" in mod_name:
                del sys.modules[mod_name]

        # Patch the module-level constant before import
        import app.core.encryption as enc_module
        monkeypatch.setattr(enc_module, "SECRET_KEY_PATH", self.key_path)
        # Re-create fernet with new key
        from cryptography.fernet import Fernet
        key = Fernet.generate_key()
        self.key_path.write_bytes(key)
        enc_module._fernet = Fernet(key)
        self.enc = enc_module

    def test_encrypt_decrypt_roundtrip(self):
        """加密后解密应还原明文"""
        plain = "sk-abc123xyz"
        cipher = self.enc.encrypt_value(plain)
        assert cipher != plain
        assert self.enc.decrypt_value(cipher) == plain

    def test_encrypt_empty_string(self):
        """空字符串加密返回空"""
        assert self.enc.encrypt_value("") == ""
        assert self.enc.decrypt_value("") == ""

    def test_decrypt_invalid_returns_original(self):
        """解密失败时返回原文（兼容旧数据）"""
        raw = "not-encrypted-text"
        assert self.enc.decrypt_value(raw) == raw

    def test_mask_value_normal(self):
        """掩码保留最后4位"""
        assert self.enc.mask_value("sk-abcdefgh1234") == "****1234"

    def test_mask_value_short(self):
        """短字符串掩码为 ****"""
        assert self.enc.mask_value("ab") == "****"
        assert self.enc.mask_value("") == "****"

    def test_is_api_key_field(self):
        """API Key 字段识别"""
        assert self.enc.is_api_key_field("prompt_api_key") is True
        assert self.enc.is_api_key_field("apiyi_API_KEY") is True
        assert self.enc.is_api_key_field("compress_target_size") is False
