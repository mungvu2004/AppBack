"""Seed toà mẫu A14 cho dev/ci: một dự án, bốn tầng, mỗi tầng một tài liệu không gian (B3-02 [5]).

`.importlinter` `db-isolated` cấm `packages.db` nhập `apps.api`, nên seed gọi ba hàm thuần
`document_to_json`, `layer_counts`, `entity_ids` của `packages.domain.spatial` — chính các hàm
mà `apps.api.spatial_read` (`codec`, `counts`) chuyển tiếp, nên hai phía không thể lệch nhau.

Idempotent bằng khoá tự nhiên: mọi `INSERT` là `ON CONFLICT DO NOTHING`; `floors.pk` do
DB cấp nên tầng tra lại theo `(project_id, level_id)` thay vì ép `pk`. Không tạo người
dùng hay thành viên: seed chạy trong `migrate_check` khi chưa có `users`.
"""

from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.text import nfc
from packages.db.models.floors import FloorRow
from packages.db.models.projects import Project, ProjectFloorSummary
from packages.db.models.spatial import FloorDocumentRow, FloorEntityIdRow
from packages.domain.spatial import (
    Level,
    SpatialGraph,
    SpatialLayer,
    document_to_json,
    entity_ids,
    layer_counts,
    polygon_area_m2,
    sample_building,
)

ORDER: Final = 50
ENVS: Final = frozenset({"dev", "ci"})
SEED_PROJECT_ID: Final = "prj_01JB302" + "0" * 19
SEED_ACTOR: Final = "system:seed"
_SCHEMA_VERSION: Final = 1
"""Bằng `documents.DOCUMENT_SCHEMA_VERSION` (test tương đương kiểm)."""


def build_sample_building() -> SpatialGraph:
    """Toà mẫu A14 với chuỗi tiếng Việt, diện tích phòng đo thật, không trục và không ghi chú.

    Giữ nguyên mọi id và toạ độ của `sample_building()`; `areaM2` phòng tính lại bằng
    `polygon_area_m2` (17,00, không giữ 27,6 khai sai của phòng cuối, A14).
    """
    graph = sample_building()
    levels = tuple(level.model_copy(update={"name": nfc(f"Tầng {i + 1}")}) for i, level in enumerate(graph.levels))
    rooms = tuple(
        room.model_copy(update={"name": nfc(f"Phòng ngủ {i + 1}"), "area_m2": float(polygon_area_m2(room.outline))})
        for i, room in enumerate(graph.rooms)
    )
    return graph.model_copy(update={"levels": levels, "rooms": rooms, "axes": (), "notes": ()})


def _layer_of(graph: SpatialGraph, level: Level) -> SpatialLayer:
    """Lớp của một tầng: thực thể cùng `levelId`, ô mở theo tường chủ."""
    walls = tuple(wall for wall in graph.walls if wall.level_id == level.id)
    wall_ids = {wall.id for wall in walls}
    return SpatialLayer(
        walls=walls,
        openings=tuple(opening for opening in graph.openings if opening.wall_id in wall_ids),
        rooms=tuple(room for room in graph.rooms if room.level_id == level.id),
        furniture=tuple(item for item in graph.furniture if item.level_id == level.id),
    )


async def _floor_pks(session: AsyncSession, level_ids: list[str]) -> dict[str, int]:
    """`pk` của các tầng seed chưa xoá, theo `level_id`."""
    stmt = select(FloorRow.level_id, FloorRow.pk).where(
        FloorRow.project_id == SEED_PROJECT_ID, FloorRow.level_id.in_(level_ids), FloorRow.deleted_at.is_(None)
    )
    return {level_id: pk for level_id, pk in (await session.execute(stmt)).all()}


async def seed(session: AsyncSession) -> None:
    """Chèn dự án, tầng, dòng đếm, tài liệu và id thực thể của toà mẫu; chạy lại không đổi gì."""
    graph = build_sample_building()
    await session.execute(
        insert(Project)
        .values(id=SEED_PROJECT_ID, name=graph.building.name, address=graph.building.address, created_by=SEED_ACTOR)
        .on_conflict_do_nothing()
    )
    await session.execute(
        insert(FloorRow)
        .values(
            [
                {
                    "project_id": SEED_PROJECT_ID,
                    "level_id": level.id,
                    "name": level.name,
                    "floor_order": level.order,
                    "elevation_mm": level.elevation_mm,
                    "height_mm": level.height_mm,
                    "created_by": SEED_ACTOR,
                }
                for level in graph.levels
            ]
        )
        .on_conflict_do_nothing()
    )
    pks = await _floor_pks(session, [level.id for level in graph.levels])
    summaries: list[dict[str, Any]] = []
    documents: list[dict[str, Any]] = []
    entity_rows: list[dict[str, Any]] = []
    for level in graph.levels:
        layer = _layer_of(graph, level)
        dimensions = tuple(item for item in graph.dimensions if item.level_id == level.id)
        counts = layer_counts(layer)
        summaries.append(
            {
                "project_id": SEED_PROJECT_ID,
                "floor_level_id": level.id,
                "floor_order": level.order,
                "walls_total": counts.walls_total,
                "walls_reviewed": counts.walls_reviewed,
                "area_m2": counts.area_m2,
            }
        )
        documents.append(
            {
                "floor_pk": pks[level.id],
                "revision": 0,
                "schema_version": _SCHEMA_VERSION,
                "document": document_to_json(layer, (), dimensions),
                "scale_source": "none",
            }
        )
        entity_rows += [
            {"project_id": SEED_PROJECT_ID, "entity_id": entity_id, "floor_pk": pks[level.id]}
            for entity_id in sorted(entity_ids(layer))
        ]
    for model, rows in (
        (ProjectFloorSummary, summaries),
        (FloorDocumentRow, documents),
        (FloorEntityIdRow, entity_rows),
    ):
        await session.execute(insert(model).values(rows).on_conflict_do_nothing())
