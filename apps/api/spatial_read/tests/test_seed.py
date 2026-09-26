"""Seed toà mẫu `packages/db/seeds/spatial.py` trên Postgres thật (B3-02 [5], [8]).

Seed không nhập `apps.api` (`db-isolated`), nên các test "tương đương" ở đây là chỗ duy
nhất kiểm nó không lệch khỏi `codec` và `counts`.
"""

import unicodedata
from typing import Final

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.spatial_read import codec
from apps.api.spatial_read.counts import layer_counts
from apps.api.spatial_read.documents import DOCUMENT_SCHEMA_VERSION, document_from_row
from apps.api.spatial_read.wire import SpatialLayerOut, layer_out
from packages.core.ids import is_id
from packages.db.models.floors import FloorRow
from packages.db.models.projects import Project, ProjectFloorSummary
from packages.db.models.spatial import FloorDocumentRow, FloorEntityIdRow
from packages.db.seeds import apply_seeds, load_seeds
from packages.db.seeds.spatial import ENVS, ORDER, SEED_PROJECT_ID, build_sample_building, seed
from packages.domain.spatial import check_integrity, has_critical, polygon_area_m2

TABLES: Final = (Project, FloorRow, ProjectFloorSummary, FloorDocumentRow, FloorEntityIdRow)


async def _row_counts(db: AsyncSession) -> dict[str, int]:
    """Số dòng của năm bảng seed, theo tên bảng."""
    return {
        model.__tablename__: (await db.execute(select(func.count()).select_from(model))).scalar_one()
        for model in TABLES
    }


def test_seed_is_discovered_for_dev_and_ci_only() -> None:
    """`load_seeds` thấy seed ở `dev`/`ci` với `ORDER=50`, không thấy ở `production`."""
    assert ORDER == 50
    assert sorted(ENVS) == ["ci", "dev"]
    assert "spatial" in [s.name for s in load_seeds("ci")]
    assert "spatial" not in [s.name for s in load_seeds("production")]


def test_sample_building_shape() -> None:
    """Đếm 4/48/16/21/14/34, không trục, không ghi chú, chuỗi NFC, `areaM2` phòng đo thật."""
    graph = build_sample_building()
    assert (len(graph.levels), len(graph.walls), len(graph.openings)) == (4, 48, 16)
    assert (len(graph.furniture), len(graph.rooms), len(graph.dimensions)) == (21, 14, 34)
    assert graph.axes == ()
    assert graph.notes == ()
    assert [level.name for level in graph.levels] == ["Tầng 1", "Tầng 2", "Tầng 3", "Tầng 4"]
    assert graph.rooms[0].name == "Phòng ngủ 1"
    assert (graph.building.name, graph.building.address) == ("Chung cư Hoàng Anh", "12 Nguyễn Huệ, Quận 1")
    assert all(room.area_m2 == float(polygon_area_m2(room.outline)) == 17.0 for room in graph.rooms)
    strings = [graph.building.name, graph.building.address, *(x.name for x in graph.levels + graph.rooms)]
    assert all(unicodedata.is_normalized("NFC", text) for text in strings if text)
    assert is_id("prj", SEED_PROJECT_ID)


async def test_seed_twice_keeps_row_counts(db_session: AsyncSession) -> None:
    """Chạy hai lần: số dòng sau lần 1 và lần 2 bằng nhau (4 tầng, 4 tài liệu, 99 id)."""
    await seed(db_session)
    first = await _row_counts(db_session)
    await apply_seeds(db_session, "ci")
    second = await _row_counts(db_session)
    print(f"seed lần 1: {first}; lần 2: {second}")
    assert (
        first
        == second
        == {
            "projects": 1,
            "floors": 4,
            "project_floor_summaries": 4,
            "floor_documents": 4,
            "floor_entity_ids": 99,
        }
    )


async def test_seed_matches_codec_and_counts(db_session: AsyncSession) -> None:
    """Tương đương: `document`, dòng đếm và id thực thể == kết quả của `codec`/`counts` trên cùng lớp."""
    await seed(db_session)
    project = (await db_session.execute(select(Project))).scalar_one()
    assert (project.id, project.created_by) == (SEED_PROJECT_ID, "system:seed")
    rows = (await db_session.execute(select(FloorDocumentRow).order_by(FloorDocumentRow.floor_pk))).scalars().all()
    assert len(rows) == 4
    for row in rows:
        layer, axes, dimensions = codec.document_from_json(row.document)
        assert row.document == codec.document_to_json(layer, axes, dimensions)
        assert (row.revision, row.scale_source, row.scale_mm_per_px) == (0, "none", None)
        assert row.schema_version == DOCUMENT_SCHEMA_VERSION
        assert document_from_row(row).layer == layer
        assert not has_critical(check_integrity(layer, level_id=None))
        floor = (await db_session.execute(select(FloorRow).where(FloorRow.pk == row.floor_pk))).scalar_one()
        summary = (
            await db_session.execute(
                select(ProjectFloorSummary).where(ProjectFloorSummary.floor_level_id == floor.level_id)
            )
        ).scalar_one()
        counts = layer_counts(layer)
        assert (summary.walls_total, summary.walls_reviewed, summary.area_m2) == (
            counts.walls_total,
            counts.walls_reviewed,
            counts.area_m2,
        )
        ids = set(
            (
                await db_session.execute(
                    select(FloorEntityIdRow.entity_id).where(FloorEntityIdRow.floor_pk == row.floor_pk)
                )
            ).scalars()
        )
        assert ids == codec.entity_ids(layer)
    assert sum(len(dimensions) for dimensions in (codec.document_from_json(r.document)[2] for r in rows)) == 34


async def test_seed_layers_decode_as_wire_models(db_session: AsyncSession) -> None:
    """Mọi lớp seed giải được bằng `SpatialLayerOut` — cột `document` đúng hình dạng N16 gửi đi.

    Kiểm ở đây chứ không ở `test_wire.py`: seed dựng jsonb bằng `model_dump` của miền, không
    qua `codec`, nên đây là chỗ duy nhất bắt được lệch giữa hai đường ghi ấy trước khi FE thấy.
    """
    await seed(db_session)
    rows = (await db_session.execute(select(FloorDocumentRow).order_by(FloorDocumentRow.floor_pk))).scalars().all()
    for row in rows:
        layer = document_from_row(row).layer
        out = layer_out(layer)
        assert SpatialLayerOut.model_validate(out.model_dump(mode="json", by_alias=True)) == out
    assert sum(len(layer_out(document_from_row(row).layer).walls) for row in rows) == 48
