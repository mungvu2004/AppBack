"""Task `run_lighting_bake`: J01-J06 trên lõi `bake_lighting` (LB-01).

Chỉ ranh giới tiến trình con là giả (`fake_blender.py` chạy bằng Python hiện tại); Postgres, kho
local, khoá Redis `gpu:0` đều thật. Như `apps/worker/datasets/tests/test_tasks.py`: việc
`define_task` đổi lỗi thành mã là hợp đồng B0-05, ở đây kiểm lõi ném đúng lỗi và `fail_lighting_bake`
(thân của `on_failed`) dọn đúng chỗ.
"""

import json

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.lighting_bake import state
from apps.worker.lighting_bake import tasks
from apps.worker.lighting_bake.tasks import bake_lighting, fail_lighting_bake
from apps.worker.lighting_bake.tests.fake_blender import argv_for
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.core.errors import AppError
from packages.db.models.lighting_bake import LightingBakeRow
from packages.messaging import PermanentError, SafeLock, safe_redis
from packages.messaging.payloads.lighting_bake import LIGHTING_BAKE_FILES, LIGHTING_BAKE_INPUT
from packages.messaging.redis import AsyncRedis
from packages.storage.keys import lighting_bake_object, lighting_bake_prefix
from packages.storage.local import LocalDiskStorage
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.lighting_bake import QueueBake

Maker = async_sessionmaker[AsyncSession]


async def _keys(storage: LocalDiskStorage, project_id: str, bake_id: str) -> list[str]:
    """Tên object dưới tiền tố của một lượt, sắp tăng."""
    prefix = lighting_bake_prefix(project_id, bake_id)
    return sorted([info.key.rsplit("/", 1)[-1] async for info in storage.list_prefix(prefix)])


async def _row(maker: Maker, bake_id: str) -> LightingBakeRow:
    """Dòng `lighting_bakes` đọc lại bằng session mới."""
    async with maker() as db:
        return (await db.execute(select(LightingBakeRow).where(LightingBakeRow.id == bake_id))).scalar_one()


async def _manifest(storage: LocalDiskStorage, project_id: str, bake_id: str) -> dict[str, object]:
    """`manifest.json` đã lưu của một lượt."""
    key = lighting_bake_object(project_id, bake_id, "manifest.json")
    loaded: dict[str, object] = json.loads(b"".join([chunk async for chunk in storage.open_read(key)]))
    return loaded


async def test_run_lighting_bake__J01(
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    safe_client: AsyncRedis,
    queue_bake: QueueBake,
) -> None:
    """Lượt hợp lệ → `done`, ba tệp, `input.glb` bị xoá; object của lượt cũ hơn cùng dự án bị dọn, dòng giữ."""
    old = await queue_bake(status="done")
    bake = await queue_bake(project_id=old.project_id)

    await bake_lighting(db_sessionmaker, local_storage, fake_clock, bake_id=bake.bake_id, argv_for=argv_for("ok"))

    assert (await _row(db_sessionmaker, bake.bake_id)).status == "done"
    assert await _keys(local_storage, bake.project_id, bake.bake_id) == sorted(LIGHTING_BAKE_FILES)
    assert (await _manifest(local_storage, bake.project_id, bake.bake_id))["cuda"] is None
    assert await _keys(local_storage, old.project_id, old.bake_id) == []
    assert (await _row(db_sessionmaker, old.bake_id)).status == "done"


async def test_run_lighting_bake__J01_gpu_busy(
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    safe_client: AsyncRedis,
    queue_bake: QueueBake,
) -> None:
    """`gpu:0` đang bị giữ → không chờ, chạy CPU với `CUDA_VISIBLE_DEVICES=""`."""
    bake = await queue_bake()
    rival = SafeLock(safe_redis(), tasks.GPU_LOCK_NAME, 60_000)
    token = await rival.acquire()
    assert token is not None
    try:
        await bake_lighting(db_sessionmaker, local_storage, fake_clock, bake_id=bake.bake_id, argv_for=argv_for("ok"))
    finally:
        await rival.release(token)

    assert (await _row(db_sessionmaker, bake.bake_id)).status == "done"
    assert (await _manifest(local_storage, bake.project_id, bake.bake_id))["cuda"] == ""


