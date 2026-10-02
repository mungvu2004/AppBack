"""Cài đặt runner huấn luyện (B6-03b [5]); đọc `TRAINING_*` từ môi trường, không DSN.

Giây là `float` để test đặt grace/nhịp nhỏ (1 s, 0,05 s) mà không vá hằng.
"""

from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from apps.ml.runtime.loader import MODEL_MAX_BYTES


class TrainingRunnerSettings(BaseSettings):
    """Trần giờ (cả chờ khoá), nhịp tim, TTL claim, grace luồng canh, nhịp đọc huỷ, trần trọng số.

    `training_trainer_override` = `"<module>:<tên>"` của trainer thay `discover_trainers`;
    `__main__` chỉ nhận khi `APP_ENV=test` (J01_smoke), môi trường khác → bỏ qua và log.
    """

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    training_max_wall_s: Annotated[float, Field(gt=0)] = 86_400
    training_heartbeat_s: Annotated[float, Field(gt=0)] = 30
    training_claim_ttl_ms: Annotated[int, Field(ge=1_000)] = 120_000
    training_stop_grace_s: Annotated[float, Field(gt=0)] = 300
    training_cancel_poll_s: Annotated[float, Field(gt=0)] = 5
    training_weights_max_bytes: Annotated[int, Field(gt=0)] = MODEL_MAX_BYTES
    training_trainer_override: str | None = None
