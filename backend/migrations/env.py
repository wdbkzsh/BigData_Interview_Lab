import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, event, pool

# Ensure backend/ is on sys.path so `app.*` imports work
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import DATABASE_PATH, settings
from app.db.base import Base

# Import all models so Base.metadata is fully populated
import app.db.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_url() -> str:
    """Return the DATABASE_URL, allowing env-var override via Settings."""
    return settings.DATABASE_URL


def _ensure_data_dir(url: str) -> None:
    """Create the data/ directory only when targeting the formal database."""
    if url.startswith("sqlite:///") and "data/app.db" in url:
        DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _configure_connection(dbapi_connection, connection_record):
    """Set PRAGMAs on every SQLite connection Alembic opens."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def run_migrations_offline() -> None:
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _get_url()
    _ensure_data_dir(url)

    connectable = create_engine(url, poolclass=pool.NullPool)
    event.listen(connectable, "connect", _configure_connection)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()