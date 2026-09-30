"""Runtime của `pipeline.persist.run`: task thật, ba ca hỏng, J09, J10 và `fail_step` (B5-06b [8]).

Chia việc với test lõi (việc A): ở đây chỉ những ca phải đi qua **dây** thật — hàm task mỏng,
`define_task`/`on_failed`, callback sau commit, hàng `pipeline.cpu` — còn luật nghiệp vụ từng bước
của `run_persist` kiểm ở lõi. J01 đầy đủ (đọc lại tài liệu, phiên bản, thông báo) cũng là việc của
lõi; `__J01_smoke` dưới đây chỉ khẳng định dây task chạy hết và gửi đúng một bước kế tiếp.

Dịch vụ thật (K23): Postgres, Redis, kho đĩa `local_storage`. Không `fakeredis`, không
`task_always_eager` — task cùng hàng `pipeline.cpu` với thông điệp nó gửi nên `__J01_smoke` dùng
`task.apply` (BE-00 §7 "Test task"), còn `__J03` cần `on_failed` của `define_task` nên dựng worker
thật nghe `pipeline.cpu` (ca hỏng không gửi thông điệp nào, worker không nuốt gì để đếm).
"""

import asyncio
import dataclasses
import logging
import time
from collections.abc import Callable, Coroutine, Iterator
from functools import partial
from pathlib import Path
from typing import Final

import pytest
from celery import Celery
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.drawings.progress import progress_wire
from apps.api.spatial_read.documents import load_document
from apps.api.spatial_write.errors import LAYER_INTEGRITY_BROKEN
from apps.worker.pipeline_build.errors import PIPELINE_ARTIFACT_INVALID, PIPELINE_ARTIFACT_MISSING
from apps.worker.pipeline_persist import service, tasks
from apps.worker.pipeline_persist.constants import STEP
from apps.worker.pipeline_persist.tests.helpers import Arranged, open_run_at_build, put_layer, sample_built
from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.core.settings import reset_settings_cache
from packages.db.engine import create_engine, create_sessionmaker
from packages.db.models.notifications import NotificationRow
from packages.db.models.versions import VersionRecord
from packages.db.settings import DatabaseSettings, reset_database_settings_cache
from packages.messaging.celery_app import send_task
from packages.messaging.payloads.pipeline import RunStepPayload
from packages.messaging.redis import AsyncRedis, SyncRedis, broker_redis_sync
from packages.messaging.streams import upload_stream, user_stream
from packages.messaging.tasks import PermanentError
from packages.storage.local import LocalDiskStorage
from packages.storage.settings import reset_storage_settings_cache
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.db import drop_after_commit
from packages.testing.fixtures.messaging import WorkerFactory, queued_payloads

type Maker = async_sessionmaker[AsyncSession]

CPU_QUEUE: Final = "pipeline.cpu"
PERSIST_TASK: Final = "pipeline.persist.run"
FAIL_WAIT_S: Final = 60.0
"""Trần **chờ** worker đánh hỏng một lượt — chống treo, không phải trần hiệu năng (nên không `perf`)."""

_log = logging.getLogger(__name__)


@pytest.fixture
def broker(messaging_env: None) -> Iterator[SyncRedis]:
    """Client broker thật; hàng `pipeline.cpu` dùng chung cả phiên nên xoá hai đầu (BE-00 §12)."""
    client = broker_redis_sync()
    client.delete(CPU_QUEUE)
    yield client
    client.delete(CPU_QUEUE)
    client.close()


