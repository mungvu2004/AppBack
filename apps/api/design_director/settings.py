"""Công tắc, hạn mức và mốc tuổi lịch quét của AI chọn phong cách (mẫu `apps/api/lighting_bake/settings.py`).

"Hàm worker nhập": `state.enqueue_auto` (worker `pipeline_quality`) và lịch quét đọc module này, nên chỉ
`pydantic_settings`. `DESIGN_DIRECTOR_VERTEX_SA_JSON` chỉ được đọc để biết "có khoá hay không";
`packages.genai` (agent G) mới dùng nội dung.
"""

from functools import cache

from pydantic import PositiveInt, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DesignDirectorSettings(BaseSettings):
    """`enabled` mặc định tắt (công tắc quản trị); hạn mức tính theo chủ dự án mỗi ngày UTC."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    design_director_enabled: bool = False
    design_director_daily_quota: PositiveInt = 30
    design_director_vertex_sa_json: SecretStr | None = None
    design_director_resend_after_s: PositiveInt = 600
    design_director_queued_max_age_s: PositiveInt = 2 * 3600
    design_director_running_max_age_s: PositiveInt = 15 * 60

    @property
    def available(self) -> bool:
        """Bật công tắc **và** có khoá service account — thiếu một trong hai thì coi như tắt."""
        key = self.design_director_vertex_sa_json
        return self.design_director_enabled and key is not None and bool(key.get_secret_value().strip())


@cache
def get_design_director_settings() -> DesignDirectorSettings:
    """Cấu hình của tiến trình, đọc biến môi trường một lần."""
    return DesignDirectorSettings()


def reset_design_director_settings_cache() -> None:
    """Chỉ cho test: đọc lại biến môi trường ở lần gọi sau."""
    get_design_director_settings.cache_clear()
