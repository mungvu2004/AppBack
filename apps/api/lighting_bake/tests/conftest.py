"""Mặc định bật `LIGHTING_BAKE_ENABLED` cho test nướng ánh sáng; test tắt dùng `monkeypatch` riêng."""

from collections.abc import Iterator

import pytest

from apps.api.lighting_bake.settings import reset_lighting_bake_settings_cache


@pytest.fixture(autouse=True)
def bake_enabled(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("LIGHTING_BAKE_ENABLED", "true")
    reset_lighting_bake_settings_cache()
    yield
    monkeypatch.undo()
    reset_lighting_bake_settings_cache()
