from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.db.session import create_db_engine, get_db, SessionLocal


@pytest.fixture
def tmp_engine(tmp_path):
    """使用 create_db_engine 创建临时 SQLite 引擎"""
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path.as_posix()}"
    test_engine = create_db_engine(db_url)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def tmp_session_factory(tmp_engine):
    """基于临时引擎创建 SessionLocal"""
    return sessionmaker(bind=tmp_engine)


def test_engine_can_connect(tmp_engine):
    """验证 Engine 可以建立连接"""
    with tmp_engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1


def test_session_can_execute(tmp_session_factory):
    """验证 Session 可以执行查询"""
    db = tmp_session_factory()
    result = db.execute(text("SELECT 1"))
    assert result.scalar() == 1
    db.close()


def test_foreign_keys_enabled(tmp_engine):
    """验证 foreign_keys=ON 已启用"""
    with tmp_engine.connect() as conn:
        result = conn.execute(text("PRAGMA foreign_keys"))
        assert result.scalar() == 1


def test_get_db_closes_session():
    """验证 get_db() 的 finally 块调用 Session.close()"""
    mock_session = MagicMock(spec=Session)

    with patch(
        "app.db.session.SessionLocal",
        return_value=mock_session,
    ):
        db_gen = get_db()
        yielded_db = next(db_gen)

        assert yielded_db is mock_session

        db_gen.close()

        mock_session.close.assert_called_once()


def test_create_engine_does_not_create_database_file(tmp_path):
    """验证 create_engine 是 lazy 的，不会立即创建数据库文件"""
    db_path = tmp_path / "test_lazy.db"
    db_url = f"sqlite:///{db_path.as_posix()}"

    test_engine = create_db_engine(db_url)

    assert not db_path.exists()

    test_engine.dispose()


def test_session_local_creates_session():
    """验证 SessionLocal 可以创建 SQLAlchemy Session 实例"""
    db = SessionLocal()
    try:
        assert isinstance(db, Session)
    finally:
        db.close()