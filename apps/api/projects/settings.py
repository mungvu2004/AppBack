"""Hạn mức của module dự án (B2-01 [5]).

Đọc **lười** qua `get_projects_settings()` như `apps/api/auth/settings.py`: B0-06 nhập
mọi module của `apps.api` khi không có biến môi trường nào, còn test đổi hạn mức bằng
`monkeypatch.setenv` rồi `reset_projects_settings_cache()`.

Trần của N1 **không** ở đây: nó là hằng `page_params(max_limit=500)` ở router, vì zod của
FE ghim 500 (HOP-DONG-MOI §0.2) — một biến môi trường đổi được sẽ làm dây lệch hợp đồng.
"""

from functools import cache

from pydantic import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProjectsSettings(BaseSettings):
    """Trần danh sách #23 và tham số lịch dọn dự án đã xoá mềm; mọi giá trị nguyên dương."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    projects_list_max: PositiveInt = 500
    project_purge_after_days: PositiveInt = 30
    project_purge_batch: PositiveInt = 20
    project_purge_lock_timeout_s: PositiveInt = 30


@cache
def get_projects_settings() -> ProjectsSettings:
    """Cấu hình của tiến trình, đọc biến môi trường một lần."""
    return ProjectsSettings()


def reset_projects_settings_cache() -> None:
    """Chỉ cho test và CLI: đọc lại biến môi trường ở lần gọi sau."""
    get_projects_settings.cache_clear()
