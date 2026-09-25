"""Bốn bảng của B2-04 trên Postgres thật (K23): CHECK **hai phía** biên, unique, cascade."""

from datetime import UTC, datetime
from typing import Any, Final

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.drawings.settings import get_drawings_settings, reset_drawings_settings_cache
from apps.api.drawings.tests._helpers import Scene, make_scene
from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.db.models.drawings import DrawingRow, PipelineRunRow, UploadChunkRow, UploadRow
from packages.db.models.floors import FloorRow
from packages.storage.local import LocalDiskStorage
from packages.testing.factories.drawings import make_complete_upload, make_upload

SHA: Final = "a" * 64
UPLOADED_AT: Final = datetime(2026, 1, 1, tzinfo=UTC)


def _upload(scene: Scene, **overrides: Any) -> UploadRow:
    """Một `UploadRow` hợp lệ; ghi đè đúng cột đang thử CHECK."""
    values: dict[str, Any] = {
        "id": new_id("upl", SystemClock()),
        "project_id": scene.project.id,
        "floor_pk": scene.floor.pk,
        "file_name": "ban-ve.png",
        "declared_size_bytes": 1024,
        "declared_type": "image/png",
        "page_index": 0,
        "chunk_count": 1,
        "status": "receiving",
        "created_by": scene.user.id,
    }
    return UploadRow(**(values | overrides))


def _run(scene: Scene, upload: UploadRow, **overrides: Any) -> PipelineRunRow:
    """Một `PipelineRunRow` hợp lệ; ghi đè đúng cột đang thử CHECK."""
    values: dict[str, Any] = {
        "id": new_id("run", SystemClock()),
        "upload_id": upload.id,
        "floor_pk": scene.floor.pk,
        "status": "pending",
        "current_step": "preprocess",
        "progress_percent": 0,
    }
    return PipelineRunRow(**(values | overrides))


def _drawing(scene: Scene, upload: UploadRow, **overrides: Any) -> DrawingRow:
    """Một `DrawingRow` hợp lệ; ghi đè đúng cột đang thử CHECK."""
    values: dict[str, Any] = {
        "id": new_id("drw", SystemClock()),
        "floor_pk": scene.floor.pk,
        "upload_id": upload.id,
        "name": "ban-ve.png",
        "page_key": "pages/0-X.png",
        "width_px": 100,
        "height_px": 80,
        "uploaded_at": UPLOADED_AT,
        "uploader_id": scene.user.id,
    }
    return DrawingRow(**(values | overrides))


@pytest.mark.parametrize(
    ("field", "value", "constraint"),
    [
        ("declared_size_bytes", 0, "declared_size_bytes_positive"),
        ("chunk_count", 0, "chunk_count_positive"),
        ("page_index", -1, "page_index_non_negative"),
        ("status", "receiving_", "status"),
    ],
)
async def test_upload_checks_reject_out_of_range(
    db_session: AsyncSession, field: str, value: object, constraint: str
) -> None:
    """Mỗi CHECK của `uploads` từ chối phía ngoài biên (B2-04 [5])."""
    scene = await make_scene(db_session)
    db_session.add(_upload(scene, **{field: value}))
    with pytest.raises(IntegrityError, match=constraint):
        await db_session.flush()


@pytest.mark.parametrize(("field", "value"), [("declared_size_bytes", 1), ("chunk_count", 1), ("page_index", 0)])
async def test_upload_checks_accept_inner_edge(db_session: AsyncSession, field: str, value: int) -> None:
    """Phía trong biên đi qua — CHECK không chặt hơn [5]."""
    scene = await make_scene(db_session)
    db_session.add(_upload(scene, **{field: value}))
    await db_session.flush()


