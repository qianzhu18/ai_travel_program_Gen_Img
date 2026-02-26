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


class VolcVisualClient:
    """Volcengine Visual API client for inpainting (async)."""

    def __init__(
        self,
        access_key_id: str,
        secret_access_key: str,
        endpoint: str = "https://visual.volcengineapi.com",
        region: str = "cn-north-1",
        service: str = "cv",
        timeout: float = 120.0,
    ):
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.endpoint = endpoint.rstrip("/")
        self.region = region
        self.service = service
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self.last_error: str = ""

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
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")

        return resp.json()

    @staticmethod
    def _encode_png_base64(image: np.ndarray) -> str:
        ok, buf = cv2.imencode(".png", image)
        if not ok:
            raise RuntimeError("Failed to encode image to PNG")
        return base64.b64encode(buf.tobytes()).decode("utf-8")

    async def inpaint(
        self,
        image: np.ndarray,
        mask: np.ndarray,
        req_key: str = "i2i_inpainting",
        seed: int = 0,
        steps: int = 30,
        strength: float = 0.8,
        poll_interval: float = 2.0,
        max_polls: int = 30,
    ) -> Optional[np.ndarray]:
        self.last_error = ""
        image_b64 = self._encode_png_base64(image)
        mask_b64 = self._encode_png_base64(mask)

        submit_body = {
            "binary_data_base64": [image_b64, mask_b64],
            "req_key": req_key,
            "seed": seed,
            "steps": steps,
            "strength": strength,
        }

        submit_resp = await self._post("CVSync2AsyncSubmitTask", "2022-08-31", submit_body)
        if submit_resp.get("code") != 10000:
            self.last_error = f"submit failed: {submit_resp.get('message')} ({submit_resp.get('code')})"
            return None

        task_id = (submit_resp.get("data") or {}).get("task_id")
        if not task_id:
            self.last_error = "submit failed: missing task_id"
            return None

        query_body = {
            "req_key": req_key,
            "task_id": task_id,
            "req_json": json.dumps({"return_url": True}, separators=(",", ":")),
        }

        for _ in range(max_polls):
            await asyncio.sleep(poll_interval)
            query_resp = await self._post("CVSync2AsyncGetResult", "2022-08-31", query_body)
            if query_resp.get("code") != 10000:
                self.last_error = f"query failed: {query_resp.get('message')} ({query_resp.get('code')})"
                return None

            data = query_resp.get("data") or {}
            status = data.get("status")

            if status == "done":
                img_b64_list = data.get("binary_data_base64") or []
                if img_b64_list:
                    img_bytes = base64.b64decode(img_b64_list[0])
                else:
                    image_urls = data.get("image_urls") or []
                    if not image_urls:
                        self.last_error = "query done but no image returned"
                        return None
                    client = await self._get_client()
                    dl_resp = await client.get(image_urls[0])
                    img_bytes = dl_resp.content

                arr = np.frombuffer(img_bytes, dtype=np.uint8)
                result = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                return result

            if status in ("failed", "error"):
                self.last_error = f"query failed status={status}"
                return None

        self.last_error = "query timeout"
        return None
