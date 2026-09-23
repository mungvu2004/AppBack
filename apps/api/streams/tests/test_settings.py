"""`StreamSettings` — mặc định và ràng buộc S07 (B4-01 [5])."""

from collections.abc import Callable

import pytest
from pydantic import ValidationError

from apps.api.streams.settings import (
    MAX_CLOSE_S,
    StreamSettings,
    get_stream_settings,
    reset_stream_settings_cache,
)


def test_defaults_match_the_charter() -> None:
    """Giá trị mặc định đúng [5] của prompt: 15 s heartbeat, 3 s recheck, 6/500 kết nối."""
    settings = StreamSettings()
    assert settings.stream_heartbeat_s == 15
    assert settings.stream_recheck_s == 3
    assert settings.stream_max_per_user == 6
    assert settings.stream_max_global == 500
    assert settings.stream_read_block_ms == 1000
    assert settings.stream_read_count == 100


def test_defaults_close_a_revoked_stream_within_s07() -> None:
    """Mặc định phải nằm dưới trần 5 giây của S07, không chỉ "hợp lệ về kiểu"."""
    settings = StreamSettings()
    assert settings.stream_recheck_s * 1.2 + settings.stream_read_block_ms / 1000 <= MAX_CLOSE_S


@pytest.mark.parametrize(
    ("recheck_s", "block_ms"),
    [(4.0, 1000), (3.0, 2000), (10.0, 100)],
)
def test_rejects_configs_that_break_s07(recheck_s: float, block_ms: int) -> None:
    """`STREAM_RECHECK_S * 1,2 + STREAM_READ_BLOCK_MS/1000 > 5` → hỏng lúc nạp, không lúc chạy."""
    with pytest.raises(ValidationError, match="S07"):
        StreamSettings(stream_recheck_s=recheck_s, stream_read_block_ms=block_ms)


@pytest.mark.parametrize("value", [0, -1])
def test_rejects_zero_and_negative(value: int) -> None:
    """Không trường nào nhận 0 hay số âm: heartbeat 0 là ping liên tục, trần 0 là chặn hết,
    `STREAM_READ_BLOCK_MS` ≤ 0 là `XREAD` không chặn (vòng phát quay không tải)."""
    builders: tuple[Callable[[], StreamSettings], ...] = (
        lambda: StreamSettings(stream_heartbeat_s=value),
        lambda: StreamSettings(stream_recheck_s=value),
        lambda: StreamSettings(stream_max_per_user=value),
        lambda: StreamSettings(stream_max_global=value),
        lambda: StreamSettings(stream_read_block_ms=value),
        lambda: StreamSettings(stream_read_count=value),
    )
    for build in builders:
        with pytest.raises(ValidationError):
            build()


def test_cache_reads_environment_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """`get_stream_settings` nhớ theo tiến trình; test đổi env thì phải xoá cache trước."""
    monkeypatch.setenv("STREAM_MAX_PER_USER", "2")
    reset_stream_settings_cache()
    try:
        assert get_stream_settings().stream_max_per_user == 2
        monkeypatch.setenv("STREAM_MAX_PER_USER", "3")
        assert get_stream_settings().stream_max_per_user == 2
    finally:
        reset_stream_settings_cache()
