"""#31 `POST …/quality/corners`: ma trận case G, "Bốn góc", "Đã duyệt", "Hoàn tác", U03/U07, "Lượt cũ" ([8])."""

import asyncio
import errno
import logging
from typing import Any, Final

import httpx
import numpy as np
import pytest
from redis import Redis as SyncRedis
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.projects.tests.test_routes_common import headers_of
from apps.api.quality import service
from apps.api.quality.assessments import load_assessment, save_assessment
from apps.api.quality.processing import process_corners
from apps.api.quality.schemas import SetCornersIn
from apps.api.quality.tests._images import desk_shot, huge_png, png_bytes, tilted_drawing, truncated_png
from apps.api.quality.tests._route_helpers import (
    CPU_QUEUE,
    FULL_PAGE,
    SHOT_H,
    SHOT_W,
    Stage,
    corners_body,
    corners_path,
    floor_view,
    make_image_floor,
    make_stage,
    mark_reviewed,
    measure_real,
    page_objects,
    read_path,
    run_count,
    runs_of,
    straighten_path,
    tune,
)
from apps.api.quality.tests._route_helpers import (
    broker as broker,
)
from apps.api.quality.tests._route_helpers import (
    quality_env as quality_env,
)
from packages.core.clock import Clock
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.db.models.drawings import DrawingRow, UploadRow
from packages.db.models.floors import FloorRow
from packages.storage import keys
from packages.storage.local import LocalDiskStorage
from packages.testing.factories.auth import make_user
from packages.testing.factories.drawings import make_complete_upload, make_drawing
from packages.testing.factories.floors import make_floor
from packages.testing.fixtures.api import make_api_client
from packages.testing.fixtures.messaging import queued_payloads
from packages.vision.preprocess import RgbImage, load_raster
from packages.vision.quality import assess

INSET: Final = ((0.05, 0.05), (0.95, 0.05), (0.95, 0.95), (0.05, 0.95))
"""Một tứ giác lồi hợp lệ khác `FULL_PAGE` (dùng khi chỉ cần góc "khác")."""


async def _post(
    client: httpx.AsyncClient, stage: Stage, points: Any, *, index: int = 0, headers: dict[str, str] | None = None
) -> httpx.Response:
    """#31 trên tầng `index` của sân khấu, mặc định bằng chủ dự án."""
    return await client.post(
        corners_path(stage.project.id, stage.level(index)),
        json=corners_body(points),
        headers=headers or stage.headers,
    )


async def test_quality_set_corners__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: Clock
) -> None:
    """Góc thật của mép giấy → 200 `ImageQualityAssessment` (golden H1) của trang mới, đã đo."""
    stage = await make_stage(db_session, local_storage)
    shot = desk_shot(SHOT_W, SHOT_H)
    await measure_real(db_session, fake_clock, stage.floors[0], shot.pixels)

    response = await _post(api_client, stage, shot.corners)

    assert response.status_code == 200, response.text
    assert floor_view(response, stage.level())["isMeasured"] is True


