"""
画质压缩服务 - 基于 Pillow 的二分查找最佳质量值压缩

策略:
- 目标文件大小默认 500KB
- 质量范围 60-95
- 二分查找最佳质量值，画质优先
"""
import io
import logging
from pathlib import Path
from PIL import Image

logger = logging.getLogger(__name__)


def compress_image(
    input_path: str,
    output_path: str,
    target_size_kb: int = 500,
    min_quality: int = 60,
    max_quality: int = 95,
) -> bool:
    """
    压缩单张图片到目标大小以内（画质优先二分查找）

    Returns:
        是否成功
    """
    try:
        src = Path(input_path)
        if not src.exists():
            logger.error(f"压缩源文件不存在: {input_path}")
            return False

        # 如果原图已经小于目标大小，直接复制
        if src.stat().st_size <= target_size_kb * 1024:
            import shutil
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(input_path, output_path)
            logger.info(f"原图已满足大小要求，直接复制: {input_path}")
            return True

        img = Image.open(input_path)
        # 转为 RGB（处理 RGBA / P 模式）
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        target_bytes = target_size_kb * 1024
        lo, hi = min_quality, max_quality
        best_quality = lo
        best_buf = None

        # 二分查找最佳质量值
        while lo <= hi:
            mid = (lo + hi) // 2
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=mid, optimize=True)
            size = buf.tell()

            if size <= target_bytes:
                best_quality = mid
                best_buf = buf
                lo = mid + 1  # 尝试更高画质
            else:
                hi = mid - 1  # 降低画质

        if best_buf is None:
            # 即使最低质量也超标，用最低质量保存
            best_buf = io.BytesIO()
            img.save(best_buf, format="JPEG", quality=min_quality, optimize=True)
            best_quality = min_quality
            logger.warning(
                f"压缩后仍超过目标大小: {input_path} "
                f"(quality={min_quality}, size={best_buf.tell() // 1024}KB)"
            )

        # 写入文件
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(best_buf.getvalue())

        final_kb = Path(output_path).stat().st_size // 1024
        logger.info(f"压缩完成: {input_path} → {final_kb}KB (quality={best_quality})")
        return True

    except Exception as e:
        logger.error(f"压缩失败 {input_path}: {e}")
        return False
