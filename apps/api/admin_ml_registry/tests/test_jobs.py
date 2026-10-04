"""Lịch `requeue_evaluations`, `purge_orphans` và ranh giới nhập (B6-01 [6], [8] "Lịch",
"Sau commit trong worker", "Ranh giới"). Postgres, Redis, kho local đều thật (K23)."""

import asyncio
import os
import subprocess
import sys
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

import pytest
from celery import Celery
from sqlalchemy import event, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.admin_ml_registry.jobs import (
    PURGE_EVERY,
    PURGE_TASK,
    REQUEUE_EVERY,
    REQUEUE_TASK,
    purge_ml_model_orphans,
    requeue_pending_model_evaluations,
    run_model_evaluation_requeue,
    run_model_orphan_purge,
)
from apps.api.admin_ml_registry.settings import get_ml_registry_settings
from apps.api.admin_ml_registry.tests._helpers import ML_QUEUE, OPENING
from packages.core.ids import new_id
from packages.core.settings import reset_settings_cache
from packages.db.engine import create_engine, create_sessionmaker
from packages.db.models.admin_ml_registry import ModelVersionRow
from packages.db.settings import get_database_settings, reset_database_settings_cache
from packages.messaging.redis import SyncRedis, broker_redis_sync
from packages.messaging.schedules import schedule_entries
from packages.storage.keys import model_artifact
from packages.storage.local import LocalDiskStorage
from packages.storage.settings import reset_storage_settings_cache
from packages.testing.factories.admin_ml_registry import make_model_version
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.messaging import WorkerFactory, queued_payloads

REPO_ROOT: Final = Path(__file__).resolve().parents[4]
BASELINE_IDS: Final = ("mdl_01KB6010000000000000000001", "mdl_01KB6010000000000000000002")
BLOCKED: Final = ("fastapi", "starlette", "uvicorn", "jwt", "argon2", "torch", "onnxruntime", "onnx", "ultralytics")
WORKER_WAIT_S: Final = 2.0


@pytest.fixture
def broker() -> Iterator[SyncRedis]:
    """Redis broker thật với hàng `ml.infer` rỗng đầu và cuối test (fixture broker không tự dọn)."""
    client = broker_redis_sync()
    client.delete(ML_QUEUE)
    try:
        yield client
    finally:
        client.delete(ML_QUEUE)
        client.close()


def _sent(client: SyncRedis) -> list[str]:
    """`version_id` của mọi thông điệp đang nằm trên `ml.infer`."""
    return [str(payload["version_id"]) for payload in queued_payloads(client, ML_QUEUE)]


async def _rows(maker: async_sessionmaker[AsyncSession]) -> dict[str, ModelVersionRow]:
    """Mọi bản trong DB theo id, đọc bằng session riêng."""
    async with maker() as db:
        return {row.id: row for row in (await db.execute(select(ModelVersionRow))).scalars()}


# ---------------------------------------------------------------------------
# requeue_evaluations
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("celery_test_app")
async def test_requeue_pending_model_evaluations__J01(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock, broker: SyncRedis
) -> None:
    """Mỗi bản gốc `pending` một thông điệp (`attempts` 0 → 1); mỗi mốc lùi gửi lại; lượt 7 → `failed`."""
    settings = get_ml_registry_settings()
    step = settings.model_eval_requeue_after_s

    assert await run_model_evaluation_requeue(db_sessionmaker, fake_clock) == 2
    assert sorted(_sent(broker)) == list(BASELINE_IDS)
    rows = await _rows(db_sessionmaker)
    assert [rows[i].evaluation_attempts for i in BASELINE_IDS] == [1, 1]
    assert {rows[i].evaluation_requested_at for i in BASELINE_IDS} == {fake_clock.now()}

    fake_clock.advance(timedelta(seconds=step - 1))
    assert await run_model_evaluation_requeue(db_sessionmaker, fake_clock) == 0
    for attempts in range(2, settings.model_eval_max_attempts + 1):
        fake_clock.advance(timedelta(seconds=step * 2 ** (attempts - 2) + 1))
        assert await run_model_evaluation_requeue(db_sessionmaker, fake_clock) == 2
        rows = await _rows(db_sessionmaker)
        assert [rows[i].evaluation_attempts for i in BASELINE_IDS] == [attempts, attempts]
    assert len(_sent(broker)) == 2 * settings.model_eval_max_attempts

    fake_clock.advance(timedelta(seconds=step * 2 ** (settings.model_eval_max_attempts - 1) + 1))
    assert await run_model_evaluation_requeue(db_sessionmaker, fake_clock) == 2
    rows = await _rows(db_sessionmaker)
    for version_id in BASELINE_IDS:
        row = rows[version_id]
        assert (row.evaluation_status, row.evaluation_error_code, row.metrics) == ("failed", "RETRY_EXHAUSTED", None)
        assert row.evaluation_attempts == settings.model_eval_max_attempts
    assert len(_sent(broker)) == 2 * settings.model_eval_max_attempts
    assert await run_model_evaluation_requeue(db_sessionmaker, fake_clock) == 0


