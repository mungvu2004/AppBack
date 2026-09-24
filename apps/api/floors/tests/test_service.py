"""Test trực tiếp một số nhánh của `service.py` mà HTTP + đua thật không đo được ổn định
(việc gộp B2-03): hai coroutine chạy đồng thời qua `asyncio.gather` (như `test_routes_create.py`
`__C14`) khiến `coverage.py` không đo đúng nhánh nằm ngay sau một `await` bên trong greenlet
của SQLAlchemy async — hành vi đã đúng (test C14 vẫn `{201, 409}`), chỉ thiếu dòng đo. Gọi
thẳng `service.create_floor`/`_insert_floor` **tuần tự** (không đua) đóng góp đúng nhánh đó
mà không phụ thuộc thời điểm hệ điều hành lập lịch coroutine.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.auth import Principal
from apps.api.floors import service
from apps.api.floors.schemas import FloorCreateIn, FloorPatchIn
from apps.api.floors.settings import get_floors_settings, reset_floors_settings_cache
from apps.api.floors.tests._bodies import floor_body, new_level_id, seed_project
from packages.core.errors import AppError
from packages.testing.factories.auth import make_user
from packages.testing.factories.floors import make_floor
from packages.testing.fixtures.clock import FakeClock


def _principal(user_id: str) -> Principal:
    """`Principal` engineer tối thiểu cho lời gọi thẳng `service.*` (không qua HTTP)."""
    return Principal(user_id=user_id, session_id="sid-test", role="engineer")


async def test_create_floor_rejects_duplicate_id_sequentially(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Gọi `create_floor` hai lần tuần tự cùng `id` → lần hai 409 `FLOOR_ID_TAKEN` (`_check_not_taken`)."""
    user = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=user)
    principal = _principal(user.id)
    body = FloorCreateIn.model_validate(floor_body())

    await service.create_floor(db_session, project.id, body, principal, fake_clock, app=None)
    with pytest.raises(AppError) as caught:
        await service.create_floor(db_session, project.id, body, principal, fake_clock, app=None)

    assert caught.value.code.code == "FLOOR_ID_TAKEN"


async def test_insert_floor_translates_unique_violation_to_floor_id_taken(db_session: AsyncSession) -> None:
    """`_insert_floor` gọi thẳng hai lần (bỏ qua `_check_not_taken`) → `IntegrityError` dịch thành 409.

    Mô phỏng đúng cửa sổ đua mà `_check_not_taken` không chặn được (hai giao dịch cùng vượt
    qua bước kiểm trước khi bên kia `INSERT`) — con đường phòng thủ thứ hai của #10 (B2-03 [6]).
    """
    user = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=user)
    principal = _principal(user.id)
    body = FloorCreateIn.model_validate(floor_body())

    await service._insert_floor(db_session, project.id, body, principal)
    with pytest.raises(AppError) as caught:
        await service._insert_floor(db_session, project.id, body, principal)

    assert caught.value.code.code == "FLOOR_ID_TAKEN"


async def test_insert_floor_reraises_non_unique_integrity_errors(db_session: AsyncSession) -> None:
    """Vi phạm CHECK (không phải `uq_floors_level`) → ném lại nguyên `IntegrityError`, không đổi mã.

    `unique_violation(exc)` trả `None` cho ràng buộc khác; `_raise_taken_if_unique_violation`
    phải để lỗi hạ tầng nổi lên chứ không lặng lẽ biến thành 409 sai nghĩa.
    """
    user = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=user)
    principal = _principal(user.id)
    # `model_construct` bỏ qua validator của schema để dựng giá trị vi phạm CHECK `height_mm` của DB.
    bad_body = FloorCreateIn.model_construct(
        id=new_level_id(), name="Tầng lỗi", order=0, elevation_mm=0, height_mm=999_999, drawings=[], area_m2=None
    )

    with pytest.raises(IntegrityError, match="height_mm_range"):
        await service._insert_floor(db_session, project.id, bad_body, principal)


async def test_create_floor_rejects_over_limit_sequentially(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """`FLOORS_MAX` (env override) đạt trần → 422 `FLOOR_LIMIT_REACHED` (`_check_not_over_limit`)."""
    reset_floors_settings_cache()
    user = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=user)
    principal = _principal(user.id)
    for index in range(get_floors_settings().floors_max):
        await make_floor(db_session, project=project, order=index)

    with pytest.raises(AppError) as caught:
        await service.create_floor(
            db_session, project.id, FloorCreateIn.model_validate(floor_body()), principal, fake_clock, app=None
        )

    assert caught.value.code.code == "FLOOR_LIMIT_REACHED"


