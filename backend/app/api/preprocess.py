"""
预处理API路由 - 水印去除 + 尺寸标准化(9:16)
支持异步后台处理 + 进度轮询
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pathlib import Path
import asyncio
import threading
import logging

from app.core.database import get_db, SessionLocal
from app.core.config import settings
from app.core.settings_resolver import get_setting_value
from app.schemas.common import PreprocessRequest, WatermarkMarkRequest, BaseResponse
from app.models.database import BaseImage, Batch
from app.services import progress_store as ps

logger = logging.getLogger(__name__)
router = APIRouter()

TASK_TYPE = "preprocess"


def _region_name_to_key(region_name: str) -> str:
    """将中文区域名转为英文key"""
    mapping = {
        "右下角": "bottom_right",
        "左下角": "bottom_left",
        "右上角": "top_right",
        "左上角": "top_left",
        "全图检测": "full_scan",
    }
    return mapping.get(region_name, "bottom_right")


def _normalize_expand_engine(engine_name: str) -> str:
    """规范化扩图引擎配置。"""
    engine = (engine_name or "seedream").lower().strip()
    if engine in ("seedream", "iopaint", "auto"):
        return engine
    if engine == "nanobanana":
        logger.warning("扩图引擎 nanobanana 未支持 outpainting，已回退为 seedream")
        return "seedream"
    logger.warning(f"未知扩图引擎: {engine_name}，已回退为 auto")
    return "auto"


def _normalize_watermark_engine(engine_name: str) -> str:
    """规范化去水印引擎配置。"""
    engine = (engine_name or "auto").lower().strip()
    alias = {
        "volcengine": "volc",
        "volcano": "volc",
        "local": "iopaint",
    }
    engine = alias.get(engine, engine)
    if engine in ("auto", "iopaint", "volc"):
        return engine
    logger.warning(f"未知去水印引擎: {engine_name}，已回退为 auto")
    return "auto"


def _run_preprocess_background(
    batch_id: str,
    mode: str,
    crop_offsets: dict = None,
    image_modes: dict = None,
    expand_offsets: dict = None,
):
    """在后台线程中运行预处理"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(
            _async_preprocess(
                batch_id,
                mode,
                crop_offsets,
                image_modes,
                expand_offsets,
            )
        )
    finally:
        loop.close()