async def test_quality_set_corners__four_corners_applied(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: Clock,
    broker: SyncRedis,
) -> None:
    """Ảnh có khung nghiêng: khoá trang mới, `FRAME_NOT_FOUND` biến mất, lượt mới `pending`, lượt cũ bị thay."""
    stage = await make_stage(db_session, local_storage)
    shot = desk_shot(SHOT_W, SHOT_H)
    await measure_real(db_session, fake_clock, stage.floors[0], shot.pixels)
    broker.delete(CPU_QUEUE)
    before = floor_view(
        await api_client.get(read_path(stage.project.id, stage.level()), headers=stage.headers), stage.level()
    )
    assert "FRAME_NOT_FOUND" in {item["code"] for item in before["findings"]}

    response = await _post(api_client, stage, shot.corners)

    assert response.status_code == 200, response.text
    after = floor_view(response, stage.level())
    assert after["sourceUrl"] != before["sourceUrl"]
    assert "FRAME_NOT_FOUND" not in {item["code"] for item in after["findings"]}
    assert after["frame"] == {"isFound": True}
    old, new = await runs_of(db_sessionmaker, stage.floors[0].floor.pk)
    assert (old.status, old.error_code, old.superseded_by) == ("failed", "PIPELINE_SUPERSEDED", new.id)
    assert new.status == "pending"
    assert [payload["run_id"] for payload in queued_payloads(broker, CPU_QUEUE)] == [new.id]

    again = await _post(api_client, stage, FULL_PAGE)

    assert again.status_code == 200, again.text
    assert again.json() == response.json()
    assert await run_count(db_sessionmaker, stage.floors[0].floor.pk) == 2
    assert len(queued_payloads(broker, CPU_QUEUE)) == 1


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"corners": "khong-phai-mang"},
        {"corners": [{"xRatio": 0, "yRatio": 0}] * 3},
        {"corners": [{"xRatio": 0, "yRatio": 0}] * 5},
        {"corners": [{"xRatio": 1.5, "yRatio": 0}] * 4},
        {"corners": [{"xRatio": "a", "yRatio": 0}] * 4},
        {"corners": [{"xRatio": 0}] * 4},
    ],
)
async def test_quality_set_corners__C02_body(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage, body: dict[str, Any]
) -> None:
    """Thân sai kiểu, sai số điểm, toạ độ ngoài [0, 1] → 422 `VALIDATION`, không lượt mới."""
    stage = await make_stage(db_session, local_storage)

    response = await api_client.post(corners_path(stage.project.id, stage.level()), json=body, headers=stage.headers)

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "VALIDATION"
    assert "field" in response.json()


@pytest.mark.parametrize(
    "points",
    [
        ((0.0, 0.0), (1.0, 1.0), (1.0, 0.0), (0.0, 1.0)),
        ((0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)),
        ((0.4, 0.4), (0.5, 0.4), (0.5, 0.5), (0.4, 0.5)),
        ((0.0, 0.0), (1.0, 0.0), (0.2, 0.2), (0.0, 1.0)),
    ],
    ids=["self_crossing", "counter_clockwise", "area_one_percent", "concave"],
)
async def test_quality_set_corners__C02_shape(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    points: Any,
) -> None:
    """Tứ giác tự cắt, ngược chiều, diện tích 1 %, lõm → 422 `VALIDATION` `field:"corners"`, không lượt mới."""
    stage = await make_stage(db_session, local_storage)

    response = await _post(api_client, stage, points)

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "VALIDATION"
    assert response.json()["field"] == "corners"
    assert await run_count(db_sessionmaker, stage.floors[0].floor.pk) == 0


async def test_quality_set_corners__C03(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage
) -> None:
    """Khoá lạ ở thân hoặc ở một góc → 422 `VALIDATION`."""
    stage = await make_stage(db_session, local_storage)
    path = corners_path(stage.project.id, stage.level())
    good = corners_body(FULL_PAGE)

    top = await api_client.post(path, json={**good, "extra": 1}, headers=stage.headers)
    nested = {"corners": [{**good["corners"][0], "z": 1}, *good["corners"][1:]]}
    inner = await api_client.post(path, json=nested, headers=stage.headers)

    assert [top.status_code, inner.status_code] == [422, 422]
    assert top.json()["code"] == inner.json()["code"] == "VALIDATION"


async def test_quality_set_corners__C06(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage
) -> None:
    """Người ngoài dự án, kể cả admin hệ thống → 404 `project`."""
    stage = await make_stage(db_session, local_storage)
    admin = await make_user(db_session, role="admin")
    await db_session.commit()

    response = await _post(api_client, stage, FULL_PAGE, headers=headers_of(admin))

    assert response.status_code == 404, response.text
    assert response.json()["resource"] == "project"