@pytest.mark.usefixtures("celery_test_app")
async def test_requeue_pending_model_evaluations__locks_the_batch_once(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock, broker: SyncRedis
) -> None:
    """Lô đã `FOR UPDATE SKIP LOCKED` sẵn: lượt chạy phát đúng một câu khoá, không khoá lại từng dòng (NO-260)."""
    statements: list[str] = []

    def record_locks(_conn: object, _cursor: object, statement: str, *_rest: object) -> None:
        """Ghi mọi câu `SELECT … FOR UPDATE` đi qua engine."""
        if "FOR UPDATE" in statement:
            statements.append(statement)

    sync_engine = db_sessionmaker.kw["bind"].sync_engine
    event.listen(sync_engine, "before_cursor_execute", record_locks)
    try:
        assert await run_model_evaluation_requeue(db_sessionmaker, fake_clock) == len(BASELINE_IDS)
    finally:
        event.remove(sync_engine, "before_cursor_execute", record_locks)

    assert len(statements) == 1
    assert sorted(_sent(broker)) == list(BASELINE_IDS)


@pytest.mark.usefixtures("celery_test_app")
async def test_requeue_pending_model_evaluations__J06(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock, broker: SyncRedis
) -> None:
    """Chạy hai lần liền: lượt hai không gửi thêm, không đổi `attempts`."""
    await run_model_evaluation_requeue(db_sessionmaker, fake_clock)
    before = await _rows(db_sessionmaker)

    assert await run_model_evaluation_requeue(db_sessionmaker, fake_clock) == 0

    assert len(_sent(broker)) == 2
    after = await _rows(db_sessionmaker)
    assert {i: after[i].evaluation_attempts for i in BASELINE_IDS} == {
        i: before[i].evaluation_attempts for i in BASELINE_IDS
    }


@pytest.mark.usefixtures("celery_test_app")
async def test_requeue_takes_running_versions_and_ignores_closed_ones(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    broker: SyncRedis,
) -> None:
    """Bản `running` quá hạn được gửi lại; `completed`, `failed` không bị đụng."""
    running = await make_model_version(db_session, family=OPENING, status="running")
    done = await make_model_version(db_session, family=OPENING, status="completed")
    failed = await make_model_version(db_session, family=OPENING, status="failed")

    await run_model_evaluation_requeue(db_sessionmaker, fake_clock)

    sent = _sent(broker)
    assert running.id in sent
    assert done.id not in sent
    assert failed.id not in sent
    rows = await _rows(db_sessionmaker)
    assert (rows[done.id].evaluation_attempts, rows[failed.id].evaluation_attempts) == (0, 0)


@pytest.mark.usefixtures("celery_test_app")
async def test_requeue_respects_the_batch_size(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock, broker: SyncRedis
) -> None:
    """`batch=1`: mỗi lượt chỉ một bản; lượt hai lấy bản còn lại."""
    assert await run_model_evaluation_requeue(db_sessionmaker, fake_clock, batch=1) == 1
    assert await run_model_evaluation_requeue(db_sessionmaker, fake_clock, batch=1) == 1
    assert sorted(_sent(broker)) == list(BASELINE_IDS)


@pytest.mark.usefixtures("celery_test_app")
async def test_requeue_skips_rows_locked_by_another_transaction(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock, broker: SyncRedis
) -> None:
    """`SKIP LOCKED`: một bản đang bị giữ khoá thì lượt lịch bỏ qua nó thay vì chờ."""
    locked_id, free_id = BASELINE_IDS
    async with db_sessionmaker() as holder:
        await holder.execute(select(ModelVersionRow).where(ModelVersionRow.id == locked_id).with_for_update())

        processed = await asyncio.wait_for(run_model_evaluation_requeue(db_sessionmaker, fake_clock), timeout=10)

        assert processed == 1
        assert _sent(broker) == [free_id]


