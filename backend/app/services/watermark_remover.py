"""
水印去除服务 - 基于 IOPaint HTTP API + OpenCV 检测

架构: 后端通过 HTTP 调用独立运行的 IOPaint 服务 (默认 localhost:8090)
IOPaint API: POST /api/v1/inpaint  (JSON body, base64 编码图片)
"""
import cv2
import numpy as np
import httpx
import base64
import asyncio
from pathlib import Path
from typing import Tuple, Optional, Dict, List, Callable
import logging

from app.services.watermark_detector import WatermarkDetector
from app.services.volc_visual import VolcVisualClient
from app.core.config import settings

logger = logging.getLogger(__name__)


class IOPaintClient:
    """IOPaint HTTP 服务客户端"""

    def __init__(self, service_url: str = settings.IOPAINT_URL, timeout: float = 60.0):
        """
        Args:
            service_url: IOPaint 服务地址
            timeout: 单次请求超时 (秒)
        """
        self.service_url = service_url.rstrip("/")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def health_check(self) -> bool:
        """检查 IOPaint 服务是否可用"""
        try:
            client = await self._get_client()
            resp = await client.get(
                f"{self.service_url}/api/v1/server-config",
                timeout=5.0,  # 健康检查快速失败
            )
            return resp.status_code == 200
        except Exception:
            return False

    async def inpaint(self, image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """
        调用 IOPaint 修复图片

        Args:
            image: BGR 格式输入图片
            mask: 二值 mask (255=需修复区域, 0=保留)

        Returns:
            修复后的 BGR 图片

        Raises:
            ConnectionError: IOPaint 服务不可用
            RuntimeError: 修复失败
        """
        # 编码为 base64
        _, img_buf = cv2.imencode(".png", image)
        img_b64 = base64.b64encode(img_buf.tobytes()).decode("utf-8")

        _, mask_buf = cv2.imencode(".png", mask)
        mask_b64 = base64.b64encode(mask_buf.tobytes()).decode("utf-8")

        payload = {
            "image": img_b64,
            "mask": mask_b64,
            "ldm_steps": 20,
            "hd_strategy": "Resize",
            "hd_strategy_resize_limit": 2048,
        }

        client = await self._get_client()
        try:
            resp = await client.post(
                f"{self.service_url}/api/v1/inpaint",
                json=payload,
            )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"IOPaint inpaint 失败: HTTP {resp.status_code} - {resp.text[:200]}"
                )

            # 解码响应 (IOPaint 返回 base64 或二进制图片)
            content_type = resp.headers.get("content-type", "")
            if "json" in content_type:
                # JSON 响应 (可能包含 base64 图片)
                data = resp.json()
                if isinstance(data, str):
                    img_bytes = base64.b64decode(data)
                elif isinstance(data, dict) and "image" in data:
                    img_bytes = base64.b64decode(data["image"])
                else:
                    img_bytes = resp.content
            else:
                # 二进制图片响应
                img_bytes = resp.content

            result_array = np.frombuffer(img_bytes, dtype=np.uint8)
            result_image = cv2.imdecode(result_array, cv2.IMREAD_COLOR)

            if result_image is None:
                raise RuntimeError("无法解码 IOPaint 返回的图片")

            return result_image

        except httpx.ConnectError:
            raise ConnectionError(
                f"IOPaint 服务不可用: {self.service_url}\n"
                "请启动 IOPaint: cd iopaint_service && start_iopaint.bat"
            )

    async def outpaint(
        self,
        image: np.ndarray,
        target_width: int,
        target_height: int,
        offset: float = 0.0,
    ) -> np.ndarray:
        """
        调用 IOPaint 扩图 (outpainting)

        通过 use_extender 参数实现画布扩展
        """
        h, w = image.shape[:2]

        # 计算偏移量：正 offset 表示原图向下/右偏移（上/左扩展更多）
        clamped = max(-1.0, min(1.0, float(offset)))
        total_x = max(0, target_width - w)
        total_y = max(0, target_height - h)
        offset_x = int(round(total_x * (0.5 + clamped * 0.5)))
        offset_x = max(0, min(total_x, offset_x))
        offset_y = int(round(total_y * (0.5 + clamped * 0.5)))
        offset_y = max(0, min(total_y, offset_y))

        # 编码图片
        _, img_buf = cv2.imencode(".png", image)
        img_b64 = base64.b64encode(img_buf.tobytes()).decode("utf-8")

        # 创建空白 mask (不需要遮罩特定区域，扩展区域由 extender 参数控制)
        mask = np.zeros((h, w), dtype=np.uint8)
        _, mask_buf = cv2.imencode(".png", mask)
        mask_b64 = base64.b64encode(mask_buf.tobytes()).decode("utf-8")

        payload = {
            "image": img_b64,
            "mask": mask_b64,
            "use_extender": True,
            "extender_x": -offset_x,
            "extender_y": -offset_y,
            "extender_width": target_width,
            "extender_height": target_height,
            "ldm_steps": 20,
            "hd_strategy": "Resize",
            "hd_strategy_resize_limit": 2048,
        }

        client = await self._get_client()
        try:
            resp = await client.post(
                f"{self.service_url}/api/v1/inpaint",
                json=payload,
            )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"IOPaint outpaint 失败: HTTP {resp.status_code}"
                )

            content_type = resp.headers.get("content-type", "")
            if "json" in content_type:
                data = resp.json()
                if isinstance(data, str):
                    img_bytes = base64.b64decode(data)
                elif isinstance(data, dict) and "image" in data:
                    img_bytes = base64.b64decode(data["image"])
                else:
                    img_bytes = resp.content
            else:
                img_bytes = resp.content

            result_array = np.frombuffer(img_bytes, dtype=np.uint8)
            result_image = cv2.imdecode(result_array, cv2.IMREAD_COLOR)

            if result_image is None:
                raise RuntimeError("无法解码 IOPaint outpaint 返回的图片")

            return result_image

        except httpx.ConnectError:
            raise ConnectionError(
                f"IOPaint 服务不可用: {self.service_url}"
            )

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


