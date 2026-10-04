"""Hàm `registry` cho worker (B6-01 [2], [8] mục `registry`): `active_versions`, `register_trained_version`,
`set_evaluation`, `request_evaluation`. Chạy trên Postgres và Redis thật (K23)."""

import asyncio
import math
from typing import Any, Final

import pytest
from sqlalchemy import event, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.admin_ml_registry.registry import (
    active_versions,
    register_trained_version,
    request_evaluation,
    set_evaluation,
)
from apps.api.admin_ml_registry.tests._helpers import DIMENSION, ML_QUEUE, OPENING, WALL
from packages.core.ids import new_id
from packages.core.object_keys import MODELS_PREFIX
from packages.db.hooks import after_commit_idle
from packages.db.models.admin_ml_registry import ModelFamilyRow, ModelVersionRow
from packages.messaging.redis import broker_redis_sync
from packages.ml_contracts.families import MODEL_FAMILIES
from packages.testing.factories.admin_ml_registry import make_model_version
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.messaging import queued_payloads

OPENING_BASELINE: Final = "mdl_01KB6010000000000000000001"
SHA: Final = "a" * 64
FLAT_CODE: Final = "MODEL_FORMAT_UNSUPPORTED"


def _register_args(fake_clock: FakeClock, **override: Any) -> dict[str, Any]:
    """Tham số hợp lệ của `register_trained_version`; `override` thay từng khoá để dựng ca sai."""
    version_id = override.get("version_id") or new_id("mdl", fake_clock)
    args: dict[str, Any] = {
        "version_id": version_id,
        "family": WALL,
        "label": "  huấn luyện lần 1  ",
        "weights_key": f"{MODELS_PREFIX}{version_id}/weights.safetensors",
        "weights_format": "safetensors",
        "checksum_sha256": SHA,
        "training_job_id": new_id("job", fake_clock),
        "dataset_version_id": new_id("dsv", fake_clock),
        "creator_id": "system:pipeline",
        "clock": fake_clock,
    }
    return args | override


async def _reload(db: AsyncSession, row: ModelVersionRow) -> ModelVersionRow:
    """Commit rồi đọc lại `row` từ DB: khẳng định trạng thái bền, không phải identity map."""
    await db.commit()
    await db.refresh(row)
    return row


async def _count(maker: async_sessionmaker[AsyncSession], **where: str) -> int:
    """Số dòng `model_versions` khớp các cột `where`, đọc bằng session riêng."""
    async with maker() as db:
        stmt = select(func.count()).select_from(ModelVersionRow)
        for column, value in where.items():
            stmt = stmt.where(getattr(ModelVersionRow, column) == value)
        return (await db.execute(stmt)).scalar_one()


# ---------------------------------------------------------------------------
# active_versions
# ---------------------------------------------------------------------------


async def test_active_versions_has_all_three_families_with_classic_wall(db_session: AsyncSession) -> None:
    """Đủ 3 khoá; `wallSegmentation` chưa kích hoạt → cổ điển, hai họ còn lại → bản gốc dạng ghim."""
    refs = await active_versions(db_session)

    assert set(refs) == set(MODEL_FAMILIES)
    wall = refs[WALL]
    assert (wall.version_id, wall.weights_key, wall.pinned_name, wall.checksum_sha256) == (None, None, None, "")
    assert wall.family == WALL
    assert refs[OPENING].version_id == OPENING_BASELINE
    assert refs[OPENING].pinned_name == "yolov8n"
    assert refs[DIMENSION].pinned_name == "rapidocrRec"


async def test_active_versions_returns_the_storage_form_after_activation(db_session: AsyncSession) -> None:
    """Họ kích hoạt một bản tải lên → `ModelRef` dạng storage mang `weights_key` và checksum của bản đó."""
    row = await make_model_version(db_session, family=WALL)
    await db_session.execute(
        update(ModelFamilyRow).where(ModelFamilyRow.family == WALL).values(active_version_id=row.id)
    )

    refs = await active_versions(db_session)

    assert (refs[WALL].version_id, refs[WALL].weights_key) == (row.id, row.weights_key)
    assert refs[WALL].pinned_name is None
    assert refs[WALL].checksum_sha256 == row.checksum_sha256


