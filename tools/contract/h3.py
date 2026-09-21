"""H3 — gương ma trận quyền của FE ở `packages.domain.permissions` (B0-07 [6].6, BE-00 §5).

FE (`src/lib/auth/permissions.ts`) là nguồn; B1-02 khai tay `ROLES`, `PERMISSION_KEYS`,
`PERMISSION_MATRIX`. So **hai chiều**: tập và thứ tự vai, tập và thứ tự khoá, rồi từng ô
trên hợp của hai bên — ô chỉ có một bên cũng là lệch.
"""

from collections.abc import Iterable, Mapping
from itertools import chain
from types import ModuleType
from typing import Any, Final

REQUIRED_NAMES: Final = ("ROLES", "PERMISSION_KEYS", "PERMISSION_MATRIX")


def _ordered_union(*groups: Iterable[str]) -> list[str]:
    """Hợp giữ thứ tự xuất hiện đầu tiên — để in ô lệch theo thứ tự của FE."""
    return list(dict.fromkeys(chain.from_iterable(groups)))


def _cell(matrix: Mapping[str, Mapping[str, bool]], key: str, role: str) -> bool | None:
    """Giá trị một ô, `None` khi khoá hay vai vắng."""
    return matrix.get(key, {}).get(role)


def compare_permissions(fe: Mapping[str, Any], mirror: ModuleType) -> list[str]:
    """Mọi chỗ lệch giữa ma trận FE (`{roles, keys, matrix}` của runner) và module gương."""
    missing = [name for name in REQUIRED_NAMES if not hasattr(mirror, name)]
    if missing:
        return [f"{mirror.__name__} thiếu {', '.join(missing)}"]
    roles, keys = list(mirror.ROLES), list(mirror.PERMISSION_KEYS)
    be_matrix: Mapping[str, Mapping[str, bool]] = mirror.PERMISSION_MATRIX
    problems: list[str] = []
    if roles != fe["roles"]:
        problems.append(f"ROLES {roles} ≠ AUTH_ROLES {fe['roles']} (tập và thứ tự)")
    if keys != fe["keys"]:
        problems.append(f"PERMISSION_KEYS {keys} ≠ khoá của permissionMatrix {fe['keys']} (tập và thứ tự)")
    for key in _ordered_union(fe["keys"], keys, be_matrix):
        for role in _ordered_union(fe["roles"], roles):
            fe_value, be_value = _cell(fe["matrix"], key, role), _cell(be_matrix, key, role)
            if fe_value != be_value:
                problems.append(f"{key} / {role}: FE {fe_value} ≠ BE {be_value}")
    return problems
