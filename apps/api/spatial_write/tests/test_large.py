"""Tầng lớn của #35: trần thân 8 MiB, số đo thời gian, và đường `merge` trên tầng lớn (B3-03 [8]).

Đây là phần duy nhất của B3-03 đo **số**: một tầng 3.000 tường vượt trần 1 MiB mặc định nên
route phải khai `body_limit=8 MiB`, và thời gian giữ khoá của `merge` là con số quyết định
`merge` của pipeline có chặn người dùng hay không. Số in ra đi vào báo cáo, không phải ngưỡng
`assert` — máy chạy cổng khác máy dev, một ngưỡng cứng chỉ tạo test đỏ nhấp nháy.

Không mock gì: Postgres thật, JSON thật, `write_layer` thật (K22, K23).
"""

import asyncio
import json
import math
import time
from collections.abc import Sequence
from typing import Any, Final

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.projects.tests.test_routes_common import headers_of
from apps.api.spatial_read.documents import FloorDocument, load_document
from apps.api.spatial_read.tests._helpers import make_scene, other_session
from apps.api.spatial_write.router import BODY_LIMIT
from apps.api.spatial_write.tests._helpers import RecordingMerge, simple_layer, write
from apps.api.spatial_write.tests._route_helpers import layer_path, put_layer, write_body
from apps.api.spatial_write.writer import WriteResult
from packages.domain.spatial import Opening, Room, SpatialLayer, Wall
from packages.testing.fixtures.clock import FakeClock

WALLS: Final = 3_000
OPENINGS: Final = 1_000
ROOMS: Final = 400
ROOM_POINTS: Final = 20
MIB: Final = 1024 * 1024
REPEATS: Final = 5
"""Số lượt ghi thật để lấy p95 — mỗi lượt là một tầng 3.000 tường đi trọn đường ghi."""
ROUTE_WRITES: Final = 20
"""Số lượt #35 chạy song song với một lượt `merge` ([8])."""


def _wall(level_id: str, index: int, *, opening_ids: Sequence[str] = ()) -> Wall:
    """Tường thứ `index` của tầng lớn: một đoạn ngang, mỗi tường một hàng riêng."""
    return Wall.model_validate(
        {
            "id": f"W-LARGE{index:05d}",
            "levelId": level_id,
            "centreline": {"start": {"x": 0, "y": index * 10}, "end": {"x": 6000, "y": index * 10}},
            "thicknessMm": 200,
            "heightMm": 3000,
            "kind": "partition",
            "openingIds": list(opening_ids),
            "confidence": 0.8,
            "source": "ai",
            "reviewed": False,
        }
    )


def _opening(index: int) -> Opening:
    """Ô mở thứ `index`, gắn vào tường cùng chỉ số (tham chiếu hợp lệ, không sinh lỗi toàn vẹn)."""
    return Opening.model_validate(
        {
            "id": f"D-LARGE{index:05d}",
            "wallId": f"W-LARGE{index:05d}",
            "kind": "door" if index % 2 == 0 else "window",
            "offsetMm": 500,
            "widthMm": 900,
            "heightMm": 2100,
            "sillHeightMm": 0 if index % 2 == 0 else 900,
            "swing": "left" if index % 2 == 0 else "fixed",
            "confidence": 0.8,
            "source": "ai",
            "reviewed": False,
        }
    )


def _room(level_id: str, index: int) -> Room:
    """Phòng thứ `index`: đa giác đều `ROOM_POINTS` đỉnh, bán kính 2 m — lồi, không tự cắt, diện tích > 0."""
    base = 10_000 + index * 50
    outline = [
        {
            "x": base + round(2_000 * math.cos(2 * math.pi * point / ROOM_POINTS)),
            "y": base + round(2_000 * math.sin(2 * math.pi * point / ROOM_POINTS)),
        }
        for point in range(ROOM_POINTS)
    ]
    return Room.model_validate(
        {
            "id": f"R-LARGE{index:05d}",
            "levelId": level_id,
            "name": f"Phòng {index}",
            "usage": "bedroom",
            "outline": outline,
            "areaM2": 0.0,
            "wallIds": [],
            "confidence": 0.8,
            "source": "ai",
            "reviewed": False,
        }
    )


def _large_layer(level_id: str) -> SpatialLayer:
    """Tầng lớn của [8]: 3.000 tường, 1.000 ô mở, 400 phòng 20 điểm — thân dây vượt 1 MiB."""
    return SpatialLayer(
        walls=tuple(
            _wall(level_id, index, opening_ids=(f"D-LARGE{index:05d}",) if index < OPENINGS else ())
            for index in range(WALLS)
        ),
        openings=tuple(_opening(index) for index in range(OPENINGS)),
        rooms=tuple(_room(level_id, index) for index in range(ROOMS)),
        furniture=(),
    )