async def test_quality_set_corners__C07(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage
) -> None:
    """Viewer (vai mạnh nhất không có `floor.upload`) → 403 `FORBIDDEN`."""
    stage = await make_stage(db_session, local_storage)

    response = await _post(api_client, stage, FULL_PAGE, headers=stage.viewer_headers)

    assert response.status_code == 403, response.text
    assert response.json()["code"] == "FORBIDDEN"


async def test_quality_set_corners__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage
) -> None:
    """Tầng không có, tầng đã xoá → 404 `floor`; tầng chưa có bản vẽ → 404 `upload`."""
    stage = await make_stage(db_session, local_storage, floors=2)
    bare = await make_floor(db_session, project=stage.project)
    await db_session.execute(
        update(FloorRow).where(FloorRow.pk == stage.floors[1].floor.pk).values(deleted_at=FloorRow.created_at)
    )
    await db_session.commit()
    project = stage.project.id

    missing = await api_client.post(
        corners_path(project, "L-NOSUCHFLOOR0"), json=corners_body(FULL_PAGE), headers=stage.headers
    )
    deleted = await _post(api_client, stage, FULL_PAGE, index=1)
    no_drawing = await api_client.post(
        corners_path(project, bare.level_id), json=corners_body(FULL_PAGE), headers=stage.headers
    )

    assert [r.status_code for r in (missing, deleted, no_drawing)] == [404, 404, 404]
    assert [r.json()["resource"] for r in (missing, deleted, no_drawing)] == ["floor", "floor", "upload"]


async def test_quality_set_corners__C17(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: Clock
) -> None:
    """Sau #31: không `null`, không `expectedConfidence`; tầng khác chưa đo vẫn vắng `measurement`, `frame`."""
    stage = await make_stage(db_session, local_storage, floors=2)
    shot = desk_shot(SHOT_W, SHOT_H)
    await measure_real(db_session, fake_clock, stage.floors[0], shot.pixels)

    response = await _post(api_client, stage, shot.corners)

    assert response.status_code == 200, response.text
    assert "null" not in response.text
    assert "expectedConfidence" not in response.text
    other = floor_view(response, stage.level(1))
    assert other["isMeasured"] is False
    assert "measurement" not in other
    assert "frame" not in other


async def test_quality_set_corners__C10_queue_once(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: Clock,
    broker: SyncRedis,
) -> None:
    """Lặp `Idempotency-Key` → cùng response, **một** lượt mới và **một** thông điệp `pipeline.cpu`."""
    stage = await make_stage(db_session, local_storage)
    shot = desk_shot(SHOT_W, SHOT_H)
    await measure_real(db_session, fake_clock, stage.floors[0], shot.pixels)
    broker.delete(CPU_QUEUE)
    headers = {**stage.headers, "Idempotency-Key": "b2-05b-corners-once"}

    first = await _post(api_client, stage, shot.corners, headers=headers)
    second = await _post(api_client, stage, shot.corners, headers=headers)

    assert (first.status_code, second.status_code) == (200, 200), (first.text, second.text)
    assert first.json() == second.json()
    assert await run_count(db_sessionmaker, stage.floors[0].floor.pk) == 2
    assert len(queued_payloads(broker, CPU_QUEUE)) == 1


async def test_quality_set_corners__C10_no_key_replay(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: Clock,
    broker: SyncRedis,
) -> None:
    """FE không gửi khoá: lượt lặp cùng góc không làm gì; mỗi lượt có xử lý tạo đúng một lượt và một thông điệp."""
    stage = await make_stage(db_session, local_storage)
    shot = desk_shot(SHOT_W, SHOT_H)
    await measure_real(db_session, fake_clock, stage.floors[0], shot.pixels)
    broker.delete(CPU_QUEUE)

    first = await _post(api_client, stage, shot.corners)
    replay = await _post(api_client, stage, FULL_PAGE)
    changed = await _post(api_client, stage, INSET)

    assert [r.status_code for r in (first, replay, changed)] == [200, 200, 200]
    assert replay.json() == first.json()
    runs = await runs_of(db_sessionmaker, stage.floors[0].floor.pk)
    assert [run.status for run in runs] == ["failed", "failed", "pending"]
    assert [run.error_code for run in runs[:2]] == ["PIPELINE_SUPERSEDED"] * 2
    assert sorted(str(p["run_id"]) for p in queued_payloads(broker, CPU_QUEUE)) == sorted([runs[1].id, runs[2].id])