async def _async_preprocess(
    batch_id: str,
    mode: str,
    crop_offsets: dict = None,
    image_modes: dict = None,
    expand_offsets: dict = None,
):
    """异步预处理核心逻辑"""
    db = SessionLocal()
    try:
        # 读取系统配置
        region_name = get_setting_value(db, "watermark_region", "右下角")
        margin_str = get_setting_value(db, "watermark_margin", "15")
        watermark_engine = _normalize_watermark_engine(
            get_setting_value(db, "watermark_engine", "auto")
        )
        expand_engine = _normalize_expand_engine(
            get_setting_value(db, "expand_engine", "seedream")
        )
        expand_allow_fallback = (
            str(get_setting_value(db, "expand_allow_fallback", "1")).strip() == "1"
        )
        apiyi_api_key = get_setting_value(db, "apiyi_api_key", "") or settings.APIYI_API_KEY
        volc_access_key_id = get_setting_value(db, "volc_access_key_id", "") or settings.VOLC_ACCESS_KEY_ID
        volc_secret_access_key = get_setting_value(db, "volc_secret_access_key", "") or settings.VOLC_SECRET_ACCESS_KEY
        region = _region_name_to_key(region_name)
        margin_ratio = int(margin_str) / 100.0

        # 查询待处理图片
        images = db.query(BaseImage).filter(
            BaseImage.batch_id == batch_id,
            BaseImage.status.in_(["pending", "failed"])
        ).all()

        if not images:
            ps.finish(TASK_TYPE, batch_id, 0, 0, "没有待处理的图片")
            return

        total = len(images)
        ps.init(TASK_TYPE, batch_id, total, f"开始预处理，共 {total} 张图片...")

        # 标记所有图片为 processing
        for img in images:
            img.status = "processing"
        db.commit()

        from app.services.image_cropper import crop_to_target_ratio  # Pillow，始终可用

        # cv2 依赖模块，可能不可用（Python 3.14 下 opencv-python 未安装）
        remover = None
        expand_available = False
        try:
            from app.services.watermark_remover import WatermarkRemover
            remover = WatermarkRemover(
                engine=watermark_engine,
                volc_access_key_id=volc_access_key_id,
                volc_secret_access_key=volc_secret_access_key,
                volc_region=settings.VOLC_REGION,
                volc_service=settings.VOLC_SERVICE,
            )
        except (ImportError, Exception) as e:
            logger.warning(f"水印去除模块不可用: {e}")
            ps.append_log(TASK_TYPE, batch_id, f"[WARN] 水印去除模块不可用: {e}")

        try:
            from app.services.image_expander import expand_to_target_ratio
            expand_available = True
        except (ImportError, Exception) as e:
            logger.warning(f"AI扩图模块不可用: {e}")

        completed_count = 0
        failed_count = 0

        # 先检测水印去除引擎是否可用
        watermark_available = False
        if remover:
            watermark_available = await remover.health_check()
        if not watermark_available:
            logger.warning(f"水印去除服务不可用（engine={watermark_engine}），将跳过水印去除步骤")
            ps.append_log(
                TASK_TYPE,
                batch_id,
                f"[WARN] 水印去除服务不可用（engine={watermark_engine}），跳过去水印",
            )

        for i, img in enumerate(images):
            try:
                output_path = str(settings.PROCESSED_DIR / Path(img.original_path).name)
                current_input = img.original_path

                # 确定该图的处理模式：image_modes > 批次默认 mode
                img_mode = mode
                if image_modes and img.id in image_modes:
                    img_mode = image_modes[img.id]
                logger.info(f"[{img.filename}] 处理模式: {img_mode} (批次默认: {mode}, image_modes中: {img.id in (image_modes or {})})")
                # 持久化到 DB
                img.preprocess_mode = img_mode

                # Step 1: 水印去除 (可选，IOPaint 不可用或 remover 未加载时跳过)
                if remover and watermark_available:
                    detection_mode = "full_scan" if region == "full_scan" else "auto"
                    wm_success = await remover.process_image(
                        input_path=current_input,
                        output_path=output_path,
                        region=region,
                        margin_ratio=margin_ratio,
                    )
                    if wm_success:
                        current_input = output_path
                        img.watermark_removed = True
                    else:
                        logger.warning(f"水印去除失败，继续处理: {img.filename}")

                # Step 2: 尺寸标准化 (9:16) — 按每张图的模式处理
                if img_mode == "crop":
                    # 使用每张图的自定义偏移量，默认居中
                    img_offset = 0.0
                    if crop_offsets and img.id in crop_offsets:
                        img_offset = float(crop_offsets[img.id])
                    crop_success = crop_to_target_ratio(
                        input_path=current_input,
                        output_path=output_path,
                        target_ratio=(9, 16),
                        offset=img_offset,
                    )
                    if not crop_success:
                        raise Exception("9:16 裁剪失败")
                elif img_mode == "expand":
                    if not expand_available:
                        raise Exception("AI扩图模块不可用")

                    # Seedream 未配置密钥时自动回退，避免整批次直接失败
                    engine_for_image = expand_engine
                    if engine_for_image == "seedream" and not apiyi_api_key:
                        engine_for_image = "auto"
                        ps.append_log(
                            TASK_TYPE,
                            batch_id,
                            "[WARN] 未配置 API Key，扩图引擎自动回退为 auto",
                        )

                    img_offset = 0.0
                    if expand_offsets and img.id in expand_offsets:
                        img_offset = float(expand_offsets[img.id])

                    expand_success = await expand_to_target_ratio(
                        input_path=current_input,
                        output_path=output_path,
                        target_ratio=(9, 16),
                        engine=engine_for_image,
                        apiyi_api_key=apiyi_api_key,
                        offset=img_offset,
                        allow_fallback=expand_allow_fallback,
                    )
                    if not expand_success:
                        raise Exception("AI扩图失败")

                img.status = "completed"
                img.processed_path = output_path
                completed_count += 1

                ps.append_log(TASK_TYPE, batch_id, f"[OK] {img.filename}")

            except Exception as e:
                logger.error(f"预处理失败 {img.filename}: {e}")
                img.status = "failed"
                img.retry_count += 1
                failed_count += 1

                # 重试3次后自动进入回收站
                if img.retry_count >= 3:
                    img.status = "discarded"
                    ps.append_log(TASK_TYPE, batch_id,
                                  f"[TRASH] {img.filename} 多次失败，已移入回收站")
                else:
                    ps.append_log(TASK_TYPE, batch_id,
                                  f"[FAIL] {img.filename} (第{img.retry_count}次)")

            db.commit()

            # 更新进度
            progress = int((i + 1) / total * 100)
            ps.update(TASK_TYPE, batch_id,
                      progress=progress, completed=completed_count, failed=failed_count)

        if remover:
            await remover.close()

        # 更新批次状态
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if batch:
            remaining = db.query(BaseImage).filter(
                BaseImage.batch_id == batch_id,
                BaseImage.status == "pending"
            ).count()
            if remaining == 0:
                batch.status = "completed" if failed_count == 0 else "ongoing"
            db.commit()

        ps.finish(TASK_TYPE, batch_id, completed_count, failed_count,
                  f"预处理完成！成功 {completed_count} 张，失败 {failed_count} 张")

    except Exception as e:
        logger.error(f"预处理批次失败 {batch_id}: {e}")
        ps.fail(TASK_TYPE, batch_id, f"预处理出错: {str(e)}")
    finally:
        db.close()


