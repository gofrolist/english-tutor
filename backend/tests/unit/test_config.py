"""Unit tests for configuration settings."""

import pytest

from src.english_tutor.config import get_settings, get_telegram_bot_token


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_get_settings_loads_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://example/db")
    monkeypatch.setenv("SQL_ECHO", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("API_HOST", "127.0.0.1")
    monkeypatch.setenv("API_PORT", "9000")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_URL", "https://example.com")
    monkeypatch.setenv("MEDIA_CACHE_DIR", "/tmp/cache")

    settings = get_settings()

    assert settings.database_url == "postgresql://example/db"
    assert settings.sql_echo is True
    assert settings.telegram_bot_token == "token"
    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 9000
    assert settings.debug is True
    assert settings.telegram_webhook_url == "https://example.com"
    assert settings.media_cache_dir == "/tmp/cache"


def test_get_telegram_bot_token_requires_value(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")

    with pytest.raises(ValueError):
        get_telegram_bot_token()
