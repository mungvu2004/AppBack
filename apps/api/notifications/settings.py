"""Hạn mức của thông báo (B4-02 [5]); đọc lười, test đổi bằng `monkeypatch.setenv` rồi xoá cache."""

from functools import cache
from typing import Final, Self

from pydantic import PositiveInt, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MARK_MAX_DEFAULT: Final = 200


class NotificationsSettings(BaseSettings):
    """Trần danh sách, đánh dấu, giữ lại; hạn khử trùng XADD; cửa sổ quét bù; lô và hạn dọn dòng ẩn."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    notifications_list_max: PositiveInt = 200
    notifications_mark_max: PositiveInt = MARK_MAX_DEFAULT
    notifications_keep_max: PositiveInt = 200
    notifications_dedupe_ttl_s: PositiveInt = 86400
    notifications_unsent_after_s: PositiveInt = 120
    notifications_unsent_window_s: PositiveInt = 43200
    notifications_sweep_batch: PositiveInt = 500
    notifications_hidden_purge_after_s: PositiveInt = 2592000

    @model_validator(mode="after")
    def _window_within_dedupe(self) -> Self:
        """`UNSENT_WINDOW_S x 2 ≤ DEDUPE_TTL_S`: quét bù không gặp khoá khử trùng đã hết hạn (K32)."""
        if self.notifications_unsent_window_s * 2 > self.notifications_dedupe_ttl_s:
            raise ValueError("NOTIFICATIONS_UNSENT_WINDOW_S x 2 phải ≤ NOTIFICATIONS_DEDUPE_TTL_S")
        return self


@cache
def get_notifications_settings() -> NotificationsSettings:
    """Cấu hình của tiến trình, đọc biến môi trường một lần."""
    return NotificationsSettings()


def reset_notifications_settings_cache() -> None:
    """Chỉ cho test: đọc lại biến môi trường ở lần gọi sau."""
    get_notifications_settings.cache_clear()
