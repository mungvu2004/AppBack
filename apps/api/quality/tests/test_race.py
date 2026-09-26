"""Đua của #31 (C14 theo việc), lượt của lần tải mới và J09 (B2-05b [8] "Đua", "J09")."""

import asyncio
from typing import Any, Final

import httpx
from fastapi import FastAPI
from redis import Redis as SyncRedis
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.drawings.runs import start_run
from apps.api.quality.tests._images import desk_shot, png_bytes
from apps.api.quality.tests._route_helpers import (
    CPU_QUEUE,
    SHOT_H,
    SHOT_W,
    HookedStorage,
    Stage,
    corners_body,
    corners_path,
    make_stage,
    page_objects,
    run_count,
    runs_of,
)
from apps.api.quality.tests._route_helpers import (
    broker as broker,
)
from apps.api.quality.tests._route_helpers import (
    quality_env as quality_env,
)
from packages.core.clock import Clock
from packages.db.hooks import after_commit_idle
from packages.db.models.drawings import PipelineRunRow
from packages.storage.local import LocalDiskStorage
from packages.testing.factories.drawings import make_complete_upload
from packages.testing.fixtures.api import make_api_client
from packages.testing.fixtures.messaging import queued_payloads

INSET_A: Final = ((0.05, 0.05), (0.95, 0.05), (0.95, 0.95), (0.05, 0.95))
INSET_B: Final = ((0.10, 0.10), (0.90, 0.10), (0.90, 0.90), (0.10, 0.90))
GATE_WAIT_S: Final = 20.0


async def _post(client: httpx.AsyncClient, stage: Stage, points: Any) -> httpx.Response:
    """#31 trên tầng đầu của sân khấu."""
    return await client.post(
        corners_path(stage.project.id, stage.level()), json=corners_body(points), headers=stage.headers
    )


async def _newer_upload(db: AsyncSession, storage: LocalDiskStorage, stage: Stage) -> str:
    """Thêm một lượt tải `complete` mới hơn bản vẽ của tầng đầu; trả `upload_id` của nó."""
    png = png_bytes(desk_shot(SHOT_W, SHOT_H).pixels)
    upload = await make_complete_upload(db, storage, project=stage.project, floor=stage.floors[0].floor, data=png)
    return upload.id


async def test_quality_set_corners__C14(
    api_app: FastAPI,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    broker: SyncRedis,
) -> None:
    """Hai #31 song song khác góc → một 200, một 409, object bên thua bị xoá, đúng một lượt mới."""
    stage = await make_stage(db_session, local_storage)
    drawn = stage.floors[0]
    broker.delete(CPU_QUEUE)
    async with make_api_client(api_app) as client_a, make_api_client(api_app) as client_b:
        gate = HookedStorage(api_app.state.storage, parties=2)
        api_app.state.storage = gate
        tasks = [
            asyncio.create_task(_post(client_a, stage, INSET_A)),
            asyncio.create_task(_post(client_b, stage, INSET_B)),
        ]
        await asyncio.wait_for(gate.entered.wait(), GATE_WAIT_S)
        gate.release.set()
        responses = await asyncio.gather(*tasks)

    assert sorted(r.status_code for r in responses) == [200, 409], [r.text for r in responses]
    loser = next(r for r in responses if r.status_code == 409)
    assert loser.json()["code"] == "QUALITY_DRAWING_CHANGED"
    assert await run_count(db_sessionmaker, drawn.floor.pk) == 1
    assert len(await page_objects(local_storage, drawn)) == 2  # trang cũ + trang của bên thắng
    assert len(queued_payloads(broker, CPU_QUEUE)) == 1


async def test_quality_set_corners__newer_upload_blocks_then_failed_run_frees(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: Clock,
    broker: SyncRedis,
) -> None:
    """Upload mới hơn, lượt chưa `failed` → 409 và lượt đó giữ nguyên; lượt `failed` → 200, N7 trả upload của bản vẽ."""
    stage = await make_stage(db_session, local_storage)
    drawn = stage.floors[0]
    newer_id = await _newer_upload(db_session, local_storage, stage)
    newer_run = await start_run(db_session, upload_id=newer_id, clock=fake_clock)
    await db_session.commit()
    await after_commit_idle(db_session)
    broker.delete(CPU_QUEUE)

    blocked = await _post(api_client, stage, INSET_A)

    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["code"] == "QUALITY_DRAWING_CHANGED"
    (kept,) = await runs_of(db_sessionmaker, drawn.floor.pk)
    assert (kept.id, kept.status, kept.superseded_by) == (newer_run.id, "pending", None)
    assert queued_payloads(broker, CPU_QUEUE) == []

    await db_session.execute(update(PipelineRunRow).where(PipelineRunRow.id == newer_run.id).values(status="failed"))
    await db_session.commit()
    freed = await _post(api_client, stage, INSET_A)

    assert freed.status_code == 200, freed.text
    latest = await api_client.get(f"/api/projects/{stage.project.id}/drawings/uploads/latest", headers=stage.headers)
    assert [item["uploadId"] for item in latest.json()["items"]] == [drawn.upload.id]


async def test_quality_set_corners__J09_rollback_queues_nothing(
    api_app: FastAPI,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: Clock,
    broker: SyncRedis,
) -> None:
    """Lần tải mới chen vào giữa lúc xử lý → 409, hàng đợi rỗng, không lượt mới, object mới bị xoá."""
    stage = await make_stage(db_session, local_storage)
    drawn = stage.floors[0]
    broker.delete(CPU_QUEUE)
    objects = await page_objects(local_storage, drawn)
    async with make_api_client(api_app) as client:
        gate = HookedStorage(api_app.state.storage)
        api_app.state.storage = gate
        request = asyncio.create_task(_post(client, stage, INSET_A))
        await asyncio.wait_for(gate.entered.wait(), GATE_WAIT_S)
        newer_id = await _newer_upload(db_session, local_storage, stage)
        await start_run(db_session, upload_id=newer_id, clock=fake_clock)
        await db_session.commit()
        await after_commit_idle(db_session)
        broker.delete(CPU_QUEUE)
        gate.release.set()
        response = await request

    assert response.status_code == 409, response.text
    assert response.json()["code"] == "QUALITY_DRAWING_CHANGED"
    assert await run_count(db_sessionmaker, drawn.floor.pk) == 1  # chỉ lượt của lần tải mới
    assert await page_objects(local_storage, drawn) == objects
    assert queued_payloads(broker, CPU_QUEUE) == []
