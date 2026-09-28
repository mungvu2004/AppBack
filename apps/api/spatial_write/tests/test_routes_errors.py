"""#35 — ánh xạ lỗi riêng, dấu chạm, idempotency và thua đua **qua HTTP** (B3-03 [8] "đặt tên theo việc").

`test_writer*.py` của việc W đã kiểm các luật này ở mức hàm; ở đây chỉ kiểm phần dây: mã lỗi
nào ra status nào, `field`/`count` có lọt ra thân không, header `Retry-After` có không, và route
`idempotency="off"` có thật sự không chạm bảng `idempotency_records`.
"""

from typing import Final

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.spatial_read.documents import load_document
from apps.api.spatial_read.tests._helpers import make_scene
from apps.api.spatial_write.tests._helpers import log_rows, make_wall, simple_layer, slipping_load
from apps.api.spatial_write.tests._route_helpers import idempotency_count, put_layer, wire, write_body
from packages.db.models.auth import User
from packages.domain.spatial import Opening
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.clock import FakeClock

GHOST_WALL: Final = "W-NOSUCHWALL1"
"""Tường không có trong lớp — ô mở trỏ vào nó là lỗi toàn vẹn `critical` (`missingReference`)."""


def _opening(wall_id: str) -> Opening:
    """Một cánh cửa gắn vào `wall_id`; `Opening` không mang `levelId` nên nó chỉ sống nhờ tường."""
    return Opening.model_validate(
        {
            "id": "D-ROUTEOPEN1",
            "wallId": wall_id,
            "kind": "door",
            "offsetMm": 100,
            "widthMm": 800,
            "heightMm": 2100,
            "sillHeightMm": 0,
            "swing": "left",
            "confidence": 0.8,
            "source": "ai",
            "reviewed": False,
        }
    )


