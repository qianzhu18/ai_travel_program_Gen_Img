"""
Export logic tests - source selection and extension handling
"""
from datetime import datetime
from pathlib import Path

from PIL import Image

from app.api import export as export_api
from app.models.database import Batch, BaseImage, GenerateTask, TemplateImage


def _make_image(path: Path, color: str, fmt: str):
    Image.new("RGB", (64, 64), color=color).save(path, format=fmt)


def _prepare_template(db_session, tmp_path):
    batch = Batch(name="export-batch", status="ongoing", total_images=1)
    db_session.add(batch)
    db_session.flush()

    base_img = BaseImage(
        batch_id=batch.id,
        filename="base.jpg",
        original_path=str(tmp_path / "base.jpg"),
        status="completed",
    )
    db_session.add(base_img)
    db_session.flush()

    gen_task = GenerateTask(
        base_image_id=base_img.id,
        crowd_type="C01",
        style_name="s1",
        ai_engine="seedream",
        status="completed",
    )
    db_session.add(gen_task)
    db_session.flush()

    original = tmp_path / "tpl_original.png"
    compressed = tmp_path / "tpl_compressed.jpg"
    _make_image(original, "red", "PNG")
    _make_image(compressed, "blue", "JPEG")

    tmpl = TemplateImage(
        generate_task_id=gen_task.id,
        crowd_type="C01",
        style_name="s1",
        original_path=str(original),
        compressed_path=str(compressed),
        final_status="selected",
    )
    db_session.add(tmpl)
    db_session.commit()
    return original, compressed


def test_sync_export_prefers_original_when_compress_disabled(db_session, tmp_path, monkeypatch):
    original, _ = _prepare_template(db_session, tmp_path)
    export_root = tmp_path / "export_out"

    monkeypatch.setattr(export_api.ps, "init", lambda *args, **kwargs: None)
    monkeypatch.setattr(export_api.ps, "finish", lambda *args, **kwargs: None)
    monkeypatch.setattr(export_api, "_update_progress", lambda *args, **kwargs: None)

    export_api._sync_export(db_session, str(export_root), use_compressed=False)

    date_dir = datetime.now().strftime("%Y%m%d")
    out_dir = export_root / date_dir / "C01_幼女"
    exported = list(out_dir.glob("*.png"))
    assert len(exported) == 1
    assert exported[0].read_bytes() == original.read_bytes()


def test_sync_export_prefers_compressed_when_enabled(db_session, tmp_path, monkeypatch):
    _, compressed = _prepare_template(db_session, tmp_path)
    export_root = tmp_path / "export_out2"

    monkeypatch.setattr(export_api.ps, "init", lambda *args, **kwargs: None)
    monkeypatch.setattr(export_api.ps, "finish", lambda *args, **kwargs: None)
    monkeypatch.setattr(export_api, "_update_progress", lambda *args, **kwargs: None)

    export_api._sync_export(db_session, str(export_root), use_compressed=True)

    date_dir = datetime.now().strftime("%Y%m%d")
    out_dir = export_root / date_dir / "C01_幼女"
    exported = list(out_dir.glob("*.jpg"))
    assert len(exported) == 1
    assert exported[0].read_bytes() == compressed.read_bytes()
