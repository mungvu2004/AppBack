"""`pins`: ghim model, `used`, `persisted_revision`, `step_requeue_count` (B5-06a [8] mục `pins`).

Postgres thật (K23): CHECK, FK CASCADE và ngữ nghĩa "một lần" đều là hành vi của DB, không
mô phỏng được bằng fake. Một lượt chạy thật (`make_complete_upload` + `start_run`, B2-04) làm
FK cho mỗi test — bảng `pipeline_run_models` không đứng một mình được.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.drawings.runs import start_run
from apps.worker.pipeline_orchestrate.pins import (
    load_pins,
    mark_artifacts_purged,
    mark_persisted,
    pin_models,
    record_used,
    set_step_requeue,
)
from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.core.object_keys import model_prefix
from packages.ml_contracts.families import MODEL_FAMILIES, ModelFamily
from packages.ml_contracts.payloads import ModelRef
from packages.storage.local import LocalDiskStorage
from packages.testing.factories.auth import make_user
from packages.testing.factories.drawings import make_complete_upload, png_bytes
from packages.testing.factories.floors import make_floor
from packages.testing.factories.pipeline_orchestrate import classic_ref, make_run_pins
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.clock import FakeClock

_CLASSIC_MODELS: dict[ModelFamily, ModelRef] = {family: classic_ref(family) for family in MODEL_FAMILIES}


async def _run_id(db: AsyncSession, storage: LocalDiskStorage, clock: FakeClock) -> str:
    """Một `run_id` thật (FK của `pipeline_run_models`) — sân khấu tối thiểu + một lượt tải PNG."""
    user = await make_user(db)
    project = await make_project(db, owner=user)
    floor = await make_floor(db, project=project)
    upload = await make_complete_upload(db, storage, project=project, floor=floor, data=png_bytes(10, 10))
    row = await start_run(db, upload_id=upload.id, clock=clock)
    return row.id


async def test_pin_models_second_call_returns_false(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Giao lặp J06: dòng đã có giữ bản đầu, `pin_models` lần hai (bộ **khác**) trả `False`.

    Lần hai ghim bản storage cho cả ba họ — nếu `pin_models` ghi đè, `pinned` đọc lại sẽ lệch
    bộ cổ điển của lần đầu (NO-295 P2-01).
    """
    run_id = await _run_id(db_session, local_storage, fake_clock)
    version_id = new_id("mdl", SystemClock())
    stored = {
        family: ModelRef(
            version_id=version_id,
            family=family,
            weights_key=f"{model_prefix(version_id)}model.onnx",
            pinned_name=None,
            checksum_sha256="a" * 64,
        )
        for family in MODEL_FAMILIES
    }
    assert await pin_models(db_session, run_id=run_id, models=_CLASSIC_MODELS) is True
    assert await pin_models(db_session, run_id=run_id, models=stored) is False
    loaded = await load_pins(db_session, run_id)
    assert loaded is not None
    assert loaded.pinned == _CLASSIC_MODELS