@pytest.mark.usefixtures("celery_test_app")
async def test_requeue_honours_the_backoff_reference_of_each_row(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock, broker: SyncRedis
) -> None:
    """Hạn tính theo `attempts` của **từng** dòng: dòng `attempts=3` chưa tới hạn khi dòng `attempts=1` đã tới."""
    step = get_ml_registry_settings().model_eval_requeue_after_s
    now = fake_clock.now()
    async with db_sessionmaker() as db:
        for version_id, attempts in zip(BASELINE_IDS, (1, 3), strict=True):
            await db.execute(
                update(ModelVersionRow)
                .where(ModelVersionRow.id == version_id)
                .values(evaluation_attempts=attempts, evaluation_requested_at=now)
            )
        await db.commit()
    fake_clock.advance(timedelta(seconds=step + 1))

    assert await run_model_evaluation_requeue(db_sessionmaker, fake_clock) == 1
    assert _sent(broker) == [BASELINE_IDS[0]]


# ---------------------------------------------------------------------------
# purge_orphans
# ---------------------------------------------------------------------------


def _age(storage_root: Path, key: str, *, hours: int) -> None:
    """Lùi `mtime` của object `key` đi `hours` giờ — `list_prefix` của kho local đọc mtime thật."""
    stamp = time.time() - hours * 3600
    os.utime(storage_root / key, (stamp, stamp))


async def _put(storage: LocalDiskStorage, key: str) -> None:
    """Ghi một object nhỏ dưới `key`."""
    await storage.put(key, b"x", content_type="application/octet-stream", max_bytes=8)


async def _orphan_setup(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock, tmp_path: Path
) -> tuple[str, str, str]:
    """Ba object: mồ côi cũ, object của một bản (cũ), mồ côi trẻ. Trả `(old, kept, young)`."""
    root = tmp_path / "objects"
    old = model_artifact(new_id("mdl", fake_clock), "weights.onnx")
    young = model_artifact(new_id("mdl", fake_clock), "weights.onnx")
    row = await make_model_version(db_session, local_storage, family=OPENING)
    assert row.weights_key is not None
    await _put(local_storage, old)
    await _put(local_storage, young)
    _age(root, old, hours=48)
    _age(root, row.weights_key, hours=48)
    fake_clock.set(datetime.now(UTC))
    return old, row.weights_key, young


async def test_purge_ml_model_orphans__J01(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    tmp_path: Path,
) -> None:
    """Mồ côi cũ bị xoá; object của một bản có `weights_key` và object < 24 giờ còn."""
    old, kept, young = await _orphan_setup(db_session, local_storage, fake_clock, tmp_path)

    deleted = await run_model_orphan_purge(db_sessionmaker, local_storage, fake_clock)

    assert deleted == 1
    assert await local_storage.stat(old) is None
    assert await local_storage.stat(kept) is not None
    assert await local_storage.stat(young) is not None


async def test_purge_ml_model_orphans__J06(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    tmp_path: Path,
) -> None:
    """Chạy hai lần liền: lượt hai không xoá gì và không đụng object còn lại."""
    _old, kept, young = await _orphan_setup(db_session, local_storage, fake_clock, tmp_path)
    await run_model_orphan_purge(db_sessionmaker, local_storage, fake_clock)

    assert await run_model_orphan_purge(db_sessionmaker, local_storage, fake_clock) == 0

    assert await local_storage.stat(kept) is not None
    assert await local_storage.stat(young) is not None