class WatermarkRemover:
    """水印去除器 - Volcengine Visual or IOPaint + OpenCV 检测"""

    def __init__(
        self,
        iopaint_url: str = settings.IOPAINT_URL,
        detection_mode: str = "auto",
        sensitivity: float = 0.5,
        engine: str = "auto",
        allow_local_fallback: bool = True,
        volc_access_key_id: str = settings.VOLC_ACCESS_KEY_ID,
        volc_secret_access_key: str = settings.VOLC_SECRET_ACCESS_KEY,
        volc_region: str = settings.VOLC_REGION,
        volc_service: str = settings.VOLC_SERVICE,
    ):
        self.detector = WatermarkDetector(sensitivity=sensitivity)
        self.detection_mode = detection_mode
        self.engine = engine
        self.allow_local_fallback = allow_local_fallback
        self._volc_client = None
        self._iopaint_client = None

        if self.engine == "auto":
            self.engine = "volc" if volc_access_key_id and volc_secret_access_key else "iopaint"

        if self.engine == "volc":
            self._volc_client = VolcVisualClient(
                access_key_id=volc_access_key_id,
                secret_access_key=volc_secret_access_key,
                region=volc_region,
                service=volc_service,
            )
        else:
            self._iopaint_client = IOPaintClient(service_url=iopaint_url)

    @staticmethod
    def _opencv_inpaint(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """本地 OpenCV 兜底去水印（无需外部服务）"""
        h, w = image.shape[:2]
        radius = max(3, int(min(h, w) * 0.01))
        return cv2.inpaint(image, mask, radius, cv2.INPAINT_TELEA)

    async def process_image(
        self,
        input_path: str,
        output_path: str,
        manual_bbox: Optional[Tuple[int, int, int, int]] = None,
        mask_data: Optional[str] = None,
        region: str = "bottom_right",
        margin_ratio: float = 0.15,
        fallback_to_fixed: bool = True,
    ) -> bool:
        """
        完整水印去除流程: 读取 → 检测 → IOPaint修复 → 保存

        Args:
            input_path: 输入图片路径
            output_path: 输出图片路径
            manual_bbox: 手动框选坐标 (x1, y1, x2, y2), None 则自动检测
            mask_data: Base64编码的手动涂抹蒙版图片，提供时跳过自动检测
            region: 水印预期位置
            margin_ratio: 候选区域比例

        Returns:
            是否成功
        """
        try:
            image = cv2.imread(input_path)
            if image is None:
                logger.error(f"无法读取图片: {input_path}")
                return False

            if mask_data:
                # 使用前端传入的手动涂抹蒙版
                if mask_data.startswith("data:"):
                    mask_data = mask_data.split(",", 1)[1]
                mask_bytes = base64.b64decode(mask_data)
                mask_array = np.frombuffer(mask_bytes, dtype=np.uint8)
                mask_color = cv2.imdecode(mask_array, cv2.IMREAD_COLOR)
                if mask_color is None:
                    logger.error(f"无法解码 mask_data")
                    return False
                # 将彩色蒙版转为灰度二值 mask（非黑色区域 → 255）
                mask_gray = cv2.cvtColor(mask_color, cv2.COLOR_BGR2GRAY)
                _, mask = cv2.threshold(mask_gray, 10, 255, cv2.THRESH_BINARY)
                # 确保 mask 尺寸与原图一致
                h, w = image.shape[:2]
                if mask.shape[:2] != (h, w):
                    mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
            else:
                # 自动检测水印
                mode = "manual" if manual_bbox else self.detection_mode
                mask = self.detector.detect(
                    image,
                    mode=mode,
                    region=region,
                    margin_ratio=margin_ratio,
                    manual_bbox=manual_bbox,
                    fallback_to_fixed=fallback_to_fixed,
                )

            # 检查 mask 是否有内容
            if cv2.countNonZero(mask) == 0:
                logger.info(f"未检测到水印，直接复制: {input_path}")
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(output_path, image)
                return True

            # Volcengine / IOPaint / OpenCV 修复
            result = None
            if self.engine == "volc":
                if not self._volc_client:
                    logger.error("Volcengine client not initialized")
                else:
                    try:
                        result = await self._volc_client.inpaint(image, mask)
                        if result is None and self._volc_client.last_error:
                            logger.error(f"Volcengine inpaint failed: {self._volc_client.last_error}")
                    except Exception as e:
                        # Volc 异常不应直接终止流程，允许回退到本地 OpenCV
                        logger.error(f"Volcengine 去水印失败: {e}")
                        result = None
            elif self.engine == "opencv":
                result = self._opencv_inpaint(image, mask)
            else:
                if not self._iopaint_client:
                    logger.error("IOPaint client not initialized")
                else:
                    try:
                        result = await self._iopaint_client.inpaint(image, mask)
                    except ConnectionError as e:
                        logger.error(f"IOPaint 服务不可用: {e}")
                    except Exception as e:
                        logger.error(f"IOPaint 去水印失败: {e}")

            if result is None and self.allow_local_fallback:
                logger.warning("主去水印引擎不可用，已回退到本地 OpenCV 修复")
                result = self._opencv_inpaint(image, mask)

            if result is None:
                logger.error("水印修复失败：所有可用引擎均不可用")
                return False

            # 保存结果
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            ok = cv2.imwrite(output_path, result)
            if not ok:
                logger.error(f"保存去水印结果失败: {output_path}")
                return False

            logger.info(f"水印去除成功: {input_path} -> {output_path}")
            return True

        except Exception as e:
            logger.error(f"水印去除失败: {input_path}, 错误: {e}")
            return False

    async def health_check(self) -> bool:
        if self.engine == "opencv":
            return True
        if self.engine == "volc":
            return self._volc_client is not None or self.allow_local_fallback
        if self._iopaint_client:
            return await self._iopaint_client.health_check() or self.allow_local_fallback
        return self.allow_local_fallback

    async def close(self):
        """关闭客户端连接"""
        if self._volc_client:
            await self._volc_client.close()
        if self._iopaint_client:
            await self._iopaint_client.close()


async def batch_remove_watermarks(
    image_paths: List[str],
    output_dir: str,
    iopaint_url: str = settings.IOPAINT_URL,
    detection_mode: str = "auto",
    sensitivity: float = 0.5,
    manual_masks: Optional[Dict[str, Tuple[int, int, int, int]]] = None,
    region: str = "bottom_right",
    margin_ratio: float = 0.15,
    progress_callback: Optional[Callable] = None,
) -> dict:
    """
    批量去除水印

    Args:
        image_paths: 图片路径列表
        output_dir: 输出目录
        iopaint_url: IOPaint 服务地址
        detection_mode: 检测模式
        sensitivity: 检测灵敏度
        manual_masks: 手动框选 {image_path: (x1,y1,x2,y2)}
        region: 默认水印位置
        margin_ratio: 默认区域比例
        progress_callback: 进度回调 (current, total, filename, status)

    Returns:
        {"success": [path, ...], "failed": [path, ...]}
    """
    remover = WatermarkRemover(
        iopaint_url=iopaint_url,
        detection_mode=detection_mode,
        sensitivity=sensitivity,
    )
    result = {"success": [], "failed": []}

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    total = len(image_paths)

    for i, path in enumerate(image_paths):
        output_path = str(Path(output_dir) / Path(path).name)
        bbox = manual_masks.get(path) if manual_masks else None

        success = await remover.process_image(
            input_path=path,
            output_path=output_path,
            manual_bbox=bbox,
            region=region,
            margin_ratio=margin_ratio,
        )

        if success:
            result["success"].append(path)
        else:
            result["failed"].append(path)

        if progress_callback:
            progress_callback(
                i + 1, total, Path(path).name,
                "success" if success else "failed"
            )

    await remover.close()

    logger.info(
        f"批量去水印完成: 成功 {len(result['success'])} 张, "
        f"失败 {len(result['failed'])} 张"
    )
    return result
