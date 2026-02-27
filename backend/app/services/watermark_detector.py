"""
水印检测服务 - 基于 OpenCV 边界检测
支持三种检测模式：智能检测(auto)、固定区域(fixed_region)、全图扫描(full_scan)
以及手动框选(manual)
"""
import cv2
import numpy as np
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class WatermarkDetector:
    """
    OpenCV 水印检测器

    检测模式:
    - "auto"         : OpenCV 边缘+轮廓分析，在候选区域内精确定位水印边界
    - "fixed_region" : 固定矩形区域蒙版（兼容旧逻辑）
    - "full_scan"    : 全图扫描（对应设置中的"全图检测"）
    - "manual"       : 用户手动框选
    """

    def __init__(self, sensitivity: float = 0.5):
        """
        Args:
            sensitivity: 检测灵敏度 0.0(保守) ~ 1.0(积极)
                         越高越容易检测到水印，但也可能误检
        """
        self.sensitivity = max(0.0, min(1.0, sensitivity))

    def detect(
        self,
        image: np.ndarray,
        mode: str = "auto",
        region: str = "bottom_right",
        margin_ratio: float = 0.15,
        manual_bbox: Optional[Tuple[int, int, int, int]] = None,
        fallback_to_fixed: bool = True,
    ) -> np.ndarray:
        """
        主入口：根据模式返回二值 mask (255=水印区域, 0=保留区域)

        Args:
            image: BGR 格式图片
            mode: 检测模式 auto/fixed_region/full_scan/manual
            region: 水印预期位置 bottom_right/bottom_left/top_right/top_left
            margin_ratio: 候选区域占图片比例
            manual_bbox: 手动框选坐标 (x1, y1, x2, y2)

        Returns:
            mask: 与 image 同宽高的单通道二值图
        """
        if mode == "manual" and manual_bbox is not None:
            return self.detect_manual(image.shape[:2], manual_bbox)
        elif mode == "fixed_region":
            return self.detect_fixed_region(image, region, margin_ratio)
        elif mode == "full_scan":
            return self.detect_full_scan(image)
        else:
            # auto 模式
            return self.detect_auto(
                image,
                region,
                margin_ratio,
                fallback_to_fixed=fallback_to_fixed,
            )

    def detect_auto(
        self,
        image: np.ndarray,
        region: str = "bottom_right",
        margin_ratio: float = 0.15,
        fallback_to_fixed: bool = True,
    ) -> np.ndarray:
        """
        OpenCV 智能检测：在候选区域内用边缘+轮廓分析精确定位水印

        流程:
        1. 裁剪候选区域 (如右下角15%)
        2. 灰度转换 + 高斯模糊去噪
        3. Canny 边缘检测
        4. 形态学闭运算连接相邻边缘
        5. findContours 提取轮廓
        6. 过滤符合水印特征的轮廓 (面积/宽高比/填充率)
        7. 膨胀 mask 确保覆盖水印边缘
        8. 无检测结果时 fallback 到固定区域
        """
        h, w = image.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)

        # 1. 确定候选区域坐标
        y1, y2, x1, x2 = self._get_region_coords(h, w, region, margin_ratio)
        roi = image[y1:y2, x1:x2]

        if roi.size == 0:
            logger.warning("候选区域为空，回退到固定区域模式")
            if fallback_to_fixed:
                return self.detect_fixed_region(image, region, margin_ratio)
            return mask

        # 2. 灰度 + 高斯模糊
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        # 3. Canny 边缘检测 (阈值受灵敏度控制)
        low_thresh = int(50 * (1.0 - self.sensitivity * 0.5))
        high_thresh = int(150 * (1.0 - self.sensitivity * 0.3))
        edges = cv2.Canny(blurred, low_thresh, high_thresh)

        # 4. 形态学闭运算连接相邻边缘
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

        # 5. 提取轮廓
        contours, _ = cv2.findContours(
            closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # 6. 过滤水印特征轮廓
        roi_h, roi_w = roi.shape[:2]
        roi_area = roi_h * roi_w
        min_area = roi_area * 0.005  # 至少占候选区域 0.5%
        max_area = roi_area * 0.8    # 最多占候选区域 80%

        roi_mask = np.zeros((roi_h, roi_w), dtype=np.uint8)
        found_contours = 0

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area or area > max_area:
                continue

            bx, by, bw, bh = cv2.boundingRect(contour)
            aspect_ratio = bw / max(bh, 1)
            fill_ratio = area / max(bw * bh, 1)

            # 水印通常：宽高比 0.1-20, 填充率 > 0.1
            if 0.1 < aspect_ratio < 20 and fill_ratio > 0.1:
                cv2.drawContours(roi_mask, [contour], -1, 255, -1)
                found_contours += 1

        # 7. 膨胀确保覆盖
        if found_contours > 0:
            dilate_size = max(10, int(15 * self.sensitivity))
            dilate_kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (dilate_size, dilate_size)
            )
            roi_mask = cv2.dilate(roi_mask, dilate_kernel, iterations=2)

            # 放回全图 mask
            mask[y1:y2, x1:x2] = roi_mask
            logger.info(
                f"智能检测完成: 区域={region}, 找到 {found_contours} 个水印轮廓"
            )
            return mask

        # 8. 无检测结果，按配置决定是否回退固定区域
        if fallback_to_fixed:
            logger.info("智能检测未找到水印轮廓，回退到固定区域模式")
            return self.detect_fixed_region(image, region, margin_ratio)
        logger.info("智能检测未找到水印轮廓，返回空掩码")
        return mask

    def detect_fixed_region(
        self,
        image: np.ndarray,
        region: str = "bottom_right",
        margin_ratio: float = 0.15,
    ) -> np.ndarray:
        """
        固定区域蒙版（兼容旧逻辑）

        将指定角落的矩形区域整体标记为水印
        """
        h, w = image.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)

        y1, y2, x1, x2 = self._get_region_coords(h, w, region, margin_ratio)
        mask[y1:y2, x1:x2] = 255

        logger.info(f"固定区域检测: {region}, 比例={margin_ratio}")
        return mask

    def detect_manual(
        self,
        image_shape: Tuple[int, int],
        bbox: Tuple[int, int, int, int],
    ) -> np.ndarray:
        """
        手动框选水印区域

        Args:
            image_shape: (height, width)
            bbox: 用户框选坐标 (x1, y1, x2, y2)
        """
        h, w = image_shape
        x1, y1, x2, y2 = bbox
        mask = np.zeros((h, w), dtype=np.uint8)

        # 确保坐标有效
        x1, x2 = max(0, min(x1, x2)), min(w, max(x1, x2))
        y1, y2 = max(0, min(y1, y2)), min(h, max(y1, y2))

        mask[y1:y2, x1:x2] = 255

        logger.info(f"手动框选水印区域: ({x1}, {y1}) -> ({x2}, {y2})")
        return mask

    def detect_full_scan(self, image: np.ndarray) -> np.ndarray:
        """
        全图扫描模式：在整张图片上检测水印

        使用边缘检测 + 频域分析检测重复/半透明水印模式
        """
        h, w = image.shape[:2]

        # 灰度 + 模糊
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # 自适应阈值 + 边缘检测
        low_thresh = int(30 * (1.0 - self.sensitivity * 0.5))
        high_thresh = int(100 * (1.0 - self.sensitivity * 0.3))
        edges = cv2.Canny(blurred, low_thresh, high_thresh)

        # 形态学操作
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

        # 提取轮廓
        contours, _ = cv2.findContours(
            closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        mask = np.zeros((h, w), dtype=np.uint8)
        total_area = h * w
        min_area = total_area * 0.001   # 至少 0.1% 的图片面积
        max_area = total_area * 0.15    # 最多 15% (水印通常不会太大)

        found = 0
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area or area > max_area:
                continue

            bx, by, bw, bh = cv2.boundingRect(contour)
            fill_ratio = area / max(bw * bh, 1)

            # 水印特征：有一定填充率，不是噪点
            if fill_ratio > 0.15:
                cv2.drawContours(mask, [contour], -1, 255, -1)
                found += 1

        if found > 0:
            dilate_kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (15, 15)
            )
            mask = cv2.dilate(mask, dilate_kernel, iterations=2)

        logger.info(f"全图扫描完成: 找到 {found} 个疑似水印区域")
        return mask

    def _get_region_coords(
        self, h: int, w: int, region: str, margin_ratio: float
    ) -> Tuple[int, int, int, int]:
        """
        根据区域名和比例计算矩形坐标

        Returns:
            (y1, y2, x1, x2) — 注意是行/列顺序，方便 numpy 切片
        """
        margin_h = int(h * margin_ratio)
        margin_w = int(w * margin_ratio)

        if region == "bottom_right":
            return (h - margin_h, h, w - margin_w, w)
        elif region == "bottom_left":
            return (h - margin_h, h, 0, margin_w)
        elif region == "top_right":
            return (0, margin_h, w - margin_w, w)
        elif region == "top_left":
            return (0, margin_h, 0, margin_w)
        else:
            # 默认右下角
            return (h - margin_h, h, w - margin_w, w)
