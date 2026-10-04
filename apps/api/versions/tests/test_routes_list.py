"""N17 `GET .../versions?floorId=` — Đ: C01 C02 C06 C08 C15 C17 (B3-04 [8]).

`sequence` giảm dần, cursor ký HMAC (W22). Mỗi bản cần một `revision` khác nhau (`create_version`
không nhân đôi khi `revision` không đổi, K18), nên `_seed` ghi một lớp mới trước mỗi bản.
"""

import unicodedata
from itertools import count
from typing import Any

import httpx
import pytest
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.pagination import decode_cursor, encode_cursor
from apps.api.projects.tests.sql_count import count_sql
from apps.api.spatial_write.tests._helpers import make_wall, simple_layer
from apps.api.versions.tests._helpers import keep_snapshots
from apps.api.versions.tests._route_helpers import (
    Stage,
    call,
    commit_snap,
    list_versions,
    make_stage,
    put_layer,
    relabel,
    versions_path,
)
from packages.core.clock import Clock
from packages.core.errors import AppError
from packages.db.models.floors import FloorRow
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.clock import FakeClock


def _forged(cursor: str) -> str:
    """Cursor sửa một ký tự **giữa** MAC — đổi 6 bit dữ liệu thật, MAC chắc chắn lệch.

    Không sửa 2 ký tự cuối: MAC 32 byte là 43 ký tự base64url, 2 bit cuối là đệm bị bỏ
    khi giải (`apps/api/core/pagination.py` `_unb64`), nên sửa đuôi có thể ra đúng MAC cũ (NO-258).
    """
    head, mac = cursor.split(".")
    middle = len(mac) // 2
    swapped = "A" if mac[middle] != "A" else "B"
    return f"{head}.{mac[:middle]}{swapped}{mac[middle + 1 :]}"


def test_forged__mac_ending_in_padding_bits(storage_env: None) -> None:
    """Cursor có MAC tận cùng `x[w-z]` (đuôi cũ `"xx"` trùng MAC thật) vẫn bị `_forged` làm hỏng (NO-258)."""
    cursor = next(
        signed
        for index in count()
        if (signed := encode_cursor("probe", {}, {"i": index}))[-2] == "x" and signed[-1] in "wxyz"
    )
    with pytest.raises(AppError, match="CURSOR_INVALID"):
        decode_cursor(_forged(cursor), "probe", {})


async def _seed(db: AsyncSession, stage: Stage, clock: Clock, count: int, *, first_base: int = 0) -> list[str]:
    """`count` phiên bản, mỗi bản ở một `revision` riêng; trả id theo thứ tự tạo (`sequence` tăng)."""
    ids: list[str] = []
    for index in range(count):
        layer = simple_layer(stage.level_id, walls=(make_wall(stage.level_id, thickness=100 + index),))
        await put_layer(db, stage, clock, layer, base=first_base + index)
        ids.append((await commit_snap(db, stage, clock, note=f"bản {index + 1}")).id)
    return ids


async def test_versions_list_versions__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Ba bản → `sequence` 3,2,1; mỗi mục có đủ trường, `floorRevision` là `revision` lúc chụp."""
    stage = await make_stage(db_session)
    ids = await _seed(db_session, stage, fake_clock, 3)

    response = await list_versions(api_client, stage)

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["sequence"] for item in items] == [3, 2, 1]
    assert [item["id"] for item in items] == ids[::-1]
    assert items[0] == {
        "id": ids[2],
        "sequence": 3,
        "floorRevision": 3,
        "createdAt": "2026-01-01T00:00:00.000Z",
        "creatorId": stage.owner.id,
        "creatorName": stage.owner.name,
        "note": "bản 3",
        "hasSnapshot": True,
    }
    assert "nextCursor" not in response.json()


@pytest.mark.parametrize(
    ("floor_id", "params", "field"),
    [
        (None, {}, None),
        ("", {}, "floorId"),
        ("L-ANY", {"limit": 0}, "limit"),
        ("L-ANY", {"limit": 201}, "limit"),
    ],
)
async def test_versions_list_versions__C02(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    floor_id: str | None,
    params: dict[str, Any],
    field: str | None,
) -> None:
    """Thiếu/rỗng `floorId`, `limit=0`, `limit=201` → 422 `VALIDATION` kèm `field` đúng tham số."""
    stage = await make_stage(db_session)

    if floor_id is None:
        response = await call(api_client, "GET", versions_path(stage.project_id), stage.owner)
        field = "floorId"
    else:
        response = await list_versions(api_client, stage, floor_id=floor_id, **params)

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"
    assert response.json()["field"] == field


async def test_versions_list_versions__C06(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Admin hệ thống không phải thành viên → 404 `resource:"project"`."""
    stage = await make_stage(db_session)
    outsider = await make_user(db_session, role="admin")
    await db_session.commit()

    response = await list_versions(api_client, stage, user=outsider)

    assert (response.status_code, response.json()["resource"]) == (404, "project")


@pytest.mark.parametrize("missing", ["absent", "other_project", "soft_deleted"])
async def test_versions_list_versions__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, missing: str
) -> None:
    """`floorId` không có, của dự án khác, hay tầng xoá mềm → 404 `resource:"floor"`."""
    stage = await make_stage(db_session)
    other = await make_stage(db_session)
    floor_id = "L-NOSUCHFLOOR"
    if missing == "other_project":
        floor_id = other.level_id
    elif missing == "soft_deleted":
        floor_id = stage.level_id
        await db_session.execute(
            update(FloorRow).where(FloorRow.pk == stage.floor.pk).values(deleted_at=fake_clock.now())
        )
        await db_session.commit()

    response = await list_versions(api_client, stage, floor_id=floor_id)

    assert (response.status_code, response.json()["resource"]) == (404, "floor")


