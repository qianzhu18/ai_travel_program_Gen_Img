"""
火山引擎官方 AIGC 图片生成服务
直接调用火山引擎 API，不通过中转站
"""
import asyncio
import base64
import hashlib
import hmac
import json
import urllib.parse
from datetime import datetime, timezone
from typing import Optional

import cv2
import httpx
import numpy as np


class VolcImageGenClient:
    """
    火山引擎 AIGC 图片生成客户端

    文档: https://www.volcengine.com/docs/83413/1265952
    """

    # 火山引擎 AIGC 支持的生图模型
    MODELS = {
        "latentSync": "latentSync",           # 人物写真生成
        "sdxl": "sdxl",                       # SDXL 模型
        "ace": "ace",                         # Ace 模型
        "wd_v1.4": "wd_v1_4",                 # WD 1.4 模型
    }

    def __init__(
        self,
        access_key_id: str,
        secret_access_key: str,
        endpoint: str = "https://visual.volcengineapi.com",
        region: str = "cn-north-1",
        service: str = "cv",
        timeout: float = 300.0,
    ):
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.endpoint = endpoint.rstrip("/")
        self.region = region
        self.service = service
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self.last_error: str = ""
        self.last_error_code: str = ""

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def _hash_sha256_hex(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    def _get_signature_key(self, date_stamp: str) -> bytes:
        k_date = self._sign(self.secret_access_key.encode("utf-8"), date_stamp)
        k_region = self._sign(k_date, self.region)
        k_service = self._sign(k_region, self.service)
        return self._sign(k_service, "request")

    @staticmethod
    def _canonical_query(params: dict) -> str:
        items = []
        for k in sorted(params.keys()):
            v = params[k]
            items.append(
                f"{urllib.parse.quote(str(k), safe='-_.~')}="
                f"{urllib.parse.quote(str(v), safe='-_.~')}"
            )
        return "&".join(items)

    def _build_auth_headers(self, method: str, host: str, uri: str, query: dict, body: bytes) -> dict:
        x_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        short_date = x_date[:8]
        payload_hash = self._hash_sha256_hex(body)

        headers = {
            "host": host,
            "content-type": "application/json",
            "x-date": x_date,
            "x-content-sha256": payload_hash,
        }

        signed_headers = ";".join(sorted(headers.keys()))
        canonical_headers = "".join(f"{k}:{headers[k]}\n" for k in sorted(headers.keys()))
        canonical_query = self._canonical_query(query)

        canonical_request = "\n".join(
            [
                method.upper(),
                uri,
                canonical_query,
                canonical_headers,
                signed_headers,
                payload_hash,
            ]
        )

        credential_scope = f"{short_date}/{self.region}/{self.service}/request"
        string_to_sign = "\n".join(
            [
                "HMAC-SHA256",
                x_date,
                credential_scope,
                self._hash_sha256_hex(canonical_request.encode("utf-8")),
            ]
        )

        signing_key = self._get_signature_key(short_date)
        signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        authorization = (
            f"HMAC-SHA256 Credential={self.access_key_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        return {
            "Content-Type": "application/json",
            "Host": host,
            "X-Date": x_date,
            "X-Content-Sha256": payload_hash,
            "Authorization": authorization,
        }

    async def _post(self, action: str, version: str, body_obj: dict) -> dict:
        method = "POST"
        uri = "/"
        host = urllib.parse.urlparse(self.endpoint).netloc
        query = {"Action": action, "Version": version}
        body = json.dumps(body_obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers = self._build_auth_headers(method, host, uri, query, body)

        client = await self._get_client()
        resp = await client.post(self.endpoint, params=query, headers=headers, content=body)

        if resp.status_code != 200:
            self.last_error = f"HTTP {resp.status_code}: {resp.text[:500]}"
            self.last_error_code = f"http_{resp.status_code}"
            raise RuntimeError(self.last_error)

        return resp.json()

    @staticmethod
    def _encode_image_base64(image_path: str) -> str:
        """编码图片为 Base64"""
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"无法读取图片: {image_path}")
        ok, buf = cv2.imencode(".jpg", image_path, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            raise ValueError("图片编码失败")
        return base64.b64encode(buf.tobytes()).decode("utf-8")

    async def text_to_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        model: str = "latentSync",
        size: str = "1440x2560",
        seed: int = 0,
        steps: int = 30,
        cfg_scale: float = 7.5,
        req_key: str = "aigc_text2img",
        poll_interval: float = 2.0,
        max_polls: int = 60,
    ) -> Optional[str]:
        """
        文生图

        Args:
            prompt: 正向提示词
            negative_prompt: 负向提示词
            model: 模型名称
            size: 图片尺寸，格式 "宽x高"
            seed: 随机种子，0 为随机
            steps: 生成步数
            cfg_scale: 提示词相关度
            req_key: 请求标识
            poll_interval: 轮询间隔（秒）
            max_polls: 最大轮询次数

        Returns:
            图片 URL 或 None
        """
        self.last_error = ""
        self.last_error_code = ""

        width, height = map(int, size.split("x"))

        submit_body = {
            "req_key": req_key,
            "prompt": prompt,
            "model_version": model,
            "width": width,
            "height": height,
            "seed": seed,
            "steps": steps,
            "cfg_scale": cfg_scale,
        }

        if negative_prompt:
            submit_body["negative_prompt"] = negative_prompt

        # 提交任务
        submit_resp = await self._post("CVSync2AsyncSubmitTask", "2022-08-31", submit_body)
        if submit_resp.get("code") != 10000:
            self.last_error = f"提交失败: {submit_resp.get('message')}"
            self.last_error_code = f"volc_{submit_resp.get('code')}"
            return None

        task_id = (submit_resp.get("data") or {}).get("task_id")
        if not task_id:
            self.last_error = "提交失败: 缺少 task_id"
            self.last_error_code = "missing_task_id"
            return None

        # 轮询结果
        return await self._poll_result(task_id, req_key, poll_interval, max_polls)

    async def image_to_image(
        self,
        prompt: str,
        reference_image_path: str,
        negative_prompt: str = "",
        model: str = "latentSync",
        size: str = "1440x2560",
        strength: float = 0.7,
        seed: int = 0,
        steps: int = 30,
        cfg_scale: float = 7.5,
        req_key: str = "aigc_img2img",
        poll_interval: float = 2.0,
        max_polls: int = 60,
    ) -> Optional[str]:
        """
        图生图

        Args:
            prompt: 正向提示词
            reference_image_path: 参考图路径
            negative_prompt: 负向提示词
            model: 模型名称
            size: 图片尺寸
            strength: 参考强度，0-1，越大越接近参考图
            seed: 随机种子
            steps: 生成步数
            cfg_scale: 提示词相关度
            req_key: 请求标识
            poll_interval: 轮询间隔
            max_polls: 最大轮询次数

        Returns:
            图片 URL 或 None
        """
        self.last_error = ""
        self.last_error_code = ""

        width, height = map(int, size.split("x"))

        # 编码参考图
        ref_b64 = self._encode_image_base64(reference_image_path)

        submit_body = {
            "req_key": req_key,
            "prompt": prompt,
            "model_version": model,
            "binary_data_base64": [ref_b64],
            "width": width,
            "height": height,
            "strength": strength,
            "seed": seed,
            "steps": steps,
            "cfg_scale": cfg_scale,
        }

        if negative_prompt:
            submit_body["negative_prompt"] = negative_prompt

        # 提交任务
        submit_resp = await self._post("CVSync2AsyncSubmitTask", "2022-08-31", submit_body)
        if submit_resp.get("code") != 10000:
            self.last_error = f"提交失败: {submit_resp.get('message')}"
            self.last_error_code = f"volc_{submit_resp.get('code')}"
            return None

        task_id = (submit_resp.get("data") or {}).get("task_id")
        if not task_id:
            self.last_error = "提交失败: 缺少 task_id"
            self.last_error_code = "missing_task_id"
            return None

        # 轮询结果
        return await self._poll_result(task_id, req_key, poll_interval, max_polls)

    async def _poll_result(
        self,
        task_id: str,
        req_key: str,
        poll_interval: float = 2.0,
        max_polls: int = 60,
    ) -> Optional[str]:
        """轮询任务结果"""
        query_body = {
            "req_key": req_key,
            "task_id": task_id,
            "req_json": json.dumps({"return_url": True}, separators=(",", ":")),
        }

        for _ in range(max_polls):
            await asyncio.sleep(poll_interval)
            query_resp = await self._post("CVSync2AsyncGetResult", "2022-08-31", query_body)

            if query_resp.get("code") != 10000:
                self.last_error = f"查询失败: {query_resp.get('message')}"
                self.last_error_code = f"volc_{query_resp.get('code')}"
                return None

            data = query_resp.get("data") or {}
            status = data.get("status")

            if status == "done":
                image_urls = data.get("image_urls") or []
                if image_urls:
                    return image_urls[0]
                self.last_error = "任务完成但无图片"
                self.last_error_code = "no_image"
                return None

            if status in ("failed", "error"):
                self.last_error = f"任务失败: status={status}"
                self.last_error_code = f"volc_{status}"
                return None

        self.last_error = "任务超时"
        self.last_error_code = "timeout"
        return None
