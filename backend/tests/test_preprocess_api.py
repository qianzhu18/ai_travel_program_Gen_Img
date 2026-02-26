"""
Preprocess API tests - manual watermark + retry behavior
"""
import base64
from io import BytesIO

from PIL import Image

from app.models.database import Batch, BaseImage, Settings


def _make_image(path):
    Image.new("RGB", (320, 240), color="white").save(path, format="JPEG")


def _make_mask_data():
    buf = BytesIO()
    Image.new("RGB", (64, 64), color="red").save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")


def test_manual_watermark_uses_local_engine_without_aksk(
    client,
    db_session,
    tmp_path,
    monkeypatch,
):
    image_path = tmp_path / "manual_input.jpg"
    _make_image(image_path)

    batch = Batch(name="b1", status="ongoing", total_images=1)
    db_session.add(batch)
    db_session.flush()

    img = BaseImage(
        batch_id=batch.id,
        filename="manual_input.jpg",
        original_path=str(image_path),
        status="completed",
    )
    db_session.add(img)
    db_session.add(Settings(key="watermark_engine", value="iopaint"))
    db_session.commit()

    class DummyRemover:
        def __init__(self, *args, **kwargs):
            pass

        async def health_check(self):
            return True

        async def process_image(self, *args, **kwargs):
            return True

        async def close(self):
            return None

    monkeypatch.setattr("app.services.watermark_remover.WatermarkRemover", DummyRemover)

    resp = client.post(
        "/api/preprocess/watermark/manual",
        json={"image_id": img.id, "mask_data": _make_mask_data()},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0


def test_retry_preprocess_expand_mode_calls_expand_flow(
    client,
    db_session,
    tmp_path,
    monkeypatch,
):
    image_path = tmp_path / "retry_expand.jpg"
    _make_image(image_path)

    batch = Batch(name="b2", status="ongoing", total_images=1)
    db_session.add(batch)
    db_session.flush()

    img = BaseImage(
        batch_id=batch.id,
        filename="retry_expand.jpg",
        original_path=str(image_path),
        status="failed",
        preprocess_mode="expand",
        retry_count=0,
    )
    db_session.add(img)
    db_session.add(Settings(key="watermark_engine", value="iopaint"))
    db_session.add(Settings(key="expand_engine", value="iopaint"))
    db_session.commit()

    class DummyRemover:
        def __init__(self, *args, **kwargs):
            pass

        async def health_check(self):
            # Skip watermark step in retry path
            return False

        async def process_image(self, *args, **kwargs):
            return True

        async def close(self):
            return None

    async def fake_expand_to_target_ratio(*args, **kwargs):
        return True

    monkeypatch.setattr("app.services.watermark_remover.WatermarkRemover", DummyRemover)
    monkeypatch.setattr(
        "app.services.image_expander.expand_to_target_ratio",
        fake_expand_to_target_ratio,
    )

    resp = client.post(f"/api/preprocess/retry/{img.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0

    db_session.expire_all()
    refreshed = db_session.query(BaseImage).filter(BaseImage.id == img.id).first()
    assert refreshed is not None
    assert refreshed.status == "completed"


def test_retry_preprocess_seedream_without_key_falls_back_to_auto(
    client,
    db_session,
    tmp_path,
    monkeypatch,
):
    image_path = tmp_path / "retry_seedream.jpg"
    _make_image(image_path)

    batch = Batch(name="b3", status="ongoing", total_images=1)
    db_session.add(batch)
    db_session.flush()

    img = BaseImage(
        batch_id=batch.id,
        filename="retry_seedream.jpg",
        original_path=str(image_path),
        status="failed",
        preprocess_mode="expand",
        retry_count=0,
    )
    db_session.add(img)
    db_session.add(Settings(key="watermark_engine", value="iopaint"))
    db_session.add(Settings(key="expand_engine", value="seedream"))
    db_session.add(Settings(key="expand_allow_fallback", value="1"))
    db_session.add(Settings(key="apiyi_api_key", value=""))
    db_session.commit()

    class DummyRemover:
        def __init__(self, *args, **kwargs):
            pass

        async def health_check(self):
            return False

        async def process_image(self, *args, **kwargs):
            return True

        async def close(self):
            return None

    called = {}

    async def fake_expand_to_target_ratio(*args, **kwargs):
        called["engine"] = kwargs.get("engine")
        called["allow_fallback"] = kwargs.get("allow_fallback")
        return True

    monkeypatch.setattr("app.services.watermark_remover.WatermarkRemover", DummyRemover)
    monkeypatch.setattr(
        "app.services.image_expander.expand_to_target_ratio",
        fake_expand_to_target_ratio,
    )
    monkeypatch.setattr("app.api.preprocess.settings.APIYI_API_KEY", "")

    resp = client.post(f"/api/preprocess/retry/{img.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0

    assert called["engine"] == "auto"
    assert called["allow_fallback"] is True
