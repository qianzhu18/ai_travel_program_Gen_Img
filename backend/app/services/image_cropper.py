"""
图片裁剪服务 — 仅依赖 Pillow，无 OpenCV 依赖
用于 9:16 等目标比例的裁剪
"""
import logging
from pathlib import Path
from PIL import Image

logger = logging.getLogger(__name__)


def crop_to_target_ratio(
    input_path: str,
    output_path: str,
    target_ratio: tuple = (9, 16),
    offset: float = 0.0,
) -> bool:
    """
    将图片裁剪为目标比例（默认 9:16）

    Args:
        input_path: 输入图片路径
        output_path: 输出图片路径
        target_ratio: 目标宽高比 (w, h)
        offset: 裁剪偏移量 [-1.0, 1.0]，0 为居中
    Returns:
        bool: 是否成功
    """
    try:
        image = Image.open(input_path)
        w, h = image.size
        target_w, target_h = target_ratio
        target_ratio_val = target_w / target_h
        current_ratio = w / h

        # 比例已接近目标，跳过裁剪
        tolerance = 0.05 * target_ratio_val
        if abs(current_ratio - target_ratio_val) < tolerance:
            logger.info(f"图片比例已接近 {target_w}:{target_h}, 跳过裁剪")
            if str(Path(input_path).resolve()) != str(Path(output_path).resolve()):
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                image.save(output_path)
            return True

        if current_ratio > target_ratio_val:
            # 图片偏宽，裁左右
            new_w = int(h * target_ratio_val)
            max_offset = (w - new_w) // 2
            cx = w // 2 + int(offset * max_offset)
            x1 = max(0, cx - new_w // 2)
            x1 = min(x1, w - new_w)
            box = (x1, 0, x1 + new_w, h)
        else:
            # 图片偏高，裁上下
            new_h = int(w / target_ratio_val)
            max_offset = (h - new_h) // 2
            cy = h // 2 + int(offset * max_offset)
            y1 = max(0, cy - new_h // 2)
            y1 = min(y1, h - new_h)
            box = (0, y1, w, y1 + new_h)

        cropped = image.crop(box)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        cropped.save(output_path)
        logger.info(
            f"裁剪成功: {w}x{h} -> {box[2]-box[0]}x{box[3]-box[1]} (offset={offset:.2f})"
        )
        return True
    except Exception as e:
        logger.error(f"裁剪失败: {input_path}, 错误: {e}")
        return False
