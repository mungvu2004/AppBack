"""Cấu hình cờ tính năng: `TelemetrySettings.feature_flags`, `resolve_feature_flags` (B7-01 [8])."""

from pathlib import Path

import pytest

from apps.api.telemetry.flags import (
    FEATURE_FLAG_KEY_PATTERN,
    FEATURE_FLAG_KEYS,
    MAX_FEATURE_FLAG_KEY_LENGTH,
    RoleFlag,
    resolve_feature_flags,
)
from apps.api.telemetry.settings import TelemetrySettings, get_telemetry_settings, reset_telemetry_settings_cache
from apps.api.telemetry.tests.mirror import read_ts_array


def test_feature_flag_keys_has_five_valid_keys() -> None:
    assert len(FEATURE_FLAG_KEYS) == 5
    assert len(set(FEATURE_FLAG_KEYS)) == 5
    for key in FEATURE_FLAG_KEYS:
        assert FEATURE_FLAG_KEY_PATTERN.fullmatch(key), key
        assert len(key) <= MAX_FEATURE_FLAG_KEY_LENGTH


def test_feature_flag_keys_mirror_appfront(appfront_dir: Path) -> None:
    """`FEATURE_FLAG_KEYS` == `FEATURE_FLAG_KEYS` của `src/lib/telemetry/flags.ts:86-92`, so như tập hợp."""
    fe_keys = read_ts_array(appfront_dir / "src/lib/telemetry/flags.ts", "FEATURE_FLAG_KEYS")
    assert set(fe_keys) == set(FEATURE_FLAG_KEYS)


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FEATURE_FLAGS", raising=False)
    reset_telemetry_settings_cache()


def test_default_feature_flags_is_empty() -> None:
    assert get_telemetry_settings().feature_flags == {}


@pytest.mark.parametrize(
    "raw",
    [
        '{"khong.ton-tai": true}',
        '{"scene.instanced-walls": "true"}',
        '{"scene.instanced-walls": 1}',
        '{"scene.instanced-walls": {"roles": []}}',
        '{"scene.instanced-walls": {"roles": ["admin", "admin"]}}',
        '{"scene.instanced-walls": {"roles": ["owner"]}}',
        '{"scene.instanced-walls": {"roles": ["admin", "engineer", "viewer", "admin"]}}',
    ],
    ids=["khoa-la", "chuoi-true", "so-1", "roles-rong", "roles-trung", "vai-la", "qua-3-vai"],
)
def test_invalid_feature_flags_raise_on_load(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("FEATURE_FLAGS", raw)
    reset_telemetry_settings_cache()
    with pytest.raises(ValueError, match="validation error"):
        get_telemetry_settings()


def test_valid_feature_flags_load(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "FEATURE_FLAGS",
        '{"scene.instanced-walls": true, "scene.soft-shadows": false, "rules.parallel-run": {"roles": ["admin"]}}',
    )
    reset_telemetry_settings_cache()
    settings = get_telemetry_settings()
    assert settings.feature_flags["scene.instanced-walls"] is True
    assert settings.feature_flags["scene.soft-shadows"] is False
    assert isinstance(settings.feature_flags["rules.parallel-run"], RoleFlag)


def test_resolve_feature_flags_only_has_configured_keys() -> None:
    settings = TelemetrySettings(
        feature_flags={
            "scene.instanced-walls": True,
            "rules.parallel-run": RoleFlag(roles=("admin",)),
        }
    )
    assert resolve_feature_flags(settings.feature_flags, "admin") == {
        "scene.instanced-walls": True,
        "rules.parallel-run": True,
    }
    assert resolve_feature_flags(settings.feature_flags, "viewer") == {
        "scene.instanced-walls": True,
        "rules.parallel-run": False,
    }


def test_resolve_feature_flags_empty_configuration_is_empty() -> None:
    assert resolve_feature_flags({}, "admin") == {}