@pytest.mark.parametrize(
    ("field", "value", "constraint"),
    [
        ("chunk_index", -1, "chunk_index_non_negative"),
        ("size_bytes", 0, "size_bytes_positive"),
        ("sha256", "A" * 64, "sha256_format"),
        ("sha256", "a" * 63, "sha256_format"),
    ],
)
async def test_chunk_checks_reject_out_of_range(
    db_session: AsyncSession, field: str, value: object, constraint: str
) -> None:
    """`upload_chunks`: chỉ số không âm, khúc có byte, `sha256` đúng 64 ký tự hex thường."""
    scene = await make_scene(db_session)
    upload = _upload(scene)
    db_session.add(upload)
    await db_session.flush()
    values: dict[str, Any] = {
        "upload_id": upload.id,
        "chunk_index": 0,
        "size_bytes": 1,
        "sha256": SHA,
        "object_key": "chunks/0/x",
    }
    db_session.add(UploadChunkRow(**(values | {field: value})))
    with pytest.raises(IntegrityError, match=constraint):
        await db_session.flush()


@pytest.mark.parametrize(
    ("field", "value", "constraint"),
    [
        ("progress_percent", -1, "progress_percent_range"),
        ("progress_percent", 101, "progress_percent_range"),
        ("requeue_count", -1, "requeue_count_non_negative"),
        ("status", "queued", "status"),
        ("current_step", "quality_check", "current_step"),
    ],
)
async def test_run_checks_reject_out_of_range(
    db_session: AsyncSession, field: str, value: object, constraint: str
) -> None:
    """`pipeline_runs`: trạng thái, bước (6 id của `PIPELINE_STEPS`), phần trăm, số quét bù."""
    scene = await make_scene(db_session)
    upload = _upload(scene)
    db_session.add(upload)
    await db_session.flush()
    db_session.add(_run(scene, upload, **{field: value}))
    with pytest.raises(IntegrityError, match=constraint):
        await db_session.flush()


@pytest.mark.parametrize(
    ("field", "value"),
    [("progress_percent", 0), ("progress_percent", 100), ("requeue_count", 0), ("current_step", "qualityCheck")],
)
async def test_run_checks_accept_inner_edge(db_session: AsyncSession, field: str, value: object) -> None:
    """Hai đầu của `progress_percent` và bước cuối đều hợp lệ."""
    scene = await make_scene(db_session)
    upload = _upload(scene)
    db_session.add(upload)
    await db_session.flush()
    db_session.add(_run(scene, upload, **{field: value}))
    await db_session.flush()


@pytest.mark.parametrize(("field", "constraint"), [("width_px", "width_px_positive"), ("height_px", "height_px")])
async def test_drawing_size_checks_reject_zero(db_session: AsyncSession, field: str, constraint: str) -> None:
    """`drawings`: kích thước pixel phải > 0 (0 là ảnh không vẽ được)."""
    scene = await make_scene(db_session)
    upload = _upload(scene)
    db_session.add(upload)
    await db_session.flush()
    db_session.add(_drawing(scene, upload, **{field: 0}))
    with pytest.raises(IntegrityError, match=constraint):
        await db_session.flush()


async def test_drawing_floor_pk_is_unique(db_session: AsyncSession) -> None:
    """Một tầng chỉ có một bản vẽ đang dùng — dòng thứ hai bị `uq_drawings_floor_pk` chặn."""
    scene = await make_scene(db_session)
    upload = _upload(scene)
    db_session.add(upload)
    await db_session.flush()
    db_session.add(_drawing(scene, upload))
    await db_session.flush()
    db_session.add(_drawing(scene, upload))
    with pytest.raises(IntegrityError, match="uq_drawings_floor_pk"):
        await db_session.flush()


async def test_deleting_floor_cascades_to_every_child(db_session: AsyncSession) -> None:
    """Xoá cứng một tầng dọn sạch upload, khúc, lượt chạy và bản vẽ của nó bằng một lệnh."""
    scene = await make_scene(db_session)
    upload = _upload(scene)
    db_session.add(upload)
    await db_session.flush()
    db_session.add_all(
        [
            UploadChunkRow(upload_id=upload.id, chunk_index=0, size_bytes=1, sha256=SHA, object_key="chunks/0/x"),
            _run(scene, upload),
            _drawing(scene, upload),
        ]
    )
    await db_session.flush()

    await db_session.execute(delete(FloorRow).where(FloorRow.pk == scene.floor.pk))
    await db_session.flush()

    for model in (UploadRow, UploadChunkRow, PipelineRunRow, DrawingRow):
        count = (await db_session.execute(select(func.count()).select_from(model))).scalar_one()
        assert count == 0, model.__tablename__