@router.post("/start", response_model=BaseResponse)
async def start_preprocess(request: PreprocessRequest, db: Session = Depends(get_db)):
    """
    开始批量预处理（异步后台任务）
    - 水印去除 (IOPaint LaMa)
    - 尺寸标准化 (9:16)
    """
    batch = db.query(Batch).filter(Batch.id == request.batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="批次不存在")

    # 检查是否已在运行
    if ps.is_running(TASK_TYPE, request.batch_id):
        return BaseResponse(code=1, message="该批次正在处理中")

    pending = db.query(BaseImage).filter(
        BaseImage.batch_id == request.batch_id,
        BaseImage.status.in_(["pending", "failed"])
    ).count()

    if pending == 0:
        return BaseResponse(code=1, message="没有待处理的图片")

    # 启动后台线程
    t = threading.Thread(
        target=_run_preprocess_background,
        args=(
            request.batch_id,
            request.mode,
            request.crop_offsets,
            request.image_modes,
            request.expand_offsets,
        ),
        daemon=True
    )
    t.start()

    return BaseResponse(code=0, message="预处理已启动", data={
        "batch_id": request.batch_id,
        "pending_count": pending,
    })


@router.get("/progress/{batch_id}", response_model=BaseResponse)
async def get_preprocess_progress(batch_id: str):
    """查询预处理进度"""
    data = ps.get(TASK_TYPE, batch_id)
    return BaseResponse(code=0, message="获取进度成功", data=data)


