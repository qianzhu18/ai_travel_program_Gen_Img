"""系统设置API路由"""
import logging
import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.encryption import encrypt_value, decrypt_value, mask_value, is_api_key_field
from app.models.database import Settings
from app.schemas.common import BaseResponse, SettingBatchUpdateRequest, TestConnectionRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=BaseResponse)
async def get_settings(db: Session = Depends(get_db)):
    """获取全部系统设置"""
    rows = db.query(Settings).all()
    data = {}
    for row in rows:
        value = row.value or ""
        if is_api_key_field(row.key) and value:
            # API Key 字段：解密后掩码显示
            plain = decrypt_value(value)
            data[row.key] = {
                "value": mask_value(plain),
                "description": row.description or ""
            }
        else:
            data[row.key] = {
                "value": value,
                "description": row.description or ""
            }
    return BaseResponse(code=0, message="获取设置成功", data=data)


@router.get("/raw", response_model=BaseResponse)
async def get_settings_raw(db: Session = Depends(get_db)):
    """获取全部系统设置（API Key 解密为明文，仅供内部服务调用）"""
    rows = db.query(Settings).all()
    data = {}
    for row in rows:
        value = row.value or ""
        if is_api_key_field(row.key) and value:
            value = decrypt_value(value)
        data[row.key] = {
            "value": value,
            "description": row.description or ""
        }
    return BaseResponse(code=0, message="获取设置成功", data=data)


@router.post("/update", response_model=BaseResponse)
async def update_settings(request: SettingBatchUpdateRequest, db: Session = Depends(get_db)):
    """批量更新系统设置"""
    updated = 0
    for item in request.settings:
        value = item.value
        # API Key 字段自动加密
        if is_api_key_field(item.key) and value and not value.startswith("****"):
            value = encrypt_value(value)

        existing = db.query(Settings).filter(Settings.key == item.key).first()
        if existing:
            # 如果前端传来的是掩码值，跳过更新（用户没改这个字段）
            if is_api_key_field(item.key) and item.value.startswith("****"):
                continue
            existing.value = value
        else:
            db.add(Settings(key=item.key, value=value))
        updated += 1

    db.commit()
    return BaseResponse(code=0, message=f"已更新 {updated} 项设置")


