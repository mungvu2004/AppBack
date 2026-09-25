"""Hạn mức của N3 (B2-02 [5]); đọc lười như `apps/api/projects/settings.py`, test đổi bằng `monkeypatch.setenv`."""

from functools import cache

from pydantic import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProjectMembersSettings(BaseSettings):
    """Hạn mức thêm thành viên: số lượt và cửa sổ (giây) tính theo người thực hiện."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    member_add_rate_limit: PositiveInt = 60
    member_add_rate_window_s: PositiveInt = 3600


@cache
def get_project_members_settings() -> ProjectMembersSettings:
    """Cấu hình của tiến trình, đọc biến môi trường một lần."""
    return ProjectMembersSettings()


def reset_project_members_settings_cache() -> None:
    """Chỉ cho test: đọc lại biến môi trường ở lần gọi sau."""
    get_project_members_settings.cache_clear()
