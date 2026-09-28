"""#36 `GET .../versions/{id}` (Đ: C01 C06 C08 C17) và N18 `GET .../snapshot` (Đ: C01 C02 C06 C08 C17).

Postgres thật, thành viên thật, không mock session (K22, K23). Ảnh chụp được dựng bằng
`write_layer` + `create_version` thật rồi đọc lại qua route; ảnh chụp hỏng dựng bằng SQL.
"""

import logging
from typing import Final

import httpx
import pytest
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.spatial_write.tests._helpers import make_dimension, make_wall, simple_layer
from apps.api.spatial_write.tests._route_helpers import make_furniture, wire
from apps.api.versions.tests._helpers import versions_of
from apps.api.versions.tests._route_helpers import (
    SNAPSHOT_LOGGER,
    Corruption,
    call,
    commit_snap,
    corrupt_snapshot,
    make_stage,
    mismatch_logged,
    put_layer,
    read_snapshot,
    read_version,
    versions_path,
)
from packages.db.models.floors import FloorRow
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.clock import FakeClock

ABSENT_VERSION: Final = "ver_01J00000000000000000000000"
"""Đúng mẫu `ver_<ULID>` nhưng không có dòng nào."""


async def test_versions_read_version__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Có `note` → đúng sáu trường cũ, `createdAt` `.sssZ`, `creatorId` là người tạo."""
    stage = await make_stage(db_session)
    await put_layer(db_session, stage, fake_clock, simple_layer(stage.level_id), base=0)
    version = await commit_snap(db_session, stage, fake_clock, note="trạng thái mẫu")

    response = await read_version(api_client, stage, version.id)

    assert response.status_code == 200
    assert response.json() == {
        "id": version.id,
        "projectId": stage.project_id,
        "sequence": 1,
        "createdAt": "2026-01-01T00:00:00.000Z",
        "creatorId": stage.owner.id,
        "note": "trạng thái mẫu",
    }


async def test_versions_read_version__C06(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Admin hệ thống không phải thành viên → 404 `resource:"project"`, không 403 (K08)."""
    stage = await make_stage(db_session)
    version = await commit_snap(db_session, stage, fake_clock)
    outsider = await make_user(db_session, role="admin")
    await db_session.commit()

    response = await read_version(api_client, stage, version.id, outsider)

    assert response.status_code == 404
    assert response.json()["resource"] == "project"


@pytest.mark.parametrize("missing", ["absent", "malformed", "other_project", "soft_deleted_floor"])
async def test_versions_read_version__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, missing: str
) -> None:
    """Id không có, sai mẫu, của dự án khác, hay của tầng đã xoá mềm → 404 `resource:"version"`."""
    stage = await make_stage(db_session)
    other = await make_stage(db_session)
    version_id = {"absent": ABSENT_VERSION, "malformed": "ver_nope"}.get(missing, "")
    if missing == "other_project":
        version_id = (await commit_snap(db_session, other, fake_clock)).id
    elif missing == "soft_deleted_floor":
        version_id = (await commit_snap(db_session, stage, fake_clock)).id
        deleted = update(FloorRow).where(FloorRow.pk == stage.floor.pk).values(deleted_at=fake_clock.now())
        await db_session.execute(deleted)
        await db_session.commit()

    response = await read_version(api_client, stage, version_id)

    assert response.status_code == 404
    assert response.json()["resource"] == "version"


