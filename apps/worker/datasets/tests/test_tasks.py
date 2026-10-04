"""Task `build_dataset_version`: J01-J09, nguồn tầng, M06 và bất biến bản đã chốt (B6-02 [8]).

Postgres, Redis, kho local đều **thật** (K23). Lỗi phụ thuộc được tiêm bằng một lớp bọc mỏng
**quanh kho thật** (`_FailingStorage`) chứ không phải kho giả: mọi lượt khác vẫn đi qua
`LocalDiskStorage`, chỉ một lượt `put` được thay bằng lỗi.

Phân chia cố ý: mọi thứ thuộc **mã của prompt này** (bước 1-9, lý do bỏ tầng, dọn tiền tố) test
trên lõi `run_build_dataset_version`; còn việc **`define_task` phân loại lỗi** thành
`TASK_TIMEOUT`/`RETRY_EXHAUSTED` là hợp đồng của B0-05 (có test riêng ở đó), nên ở đây chỉ kiểm
hai đầu nối: lỗi đúng loại thoát ra khỏi lõi, và `on_failed` dọn đúng chỗ. J08 chạy được nguyên
vẹn vì `define_task` từ chối payload **trước** khi gọi thân (không cần DB, không cần vòng sự kiện).
"""

import logging
from datetime import datetime, timedelta

import pytest
from celery import Celery
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.admin_ml_datasets.errors import (
    DATASET_EMPTY,
    DATASET_FAMILY_UNSUPPORTED,
    DATASET_TOO_LARGE,
)
from apps.api.admin_ml_datasets.settings import reset_ml_datasets_settings_cache
from apps.api.admin_ml_datasets.versions import fail_version, finish_version, start_version
from apps.worker.datasets import tasks
from apps.worker.datasets.tasks import (
    run_build_dataset_version,
    run_fail_dataset_version,
    version_prefix,
)
from apps.worker.datasets.tests._helpers import (
    DOOR_OFFSET_MM,
    DOOR_WIDTH_MM,
    HEIGHT,
    MM_PER_PX,
    WALL_START,
    WALL_THICKNESS,
    WIDTH,
    AtPutStorage,
    add_human_write,
    add_pending_run,
    ai_layer,
    approved_floor,
    make_scene,
    move_drawing_after_review,
    open_building_version,
    other_project,
    page_key_of,
    read_version,
    rooms_only_layer,
    set_failed,
    set_ready,
    steal_lock,
    with_furniture_layer,
)
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.core.errors import AppError
from packages.db.hooks import on_after_commit
from packages.db.models.admin_ml_datasets import DatasetVersionRow
from packages.db.models.floors import FloorRow
from packages.db.models.spatial import FloorDocumentRow
from packages.messaging import PermanentError, SafeLock, safe_redis, send_task
from packages.messaging.payloads.datasets import BUILD_VERSION_TASK, BuildDatasetVersionPayload
from packages.messaging.redis import AsyncRedis, SyncRedis, broker_redis_sync, safe_redis_sync
from packages.ml_contracts.artifacts import decode_mask
from packages.ml_contracts.datasets import parse_manifest, split_for
from packages.storage.keys import dataset_object
from packages.storage.local import LocalDiskStorage
from packages.storage.port import CHUNK_SIZE, ObjectStorage
from packages.testing.factories.admin_ml_datasets import make_dataset
from packages.testing.factories.drawings import PNG_SIGNATURE, png_bytes
from packages.testing.factories.floors import make_floor
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.messaging import queued_payloads

Maker = async_sessionmaker[AsyncSession]
DEFAULT_QUEUE = "default"
EMPTY_COUNTS = {"train": 0, "validation": 0, "test": 0}


async def _keys(storage: ObjectStorage, version_id: str) -> list[str]:
    """Khoá dưới tiền tố của một phiên bản, sắp tăng."""
    return sorted([info.key async for info in storage.list_prefix(version_prefix(version_id))])


async def _read(storage: ObjectStorage, key: str) -> bytes:
    """Toàn bộ byte của một object (chỉ dùng cho object nhỏ của test)."""
    return b"".join([chunk async for chunk in storage.open_read(key)])


async def _build_or_fail(maker: Maker, storage: ObjectStorage, clock: FakeClock) -> DatasetVersionRow:
    """Một lượt dựng trên dữ liệu đã có; `PermanentError` → chạy `on_failed` như worker thật."""
    version_id = await open_building_version(maker, clock)
    try:
        await run_build_dataset_version(maker, storage, clock, version_id=version_id)
    except PermanentError as exc:
        await run_fail_dataset_version(maker, storage, clock, version_id=version_id, code=exc.code)
    return await read_version(maker, version_id)


async def _assert_failed_clean(
    maker: Maker, storage: ObjectStorage, clock: FakeClock, *, version_id: str, code: str
) -> None:
    """Chạy `on_failed` như `define_task` sẽ làm, rồi kiểm bản `failed` và tiền tố rỗng."""
    await run_fail_dataset_version(maker, storage, clock, version_id=version_id, code=code)
    row = await read_version(maker, version_id)
    assert (row.status, row.failure_code) == ("failed", code)
    assert await _keys(storage, version_id) == []


@pytest.fixture
def broker(messaging_env: None) -> SyncRedis:
    """Broker thật với hàng `default` rỗng đầu test (J09 đếm thông điệp trên đó)."""
    client = broker_redis_sync()
    client.delete(DEFAULT_QUEUE)
    return client


