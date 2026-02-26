"""
模板管理API路由
- 模板图列表（三库视图：选用库/待修改库/回收站）
- 模板图库间移动
- 模板图删除
- 模板图统计
- 模板图文件服务
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from pathlib import Path
from typing import Optional, List
import logging

from app.core.database import get_db
from app.core.constants import CROWD_TYPES
from app.schemas.common import TemplateMoveRequest, BaseResponse
from app.models.database import TemplateImage, GenerateTask

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/list", response_model=BaseResponse)
async def list_templates(
    crowd_type: Optional[str] = Query(None),
    final_status: Optional[str] = Query("selected", description="selected/pending_modification/trash"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """获取模板图列表（按人群类型+库筛选）"""
    query = db.query(TemplateImage)

    if crowd_type:
        query = query.filter(TemplateImage.crowd_type == crowd_type)
    if final_status:
        query = query.filter(TemplateImage.final_status == final_status)

    total = query.count()
    templates = (
        query.order_by(TemplateImage.crowd_type, TemplateImage.style_name)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for t in templates:
        items.append({
            "id": t.id,
            "generate_task_id": t.generate_task_id,
            "crowd_type": t.crowd_type,
            "crowd_name": CROWD_TYPES.get(t.crowd_type, t.crowd_type),
            "style_name": t.style_name,
            "original_path": t.original_path,
            "wide_face_path": t.wide_face_path,
            "wide_face_status": t.wide_face_status,
            "compress_status": t.compress_status,
            "compressed_path": t.compressed_path,
            "final_status": t.final_status,
            "create_time": t.create_time.isoformat() if t.create_time else "",
        })

    return BaseResponse(code=0, data={
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@router.post("/move", response_model=BaseResponse)
async def move_template(request: TemplateMoveRequest, db: Session = Depends(get_db)):
    """移动模板图到指定库"""
    valid_targets = ("selected", "pending_modification", "trash")
    if request.target not in valid_targets:
        raise HTTPException(status_code=400, detail=f"无效目标库: {request.target}")

    tpl = db.query(TemplateImage).filter(TemplateImage.id == request.template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板图不存在")

    old_status = tpl.final_status
    tpl.final_status = request.target

    # 同步更新 GenerateTask 的 review_status
    if tpl.generate_task_id:
        task = db.query(GenerateTask).filter(GenerateTask.id == tpl.generate_task_id).first()
        if task:
            status_map = {
                "selected": "selected",
                "pending_modification": "pending_modification",
                "trash": "not_selected",
            }
            task.review_status = status_map[request.target]

    db.commit()

    target_names = {"selected": "选用库", "pending_modification": "待修改库", "trash": "回收站"}
    return BaseResponse(
        code=0,
        message=f"已移动到「{target_names[request.target]}」",
    )


@router.post("/batch-move", response_model=BaseResponse)
async def batch_move_templates(
    template_ids: List[str],
    target: str,
    db: Session = Depends(get_db),
):
    """批量移动模板图"""
    valid_targets = ("selected", "pending_modification", "trash")
    if target not in valid_targets:
        raise HTTPException(status_code=400, detail=f"无效目标库: {target}")

    status_map = {
        "selected": "selected",
        "pending_modification": "pending_modification",
        "trash": "not_selected",
    }

    updated = 0
    for tid in template_ids:
        tpl = db.query(TemplateImage).filter(TemplateImage.id == tid).first()
        if not tpl:
            continue
        tpl.final_status = target

        if tpl.generate_task_id:
            task = db.query(GenerateTask).filter(GenerateTask.id == tpl.generate_task_id).first()
            if task:
                task.review_status = status_map[target]

        updated += 1

    db.commit()

    target_names = {"selected": "选用库", "pending_modification": "待修改库", "trash": "回收站"}
    return BaseResponse(
        code=0,
        message=f"已批量移动 {updated} 张到「{target_names[target]}」",
        data={"updated_count": updated},
    )


@router.delete("/delete/{template_id}", response_model=BaseResponse)
async def delete_template(template_id: str, db: Session = Depends(get_db)):
    """永久删除模板图（仅回收站中的可删除）"""
    tpl = db.query(TemplateImage).filter(TemplateImage.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板图不存在")

    if tpl.final_status != "trash":
        raise HTTPException(status_code=400, detail="只能删除回收站中的模板图")

    db.delete(tpl)
    db.commit()

    return BaseResponse(code=0, message="已永久删除")


@router.get("/stats", response_model=BaseResponse)
async def template_stats(
    crowd_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """获取模板图统计数据"""
    base_query = db.query(TemplateImage)
    if crowd_type:
        base_query = base_query.filter(TemplateImage.crowd_type == crowd_type)

    total = base_query.count()
    selected = base_query.filter(TemplateImage.final_status == "selected").count()
    pending_mod = base_query.filter(TemplateImage.final_status == "pending_modification").count()
    trash = base_query.filter(TemplateImage.final_status == "trash").count()

    # 按人群类型分组统计（仅选用库）
    crowd_stats = {}
    for ct_id, ct_name in CROWD_TYPES.items():
        count = db.query(TemplateImage).filter(
            TemplateImage.crowd_type == ct_id,
            TemplateImage.final_status == "selected",
        ).count()
        if count > 0:
            crowd_stats[ct_id] = {"name": ct_name, "count": count}

    return BaseResponse(code=0, data={
        "total": total,
        "selected": selected,
        "pending_modification": pending_mod,
        "trash": trash,
        "crowd_stats": crowd_stats,
    })


@router.get("/image/{template_id}")
async def serve_template_image(template_id: str, db: Session = Depends(get_db)):
    """提供模板图文件访问"""
    tpl = db.query(TemplateImage).filter(TemplateImage.id == template_id).first()
    if not tpl:
        raise HTTPException(status_code=404, detail="模板图不存在")

    # 优先返回压缩版，其次原图
    image_path = tpl.compressed_path or tpl.original_path
    if not image_path:
        raise HTTPException(status_code=404, detail="图片路径为空")

    file_path = Path(image_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="图片文件未找到")

    return FileResponse(
        str(file_path),
        media_type="image/jpeg",
        filename=f"{tpl.crowd_type}_{tpl.style_name}.jpg",
    )