@pytest.fixture
def process_env(db_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Môi trường của một tiến trình worker thật: DB test riêng, kho local trong `tmp_path`.

    Khuôn `apps/worker/pipeline_orchestrate/tests/test_start_cases.py`. Hàm task tự dựng
    `worker_sessionmaker()` trên vòng sự kiện của **chính nó**, nên không đưa `db_sessionmaker` của
    fixture vào task (engine đó gắn vòng của pytest-asyncio — dùng chéo vòng ném "attached to a
    different loop"); vì vậy `DATABASE_URL` phải có trong biến môi trường. Cache settings và kho đã
    nhớ theo tiến trình xoá ở hai đầu: URL của DB và của kho đổi mỗi test.
    """
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path / "objects"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://appback.test")
    monkeypatch.setenv("SECRET_KEY", "fixture-secret-for-pipeline-persist-runtime-01")
    caches = (reset_settings_cache, reset_database_settings_cache, reset_storage_settings_cache)
    for reset in caches:
        reset()
    tasks.reset_persist_storage()
    yield
    tasks.reset_persist_storage()
    for reset in caches:
        reset()


def on_own_loop[T](db_url: str, work: Callable[[Maker], Coroutine[object, object, T]]) -> T:
    """Chạy `work` trên engine dựng riêng cho vòng `asyncio.run` này; trả kết quả của nó.

    Test đồng bộ (`task.apply`, worker thật) phải vào DB nhiều lượt, mà engine của `db_sessionmaker`
    gắn vào vòng sự kiện của pytest-asyncio: lượt `asyncio.run` thứ hai dùng nó ném "attached to a
    different loop" (khuôn `apps/api/auth_recovery/tests/test_jobs.py`). Engine dựng và `dispose`
    trong cùng vòng nên không kết nối nào sống qua ranh giới vòng.
    """

    async def main() -> T:
        """Thân chạy trên vòng mới: dựng engine, làm việc, luôn `dispose`."""
        engine = create_engine(DatabaseSettings(database_url=db_url))
        try:
            return await work(create_sessionmaker(engine))
        finally:
            await engine.dispose()

    return asyncio.run(main())


def _broken_layer(level_id: str) -> bytes:
    """`layer.json` hợp lệ về schema nhưng ô mở trỏ tường không có — bỏ hết `walls` khỏi lớp AI.

    `merge_pipeline_result` không kiểm tham chiếu chéo, nên lỗi đến từ chính `write_layer` (B3-03)
    như trên đường thật, chứ không phải từ bước trộn.
    """
    built = sample_built(level_id)
    return dataclasses.replace(built, layer=built.layer.model_copy(update={"walls": ()})).to_json()


async def _arrange(
    maker: Maker, storage: LocalDiskStorage, clock: FakeClock, *, layer: bytes | None = None
) -> Arranged:
    """Lượt đang ở `spatialDataBuild` + `layer.json` trong kho; `layer=None` → lớp mẫu hợp lệ."""
    arranged = await open_run_at_build(maker, clock)
    await put_layer(storage, arranged, sample_built(arranged.level_id).to_json() if layer is None else layer)
    return arranged


def _quality_messages(client: SyncRedis, run_id: str) -> list[dict[str, object]]:
    """Thông điệp `pipeline.quality.run` của đúng lượt này trên hàng `pipeline.cpu`.

    Lọc hai lần: theo `run_id`, và theo **hình dạng** payload — `start_run` của lúc dựng cảnh cũng
    xếp một `pipeline.orchestrate.start` mang cùng `run_id` lên hàng này, nhưng payload của nó có
    thêm `upload_id`, còn `RunStepPayload` chỉ có đúng hai khoá. `queued_payloads` bóc vỏ kombu nên
    không còn tên task để lọc, hình dạng là dấu hiệu chắc chắn còn lại.
    """
    wanted = {"schema_version", "run_id"}
    queued = queued_payloads(client, CPU_QUEUE)
    return [item for item in queued if item.get("run_id") == run_id and set(item) == wanted]


async def _progress(maker: Maker, upload_id: str) -> dict[str, object]:
    """`Progress` đọc lại trên session mới: trạng thái đã commit, không phải cache của session cũ."""
    async with maker() as db:
        return await progress_wire(db, upload_id)


async def _row_count(maker: Maker, model: type[NotificationRow] | type[VersionRecord]) -> int:
    """Số dòng của một bảng — dùng để khẳng định "không ghi gì" và "đúng một dòng"."""
    async with maker() as db:
        return int((await db.execute(select(func.count()).select_from(model))).scalar_one())


async def _no_writes(maker: Maker, *, floor_pk: int) -> None:
    """Ca hỏng không để lại tài liệu, phiên bản hay thông báo nào (J03, J09)."""
    async with maker() as db:
        assert await load_document(db, floor_pk) is None
    assert await _row_count(maker, VersionRecord) == 0
    assert await _row_count(maker, NotificationRow) == 0


def _wait_failed(db_url: str, upload_id: str, deadline: float) -> dict[str, object]:
    """Chờ tới `deadline` cho tới khi `Progress` của lượt tải thành `failed`; hết hạn → trả bản cuối."""
    wire = on_own_loop(db_url, lambda maker: _progress(maker, upload_id))
    while time.monotonic() < deadline and wire.get("status") != "failed":
        time.sleep(0.1)
        wire = on_own_loop(db_url, lambda maker: _progress(maker, upload_id))
    return wire


@pytest.mark.usefixtures("process_env")
def test_persist_pipeline_result__J01_smoke(
    db_url: str,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    broker: SyncRedis,
    celery_test_app: Celery,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task thật qua `task.apply`, **không** gọi `after_commit_idle`: đúng một `pipeline.quality.run`.

    Task gửi bước kế tiếp lên chính hàng `pipeline.cpu` mà nó chạy trên đó, nên BE-00 §7 đòi
    `task.apply` chứ không dựng worker thật (worker sẽ nuốt mất thông điệp cần đếm). `celery_test_app`
    đặt `DB_AFTER_COMMIT_INLINE=1` như tiến trình worker, nên `on_after_commit` chạy tại chỗ trong
    lượt commit và test không phải chờ gì.

    Kho vẫn trỏ qua `_STORAGE._factory` để dùng chung `local_storage` đã mồi `layer.json`; DB thì
    task tự dựng từ `DATABASE_URL` của `process_env`. Không mang marker `perf`: test mang mã case
    không được là test `perf` (cổng bước 5b), số đo thời gian ghi bằng `logging`.
    """
    monkeypatch.setattr(tasks._STORAGE, "_factory", lambda: local_storage)
    arranged = on_own_loop(db_url, lambda maker: _arrange(maker, local_storage, fake_clock))

    start = time.monotonic()
    tasks.persist_pipeline_result.apply(args=[arranged.payload.model_dump(mode="json")])
    _log.info("j01_smoke_elapsed_s=%.3f", time.monotonic() - start)

    assert len(_quality_messages(broker, arranged.run_id)) == 1
    assert on_own_loop(db_url, lambda maker: _progress(maker, arranged.upload_id))["status"] == "running"


@pytest.mark.usefixtures("process_env")
def test_persist_pipeline_result__J03(
    db_url: str,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    broker: SyncRedis,
    celery_worker_factory: WorkerFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ba ca hỏng qua worker thật: `Progress` `failed` + đúng mã, không `endedAt`, không ghi gì.

    Một test cho cả ba ca chứ không `parametrize`: `case_gate` nhận case qua tên hàm
    (`^test_<fn>__J\\d{2}$`) mà hậu tố `[…]` của `parametrize` trượt regex đó.

    Ba ca là đúng ba đường lỗi của [6] bước 2 và bước 5: object vắng, JSON hỏng, ô mở trỏ tường không
    có. Mỗi ca một lượt chạy riêng vì lượt đã `failed` không nhận kết quả nữa. Worker nghe
    `pipeline.cpu` được: ca hỏng không gửi thông điệp nào nên không có gì bị nuốt.
    """
    monkeypatch.setattr(tasks._STORAGE, "_factory", lambda: local_storage)
    cases: tuple[tuple[str, Callable[[Arranged], bytes | None], str], ...] = (
        ("artifact vắng", lambda _a: None, PIPELINE_ARTIFACT_MISSING),
        ("json hỏng", lambda _a: b"{khong-phai-json", PIPELINE_ARTIFACT_INVALID),
        ("ô mở trỏ tường không có", lambda a: _broken_layer(a.level_id), LAYER_INTEGRITY_BROKEN.code),
    )

    with celery_worker_factory([CPU_QUEUE]):
        for label, make_layer, code in cases:
            arranged = on_own_loop(db_url, lambda maker: open_run_at_build(maker, fake_clock))
            data = make_layer(arranged)
            if data is not None:
                asyncio.run(put_layer(local_storage, arranged, data))
            send_task(PERSIST_TASK, arranged.payload)
            wire = _wait_failed(db_url, arranged.upload_id, time.monotonic() + FAIL_WAIT_S)
            assert wire["status"] == "failed", label
            assert wire["error"] == code, label
            assert "endedAt" not in wire, label
            assert wire["step"] == STEP, label
            on_own_loop(db_url, partial(_no_writes, floor_pk=arranged.floor_pk))


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_pipeline_result__J09(
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    broker: SyncRedis,
    streams_client: AsyncRedis,
) -> None:
    """Lỗi giữa giao dịch rollback cả bản "trước": hàng `pipeline.cpu` và `user_stream` rỗng.

    Gọi thẳng lõi và **không** dựng worker nào nghe `pipeline.cpu` (BE-00 §12) để đếm được rằng
    không thông điệp nào đi ra. Ca dùng là `LAYER_INTEGRITY_BROKEN` vì nó hỏng ở bước 5, tức **sau**
    `create_version` của bước 4 — giao dịch không rollback thì phiên bản "trước" sẽ còn lại.
    """
    arranged = await open_run_at_build(db_sessionmaker, fake_clock)
    await put_layer(local_storage, arranged, _broken_layer(arranged.level_id))

    with pytest.raises(PermanentError) as caught:
        await service.run_persist(
            arranged.payload, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock
        )

    assert caught.value.code == LAYER_INTEGRITY_BROKEN.code
    assert _quality_messages(broker, arranged.run_id) == []
    assert await streams_client.xlen(user_stream(arranged.uploader_id)) == 0
    await _no_writes(db_sessionmaker, floor_pk=arranged.floor_pk)


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_pipeline_result__J10(
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    broker: SyncRedis,
    streams_client: AsyncRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lượt đầu commit xong rồi chết trước khi phát → gọi lại `replayed`, không nhân đôi tác dụng.

    `drop_after_commit()` bỏ callback sau commit, đúng hình dạng "worker chết ngay sau commit": DB đã
    có phiên bản và thông báo, nhưng chưa có thông điệp `pipeline.quality.run`, chưa `Progress`, chưa
    mục `user_stream`. Nhánh phát lại phải bù đúng **một** lần mỗi thứ (K18, K32).
    """
    monkeypatch.setenv("APP_ENV", "test")
    arranged = await _arrange(db_sessionmaker, local_storage, fake_clock)
    before = await streams_client.xlen(upload_stream(arranged.upload_id))

    with drop_after_commit():
        first = await service.run_persist(
            arranged.payload, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock
        )
    assert first == "persisted"
    assert _quality_messages(broker, arranged.run_id) == []
    # Lượt đầu chết trước khi phát: không khung `Progress` nào, kể cả khung của `record_step`.
    assert await streams_client.xlen(upload_stream(arranged.upload_id)) == before

    second = await service.run_persist(
        arranged.payload, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock
    )

    assert second == "replayed"
    assert len(_quality_messages(broker, arranged.run_id)) == 1
    assert await streams_client.xlen(upload_stream(arranged.upload_id)) == before + 1
    assert await streams_client.xlen(user_stream(arranged.uploader_id)) == 1
    assert await _row_count(db_sessionmaker, NotificationRow) == 1


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_fail_step_marks_step_failed(db_sessionmaker: Maker, fake_clock: FakeClock) -> None:
    """`fail_step` trên lượt còn hiệu lực: `Progress` `failed` mang mã, vẫn không có `endedAt` (K33)."""
    arranged = await open_run_at_build(db_sessionmaker, fake_clock)

    await service.fail_step(arranged.payload, PIPELINE_ARTIFACT_MISSING, sessionmaker=db_sessionmaker, clock=fake_clock)

    wire = await _progress(db_sessionmaker, arranged.upload_id)
    assert wire["status"] == "failed"
    assert wire["error"] == PIPELINE_ARTIFACT_MISSING
    assert "endedAt" not in wire


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_fail_step_ignores_missing_run(db_sessionmaker: Maker, fake_clock: FakeClock) -> None:
    """`run_id` không có dòng nào → `fail_step` im lặng: `on_failed` chạy cả với thông điệp lạc."""
    payload = RunStepPayload(schema_version=1, run_id=new_id("run", SystemClock()))

    await service.fail_step(payload, PIPELINE_ARTIFACT_MISSING, sessionmaker=db_sessionmaker, clock=fake_clock)

    assert await _row_count(db_sessionmaker, VersionRecord) == 0