@router.post("/watermark/manual", response_model=BaseResponse)
async def manual_watermark_mark(request: WatermarkMarkRequest, db: Session = Depends(get_db)):
    """
    手动涂抹标记水印区域并AI消除
    前端通过画笔工具生成涂抹蒙版（mask），传入Base64编码的蒙版图片
    """
    image = db.query(BaseImage).filter(BaseImage.id == request.image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")

    try:
        from app.services.watermark_remover import WatermarkRemover
        output_path = str(settings.PROCESSED_DIR / Path(image.original_path).name)
        input_path = image.processed_path or image.original_path

        watermark_engine = _normalize_watermark_engine(
            get_setting_value(db, "watermark_engine", "auto")
        )
        volc_access_key_id = get_setting_value(db, "volc_access_key_id", "") or settings.VOLC_ACCESS_KEY_ID
        volc_secret_access_key = get_setting_value(db, "volc_secret_access_key", "") or settings.VOLC_SECRET_ACCESS_KEY

        if (
            watermark_engine == "volc"
            and (not volc_access_key_id or not volc_secret_access_key)
        ):
            return BaseResponse(code=1, message="当前去水印引擎为火山视觉，但AK/SK未配置")

        remover = WatermarkRemover(
            engine=watermark_engine,
            volc_access_key_id=volc_access_key_id,
            volc_secret_access_key=volc_secret_access_key,
            volc_region=settings.VOLC_REGION,
            volc_service=settings.VOLC_SERVICE,
        )
        try:
            if not await remover.health_check():
                if watermark_engine in ("iopaint", "auto"):
                    return BaseResponse(code=1, message="IOPaint 服务不可用，请先启动本地服务")
                return BaseResponse(code=1, message="去水印服务不可用，请检查配置")

            success = await remover.process_image(
                input_path=input_path,
                output_path=output_path,
                mask_data=request.mask_data
            )
        finally:
            await remover.close()

        if success:
            image.status = "completed"
            image.watermark_removed = True
            image.processed_path = output_path
            db.commit()
            return BaseResponse(code=0, message="水印去除成功")
        else:
            return BaseResponse(code=1, message="水印去除失败")

    except Exception as e:
        logger.error(f"手动水印去除失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retry/{image_id}", response_model=BaseResponse)
async def retry_preprocess(image_id: str, db: Session = Depends(get_db)):
    """重试失败的预处理（3次失败后自动进入回收站）"""
    image = db.query(BaseImage).filter(BaseImage.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")

    if image.status == "discarded":
        return BaseResponse(code=1, message="该图片已被移入回收站（重试次数已达上限）")

    if image.retry_count >= 3:
        image.status = "discarded"
        db.commit()
        return BaseResponse(code=1, message="重试次数已达上限，已移入回收站")

    try:
        from app.services.watermark_remover import WatermarkRemover
        from app.services.image_cropper import crop_to_target_ratio
        from app.services.image_expander import expand_to_target_ratio

        output_path = str(settings.PROCESSED_DIR / Path(image.original_path).name)
        input_path = image.original_path

        # 读取系统配置
        region_name = get_setting_value(db, "watermark_region", "右下角")
        margin_str = get_setting_value(db, "watermark_margin", "15")
        watermark_engine = _normalize_watermark_engine(
            get_setting_value(db, "watermark_engine", "auto")
        )
        expand_engine = _normalize_expand_engine(
            get_setting_value(db, "expand_engine", "seedream")
        )
        expand_allow_fallback = (
            str(get_setting_value(db, "expand_allow_fallback", "1")).strip() == "1"
        )
        apiyi_api_key = get_setting_value(db, "apiyi_api_key", "") or settings.APIYI_API_KEY
        region = _region_name_to_key(region_name)
        margin_ratio = int(margin_str) / 100.0

        volc_access_key_id = get_setting_value(db, "volc_access_key_id", "") or settings.VOLC_ACCESS_KEY_ID
        volc_secret_access_key = get_setting_value(db, "volc_secret_access_key", "") or settings.VOLC_SECRET_ACCESS_KEY

        remover = WatermarkRemover(
            engine=watermark_engine,
            volc_access_key_id=volc_access_key_id,
            volc_secret_access_key=volc_secret_access_key,
            volc_region=settings.VOLC_REGION,
            volc_service=settings.VOLC_SERVICE,
        )
        try:
            watermark_available = await remover.health_check()
            if watermark_available:
                wm_success = await remover.process_image(
                    input_path=input_path,
                    output_path=output_path,
                    region=region,
                    margin_ratio=margin_ratio,
                )
                if wm_success:
                    input_path = output_path
                    image.watermark_removed = True
            else:
                logger.warning(f"重试时去水印引擎不可用（engine={watermark_engine}），跳过去水印")
        finally:
            await remover.close()

        preprocess_mode = (image.preprocess_mode or "crop").lower().strip()
        if preprocess_mode not in ("crop", "expand"):
            preprocess_mode = "crop"

        if preprocess_mode == "crop":
            ok = crop_to_target_ratio(
                input_path=input_path,
                output_path=output_path,
                target_ratio=(9, 16),
                offset=0.0,
            )
        else:
            engine_for_image = expand_engine
            if engine_for_image == "seedream" and not apiyi_api_key:
                engine_for_image = "auto"
                logger.warning("重试扩图时未配置API Key，扩图引擎自动回退为 auto")

            ok = await expand_to_target_ratio(
                input_path=input_path,
                output_path=output_path,
                target_ratio=(9, 16),
                engine=engine_for_image,
                apiyi_api_key=apiyi_api_key,
                offset=0.0,
                allow_fallback=expand_allow_fallback,
            )

        if ok:
            image.status = "completed"
            image.processed_path = output_path
        else:
            image.retry_count += 1
            if image.retry_count >= 3:
                image.status = "discarded"
            else:
                image.status = "failed"

        db.commit()

        if ok:
            return BaseResponse(code=0, message="重试成功")
        elif image.status == "discarded":
            return BaseResponse(code=1, message="重试失败，已移入回收站")
        else:
            return BaseResponse(code=1, message=f"重试失败（第{image.retry_count}次）")

    except Exception as e:
        logger.error(f"重试失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
