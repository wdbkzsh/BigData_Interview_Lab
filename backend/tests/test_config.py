from app.core.config import DATABASE_PATH, Settings


def test_default_app_name():
    settings = Settings()
    assert settings.APP_NAME == "BigData Interview Lab"


def test_default_app_env():
    settings = Settings()
    assert settings.APP_ENV == "development"


def test_default_timezone():
    settings = Settings()
    assert settings.APP_TIMEZONE == "Asia/Shanghai"


def test_default_database_url():
    settings = Settings()
    assert settings.DATABASE_URL == f"sqlite:///{DATABASE_PATH.as_posix()}"


def test_env_override(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_TIMEZONE", "UTC")
    new_settings = Settings()
    assert new_settings.APP_ENV == "test"
    assert new_settings.APP_TIMEZONE == "UTC"