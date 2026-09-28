"""Hàm dùng chung của test phép đo và khuôn (B2-07): đường, thân FE thật, mồi dữ liệu, đọc lại.

`headers_of`, `seed_project`, `FORBIDDEN_ROLE` nhập lại từ B2-01 thay vì chép (R-07). Không phải
file test và không phải `conftest.py`: mỗi test nhập tên nó cần.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Final

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.projects.tests.test_routes_common import FORBIDDEN_ROLE, headers_of, project_path, seed_project
from packages.db.models.measurements import MeasurementRow
from packages.db.models.projects import Project

__all__ = [
    "FORBIDDEN_ROLE",
    "LIMIT_TEST",
    "floor_area_body",
    "headers_of",
    "measurement_path",
    "measurement_rows",
    "measurements_path",
    "point_body",
    "post_raw",
    "project_updated_at",
    "record_body",
    "seed_project",
    "with_env",
]

LIMIT_TEST: Final = 3
"""Trần dùng cho C15 và các test biên: luôn nhỏ hơn mặc định (1000, 500)."""


def measurements_path(project_id: str) -> str:
    """`/api/projects/{project_id}/measurements` — đường #16, #17."""
    return f"{project_path(project_id)}/measurements"


def measurement_path(project_id: str, measurement_id: str) -> str:
    """`/api/projects/{project_id}/measurements/{measurement_id}` — đường #18."""
    return f"{measurements_path(project_id)}/{measurement_id}"


def point_body(x: float, y: float, z: float | None = None) -> dict[str, float]:
    """Một điểm trên dây; `z` vắng thì **vắng khoá** (FE `MeasurePoint`)."""
    point = {"x": x, "y": y}
    if z is not None:
        point["z"] = z
    return point


def record_body(
    id: str = "MS-0001",
    *,
    name: str = "Chiều rộng phòng khách",
    mode: str = "pointToPoint",
    points: list[dict[str, float]] | None = None,
    raw_value_mm: float = 3000.5,
) -> dict[str, Any]:
    """Thân FE thật của #17: `pointToPoint` 2 điểm không `z` (mặc định)."""
    return {
        "id": id,
        "name": name,
        "mode": mode,
        "points": points if points is not None else [point_body(0, 0), point_body(3000.5, 0)],
        "rawValueMm": raw_value_mm,
    }


def floor_area_body(id: str = "MS-0002") -> dict[str, Any]:
    """Thân FE thật của `floorArea`: 3 điểm có `z`, `rawValueMm` là mm²."""
    points = [point_body(0, 0, 0), point_body(4000, 0, 0), point_body(4000, 3000.25, 0)]
    return record_body(id, name="Diện tích sàn", mode="floorArea", points=points, raw_value_mm=6_000_125.0)


async def post_raw(client: httpx.AsyncClient, path: str, headers: dict[str, str], raw: str) -> httpx.Response:
    """POST thân JSON **thô** — để gửi `NaN`, thứ `json=` của httpx từ chối tuần tự hoá."""
    return await client.post(path, content=raw.encode(), headers=headers | {"Content-Type": "application/json"})


async def measurement_rows(sessionmaker: async_sessionmaker[AsyncSession], project_id: str) -> list[MeasurementRow]:
    """Mọi dòng `measurements` của dự án, đọc qua **session mới** (K22)."""
    async with sessionmaker() as session:
        stmt = select(MeasurementRow).where(MeasurementRow.project_id == project_id)
        return list((await session.execute(stmt.order_by(MeasurementRow.measurement_id))).scalars())


async def project_updated_at(sessionmaker: async_sessionmaker[AsyncSession], project_id: str) -> datetime:
    """`projects.updated_at` hiện tại — dấu vết của `touch_project` mà không cần mock."""
    async with sessionmaker() as session:
        return (await session.execute(select(Project.updated_at).where(Project.id == project_id))).scalar_one()


@contextmanager
def with_env(monkeypatch: pytest.MonkeyPatch, reset: Callable[[], None], **env: int) -> Iterator[None]:
    """Đặt biến môi trường của trần rồi xoá cache cấu hình; xoá lại khi ra (monkeypatch tự trả env ở cuối test)."""
    for key, value in env.items():
        monkeypatch.setenv(key, str(value))
    reset()
    try:
        yield
    finally:
        reset()