async def test_run_lighting_bake__J02(
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    safe_client: AsyncRedis,
    queue_bake: QueueBake,
) -> None:
    """Blender bị `SIGKILL` không do cha (OOM) → `DEPENDENCY_UNAVAILABLE` (thử lại); lượt hai `done`."""
    bake = await queue_bake()

    with pytest.raises(AppError) as caught:
        await bake_lighting(
            db_sessionmaker, local_storage, fake_clock, bake_id=bake.bake_id, argv_for=argv_for("killed")
        )
    assert caught.value.code is DEPENDENCY_UNAVAILABLE
    assert (await _row(db_sessionmaker, bake.bake_id)).status == "running"
    assert await _keys(local_storage, bake.project_id, bake.bake_id) == [LIGHTING_BAKE_INPUT]

    await bake_lighting(db_sessionmaker, local_storage, fake_clock, bake_id=bake.bake_id, argv_for=argv_for("ok"))

    assert (await _row(db_sessionmaker, bake.bake_id)).status == "done"
    assert await _keys(local_storage, bake.project_id, bake.bake_id) == sorted(LIGHTING_BAKE_FILES)


async def test_run_lighting_bake__J03(
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    safe_client: AsyncRedis,
    queue_bake: QueueBake,
) -> None:
    """Hai ca hỏng vĩnh viễn: Blender thoát 1, thiếu tệp ra; `on_failed` → `failed` + tiền tố rỗng."""
    for mode, code in (("fail", state.LIGHTING_BAKE_FAILED), ("missing", state.LIGHTING_BAKE_OUTPUT_INVALID)):
        bake = await queue_bake()
        with pytest.raises(PermanentError, match=code):
            await bake_lighting(
                db_sessionmaker, local_storage, fake_clock, bake_id=bake.bake_id, argv_for=argv_for(mode)
            )

        await fail_lighting_bake(db_sessionmaker, local_storage, fake_clock, bake_id=bake.bake_id, code=code)

        row = await _row(db_sessionmaker, bake.bake_id)
        assert (row.status, row.failure_code) == ("failed", code)
        assert await _keys(local_storage, bake.project_id, bake.bake_id) == []


async def test_run_lighting_bake__J05(
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    safe_client: AsyncRedis,
    queue_bake: QueueBake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Blender quá `timeout_s` → giết nhóm tiến trình, `LIGHTING_BAKE_TIMEOUT`; giờ mềm Celery thoát nguyên vẹn."""
    bake = await queue_bake()

    with pytest.raises(PermanentError, match=state.LIGHTING_BAKE_TIMEOUT):
        await bake_lighting(
            db_sessionmaker, local_storage, fake_clock, bake_id=bake.bake_id, argv_for=argv_for("sleep"), timeout_s=1
        )
    await fail_lighting_bake(
        db_sessionmaker, local_storage, fake_clock, bake_id=bake.bake_id, code=state.LIGHTING_BAKE_TIMEOUT
    )
    assert (await _row(db_sessionmaker, bake.bake_id)).failure_code == state.LIGHTING_BAKE_TIMEOUT
    assert await _keys(local_storage, bake.project_id, bake.bake_id) == []

    other = await queue_bake()

    async def soft_limit(*_: object, **__: object) -> None:
        """Giờ mềm của Celery tới giữa lượt Blender."""
        raise SoftTimeLimitExceeded

    monkeypatch.setattr(tasks, "_run_blender", soft_limit)
    with pytest.raises(SoftTimeLimitExceeded):
        await bake_lighting(db_sessionmaker, local_storage, fake_clock, bake_id=other.bake_id, argv_for=argv_for("ok"))
    assert (await _row(db_sessionmaker, other.bake_id)).status == "running"

    await fail_lighting_bake(db_sessionmaker, local_storage, fake_clock, bake_id=other.bake_id, code="TASK_TIMEOUT")
    assert (await _row(db_sessionmaker, other.bake_id)).failure_code == state.LIGHTING_BAKE_TIMEOUT
    assert await _keys(local_storage, other.project_id, other.bake_id) == []


async def test_run_lighting_bake__J06(
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    safe_client: AsyncRedis,
    queue_bake: QueueBake,
) -> None:
    """Giao lặp sau `done` → `claim` 0 dòng, no-op: không chạy Blender, object và dòng giữ nguyên."""
    bake = await queue_bake()
    await bake_lighting(db_sessionmaker, local_storage, fake_clock, bake_id=bake.bake_id, argv_for=argv_for("ok"))
    first = await _row(db_sessionmaker, bake.bake_id)

    await bake_lighting(db_sessionmaker, local_storage, fake_clock, bake_id=bake.bake_id, argv_for=argv_for("fail"))

    again = await _row(db_sessionmaker, bake.bake_id)
    assert (again.status, again.ended_at) == ("done", first.ended_at)
    assert await _keys(local_storage, bake.project_id, bake.bake_id) == sorted(LIGHTING_BAKE_FILES)
