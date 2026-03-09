"""
即梦 Ark API 图文生图客户端

文档: https://www.volcengine.com/docs/82379/1824121
API: https://ark.cn-beijing.volces.com/api/v3/images/generations

功能: 基于已有图片，结合文字指令进行图像编辑
"""
import base64
import logging
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class ArkImageClient:
    """
    即梦 Ark API 图文生图客户端

    支持图像元素增删、风格转化、材质替换、色调迁移、改变背景/视角/尺寸等
    """

    API_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"

    # 默认模型（可通过构造参数覆盖）
    MODEL = "doubao-seedream-4-5-251128"

    # 支持的尺寸
    SIZES = ["1K", "2K"]

    # 支持的输出格式
    OUTPUT_FORMATS = ["png", "jpg"]

    def __init__(
        self,
        api_key: str = "",
        model: str = "",
        size: str = "2K",
        output_format: str = "png",
        watermark: bool = False,
        timeout: float = 120.0,
    ):
        """
        初始化 Ark API 客户端

        Args:
            api_key: Ark API Key (Authorization: Bearer $ARK_API_KEY)
            model: Ark 模型ID（需为账号已开通模型）
            size: 输出尺寸 (1K, 2K)
            output_format: 输出格式 (png, jpg)
            watermark: 是否添加水印
            timeout: 请求超时时间（秒）
        """
        self.api_key = api_key
        self.model = self._normalize_model(model)
        self.size = size if size in self.SIZES else "2K"
        self.output_format = output_format if output_format in self.OUTPUT_FORMATS else "png"
        self.watermark = watermark
        self.timeout = timeout
        self.last_error = ""
        self.last_error_code = ""

    @classmethod
    def _normalize_model(cls, model: str) -> str:
        token = (model or "").strip()
        if not token:
            return cls.MODEL
        alias = {
            "doubao-seedream-4.5": "doubao-seedream-4-5-251128",
            "seedream-4.5": "doubao-seedream-4-5-251128",
        }
        return alias.get(token, token)

    def _encode_image_data_uri(self, image_path: str) -> str:
        """将图片编码为 data URI（Ark 对本地图输入需带 data:image/... 前缀）"""
        suffix = Path(image_path).suffix.lower()
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }
        mime = mime_map.get(suffix, "image/jpeg")
        with open(image_path, "rb") as f:
            raw = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime};base64,{raw}"

    async def image_to_image(
        self,
        prompt: str,
        image_path: str,
        size: Optional[str] = None,
        output_format: Optional[str] = None,
        watermark: Optional[bool] = None,
    ) -> Optional[str]:
        """
        图文生图（单图输入单图输出）

        Args:
            prompt: 图像编辑指令（如：保持模特姿势，将服装材质从银色改为透明玻璃）
            image_path: 输入图片路径
            size: 输出尺寸（可选，默认使用初始化值）
            output_format: 输出格式（可选，默认使用初始化值）
            watermark: 是否添加水印（可选，默认使用初始化值）

        Returns:
            生成图片的 URL，失败返回 None
        """
        self.last_error = ""
        self.last_error_code = ""

        if not self.api_key:
            self.last_error = "Ark API Key 未配置"
            self.last_error_code = "missing_api_key"
            logger.error("Ark API Key 未配置")
            return None

        # 编码输入图片
        try:
            image_data_uri = self._encode_image_data_uri(image_path)
        except Exception as e:
            self.last_error = f"读取图片失败: {str(e)}"
            self.last_error_code = "read_image_error"
            logger.error(f"读取图片失败: {e}")
            return None

        output_format_value = output_format or self.output_format

        # 构建请求
        payload = {
            "model": self.model,
            "prompt": prompt,
            "image": image_data_uri,
            "size": size or self.size,
            "watermark": watermark if watermark is not None else self.watermark,
        }
        if output_format_value:
            payload["output_format"] = output_format_value

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.API_URL,
                    json=payload,
                    headers=headers,
                )

                if response.status_code in (400, 422) and "output_format" in payload:
                    # 部分模型不支持 output_format，兼容重试一次
                    detail = (response.text or "").lower()
                    if "output_format" in detail:
                        retry_payload = {k: v for k, v in payload.items() if k != "output_format"}
                        response = await client.post(
                            self.API_URL,
                            json=retry_payload,
                            headers=headers,
                        )

                if response.status_code == 200:
                    result = response.json()
                    image_url = ""
                    data = result.get("data")
                    # 兼容两种返回格式:
                    # 1) {"data":{"image_url":"..."}}
                    # 2) {"data":[{"url":"..."}]}
                    if isinstance(data, dict):
                        image_url = str(data.get("image_url") or data.get("url") or "")
                    elif isinstance(data, list) and data and isinstance(data[0], dict):
                        image_url = str(data[0].get("url") or data[0].get("image_url") or "")
                    if image_url:
                        logger.info(f"Ark API 生图成功: {image_url}")
                        return image_url
                    else:
                        self.last_error = "响应中缺少 image_url"
                        self.last_error_code = "missing_image_url"
                        logger.error(f"Ark API 响应格式异常: {result}")
                        return None
                else:
                    error_detail = response.text[:500]
                    self.last_error = f"HTTP {response.status_code}: {error_detail}"
                    self.last_error_code = f"http_{response.status_code}"

                    # 解析常见错误
                    if response.status_code == 401:
                        self.last_error_code = "unauthorized"
                    elif response.status_code == 429:
                        self.last_error_code = "rate_limited"
                    elif "quota" in error_detail.lower():
                        self.last_error_code = "insufficient_quota"

                    logger.error(f"Ark API 请求失败: {self.last_error}")
                    return None

        except httpx.TimeoutException:
            self.last_error = "请求超时"
            self.last_error_code = "timeout"
            logger.error("Ark API 请求超时")
            return None
        except Exception as e:
            self.last_error = f"请求异常: {str(e)}"
            self.last_error_code = "request_error"
            logger.exception("Ark API 请求异常")
            return None

    async def close(self):
        """关闭客户端（保留接口兼容性）"""
        pass
