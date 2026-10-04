"""Ma trận J/U đầu-cuối của `orchestrate_pipeline_start` (B5-06a việc D, [8]).

Mã của prompt này gọi thẳng lõi `run_pipeline_start`/`fail_pipeline_start_core` (khuôn
`apps/worker/pipeline_orchestrate/tests/test_start_core.py` của việc C và
`apps/worker/datasets/tests/test_tasks.py` của B6-02): lỗi đúng loại thoát khỏi lõi là việc
kiểm ở đây, còn `define_task` đổi ngoại lệ thành `RETRY_EXHAUSTED`/`TASK_TIMEOUT` là hợp đồng
B0-05 (test riêng ở đó). J01 và J08 là hai ca duy nhất chạy qua task thật (`orchestrate_pipeline_start`)
vì chúng kiểm đúng dây `define_task`/`queue_infer` → hàng `ml.infer`. J06, J09, J10 (dây
`after_commit`, giao lặp task, chạy lại giữ trang #31) là việc của C — không viết lại ở đây.

Dịch vụ thật (K23): Postgres, Redis, kho đĩa `local_storage`. Không `fakeredis`,
không `task_always_eager`.
"""

import asyncio
import logging
import time
from collections.abc import AsyncIterable, Iterator
from pathlib import Path
from typing import Final

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.drawings.runs import RunRow
from apps.api.drawings.tests._helpers import Scene, make_scene
from apps.worker.pipeline_orchestrate import tasks
from apps.worker.pipeline_orchestrate.settings import OrchestrateSettings
from apps.worker.pipeline_orchestrate.start import fail_pipeline_start_core, run_pipeline_start
from apps.worker.pipeline_orchestrate.tests._helpers import ML_QUEUE, floor_drawings, open_run, run_row
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE, IMAGE_TOO_LARGE, PDF_UNREADABLE
from packages.core.errors import AppError
from packages.core.settings import reset_settings_cache
from packages.db.models.drawings import DrawingRow, PipelineRunRow
from packages.db.settings import reset_database_settings_cache
from packages.messaging.payloads.drawings import PipelineStartPayload
from packages.messaging.redis import SyncRedis, broker_redis_sync
from packages.messaging.tasks import RETRY_EXHAUSTED, TASK_TIMEOUT, PermanentError
from packages.storage.local import LocalDiskStorage
from packages.storage.port import ObjectInfo
from packages.storage.settings import reset_storage_settings_cache
from packages.testing.factories.drawings import make_complete_upload
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.messaging import WorkerFactory, queued_payloads
from packages.vision.preprocess.tests.synthetic import encode, jpeg_with_orientation, make_pdf

type Maker = async_sessionmaker[AsyncSession]

START_QUEUE: Final = "pipeline.cpu"
"""Hàng worker `pipeline.cpu` nghe (`apps/worker/celery_main.py`), nơi `send_start_after_commit` xếp `start`."""

J01_WAIT_S: Final = 30.0
"""Trần **chờ** hàng ML của `__J01_smoke` — chống treo, không phải trần hiệu năng (xem docstring test)."""

J01_CEILING_S: Final = 5.0
"""Trần đặc tả của smoke: "≤ 5 s có ba `ml.infer.*`" (B5-06a [8] `__J01_smoke`); kiểm ở test `perf` riêng."""

_log = logging.getLogger(__name__)


async def _upload_and_run(
    maker: Maker, storage: LocalDiskStorage, *, data: bytes, file_name: str, clock: FakeClock
) -> tuple[Scene, RunRow]:
    """Sân khấu + lượt tải `complete` với `data` đã ghi vào kho + lượt chạy `pending` mở sẵn."""
    async with maker() as db:
        scene = await make_scene(db)
        upload = await make_complete_upload(
            db, storage, project=scene.project, floor=scene.floor, data=data, file_name=file_name
        )
        await db.commit()
    run = await open_run(maker, upload.id, clock)
    return scene, run


async def _run_row(maker: Maker, run_id: str) -> PipelineRunRow:
    """`run_row` trên session mới — trạng thái task đã commit, không cache."""
    async with maker() as db:
        return await run_row(db, run_id)


async def _only_drawing(maker: Maker, floor_pk: int) -> DrawingRow:
    """Bản vẽ duy nhất của tầng — task ghi đúng một dòng `drawings`."""
    async with maker() as db:
        rows = await floor_drawings(db, floor_pk)
    assert len(rows) == 1, rows
    return rows[0]


