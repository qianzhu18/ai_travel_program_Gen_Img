"""
批量导出API路由
- 将选用库图片按 日期/人群类型 目录结构导出到本地
- 后台异步执行 + 进度轮询
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pathlib import Path
from datetime import datetime
import shutil
import threading
import logging

from app.core.database import get_db, SessionLocal
from app.core.config import settings
from app.core.settings_resolver import get_setting_value
from app.core.constants import CROWD_TYPES
from app.core.security import validate_export_dir
from app.schemas.common import ExportRequest, BaseResponse
from app.models.database import TemplateImage
from app.services import progress_store as ps

logger = logging.getLogger(__name__)
router = APIRouter()

TASK_TYPE = "export"
TASK_KEY = "current"


def _run_export_background(export_dir: str):
    """后台线程入口"""
    db = SessionLocal()
    try:
        compress_enabled = get_setting_value(db, "compress_enabled", "1")
        use_compressed = str(compress_enabled).strip() == "1"
        _sync_export(db, export_dir, use_compressed=use_compressed)
    except Exception as e:
        logger.error(f"导出任务异常: {e}")
        ps.fail(TASK_TYPE, TASK_KEY, f"导出出错: {str(e)}")
    finally:
        db.close()


def _sync_export(db: Session, export_dir: str, use_compressed: bool = True):
    """同步导出核心逻辑"""
    # 查询所有选用状态的模板图
    templates = db.query(TemplateImage).filter(
        TemplateImage.final_status == "selected",
    ).all()

    if not templates:
        ps.finish(TASK_TYPE, TASK_KEY, 0, 0, "没有需要导出的图片")
        return

    total = len(templates)
    date_str = datetime.now().strftime("%Y%m%d")
    base_dir = Path(export_dir) / date_str

    source_mode = "压缩图优先" if use_compressed else "原图优先"
    ps.init(
        TASK_TYPE,
        TASK_KEY,
        total,
        f"开始导出: {total} 张图片 → {base_dir} ({source_mode})",
    )

    completed = 0
    failed = 0

    for tmpl in templates:
        crowd_name = CROWD_TYPES.get(tmpl.crowd_type, tmpl.crowd_type)
        type_dir = base_dir / f"{tmpl.crowd_type}_{crowd_name}"
        type_dir.mkdir(parents=True, exist_ok=True)

        # 根据配置选择导出来源
        src_path = (
            (tmpl.compressed_path if use_compressed else None)
            or tmpl.original_path
        )
        if not src_path or not Path(src_path).exists():
            failed += 1
            _update_progress(total, completed, failed, f"[FAIL] 源文件不存在: {tmpl.id[:8]}")
            continue

        # 生成导出文件名
        src_ext = Path(src_path).suffix or ".jpg"
        dst_name = f"{tmpl.crowd_type}_{tmpl.style_name}_{tmpl.id[:8]}{src_ext}"
        dst_path = type_dir / dst_name

        try:
            shutil.copy2(src_path, dst_path)
            completed += 1
            _update_progress(total, completed, failed, f"[OK] {crowd_name}/{dst_name}")
        except Exception as e:
            failed += 1
            logger.error(f"导出文件失败 {src_path}: {e}")
            _update_progress(total, completed, failed, f"[FAIL] {crowd_name}/{dst_name}")

        # 导出宽脸版（如果有）
        wf_src = (
            (tmpl.compressed_wide_face_path if use_compressed else None)
            or tmpl.wide_face_path
        )
        if wf_src and Path(wf_src).exists():
            wf_ext = Path(wf_src).suffix or ".jpg"
            wf_dst_name = f"{tmpl.crowd_type}_{tmpl.style_name}_{tmpl.id[:8]}_wide{wf_ext}"
            wf_dst_path = type_dir / wf_dst_name
            try:
                shutil.copy2(wf_src, wf_dst_path)
            except Exception as e:
                logger.warning(f"导出宽脸图失败 {wf_src}: {e}")

    ps.finish(TASK_TYPE, TASK_KEY, completed, failed,
              f"导出完成！成功 {completed} 张，失败 {failed} 张 → {base_dir}")


def _update_progress(total: int, completed: int, failed: int, log_msg: str):
    done = completed + failed
    progress = int(done / total * 100) if total > 0 else 0
    current = ps.get(TASK_TYPE, TASK_KEY)
    current.update({
        "progress": progress,
        "completed": completed,
        "failed": failed,
    })
    logs = current.get("logs", [])
    logs.append(log_msg)
    current["logs"] = logs
    ps.set(TASK_TYPE, TASK_KEY, current)


@router.post("/start", response_model=BaseResponse)
async def start_export(request: ExportRequest, db: Session = Depends(get_db)):
    """批量导出选用库图片到本地（按日期+人群类型平铺）"""
    if ps.is_running(TASK_TYPE, TASK_KEY):
        return BaseResponse(code=1, message="导出任务正在进行中")

    export_dir = request.export_dir or get_setting_value(
        db, "export_default_dir", ""
    ) or str(settings.DEFAULT_EXPORT_DIR)

    # 路径穿越防护
    try:
        validated_path = validate_export_dir(export_dir)
        export_dir = str(validated_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 确保导出目录可写
    try:
        Path(export_dir).mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"导出目录无法创建: {e}")

    t = threading.Thread(
        target=_run_export_background,
        args=(export_dir,),
        daemon=True,
    )
    t.start()

    return BaseResponse(code=0, message="导出任务已启动", data={
        "export_dir": export_dir,
    })


@router.get("/progress", response_model=BaseResponse)
async def get_export_progress():
    """获取导出进度"""
    data = ps.get(TASK_TYPE, TASK_KEY)
    return BaseResponse(code=0, data=data)