@router.post("/test-connection", response_model=BaseResponse)
async def test_connection(request: TestConnectionRequest, db: Session = Depends(get_db)):
    """测试 API Key 连通性"""
    service = request.service.lower()
    api_key = request.api_key
    model = (request.model or "").strip()

    # 如果前端传来的是掩码值，从数据库读取已保存的明文 key
    if not api_key or api_key.startswith("****"):
        key_map = {
            "bailian": "prompt_api_key",
            "apiyi": "apiyi_api_key",
            "ark": "ark_api_key",
        }
        key_field = key_map.get(service, "apiyi_api_key")
        row = db.query(Settings).filter(Settings.key == key_field).first()
        if row and row.value:
            api_key = decrypt_value(row.value)
        if not api_key or api_key.startswith("****"):
            return BaseResponse(code=1, message="请先输入并保存有效的 API Key")

    try:
        timeout = 90.0 if service == "ark" else 15.0
        async with httpx.AsyncClient(timeout=timeout) as client:
            if service == "bailian":
                # 阿里百炼 - 调用 OpenAI 兼容的模型列表接口验证
                resp = await client.get(
                    "https://dashscope.aliyuncs.com/compatible-mode/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                if resp.status_code == 200:
                    return BaseResponse(code=0, message="阿里百炼连接成功", data={"connected": True})
                else:
                    return BaseResponse(code=1, message=f"阿里百炼认证失败 (HTTP {resp.status_code})",
                                        data={"connected": False})

            elif service == "apiyi":
                # API易平台 - 调用模型列表接口验证
                resp = await client.get(
                    "https://api.apiyi.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                if resp.status_code == 200:
                    return BaseResponse(code=0, message="API易平台连接成功",
                                        data={"connected": True})
                # 某些中转平台不支持 /v1/models，尝试用空请求探测认证
                if resp.status_code in (401, 403):
                    return BaseResponse(code=1, message=f"API易平台认证失败 (HTTP {resp.status_code})，请检查 API Key 是否正确",
                                        data={"connected": False})
                # 404 等状态码说明平台不支持 models 端点，但 key 格式可能是对的
                # 尝试发一个最小的 chat 请求来验证 key
                chat_resp = await client.post(
                    "https://api.apiyi.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": 1,
                    },
                )
                if chat_resp.status_code in (200, 429):
                    # 200 = 成功, 429 = 限流但 key 有效
                    return BaseResponse(code=0, message="API易平台连接成功",
                                        data={"connected": True})
                return BaseResponse(code=1, message=f"API易平台认证失败 (HTTP {chat_resp.status_code})，请检查 API Key 是否正确",
                                    data={"connected": False})

            elif service == "ark":
                # 即梦 Ark 图文生图连通性验证（真实生图请求，单图输入单图输出）
                if not model:
                    row = db.query(Settings).filter(Settings.key == "ark_model").first()
                    model = (row.value if row else "").strip() or "doubao-seedream-4-5-251128"

                candidate_sizes = ["2K", "1K"] if "4-5" in model or "4.5" in model else ["1K", "2K"]
                resp = None
                used_size = ""
                for size in candidate_sizes:
                    payload = {
                        "model": model,
                        "prompt": "保持原图构图，进行轻微风格化处理（测试请求）。",
                        "image": "https://ark-project.tos-cn-beijing.volces.com/doc_image/seedream4_imageToimage.png",
                        "size": size,
                        "watermark": False,
                    }

                    resp = await client.post(
                        "https://ark.cn-beijing.volces.com/api/v3/images/generations",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                    used_size = size
                    if resp.status_code == 200:
                        break
                    detail = (resp.text or "").lower()
                    # 尺寸不支持时尝试下一个候选尺寸
                    if resp.status_code in (400, 422) and "size" in detail and "not valid" in detail:
                        continue
                    break

                if resp is not None and resp.status_code == 200:
                    result = resp.json()
                    images = result.get("data") or []
                    image_url = ""
                    if isinstance(images, list) and images and isinstance(images[0], dict):
                        image_url = str(images[0].get("url") or "")
                    return BaseResponse(
                        code=0,
                        message=f"即梦 Ark 可用（模型: {model}）",
                        data={
                            "connected": True,
                            "model": model,
                            "size": used_size,
                            "image_url": image_url,
                        },
                    )

                if resp is None:
                    return BaseResponse(
                        code=1,
                        message="即梦 Ark 测试失败：未得到有效响应",
                        data={"connected": False, "model": model},
                    )

                error_text = resp.text[:500]
                error_code = ""
                error_msg = error_text
                try:
                    error_payload = resp.json().get("error", {})
                    error_code = str(error_payload.get("code") or "")
                    error_msg = str(error_payload.get("message") or error_text)
                except Exception:
                    pass

                msg = f"即梦 Ark 测试失败 (HTTP {resp.status_code})"
                if error_code:
                    msg += f" [{error_code}]"
                msg += f": {error_msg[:180]}"
                return BaseResponse(
                    code=1,
                    message=msg,
                    data={
                        "connected": False,
                        "model": model,
                        "status_code": resp.status_code,
                        "error_code": error_code,
                    },
                )

            elif service == "volcgen":
                # 火山引擎生图 - 测试 AK/SK 是否有效
                ak_key = "volcgen_access_key_id"
                sk_key = "volcgen_secret_access_key"

                # 如果请求中包含完整的 AK/SK（格式: AK:SK），使用请求中的值
                if ":" in api_key:
                    parts = api_key.split(":", 1)
                    access_key_id = parts[0]
                    secret_access_key = parts[1] if len(parts) > 1 else ""
                else:
                    # 否则从数据库读取
                    ak_row = db.query(Settings).filter(Settings.key == ak_key).first()
                    sk_row = db.query(Settings).filter(Settings.key == sk_key).first()
                    access_key_id = decrypt_value(ak_row.value) if ak_row and ak_row.value else ""
                    secret_access_key = decrypt_value(sk_row.value) if sk_row and sk_row.value else ""

                if not access_key_id or not secret_access_key:
                    return BaseResponse(code=1, message="请先配置火山引擎 AccessKeyId 和 SecretAccessKey",
                                        data={"connected": False})

                try:
                    from app.services.volc_image_gen import VolcImageGenClient

                    volc_client = VolcImageGenClient(
                        access_key_id=access_key_id,
                        secret_access_key=secret_access_key,
                    )

                    # 尝试调用接口验证凭据
                    test_body = {
                        "req_key": "aigc_text2img",
                        "prompt": "test",
                        "model_version": "latentSync",
                        "width": 512,
                        "height": 512,
                        "seed": 0,
                        "steps": 10,
                    }

                    result = await volc_client._post("CVSync2AsyncSubmitTask", "2022-08-31", test_body)
                    await volc_client.close()

                    # 只要没有抛出异常，说明认证是成功的
                    return BaseResponse(code=0, message="火山引擎生图连接成功",
                                        data={"connected": True})

                except RuntimeError as e:
                    error_str = str(e)
                    if "HTTP 400" in error_str or "HTTP 403" in error_str or "HTTP 401" in error_str:
                        return BaseResponse(code=1, message="火山引擎认证失败，请检查 AK/SK 是否正确",
                                            data={"connected": False})
                    return BaseResponse(code=1, message=f"火山引擎连接失败: {error_str[:100]}",
                                        data={"connected": False})
                except Exception as e:
                    return BaseResponse(code=1, message=f"火山引擎连接失败: {str(e)[:100]}",
                                        data={"connected": False})

            else:
                return BaseResponse(code=1, message=f"未知服务: {service}")

    except httpx.TimeoutException:
        return BaseResponse(code=1, message=f"{service} 连接超时，请检查网络", data={"connected": False})
    except Exception as e:
        logger.error(f"测试连接失败: {e}")
        return BaseResponse(code=1, message=f"连接失败: {str(e)}", data={"connected": False})
