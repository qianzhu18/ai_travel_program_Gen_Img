import base64
import hashlib
import hmac
import json
import os
import re
import time
import urllib.parse
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont


def _load_ak_sk() -> tuple[str, str]:
    env_ak = os.getenv("VOLC_ACCESS_KEY_ID", "").strip()
    env_sk = os.getenv("VOLC_SECRET_ACCESS_KEY", "").strip()
    if env_ak and env_sk:
        return env_ak, env_sk

    access_path = Path(__file__).resolve().parents[1] / "可行性分析" / "AccessKey.txt"
    if not access_path.exists():
        raise RuntimeError("AccessKey.txt not found; set VOLC_ACCESS_KEY_ID/VOLC_SECRET_ACCESS_KEY instead.")

    content = access_path.read_text(encoding="utf-8", errors="ignore")
    ak_match = re.search(r"AccessKeyId:\s*([A-Za-z0-9]+)", content)
    sk_match = re.search(r"SecretAccessKey:\s*([A-Za-z0-9+/=]+)", content)
    if not ak_match or not sk_match:
        raise RuntimeError("AccessKeyId/SecretAccessKey not found in AccessKey.txt.")
    return ak_match.group(1), sk_match.group(1)


def _make_sample_images(size: int = 512) -> tuple[str, str]:
    img = Image.new("RGB", (size, size), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    text = "WATERMARK"
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    text_w, text_h = draw.textbbox((0, 0), text, font=font)[2:]
    x = size - text_w - 20
    y = size - text_h - 20
    draw.rectangle([x - 6, y - 4, x + text_w + 6, y + text_h + 4], fill=(240, 240, 240))
    draw.text((x, y), text, fill=(50, 50, 50), font=font)

    mask = Image.new("L", (size, size), color=0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rectangle([x - 8, y - 6, x + text_w + 8, y + text_h + 6], fill=255)

    def to_b64(pil_img: Image.Image) -> str:
        buffer = BytesIO()
        pil_img.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    return to_b64(img), to_b64(mask)


def _hash_sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _get_signature_key(secret_key: str, date_stamp: str, region: str, service: str) -> bytes:
    k_date = _sign(secret_key.encode("utf-8"), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    return _sign(k_service, "request")


def _canonical_query(params: dict) -> str:
    items = []
    for k in sorted(params.keys()):
        v = params[k]
        items.append(
            f"{urllib.parse.quote(str(k), safe='-_.~')}="
            f"{urllib.parse.quote(str(v), safe='-_.~')}"
        )
    return "&".join(items)


def _build_auth(
    method: str,
    host: str,
    uri: str,
    query: dict,
    body: bytes,
    access_key: str,
    secret_key: str,
    region: str,
    service: str,
    content_type: str,
) -> tuple[dict, str]:
    x_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    short_date = x_date[:8]
    payload_hash = _hash_sha256_hex(body)

    headers = {
        "host": host,
        "content-type": content_type,
        "x-date": x_date,
        "x-content-sha256": payload_hash,
    }

    signed_headers = ";".join(sorted(headers.keys()))
    canonical_headers = "".join(f"{k}:{headers[k]}\n" for k in sorted(headers.keys()))
    canonical_query = _canonical_query(query)

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

    credential_scope = f"{short_date}/{region}/{service}/request"
    string_to_sign = "\n".join(
        [
            "HMAC-SHA256",
            x_date,
            credential_scope,
            _hash_sha256_hex(canonical_request.encode("utf-8")),
        ]
    )

    signing_key = _get_signature_key(secret_key, short_date, region, service)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    return {
        "Content-Type": content_type,
        "Host": host,
        "X-Date": x_date,
        "X-Content-Sha256": payload_hash,
        "Authorization": authorization,
    }, x_date


def _post(action: str, version: str, body_obj: dict, access_key: str, secret_key: str) -> dict:
    host = "visual.volcengineapi.com"
    endpoint = "https://visual.volcengineapi.com"
    region = os.getenv("VOLC_REGION", "cn-north-1")
    service = os.getenv("VOLC_SERVICE", "cv")
    uri = "/"
    method = "POST"
    query = {"Action": action, "Version": version}
    body = json.dumps(body_obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    headers, _ = _build_auth(method, host, uri, query, body, access_key, secret_key, region, service, "application/json")

    with httpx.Client(timeout=120.0) as client:
        resp = client.post(endpoint, params=query, headers=headers, content=body)

    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")

    return resp.json()


def main() -> None:
    access_key, secret_key = _load_ak_sk()
    image_b64, mask_b64 = _make_sample_images()

    submit_body = {
        "binary_data_base64": [image_b64, mask_b64],
        "req_key": "i2i_inpainting",
        "seed": 0,
        "steps": 30,
        "strength": 0.8,
    }

    submit_resp = _post("CVSync2AsyncSubmitTask", "2022-08-31", submit_body, access_key, secret_key)
    print(f"submit: code={submit_resp.get('code')} message={submit_resp.get('message')} request_id={submit_resp.get('request_id')}")

    if submit_resp.get("code") != 10000:
        print("Submit failed, stop.")
        return

    task_id = (submit_resp.get("data") or {}).get("task_id")
    if not task_id:
        print("No task_id returned.")
        return

    query_body = {
        "req_key": "i2i_inpainting",
        "task_id": task_id,
        "req_json": json.dumps({"return_url": True}, separators=(",", ":")),
    }

    for _ in range(30):
        time.sleep(2)
        query_resp = _post("CVSync2AsyncGetResult", "2022-08-31", query_body, access_key, secret_key)
        code = query_resp.get("code")
        data = query_resp.get("data") or {}
        status = data.get("status")
        print(f"query: code={code} status={status} request_id={query_resp.get('request_id')}")

        if code != 10000:
            print("Query failed.")
            return

        if status == "done":
            img_b64_list = data.get("binary_data_base64") or []
            if img_b64_list:
                out_path = Path(__file__).resolve().parents[1] / "data" / "processed" / "volc_inpaint_test.png"
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(base64.b64decode(img_b64_list[0]))
                print(f"saved: {out_path}")
            else:
                print(f"image_urls: {data.get('image_urls')}")
            return

    print("Query timeout.")


if __name__ == "__main__":
    main()