@pytest.mark.parametrize("count", [0, 1])
async def test_versions_list_versions__C15_small(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, count: int
) -> None:
    """0 bản → `items: []`; 1 bản → một mục; cả hai không có `nextCursor`."""
    stage = await make_stage(db_session)
    await _seed(db_session, stage, fake_clock, count)

    body = (await list_versions(api_client, stage, limit=3)).json()

    assert len(body["items"]) == count
    assert "nextCursor" not in body


async def test_versions_list_versions__C15_pages(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """7 bản, `limit=3` → trang 3/3/1, trang cuối vắng `nextCursor`; bản mới chen giữa hai trang không trùng."""
    stage = await make_stage(db_session)
    await _seed(db_session, stage, fake_clock, 7)

    first = (await list_versions(api_client, stage, limit=3)).json()
    await _seed_more(db_session, stage, fake_clock, base=7)
    second = (await list_versions(api_client, stage, limit=3, cursor=first["nextCursor"])).json()
    third = (await list_versions(api_client, stage, limit=3, cursor=second["nextCursor"])).json()

    pages = [[item["sequence"] for item in page["items"]] for page in (first, second, third)]
    assert pages == [[7, 6, 5], [4, 3, 2], [1]]
    assert "nextCursor" not in third


async def _seed_more(db: AsyncSession, stage: Stage, clock: Clock, *, base: int) -> None:
    """Thêm một bản mới ở `revision` `base + 1` (chen vào lịch sử giữa hai lần lật trang)."""
    layer = simple_layer(stage.level_id, walls=(make_wall(stage.level_id, thickness=300),))
    await put_layer(db, stage, clock, layer, base=base)
    await commit_snap(db, stage, clock, note="bản chen")


async def test_versions_list_versions__C17(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Không `note`, không `label`, hết trang → ba khoá cùng vắng (W2); có nhãn thì khoá `label` hiện."""
    stage = await make_stage(db_session)
    bare = await commit_snap(db_session, stage, fake_clock)

    item = (await list_versions(api_client, stage)).json()["items"][0]
    assert not {"note", "label"} & set(item)
    assert "nextCursor" not in (await list_versions(api_client, stage)).json()

    assert (await relabel(api_client, stage, bare.id, "bản chốt")).status_code == 200
    assert (await list_versions(api_client, stage)).json()["items"][0]["label"] == "bản chốt"


async def test_versions_list_versions__cursor_of_another_floor(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Cursor của tầng A dùng cho tầng B, hay cursor sửa → 422 `CURSOR_INVALID`."""
    stage = await make_stage(db_session, floors=2)
    await _seed(db_session, stage, fake_clock, 3)
    cursor = (await list_versions(api_client, stage, limit=1)).json()["nextCursor"]

    other = await list_versions(api_client, stage, floor_id=stage.other_level_id, cursor=cursor)
    forged = await list_versions(api_client, stage, cursor=_forged(cursor))

    assert (other.status_code, other.json()["code"]) == (422, "CURSOR_INVALID")
    assert (forged.status_code, forged.json()["code"]) == (422, "CURSOR_INVALID")


def _without(statement: str, allowed: tuple[str, ...]) -> str:
    """Câu SQL sau khi bỏ các cụm được phép nhắc `snapshot` (chỉ phép thử `IS NOT NULL` cho `hasSnapshot`)."""
    for phrase in allowed:
        statement = statement.replace(phrase, "")
    return statement


async def test_versions_list_versions__never_selects_the_snapshot(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Mọi câu SQL chạm `versions` trong một lượt N17 không nhắc cột `snapshot` ngoài `snapshot IS NOT NULL`."""
    stage = await make_stage(db_session)
    await _seed(db_session, stage, fake_clock, 2)

    with count_sql() as counter:
        response = await list_versions(api_client, stage)

    assert response.status_code == 200
    touching = [s for s in counter.statements if "FROM versions" in s]
    assert touching, counter.statements
    allowed = ("versions.snapshot IS NOT NULL AS has_snapshot",)
    assert all("snapshot" not in _without(s, allowed) for s in touching), touching


async def test_versions_list_versions__creator_name_is_the_name_at_write_time(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Đổi `users.name` sau khi tạo bản → N17 vẫn trả tên **lúc ghi** (chuẩn hoá NFC)."""
    stage = await make_stage(db_session)
    await commit_snap(db_session, stage, fake_clock)
    old_name = stage.owner.name
    await db_session.execute(
        text("UPDATE users SET name = :n WHERE id = :id"),
        {"n": unicodedata.normalize("NFC", "Tên mới"), "id": stage.owner.id},
    )
    await db_session.commit()

    item = (await list_versions(api_client, stage)).json()["items"][0]

    assert item["creatorName"] == old_name


async def test_versions_list_versions__retention(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trần 3, tạo 5 bản → hai bản cũ `hasSnapshot: false`, siêu dữ liệu còn đủ năm dòng."""
    keep_snapshots(monkeypatch, 3)
    stage = await make_stage(db_session)
    await _seed(db_session, stage, fake_clock, 5)

    items = (await list_versions(api_client, stage)).json()["items"]

    flags = [item["hasSnapshot"] for item in items]
    print(f"retention (trần 3, 5 bản): hasSnapshot=false ở {flags.count(False)} bản, đủ {len(items)} dòng")
    assert [item["sequence"] for item in items] == [5, 4, 3, 2, 1]
    assert flags == [True, True, True, False, False]
