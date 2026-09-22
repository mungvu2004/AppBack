"""Gương ma trận quyền của FE (BE-00 §5, B0-07 H3) — xuất lại cho `apps.api.access.deps` (D)."""

from packages.domain.permissions.matrix import (
    PERMISSION_KEYS,
    PERMISSION_MATRIX,
    ROLES,
    SYSTEM_SCOPED_KEYS,
    PermissionKey,
    Role,
    can,
)

__all__ = [
    "PERMISSION_KEYS",
    "PERMISSION_MATRIX",
    "ROLES",
    "SYSTEM_SCOPED_KEYS",
    "PermissionKey",
    "Role",
    "can",
]
