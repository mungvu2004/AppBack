"""Cấu hình cổng mô hình sinh (AID-01), chỉ đọc biến môi trường.

Đọc **lười** qua `get_genai_settings()` như các gói khác (nạp module không đọc settings).
Thiếu `DESIGN_DIRECTOR_VERTEX_SA_JSON` là trạng thái hợp lệ: `create_genai` trả `None`
và tính năng tự tắt.
"""

import json
from functools import cache

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GenAISettings(BaseSettings):
    """Khoá service account (nội dung JSON), dự án GCP và tên mô hình Vertex."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    design_director_vertex_sa_json: SecretStr | None = None
    design_director_vertex_project: str | None = None
    design_director_model: str = "gemini-3.8-flash"

    @model_validator(mode="after")
    def _validate_key(self) -> "GenAISettings":
        """Khoá có mặt thì phải là đối tượng JSON; thiếu dự án ở cả setting lẫn khoá → lỗi lúc nạp."""
        info = self.service_account_info()
        if info is not None and not self.project():
            raise ValueError("Cần DESIGN_DIRECTOR_VERTEX_PROJECT hoặc project_id trong khoá service account")
        return self

    def service_account_info(self) -> dict[str, object] | None:
        """Nội dung khoá đã giải JSON; `None` khi chưa cấu hình (chuỗi rỗng coi như thiếu)."""
        secret = self.design_director_vertex_sa_json
        raw = secret.get_secret_value().strip() if secret else ""
        if not raw:
            return None
        try:
            info = json.loads(raw)
        except ValueError:
            raise ValueError("DESIGN_DIRECTOR_VERTEX_SA_JSON không phải JSON") from None
        if not isinstance(info, dict):
            raise ValueError("DESIGN_DIRECTOR_VERTEX_SA_JSON phải là đối tượng JSON")
        return info

    def project(self) -> str | None:
        """Dự án GCP: setting thắng, không thì `project_id` của khoá."""
        if self.design_director_vertex_project:
            return self.design_director_vertex_project
        info = self.service_account_info()
        value = info.get("project_id") if info else None
        return value if isinstance(value, str) and value else None


@cache
def get_genai_settings() -> GenAISettings:
    """Cấu hình của tiến trình, đọc biến môi trường một lần."""
    return GenAISettings()


def reset_genai_settings_cache() -> None:
    """Chỉ cho test: đọc lại biến môi trường ở lần gọi `get_genai_settings()` sau."""
    get_genai_settings.cache_clear()
