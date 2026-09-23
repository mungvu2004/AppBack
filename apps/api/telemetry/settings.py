"""`TelemetrySettings` — cờ #9 và hạn mức lô #37 (B7-01 [5]).

`FEATURE_FLAGS` sai (khoá lạ, giá trị khác kiểu, `roles` rỗng/trùng/vai lạ) ném
`ValueError` **lúc nạp**: app không lên, không đợi tới lượt đọc đầu tiên.
"""

from functools import cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from apps.api.telemetry.flags import FEATURE_FLAG_KEYS, FeatureFlagValue


class TelemetrySettings(BaseSettings):
    """Đọc lười qua `get_telemetry_settings()`, một lần mỗi tiến trình."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    feature_flags: dict[str, FeatureFlagValue] = {}
    telemetry_body_max_bytes: int = 65536
    telemetry_rate_limit: int = 120
    telemetry_rate_window_s: int = 60
    telemetry_max_events: int = 20
    telemetry_max_fields: int = 16
    telemetry_log_max_per_min: int = 600

    @field_validator("feature_flags")
    @classmethod
    def _known_keys(cls, value: dict[str, FeatureFlagValue]) -> dict[str, FeatureFlagValue]:
        """Mọi khoá `FEATURE_FLAGS` phải nằm trong 5 khoá của `flags.FEATURE_FLAG_KEYS`."""
        unknown = sorted(set(value) - set(FEATURE_FLAG_KEYS))
        if unknown:
            raise ValueError(f"khoá cờ tính năng lạ: {unknown!r}")
        return value


@cache
def get_telemetry_settings() -> TelemetrySettings:
    """Cấu hình của tiến trình, đọc biến môi trường một lần."""
    return TelemetrySettings()


def reset_telemetry_settings_cache() -> None:
    """Chỉ cho test: đọc lại biến môi trường ở lần gọi sau."""
    get_telemetry_settings.cache_clear()
