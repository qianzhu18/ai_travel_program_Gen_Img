"""
Test fixtures - in-memory SQLite DB + FastAPI test client
"""
import os
import sys
import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure backend root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.database import Base, TaskProgress
from app.core.database import get_db
from app.services import progress_store as ps


# --------------- DB fixtures ---------------

@pytest.fixture()
def db_engine():
    """In-memory SQLite engine, tables created fresh each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    """Scoped session bound to the in-memory engine."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def patch_progress_store(db_engine, monkeypatch):
    """
    Patch progress_store.SessionLocal so it uses the in-memory DB,
    and clear the module-level cache between tests.
    """
    Session = sessionmaker(bind=db_engine)
    monkeypatch.setattr(ps, "SessionLocal", Session)
    ps._cache.clear()
    yield
    ps._cache.clear()


# --------------- FastAPI test client ---------------

@pytest.fixture()
def client(db_engine):
    """Starlette sync TestClient wired to the test DB."""
    from starlette.testclient import TestClient
    from app.main import app

    Session = sessionmaker(bind=db_engine)

    def _override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db

    # Also patch progress_store to use test DB
    original_session = ps.SessionLocal
    ps.SessionLocal = Session
    ps._cache.clear()

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    ps.SessionLocal = original_session
    ps._cache.clear()


# --------------- Temp image helpers ---------------

@pytest.fixture()
def tmp_image(tmp_path):
    """Create a simple 100x100 red JPEG for testing."""
    from PIL import Image
    img = Image.new("RGB", (100, 100), color="red")
    path = tmp_path / "test_input.jpg"
    img.save(str(path), format="JPEG", quality=95)
    return path


@pytest.fixture()
def large_image(tmp_path):
    """Create a ~1MB+ image that needs compression."""
    from PIL import Image
    img = Image.new("RGB", (3000, 3000), color="blue")
    path = tmp_path / "large_input.jpg"
    img.save(str(path), format="JPEG", quality=98)
    return path
