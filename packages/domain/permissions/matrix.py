"""Gương ma trận quyền của FE: `src/lib/auth/permissions.ts:19-29,90-141` (BE-00 §5, B0-07 H3).

`PERMISSION_MATRIX` là **dữ liệu khai tay**, không sinh từ file FE lúc chạy — lệch
FE thì H3 hỏng và người sửa cả hai bên (BE-01 [9]). Quyền theo dự án
(`require_project`) không nằm ở đây, thuộc B2-01.

`PERMISSION_KEYS` giữ đúng thứ tự khai của object literal `permissionMatrix` ở
FE (`bảng chữ cái`, không phải thứ tự khai `permissionEntries` phía trên nó) —
H3 so **thứ tự**, không chỉ tập hợp.
"""

from types import MappingProxyType
from typing import Final, Literal

Role = Literal["admin", "engineer", "viewer"]
PermissionKey = Literal[
    "floor.upload",
    "layer.edit",
    "library.manage",
    "model.export",
    "project.create",
    "project.settings.edit",
    "qc.approve",
    "ruleset.edit",
    "share.create",
    "user.manage",
]

ROLES: Final[tuple[Role, ...]] = ("admin", "engineer", "viewer")

PERMISSION_KEYS: Final[tuple[PermissionKey, ...]] = (
    "floor.upload",
    "layer.edit",
    "library.manage",
    "model.export",
    "project.create",
    "project.settings.edit",
    "qc.approve",
    "ruleset.edit",
    "share.create",
    "user.manage",
)

PERMISSION_MATRIX: Final[MappingProxyType[PermissionKey, MappingProxyType[Role, bool]]] = MappingProxyType(
    {
        "floor.upload": MappingProxyType({"admin": True, "engineer": True, "viewer": False}),
        "layer.edit": MappingProxyType({"admin": True, "engineer": True, "viewer": False}),
        "library.manage": MappingProxyType({"admin": True, "engineer": False, "viewer": False}),
        "model.export": MappingProxyType({"admin": True, "engineer": True, "viewer": False}),
        "project.create": MappingProxyType({"admin": True, "engineer": True, "viewer": False}),
        "project.settings.edit": MappingProxyType({"admin": True, "engineer": True, "viewer": False}),
        "qc.approve": MappingProxyType({"admin": True, "engineer": True, "viewer": False}),
        "ruleset.edit": MappingProxyType({"admin": True, "engineer": False, "viewer": False}),
        "share.create": MappingProxyType({"admin": True, "engineer": True, "viewer": False}),
        "user.manage": MappingProxyType({"admin": True, "engineer": False, "viewer": False}),
    }
)

SYSTEM_SCOPED_KEYS: Final[frozenset[PermissionKey]] = frozenset({"project.create", "user.manage", "library.manage"})
"""Khoá chỉ kiểm ở cấp hệ thống (`require_permission`); các khoá còn lại chỉ kiểm qua
`require_project` (B2-01), không dùng ở đây (K08)."""


def can(role: str, key: str) -> bool:
    """`role`/`key` lạ → `False`, không ném — cùng hành vi với `can` của FE (permissions.ts:149-163)."""
    if key not in PERMISSION_KEYS or role not in ROLES:
        return False
    return PERMISSION_MATRIX[key][role]
