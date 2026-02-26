"""
图片审核API路由
- 审核列表查询（支持批次、人群、状态筛选）
- 单张/批量审核标记
- 审核统计
- 生成图片文件服务
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from pathlib import Path
from typing import Optional
import logging

from app.core.database import get_db
from app.core.constants import CROWD_TYPES
from app.schemas.common import ReviewMarkRequest, ReviewBatchMarkRequest, BaseResponse
from app.models.database import GenerateTask, BaseImage, TemplateImage

logger = logging.getLogger(__name__)
router = APIRouter()

# review_status -> TemplateImage.final_status 映射
_STATUS_MAP = {
    "selected": "selected",
    "pending_modification": "pending_modification",
    "not_selected": "trash",
}


@router.get("/list", response_model=BaseResponse)
async def list_review_images(
    batch_id: Optional[str] = Query(None),
    crowd_type: Optional[str] = Query(None),
    review_status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """获取审核图片列表（支持筛选+分页）"""
    query = db.query(GenerateTask).join(BaseImage)

    # 只查已完成生图的任务
    query = query.filter(GenerateTask.status == "completed")

    if batch_id:
        query = query.filter(BaseImage.batch_id == batch_id)
    if crowd_type:
        query = query.filter(GenerateTask.crowd_type == crowd_type)
    if review_status:
        query = query.filter(GenerateTask.review_status == review_status)

    total = query.count()
    tasks = (
        query.order_by(GenerateTask.create_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for t in tasks:
        img = db.query(BaseImage).filter(BaseImage.id == t.base_image_id).first()
        items.append({
            "id": t.id,
            "crowd_type": t.crowd_type,
            "crowd_name": CROWD_TYPES.get(t.crowd_type, t.crowd_type),
            "style_name": t.style_name,
            "review_status": t.review_status,
            "result_path": t.result_path,
            "base_image_filename": img.filename if img else "",
            "batch_id": img.batch_id if img else "",
            "create_time": t.create_time.isoformat() if t.create_time else "",
        })

    return BaseResponse(code=0, data={
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@router.post("/mark", response_model=BaseResponse)
async def mark_review(request: ReviewMarkRequest, db: Session = Depends(get_db)):
    """标记单张图片审核状态"""
    task = db.query(GenerateTask).filter(GenerateTask.id == request.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if request.status not in _STATUS_MAP:
        raise HTTPException(status_code=400, detail=f"无效状态: {request.status}")

    task.review_status = request.status

    # 同步更新 TemplateImage
    tpl = db.query(TemplateImage).filter(
        TemplateImage.generate_task_id == task.id
    ).first()
    if tpl:
        tpl.final_status = _STATUS_MAP[request.status]

    db.commit()

    status_name = {"selected": "选用", "pending_modification": "待修改", "not_selected": "不选用"}
    return BaseResponse(
        code=0,
        message=f"已标记为「{status_name.get(request.status, request.status)}」",
    )


@router.post("/batch-mark", response_model=BaseResponse)
async def batch_mark_review(request: ReviewBatchMarkRequest, db: Session = Depends(get_db)):
    """批量标记审核状态"""
    if request.status not in _STATUS_MAP:
        raise HTTPException(status_code=400, detail=f"无效状态: {request.status}")

    updated = 0
    for task_id in request.task_ids:
        task = db.query(GenerateTask).filter(GenerateTask.id == task_id).first()
        if not task:
            continue
        task.review_status = request.status

        tpl = db.query(TemplateImage).filter(
            TemplateImage.generate_task_id == task.id
        ).first()
        if tpl:
            tpl.final_status = _STATUS_MAP[request.status]

        updated += 1

    db.commit()

    return BaseResponse(code=0, message=f"已批量标记 {updated} 张图片", data={
        "updated_count": updated,
    })


@router.get("/stats", response_model=BaseResponse)
async def review_stats(
    batch_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """获取审核统计数据"""
    base_query = db.query(GenerateTask).join(BaseImage).filter(
        GenerateTask.status == "completed",
    )
    if batch_id:
        base_query = base_query.filter(BaseImage.batch_id == batch_id)

    total = base_query.count()
    pending = base_query.filter(GenerateTask.review_status == "pending_review").count()
    selected = base_query.filter(GenerateTask.review_status == "selected").count()
    pending_mod = base_query.filter(GenerateTask.review_status == "pending_modification").count()
    not_selected = base_query.filter(GenerateTask.review_status == "not_selected").count()

    return BaseResponse(code=0, data={
        "total": total,
        "pending_review": pending,
        "selected": selected,
        "pending_modification": pending_mod,
        "not_selected": not_selected,
    })


@router.get("/image/{task_id}")
async def serve_image(task_id: str, db: Session = Depends(get_db)):
    """提供生成图片的文件访问"""
    task = db.query(GenerateTask).filter(GenerateTask.id == task_id).first()
    if not task or not task.result_path:
        raise HTTPException(status_code=404, detail="图片不存在")

    file_path = Path(task.result_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="图片文件未找到")

    return FileResponse(
        str(file_path),
        media_type="image/jpeg",
        filename=f"{task.crowd_type}_{task.style_name}.jpg",
    )