async def test_delete_floor_missing_raises_not_found(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """`level_id` không tồn tại → 404 `resource:"floor"` (`_checked_floor`)."""
    user = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=user)
    principal = _principal(user.id)

    with pytest.raises(AppError) as caught:
        await service.delete_floor(db_session, project.id, new_level_id(), principal, fake_clock, app=None)

    assert caught.value.code.code == "NOT_FOUND"


async def test_delete_floor_returns_snapshot_before_delete(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Xoá thành công → trả ảnh chụp tên tầng ngay trước khi xoá."""
    user = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=user)
    floor = await make_floor(db_session, project=project, name="Sắp xoá", order=0)
    principal = _principal(user.id)

    snapshot = await service.delete_floor(db_session, project.id, floor.level_id, principal, fake_clock, app=None)

    assert snapshot.name == "Sắp xoá"


async def test_reorder_floors_raises_mismatch_when_set_differs(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Tập `floor_ids` không khớp tập tầng chưa xoá của dự án → 422 `FLOOR_REORDER_MISMATCH`."""
    user = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=user)
    await make_floor(db_session, project=project, order=0)
    principal = _principal(user.id)

    with pytest.raises(AppError) as caught:
        await service.reorder_floors(
            db_session, project.id, project.name, [new_level_id()], principal, fake_clock, app=None
        )

    assert caught.value.code.code == "FLOOR_REORDER_MISMATCH"


async def test_reorder_floors_applies_new_order_when_changed(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Mảng đảo ngược thứ tự → `floor_order` mới đúng vị trí trong mảng."""
    user = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=user)
    first = await make_floor(db_session, project=project, order=0)
    second = await make_floor(db_session, project=project, order=1)
    principal = _principal(user.id)

    result = await service.reorder_floors(
        db_session, project.id, project.name, [second.level_id, first.level_id], principal, fake_clock, app=None
    )

    assert [floor.id for floor in result] == [second.level_id, first.level_id]


async def test_reorder_floors_noop_when_order_already_matches(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Mảng đúng thứ tự hiện tại → không dòng nào đổi, vẫn 200 đủ tầng (nhánh `if changed` rỗng)."""
    user = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=user)
    first = await make_floor(db_session, project=project, order=0)
    second = await make_floor(db_session, project=project, order=1)
    principal = _principal(user.id)

    result = await service.reorder_floors(
        db_session, project.id, project.name, [first.level_id, second.level_id], principal, fake_clock, app=None
    )

    assert [floor.id for floor in result] == [first.level_id, second.level_id]


async def test_patch_floor_missing_raises_not_found(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """`level_id` không tồn tại → 404 `resource:"floor"` (`_checked_floor`, dùng lại ở #34)."""
    user = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=user)
    principal = _principal(user.id)

    with pytest.raises(AppError) as caught:
        await service.patch_floor(
            db_session, project.id, new_level_id(), FloorPatchIn.model_validate({}), principal, fake_clock, app=None
        )

    assert caught.value.code.code == "NOT_FOUND"


async def test_patch_floor_applies_changed_fields(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Thân có `name` mới, khác hiện trạng → ghi và trả tên mới."""
    user = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=user)
    floor = await make_floor(db_session, project=project, name="Cũ", order=0)
    principal = _principal(user.id)

    result = await service.patch_floor(
        db_session,
        project.id,
        floor.level_id,
        FloorPatchIn.model_validate({"name": "Mới"}),
        principal,
        fake_clock,
        app=None,
    )

    assert result.name == "Mới"


async def test_patch_floor_noop_when_no_field_changes(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Thân `{}` → không ghi gì, trả hiện trạng (nhánh `if changes` rỗng của #34)."""
    user = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=user)
    floor = await make_floor(db_session, project=project, name="Không đổi", order=0)
    principal = _principal(user.id)

    result = await service.patch_floor(
        db_session, project.id, floor.level_id, FloorPatchIn.model_validate({}), principal, fake_clock, app=None
    )

    assert result.name == "Không đổi"


async def test_patch_floor_order_change_updates_summary_orders(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Thân có `order` mới, khác hiện trạng → gọi `set_floor_orders` (nhánh `"order" in changes`)."""
    user = await make_user(db_session, role="engineer")
    project = await seed_project(db_session, owner=user)
    floor = await make_floor(db_session, project=project, order=0)
    await make_floor(db_session, project=project, order=1)
    principal = _principal(user.id)

    result = await service.patch_floor(
        db_session,
        project.id,
        floor.level_id,
        FloorPatchIn.model_validate({"order": 1}),
        principal,
        fake_clock,
        app=None,
    )

    assert result.order == 1