async def test_purge_batches_lookups_and_never_holds_a_connection_while_deleting(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """5 mồ côi, `batch=2`: cả 5 bị xoá qua 3 lô; lúc `delete` chạy, pool không có kết nối đang mượn (K36)."""
    keys = [model_artifact(new_id("mdl", fake_clock), "weights.onnx") for _ in range(5)]
    for key in keys:
        await _put(local_storage, key)
        _age(tmp_path / "objects", key, hours=48)
    fake_clock.set(datetime.now(UTC))
    pool = db_sessionmaker.kw["bind"].pool
    checked_out: list[int] = []
    real_delete = local_storage.delete

    async def spy(key: str) -> None:
        """Ghi số kết nối đang mượn rồi xoá thật."""
        checked_out.append(pool.checkedout())
        await real_delete(key)

    monkeypatch.setattr(local_storage, "delete", spy)

    assert await run_model_orphan_purge(db_sessionmaker, local_storage, fake_clock, batch=2) == 5

    assert checked_out == [0] * 5
    assert [await local_storage.stat(key) for key in keys] == [None] * 5


# ---------------------------------------------------------------------------
# Lịch: đăng ký và test khói
# ---------------------------------------------------------------------------


def test_both_schedules_are_registered_with_their_periods() -> None:
    """Lịch đăng ký đúng tên, hàm và chu kỳ (5 phút, 24 giờ)."""
    entries = {entry.name: entry for entry in schedule_entries()}

    assert entries[REQUEUE_TASK].function == "requeue_pending_model_evaluations"
    assert entries[REQUEUE_TASK].every == REQUEUE_EVERY == timedelta(minutes=5)
    assert entries[PURGE_TASK].function == "purge_ml_model_orphans"
    assert entries[PURGE_TASK].every == PURGE_EVERY == timedelta(hours=24)


@pytest.fixture
def process_env(db_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Môi trường của một tiến trình lịch: DB test riêng, kho local trong `tmp_path`."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path / "objects"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://appback.test")
    monkeypatch.setenv("SECRET_KEY", "fixture-secret-for-ml-registry-jobs-01")
    caches = (reset_settings_cache, reset_database_settings_cache, reset_storage_settings_cache)
    for reset in caches:
        reset()
    yield
    for reset in caches:
        reset()


async def _attempts() -> dict[str, int]:
    """`attempts` của hai bản gốc, đọc từ DB của môi trường tiến trình."""
    engine = create_engine(get_database_settings())
    try:
        async with create_sessionmaker(engine)() as db:
            rows = (await db.execute(select(ModelVersionRow))).scalars()
            return {row.id: row.evaluation_attempts for row in rows}
    finally:
        await engine.dispose()


@pytest.mark.usefixtures("process_env", "celery_test_app")
def test_requeue_pending_model_evaluations_smoke(broker: SyncRedis) -> None:
    """Test khói: hàm lịch thật (`SystemClock`, `worker_sessionmaker`) gửi lại cả hai bản gốc."""
    requeue_pending_model_evaluations()
    reset_database_settings_cache()

    assert sorted(_sent(broker)) == list(BASELINE_IDS)
    assert asyncio.run(_attempts()) == {BASELINE_IDS[0]: 1, BASELINE_IDS[1]: 1}


@pytest.mark.usefixtures("process_env")
def test_purge_ml_model_orphans_smoke(local_storage: LocalDiskStorage, tmp_path: Path) -> None:
    """Test khói: hàm lịch thật mở kho local của tiến trình (cùng gốc `tmp_path/objects`) và xoá mồ côi cũ."""
    key = model_artifact("mdl_01KB6010000000000000000009", "weights.onnx")
    asyncio.run(_put(local_storage, key))
    _age(tmp_path / "objects", key, hours=48)

    purge_ml_model_orphans()

    assert not (tmp_path / "objects" / key).exists()


# ---------------------------------------------------------------------------
# Sau commit trong worker
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("process_env")
def test_scheduled_requeue_sends_after_commit_inside_a_real_worker(
    celery_test_app: Celery, celery_worker_factory: WorkerFactory, broker: SyncRedis
) -> None:
    """Worker thật (`default`) chạy task lịch: hai bản quá hạn → hai lượt gửi sau commit, thông điệp có
    trên `ml.infer` (không worker nào nghe hàng này) trong ≤ 2 s."""
    with celery_worker_factory(["default"]):
        celery_test_app.send_task(REQUEUE_TASK, queue="default")
        deadline = time.monotonic() + WORKER_WAIT_S
        while len(_sent(broker)) < 2 and time.monotonic() < deadline:
            time.sleep(0.05)

    assert sorted(_sent(broker)) == list(BASELINE_IDS)


# ---------------------------------------------------------------------------
# Ranh giới nhập
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module",
    [
        "apps.api.admin_ml_registry.registry",
        "apps.api.admin_ml_registry.errors",
        "apps.api.admin_ml_registry.jobs",
        "apps.api.admin_ml_registry.cli",
    ],
)
def test_imports_without_web_crypto_or_ml_runtime_packages(module: str) -> None:
    """Worker/CLI nhập được module khi `fastapi`, `jwt`, `argon2`, `torch`, `onnxruntime`… bị chặn (BE-00 §7, §12)."""
    blocked = "; ".join(f"sys.modules[{name!r}] = None" for name in BLOCKED)
    result = subprocess.run(  # noqa: S603 — trình thông dịch của chính tiến trình test, mã cố định
        [sys.executable, "-c", f"import sys; {blocked}; import {module}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
