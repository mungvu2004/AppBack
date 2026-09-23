"""Tham số của trung tâm SSE (B4-01 [5]).

Đọc **lười** qua `get_stream_settings()` như `apps/api/projects/settings.py`: B0-06
nhập mọi module của `apps.api` khi chưa có biến môi trường nào, còn test đặt
`monkeypatch.setenv` rồi `reset_stream_settings_cache()` **trước** khi dựng app —
`lifespan` của router đọc cấu hình đúng một lần lúc khởi động.

Ràng buộc S07 kiểm **lúc nạp**: một luồng chỉ phát hiện mất quyền ở đầu vòng kế
tiếp, nên thời gian đóng tệ nhất là `STREAM_RECHECK_S` (đã cộng lệch +20 %) cộng
một lượt `XREAD BLOCK`. Cấu hình nào vượt 5 giây là hỏng hợp đồng S07 ngay cả khi
mã chạy đúng, nên nó phải chết lúc khởi động chứ không phải lúc review.
"""

from functools import cache
from typing import Final

from pydantic import PositiveFloat, PositiveInt, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RECHECK_JITTER: Final = 0.2
"""Lệch ngẫu nhiên ±20 % của chu kỳ recheck — hàng nghìn luồng không kiểm phiên cùng một nhịp."""

MAX_CLOSE_S: Final = 5.0
"""Trần S07: server phải đóng luồng mất quyền trong 5 giây."""


class StreamSettings(BaseSettings):
    """Trần kết nối, nhịp heartbeat và tham số đọc stream; mọi giá trị dương."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    stream_heartbeat_s: PositiveFloat = 15
    stream_recheck_s: PositiveFloat = 3
    stream_max_per_user: PositiveInt = 6
    stream_max_global: PositiveInt = 500
    stream_read_block_ms: PositiveInt = 1000
    stream_read_count: PositiveInt = 100

    @model_validator(mode="after")
    def _closes_within_s07(self) -> "StreamSettings":
        """Trần đóng luồng tệ nhất phải ≤ `MAX_CLOSE_S` (B4-01 [5], S07)."""
        worst = self.stream_recheck_s * (1 + RECHECK_JITTER) + self.stream_read_block_ms / 1000
        if worst > MAX_CLOSE_S:
            raise ValueError(
                f"STREAM_RECHECK_S * {1 + RECHECK_JITTER} + STREAM_READ_BLOCK_MS/1000 = {worst} "
                f"vượt {MAX_CLOSE_S} giây (S07)"
            )
        return self


@cache
def get_stream_settings() -> StreamSettings:
    """Cấu hình của tiến trình, đọc biến môi trường một lần."""
    return StreamSettings()


def reset_stream_settings_cache() -> None:
    """Chỉ cho test và CLI: đọc lại biến môi trường ở lần gọi sau."""
    get_stream_settings.cache_clear()