async def test_pin_models_missing_family_raises(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Thiếu một trong ba họ → `ValueError`, không ghi dòng nào."""
    run_id = await _run_id(db_session, local_storage, fake_clock)
    models: dict[ModelFamily, ModelRef] = {
        family: classic_ref(family) for family in MODEL_FAMILIES if family != "dimensionReading"
    }
    with pytest.raises(ValueError, match="thiếu họ"):
        await pin_models(db_session, run_id=run_id, models=models)
    assert await load_pins(db_session, run_id) is None


async def test_record_used_second_call_returns_false(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Họ đã ghi `used` → lần hai `False`; `last_used_at` được đặt."""
    run_id = await _run_id(db_session, local_storage, fake_clock)
    await pin_models(db_session, run_id=run_id, models=_CLASSIC_MODELS)
    assert await record_used(db_session, run_id=run_id, family="wallSegmentation", used="classic") is True
    assert await record_used(db_session, run_id=run_id, family="wallSegmentation", used="classic") is False
    loaded = await load_pins(db_session, run_id)
    assert loaded is not None
    assert loaded.used == {"wallSegmentation": "classic"}


async def test_mark_persisted_second_call_returns_false_and_resets_requeue(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """`mark_persisted` chỉ ghi khi còn NULL; thành công thì `step_requeue_count` về 0."""
    run_id = await _run_id(db_session, local_storage, fake_clock)
    await pin_models(db_session, run_id=run_id, models=_CLASSIC_MODELS)
    await set_step_requeue(db_session, run_id=run_id, count=2)
    assert await mark_persisted(db_session, run_id=run_id, revision=1) is True
    assert await mark_persisted(db_session, run_id=run_id, revision=2) is False
    loaded = await load_pins(db_session, run_id)
    assert loaded is not None
    assert (loaded.persisted_revision, loaded.step_requeue_count) == (1, 0)


async def test_mark_persisted_negative_revision_raises(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """`revision < 0` → `ValueError`, không chạm DB."""
    run_id = await _run_id(db_session, local_storage, fake_clock)
    await pin_models(db_session, run_id=run_id, models=_CLASSIC_MODELS)
    with pytest.raises(ValueError, match="không được âm"):
        await mark_persisted(db_session, run_id=run_id, revision=-1)


async def test_set_step_requeue_negative_count_raises(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """`count < 0` → `ValueError`."""
    run_id = await _run_id(db_session, local_storage, fake_clock)
    await pin_models(db_session, run_id=run_id, models=_CLASSIC_MODELS)
    with pytest.raises(ValueError, match="không được âm"):
        await set_step_requeue(db_session, run_id=run_id, count=-1)


async def test_mark_artifacts_purged_second_call_returns_false(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Đã dọn rồi → `False`, `artifacts_purged_at` giữ mốc đầu."""
    run_id = await _run_id(db_session, local_storage, fake_clock)
    await pin_models(db_session, run_id=run_id, models=_CLASSIC_MODELS)
    at = fake_clock.now()
    assert await mark_artifacts_purged(db_session, run_id=run_id, at=at) is True
    assert await mark_artifacts_purged(db_session, run_id=run_id, at=datetime.now(UTC)) is False


async def test_delete_run_cascades_to_run_models(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Xoá `pipeline_runs` → dòng `pipeline_run_models` biến mất theo (FK CASCADE)."""
    run_id = await _run_id(db_session, local_storage, fake_clock)
    await pin_models(db_session, run_id=run_id, models=_CLASSIC_MODELS)
    await db_session.execute(text("DELETE FROM pipeline_runs WHERE id = :run_id"), {"run_id": run_id})
    assert await load_pins(db_session, run_id) is None


async def test_make_run_pins_applies_used_and_persisted_revision(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """`make_run_pins` (mặc định cổ điển) ghim rồi áp `used`/`persisted_revision`/số đếm."""
    run_id = await _run_id(db_session, local_storage, fake_clock)
    await make_run_pins(
        db_session,
        run_id=run_id,
        used={"wallSegmentation": "classic"},
        persisted_revision=3,
        step_requeue_count=1,
    )
    loaded = await load_pins(db_session, run_id)
    assert loaded is not None
    assert loaded.used == {"wallSegmentation": "classic"}
    assert (loaded.persisted_revision, loaded.step_requeue_count) == (3, 1)


async def test_load_pins_for_update_locks_the_row(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """`for_update=True` vẫn đọc đúng dòng (nhánh `FOR UPDATE` của `load_pins`)."""
    run_id = await _run_id(db_session, local_storage, fake_clock)
    await pin_models(db_session, run_id=run_id, models=_CLASSIC_MODELS)
    loaded = await load_pins(db_session, run_id, for_update=True)
    assert loaded is not None
    assert loaded.run_id == run_id


async def test_check_constraints_reject_negative_values(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """CHECK chặn `step_requeue_count` âm ghi thẳng bằng SQL (phòng thủ ở DB, không chỉ ở hàm)."""
    run_id = await _run_id(db_session, local_storage, fake_clock)
    await pin_models(db_session, run_id=run_id, models=_CLASSIC_MODELS)
    await db_session.flush()
    with pytest.raises(IntegrityError):
        await db_session.execute(
            text("UPDATE pipeline_run_models SET step_requeue_count = -1 WHERE run_id = :run_id"),
            {"run_id": run_id},
        )
    await db_session.rollback()
