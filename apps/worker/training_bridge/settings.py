"""Cấu hình của cầu nối: đọc lại `apps.api.admin_ml_jobs.settings` (một nguồn với N35, N36/N37).

TTL `cancel_key` và cửa sổ muộn phải trùng giữa route và cầu nối; hai lớp cài đặt riêng sẽ
lệch âm thầm khi một bên đổi biến môi trường. File đó không nhập `fastapi`.
"""

from apps.api.admin_ml_jobs.settings import TrainingSettings, get_training_settings, reset_training_settings_cache

__all__ = ["TrainingSettings", "get_training_settings", "reset_training_settings_cache"]
