"""Test hai cổng mở rộng của module dự án (B2-01 [6] "Cổng mở rộng")."""

from collections.abc import Mapping, Sequence

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core import extensions
from apps.api.core.wire import WireModel
from apps.api.projects.parts import (
    FLOOR_DRAWINGS,
    PROJECT_CREATE_FLOORS,
    PROJECT_FLOORS,
    SUBMODULE,
    CreateHook,
    FloorDraft,
    ViewPart,
    create_hook,
    view_part,
)
from packages.core.clock import Clock


class _App:
    """Chỗ treo `override` — `extensions` chỉ cần một object bất kỳ, không phải `FastAPI`."""


@pytest.fixture(autouse=True)
def _test_env(storage_env: None) -> None:
    """`extensions.override` chỉ chạy khi `APP_ENV=test`; `storage_env` đặt biến ấy (B0-04)."""


async def _load(db: AsyncSession, ids: Sequence[str]) -> Mapping[str, Sequence[WireModel]]:
    """`load` giả: không chạm DB, chỉ để phân biệt đúng đối tượng được trả về."""
    return {}


async def _run(
    db: AsyncSession, project_id: str, drafts: Sequence[FloorDraft], principal: object, clock: Clock
) -> None:
    """`run` giả của `CreateHook`."""


def _app_with(*parts: ViewPart | CreateHook) -> _App:
    """App thử đã cắm sẵn `PARTS` (một module giả tên `test`)."""
    app = _App()
    extensions.override(app, SUBMODULE, [("test", list(parts))])
    return app


def test_missing_parts_return_none() -> None:
    """Chưa module nào cắm → `None`, không ném: `ProjectOut.floors` khi đó là `[]`."""
    app = _app_with()
    assert view_part(PROJECT_FLOORS, app=app) is None
    assert create_hook(PROJECT_CREATE_FLOORS, app=app) is None


def test_registered_parts_are_returned_by_kind() -> None:
    """Mỗi cổng trả đúng phần của `kind` mình, không lẫn sang `kind` khác."""
    floors = ViewPart(kind=PROJECT_FLOORS, load=_load)
    drawings = ViewPart(kind=FLOOR_DRAWINGS, load=_load)
    hook = CreateHook(kind=PROJECT_CREATE_FLOORS, run=_run)
    app = _app_with(floors, drawings, hook)
    assert view_part(PROJECT_FLOORS, app=app) is floors
    assert view_part(FLOOR_DRAWINGS, app=app) is drawings
    assert create_hook(PROJECT_CREATE_FLOORS, app=app) is hook


def test_duplicate_kind_raises() -> None:
    """Hai module khai cùng `kind` → `RuntimeError` nêu cả hai, không "ai sau thì thắng"."""
    app = _App()
    part = ViewPart(kind=PROJECT_FLOORS, load=_load)
    extensions.override(app, SUBMODULE, [("mot", [part]), ("hai", [part])])
    with pytest.raises(RuntimeError, match=PROJECT_FLOORS):
        view_part(PROJECT_FLOORS, app=app)


def test_wrong_part_type_raises() -> None:
    """`kind` có thật nhưng sai loại → `RuntimeError`, không lặng lẽ thành "chưa ai cài"."""
    app = _app_with(CreateHook(kind=PROJECT_FLOORS, run=_run))
    with pytest.raises(RuntimeError, match="ViewPart"):
        view_part(PROJECT_FLOORS, app=app)


def test_default_app_falls_back_to_discover() -> None:
    """`app=None` → `discover` (FIX-082: không giả định module nào đã/chưa cài `view_parts.py`,
    K27 — từ B2-03, `apps.api.floors.view_parts` cắm thật vào lượt `discover` toàn cục)."""
    assert extensions.resolve(None, SUBMODULE, "PARTS") == extensions.discover(SUBMODULE, "PARTS")
    assert view_part(PROJECT_FLOORS) == view_part(PROJECT_FLOORS, app=None)
    assert create_hook(PROJECT_CREATE_FLOORS) == create_hook(PROJECT_CREATE_FLOORS, app=None)