# ---------------------------------------------------------------------------
# J01, M06 — đường đúng
# ---------------------------------------------------------------------------


async def test_build_dataset_version__J01(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, safe_client: AsyncRedis
) -> None:
    """Ba tầng A/B/C → một mẫu: A đạt, B nhãn AI chưa duyệt, C không bản vẽ.

    Kiểm cả manifest (`sha256`, `bytes` khớp từng object thật) và pixel `walls.png`: tâm tường là
    `True`, điểm cách tường hai lần bề dày là `False` (quy ước mm → px của `render.py`).
    """
    async with db_sessionmaker() as db:
        scene = await make_scene(db)
        floor_a = await approved_floor(db, local_storage, scene, fake_clock)
        await approved_floor(db, local_storage, scene, fake_clock, layer_of=ai_layer, page=png_bytes(WIDTH + 1, HEIGHT))
        await approved_floor(db, local_storage, scene, fake_clock, drawing=False)
        await db.commit()
    version_id = await open_building_version(db_sessionmaker, fake_clock)

    await run_build_dataset_version(db_sessionmaker, local_storage, fake_clock, version_id=version_id)

    row = await read_version(db_sessionmaker, version_id)
    split = split_for(scene.project.id)
    assert (row.status, row.failure_code) == ("ready", None)
    assert row.split_counts == EMPTY_COUNTS | {split: 1}
    assert row.manifest_sha256 is not None
    assert row.build_started_at is not None

    sample_id = f"{scene.project.id}_{floor_a.level_id}"
    prefix = f"{version_prefix(version_id)}{split}/{sample_id}/"
    assert await _keys(local_storage, version_id) == sorted(
        [
            f"{version_prefix(version_id)}manifest.jsonl",
            f"{prefix}image.png",
            f"{prefix}meta.json",
            f"{prefix}walls.png",
        ]
    )

    entries = parse_manifest(await _read(local_storage, f"{version_prefix(version_id)}manifest.jsonl"))
    assert {entry.path for entry in entries} == {
        f"{split}/{sample_id}/image.png",
        f"{split}/{sample_id}/walls.png",
        f"{split}/{sample_id}/meta.json",
    }
    for entry in entries:
        info = await local_storage.stat(f"{version_prefix(version_id)}{entry.path}")
        assert info is not None
        assert (info.sha256, info.size) == (entry.sha256, entry.bytes)

    mask = decode_mask(await _read(local_storage, f"{prefix}walls.png"), width_px=WIDTH, height_px=HEIGHT)
    scale = float(MM_PER_PX)
    centre_y = int(WALL_START[1] / scale)
    on_wall_x = int((WALL_START[0] + DOOR_OFFSET_MM / 2) / scale)
    in_door_x = int((WALL_START[0] + DOOR_OFFSET_MM + DOOR_WIDTH_MM / 2) / scale)
    assert bool(mask[centre_y, on_wall_x]) is True
    assert bool(mask[centre_y, in_door_x]) is False, "khe cửa phải là nền"
    assert bool(mask[centre_y + int(2 * WALL_THICKNESS / scale), on_wall_x]) is False


