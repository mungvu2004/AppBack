"""N20 `PATCH .../versions/{id}/label` — G: C01 C02 C03 C06 C07 C08 C16 C17 C18 (B3-04 [8]).

Nhãn là siêu dữ liệu của lịch sử: không sinh phiên bản, không đổi `revision` tầng. C10/C22
(idempotency) do `apps/api/core/tests/test_common.py` chạy chung cho mọi route `auto`.
"""

import unicodedata
from typing import Any

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.access.kinds import ActivityKind
from apps.api.spatial_read.documents import load_document
from apps.api.spatial_write.tests._helpers import simple_layer
from apps.api.versions.tests._helpers import versions_of
from apps.api.versions.tests._route_helpers import (
    Stage,
    call,
    commit_snap,
    corrupt_snapshot,
    make_stage,
    put_layer,
    relabel,
    versions_path,
)
from packages.db.models.floors import FloorRow
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.access import activity_rows, assert_one_activity
from packages.testing.fixtures.clock import FakeClock

ABSENT_VERSION = "ver_01J00000000000000000000000"


async def _one_version(db: AsyncSession, stage: Stage, clock: FakeClock) -> str:
    """Tầng có một lớp và một phiên bản; trả id phiên bản."""
    await put_layer(db, stage, clock, simple_layer(stage.level_id), base=0)
    return (await commit_snap(db, stage, clock)).id


async def test_versions_label_version__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Đặt nhãn → 200 `FloorVersionSummary` đủ trường, `label` đã cắt khoảng trắng."""
    stage = await make_stage(db_session)
    version_id = await _one_version(db_session, stage, fake_clock)

    response = await relabel(api_client, stage, version_id, "  bản gửi chủ đầu tư ")

    assert response.status_code == 200
    assert response.json() == {
        "id": version_id,
        "sequence": 1,
        "floorRevision": 1,
        "createdAt": "2026-01-01T00:00:00.000Z",
        "creatorId": stage.owner.id,
        "creatorName": stage.owner.name,
        "label": "bản gửi chủ đầu tư",
        "hasSnapshot": True,
    }


@pytest.mark.parametrize(
    "payload",
    [{"label": "a" * 61}, {"label": "😀" * 31}, {"label": 5}, {"label": None}, {"label": "x‮y"}, {}],
)
async def test_versions_label_version__C02(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, payload: dict[str, Any]
) -> None:
    """61 đơn vị UTF-16 (kể cả 31 emoji = 62), `label: 5`, `null`, thiếu, U+202E → 422 `VALIDATION` `field:"label"`."""
    stage = await make_stage(db_session)
    version_id = await _one_version(db_session, stage, fake_clock)

    response = await call(
        api_client, "PATCH", versions_path(stage.project_id, version_id, "/label"), stage.owner, json=payload
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"
    assert response.json()["field"] == "label"


async def test_versions_label_version__C03(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Khoá lạ ở thân → 422 `VALIDATION` (zod `.strict()`)."""
    stage = await make_stage(db_session)
    version_id = await _one_version(db_session, stage, fake_clock)

    response = await call(
        api_client,
        "PATCH",
        versions_path(stage.project_id, version_id, "/label"),
        stage.owner,
        json={"label": "a", "nonsense": 1},
    )

    assert (response.status_code, response.json()["code"]) == (422, "VALIDATION")


async def test_versions_label_version__C06(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Admin hệ thống không phải thành viên → 404 `resource:"project"`."""
    stage = await make_stage(db_session)
    version_id = await _one_version(db_session, stage, fake_clock)
    outsider = await make_user(db_session, role="admin")
    await db_session.commit()

    response = await relabel(api_client, stage, version_id, "a", outsider)

    assert (response.status_code, response.json()["resource"]) == (404, "project")


async def test_versions_label_version__C07(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Viewer thiếu `layer.edit` → 403 `FORBIDDEN`."""
    viewer = await make_user(db_session, role="viewer")
    stage = await make_stage(db_session, members=[viewer])
    version_id = await _one_version(db_session, stage, fake_clock)

    response = await relabel(api_client, stage, version_id, "a", viewer)

    assert (response.status_code, response.json()["code"]) == (403, "FORBIDDEN")


@pytest.mark.parametrize("missing", ["absent", "malformed", "other_project", "soft_deleted_floor"])
async def test_versions_label_version__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, missing: str
) -> None:
    """Phiên bản không có, sai mẫu, của dự án khác, hay của tầng xoá mềm → 404 `resource:"version"`."""
    stage = await make_stage(db_session)
    other = await make_stage(db_session)
    version_id = {"absent": ABSENT_VERSION, "malformed": "ver_nope"}.get(missing, "")
    if missing == "other_project":
        version_id = await _one_version(db_session, other, fake_clock)
    elif missing == "soft_deleted_floor":
        version_id = await _one_version(db_session, stage, fake_clock)
        deleted = update(FloorRow).where(FloorRow.pk == stage.floor.pk).values(deleted_at=fake_clock.now())
        await db_session.execute(deleted)
        await db_session.commit()

    response = await relabel(api_client, stage, version_id, "a")

    assert (response.status_code, response.json()["resource"]) == (404, "version")


