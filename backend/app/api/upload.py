"""
素材上传API路由
"""
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from pathlib import Path
import uuid
import shutil
import httpx
import mimetypes
import logging

from app.core.database import get_db
from app.core.config import settings
from app.core.security import sanitize_filename, validate_url
from app.models.database import Batch, BaseImage
from app.schemas.common import BaseResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/batch", response_model=BaseResponse)
async def create_batch_upload(
    files: List[UploadFile] = File(...),
    batch_name: str = Form(...),
    batch_description: str = Form(None),
    db: Session = Depends(get_db)
):
    """
    批量上传图片
    - 支持多图上传（最多100张）
    - 自动创建批次
    - 校验文件类型和大小
    """
    if len(files) > settings.MAX_BATCH_SIZE:
        raise HTTPException(status_code=400, detail=f"单次最多上传{settings.MAX_BATCH_SIZE}张图片")

    batch = Batch(name=batch_name, description=batch_description, total_images=0)
    db.add(batch)
    db.flush()

    uploaded, failed, skipped = [], [], []

    for file in files:
        try:
            if not file.filename:
                continue

            safe_name = sanitize_filename(file.filename)
            ext = Path(safe_name).suffix.lower()
            if ext not in settings.ALLOWED_EXTENSIONS:
                failed.append({"name": safe_name, "reason": "不支持的文件格式"})
                continue

            # 读取文件内容并检查大小
            content = await file.read()
            if len(content) > settings.MAX_UPLOAD_SIZE:
                failed.append({"name": safe_name, "reason": f"文件超过{settings.MAX_UPLOAD_SIZE // 1024 // 1024}MB"})
                continue

            if len(content) == 0:
                failed.append({"name": safe_name, "reason": "空文件"})
                continue

            file_id = str(uuid.uuid4())
            save_path = settings.UPLOAD_DIR / f"{file_id}{ext}"

            with open(save_path, "wb") as buffer:
                buffer.write(content)

            base_image = BaseImage(
                batch_id=batch.id,
                filename=safe_name,
                original_path=str(save_path),
                preprocess_mode="crop",
            )
            db.add(base_image)
            uploaded.append(safe_name)
        except Exception as e:
            logger.error(f"上传失败 {file.filename}: {e}")
            failed.append({"name": file.filename, "reason": str(e)})

    batch.total_images = len(uploaded)
    db.commit()

    return BaseResponse(
        code=0, message="上传完成",
        data={
            "batch_id": batch.id,
            "batch_name": batch.name,
            "uploaded_count": len(uploaded),
            "failed_count": len(failed),
            "failed_files": failed,
        }
    )


@router.get("/batches", response_model=BaseResponse)
async def list_batches(db: Session = Depends(get_db)):
    """获取所有批次列表（含图片统计）"""
    batches = db.query(Batch).order_by(Batch.create_time.desc()).all()
    result = []
    for b in batches:
        # 统计各状态图片数
        total = db.query(func.count(BaseImage.id)).filter(BaseImage.batch_id == b.id).scalar()
        pending = db.query(func.count(BaseImage.id)).filter(
            BaseImage.batch_id == b.id, BaseImage.status == "pending"
        ).scalar()
        completed = db.query(func.count(BaseImage.id)).filter(
            BaseImage.batch_id == b.id, BaseImage.status == "completed"
        ).scalar()
        failed = db.query(func.count(BaseImage.id)).filter(
            BaseImage.batch_id == b.id, BaseImage.status == "failed"
        ).scalar()

        result.append({
            "id": b.id,
            "name": b.name,
            "status": b.status,
            "total_images": total,
            "pending": pending,
            "completed": completed,
            "failed": failed,
            "create_time": b.create_time.isoformat() if b.create_time else None,
        })

    return BaseResponse(code=0, message="获取批次列表成功", data={"batches": result})


@router.get("/batch/{batch_id}", response_model=BaseResponse)
async def get_batch_detail(batch_id: str, db: Session = Depends(get_db)):
    """获取单个批次详情（含图片列表）"""
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在")

    images = db.query(BaseImage).filter(BaseImage.batch_id == batch_id).all()
    image_list = [{
        "id": img.id,
        "filename": img.filename,
        "status": img.status,
        "preprocess_mode": img.preprocess_mode,
        "watermark_removed": img.watermark_removed,
        "retry_count": img.retry_count,
        "original_path": img.original_path,
        "processed_path": img.processed_path,
    } for img in images]

    return BaseResponse(code=0, message="获取批次详情成功", data={
        "id": batch.id,
        "name": batch.name,
        "status": batch.status,
        "total_images": batch.total_images,
        "images": image_list,
    })


@router.post("/url", response_model=BaseResponse)
async def upload_from_url(
    url: str = Form(...),
    batch_id: str = Form(None),
    batch_name: str = Form(None),
    db: Session = Depends(get_db)
):
    """
    从URL导入图片
    - 支持直接图片链接
    - 自动检测文件类型
    """
    # SSRF 防护：校验 URL 安全性
    try:
        validate_url(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 获取或创建批次
    if batch_id:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            raise HTTPException(status_code=404, detail="批次不存在")
    else:
        batch = Batch(name=batch_name or "URL导入", total_images=0)
        db.add(batch)
        db.flush()

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()

            # 检测文件类型
            content_type = resp.headers.get("content-type", "")
            ext = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ""
            if ext == ".jpe":
                ext = ".jpg"

            if ext not in settings.ALLOWED_EXTENSIONS:
                return BaseResponse(code=1, message=f"不支持的文件类型: {content_type}")

            content = resp.content
            if len(content) > settings.MAX_UPLOAD_SIZE:
                return BaseResponse(code=1, message=f"文件超过{settings.MAX_UPLOAD_SIZE // 1024 // 1024}MB限制")

            # 保存文件
            file_id = str(uuid.uuid4())
            save_path = settings.UPLOAD_DIR / f"{file_id}{ext}"
            save_path.write_bytes(content)

            # 从URL提取文件名并清洗
            url_path = url.split("?")[0].split("#")[0]
            raw_name = Path(url_path).name or f"url_import{ext}"
            filename = sanitize_filename(raw_name)

            base_image = BaseImage(
                batch_id=batch.id,
                filename=filename,
                original_path=str(save_path),
                preprocess_mode="crop",
            )
            db.add(base_image)
            batch.total_images += 1
            db.commit()

            return BaseResponse(code=0, message="URL导入成功", data={
                "batch_id": batch.id,
                "filename": filename,
            })

    except httpx.HTTPStatusError as e:
        return BaseResponse(code=1, message=f"下载失败: HTTP {e.response.status_code}")
    except httpx.RequestError as e:
        return BaseResponse(code=1, message=f"网络请求失败: {str(e)}")
    except Exception as e:
        logger.error(f"URL导入失败: {e}")
        return BaseResponse(code=1, message=f"导入失败: {str(e)}")
