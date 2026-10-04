"""`create_version`, `snapshot_of`, `decode_snapshot`, `summary_query` và bảng `versions` (B3-04 [5], [6], [8]).

Postgres thật, không mock session (CLAUDE.md). Tài liệu đổi bằng `write_layer` (qua `bump`), không
bằng SQL trên `floor_documents`, để `revision` tăng đúng như đường ghi thật.
"""

import copy
import logging
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import delete, event, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.spatial_read.documents import FloorDocument, load_document
from apps.api.spatial_read.tests._helpers import race
from apps.api.versions.snapshots import (
    create_version,
    decode_snapshot,
    get_versions_settings,
    record_version,
    reset_versions_settings_cache,
    snapshot_of,
    summary_query,
    version_row,
)
from apps.api.versions.tests._helpers import (
    PIPELINE_ACTOR,
    VersionScene,
    bump,
    keep_snapshots,
    make_version_scene,
    snap,
    versions_of,
)
from packages.core.clock import Clock
from packages.core.errors import AppError
from packages.core.ids import new_id
from packages.db.models.floors import FloorRow
from packages.db.models.projects import Project
from packages.db.models.versions import VersionRecord
from packages.testing.fixtures.clock import FakeClock

LOGGER = "apps.api.versions.snapshots"


async def _document(db: AsyncSession, floor_pk: int) -> FloorDocument:
    """Tài liệu hiện tại của tầng (phải tồn tại)."""
    document = await load_document(db, floor_pk)
    assert document is not None
    return document


