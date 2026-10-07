"""Pytest configuration, shared fixtures, database isolation, and test client."""

import tempfile
from pathlib import Path
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.database import Base, get_db
from app.main import app


@pytest.fixture(scope="session")
def test_temp_dir() -> Generator[Path, None, None]:
    """Provide temporary directory for test file uploads."""
    with tempfile.TemporaryDirectory(prefix="geo_test_uploads_") as td:
        upload_path = Path(td)
        # Override settings upload path
        old_dir = settings.UPLOAD_DIR
        settings.UPLOAD_DIR = str(upload_path)
        yield upload_path
        settings.UPLOAD_DIR = old_dir


@pytest.fixture(scope="function")
def test_db_session(test_temp_dir: Path) -> Generator[Session, None, None]:
    """Create a pristine SQLite database for each test function."""
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture(scope="function")
def client(test_db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient fixture with overridden database dependency."""
    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
