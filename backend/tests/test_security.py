"""
安全模块测试：sanitize_filename / safe_resolve / validate_export_dir / validate_url
"""
import pytest
from pathlib import Path

from app.core.security import (
    sanitize_filename,
    safe_resolve,
    validate_export_dir,
    validate_url,
)


# ── sanitize_filename ──────────────────────────────────────────

class TestSanitizeFilename:
    def test_normal_name(self):
        assert sanitize_filename("photo.jpg") == "photo.jpg"

    def test_chinese_name(self):
        assert sanitize_filename("人群_广场.png") == "人群_广场.png"

    def test_strips_path_separators(self):
        result = sanitize_filename("../../etc/passwd")
        assert "/" not in result
        assert ".." not in result

    def test_backslash_path(self):
        result = sanitize_filename("C:\\Users\\hack\\evil.exe")
        assert "\\" not in result
        assert "evil.exe" in result

    def test_special_chars_replaced(self):
        result = sanitize_filename("file<>:\"|?*.jpg")
        # 特殊字符应被替换为下划线
        assert "<" not in result
        assert ">" not in result
        assert "|" not in result

    def test_empty_returns_unnamed(self):
        assert sanitize_filename("") == "unnamed"

    def test_only_dots(self):
        # "..." 经过 Path.name 和替换后应返回合理结果
        result = sanitize_filename("...")
        assert result  # 不为空

    def test_long_name_truncated(self):
        long_name = "a" * 300 + ".jpg"
        result = sanitize_filename(long_name)
        assert len(result) <= 200

    def test_consecutive_underscores_collapsed(self):
        result = sanitize_filename("a!!!b@@@c.jpg")
        assert "__" not in result


# ── safe_resolve ───────────────────────────────────────────────

class TestSafeResolve:
    def test_valid_subpath(self, tmp_path):
        child = tmp_path / "sub" / "file.txt"
        child.parent.mkdir(parents=True, exist_ok=True)
        child.touch()
        result = safe_resolve(str(child), tmp_path)
        assert result == child.resolve()

    def test_traversal_blocked(self, tmp_path):
        evil = str(tmp_path / ".." / ".." / "etc" / "passwd")
        with pytest.raises(ValueError, match="不在允许范围"):
            safe_resolve(evil, tmp_path)

    def test_exact_root_allowed(self, tmp_path):
        result = safe_resolve(str(tmp_path), tmp_path)
        assert result == tmp_path.resolve()


# ── validate_export_dir ────────────────────────────────────────

class TestValidateExportDir:
    def test_normal_path(self, tmp_path):
        p = str(tmp_path / "output")
        result = validate_export_dir(p)
        assert isinstance(result, Path)

    def test_dotdot_rejected(self):
        with pytest.raises(ValueError, match="不允许包含"):
            validate_export_dir("/tmp/../etc")

    @pytest.mark.skipif(
        not Path("/etc").exists(),
        reason="系统目录检测仅在 Linux/macOS 上有效",
    )
    def test_system_dir_blocked(self):
        for d in ("/etc/exports", "/usr/local", "/bin/sh"):
            with pytest.raises(ValueError, match="不允许导出到系统目录"):
                validate_export_dir(d)


# ── validate_url ───────────────────────────────────────────────

class TestValidateUrl:
    def test_valid_https(self):
        assert validate_url("https://example.com/img.jpg") == "https://example.com/img.jpg"

    def test_valid_http(self):
        assert validate_url("http://cdn.example.com/a.png") == "http://cdn.example.com/a.png"

    def test_ftp_rejected(self):
        with pytest.raises(ValueError, match="不支持的协议"):
            validate_url("ftp://evil.com/file")

    def test_file_scheme_rejected(self):
        with pytest.raises(ValueError, match="不支持的协议"):
            validate_url("file:///etc/passwd")

    def test_localhost_rejected(self):
        with pytest.raises(ValueError, match="不允许访问本地地址"):
            validate_url("http://localhost:8080/admin")

    def test_zero_ip_rejected(self):
        with pytest.raises(ValueError, match="不允许访问本地地址"):
            validate_url("http://0.0.0.0/secret")

    def test_private_10_rejected(self):
        with pytest.raises(ValueError, match="不允许访问内网地址"):
            validate_url("http://10.0.0.1/internal")

    def test_private_172_rejected(self):
        with pytest.raises(ValueError, match="不允许访问内网地址"):
            validate_url("http://172.16.0.1/api")

    def test_private_192_rejected(self):
        with pytest.raises(ValueError, match="不允许访问内网地址"):
            validate_url("http://192.168.1.1/admin")

    def test_loopback_127_rejected(self):
        with pytest.raises(ValueError, match="不允许访问内网地址"):
            validate_url("http://127.0.0.1:3000/")

    def test_link_local_rejected(self):
        with pytest.raises(ValueError, match="不允许访问内网地址"):
            validate_url("http://169.254.169.254/latest/meta-data/")

    def test_no_hostname_rejected(self):
        with pytest.raises(ValueError, match="缺少主机名"):
            validate_url("http://")

    def test_public_domain_allowed(self):
        url = "https://images.unsplash.com/photo-123.jpg"
        assert validate_url(url) == url