async def test_create_version__same_revision_twice_returns_one_row(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """K18: pipeline giao lặp khi `revision` không đổi → cùng một dòng, không nhân đôi."""
    vs = await make_version_scene(db_session, fake_clock)
    first = await snap(db_session, vs, fake_clock, note="lần một")
    second = await snap(db_session, vs, fake_clock, note="lần hai")
    await db_session.commit()
    assert second == first
    rows = await versions_of(db_sessionmaker, vs.floor.pk)
    assert [(r.sequence, r.note) for r in rows] == [(1, "lần một")]
    assert rows[0].snapshot is not None
    assert (first.sequence, first.floor_revision, first.label, first.has_snapshot) == (1, 0, None, True)


async def test_create_version__changed_document_makes_next_sequence(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Đổi tài liệu qua `write_layer` → bản mới `sequence + 1` với `floorRevision` mới."""
    vs = await make_version_scene(db_session, fake_clock)
    first = await snap(db_session, vs, fake_clock)
    revision = await bump(db_session, vs, fake_clock, length=2000)
    second = await snap(db_session, vs, fake_clock)
    assert (second.sequence, second.floor_revision) == (first.sequence + 1, revision)
    assert second.floor_revision != first.floor_revision
    assert (second.floor_pk, second.project_id) == (vs.floor.pk, vs.scene.project.id)
    assert second.created_at == fake_clock.now()


async def test_create_version__cap_strips_old_snapshots_but_keeps_rows(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trần 3, tạo 5 bản → hai bản cũ mất ảnh chụp nhưng siêu dữ liệu và dòng còn nguyên."""
    keep_snapshots(monkeypatch, 3)
    vs = await make_version_scene(db_session, fake_clock)
    for index in range(5):
        if index:
            await bump(db_session, vs, fake_clock, length=1000 + index * 100)
        last = await snap(db_session, vs, fake_clock, note=f"bản {index + 1}")
    await db_session.commit()
    rows = await versions_of(db_sessionmaker, vs.floor.pk)
    assert [r.sequence for r in rows] == [1, 2, 3, 4, 5]
    assert [r.snapshot is not None for r in rows] == [False, False, True, True, True]
    assert [r.note for r in rows] == [f"bản {n}" for n in range(1, 6)]
    assert last.has_snapshot
    by_query = (await db_session.execute(summary_query().where(VersionRecord.floor_pk == vs.floor.pk))).mappings().all()
    assert sorted(r["sequence"] for r in by_query if not r["has_snapshot"]) == [1, 2]


async def test_create_version__system_pipeline_actor_keeps_literal(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """`actor_id="system:pipeline"` → `creator_id` đúng literal; tên được chuẩn hoá NFC."""
    vs = await make_version_scene(db_session, fake_clock)
    row = await create_version(
        db_session,
        floor_pk=vs.floor.pk,
        actor_id=PIPELINE_ACTOR,
        actor_name="Pipeline nhận dạng",
        note=None,
        clock=fake_clock,
    )
    await db_session.commit()
    assert row.creator_id == "system:pipeline"
    assert row.creator_name == "Pipeline nhận dạng"
    assert row.note is None
    (stored,) = await versions_of(db_sessionmaker, vs.floor.pk)
    assert stored.creator_id == "system:pipeline"


@pytest.mark.parametrize(
    ("actor_id", "actor_name", "note"),
    [
        ("usr_short", "An", None),
        ("system:worker", "An", None),
        ("system:pipeline", "", None),
        ("system:pipeline", "   \t", None),
        ("system:pipeline", "An", ""),
    ],
)
async def test_create_version__invalid_input_raises_value_error(
    db_session: AsyncSession, fake_clock: FakeClock, actor_id: str, actor_name: str, note: str | None
) -> None:
    """K21: `actor_id` sai mẫu, tên rỗng/khoảng trắng, `note=""` → `ValueError` trước mọi truy vấn."""
    vs = await make_version_scene(db_session, fake_clock)
    with pytest.raises(ValueError, match=r".+"):
        await create_version(
            db_session, floor_pk=vs.floor.pk, actor_id=actor_id, actor_name=actor_name, note=note, clock=fake_clock
        )


@pytest.mark.parametrize("state", ["missing", "soft_deleted"])
async def test_create_version__floor_not_found(db_session: AsyncSession, fake_clock: FakeClock, state: str) -> None:
    """Tầng không có hoặc đã xoá mềm → `NOT_FOUND` `resource="floor"`."""
    vs = await make_version_scene(db_session, fake_clock)
    floor_pk = vs.floor.pk
    if state == "soft_deleted":
        await db_session.execute(update(FloorRow).where(FloorRow.pk == floor_pk).values(deleted_at=fake_clock.now()))
    else:
        floor_pk = 2_000_000_000
    with pytest.raises(AppError) as caught:
        await create_version(
            db_session, floor_pk=floor_pk, actor_id=vs.actor.id, actor_name="An", note=None, clock=fake_clock
        )
    assert caught.value.code.status == 404
    assert caught.value.params["resource"] == "floor"


async def test_create_version__creates_missing_document_then_snapshots_it(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Tầng chưa có tài liệu → `ensure_document` rồi chụp bản `floorRevision` 0."""
    vs = await make_version_scene(db_session, fake_clock, document=False)
    row = await snap(db_session, vs, fake_clock)
    assert (row.sequence, row.floor_revision) == (1, 0)


async def test_create_version__parallel_on_floor_without_document(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Hai giao dịch song song trên tầng chưa có tài liệu: không lỗi, `sequence` không trùng, không nhân đôi."""
    async with db_sessionmaker() as setup:
        vs = await make_version_scene(setup, fake_clock, document=False)

    async def one() -> int:
        """Một lượt chụp trong phiên riêng; trả `sequence`."""
        async with db_sessionmaker() as session:
            row = await snap(session, vs, fake_clock)
            await session.commit()
            return row.sequence

    results = await race(one, one)
    assert all(isinstance(r, int) for r in results), results
    rows = await versions_of(db_sessionmaker, vs.floor.pk)
    assert len({r.sequence for r in rows}) == len(rows) == 1
    assert set(results) == {1}


async def test_record_version__stores_restore_fields(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Hàm nội bộ ghi `restored_from_id`, `restore_base_revision`; vỏ công khai để trống."""
    vs = await make_version_scene(db_session, fake_clock)
    await snap(db_session, vs, fake_clock)
    revision = await bump(db_session, vs, fake_clock, length=1500)
    source = new_id("ver", fake_clock)
    row = await record_version(
        db_session,
        floor_pk=vs.floor.pk,
        actor_id=vs.actor.id,
        actor_name=vs.actor.name,
        note="sau",
        clock=fake_clock,
        restored_from_id=source,
        restore_base_revision=revision - 1,
    )
    await db_session.commit()
    first, second = await versions_of(db_sessionmaker, vs.floor.pk)
    assert (first.restored_from_id, first.restore_base_revision) == (None, None)
    assert (second.id, second.restored_from_id, second.restore_base_revision) == (row.id, source, revision - 1)


def test_get_versions_settings__default_is_fifty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Không đặt biến môi trường → giữ ảnh chụp 50 bản mới nhất; đọc lười, reset đọc lại."""
    monkeypatch.delenv("VERSIONS_KEEP_SNAPSHOTS", raising=False)
    reset_versions_settings_cache()
    assert get_versions_settings().versions_keep_snapshots == 50
    monkeypatch.setenv("VERSIONS_KEEP_SNAPSHOTS", "7")
    assert get_versions_settings().versions_keep_snapshots == 50
    reset_versions_settings_cache()
    assert get_versions_settings().versions_keep_snapshots == 7
    monkeypatch.delenv("VERSIONS_KEEP_SNAPSHOTS")
    reset_versions_settings_cache()


@pytest.mark.parametrize("scale", [None, Decimal("2.5")])
async def test_snapshot_of__scale_key_only_when_scale_known(
    db_session: AsyncSession, fake_clock: FakeClock, scale: Decimal | None
) -> None:
    """`scaleMmPerPx` vắng khi tỉ lệ NULL, là `str(Decimal)` khi có (K20)."""
    vs = await make_version_scene(db_session, fake_clock, scale=scale)
    document = await _document(db_session, vs.floor.pk)
    snapshot = snapshot_of(document)
    assert snapshot["schemaVersion"] == 1
    body = snapshot["document"]
    assert isinstance(body, dict)
    assert set(body) == {"layer", "axes", "dimensions"}
    if scale is None:
        assert "scaleMmPerPx" not in snapshot
    else:
        assert snapshot["scaleMmPerPx"] == str(document.scale_mm_per_px)
        assert Decimal(str(snapshot["scaleMmPerPx"])) == scale


async def test_decode_snapshot__valid_roundtrip_and_absent(
    db_session: AsyncSession, fake_clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    """Bản hợp lệ giải đúng `layer`, `dimensions`, tỉ lệ; `None` → `None` **không** log."""
    vs = await make_version_scene(db_session, fake_clock, scale=Decimal("2.5"))
    document = await _document(db_session, vs.floor.pk)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        decoded = decode_snapshot(snapshot_of(document), version_id="ver_x")
        assert decode_snapshot(None, version_id="ver_x") is None
    assert decoded is not None
    assert (decoded.layer, decoded.dimensions) == (document.layer, document.dimensions)
    assert decoded.scale_mm_per_px == document.scale_mm_per_px
    assert caplog.records == []


async def test_decode_snapshot__without_scale_key_gives_none_scale(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Ảnh chụp không có `scaleMmPerPx` → `scale_mm_per_px is None`."""
    vs = await make_version_scene(db_session, fake_clock)
    decoded = decode_snapshot(snapshot_of(await _document(db_session, vs.floor.pk)), version_id="ver_x")
    assert decoded is not None
    assert decoded.scale_mm_per_px is None


def _set(key: str, value: Any) -> Callable[[dict[str, Any]], None]:
    """Đột biến: đặt `raw[key] = value`."""

    def apply(raw: dict[str, Any]) -> None:
        """Gán `key = value` vào ảnh chụp thô."""
        raw[key] = value

    return apply


def _drop_document(raw: dict[str, Any]) -> None:
    """Đột biến: bỏ khoá `document`."""
    del raw["document"]


def _extra_document_key(raw: dict[str, Any]) -> None:
    """Đột biến: thêm khoá lạ vào `document` (khoá lạ → `DocumentCorruptError`)."""
    raw["document"]["unexpected"] = 1


@pytest.mark.parametrize(
    "mutate",
    [
        _set("schemaVersion", 2),
        _drop_document,
        _set("document", []),
        _extra_document_key,
        _set("scaleMmPerPx", "abc"),
        _set("scaleMmPerPx", 2.5),
        _set("scaleMmPerPx", "-1"),
        _set("scaleMmPerPx", "NaN"),
    ],
)
async def test_decode_snapshot__mismatch_returns_none_and_logs(
    db_session: AsyncSession,
    fake_clock: FakeClock,
    caplog: pytest.LogCaptureFixture,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    """Lược đồ lệch / khoá lạ / tỉ lệ hỏng → `None` và một log `snapshot_schema_mismatch` kèm `version_id`."""
    vs = await make_version_scene(db_session, fake_clock, scale=Decimal("2.5"))
    raw = copy.deepcopy(snapshot_of(await _document(db_session, vs.floor.pk)))
    mutate(raw)
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        assert decode_snapshot(raw, version_id="ver_bad") is None
    (record,) = caplog.records
    assert record.getMessage() == "snapshot_schema_mismatch"
    assert record.__dict__["version_id"] == "ver_bad"


async def test_summary_query__never_selects_snapshot_column(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Câu SQL thật chỉ nhắc `snapshot` trong `IS NOT NULL AS has_snapshot`; `version_row` dựng đúng dòng."""
    vs = await make_version_scene(db_session, fake_clock)
    created = await snap(db_session, vs, fake_clock)
    statements: list[str] = []

    def capture(_conn: Any, _cursor: Any, statement: str, *_rest: Any) -> None:
        """Ghi lại mọi câu SQL gửi tới Postgres."""
        statements.append(statement)

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", capture)
    try:
        rows = (await db_session.execute(summary_query().where(VersionRecord.floor_pk == vs.floor.pk))).mappings().all()
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    (sql,) = [s for s in statements if "FROM versions" in s]
    assert "versions.snapshot IS NOT NULL AS has_snapshot" in sql
    assert "snapshot" not in sql.replace("versions.snapshot IS NOT NULL AS has_snapshot", "")
    assert [version_row(r) for r in rows] == [created]


async def test_versions__hard_delete_of_floor_or_project_cascades(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """CASCADE: xoá cứng tầng → dòng `versions` của tầng mất; xoá cứng dự án → dòng của dự án mất."""
    first = await make_version_scene(db_session, fake_clock)
    second = await make_version_scene(db_session, fake_clock)
    await snap(db_session, first, fake_clock)
    await snap(db_session, second, fake_clock)
    await db_session.commit()
    await db_session.execute(delete(FloorRow).where(FloorRow.pk == first.floor.pk))
    await db_session.commit()
    assert await versions_of(db_sessionmaker, first.floor.pk) == []
    assert len(await versions_of(db_sessionmaker, second.floor.pk)) == 1
    await db_session.execute(delete(Project).where(Project.id == second.scene.project.id))
    await db_session.commit()
    assert await versions_of(db_sessionmaker, second.floor.pk) == []
    total = (await db_session.execute(select(func.count()).select_from(VersionRecord))).scalar_one()
    assert total == 0


def _record(vs: VersionScene, clock: Clock, **override: Any) -> VersionRecord:
    """Một dòng `versions` hợp lệ, ghi đè bằng `override` để mỗi test phá đúng một CHECK."""
    now = clock.now()
    values: dict[str, Any] = {
        "id": new_id("ver", clock),
        "floor_pk": vs.floor.pk,
        "project_id": vs.scene.project.id,
        "sequence": 1,
        "floor_revision": 0,
        "creator_id": vs.actor.id,
        "creator_name": "An",
        "created_at": now,
        "updated_at": now,
    }
    return VersionRecord(**{**values, **override})


@pytest.mark.parametrize(
    "override",
    [
        {"label": "x" * 61},
        {"label": ""},
        {"note": ""},
        {"creator_id": "usr_khong-hop-le"},
        {"creator_id": "system:worker"},
        {"creator_name": ""},
        {"sequence": 0},
        {"floor_revision": -1},
    ],
)
async def test_versions__check_rejects_bad_row(
    db_session: AsyncSession, fake_clock: FakeClock, override: dict[str, Any]
) -> None:
    """CHECK của [5]: nhãn 61 ký tự, `creator_id` sai mẫu, chuỗi rỗng, số ngoài miền → `IntegrityError`."""
    vs = await make_version_scene(db_session, fake_clock)
    db_session.add(_record(vs, fake_clock, **override))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_versions__boundary_row_and_duplicate_sequence(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Nhãn 60 ký tự và `system:pipeline` được nhận; trùng `(floor_pk, sequence)` bị unique chặn."""
    vs = await make_version_scene(db_session, fake_clock)
    db_session.add(_record(vs, fake_clock, label="x" * 60, creator_id=PIPELINE_ACTOR))
    await db_session.flush()
    db_session.add(_record(vs, fake_clock))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_create_version__reads_floors_once(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Một lượt chụp chỉ chạm `floors` một lần (câu khoá); `project_id` lấy từ câu đó (NO-245)."""
    vs = await make_version_scene(db_session, fake_clock)
    statements: list[str] = []

    def capture(_conn: Any, _cursor: Any, statement: str, *_rest: Any) -> None:
        """Ghi lại mọi câu SQL gửi tới Postgres."""
        statements.append(statement)

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", capture)
    try:
        created = await snap(db_session, vs, fake_clock)
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert created.project_id == vs.floor.project_id
    assert len([s for s in statements if s.startswith("SELECT") and "FROM floors" in s]) == 1
