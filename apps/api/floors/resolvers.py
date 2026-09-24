"""Resolver đường phẳng của tầng (B2-03 [2] "Giao diện công khai", [6] "Resolver").

Cả hai chạy **trước** kiểm thành viên của `require_project`, không khoá, một truy vấn:
lỗi của resolver thắng ngay cả khi người gọi không phải thành viên dự án nào cả, và tầng
thuộc dự án người gọi không là thành viên **không được tính** (không lộ tồn tại, K08).
"""

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from apps.api.core.auth import Principal
from apps.api.floors.errors import FLOOR_ID_AMBIGUOUS, FLOOR_REORDER_MISMATCH
from apps.api.floors.settings import get_floors_settings
from packages.core.error_codes import NOT_FOUND, VALIDATION
from packages.core.ids import is_spatial_id
from packages.db.models.floors import FloorRow
from packages.db.models.projects import Project, ProjectMembership


async def _member_floor_projects(db: AsyncSession, level_ids: list[str], user_id: str) -> list[tuple[str, str]]:
    """`(project_id, level_id)` của mọi tầng chưa xoá, dự án chưa xoá, mà `user_id` là thành viên."""
    stmt = (
        select(FloorRow.project_id, FloorRow.level_id)
        .join(Project, Project.id == FloorRow.project_id)
        .join(ProjectMembership, ProjectMembership.project_id == FloorRow.project_id)
        .where(
            FloorRow.level_id.in_(level_ids),
            FloorRow.deleted_at.is_(None),
            Project.deleted_at.is_(None),
            ProjectMembership.user_id == user_id,
        )
    )
    return [(row.project_id, row.level_id) for row in (await db.execute(stmt)).all()]


def _single_project(rows: list[tuple[str, str]]) -> str:
    """Đúng một dự án chứa tầng trong `rows`; 0 → 404, > 1 → 409.

    Tách khỏi `project_of_floor` (hàm đồng bộ, gọi ngay sau `await`): `coverage.py` không đo
    đúng nhánh nằm ngay sau một `await` của SQLAlchemy async (greenlet, B2-01 `service.py`).
    """
    project_ids = {project_id for project_id, _ in rows}
    if not project_ids:
        raise NOT_FOUND.error(resource="floor")
    if len(project_ids) > 1:
        raise FLOOR_ID_AMBIGUOUS.error()
    return next(iter(project_ids))


async def project_of_floor(request: Request, principal: Principal, db: AsyncSession) -> str:
    """`{floor_id}` → dự án; sai mẫu hoặc không khớp tầng nào → 404, khớp > 1 dự án → 409 (#11, #13)."""
    floor_id = request.path_params["floor_id"]
    if not isinstance(floor_id, str) or not is_spatial_id("level", floor_id):
        raise NOT_FOUND.error(resource="floor")
    rows = await _member_floor_projects(db, [floor_id], principal.user_id)
    return _single_project(rows)


def _parsed_floor_ids(payload: Any, floors_max: int) -> list[str]:
    """`payload["floorIds"]` là mảng chuỗi 1-`floors_max` phần tử, không trùng; sai → `ValueError`.

    Khoá lạ ngoài `floorIds` → `ValueError` (C03, cùng luật `extra="forbid"` của `WireRequest`
    mà `FloorReorderIn` khai cho OpenAPI — thân này được đọc thô nên phải tự kiểm lại).
    """
    if not isinstance(payload, dict):
        raise ValueError("thân phải là object")
    if set(payload) - {"floorIds"}:
        raise ValueError(f"khoá lạ trong thân: {sorted(set(payload) - {'floorIds'})}")
    floor_ids = payload.get("floorIds")
    if (
        not isinstance(floor_ids, list)
        or not 1 <= len(floor_ids) <= floors_max
        or not all(isinstance(item, str) for item in floor_ids)
        or len(set(floor_ids)) != len(floor_ids)
    ):
        raise ValueError("floorIds phải là mảng chuỗi 1..floors_max phần tử, không trùng")
    return floor_ids


async def _read_floor_ids(request: Request, floors_max: int) -> list[str]:
    """Thân thô (chưa qua Pydantic) của #13; lỗi giải mã hay hình dạng sai → 422 `field:"floorIds"`."""
    try:
        payload = await request.json()
        return _parsed_floor_ids(payload, floors_max)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise VALIDATION.error(field="floorIds") from exc


def _complete_projects(rows: list[tuple[str, str]], floor_ids: list[str]) -> list[str]:
    """Dự án chứa **đủ** mọi id trong `floor_ids` (gom theo `project_id`, tương đương `GROUP BY … HAVING`)."""
    by_project: dict[str, set[str]] = {}
    for project_id, level_id in rows:
        by_project.setdefault(project_id, set()).add(level_id)
    wanted = set(floor_ids)
    return [project_id for project_id, level_ids in by_project.items() if level_ids == wanted]


def _matching_project(rows: list[tuple[str, str]], floor_ids: list[str]) -> str:
    """Dự án chứa đủ mọi id của `floor_ids`; 0 khớp → 404, > 1 dự án → 409, tập lệch → 422.

    Tách khỏi `project_of_floor_list` cùng lý do `_single_project` ở trên (greenlet + coverage).
    """
    if not rows:
        raise NOT_FOUND.error(resource="floor")
    complete = _complete_projects(rows, floor_ids)
    if len(complete) > 1:
        raise FLOOR_ID_AMBIGUOUS.error()
    if not complete:
        raise FLOOR_REORDER_MISMATCH.error(field="floorIds")
    return complete[0]


async def project_of_floor_list(request: Request, principal: Principal, db: AsyncSession) -> str:
    """`floorIds` của #13 → dự án chứa đủ mọi id; 0 khớp → 404, > 1 dự án → 409, tập lệch → 422."""
    floor_ids = await _read_floor_ids(request, get_floors_settings().floors_max)
    rows = await _member_floor_projects(db, floor_ids, principal.user_id)
    return _matching_project(rows, floor_ids)
