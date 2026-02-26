"""
图片扩图服务测试（降级路径 + 偏移量）
"""
from pathlib import Path

import cv2
import numpy as np

from app.services.image_expander import _fallback_expand


def _build_test_image() -> np.ndarray:
    """构造一张顶部/底部颜色不同的测试图，便于验证 padding 方向。"""
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[:, :] = (0, 0, 0)
    img[0, :] = (255, 0, 0)      # 顶部：蓝色(BGR)
    img[-1, :] = (0, 0, 255)     # 底部：红色
    return img


def _read(path: Path) -> np.ndarray:
    result = cv2.imread(str(path))
    assert result is not None
    return result


def test_fallback_expand_center_offset(tmp_path):
    img = _build_test_image()
    out = tmp_path / "center.png"

    ok = _fallback_expand(
        image=img,
        output_path=str(out),
        target_width=100,
        target_height=200,
        offset=0.0,
    )
    assert ok is True
    result = _read(out)
    assert result.shape[:2] == (200, 100)

    # 居中扩展：上下各 50 像素，最顶/最底分别复制原图边缘
    assert tuple(result[0, 0]) == (255, 0, 0)
    assert tuple(result[-1, 0]) == (0, 0, 255)


def test_fallback_expand_positive_offset_moves_image_down(tmp_path):
    img = _build_test_image()
    out = tmp_path / "offset_plus.png"

    ok = _fallback_expand(
        image=img,
        output_path=str(out),
        target_width=100,
        target_height=200,
        offset=1.0,
    )
    assert ok is True
    result = _read(out)
    assert result.shape[:2] == (200, 100)

    # offset=1: 上方扩展最大（100 像素），底部不扩展
    # 因此第 100 行应是原图第一行（蓝色），最后一行是原图最后一行（红色）
    assert tuple(result[99, 0]) == (255, 0, 0)
    assert tuple(result[-1, 0]) == (0, 0, 255)