async def test_versions_label_version__C16(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Nhãn NFD → lưu và trả NFC; N17 đọc lại cũng NFC."""
    stage = await make_stage(db_session)
    version_id = await _one_version(db_session, stage, fake_clock)
    nfd = unicodedata.normalize("NFD", "Bản đẹp")
    assert nfd != "Bản đẹp"

    response = await relabel(api_client, stage, version_id, nfd)

    assert response.json()["label"] == "Bản đẹp"
    listed = await call(
        api_client, "GET", versions_path(stage.project_id), stage.owner, params={"floorId": stage.level_id}
    )
    assert listed.json()["items"][0]["label"] == "Bản đẹp"


async def test_versions_label_version__C17(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Gỡ nhãn (`''`, hay chỉ khoảng trắng) → 200 vắng khoá `label` (không phải `null`, không phải rỗng)."""
    stage = await make_stage(db_session)
    version_id = await _one_version(db_session, stage, fake_clock)
    assert (await relabel(api_client, stage, version_id, "tạm")).json()["label"] == "tạm"

    blank = await relabel(api_client, stage, version_id, "   ")
    again = await relabel(api_client, stage, version_id, "")

    assert blank.status_code == again.status_code == 200
    assert "label" not in blank.json()
    assert "label" not in again.json()


async def test_versions_label_version__C18(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
) -> None:
    """Đổi nhãn → một dòng `version.label` (`object_code` = id, nhãn = tên tầng); nhãn không đổi → không thêm."""
    stage = await make_stage(db_session)
    version_id = await _one_version(db_session, stage, fake_clock)

    assert (await relabel(api_client, stage, version_id, "chốt")).status_code == 200
    assert (await relabel(api_client, stage, version_id, "chốt")).status_code == 200

    row = await assert_one_activity(
        db_sessionmaker, actor_id=stage.owner.id, kind=ActivityKind.VERSION_LABEL, object_code=version_id
    )
    assert row.object_label == stage.floor.name
    assert row.project_id == stage.project_id


async def test_versions_label_version__keeps_the_floor_untouched(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
) -> None:
    """Gắn nhãn không sinh phiên bản, không đổi `revision` tầng, không nhật ký `version.restore`."""
    stage = await make_stage(db_session)
    version_id = await _one_version(db_session, stage, fake_clock)

    assert (await relabel(api_client, stage, version_id, "a" * 30)).status_code == 200

    async with db_sessionmaker() as session:
        document = await load_document(session, stage.floor.pk)
    assert document is not None
    assert document.revision == 1
    assert len(await versions_of(db_sessionmaker, stage.floor.pk)) == 1
    assert await activity_rows(db_sessionmaker, actor_id=stage.owner.id, kind=ActivityKind.VERSION_RESTORE) == []


async def test_versions_label_version__sixty_vietnamese_characters(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """60 ký tự tiếng Việt (mỗi ký tự 1 đơn vị UTF-16, có dấu) → 200; 30 emoji (= 60 đơn vị) → 200."""
    stage = await make_stage(db_session)
    version_id = await _one_version(db_session, stage, fake_clock)

    vietnamese = await relabel(api_client, stage, version_id, "ệ" * 60)
    emoji = await relabel(api_client, stage, version_id, "😀" * 30)

    assert (vietnamese.status_code, vietnamese.json()["label"]) == (200, "ệ" * 60)
    assert (emoji.status_code, emoji.json()["label"]) == (200, "😀" * 30)


async def test_versions_label_version__purged_snapshot_can_be_labelled(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Bản đã mất ảnh chụp vẫn gắn được nhãn; `hasSnapshot` vẫn `false`."""
    stage = await make_stage(db_session)
    version_id = await _one_version(db_session, stage, fake_clock)
    await corrupt_snapshot(db_session, version_id, "purged")

    response = await relabel(api_client, stage, version_id, "bản cũ")

    assert response.status_code == 200
    assert (response.json()["label"], response.json()["hasSnapshot"]) == ("bản cũ", False)