async def test_versions_read_version__C17(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Không `note` → vắng khoá `note`, không phải `null` (W2)."""
    stage = await make_stage(db_session)
    version = await commit_snap(db_session, stage, fake_clock)

    body = (await read_version(api_client, stage, version.id)).json()

    assert "note" not in body
    assert set(body) == {"id", "projectId", "sequence", "createdAt", "creatorId"}


async def test_versions_read_snapshot__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """200 `{versionId, layer, dimensions}`: đúng lớp và kích thước lúc chụp, không phải hiện trạng."""
    stage = await make_stage(db_session)
    wall = make_wall(stage.level_id)
    dimension = make_dimension(stage.level_id, refs=[wall.id])
    layer = simple_layer(stage.level_id, walls=(wall,))
    revision = await put_layer(db_session, stage, fake_clock, layer, base=0, dimensions=[dimension])
    version = await commit_snap(db_session, stage, fake_clock)
    thicker = simple_layer(stage.level_id, walls=(make_wall(stage.level_id, thickness=250),))
    await put_layer(db_session, stage, fake_clock, thicker, base=revision)

    response = await read_snapshot(api_client, stage, version.id)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"versionId", "layer", "dimensions"}
    assert body["versionId"] == version.id
    assert body["layer"]["walls"] == [wire(wall)]
    assert [item["id"] for item in body["dimensions"]] == [dimension.id]


@pytest.mark.parametrize("floor_id", [None, ""])
async def test_versions_read_snapshot__C02(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, floor_id: str | None
) -> None:
    """Thiếu hay rỗng `floorId` → 422 `VALIDATION` `field:"floorId"` (kiểm trước cả 404 của phiên bản)."""
    stage = await make_stage(db_session)
    version = await commit_snap(db_session, stage, fake_clock)

    if floor_id is None:
        path = versions_path(stage.project_id, version.id, "/snapshot")
        response = await call(api_client, "GET", path, stage.owner)
    else:
        response = await read_snapshot(api_client, stage, version.id, floor_id=floor_id)

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"
    assert response.json()["field"] == "floorId"


async def test_versions_read_snapshot__C06(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Người ngoài dự án → 404 `resource:"project"`."""
    stage = await make_stage(db_session)
    version = await commit_snap(db_session, stage, fake_clock)
    outsider = await make_user(db_session, role="admin")
    await db_session.commit()

    response = await read_snapshot(api_client, stage, version.id, outsider)

    assert (response.status_code, response.json()["resource"]) == (404, "project")


@pytest.mark.parametrize("missing", ["absent", "soft_deleted_floor"])
async def test_versions_read_snapshot__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, missing: str
) -> None:
    """Phiên bản không có, hoặc thuộc tầng đã xoá mềm → 404 `resource:"version"`."""
    stage = await make_stage(db_session)
    version_id = ABSENT_VERSION
    if missing == "soft_deleted_floor":
        version_id = (await commit_snap(db_session, stage, fake_clock)).id
        deleted = update(FloorRow).where(FloorRow.pk == stage.floor.pk).values(deleted_at=fake_clock.now())
        await db_session.execute(deleted)
        await db_session.commit()

    response = await read_snapshot(api_client, stage, version_id)

    assert (response.status_code, response.json()["resource"]) == (404, "version")


async def test_versions_read_snapshot__C17(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Đồ đạc chưa gắn phòng → ảnh chụp **vắng** khoá `roomId`, không phải `null`."""
    stage = await make_stage(db_session)
    layer = simple_layer(stage.level_id, furniture=(make_furniture(stage.level_id),))
    await put_layer(db_session, stage, fake_clock, layer, base=0)
    version = await commit_snap(db_session, stage, fake_clock)

    item = (await read_snapshot(api_client, stage, version.id)).json()["layer"]["furniture"][0]

    assert "roomId" not in item


async def test_versions_read_snapshot__floor_mismatch(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """`floorId` của tầng khác trong cùng dự án → 422 `VERSION_FLOOR_MISMATCH` `field:"floorId"`."""
    stage = await make_stage(db_session, floors=2)
    version = await commit_snap(db_session, stage, fake_clock)

    response = await read_snapshot(api_client, stage, version.id, floor_id=stage.other_level_id)

    assert response.status_code == 422
    assert response.json()["code"] == "VERSION_FLOOR_MISMATCH"
    assert response.json()["field"] == "floorId"


@pytest.mark.parametrize("how", ["purged", "schema", "alien_key"])
async def test_versions_read_snapshot__purged(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    fake_clock: FakeClock,
    caplog: pytest.LogCaptureFixture,
    how: Corruption,
) -> None:
    """Mất ảnh chụp, `schemaVersion: 2` hay khoá lạ trong `document` → 422 `VERSION_SNAPSHOT_PURGED` (không 500).

    Hai dạng hỏng có log `snapshot_schema_mismatch`; "mất ảnh chụp" là chuyện bình thường nên không log.
    """
    stage = await make_stage(db_session)
    await put_layer(db_session, stage, fake_clock, simple_layer(stage.level_id), base=0)
    version = await commit_snap(db_session, stage, fake_clock)
    await corrupt_snapshot(db_session, version.id, how)
    caplog.set_level(logging.WARNING, logger=SNAPSHOT_LOGGER)

    response = await read_snapshot(api_client, stage, version.id)

    assert response.status_code == 422
    assert response.json()["code"] == "VERSION_SNAPSHOT_PURGED"
    assert mismatch_logged(caplog) is (how != "purged")


async def test_versions_read_version__hard_deleting_the_floor_cascades(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
) -> None:
    """Xoá cứng tầng (SQL) → `versions` của tầng mất theo CASCADE, #36 trả 404 (không dòng mồ côi)."""
    stage = await make_stage(db_session)
    await put_layer(db_session, stage, fake_clock, simple_layer(stage.level_id), base=0)
    version = await commit_snap(db_session, stage, fake_clock)
    floor_pk = stage.floor.pk

    await db_session.execute(delete(FloorRow).where(FloorRow.pk == floor_pk))
    await db_session.commit()

    assert await versions_of(db_sessionmaker, floor_pk) == []
    assert (await read_version(api_client, stage, version.id)).status_code == 404