async def test_quality_set_corners__reviewed_layer(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: Clock,
    broker: SyncRedis,
) -> None:
    """Tầng đã duyệt (lượt `completed`) → #31, #32 đều 422; bản vẽ mới chưa `completed` → #32 200."""
    stage = await make_stage(db_session, local_storage)
    drawn = stage.floors[0]
    await mark_reviewed(db_session, fake_clock, drawn)
    broker.delete(CPU_QUEUE)
    objects = await page_objects(local_storage, drawn)

    r31 = await _post(api_client, stage, INSET)
    r32 = await api_client.post(straighten_path(stage.project.id, stage.level()), json={}, headers=stage.headers)

    assert [r31.status_code, r32.status_code] == [422, 422]
    assert r31.json()["code"] == r32.json()["code"] == "QUALITY_LAYER_REVIEWED"
    assert await run_count(db_sessionmaker, drawn.floor.pk) == 1
    assert await page_objects(local_storage, drawn) == objects
    assert queued_payloads(broker, CPU_QUEUE) == []

    pixels = desk_shot(SHOT_W, SHOT_H).pixels
    upload = await make_complete_upload(
        db_session, local_storage, project=stage.project, floor=drawn.floor, data=png_bytes(pixels)
    )
    await db_session.execute(delete(DrawingRow).where(DrawingRow.floor_pk == drawn.floor.pk))
    await make_drawing(db_session, local_storage, upload=upload, png=png_bytes(pixels))
    await db_session.commit()

    fresh = await api_client.post(straighten_path(stage.project.id, stage.level()), json={}, headers=stage.headers)

    assert fresh.status_code == 200, fresh.text


async def test_quality_set_corners__undo(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: Clock,
) -> None:
    """Khung C0 chưa áp → #31 với C1 → #31 với C0: trang cuối = nắn từ C0 trên trang chưa nắn, không nắn chồng."""
    pixels = tilted_drawing(2.0, 900, 640)
    stage = await make_stage(db_session, local_storage, pixels=pixels)
    await measure_real(db_session, fake_clock, stage.floors[0], pixels)
    view = floor_view(
        await api_client.get(read_path(stage.project.id, stage.level()), headers=stage.headers), stage.level()
    )
    c0 = [(c["xRatio"], c["yRatio"]) for c in view["frame"]["corners"]]
    c1 = [(x + (0.5 - x) * 0.05, y + (0.5 - y) * 0.05) for x, y in c0]

    applied = await _post(api_client, stage, c1)
    undone = await _post(api_client, stage, c0)

    assert (applied.status_code, undone.status_code) == (200, 200), (applied.text, undone.text)
    assert await run_count(db_sessionmaker, stage.floors[0].floor.pk) == 3
    async with db_sessionmaker() as session:
        page_key = (
            await session.execute(select(DrawingRow.page_key).where(DrawingRow.floor_pk == stage.floors[0].floor.pk))
        ).scalar_one()
    stored = b"".join([chunk async for chunk in local_storage.open_read(page_key)])
    expected = await process_corners(
        png_bytes(pixels), kind="png", page_index=0, corner_ratios=(c0[0], c0[1], c0[2], c0[3])
    )
    got = load_raster(stored, max_pixels=40_000_000).pixels
    want = load_raster(expected.png, max_pixels=40_000_000).pixels
    assert got.shape == want.shape
    assert np.abs(got.astype(int) - want.astype(int)).mean() <= 1.0