async def test_active_versions_runs_one_query(db_session: AsyncSession) -> None:
    """Pipeline ghim ở đầu lượt: đúng một câu SELECT, không N lượt đọc theo họ."""
    statements: list[str] = []
    engine = db_session.get_bind()

    def record(_conn: object, _cursor: object, statement: str, *_rest: object) -> None:
        """Ghi mọi câu SQL đi qua engine."""
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        await active_versions(db_session)
    finally:
        event.remove(engine, "before_cursor_execute", record)

    assert len([s for s in statements if s.lstrip().upper().startswith("SELECT")]) == 1


# ---------------------------------------------------------------------------
# register_trained_version
# ---------------------------------------------------------------------------


async def test_register_trained_version_inserts_a_pending_row(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Bản mới `pending`, `attempts 0`, chưa gửi lần nào (`requested_at NULL`), nhãn đã `nfc(strip)`."""
    args = _register_args(fake_clock)

    returned = await register_trained_version(db_session, **args)
    row = await db_session.get(ModelVersionRow, returned)

    assert returned == args["version_id"]
    assert row is not None
    assert (row.evaluation_status, row.evaluation_attempts, row.evaluation_requested_at) == ("pending", 0, None)
    assert (row.label, row.family, row.metrics, row.evaluation_error_code) == ("huấn luyện lần 1", WALL, None, None)
    assert (row.training_job_id, row.dataset_version_id) == (args["training_job_id"], args["dataset_version_id"])
    assert (row.created_at, row.updated_at) == (fake_clock.now(), fake_clock.now())


async def test_register_trained_version__J06_repeat_returns_the_same_id(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Cùng `version_id` **và** cùng `training_job_id`: lặp lại trả id cũ, vẫn một dòng."""
    args = _register_args(fake_clock)
    first = await register_trained_version(db_session, **args)
    await db_session.commit()

    second = await register_trained_version(db_session, **args)
    await db_session.commit()

    assert first == second == args["version_id"]
    assert await _count(db_sessionmaker, training_job_id=args["training_job_id"]) == 1


async def test_register_trained_version_rejects_a_pair_that_matches_only_one_side(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Cùng job khác id, hay cùng id khác job → `ValueError`, không ghi thêm dòng."""
    args = _register_args(fake_clock)
    await register_trained_version(db_session, **args)
    await db_session.commit()

    same_job = _register_args(fake_clock, training_job_id=args["training_job_id"])
    with pytest.raises(ValueError, match="thuộc một bản khác"):
        await register_trained_version(db_session, **same_job)
    same_id = _register_args(fake_clock, version_id=args["version_id"])
    with pytest.raises(ValueError, match="thuộc một bản khác"):
        await register_trained_version(db_session, **same_id)


async def test_register_trained_version_concurrent_same_args_makes_one_row(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Hai lượt chạy song song cùng tham số (task giao lặp): đều trả id, DB có đúng một dòng."""
    args = _register_args(fake_clock)

    async def attempt() -> str:
        """Một lượt đăng ký bản huấn luyện trong session riêng, commit rồi trả id."""
        async with db_sessionmaker() as db:
            version_id = await register_trained_version(db, **args)
            await db.commit()
            return version_id

    results = await asyncio.gather(attempt(), attempt())

    assert list(results) == [args["version_id"]] * 2
    assert await _count(db_sessionmaker, id=args["version_id"]) == 1


async def test_register_trained_version_concurrent_same_job_different_id_loses_with_value_error(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Hai id khác nhau cho một job: đúng một bên thắng, bên kia `ValueError`, DB một dòng cho job."""
    job_id = new_id("job", fake_clock)

    async def attempt() -> str:
        """Một lượt đăng ký cùng `training_job_id` trong session riêng, commit rồi trả id."""
        async with db_sessionmaker() as db:
            version_id = await register_trained_version(db, **_register_args(fake_clock, training_job_id=job_id))
            await db.commit()
            return version_id

    results = await asyncio.gather(attempt(), attempt(), return_exceptions=True)

    assert sorted(type(result).__name__ for result in results) == ["ValueError", "str"]
    assert await _count(db_sessionmaker, training_job_id=job_id) == 1


_OTHER_ID: Final = "mdl_01KB6010000000000000000009"
_BAD_ARGS: Final[dict[str, dict[str, Any]]] = {
    "version-prefix": {"version_id": "mdx_01KB6010000000000000000009"},
    "version-body": {"version_id": "mdl_short"},
    "key-other-version": {"weights_key": f"{MODELS_PREFIX}{_OTHER_ID}/weights.onnx"},
    "key-prefix-only": {"weights_key": MODELS_PREFIX},
    "key-outside": {"weights_key": "projects/x/weights.onnx"},
    "family-not-trainable": {"family": DIMENSION},
    "family-unknown": {"family": "nope"},
    "format": {"weights_format": "pt"},
    "checksum-upper": {"checksum_sha256": "A" * 64},
    "checksum-short": {"checksum_sha256": "a" * 63},
    "job-prefix": {"training_job_id": "dsv_01KB6010000000000000000009"},
    "dsv-prefix": {"dataset_version_id": "job_01KB6010000000000000000009"},
    "creator-empty": {"creator_id": ""},
    "creator-long": {"creator_id": "x" * 65},
    "label-blank": {"label": "   "},
    "label-long": {"label": "x" * 81},
}


@pytest.mark.parametrize("override", _BAD_ARGS.values(), ids=_BAD_ARGS.keys())
async def test_register_trained_version_rejects_invalid_parameters(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    override: dict[str, Any],
) -> None:
    """Tham số sai luật → `ValueError` (lỗi lập trình của task), không dòng nào được ghi."""
    args = _register_args(fake_clock, **override)

    with pytest.raises(ValueError, match=r"phải|không huấn luyện được|lạ"):
        await register_trained_version(db_session, **args)

    assert await _count(db_sessionmaker, training_job_id=args["training_job_id"]) == 0


async def test_register_trained_version_accepts_boundary_lengths(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Biên hợp lệ: nhãn 80 ký tự, `creator_id` 64 ký tự."""
    args = _register_args(fake_clock, label="x" * 80, creator_id="c" * 64)

    assert await register_trained_version(db_session, **args) == args["version_id"]


# ---------------------------------------------------------------------------
# set_evaluation
# ---------------------------------------------------------------------------


async def _pending(db: AsyncSession, family: str = OPENING) -> ModelVersionRow:
    """Bản `pending` đã commit của `family`."""
    return await make_model_version(db, family=family, status="pending")


async def test_set_evaluation_returns_false_for_an_unknown_version(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Bản không có → `False`, không ném."""
    missing = new_id("mdl", fake_clock)
    result = await set_evaluation(
        db_session, version_id=missing, status="running", metrics=None, error_code=None, clock=fake_clock
    )

    assert result is False


@pytest.mark.parametrize("status", ["pending", "queued", ""])
async def test_set_evaluation_rejects_statuses_it_cannot_write(
    db_session: AsyncSession, fake_clock: FakeClock, status: str
) -> None:
    """Chỉ `running|completed|failed` ghi được; `pending` là việc của lịch và CLI."""
    row = await _pending(db_session)

    with pytest.raises(ValueError, match="không ghi được"):
        await set_evaluation(
            db_session, version_id=row.id, status=status, metrics=None, error_code=None, clock=fake_clock
        )


@pytest.mark.parametrize(
    ("family", "metrics"),
    [
        (OPENING, None),
        (OPENING, {}),
        (OPENING, {"iou": 0.5}),
        (OPENING, {"map50": 0.5, "iou": 0.5}),
        (OPENING, {"map50": 1.2}),
        (OPENING, {"map50": -0.1}),
        (OPENING, {"map50": math.nan}),
        (OPENING, {"map50": math.inf}),
        (WALL, {"iou": 1.2}),
        (WALL, {"cer": 0.1}),
        (DIMENSION, {"cer": -0.5}),
        (DIMENSION, {"cer": math.nan}),
        (DIMENSION, {"map50": 0.5}),
    ],
)
async def test_set_evaluation_rejects_invalid_metrics_for_completed(
    db_session: AsyncSession, fake_clock: FakeClock, family: str, metrics: dict[str, float] | None
) -> None:
    """`completed` cần đúng một khoá của họ, hữu hạn, trong dải; sai → `ValueError` và bản vẫn `pending`."""
    row = await _pending(db_session, family)

    with pytest.raises(ValueError, match=r"cần metrics|phải có đúng|ngoài dải|chỉ có số đo"):
        await set_evaluation(
            db_session, version_id=row.id, status="completed", metrics=metrics, error_code=None, clock=fake_clock
        )

    assert (await _reload(db_session, row)).evaluation_status == "pending"


@pytest.mark.parametrize("code", ["lower_case", "AB", "1ABC", "x" * 3])
async def test_set_evaluation_rejects_malformed_or_misplaced_error_codes(
    db_session: AsyncSession, fake_clock: FakeClock, code: str
) -> None:
    """Mã lỗi phải UPPER_SNAKE và chỉ đi với `failed`; `running` mang mã → `ValueError`."""
    row = await _pending(db_session)

    with pytest.raises(ValueError, match="mã lỗi"):
        await set_evaluation(
            db_session, version_id=row.id, status="failed", metrics=None, error_code=code, clock=fake_clock
        )
    with pytest.raises(ValueError, match="mã lỗi"):
        await set_evaluation(
            db_session, version_id=row.id, status="running", metrics=None, error_code=FLAT_CODE, clock=fake_clock
        )


@pytest.mark.parametrize("code", ["RETRY_EXHAUSTED", "DEPENDENCY_UNAVAILABLE"])
async def test_set_evaluation_ignores_transient_failure_codes(
    db_session: AsyncSession, fake_clock: FakeClock, code: str
) -> None:
    """`failed` + mã tạm → `False`, không ghi: bản còn `pending` để lịch gửi lại."""
    row = await _pending(db_session)

    result = await set_evaluation(
        db_session, version_id=row.id, status="failed", metrics=None, error_code=code, clock=fake_clock
    )

    assert result is False
    reloaded = await _reload(db_session, row)
    assert (reloaded.evaluation_status, reloaded.evaluation_error_code) == ("pending", None)


async def test_set_evaluation_records_a_final_failure_with_null_metrics(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """`failed` mã khác + `metrics={}` → `True`; `metrics` NULL (không JSON `null`), mã được lưu."""
    row = await _pending(db_session)

    result = await set_evaluation(
        db_session, version_id=row.id, status="failed", metrics={}, error_code=FLAT_CODE, clock=fake_clock
    )

    assert result is True
    reloaded = await _reload(db_session, row)
    assert (reloaded.evaluation_status, reloaded.evaluation_error_code, reloaded.metrics) == ("failed", FLAT_CODE, None)
    assert reloaded.updated_at == fake_clock.now()


async def test_set_evaluation_failed_without_a_code_is_allowed(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """`failed` không mã vẫn hợp lệ với CHECK của bảng (mã NULL)."""
    row = await _pending(db_session)

    assert await set_evaluation(
        db_session, version_id=row.id, status="failed", metrics=None, error_code=None, clock=fake_clock
    )
    assert (await _reload(db_session, row)).evaluation_error_code is None


async def test_set_evaluation_running_then_completed_stores_family_metric(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """`pending → running → completed`: số đo của họ được ghi, mã lỗi vắng."""
    row = await _pending(db_session, DIMENSION)

    running = await set_evaluation(
        db_session, version_id=row.id, status="running", metrics=None, error_code=None, clock=fake_clock
    )
    done = await set_evaluation(
        db_session, version_id=row.id, status="completed", metrics={"cer": 1.5}, error_code=None, clock=fake_clock
    )

    assert (running, done) == (True, True)
    reloaded = await _reload(db_session, row)
    assert (reloaded.evaluation_status, reloaded.metrics, reloaded.evaluation_error_code) == (
        "completed",
        {"cer": 1.5},
        None,
    )


async def test_set_evaluation_completed_overwrites_failed_and_clears_the_code(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Object bất biến (M06): `completed` ghi đè `failed`, mã lỗi cũ bị xoá."""
    row = await _pending(db_session)
    await set_evaluation(
        db_session, version_id=row.id, status="failed", metrics=None, error_code=FLAT_CODE, clock=fake_clock
    )

    result = await set_evaluation(
        db_session, version_id=row.id, status="completed", metrics={"map50": 0.6}, error_code=None, clock=fake_clock
    )

    assert result is True
    reloaded = await _reload(db_session, row)
    assert (reloaded.evaluation_status, reloaded.metrics, reloaded.evaluation_error_code) == (
        "completed",
        {"map50": 0.6},
        None,
    )


async def test_set_evaluation_running_does_not_revive_a_failed_version(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Thông điệp `running` tới muộn không kéo bản `failed` về "đang chạy" → `False`."""
    row = await _pending(db_session)
    await set_evaluation(
        db_session, version_id=row.id, status="failed", metrics=None, error_code=FLAT_CODE, clock=fake_clock
    )

    result = await set_evaluation(
        db_session, version_id=row.id, status="running", metrics=None, error_code=None, clock=fake_clock
    )

    assert result is False
    assert (await _reload(db_session, row)).evaluation_status == "failed"


@pytest.mark.parametrize("status", ["running", "failed", "completed"])
async def test_set_evaluation_never_rewrites_a_completed_version(
    db_session: AsyncSession, fake_clock: FakeClock, status: str
) -> None:
    """Kết quả `completed` bất biến (M06): mọi lần ghi sau → `False`, `metrics` giữ nguyên."""
    row = await make_model_version(db_session, family=OPENING, status="completed")
    before = dict(row.metrics or {})
    metrics = {"map50": 0.1} if status == "completed" else None
    code = FLAT_CODE if status == "failed" else None

    result = await set_evaluation(
        db_session, version_id=row.id, status=status, metrics=metrics, error_code=code, clock=fake_clock
    )

    assert result is False
    reloaded = await _reload(db_session, row)
    assert (reloaded.evaluation_status, reloaded.metrics) == ("completed", before)


# ---------------------------------------------------------------------------
# request_evaluation
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("messaging_env")
@pytest.mark.parametrize("status", ["pending", "running"])
async def test_request_evaluation_bumps_attempts_and_sends_after_commit(
    db_session: AsyncSession, fake_clock: FakeClock, status: str
) -> None:
    """`pending|running`: `attempts + 1`, `requested_at = now`, task chỉ gửi **sau** commit (K17)."""
    broker = broker_redis_sync()
    broker.delete(ML_QUEUE)
    row = await make_model_version(db_session, family=OPENING, status=status)
    try:
        await db_session.refresh(row)  # mở lại giao dịch cho `on_after_commit` bám vào
        result = await request_evaluation(db_session, version_id=row.id, clock=fake_clock)
        assert queued_payloads(broker, ML_QUEUE) == []
        await db_session.commit()
        await after_commit_idle(db_session)
        payloads = queued_payloads(broker, ML_QUEUE)
    finally:
        broker.delete(ML_QUEUE)
        broker.close()

    assert result is True
    assert [payload["version_id"] for payload in payloads] == [row.id]
    await db_session.refresh(row)
    assert (row.evaluation_attempts, row.evaluation_requested_at) == (1, fake_clock.now())
    assert row.updated_at == fake_clock.now()


@pytest.mark.usefixtures("messaging_env")
@pytest.mark.parametrize("status", ["completed", "failed"])
async def test_request_evaluation_skips_closed_versions_and_sends_nothing(
    db_session: AsyncSession, fake_clock: FakeClock, status: str
) -> None:
    """Bản đã chốt (`completed|failed`) → `False`: không ghi, không gửi."""
    broker = broker_redis_sync()
    broker.delete(ML_QUEUE)
    row = await make_model_version(db_session, family=OPENING, status=status)
    try:
        await db_session.refresh(row)
        result = await request_evaluation(db_session, version_id=row.id, clock=fake_clock)
        await db_session.commit()
        await after_commit_idle(db_session)
        assert queued_payloads(broker, ML_QUEUE) == []
    finally:
        broker.close()

    assert result is False
    await db_session.refresh(row)
    assert (row.evaluation_attempts, row.evaluation_requested_at) == (0, None)


async def test_request_evaluation_returns_false_for_an_unknown_version(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Bản không có → `False`."""
    assert await request_evaluation(db_session, version_id=new_id("mdl", fake_clock), clock=fake_clock) is False
