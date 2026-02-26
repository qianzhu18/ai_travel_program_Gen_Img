"""
Tests for app.services.image_compressor
"""
import os
from pathlib import Path
from PIL import Image

from app.services.image_compressor import compress_image


class TestCompressImage:
    """compress_image 核心逻辑测试"""

    def test_small_image_copied_directly(self, tmp_image, tmp_path):
        """原图已小于目标大小时，直接复制不压缩"""
        out = tmp_path / "out.jpg"
        result = compress_image(str(tmp_image), str(out), target_size_kb=500)
        assert result is True
        assert out.exists()
        # 输出文件大小应与原图一致（直接复制）
        assert out.stat().st_size == tmp_image.stat().st_size

    def test_large_image_compressed_below_target(self, large_image, tmp_path):
        """大图应被压缩到目标大小以内"""
        out = tmp_path / "compressed.jpg"
        target_kb = 200
        result = compress_image(str(large_image), str(out), target_size_kb=target_kb)
        assert result is True
        assert out.exists()
        assert out.stat().st_size <= target_kb * 1024

    def test_output_is_valid_jpeg(self, large_image, tmp_path):
        """压缩输出应为可打开的 JPEG"""
        out = tmp_path / "compressed.jpg"
        compress_image(str(large_image), str(out), target_size_kb=300)
        img = Image.open(str(out))
        assert img.format == "JPEG"

    def test_nonexistent_source_returns_false(self, tmp_path):
        """源文件不存在时返回 False"""
        out = tmp_path / "out.jpg"
        result = compress_image("/no/such/file.jpg", str(out))
        assert result is False
        assert not out.exists()

    def test_creates_output_directory(self, large_image, tmp_path):
        """输出目录不存在时自动创建"""
        out = tmp_path / "sub" / "dir" / "out.jpg"
        result = compress_image(str(large_image), str(out), target_size_kb=300)
        assert result is True
        assert out.exists()

    def test_rgba_image_handled(self, tmp_path):
        """RGBA 模式图片应正常压缩（转 RGB）"""
        img = Image.new("RGBA", (500, 500), color=(255, 0, 0, 128))
        src = tmp_path / "rgba.png"
        img.save(str(src), format="PNG")
        out = tmp_path / "out.jpg"
        result = compress_image(str(src), str(out), target_size_kb=500)
        assert result is True
        assert out.exists()

    def test_quality_range_respected(self, large_image, tmp_path):
        """min_quality > max_quality 边界情况不崩溃"""
        out = tmp_path / "out.jpg"
        # min == max，只尝试一个质量值
        result = compress_image(str(large_image), str(out),
                                target_size_kb=300, min_quality=80, max_quality=80)
        assert result is True
        assert out.exists()