async def test_quality_set_corners__U03(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
) -> None:
    """Gốc PNG khai 20 000 x 20 000 → 422 `IMAGE_TOO_LARGE`, không lượt mới, không object mới."""
    stage = await make_stage(db_session, local_storage)
    pixels = desk_shot(SHOT_W, SHOT_H).pixels
    drawn = await make_image_floor(db_session, local_storage, project=stage.project, pixels=pixels, original=huge_png())
    stage.floors.append(drawn)
    await db_session.commit()
    objects = await page_objects(local_storage, drawn)

    response = await _post(api_client, stage, INSET, index=1)

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "IMAGE_TOO_LARGE"
    assert await run_count(db_sessionmaker, drawn.floor.pk) == 0
    assert await page_objects(local_storage, drawn) == objects


async def test_quality_set_corners__U07(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
) -> None:
    """Gốc PNG cụt → 422 `FILE_CORRUPT`, không lượt mới."""
    stage = await make_stage(db_session, local_storage)
    pixels = desk_shot(SHOT_W, SHOT_H).pixels
    drawn = await make_image_floor(
        db_session, local_storage, project=stage.project, pixels=pixels, original=truncated_png()
    )
    stage.floors.append(drawn)
    await db_session.commit()

    response = await _post(api_client, stage, INSET, index=1)

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "FILE_CORRUPT"
    assert await run_count(db_sessionmaker, drawn.floor.pk) == 0


async def test_quality_set_corners__prefers_unrectified_page_png(
    api_client: httpx.AsyncClient, db_session: AsyncSession, local_storage: LocalDiskStorage
) -> None:
    """Có `pages/{i}.png` (sau ML) thì đọc nó chứ không đọc tệp gốc: gốc cụt mà vẫn 200."""
    stage = await make_stage(db_session, local_storage)
    pixels = desk_shot(SHOT_W, SHOT_H).pixels
    drawn = await make_image_floor(
        db_session, local_storage, project=stage.project, pixels=pixels, original=truncated_png()
    )
    stage.floors.append(drawn)
    await db_session.commit()
    page = keys.upload_page(stage.project.id, drawn.floor.level_id, drawn.upload.id, 0)
    png = png_bytes(pixels)
    await local_storage.put(page, png, content_type="image/png", max_bytes=len(png))

    response = await _post(api_client, stage, INSET, index=1)

    assert response.status_code == 200, response.text


