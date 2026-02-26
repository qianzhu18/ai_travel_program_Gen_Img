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

    # 如果前端传来的是掩码值，从数据库读取已保存的明文 key
    if not api_key or api_key.startswith("****"):
        key_field = "prompt_api_key" if service == "bailian" else "apiyi_api_key"
        row = db.query(Settings).filter(Settings.key == key_field).first()
        if row and row.value:
            api_key = decrypt_value(row.value)
        if not api_key or api_key.startswith("****"):
            return BaseResponse(code=1, message="请先输入并保存有效的 API Key")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
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

            else:
                return BaseResponse(code=1, message=f"未知服务: {service}")

    except httpx.TimeoutException:
        return BaseResponse(code=1, message=f"{service} 连接超时，请检查网络", data={"connected": False})
    except Exception as e:
        logger.error(f"测试连接失败: {e}")
        return BaseResponse(code=1, message=f"连接失败: {str(e)}", data={"connected": False})
