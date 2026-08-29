"""Shared test fixtures for BigData Interview Lab."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Session:
    """Create a temporary SQLite DB with Alembic migrations applied.

    Each test gets its own isolated database in tmp_path.
    Uses real Alembic migration — NOT Base.metadata.create_all().
    """
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path.as_posix()}"

    # Override settings.DATABASE_URL so Alembic env.py uses our temp DB
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    with patch("app.core.config.settings.DATABASE_URL", db_url):
        command.upgrade(alembic_cfg, "head")

    # Create engine with PRAGMA foreign_keys=ON (same as app)
    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def content_dir(tmp_path: Path) -> Path:
    """Return a clean content directory path for test file writing."""
    return tmp_path / "content"
