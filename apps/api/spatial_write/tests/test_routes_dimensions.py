"""#35 nhận `body.dimensions` (BUG-577): lưu duyệt kích thước, N16 trả lại, A5 và `levelId` bị chặn."""

from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.projects.tests.test_routes_common import headers_of
from apps.api.spatial_read.tests._helpers import make_scene
from apps.api.spatial_write.tests._helpers import log_rows, make_dimension, review, simple_layer
from apps.api.spatial_write.tests._route_helpers import layer_path, put_layer
from packages.testing.factories.auth import make_user


def _dimension(level_id: str, source: str = "human", reviewed: bool = True) -> dict[str, Any]:
    """Một `DimensionSchema` dạng dây với dấu duyệt `source`/`reviewed` (mặc định người đã duyệt)."""
    wire = make_dimension(level_id).model_dump(mode="json", by_alias=True, exclude_none=True)
    wire.update(review(source=source, reviewed=reviewed))
    return wire


async def test_put_dimensions_persisted_and_read_back(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Chỉ gửi `dimensions` → 200 `revision 1`; N16 trả đúng chuỗi kích thước đã duyệt."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    payload = {"baseVersion": 0, "body": {"dimensions": [_dimension(floor.level_id)]}}

    response = await put_layer(api_client, scene.project.id, floor.level_id, scene.owner, payload)

    assert response.status_code == 200
    assert response.json()["revision"] == 1
    read = await api_client.get(layer_path(scene.project.id, floor.level_id), headers=headers_of(scene.owner))
    assert [(d["id"], d["reviewed"], d["valueMm"]) for d in read.json()["dimensions"]] == [("M-TESTDIM001", True, 1000)]


async def test_put_dimensions_ai_reviewed_forbidden(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """A5: `source:'ai'` kèm `reviewed:true` → 422 `REVIEW_BY_AI_FORBIDDEN`, `field` trỏ vào mục."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    payload = {"baseVersion": 0, "body": {"dimensions": [_dimension(floor.level_id, source="ai", reviewed=True)]}}

    response = await put_layer(api_client, scene.project.id, floor.level_id, scene.owner, payload)

    assert response.status_code == 422
    assert response.json()["code"] == "REVIEW_BY_AI_FORBIDDEN"
    assert response.json()["field"] == "body.dimensions.0.reviewed"


async def test_put_dimensions_foreign_level_rejected(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`levelId` của kích thước khác tầng đang ghi → 422 `LAYER_LEVEL_MISMATCH`."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    payload = {"baseVersion": 0, "body": {"dimensions": [_dimension("L-OTHER00001")]}}

    response = await put_layer(api_client, scene.project.id, floor.level_id, scene.owner, payload)

    assert response.status_code == 422
    assert response.json()["code"] == "LAYER_LEVEL_MISMATCH"


async def _dimension_ids(api_client: httpx.AsyncClient, scene: Any, level_id: str) -> list[str]:
    """Các `id` kích thước N16 trả lại cho tầng `level_id`, theo thứ tự lưu."""
    read = await api_client.get(layer_path(scene.project.id, level_id), headers=headers_of(scene.owner))
    return [d["id"] for d in read.json()["dimensions"]]


async def test_put_empty_dimensions_clears_and_absent_keeps(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`dimensions: []` xoá hết; thân chỉ có `scale` (không gửi `dimensions`) giữ nguyên danh sách."""
    scene = await make_scene(db_session)
    level_id = scene.floors[0].level_id
    put = scene.project.id, level_id, scene.owner
    await put_layer(api_client, *put, {"baseVersion": 0, "body": {"dimensions": [_dimension(level_id)]}})
    kept = await put_layer(
        api_client,
        *put,
        {
            "baseVersion": 1,
            "body": {"layer": simple_layer(level_id).model_dump(mode="json", by_alias=True, exclude_none=True)},
        },
    )
    assert kept.status_code == 200
    assert await _dimension_ids(api_client, scene, level_id) == ["M-TESTDIM001"]

    cleared = await put_layer(api_client, *put, {"baseVersion": kept.json()["revision"], "body": {"dimensions": []}})

    assert cleared.status_code == 200
    assert await _dimension_ids(api_client, scene, level_id) == []


async def test_put_duplicate_dimension_ids_rejected(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Hai mục cùng `id` trong thân → 422 `VALIDATION`, `field` trỏ vào mục trùng; không lưu gì."""
    scene = await make_scene(db_session)
    level_id = scene.floors[0].level_id
    payload = {"baseVersion": 0, "body": {"dimensions": [_dimension(level_id), _dimension(level_id)]}}

    response = await put_layer(api_client, scene.project.id, level_id, scene.owner, payload)

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"
    assert response.json()["field"] == "body.dimensions.1.id"


async def test_put_dimensions_logs_rows_per_dimension_id(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Mới = mỗi trường một dòng; chỉ đổi dấu duyệt = một dấu chạm `value_mm`; `[]` = `__deleted__`."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    put = scene.project.id, floor.level_id, scene.owner
    unreviewed = _dimension(floor.level_id, source="ai", reviewed=False)
    await put_layer(api_client, *put, {"baseVersion": 0, "body": {"dimensions": [unreviewed]}})
    await put_layer(api_client, *put, {"baseVersion": 1, "body": {"dimensions": [_dimension(floor.level_id)]}})
    await put_layer(api_client, *put, {"baseVersion": 2, "body": {"dimensions": []}})
    await db_session.commit()

    rows = await log_rows(db_session, floor.pk)

    by_revision = {n: [(r.entity_type, r.entity_id, r.field) for r in rows if r.revision == n] for n in (1, 2, 3)}
    assert {field for _, _, field in by_revision[1]} == {"value_mm", "reference_ids"}
    assert by_revision[2] == [("dimension", "M-TESTDIM001", "value_mm")]
    assert by_revision[3] == [("dimension", "M-TESTDIM001", "__deleted__")]


async def test_put_dimensions_stale_base_conflicts(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """A duyệt kích thước; B cầm base cũ, chỉ gửi `dimensions` → 409 `VERSION_CONFLICT` nêu kích thước đó."""
    second = await make_user(db_session, name="Người thứ hai")
    scene = await make_scene(db_session, members=[second])
    level_id = scene.floors[0].level_id
    project_id = scene.project.id
    first = await put_layer(
        api_client,
        project_id,
        level_id,
        scene.owner,
        {"baseVersion": 0, "body": {"dimensions": [_dimension(level_id)]}},
    )
    assert first.status_code == 200

    stale = await put_layer(api_client, project_id, level_id, second, {"baseVersion": 0, "body": {"dimensions": []}})

    assert stale.status_code == 409
    assert stale.json()["code"] == "VERSION_CONFLICT"
    changes = stale.json()["remoteChanges"]
    assert len(changes) >= 1
    assert {(c["entityType"], c["entityId"]) for c in changes} == {("dimension", "M-TESTDIM001")}
