"""Test `CoreSettings` (BE-00 §2.1, §5)."""

from collections.abc import Callable, Iterator
from functools import partial
from pathlib import Path

import pytest
from pydantic import ValidationError

from packages.core.settings import CoreSettings, get_core_settings, reset_settings_cache

ENV_NAMES = ("APP_ENV", "PUBLIC_BASE_URL", "SECRET_KEY", "SECRET_KEY_PREVIOUS", "LOG_LEVEL", "LOG_JSON")
BASE_ENV = {"APP_ENV": "test", "PUBLIC_BASE_URL": "https://appback.test", "SECRET_KEY": "k" * 32}


def _use_env(monkeypatch: pytest.MonkeyPatch, **values: str | None) -> None:
    """Hàm phụ của test: use env."""
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    for name, value in (BASE_ENV | values).items():
        if value is not None:
            monkeypatch.setenv(name, value)
    reset_settings_cache()


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., None]]:
    """Hàm phụ của test: env."""
    yield partial(_use_env, monkeypatch)
    reset_settings_cache()


def test_defaults(env: Callable[..., None]) -> None:
    """Kiểm test defaults."""
    env()
    settings = CoreSettings()
    assert settings.app_env == "test"
    assert settings.public_base_url == "https://appback.test"
    assert settings.secret_key.get_secret_value() == "k" * 32
    assert settings.secret_key_previous == ()
    assert settings.log_level == "INFO"
    assert settings.log_json is True


def test_secret_not_in_repr(env: Callable[..., None]) -> None:
    """Kiểm test secret not in repr."""
    env()
    assert "k" * 32 not in repr(CoreSettings())


def test_missing_secret_key_fails(env: Callable[..., None]) -> None:
    """Kiểm test missing secret key fails."""
    env(SECRET_KEY=None)
    with pytest.raises(ValidationError, match="secret_key"):
        CoreSettings()


def test_secret_key_31_bytes_fails(env: Callable[..., None]) -> None:
    """Kiểm test secret key 31 bytes fails."""
    env(SECRET_KEY="k" * 31)
    with pytest.raises(ValidationError, match="32 byte"):
        CoreSettings()


def test_secret_key_32_bytes_ok(env: Callable[..., None]) -> None:
    """Kiểm test secret key 32 bytes ok."""
    env(SECRET_KEY="é" * 16)  # 16 ký tự, 32 byte UTF-8: đếm byte, không đếm ký tự
    assert CoreSettings().secret_key.get_secret_value() == "é" * 16


def test_secret_key_previous_list(env: Callable[..., None]) -> None:
    """Kiểm test secret key previous list."""
    env(SECRET_KEY_PREVIOUS=f"{'a' * 32}, {'b' * 32},")
    assert [s.get_secret_value() for s in CoreSettings().secret_key_previous] == ["a" * 32, "b" * 32]


def test_secret_key_previous_empty(env: Callable[..., None]) -> None:
    """Kiểm test secret key previous empty."""
    env(SECRET_KEY_PREVIOUS="")
    assert CoreSettings().secret_key_previous == ()


def test_secret_key_previous_short_fails(env: Callable[..., None]) -> None:
    """Kiểm test secret key previous short fails."""
    env(SECRET_KEY_PREVIOUS=f"{'a' * 32},short")
    with pytest.raises(ValidationError, match="32 byte"):
        CoreSettings()


@pytest.mark.parametrize("app_env", ["staging", "production"])
def test_http_rejected_outside_dev(env: Callable[..., None], app_env: str) -> None:
    """Kiểm test http rejected outside dev."""
    env(APP_ENV=app_env, PUBLIC_BASE_URL="http://appback.vn")
    with pytest.raises(ValidationError, match="https"):
        CoreSettings()


def test_https_accepted_in_production(env: Callable[..., None]) -> None:
    """Kiểm test https accepted in production."""
    env(APP_ENV="production", PUBLIC_BASE_URL="https://appback.vn")
    assert CoreSettings().public_base_url == "https://appback.vn"


def test_http_allowed_in_dev(env: Callable[..., None]) -> None:
    """Kiểm test http allowed in dev."""
    env(APP_ENV="dev", PUBLIC_BASE_URL="http://localhost:8080")
    assert CoreSettings().public_base_url == "http://localhost:8080"


@pytest.mark.parametrize(
    "url",
    [
        "https://appback.vn/",
        "https://appback.vn/app/",
        "/api",
        "appback.vn",
        "ftp://appback.vn",
        "https://",
        "https://a.vn?x=1",
        "https://a.vn#x",
    ],
)
def test_public_base_url_rejected(env: Callable[..., None], url: str) -> None:
    """Kiểm test public base url rejected."""
    env(PUBLIC_BASE_URL=url)
    with pytest.raises(ValidationError, match="PUBLIC_BASE_URL"):
        CoreSettings()


def test_unknown_app_env_rejected(env: Callable[..., None]) -> None:
    """Kiểm test unknown app env rejected."""
    env(APP_ENV="prod")
    with pytest.raises(ValidationError, match="app_env"):
        CoreSettings()


def test_log_settings_and_unrelated_env(env: Callable[..., None], monkeypatch: pytest.MonkeyPatch) -> None:
    """Kiểm test log settings and unrelated env."""
    env(LOG_LEVEL="DEBUG", LOG_JSON="false")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x")
    settings = CoreSettings()
    assert (settings.log_level, settings.log_json) == ("DEBUG", False)


def test_dotenv_not_read(env: Callable[..., None], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Kiểm test dotenv not read."""
    env(SECRET_KEY=None)
    (tmp_path / ".env").write_text(f"SECRET_KEY={'z' * 32}\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValidationError, match="secret_key"):
        CoreSettings()


def test_get_core_settings_cached_until_reset(env: Callable[..., None]) -> None:
    """Kiểm test get core settings cached until reset."""
    env(LOG_LEVEL="WARNING")
    first = get_core_settings()
    assert get_core_settings() is first
    env(LOG_LEVEL="ERROR")
    assert get_core_settings().log_level == "ERROR"


@pytest.mark.parametrize("app_env", ["staging", "production"])
@pytest.mark.parametrize("placeholder", ["change-me-32-bytes-minimum-please", "CHANGE-ME-" + "x" * 32])
def test_secret_key_placeholder_rejected_outside_dev(env: Callable[..., None], app_env: str, placeholder: str) -> None:
    """SEC-041: khoá mẫu của `env.example` (đúng 33 byte, qua kiểm độ dài) bị từ chối ở staging/production,
    cả ở `SECRET_KEY` lẫn `SECRET_KEY_PREVIOUS`; dev/test/ci vẫn dùng được."""
    env(APP_ENV=app_env, PUBLIC_BASE_URL="https://appback.vn", SECRET_KEY=placeholder)
    with pytest.raises(ValidationError, match="change-me"):
        CoreSettings()
    env(APP_ENV=app_env, PUBLIC_BASE_URL="https://appback.vn", SECRET_KEY_PREVIOUS=f"{'a' * 32},{placeholder}")
    with pytest.raises(ValidationError, match="change-me"):
        CoreSettings()
    env(APP_ENV="ci", SECRET_KEY=placeholder)
    assert CoreSettings().secret_key.get_secret_value() == placeholder
