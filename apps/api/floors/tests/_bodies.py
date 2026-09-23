"""Thân FE thật, đường và tiện ích dùng chung cho `test_routes_*.py` của tầng (B2-03 việc T).

Route, model, factory của B2-03 (`router.py`, `service.py`, `lookup.py`,
`packages/db/models/floors.py`, `packages/testing/factories/floors.py`) chưa tồn tại trên
nhánh này — việc R/D chạy song song trên nhánh khác. Mọi hàm ở đây chỉ dựng dữ liệu, thân
request và đường theo hợp đồng `prompts/B2-03.md` [2], [6], [8]; import tên của R/D chỉ để
đúng chữ ký đã chốt (`dinh-chinh.md` #9), không chạy được cho tới khi hợp nhất.

`principal_of`, `headers_of`, `FORBIDDEN_ROLE`, `project_path`, `seed_project` nhập lại từ
B2-01 (`apps.api.projects.tests.test_routes_common`) thay vì chép, theo R-06/R-07.
"""

import secrets
from collections.abc import Sequence
from typing import Any, Final

from packages.db.models.floors import FloorRow
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.projects.tests.test_routes_common import (
    FORBIDDEN_ROLE,
    headers_of,
    principal_of,
    project_path,
    seed_project,
)
from packages.db.models.projects import ProjectFloorSummary

PROJECTS_PATH: Final = "/api/projects"
REORDER_PATH: Final = "/api/floors/reorder"
FLOORS_MAX_TEST: Final = 3
"""Trần tầng dùng cho C15 và các test biên khác — luôn nhỏ hơn mặc định 50 (dinh-chinh.md #8)."""


def floors_path(project_id: str) -> str:
    """`/api/projects/{project_id}/floors` — đường #10 (POST), #12 (GET)."""
    return f"{project_path(project_id)}/floors"


def floor_path(floor_id: str) -> str:
    """`/api/floors/{floor_id}` — đường #11 (DELETE)."""
    return f"/api/floors/{floor_id}"


def spatial_path(project_id: str, floor_id: str) -> str:
    """`/api/projects/{project_id}/floors/{floor_id}/spatial` — đường #34 (PATCH)."""
    return f"{project_path(project_id)}/floors/{floor_id}/spatial"


def new_level_id() -> str:
    """Id tầng hợp lệ ngẫu nhiên, khớp `is_spatial_id("level", …)` = `L-[0-9A-Z]{10,64}`."""
    return f"L-{secrets.token_hex(6).upper()}"


def floor_body(
    *,
    id: str | None = None,
    name: str = "Tầng trệt",
    order: int = 0,
    elevation_mm: int | float = 0,
    height_mm: int | float = 3000,
    area_m2: float | None = None,
    drawings: Sequence[Any] = (),
) -> dict[str, Any]:
    """Thân FE thật của #10/#34 (`floorWriteBodyOf` + `id`, `src/api/client.ts:751-759,903-909`).

    `drawings`, `areaM2` là hai khoá server **nhận rồi bỏ** (W18) — có mặt để test C17/C08
    dựng đúng hình dạng FE gửi, không phải để server đọc.
    """
    body: dict[str, Any] = {
        "id": id if id is not None else new_level_id(),
        "name": name,
        "order": order,
        "elevationMm": elevation_mm,
        "heightMm": height_mm,
        "drawings": list(drawings),
    }
    if area_m2 is not None:
        body["areaM2"] = area_m2
    return body


async def live_floor_row(
    sessionmaker: async_sessionmaker[AsyncSession], *, project_id: str, level_id: str
) -> FloorRow | None:
    """Dòng `floors` chưa xoá của `(project_id, level_id)`, đọc qua **session mới** (K22)."""
    async with sessionmaker() as session:
        return (
            await session.execute(
                select(FloorRow).where(
                    FloorRow.project_id == project_id,
                    FloorRow.level_id == level_id,
                    FloorRow.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()


async def summary_row(
    sessionmaker: async_sessionmaker[AsyncSession], *, project_id: str, floor_level_id: str
) -> ProjectFloorSummary | None:
    """Dòng `project_floor_summaries` của một tầng (ẩn hay không), đọc qua **session mới** (K22)."""
    async with sessionmaker() as session:
        return (
            await session.execute(
                select(ProjectFloorSummary).where(
                    ProjectFloorSummary.project_id == project_id,
                    ProjectFloorSummary.floor_level_id == floor_level_id,
                )
            )
        ).scalar_one_or_none()


__all__ = [
    "FLOORS_MAX_TEST",
    "FORBIDDEN_ROLE",
    "PROJECTS_PATH",
    "REORDER_PATH",
    "floor_body",
    "floor_path",
    "floors_path",
    "headers_of",
    "live_floor_row",
    "new_level_id",
    "principal_of",
    "project_path",
    "seed_project",
    "spatial_path",
    "summary_row",
]
