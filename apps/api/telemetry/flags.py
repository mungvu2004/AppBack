"""5 khoá cờ tính năng #9 và cách tính theo vai (B7-01 [2], [5], [6]).

Gương `src/lib/telemetry/flags.ts:73,76,86-92` (FE): 5 khoá, cùng mẫu và trần độ dài,
client không giải mã bằng schema nên khoá lạ/kiểu sai phải bị chặn ngay lúc **nạp cấu
hình** ở BE (K01/K02), không phải lúc trả response.
"""

import re
from typing import Final

from pydantic import BaseModel, ConfigDict, StrictBool, field_validator

from apps.api.core.auth import Role

FEATURE_FLAG_KEY_PATTERN: Final = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
MAX_FEATURE_FLAG_KEY_LENGTH: Final = 48

FEATURE_FLAG_KEYS: Final = (
    "scene.instanced-walls",
    "scene.soft-shadows",
    "rules.parallel-run",
    "export.pdf-vector",
    "qc.live-collaboration",
)

_MIN_ROLES: Final = 1
_MAX_ROLES: Final = 3


class RoleFlag(BaseModel):
    """Cờ bật theo vai: `{"roles": [...]}` — 1-3 vai, không trùng (B7-01 [5])."""

    model_config = ConfigDict(extra="forbid")

    roles: tuple[Role, ...]

    @field_validator("roles")
    @classmethod
    def _valid_roles(cls, value: tuple[Role, ...]) -> tuple[Role, ...]:
        if not _MIN_ROLES <= len(value) <= _MAX_ROLES:
            raise ValueError(f"roles phải có {_MIN_ROLES}-{_MAX_ROLES} phần tử, nhận {len(value)}")
        if len(set(value)) != len(value):
            raise ValueError(f"roles không được trùng: {value!r}")
        return value


FeatureFlagValue = StrictBool | RoleFlag
"""`StrictBool` để `"true"`/`1` bị từ chối thay vì ép kiểu (K01/K02)."""


def resolve_feature_flags(configured: dict[str, FeatureFlagValue], role: Role) -> dict[str, bool]:
    """Cờ theo vai của phiên hiện tại; khoá chưa cấu hình **vắng mặt** trong kết quả."""
    resolved: dict[str, bool] = {}
    for key in FEATURE_FLAG_KEYS:
        value = configured.get(key)
        if value is None:
            continue
        resolved[key] = value if isinstance(value, bool) else role in value.roles
    return resolved