class _FlakyPut(LocalDiskStorage):
    """Kho đĩa thật ném `DEPENDENCY_UNAVAILABLE` ở `failures` lượt `put` đầu (J02, khuôn `FlakyReads`)."""

    def __init__(self, base: LocalDiskStorage, *, failures: int) -> None:
        """Mượn nguyên cấu hình của `base` (không dựng kho thứ hai), `failures < 0` nghĩa là hỏng mãi."""
        self.__dict__.update(base.__dict__)
        self.failures = failures
        self.attempts = 0

    async def put(
        self, key: str, data: bytes | AsyncIterable[bytes], *, content_type: str, max_bytes: int
    ) -> ObjectInfo:
        """Lượt `put` thứ `n`: ném `DEPENDENCY_UNAVAILABLE` khi `n ≤ failures`, không thì ghi thật."""
        self.attempts += 1
        if self.failures < 0 or self.attempts <= self.failures:
            raise DEPENDENCY_UNAVAILABLE.error(retry_after=5)
        return await super().put(key, data, content_type=content_type, max_bytes=max_bytes)


@pytest.fixture
def clean_ml_queue(messaging_env: None) -> SyncRedis:
    """Hàng `ml.infer` và `pipeline.cpu` dùng chung cả phiên; xoá trước khi đếm (BE-00 §12).

    `pipeline.cpu` tích thông điệp `start` của mọi `start_run` trước đó trong tiến trình (broker một
    bản mỗi tiến trình xdist, không xoá chéo) — xoá để J01 đếm đúng một thông điệp của chính nó.
    """
    client = broker_redis_sync()
    client.delete(ML_QUEUE, START_QUEUE)
    return client