async def test_quality_set_corners__source_over_byte_cap(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tệp nguồn vượt `QUALITY_PAGE_MAX_BYTES` → 422 `IMAGE_TOO_LARGE`, dừng đọc, không lượt mới."""
    stage = await make_stage(db_session, local_storage)
    tune(monkeypatch, quality_page_max_bytes=100)

    response = await _post(api_client, stage, INSET)

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "IMAGE_TOO_LARGE"
    assert await run_count(db_sessionmaker, stage.floors[0].floor.pk) == 0


async def test_quality_set_corners__stale_run_cannot_overwrite(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: Clock,
) -> None:
    """#31 xong khi lượt đầu còn `preprocess`: `save_assessment(lượt đầu)` → `None`, `corners` vẫn là góc người dùng."""
    stage = await make_stage(db_session, local_storage)
    drawn = stage.floors[0]
    shot = desk_shot(SHOT_W, SHOT_H)
    await measure_real(db_session, fake_clock, drawn, shot.pixels)
    first_run = (await runs_of(db_sessionmaker, drawn.floor.pk))[0]
    assert (await _post(api_client, stage, shot.corners)).status_code == 200

    late = await save_assessment(
        db_session,
        run_id=first_run.id,
        floor_pk=drawn.floor.pk,
        drawing_id=drawn.drawing.id,
        page_key=drawn.drawing.page_key,
        width_px=SHOT_W,
        height_px=SHOT_H,
        report=assess(RgbImage(shot.pixels)),
        homography={},
        clock=fake_clock,
    )

    assert late is None
    kept = await load_assessment(db_session, drawn.floor.pk)
    assert kept is not None
    assert kept.corners is not None


async def test_quality_set_corners__complete_upload_without_original(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: Clock
) -> None:
    """Lỗi lược đồ: upload `complete` mất `original_key` → `ValueError` (lỗi lập trình, không phải 4xx)."""
    stage = await make_stage(db_session, local_storage)
    await db_session.execute(
        update(UploadRow).where(UploadRow.id == stage.floors[0].upload.id).values(original_key=None)
    )
    await db_session.commit()
    body = SetCornersIn.model_validate(corners_body(INSET))

    with pytest.raises(ValueError, match="thiếu tệp gốc"):
        await service.set_corners(
            db_session, local_storage, project_id=stage.project.id, level_id=stage.level(), body=body, clock=fake_clock
        )


async def test_quality_set_corners__concurrent_no_500(
    api_app: Any, db_session: AsyncSession, local_storage: LocalDiskStorage
) -> None:
    """Hai người gửi cùng lúc trên hai tầng khác nhau đều 200 (khoá theo tầng, không chặn nhau)."""
    stage = await make_stage(db_session, local_storage, floors=2)

    async with make_api_client(api_app) as a, make_api_client(api_app) as b:
        one, two = await asyncio.gather(_post(a, stage, INSET, index=0), _post(b, stage, INSET, index=1))

    assert (one.status_code, two.status_code) == (200, 200), (one.text, two.text)


@pytest.mark.parametrize("target", ["upsert_drawing", "save_assessment"])
async def test_quality_set_corners__J09_writer_returns_none(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    broker: SyncRedis,
    monkeypatch: pytest.MonkeyPatch,
    target: str,
) -> None:
    """Hàm ghi trả `None` (lượt bị thay) → như "sai": 409, rollback cả `start_run`, hàng rỗng, object mới bị xoá."""
    stage = await make_stage(db_session, local_storage)
    objects = await page_objects(local_storage, stage.floors[0])

    async def refuse(*_args: Any, **_kwargs: Any) -> None:
        """Hàm ghi B2-04/D nhìn thấy lượt đã bị thay: trả `None`, không ghi gì."""
        return None

    monkeypatch.setattr(service, target, refuse)
    broker.delete(CPU_QUEUE)

    response = await _post(api_client, stage, INSET)

    assert response.status_code == 409, response.text
    assert response.json()["code"] == "QUALITY_DRAWING_CHANGED"
    assert await run_count(db_sessionmaker, stage.floors[0].floor.pk) == 0
    assert await page_objects(local_storage, stage.floors[0]) == objects
    assert queued_payloads(broker, CPU_QUEUE) == []


@pytest.mark.parametrize(
    "failure",
    [OSError(errno.EIO, "đĩa lỗi"), DEPENDENCY_UNAVAILABLE.error(retry_after=2)],
    ids=["os_error", "unavailable"],
)
async def test_quality_set_corners__orphan_delete_failure_keeps_the_real_error(
    api_client: httpx.AsyncClient,
    api_app: Any,
    db_session: AsyncSession,
    local_storage: LocalDiskStorage,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    failure: BaseException,
) -> None:
    """NO-228: xoá object bên thua lỗi kho → client vẫn nhận 409 gốc, có log `quality_orphan_delete_failed`."""
    stage = await make_stage(db_session, local_storage)

    async def refuse(*_args: Any, **_kwargs: Any) -> None:
        """Hàm ghi B2-04 thấy lượt đã bị thay: trả `None` để ép nhánh 409."""
        return None

    async def broken_delete(_key: str) -> None:
        """Kho hỏng đúng lúc dọn object mồ côi."""
        raise failure

    monkeypatch.setattr(service, "upsert_drawing", refuse)
    monkeypatch.setattr(api_app.state.storage, "delete", broken_delete)

    with caplog.at_level(logging.WARNING):
        response = await _post(api_client, stage, INSET)

    assert response.status_code == 409, response.text
    assert response.json()["code"] == "QUALITY_DRAWING_CHANGED"
    assert "quality_orphan_delete_failed" in [record.getMessage() for record in caplog.records]