async def test_deleting_upload_cascades_to_chunks(db_session: AsyncSession) -> None:
    """Lịch dọn xoá dòng upload là đủ: khúc của nó đi theo FK CASCADE."""
    scene = await make_scene(db_session)
    upload = _upload(scene)
    db_session.add(upload)
    await db_session.flush()
    db_session.add(UploadChunkRow(upload_id=upload.id, chunk_index=0, size_bytes=1, sha256=SHA, object_key="k"))
    await db_session.flush()

    await db_session.execute(delete(UploadRow).where(UploadRow.id == upload.id))
    await db_session.flush()

    count = (await db_session.execute(select(func.count()).select_from(UploadChunkRow))).scalar_one()
    assert count == 0


# ---------------------------------------------------------------------------
# Factory và cấu hình
# ---------------------------------------------------------------------------


async def test_make_upload_derives_chunk_count_from_the_settings(db_session: AsyncSession) -> None:
    """`chunk_count` của factory theo đúng luật #5 `ceil(size / UPLOAD_CHUNK_BYTES)`."""
    scene = await make_scene(db_session)
    upload = await make_upload(db_session, project=scene.project, floor=scene.floor, size_bytes=1)
    assert upload.chunk_count == 1
    assert (upload.status, upload.declared_type) == ("receiving", "image/png")


async def test_make_upload_maps_unknown_extension_to_png(db_session: AsyncSession) -> None:
    """Tên tệp không có đuôi biết được vẫn dựng dòng hợp lệ (mặc định của factory là PNG)."""
    scene = await make_scene(db_session)
    upload = await make_upload(db_session, project=scene.project, floor=scene.floor, file_name="ban-ve")
    assert upload.declared_type == "image/png"


async def test_make_complete_upload_writes_every_chunk_and_the_original(
    db_session: AsyncSession,
    local_storage: LocalDiskStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lượt tải `complete` của factory có khúc thật trong kho và `original.pdf` đúng byte."""
    monkeypatch.setenv("UPLOAD_CHUNK_BYTES", "4")
    reset_drawings_settings_cache()
    try:
        scene = await make_scene(db_session)
        data = b"%PDF-1.7 xin chao"
        upload = await make_complete_upload(
            db_session, local_storage, project=scene.project, floor=scene.floor, data=data, file_name="ban-ve.pdf"
        )
    finally:
        monkeypatch.delenv("UPLOAD_CHUNK_BYTES")
        reset_drawings_settings_cache()

    assert (upload.status, upload.sniffed_kind) == ("complete", "pdf")
    assert upload.original_key is not None
    chunks = (
        (await db_session.execute(select(UploadChunkRow).where(UploadChunkRow.upload_id == upload.id))).scalars().all()
    )
    assert len(chunks) == upload.chunk_count == 5
    original = await local_storage.stat(upload.original_key)
    assert original is not None
    assert original.size == len(data)


async def test_make_complete_upload_refuses_empty_data(
    db_session: AsyncSession, local_storage: LocalDiskStorage
) -> None:
    """`declared_size_bytes > 0` là CHECK của bảng — factory chặn sớm với thông điệp rõ."""
    scene = await make_scene(db_session)
    with pytest.raises(ValueError, match="ít nhất một byte"):
        await make_complete_upload(db_session, local_storage, project=scene.project, floor=scene.floor, data=b"")


def test_drawings_settings_defaults_match_the_charter() -> None:
    """Bảy hạn mức của [5]; đổi giá trị ở đây là đổi hợp đồng với FE."""
    settings = get_drawings_settings()
    assert (settings.upload_max_bytes, settings.upload_chunk_bytes) == (104_857_600, 5_242_880)
    assert (settings.upload_init_dedupe_s, settings.upload_abandon_after_h) == (120, 24)
    assert settings.pipeline_requeue_after_s == 600
    assert (settings.drawings_init_rate_limit, settings.drawings_init_rate_window_s) == (60, 600)