@pytest.fixture
def process_env(db_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Môi trường của một tiến trình worker thật: DB test riêng, kho local trong `tmp_path`.

    Khuôn `apps/api/admin_ml_registry/tests/test_jobs.py:310-325`. Task chạy trên vòng sự kiện
    riêng của worker (`celery_worker_factory`, pool `solo`) nên phải tự dựng `worker_sessionmaker()`
    từ biến môi trường thay vì mượn engine của fixture `db_sessionmaker` (engine đó gắn với vòng
    sự kiện của pytest-asyncio — dùng chéo vòng ném "attached to a different loop").
    """
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path / "objects"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://appback.test")
    monkeypatch.setenv("SECRET_KEY", "fixture-secret-for-pipeline-orchestrate-cases-01")
    caches = (reset_settings_cache, reset_database_settings_cache, reset_storage_settings_cache)
    for reset in caches:
        reset()
    yield
    for reset in caches:
        reset()


def _run_smoke(
    maker: Maker,
    storage: LocalDiskStorage,
    clock: FakeClock,
    broker: SyncRedis,
    worker_factory: WorkerFactory,
) -> float:
    """Đường smoke dùng chung của `__J01_smoke` và test trần thời gian; trả số giây tới khi đủ ba `ml.infer.*`.

    Đồng hồ bắt đầu ngay trước khi dựng worker (thông điệp `start` đã nằm trên `pipeline.cpu`).
    """
    with tasks._STORAGE.override(lambda: storage):
        data = jpeg_with_orientation(640, 480, orientation=1)
        _scene, run = asyncio.run(_upload_and_run(maker, storage, data=data, file_name="plan.jpg", clock=clock))
        payload = PipelineStartPayload(run_id=run.id, upload_id=run.upload_id)
        assert queued_payloads(broker, START_QUEUE) == [payload.model_dump(mode="json")]

        start = time.monotonic()
        with worker_factory([START_QUEUE]):
            deadline = start + J01_WAIT_S
            while time.monotonic() < deadline and broker.llen(ML_QUEUE) < 3:
                time.sleep(0.05)
            elapsed = time.monotonic() - start
        assert len(queued_payloads(broker, ML_QUEUE)) == 3
        return elapsed


@pytest.mark.usefixtures("process_env")
def test_orchestrate_pipeline_start__J01_smoke(
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    clean_ml_queue: SyncRedis,
    celery_worker_factory: WorkerFactory,
) -> None:
    """Đường gửi thật → task thật (BE-00 §7 "Test task"): đủ ba `ml.infer.*` (NO-218).

    Không tự `apply_async`: thông điệp duy nhất là của `start_run` → `send_start_after_commit` →
    `send_task(START_TASK)` **theo tên** lên `pipeline.cpu`, khẳng định ngay trước khi dựng worker
    (callback sau commit lỗi chỉ được ghi log, không ném). Worker thật nhận đúng tên ấy — tên khai
    ở `tasks.py` lệch `START_TASK` thì không có `ml.infer.*` nào.

    `DB_AFTER_COMMIT_INLINE=1` (đặt bởi `create_celery` cho app thử) chạy callback sau commit
    tại chỗ trong luồng worker, nên không cần chờ riêng. Task tự dựng `worker_sessionmaker()`
    (đọc `DATABASE_URL` của `process_env`, khoá theo vòng sự kiện của chính nó — `packages.db.
    engine.worker_sessionmaker`); chỉ kho vẫn trỏ qua `_STORAGE.override` để dùng chung
    `local_storage` với dữ liệu đã mồi.

    Không mang marker `perf` và **không** khẳng định thời gian: `J01_WAIT_S` chỉ là trần chờ
    chống treo. Case `J01` không được là test `perf` (cổng bước 5b cấm test `perf` mang tên
    case); trần 5 s của [8] kiểm ở `test_orchestrate_start_smoke_stays_under_ceiling`.
    """
    elapsed = _run_smoke(db_sessionmaker, local_storage, fake_clock, clean_ml_queue, celery_worker_factory)
    _log.info("j01_elapsed_s=%.3f", elapsed)


@pytest.mark.perf
@pytest.mark.usefixtures("process_env")
def test_orchestrate_start_smoke_stays_under_ceiling(
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    clean_ml_queue: SyncRedis,
    celery_worker_factory: WorkerFactory,
) -> None:
    """Trần thời gian của smoke: worker thật đưa đủ ba `ml.infer.*` trong ≤ 5 s (NO-295 P3-04).

    Nguồn trần: B5-06a [8] `__J01_smoke` "≤ 5 s có ba `ml.infer.*`" — trần đặc tả, không tự đặt.
    Tên không mang mã case nên được gắn `perf` (cổng bước 5b); cùng đường với `__J01_smoke`.
    """
    elapsed = _run_smoke(db_sessionmaker, local_storage, fake_clock, clean_ml_queue, celery_worker_factory)
    _log.info("start_smoke_elapsed_s=%.3f", elapsed)
    assert elapsed <= J01_CEILING_S, f"smoke {elapsed:.3f} s > trần {J01_CEILING_S} s"


@pytest.mark.asyncio(loop_scope="function")
async def test_orchestrate_pipeline_start__J02(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Kho ném `DEPENDENCY_UNAVAILABLE` hai lần ở `put` → lượt đi tiếp; luôn ném → `RETRY_EXHAUSTED`.

    Kho hỏng chỉ bọc **sau** khi lượt tải đã ghi xong (khuôn `AtPutStorage` của B6-02): hỏng lúc
    mồi dữ liệu test không phải ca cần kiểm. Mỗi lỗi tạm thoát nguyên trạng khỏi lõi (giống
    `define_task` sẽ thấy khi thử lại thật) — lõi kiểm ở đây không tự lặp lại việc thử lại, ba
    lượt gọi trực tiếp mô phỏng ba lượt giao của cùng task (`attempts` cộng dồn trên cùng kho).
    """
    data = jpeg_with_orientation(640, 480, orientation=1)
    _scene, run = await _upload_and_run(db_sessionmaker, local_storage, data=data, file_name="a.jpg", clock=fake_clock)
    payload = PipelineStartPayload(run_id=run.id, upload_id=run.upload_id)
    flaky_ok = _FlakyPut(local_storage, failures=2)
    for _ in range(2):
        with pytest.raises(AppError) as caught:
            await run_pipeline_start(payload, sessionmaker=db_sessionmaker, storage=flaky_ok, clock=fake_clock)
        assert caught.value.code is DEPENDENCY_UNAVAILABLE
    await run_pipeline_start(payload, sessionmaker=db_sessionmaker, storage=flaky_ok, clock=fake_clock)
    assert flaky_ok.attempts == 3
    row = await _run_row(db_sessionmaker, run.id)
    assert row.status in ("running", "completed")

    _scene2, run2 = await _upload_and_run(
        db_sessionmaker, local_storage, data=data, file_name="b.jpg", clock=fake_clock
    )
    payload2 = PipelineStartPayload(run_id=run2.id, upload_id=run2.upload_id)
    flaky_dead = _FlakyPut(local_storage, failures=-1)
    with pytest.raises(AppError) as caught:
        await run_pipeline_start(payload2, sessionmaker=db_sessionmaker, storage=flaky_dead, clock=fake_clock)
    assert caught.value.code is DEPENDENCY_UNAVAILABLE

    await fail_pipeline_start_core(payload2, RETRY_EXHAUSTED, sessionmaker=db_sessionmaker, clock=fake_clock)
    row2 = await _run_row(db_sessionmaker, run2.id)
    assert (row2.status, row2.error_code, row2.current_step) == ("failed", RETRY_EXHAUSTED, "preprocess")
    assert row2.ended_at is None


@pytest.mark.asyncio(loop_scope="function")
async def test_orchestrate_pipeline_start__J03(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """`PIPELINE_MAX_PIXELS=1_000_000` (tham số `settings=`) → ảnh PNG 2000x2000 (4Mpx) vượt trần → `IMAGE_TOO_LARGE`.

    PNG, không phải JPEG: JPEG hạ cỡ bằng `draft()` trước khi so trần (tối ưu giải mã của
    Pillow), nên một JPEG 2000x2000 tự co xuống dưới trần trước khi kiểm được — không phải ca
    cần thử ở đây.
    """
    small_settings = OrchestrateSettings(pipeline_max_pixels=1_000_000)
    data = encode(Image.new("RGB", (2000, 2000), (10, 20, 30)), "PNG")
    _scene, run = await _upload_and_run(
        db_sessionmaker, local_storage, data=data, file_name="big.png", clock=fake_clock
    )
    payload = PipelineStartPayload(run_id=run.id, upload_id=run.upload_id)
    with pytest.raises(PermanentError, match=IMAGE_TOO_LARGE.code):
        await run_pipeline_start(
            payload, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock, settings=small_settings
        )
    await fail_pipeline_start_core(payload, IMAGE_TOO_LARGE.code, sessionmaker=db_sessionmaker, clock=fake_clock)
    row = await _run_row(db_sessionmaker, run.id)
    assert (row.status, row.error_code) == ("failed", IMAGE_TOO_LARGE.code)


@pytest.mark.asyncio(loop_scope="function")
async def test_orchestrate_pipeline_start__J05(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`SoftTimeLimitExceeded` ở tiền xử lý → thoát nguyên trạng → `on_failed` ghi `TASK_TIMEOUT`.

    Giả lập "lượt đã ở bước ML" bằng cách đẩy `current_step` qua `record_step` trước khi gọi
    `fail_pipeline_start_core`: bước đã qua `preprocess` thì hàm đó phải bỏ qua, không đè `failed`
    lên một lượt đang chạy tốt (đọc `start.py::fail_pipeline_start_core`).
    """
    from apps.api.drawings.runs import record_step
    from apps.worker.pipeline_orchestrate import start as start_module

    data = jpeg_with_orientation(640, 480, orientation=1)
    _scene, run = await _upload_and_run(db_sessionmaker, local_storage, data=data, file_name="t.jpg", clock=fake_clock)
    payload = PipelineStartPayload(run_id=run.id, upload_id=run.upload_id)

    async def _timeout(*_a: object, **_k: object) -> object:
        """Đứng vào chỗ `prepare_page` của `start.py` để giả lập hết giờ mềm giữa việc chậm."""
        raise SoftTimeLimitExceeded

    monkeypatch.setattr(start_module, "prepare_page", _timeout)
    with pytest.raises(SoftTimeLimitExceeded):
        await run_pipeline_start(payload, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock)
    await fail_pipeline_start_core(payload, TASK_TIMEOUT, sessionmaker=db_sessionmaker, clock=fake_clock)
    row = await _run_row(db_sessionmaker, run.id)
    assert (row.status, row.error_code) == ("failed", TASK_TIMEOUT)

    data2 = jpeg_with_orientation(640, 480, orientation=1)
    _scene2, run2 = await _upload_and_run(
        db_sessionmaker, local_storage, data=data2, file_name="t2.jpg", clock=fake_clock
    )
    payload2 = PipelineStartPayload(run_id=run2.id, upload_id=run2.upload_id)
    async with db_sessionmaker() as db:
        await record_step(db, run_id=run2.id, step="wallSegmentation", status="running", clock=fake_clock)
        await db.commit()
    await fail_pipeline_start_core(payload2, TASK_TIMEOUT, sessionmaker=db_sessionmaker, clock=fake_clock)
    row2 = await _run_row(db_sessionmaker, run2.id)
    assert row2.status != "failed"


def test_orchestrate_pipeline_start__J08(caplog: pytest.LogCaptureFixture) -> None:
    """Payload sai hợp đồng (`run_id` kiểu `int`) → `define_task` loại trước khi vào thân → `poison_message`."""
    with caplog.at_level(logging.WARNING):
        result = tasks.orchestrate_pipeline_start.apply(args=[{"run_id": 1}])
    assert result.successful()
    assert "poison_message" in caplog.text


@pytest.mark.asyncio(loop_scope="function")
async def test_orchestrate_pipeline_start__U01(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """JPEG EXIF `Orientation=6` (xoay 90°) → `width_px`/`height_px` của bản vẽ mới hoán vị so với tệp gốc."""
    data = jpeg_with_orientation(640, 480, orientation=6)
    scene, run = await _upload_and_run(db_sessionmaker, local_storage, data=data, file_name="rot.jpg", clock=fake_clock)
    payload = PipelineStartPayload(run_id=run.id, upload_id=run.upload_id)
    await run_pipeline_start(payload, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock)
    drawing = await _only_drawing(db_sessionmaker, scene.floor.pk)
    assert (drawing.width_px, drawing.height_px) == (480, 640)


@pytest.mark.asyncio(loop_scope="function")
async def test_orchestrate_pipeline_start__U02(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """PNG 16-bit (mode `I`) và JPEG CMYK: cả hai qua bước tiền xử lý mà không hỏng."""
    png16 = Image.new("I", (320, 240), 1000)
    png_data = encode(png16, "PNG")
    _scene, run = await _upload_and_run(
        db_sessionmaker, local_storage, data=png_data, file_name="a.png", clock=fake_clock
    )
    payload = PipelineStartPayload(run_id=run.id, upload_id=run.upload_id)
    await run_pipeline_start(payload, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock)
    row = await _run_row(db_sessionmaker, run.id)
    assert row.error_code is None

    cmyk = Image.new("CMYK", (320, 240), (0, 0, 0, 0))
    jpeg_data = encode(cmyk, "JPEG")
    _scene2, run2 = await _upload_and_run(
        db_sessionmaker, local_storage, data=jpeg_data, file_name="b.jpg", clock=fake_clock
    )
    payload2 = PipelineStartPayload(run_id=run2.id, upload_id=run2.upload_id)
    await run_pipeline_start(payload2, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock)
    row2 = await _run_row(db_sessionmaker, run2.id)
    assert row2.error_code is None


@pytest.mark.asyncio(loop_scope="function")
async def test_orchestrate_pipeline_start__U04(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """PDF có `user_password` (mật khẩu người dùng không rỗng) → không mở được → `PDF_UNREADABLE`."""
    data = make_pdf(1, encrypt="user_password")
    _scene, run = await _upload_and_run(
        db_sessionmaker, local_storage, data=data, file_name="locked.pdf", clock=fake_clock
    )
    payload = PipelineStartPayload(run_id=run.id, upload_id=run.upload_id)
    with pytest.raises(PermanentError, match=PDF_UNREADABLE.code):
        await run_pipeline_start(payload, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock)
    await fail_pipeline_start_core(payload, PDF_UNREADABLE.code, sessionmaker=db_sessionmaker, clock=fake_clock)
    row = await _run_row(db_sessionmaker, run.id)
    assert (row.status, row.error_code) == ("failed", PDF_UNREADABLE.code)


@pytest.mark.asyncio(loop_scope="function")
async def test_orchestrate_pipeline_start__U06(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Trang PDF khổ 5.000pt, trần `PIPELINE_MAX_PIXELS=4_000_000` → DPI hạ để `w x h <=` trần."""
    settings = OrchestrateSettings(pipeline_max_pixels=4_000_000)
    data = make_pdf(1, size=(5000.0, 5000.0))
    scene, run = await _upload_and_run(
        db_sessionmaker, local_storage, data=data, file_name="huge.pdf", clock=fake_clock
    )
    payload = PipelineStartPayload(run_id=run.id, upload_id=run.upload_id)
    await run_pipeline_start(
        payload, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock, settings=settings
    )
    drawing = await _only_drawing(db_sessionmaker, scene.floor.pk)
    assert drawing.width_px * drawing.height_px <= 4_000_000