def _reordered(walls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Đảo thứ tự tường: jsonb đổi nhưng không mục nào đổi, nên không sinh dòng nhật ký."""
    return walls[::-1]


async def test_spatial_write_layer_accepts_a_large_floor(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Thân > 1 MiB → 200; in kích thước thân, thời gian từng lượt và p95 của `REPEATS` lượt thật."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    payload = write_body(0, layer=_large_layer(floor.level_id))
    size = len(json.dumps(payload).encode())
    assert size > MIB
    assert size < BODY_LIMIT

    durations: list[float] = []
    for attempt in range(REPEATS):
        payload["baseVersion"] = attempt
        payload["body"]["layer"]["walls"] = _reordered(payload["body"]["layer"]["walls"])
        started = time.perf_counter()
        response = await put_layer(api_client, scene.project.id, floor.level_id, scene.owner, payload)
        durations.append(time.perf_counter() - started)
        assert response.status_code == 200
        assert response.json()["revision"] == attempt + 1

    ordered = sorted(durations)
    p95 = ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))]
    print(
        f"tầng lớn spatial_write_layer: thân = {size / MIB:.2f} MiB "
        f"({WALLS} tường, {OPENINGS} ô mở, {ROOMS} phòng x {ROOM_POINTS} điểm), "
        f"{REPEATS} lượt = {[f'{value:.2f}s' for value in durations]}, p95 = {p95:.2f}s"
    )
    read = await api_client.get(layer_path(scene.project.id, floor.level_id), headers=headers_of(scene.owner))
    assert len(read.json()["layer"]["walls"]) == WALLS


async def test_spatial_write_layer_rejects_a_body_over_eight_mebibytes(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Thân > 8 MiB → 413 từ `BodyLimitMiddleware`, trước cả xác thực thân (C12 của route này)."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    raw = json.dumps(write_body(0, layer=simple_layer(floor.level_id))).encode()
    oversized = b" " * (BODY_LIMIT + 1 - len(raw)) + raw
    assert len(oversized) > BODY_LIMIT

    response = await api_client.put(
        layer_path(scene.project.id, floor.level_id),
        content=oversized,
        headers={**headers_of(scene.owner), "content-type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json()["code"] == "PAYLOAD_TOO_LARGE"


async def test_merge_on_a_large_floor_holds_the_document_lock_briefly(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`merge` trên tầng lớn: đo thời gian giữ khoá `floor_documents` (bước 3 → hết `write_layer`).

    Đường `merge` khoá dòng tài liệu `FOR UPDATE` ngay ở bước 3, nên mọi lượt #35 của người dùng
    chờ đúng khoảng này. Con số đi vào báo cáo; không `assert` ngưỡng vì máy cổng khác máy dev.
    """
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    large = _large_layer(floor.level_id)
    assert (
        await put_layer(api_client, scene.project.id, floor.level_id, scene.owner, write_body(0, layer=large))
    ).status_code == 200
    original = load_document
    locked_at: list[float] = []

    async def timed_load(db: AsyncSession, floor_pk: int, *, for_update: bool = False) -> FloorDocument | None:
        """Ghi lại lúc khoá được nhận — chỉ đường `merge` gọi với `for_update=True`."""
        document = await original(db, floor_pk, for_update=for_update)
        if for_update:
            locked_at.append(time.perf_counter())
        return document

    monkeypatch.setattr("apps.api.spatial_write.writer.load_document", timed_load)
    merge = RecordingMerge(lambda base: base.model_copy(update={"walls": base.walls[::-1]}))

    async with other_session(db_sessionmaker) as session:
        result = await write(session, floor=floor, actor=scene.owner, clock=fake_clock, merge=merge)
        await session.commit()
    held = time.perf_counter() - locked_at[0]

    assert result.applied is True
    assert merge.calls == 1
    assert merge.base is not None
    assert len(merge.base.walls) == WALLS
    print(f"merge trên tầng lớn ({WALLS} tường): giữ khoá floor_documents = {held:.2f}s")


async def test_merge_runs_beside_twenty_route_writes_without_conflict(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
) -> None:
    """Một lượt `merge` song song với 20 lượt #35 qua HTTP → không lượt nào ra 409.

    Cả hai bên chỉ **đổi thứ tự** danh sách nên không để lại dòng nhật ký: bên nào thua đua ở
    `UPDATE` cũng chỉ thấy "diff rỗng" và được nhận ghi (W20), không phải xung đột.
    """
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    two_walls = simple_layer(
        floor.level_id,
        walls=(_wall(floor.level_id, 0), _wall(floor.level_id, 1)),
    )
    assert (
        await put_layer(api_client, scene.project.id, floor.level_id, scene.owner, write_body(0, layer=two_walls))
    ).status_code == 200

    async def merge_once() -> WriteResult:
        """Lượt gộp của pipeline: đảo thứ tự tường, giữ nguyên mọi trường."""
        merge = RecordingMerge(lambda base: base.model_copy(update={"walls": base.walls[::-1]}))
        async with other_session(db_sessionmaker) as session:
            result = await write(session, floor=floor, actor=scene.owner, clock=fake_clock, merge=merge)
            await session.commit()
            return result

    async def route_writes() -> list[int]:
        """20 lượt #35 nối đuôi nhau; mỗi lượt đọc `revision` hiện tại của N16 làm `baseVersion`."""
        statuses: list[int] = []
        for _ in range(ROUTE_WRITES):
            read = await api_client.get(layer_path(scene.project.id, floor.level_id), headers=headers_of(scene.owner))
            layer = read.json()["layer"]
            layer["walls"] = _reordered(layer["walls"])
            response = await put_layer(
                api_client,
                scene.project.id,
                floor.level_id,
                scene.owner,
                {"baseVersion": read.json()["revision"], "body": {"layer": layer}},
            )
            statuses.append(response.status_code)
        return statuses

    merged, statuses = await asyncio.gather(merge_once(), route_writes())

    assert merged.applied is True
    assert set(statuses) == {200}