async def test_spatial_write_layer_rejects_base_version_above_current(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`baseVersion` lớn hơn bản ghi hiện tại → 422 `field:"baseVersion"`, không phải 409 (W20)."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]

    response = await put_layer(api_client, scene.project.id, floor.level_id, scene.owner, write_body(7, scale=10.0))

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"
    assert response.json()["field"] == "baseVersion"


async def test_spatial_write_layer_rejects_ai_reviewed_entity(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """A5 (W5): `source="ai"` kèm `reviewed=True` → 422 `REVIEW_BY_AI_FORBIDDEN` trỏ đúng mục."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    payload = write_body(0, layer=simple_layer(floor.level_id))
    payload["body"]["layer"]["walls"][0]["reviewed"] = True

    response = await put_layer(api_client, scene.project.id, floor.level_id, scene.owner, payload)

    assert response.status_code == 422
    assert response.json()["code"] == "REVIEW_BY_AI_FORBIDDEN"
    assert response.json()["field"] == "body.layer.walls.0.reviewed"


async def test_spatial_write_layer_rejects_wall_of_other_level(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Tường mang `levelId` của tầng khác → 422 `LAYER_LEVEL_MISMATCH`."""
    scene = await make_scene(db_session, floors=2)
    floor, elsewhere = scene.floors

    response = await put_layer(
        api_client,
        scene.project.id,
        floor.level_id,
        scene.owner,
        write_body(0, layer=simple_layer(elsewhere.level_id)),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "LAYER_LEVEL_MISMATCH"
    assert response.json()["field"] == "body.layer.walls.0.levelId"


async def test_spatial_write_layer_rejects_broken_integrity(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Ô mở trỏ tường không có → 422 `LAYER_INTEGRITY_BROKEN` kèm `count` số lỗi `critical`."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    payload = write_body(0, layer=simple_layer(floor.level_id))
    payload["body"]["layer"]["openings"] = [wire(_opening(GHOST_WALL))]

    response = await put_layer(api_client, scene.project.id, floor.level_id, scene.owner, payload)

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "LAYER_INTEGRITY_BROKEN"
    assert body["count"] >= 1


async def test_spatial_write_layer_logs_a_touch_mark_for_a_review(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """A duyệt một tường AI → đúng một dòng `wall`/`thickness_mm`; B gửi base cũ → 409 và việc duyệt còn nguyên."""
    second = await make_user(db_session, name="Người thứ hai")
    scene = await make_scene(db_session, members=[second])
    floor = scene.floors[0]
    floor_pk, level_id, project_id = floor.pk, floor.level_id, scene.project.id
    assert (
        await put_layer(api_client, project_id, level_id, scene.owner, write_body(0, layer=simple_layer(level_id)))
    ).status_code == 200
    reviewed = simple_layer(level_id, walls=(make_wall(level_id, source="human", reviewed=True),))

    approve = await put_layer(api_client, project_id, level_id, scene.owner, write_body(1, layer=reviewed))

    assert approve.status_code == 200
    assert approve.json()["revision"] == 2
    await db_session.commit()
    marks = [row for row in await log_rows(db_session, floor_pk) if row.revision == 2]
    assert [(row.entity_type, row.field) for row in marks] == [("wall", "thickness_mm")]
    stale = await put_layer(api_client, project_id, level_id, second, write_body(0, layer=simple_layer(level_id)))
    assert stale.status_code == 409
    assert len(stale.json()["remoteChanges"]) >= 1
    await db_session.commit()
    document = await load_document(db_session, floor_pk)
    assert document is not None
    assert document.layer.walls[0].reviewed is True


async def test_spatial_write_layer_logs_the_token_subject(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`changedBy` = `sub` của token, `changedByName` = tên **lúc ghi**; đổi tên sau không đổi dòng cũ (K05)."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    floor_pk, level_id, project_id = floor.pk, floor.level_id, scene.project.id
    owner_id, owner_name = scene.owner.id, scene.owner.name
    assert (
        await put_layer(api_client, project_id, level_id, scene.owner, write_body(0, layer=simple_layer(level_id)))
    ).status_code == 200
    await db_session.commit()
    before = {row.id: row.changed_by_name for row in await log_rows(db_session, floor_pk)}
    assert set(before.values()) == {owner_name}

    await db_session.execute(update(User).where(User.id == owner_id).values(name="Tên Mới"))
    await db_session.commit()
    later = await put_layer(api_client, project_id, level_id, scene.owner, write_body(1, scale=10.0))

    assert later.status_code == 200
    await db_session.commit()
    rows = await log_rows(db_session, floor_pk)
    assert {row.changed_by for row in rows} == {owner_id}
    assert {row.id: row.changed_by_name for row in rows if row.id in before} == before


async def test_spatial_write_layer_ignores_the_idempotency_key(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Route GV khai `idempotency="off"`: lượt lặp cùng khoá đi qua C09b, bảng nhận việc vẫn rỗng."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    payload = write_body(0, layer=simple_layer(floor.level_id))
    level_id, project_id = floor.level_id, scene.project.id
    headers = {"Idempotency-Key": "01JBQ0000000000000000000AA"}

    first = await put_layer(api_client, project_id, level_id, scene.owner, payload, headers=headers)
    repeat = await put_layer(api_client, project_id, level_id, scene.owner, payload, headers=headers)

    assert (first.status_code, repeat.status_code) == (200, 200)
    assert repeat.json() == first.json()
    await db_session.commit()
    assert await idempotency_count(db_session) == 0


async def test_spatial_write_layer_returns_503_after_losing_every_race(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Thua đua `SPATIAL_WRITE_ATTEMPTS` lần liền → 503 `DEPENDENCY_UNAVAILABLE` + `Retry-After: 1`, không 500.

    Bên chen vào (`slipping_load`) chỉ đổi thứ tự danh sách nên không sinh dòng nhật ký: lượt
    của route vì thế luôn qua được bước 5 rồi mới chết ở `UPDATE`, đúng cảnh 503 mô tả.
    """
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    walls = (make_wall(floor.level_id), make_wall(floor.level_id, entity_id="W-TESTWALL02", length=1500))
    start = simple_layer(floor.level_id, walls=walls)
    assert (
        await put_layer(api_client, scene.project.id, floor.level_id, scene.owner, write_body(0, layer=start))
    ).status_code == 200
    loader = slipping_load(db_sessionmaker, floor=floor, actor=scene.owner, clock=fake_clock)
    monkeypatch.setattr("apps.api.spatial_write.writer.load_document", loader)
    thicker = simple_layer(floor.level_id, walls=tuple(wall.model_copy(update={"thickness_mm": 250}) for wall in walls))

    response = await put_layer(api_client, scene.project.id, floor.level_id, scene.owner, write_body(1, layer=thicker))

    assert response.status_code == 503
    assert response.json()["code"] == "DEPENDENCY_UNAVAILABLE"
    assert response.headers["Retry-After"] == "1"