async def test_build_dataset_version__M06(
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    safe_client: AsyncRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hai tầng **cùng dự án** rơi vào cùng một `split` (chia theo nhóm, không theo mẫu).

    `TOUCH_EVERY_SAMPLES=1` để nhịp `touch_version` đập sau **mỗi** mẫu và vẫn thấy bản còn
    `building`: đường nhịp-đập-thành-công không có ca nào khác đi qua.
    """
    monkeypatch.setattr(tasks, "TOUCH_EVERY_SAMPLES", 1)
    async with db_sessionmaker() as db:
        scene = await make_scene(db)
        await approved_floor(db, local_storage, scene, fake_clock)
        await approved_floor(db, local_storage, scene, fake_clock, page=png_bytes(WIDTH, HEIGHT + 4))
        await db.commit()
    version_id = await open_building_version(db_sessionmaker, fake_clock)

    await run_build_dataset_version(db_sessionmaker, local_storage, fake_clock, version_id=version_id)

    row = await read_version(db_sessionmaker, version_id)
    assert row.split_counts == EMPTY_COUNTS | {split_for(scene.project.id): 2}


async def test_build_dataset_version__objects_family(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, safe_client: AsyncRedis
) -> None:
    """Họ cửa-đồ ghi `objects.json` và **không** ghi `walls.png`."""
    async with db_sessionmaker() as db:
        scene = await make_scene(db)
        await approved_floor(db, local_storage, scene, fake_clock, layer_of=with_furniture_layer)
        await db.commit()
    version_id = await open_building_version(db_sessionmaker, fake_clock, family="openingAndFurnitureDetection")

    await run_build_dataset_version(db_sessionmaker, local_storage, fake_clock, version_id=version_id)

    keys = await _keys(local_storage, version_id)
    assert any(key.endswith("objects.json") for key in keys)
    assert not any(key.endswith("walls.png") for key in keys)


async def test_build_dataset_version__project_filter(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, safe_client: AsyncRedis
) -> None:
    """`project_ids` giới hạn tập tầng: tầng của dự án ngoài danh sách không thành mẫu."""
    async with db_sessionmaker() as db:
        inside = await make_scene(db)
        outside = await other_project(db, inside)
        await approved_floor(db, local_storage, inside, fake_clock)
        await approved_floor(db, local_storage, outside, fake_clock, page=png_bytes(WIDTH, HEIGHT + 8))
        await db.commit()
    version_id = await open_building_version(db_sessionmaker, fake_clock, project_ids=[inside.project.id])

    await run_build_dataset_version(db_sessionmaker, local_storage, fake_clock, version_id=version_id)

    row = await read_version(db_sessionmaker, version_id)
    assert sum((row.split_counts or {}).values()) == 1


async def test_build_dataset_version__stream_keeps_whole_page(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, safe_client: AsyncRedis
) -> None:
    """`image.png` bằng **đúng** byte trang gốc, kể cả trang **nhiều khúc**.

    Trang dài hơn một khúc `open_read` (1 MiB) là ca duy nhất chứng minh phần sau khúc đầu cũng
    đi vào `put`: khúc đầu bị tách ra để kiểm PNG nên rất dễ mất phần còn lại.
    """
    big_page = png_bytes(WIDTH, HEIGHT) + bytes(CHUNK_SIZE + 7)
    async with db_sessionmaker() as db:
        scene = await make_scene(db)
        floor = await approved_floor(db, local_storage, scene, fake_clock, page=big_page)
        page_key = await page_key_of(db, floor)
        await db.commit()
    version_id = await open_building_version(db_sessionmaker, fake_clock)

    await run_build_dataset_version(db_sessionmaker, local_storage, fake_clock, version_id=version_id)

    split = split_for(scene.project.id)
    image_key = f"{version_prefix(version_id)}{split}/{scene.project.id}_{floor.level_id}/image.png"
    assert await _read(local_storage, image_key) == await _read(local_storage, page_key)


# ---------------------------------------------------------------------------
# J02 — lỗi tạm rồi thử lại
# ---------------------------------------------------------------------------


async def test_build_dataset_version__J02(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, safe_client: AsyncRedis
) -> None:
    """Kho ném `DEPENDENCY_UNAVAILABLE` một lần → lỗi nổi lên (define_task thử lại) → lượt hai `ready`.

    Lượt hai xoá sạch tiền tố của lượt chết trước khi ghi lại: manifest của bản `ready` kể **đúng**
    ba tệp, không có tệp sót của lượt hỏng.
    """
    async with db_sessionmaker() as db:
        scene = await make_scene(db)
        await approved_floor(db, local_storage, scene, fake_clock)
        await db.commit()
    version_id = await open_building_version(db_sessionmaker, fake_clock)
    flaky = AtPutStorage(local_storage, at_put=2, error=DEPENDENCY_UNAVAILABLE.error(retry_after=5))

    with pytest.raises(AppError) as caught:
        await run_build_dataset_version(db_sessionmaker, flaky, fake_clock, version_id=version_id)
    assert caught.value.code is DEPENDENCY_UNAVAILABLE
    assert (await read_version(db_sessionmaker, version_id)).status == "building"
    assert await _keys(local_storage, version_id) != []

    await run_build_dataset_version(db_sessionmaker, local_storage, fake_clock, version_id=version_id)

    assert (await read_version(db_sessionmaker, version_id)).status == "ready"
    entries = parse_manifest(await _read(local_storage, f"{version_prefix(version_id)}manifest.jsonl"))
    assert len(entries) == 3
    assert len(await _keys(local_storage, version_id)) == 4


# ---------------------------------------------------------------------------
# J03 — bốn ca hỏng vĩnh viễn
# ---------------------------------------------------------------------------


async def _case_family_unsupported(maker: Maker, storage: ObjectStorage, clock: FakeClock) -> None:
    """Họ `dimensionReading` -> `DATASET_FAMILY_UNSUPPORTED`, tiền tố rỗng."""
    version_id = await open_building_version(maker, clock, family="dimensionReading")

    with pytest.raises(PermanentError, match=DATASET_FAMILY_UNSUPPORTED):
        await run_build_dataset_version(maker, storage, clock, version_id=version_id)

    await _assert_failed_clean(maker, storage, clock, version_id=version_id, code=DATASET_FAMILY_UNSUPPORTED)


async def _case_no_sample(maker: Maker, storage: ObjectStorage, clock: FakeClock) -> None:
    """Không tầng nào đạt (tầng duy nhất thiếu tỉ lệ, K19) -> `DATASET_EMPTY`, tiền tố rỗng.

    `SampleWriter.finish()` **không** ném ca này: quyết định thuộc task, vì chỉ task biết đã
    duyệt hết tầng nào.
    """
    version_id = await open_building_version(maker, clock)

    with pytest.raises(PermanentError, match=DATASET_EMPTY):
        await run_build_dataset_version(maker, storage, clock, version_id=version_id)

    await _assert_failed_clean(maker, storage, clock, version_id=version_id, code=DATASET_EMPTY)


async def _case_too_many_samples(maker: Maker, storage: ObjectStorage, clock: FakeClock) -> None:
    """`DATASET_MAX_SAMPLES=1` với hai tầng đạt -> `DATASET_TOO_LARGE`, tiền tố rỗng."""
    version_id = await open_building_version(maker, clock)

    with pytest.raises(PermanentError, match=DATASET_TOO_LARGE):
        await run_build_dataset_version(maker, storage, clock, version_id=version_id)

    await _assert_failed_clean(maker, storage, clock, version_id=version_id, code=DATASET_TOO_LARGE)


async def _case_too_many_bytes(maker: Maker, storage: ObjectStorage, clock: FakeClock) -> None:
    """Trần byte nhỏ hơn một mẫu -> `DATASET_TOO_LARGE` từ writer, tiền tố rỗng."""
    version_id = await open_building_version(maker, clock)

    with pytest.raises(PermanentError, match=DATASET_TOO_LARGE):
        await run_build_dataset_version(maker, storage, clock, version_id=version_id, sample_max_bytes=16)

    await _assert_failed_clean(maker, storage, clock, version_id=version_id, code=DATASET_TOO_LARGE)


async def test_build_dataset_version__J03(
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    safe_client: AsyncRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bốn ca hỏng vĩnh viễn, ca nào cũng để lại tiền tố **rỗng** ([8] `__J03`).

    Bốn ca nằm trong **một** hàm test vì `tools/case_gate.py` neo tên case của task vào cuối
    (`test_<fn>__J` + đúng hai chữ số, hết chuỗi): `…__J03_empty` sẽ không được tính là J03.
    Ca "0 mẫu" dựng bằng một tầng **thiếu tỉ lệ** (K19), không phải DB trống: tầng bị bỏ vì lý do
    nghiệp vụ mới là ca thật, DB trống chỉ chứng minh câu `SELECT` rỗng.
    """
    await _case_family_unsupported(db_sessionmaker, local_storage, fake_clock)

    async with db_sessionmaker() as db:
        scene = await make_scene(db)
        await approved_floor(db, local_storage, scene, fake_clock, scale=None)
        await db.commit()
    await _case_no_sample(db_sessionmaker, local_storage, fake_clock)

    async with db_sessionmaker() as db:
        await approved_floor(db, local_storage, scene, fake_clock)
        await approved_floor(db, local_storage, scene, fake_clock, page=png_bytes(WIDTH, HEIGHT + 4))
        await db.commit()

    monkeypatch.setenv("DATASET_MAX_SAMPLES", "1")
    reset_ml_datasets_settings_cache()
    try:
        await _case_too_many_samples(db_sessionmaker, local_storage, fake_clock)
    finally:
        monkeypatch.delenv("DATASET_MAX_SAMPLES")
        reset_ml_datasets_settings_cache()

    await _case_too_many_bytes(db_sessionmaker, local_storage, fake_clock)


# ---------------------------------------------------------------------------
# J05 — hết giờ mềm
# ---------------------------------------------------------------------------


async def test_build_dataset_version__J05(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, safe_client: AsyncRedis
) -> None:
    """`SoftTimeLimitExceeded` giữa lượt **không** bị nuốt; `on_failed` → `TASK_TIMEOUT`, tiền tố rỗng.

    `define_task` đổi ngoại lệ này thành `TASK_TIMEOUT` (hợp đồng B0-05), nên việc của lõi ở đây
    là để nó thoát ra nguyên vẹn thay vì biến thành một lượt "dừng im lặng".
    """
    async with db_sessionmaker() as db:
        scene = await make_scene(db)
        await approved_floor(db, local_storage, scene, fake_clock)
        await db.commit()
    version_id = await open_building_version(db_sessionmaker, fake_clock)
    timing_out = AtPutStorage(local_storage, at_put=1, error=SoftTimeLimitExceeded())

    with pytest.raises(SoftTimeLimitExceeded):
        await run_build_dataset_version(db_sessionmaker, timing_out, fake_clock, version_id=version_id)

    await _assert_failed_clean(db_sessionmaker, local_storage, fake_clock, version_id=version_id, code="TASK_TIMEOUT")


# ---------------------------------------------------------------------------
# J06 — giao lặp, khoá bị giữ, lượt muộn
# ---------------------------------------------------------------------------


async def test_build_dataset_version__J06(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, safe_client: AsyncRedis
) -> None:
    """Gửi lặp → cùng `manifestSha256`, không phiên bản thứ hai (K18)."""
    async with db_sessionmaker() as db:
        scene = await make_scene(db)
        await approved_floor(db, local_storage, scene, fake_clock)
        await db.commit()
    version_id = await open_building_version(db_sessionmaker, fake_clock)

    await run_build_dataset_version(db_sessionmaker, local_storage, fake_clock, version_id=version_id)
    first = await read_version(db_sessionmaker, version_id)
    keys_before = await _keys(local_storage, version_id)

    await run_build_dataset_version(db_sessionmaker, local_storage, fake_clock, version_id=version_id)

    again = await read_version(db_sessionmaker, version_id)
    assert (again.status, again.manifest_sha256) == ("ready", first.manifest_sha256)
    assert await _keys(local_storage, version_id) == keys_before
    async with db_sessionmaker() as db:
        assert len((await db.execute(select(DatasetVersionRow.id))).scalars().all()) == 1


async def test_build_dataset_version__J06_lock_held(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, safe_client: AsyncRedis
) -> None:
    """Khoá đang bị người khác giữ → lượt này không ghi object nào, bản vẫn `building`."""
    async with db_sessionmaker() as db:
        scene = await make_scene(db)
        await approved_floor(db, local_storage, scene, fake_clock)
        await db.commit()
    version_id = await open_building_version(db_sessionmaker, fake_clock)
    rival = SafeLock(safe_redis(), f"datasets:build:{version_id}", ttl_ms=60_000)
    token = await rival.acquire()
    assert token is not None

    try:
        await run_build_dataset_version(db_sessionmaker, local_storage, fake_clock, version_id=version_id)
    finally:
        await rival.release(token)

    assert await _keys(local_storage, version_id) == []
    row = await read_version(db_sessionmaker, version_id)
    assert (row.status, row.build_started_at) == ("building", None)


async def test_build_dataset_version__J06_late_run(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, safe_client: AsyncRedis
) -> None:
    """Bản đã `ready` cộng một lượt muộn báo hỏng → object và manifest còn nguyên (bản `ready` bất biến)."""
    async with db_sessionmaker() as db:
        scene = await make_scene(db)
        await approved_floor(db, local_storage, scene, fake_clock)
        await db.commit()
    version_id = await open_building_version(db_sessionmaker, fake_clock)
    await run_build_dataset_version(db_sessionmaker, local_storage, fake_clock, version_id=version_id)
    before = await _keys(local_storage, version_id)
    manifest = (await read_version(db_sessionmaker, version_id)).manifest_sha256

    await run_fail_dataset_version(
        db_sessionmaker, local_storage, fake_clock, version_id=version_id, code="TASK_TIMEOUT"
    )

    row = await read_version(db_sessionmaker, version_id)
    assert (row.status, row.manifest_sha256, row.failure_code) == ("ready", manifest, None)
    assert await _keys(local_storage, version_id) == before


async def test_build_dataset_version__not_building(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, safe_client: AsyncRedis
) -> None:
    """Bản đã `failed` trước khi task chạy → lượt này không làm gì, không ghi object."""
    version_id = await open_building_version(db_sessionmaker, fake_clock)
    async with db_sessionmaker() as db:
        await fail_version(db, version_id=version_id, failure_code=DATASET_EMPTY, clock=fake_clock)
        await db.commit()

    await run_build_dataset_version(db_sessionmaker, local_storage, fake_clock, version_id=version_id)

    assert await _keys(local_storage, version_id) == []
    assert (await read_version(db_sessionmaker, version_id)).build_started_at is None


# ---------------------------------------------------------------------------
# J08, J09
# ---------------------------------------------------------------------------


def test_build_dataset_version__J08(celery_test_app: Celery, caplog: pytest.LogCaptureFixture) -> None:
    """Payload sai hợp đồng → `poison_message`; thân task không chạy nên không bản nào đổi.

    Chạy đồng bộ qua `apply()`: `define_task` từ chối payload **trước** khi gọi thân, nên lượt
    này không mở session hay chạm kho — đúng thứ cần kiểm.
    """
    with caplog.at_level(logging.WARNING):
        result = celery_test_app.tasks[BUILD_VERSION_TASK].apply(
            args=({"schema_version": 1, "dataset_version_id": "sai"},)
        )

    assert result.successful()
    assert "poison_message" in caplog.text


class _RouteFailedError(RuntimeError):
    """Lỗi giả của route N31 sau khi đã chèn dòng phiên bản (J09)."""


async def _insert_then_fail(maker: Maker, clock: FakeClock, *, dataset_id: str) -> None:
    """Chèn phiên bản, đăng ký gửi task sau commit, rồi ném: giao dịch phải bỏ **cả hai**."""
    async with maker() as db:
        row = await start_version(
            db,
            dataset_id=dataset_id,
            source="approvedFloors",
            project_ids=None,
            created_by="usr_seed",
            clock=clock,
        )
        assert row is not None
        payload = BuildDatasetVersionPayload(dataset_version_id=row.id)
        on_after_commit(db, lambda: send_task(BUILD_VERSION_TASK, payload))
        raise _RouteFailedError


async def test_build_dataset_version__J09(db_sessionmaker: Maker, fake_clock: FakeClock, broker: SyncRedis) -> None:
    """Lỗi giả sau khi chèn phiên bản -> rollback, hàng `default` **rỗng** (K17).

    Route N31 nằm ở nhánh khác (việc B) nên J09 viết trên hàm mức thấp nhất có ở đây:
    `start_version` + `on_after_commit(send_task)` trong một giao dịch bị rollback.
    """
    async with db_sessionmaker() as db:
        dataset_id = (await make_dataset(db, family="wallSegmentation", created_by="usr_seed")).id
        await db.commit()

    with pytest.raises(_RouteFailedError):
        await _insert_then_fail(db_sessionmaker, fake_clock, dataset_id=dataset_id)

    async with db_sessionmaker() as db:
        assert (await db.execute(select(DatasetVersionRow.id))).scalars().all() == []
    assert queued_payloads(broker, DEFAULT_QUEUE) == []


# ---------------------------------------------------------------------------
# Nguồn tầng — bốn ca của [8]
# ---------------------------------------------------------------------------


async def test_build_dataset_version__sources_drawing_after_review(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, safe_client: AsyncRedis
) -> None:
    """Bản vẽ mới hơn lượt duyệt → bỏ; thêm một lượt ghi của người → nhận lại."""
    async with db_sessionmaker() as db:
        scene = await make_scene(db)
        floor = await approved_floor(db, local_storage, scene, fake_clock)
        await move_drawing_after_review(db, floor, fake_clock)
        await db.commit()

    assert (await _build_or_fail(db_sessionmaker, local_storage, fake_clock)).failure_code == DATASET_EMPTY

    async with db_sessionmaker() as db:
        fake_clock.advance(timedelta(hours=2))
        await add_human_write(db, floor, scene, fake_clock)
        await db.commit()

    assert (await _build_or_fail(db_sessionmaker, local_storage, fake_clock)).status == "ready"


async def test_build_dataset_version__sources_pipeline_pending(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, safe_client: AsyncRedis
) -> None:
    """Lượt pipeline của lượt tải còn `running` → bỏ tầng (`pipeline_pending`)."""
    async with db_sessionmaker() as db:
        scene = await make_scene(db)
        floor = await approved_floor(db, local_storage, scene, fake_clock)
        await add_pending_run(db, floor, fake_clock)
        await db.commit()

    assert (await _build_or_fail(db_sessionmaker, local_storage, fake_clock)).failure_code == DATASET_EMPTY


async def test_build_dataset_version__sources_document_corrupt(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, safe_client: AsyncRedis
) -> None:
    """`schema_version` lạ → `DocumentCorruptError` → bỏ tầng, không làm hỏng cả lượt."""
    async with db_sessionmaker() as db:
        scene = await make_scene(db)
        floor = await approved_floor(db, local_storage, scene, fake_clock)
        document = await db.get(FloorDocumentRow, floor.pk)
        assert document is not None
        document.schema_version = 99
        await db.commit()

    assert (await _build_or_fail(db_sessionmaker, local_storage, fake_clock)).failure_code == DATASET_EMPTY


async def test_build_dataset_version__sources_duplicate_image(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, safe_client: AsyncRedis
) -> None:
    """Hai tầng của **hai** dự án cùng ảnh trang → một mẫu; giữ tầng `floors.pk` nhỏ nhất."""
    async with db_sessionmaker() as db:
        first = await make_scene(db)
        second = await other_project(db, first)
        kept = await approved_floor(db, local_storage, first, fake_clock)
        await approved_floor(db, local_storage, second, fake_clock)
        await db.commit()
    version_id = await open_building_version(db_sessionmaker, fake_clock)

    await run_build_dataset_version(db_sessionmaker, local_storage, fake_clock, version_id=version_id)

    row = await read_version(db_sessionmaker, version_id)
    assert sum((row.split_counts or {}).values()) == 1
    sample_id = f"{first.project.id}_{kept.level_id}"
    assert any(sample_id in key for key in await _keys(local_storage, version_id))


async def test_build_dataset_version__sources_no_labels(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, safe_client: AsyncRedis
) -> None:
    """Tầng chỉ có phòng → không có nhãn của họ tường (`no_labels`)."""
    async with db_sessionmaker() as db:
        scene = await make_scene(db)
        await approved_floor(db, local_storage, scene, fake_clock, layer_of=rooms_only_layer)
        await db.commit()

    assert (await _build_or_fail(db_sessionmaker, local_storage, fake_clock)).failure_code == DATASET_EMPTY


async def test_build_dataset_version__sources_image_not_png(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, safe_client: AsyncRedis
) -> None:
    """Object trang bị thay bằng byte không phải PNG → bỏ tầng (`image_mismatch`)."""
    async with db_sessionmaker() as db:
        scene = await make_scene(db)
        floor = await approved_floor(db, local_storage, scene, fake_clock)
        page_key = await page_key_of(db, floor)
        await db.commit()
    await local_storage.put(page_key, b"khong-phai-png", content_type="image/png", max_bytes=100)

    assert (await _build_or_fail(db_sessionmaker, local_storage, fake_clock)).failure_code == DATASET_EMPTY


# ---------------------------------------------------------------------------
# Bất biến
# ---------------------------------------------------------------------------


async def test_build_dataset_version__finish_on_failed_is_noop(db_sessionmaker: Maker, fake_clock: FakeClock) -> None:
    """`finish_version` trên một bản đã `failed` → `False`, không sửa dòng (bản đã chốt bất biến)."""
    version_id = await open_building_version(db_sessionmaker, fake_clock)
    async with db_sessionmaker() as db:
        assert await fail_version(db, version_id=version_id, failure_code=DATASET_EMPTY, clock=fake_clock) is True
        await db.commit()

    async with db_sessionmaker() as db:
        done = await finish_version(
            db, version_id=version_id, manifest_sha256="a" * 64, split_counts=EMPTY_COUNTS, clock=fake_clock
        )
        await db.commit()

    row = await read_version(db_sessionmaker, version_id)
    assert done is False
    assert (row.status, row.manifest_sha256, row.failure_code) == ("failed", None, DATASET_EMPTY)


async def test_build_dataset_version__second_version_keeps_first(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, safe_client: AsyncRedis
) -> None:
    """Lượt dựng thứ hai của cùng dataset → `sequence 2`; bản 1 giữ `manifestSha256` và object."""
    async with db_sessionmaker() as db:
        scene = await make_scene(db)
        await approved_floor(db, local_storage, scene, fake_clock)
        await db.commit()
    first_id = await open_building_version(db_sessionmaker, fake_clock)
    await run_build_dataset_version(db_sessionmaker, local_storage, fake_clock, version_id=first_id)
    first = await read_version(db_sessionmaker, first_id)
    first_keys = await _keys(local_storage, first_id)

    second_id = await open_building_version(db_sessionmaker, fake_clock, dataset_id=first.dataset_id)
    await run_build_dataset_version(db_sessionmaker, local_storage, fake_clock, version_id=second_id)

    assert (await read_version(db_sessionmaker, second_id)).sequence == 2
    kept = await read_version(db_sessionmaker, first_id)
    assert (kept.status, kept.manifest_sha256) == ("ready", first.manifest_sha256)
    assert await _keys(local_storage, first_id) == first_keys


async def test_build_dataset_version__second_build_blocked(db_sessionmaker: Maker, fake_clock: FakeClock) -> None:
    """Dataset đã có bản `building` → `start_version` trả `None` (K18, một bản đang dựng)."""
    version_id = await open_building_version(db_sessionmaker, fake_clock)
    dataset_id = (await read_version(db_sessionmaker, version_id)).dataset_id

    async with db_sessionmaker() as db:
        again = await start_version(
            db,
            dataset_id=dataset_id,
            source="approvedFloors",
            project_ids=None,
            created_by="usr_seed",
            clock=fake_clock,
        )
        await db.rollback()

    assert again is None


async def test_build_dataset_version__unknown_floors_ignored(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, safe_client: AsyncRedis
) -> None:
    """Dự án đã xoá mềm bị loại ngay ở bước liệt kê tầng (bước 4)."""
    async with db_sessionmaker() as db:
        scene = await make_scene(db)
        await approved_floor(db, local_storage, scene, fake_clock)
        scene.project.deleted_at = fake_clock.now()
        await db.commit()

    assert (await _build_or_fail(db_sessionmaker, local_storage, fake_clock)).failure_code == DATASET_EMPTY


# ---------------------------------------------------------------------------
# Mất khoá, nhịp sống, chốt trạng thái muộn
# ---------------------------------------------------------------------------


async def test_build_dataset_version__stops_when_the_lock_is_stolen(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, safe_client: AsyncRedis
) -> None:
    """Khoá bị xoá giữa lượt → dừng trước lượt `put` kế tiếp: không manifest, không `finish_version`."""
    async with db_sessionmaker() as db:
        scene = await make_scene(db)
        await approved_floor(db, local_storage, scene, fake_clock)
        await db.commit()
    version_id = await open_building_version(db_sessionmaker, fake_clock)
    storage = AtPutStorage(local_storage, at_put=1, hook=lambda: steal_lock(version_id))

    await run_build_dataset_version(db_sessionmaker, storage, fake_clock, version_id=version_id)

    row = await read_version(db_sessionmaker, version_id)
    assert (row.status, row.manifest_sha256) == ("building", None)
    keys = await _keys(local_storage, version_id)
    assert keys != []
    assert not any(key.endswith("manifest.jsonl") for key in keys)


async def test_build_dataset_version__beats_and_stops_when_no_longer_building(
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    safe_client: AsyncRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nhịp `touch_version` mỗi mẫu; bản bị chốt `failed` giữa lượt → dừng, không `finish_version`.

    `TOUCH_EVERY_SAMPLES=1` để nhịp đập ngay sau mẫu đầu: mặc định 50 mẫu thì ca này cần 50 tầng
    chỉ để chứng minh một điều không liên quan gì tới số 50.
    """
    monkeypatch.setattr(tasks, "TOUCH_EVERY_SAMPLES", 1)
    async with db_sessionmaker() as db:
        scene = await make_scene(db)
        await approved_floor(db, local_storage, scene, fake_clock)
        await approved_floor(db, local_storage, scene, fake_clock, page=png_bytes(WIDTH, HEIGHT + 4))
        await db.commit()
    version_id = await open_building_version(db_sessionmaker, fake_clock)
    storage = AtPutStorage(
        local_storage, at_put=3, hook=lambda: set_failed(db_sessionmaker, version_id, clock=fake_clock)
    )

    await run_build_dataset_version(db_sessionmaker, storage, fake_clock, version_id=version_id)

    row = await read_version(db_sessionmaker, version_id)
    assert (row.status, row.manifest_sha256) == ("failed", None)
    assert not any(key.endswith("manifest.jsonl") for key in await _keys(local_storage, version_id))


async def test_build_dataset_version__cleans_up_when_finish_loses(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, safe_client: AsyncRedis
) -> None:
    """Bản bị chốt `failed` trước `finish_version` → `False` → đọc lại và xoá tiền tố (bước 9)."""
    async with db_sessionmaker() as db:
        scene = await make_scene(db)
        await approved_floor(db, local_storage, scene, fake_clock)
        await db.commit()
    version_id = await open_building_version(db_sessionmaker, fake_clock)
    storage = AtPutStorage(
        local_storage, at_put=4, hook=lambda: set_failed(db_sessionmaker, version_id, clock=fake_clock)
    )

    await run_build_dataset_version(db_sessionmaker, storage, fake_clock, version_id=version_id)

    row = await read_version(db_sessionmaker, version_id)
    assert (row.status, row.manifest_sha256) == ("failed", None)
    assert await _keys(local_storage, version_id) == []


# ---------------------------------------------------------------------------
# Cửa lọc ảnh và tài liệu — ca chỉ dựng được bằng cách chạm trực tiếp
# ---------------------------------------------------------------------------


async def test_build_dataset_version__missing_page_object(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, safe_client: AsyncRedis
) -> None:
    """Dòng `drawings` còn nhưng object trang đã mất → bỏ tầng (`no_image`), không ném."""
    async with db_sessionmaker() as db:
        scene = await make_scene(db)
        floor = await approved_floor(db, local_storage, scene, fake_clock)
        page_key = await page_key_of(db, floor)
        await db.commit()
    await local_storage.delete(page_key)

    assert (await _build_or_fail(db_sessionmaker, local_storage, fake_clock)).failure_code == DATASET_EMPTY


async def test_build_dataset_version__png_with_broken_ihdr(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, safe_client: AsyncRedis
) -> None:
    """Chữ ký PNG đúng nhưng IHDR hỏng → `read_png_header` ném `ValueError` → bỏ tầng, không ném."""
    async with db_sessionmaker() as db:
        scene = await make_scene(db)
        floor = await approved_floor(db, local_storage, scene, fake_clock)
        page_key = await page_key_of(db, floor)
        await db.commit()
    await local_storage.put(page_key, PNG_SIGNATURE + b"rac", content_type="image/png", max_bytes=64)

    assert (await _build_or_fail(db_sessionmaker, local_storage, fake_clock)).failure_code == DATASET_EMPTY


async def test_read_floor_reports_a_missing_document(db_session: AsyncSession) -> None:
    """Dòng `floor_documents` mất giữa lúc liệt kê và lúc đọc → `no_document`.

    Không dựng được qua lượt dựng thật (câu liệt kê `JOIN floor_documents` đã loại tầng như thế),
    nên gọi thẳng hàm đọc một tầng — đúng nơi luật ấy sống.
    """
    scene = await make_scene(db_session)
    floor = await make_floor(db_session, project=scene.project)
    stmt = select(FloorRow.pk, FloorRow.project_id, FloorRow.level_id).where(FloorRow.pk == floor.pk)
    row = (await db_session.execute(stmt)).one()

    assert await tasks._read_floor(db_session, row, "wallSegmentation") == "no_document"


async def test_close_ignores_an_iterator_without_aclose() -> None:
    """Kho trả bộ duyệt **không** phải bộ sinh (không có `aclose`) thì `_close` bỏ qua, không ném."""

    class _Chunks:
        """Bộ duyệt byte trần — đúng cổng `AsyncIterator`, không có `aclose`."""

        def __aiter__(self) -> "_Chunks":
            """Chính nó là bộ duyệt."""
            return self

        async def __anext__(self) -> bytes:
            """Rỗng ngay từ đầu."""
            raise StopAsyncIteration

    await tasks._close(_Chunks())


async def test_build_dataset_version__keeps_objects_when_another_run_finished(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, safe_client: AsyncRedis
) -> None:
    """Một lượt khác chốt `ready` trước → `finish_version` trả `False` và tiền tố **không** bị xoá.

    Đây là nửa còn lại của bước 9: chỉ bản `failed` mới được dọn, bản `ready` thì object dưới
    tiền tố là của lượt đã về đích.
    """
    async with db_sessionmaker() as db:
        scene = await make_scene(db)
        await approved_floor(db, local_storage, scene, fake_clock)
        await db.commit()
    version_id = await open_building_version(db_sessionmaker, fake_clock)
    storage = AtPutStorage(
        local_storage, at_put=4, hook=lambda: set_ready(db_sessionmaker, version_id, clock=fake_clock)
    )

    await run_build_dataset_version(db_sessionmaker, storage, fake_clock, version_id=version_id)

    row = await read_version(db_sessionmaker, version_id)
    assert (row.status, row.manifest_sha256) == ("ready", "b" * 64)
    assert await _keys(local_storage, version_id) != []


class _ClockThatStealsTheLock:
    """`Clock` bọc `FakeClock`; lượt `now()` **đầu tiên** xoá khoá dựng trong Redis thật.

    `_claim` gọi `clock.now()` để ghi `build_started_at`, và đó là lời gọi `now()` đầu tiên của một
    lượt dựng. Tiêm ở đây là cách duy nhất chen vào **đúng** khe giữa `_claim` và lượt `delete_prefix`
    dọn đầu lượt mà không phải gọi hàm private nào. Xoá bằng client **đồng bộ** vì `now()` là hàm đồng
    bộ — vẫn là Redis thật (K23), không phải `fakeredis`.
    """

    def __init__(self, inner: FakeClock, *, version_id: str) -> None:
        """Bọc đồng hồ `inner` cho bản `version_id`; `stolen` đánh dấu đã bị cướp."""
        self._inner = inner
        self._version_id = version_id
        self.stolen = False

    def now(self) -> datetime:
        """Giờ của `FakeClock`; lượt đầu cướp khoá trước khi trả về."""
        if not self.stolen:
            self.stolen = True
            client = safe_redis_sync()
            try:
                client.delete(f"lock:datasets:build:{self._version_id}")
            finally:
                client.close()
        return self._inner.now()


async def test_build_dataset_version__keeps_objects_when_the_lock_dies_before_cleanup(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, safe_client: AsyncRedis
) -> None:
    """Mất khoá giữa `_claim` và lượt dọn → **không** `delete_prefix`; object của lượt kia còn nguyên (NO-273).

    Đây là khe duy nhất của bước 2 mà bất biến số 1 từng bỏ ngỏ: `_claim` mở rồi đóng một session, nên
    một lượt khác có thể đã nhận cùng phiên bản và ghi object xong **trước** khi lượt này chạm kho.
    `build_started_at` khác `None` chứng minh lượt này đã qua `_claim`, tức dừng đúng trong khe cần kiểm.
    """
    async with db_sessionmaker() as db:
        scene = await make_scene(db)
        await approved_floor(db, local_storage, scene, fake_clock)
        await db.commit()
    version_id = await open_building_version(db_sessionmaker, fake_clock)
    rival_key = dataset_object(version_id, "manifest.jsonl")
    await local_storage.put(rival_key, b"{}\n", content_type="application/x-ndjson", max_bytes=16)
    clock = _ClockThatStealsTheLock(fake_clock, version_id=version_id)

    await run_build_dataset_version(db_sessionmaker, local_storage, clock, version_id=version_id)

    assert clock.stolen
    assert await local_storage.stat(rival_key) is not None, "object của lượt kia đã bị lượt mất khoá dọn mất"
    assert await _keys(local_storage, version_id) == [rival_key]
    row = await read_version(db_sessionmaker, version_id)
    assert (row.status, row.manifest_sha256) == ("building", None)
    assert row.build_started_at is not None
