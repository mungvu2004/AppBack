"""So từng ô của `PERMISSION_MATRIX` với bảng viết tay — độc lập với H3 (B0-07),
chép bảng khối [2] của B1-02.md, gương `src/lib/auth/permissions.ts:90-141`.
Thứ tự khoá theo object literal `permissionMatrix` thật của FE (bảng chữ cái),
không phải thứ tự bảng trong prompt: H3 so cả thứ tự, chỉ nguồn FE thật là đúng.
"""

import pytest

from packages.domain.permissions import (
    PERMISSION_KEYS,
    PERMISSION_MATRIX,
    ROLES,
    SYSTEM_SCOPED_KEYS,
    can,
)

EXPECTED_KEYS = (
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

EXPECTED_MATRIX = {
    "floor.upload": {"admin": True, "engineer": True, "viewer": False},
    "layer.edit": {"admin": True, "engineer": True, "viewer": False},
    "library.manage": {"admin": True, "engineer": False, "viewer": False},
    "model.export": {"admin": True, "engineer": True, "viewer": False},
    "project.create": {"admin": True, "engineer": True, "viewer": False},
    "project.settings.edit": {"admin": True, "engineer": True, "viewer": False},
    "qc.approve": {"admin": True, "engineer": True, "viewer": False},
    "ruleset.edit": {"admin": True, "engineer": False, "viewer": False},
    "share.create": {"admin": True, "engineer": True, "viewer": False},
    "user.manage": {"admin": True, "engineer": False, "viewer": False},
}


def test_roles_are_exactly_three_in_fe_order() -> None:
    """3 vai, đúng thứ tự admin/engineer/viewer."""
    assert ROLES == ("admin", "engineer", "viewer")


def test_permission_keys_match_fe_order_exactly() -> None:
    """10 khoá, không thừa, đúng thứ tự `permissions.ts:19-29`."""
    assert PERMISSION_KEYS == EXPECTED_KEYS


def test_matrix_cells_match_expected_table_cell_by_cell() -> None:
    """So từng ô — không thừa, không thiếu khoá hay vai nào."""
    assert set(PERMISSION_MATRIX) == set(EXPECTED_KEYS)
    for key, expected_row in EXPECTED_MATRIX.items():
        actual_row = PERMISSION_MATRIX[key]  # type: ignore[index]
        assert dict(actual_row) == expected_row, key


@pytest.mark.parametrize(
    ("role", "key", "expected"),
    [
        ("admin", "user.manage", True),
        ("engineer", "user.manage", False),
        ("viewer", "floor.upload", False),
        ("engineer", "floor.upload", True),
    ],
)
def test_can_reads_matrix_for_known_role_and_key(role: str, key: str, expected: bool) -> None:
    """`can` chỉ là tra bảng, không thêm luật."""
    assert can(role, key) is expected


def test_can_returns_false_for_unknown_role() -> None:
    """Vai lạ → `False`, không ném."""
    assert can("superadmin", "floor.upload") is False


def test_can_returns_false_for_unknown_key() -> None:
    """Khoá lạ → `False`, không ném."""
    assert can("admin", "no.such.key") is False


def test_can_returns_false_when_both_role_and_key_are_unknown() -> None:
    """Cả vai và khoá lạ → vẫn `False`."""
    assert can("nobody", "nothing") is False


def test_matrix_outer_mapping_is_immutable() -> None:
    """Không sinh `PERMISSION_MATRIX` ra khỏi tầng ngoài lúc chạy (K19/BE-01 [9])."""
    with pytest.raises(TypeError):
        PERMISSION_MATRIX["floor.upload"] = PERMISSION_MATRIX["floor.upload"]  # type: ignore[index]


def test_matrix_inner_mapping_is_immutable() -> None:
    """Tầng trong cũng bất biến — không sửa được quyền của một vai riêng lẻ."""
    with pytest.raises(TypeError):
        PERMISSION_MATRIX["floor.upload"]["admin"] = False  # type: ignore[index]


def test_system_scoped_keys_is_subset_of_permission_keys() -> None:
    """Mọi khoá cấp hệ thống phải là một khoá quyền hợp lệ."""
    assert set(PERMISSION_KEYS) >= SYSTEM_SCOPED_KEYS


def test_system_scoped_keys_exact_membership() -> None:
    """Đúng ba khoá cấp hệ thống theo hợp đồng [2]."""
    assert frozenset({"project.create", "user.manage", "library.manage"}) == SYSTEM_SCOPED_KEYS
