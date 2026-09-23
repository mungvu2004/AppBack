"""Test model response (B2-01 [2]): strict như zod, vắng thay cho `null` (K01, K02)."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Final

import pytest

from apps.api.projects.wire import (
    ProjectOut,
    ProjectRollup,
    ProjectStatus,
    SummaryStatus,
    UserOut,
    project_summary_out,
    summary_member_out,
    user_out,
)
from packages.db.models.auth import User
from packages.db.models.projects import Project

AT: Final = datetime(2026, 9, 23, 7, 8, 9, tzinfo=UTC)


def _user(name: str = "Chị Hà") -> User:
    """Một dòng `users` dựng trong bộ nhớ — test này không chạm DB."""
    return User(id="usr_" + "0" * 26, email="ha@example.com", name=name, role="engineer", status="active")


def _project() -> Project:
    """Một dòng `projects` dựng trong bộ nhớ, đủ trường mà dây cần."""
    project = Project(id="prj_" + "0" * 26, name="Nhà A", created_by=_user().id)
    project.created_at = AT
    project.updated_at = AT
    return project


def _rollup(
    *,
    floor_count: int = 0,
    area_m2: Decimal = Decimal("0.00"),
    walls_total: int = 0,
    walls_reviewed: int = 0,
    status: SummaryStatus = "processing",
    legacy_status: ProjectStatus = "draft",
    default_floor_id: str | None = None,
) -> ProjectRollup:
    """Rollup của dự án 0 tầng; mỗi test ghi đè đúng trường nó nói tới."""
    return ProjectRollup(
        floor_count=floor_count,
        area_m2=area_m2,
        walls_total=walls_total,
        walls_reviewed=walls_reviewed,
        status=status,
        legacy_status=legacy_status,
        default_floor_id=default_floor_id,
    )


def test_project_out_has_exactly_the_contract_keys() -> None:
    """`ProjectSchema` strict: không `currentVersion`, `progress`, `deletedAt`, không `null`."""
    dumped = ProjectOut(
        id=_project().id,
        name="Nhà A",
        created_at=AT,
        updated_at=AT,
        status="draft",
        floors=[],
        members=[user_out(_user())],
    ).model_dump(by_alias=True)
    assert set(dumped) == {"id", "name", "createdAt", "updatedAt", "status", "floors", "members"}
    assert None not in dumped.values()


def test_project_out_keeps_optional_strings_when_present() -> None:
    """`code`, `address` có giá trị thì có mặt — "vắng" chỉ nói về `None`."""
    dumped = ProjectOut(
        id=_project().id,
        name="Nhà A",
        code="NA-01",
        address="1 Lê Lợi",
        created_at=AT,
        updated_at=AT,
        status="approved",
        floors=[],
        members=[],
    ).model_dump(by_alias=True)
    assert (dumped["code"], dumped["address"]) == ("NA-01", "1 Lê Lợi")


def test_user_out_omits_avatar_url() -> None:
    """`avatarUrl` vắng ở v1 (đường ký URL thuộc B1-04), `role` là vai hệ thống."""
    dumped = user_out(_user()).model_dump(by_alias=True)
    assert dumped == {"id": _user().id, "email": "ha@example.com", "name": "Chị Hà", "role": "engineer"}


def test_user_out_rejects_unknown_role() -> None:
    """Vai ngoài `admin|engineer|viewer` không lọt ra dây được (FE dùng `z.enum`)."""
    with pytest.raises(ValueError, match="role"):
        UserOut.model_validate({"id": "usr_1", "email": "a@b.c", "name": "A", "role": "owner"})


def test_summary_area_is_a_json_number_rounded_to_two_places() -> None:
    """`areaM2` phải là **số** JSON hai chữ số, không phải chuỗi `Decimal` (N1)."""
    out = project_summary_out(_project(), _rollup(area_m2=Decimal("12.345")), [_user()])
    dumped = out.model_dump(by_alias=True)
    assert isinstance(dumped["areaM2"], float)
    assert dumped["areaM2"] == 12.35


def test_summary_without_floors_omits_default_floor_id() -> None:
    """Dự án 0 tầng: `defaultFloorId` vắng, `areaM2` là 0 chứ không `null`."""
    dumped = project_summary_out(_project(), _rollup(), [_user()]).model_dump(by_alias=True)
    assert "defaultFloorId" not in dumped
    assert dumped["areaM2"] == 0
    assert set(dumped) == {
        "id",
        "name",
        "floorCount",
        "areaM2",
        "status",
        "wallsReviewedCount",
        "wallsTotalCount",
        "updatedAt",
        "members",
    }


def test_summary_carries_counts_and_default_floor() -> None:
    """Dự án có tầng: đủ số đếm, `defaultFloorId` và `members` chỉ có `id`, `name`."""
    rollup = _rollup(
        floor_count=2,
        area_m2=Decimal("40.00"),
        walls_total=10,
        walls_reviewed=10,
        status="done",
        legacy_status="approved",
        default_floor_id="L-0000000001",
    )
    dumped = project_summary_out(_project(), rollup, [_user()]).model_dump(by_alias=True)
    assert dumped["defaultFloorId"] == "L-0000000001"
    assert (dumped["floorCount"], dumped["wallsReviewedCount"], dumped["wallsTotalCount"]) == (2, 10, 10)
    assert dumped["members"] == [{"id": _user().id, "name": "Chị Hà"}]


def test_summary_member_out_drops_email() -> None:
    """N1 không lộ email (khác #24): `members[]` chỉ `{id, name}` strict."""
    assert set(summary_member_out(_user()).model_dump(by_alias=True)) == {"id", "name"}
