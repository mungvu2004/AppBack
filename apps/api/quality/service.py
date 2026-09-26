"""Nghiệp vụ #31 (bốn góc) và #32 (nắn nghiêng) của API chất lượng (B2-05b [6]).

Hai đường ghi dùng chung một khung: đọc sự thật DB → **nhả kết nối** (`db.rollback()`, K36) →
đọc storage và xử lý ảnh trong executor riêng (`processing`) → `put` trang mới → giao dịch
cuối khoá theo BE-00 §7 (`floors` → `uploads` → `drawings` → `quality_assessments`, mọi khoá
**trước** `start_run`), kiểm lại sự thật rồi mới đổi bản vẽ. Sự thật đã đổi thì rollback,
xoá object mới và trả lỗi: không object nào bị ghi đè, không lượt chạy nào thừa (J09).

Không có `send_task` ở đây: hàng đợi chỉ được chạm bởi `start_run` (K17). Mọi số liệu dùng
sau `rollback()` là bản chụp thường (`_State`), vì đối tượng ORM đã hết hạn.
"""

import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.drawings.drawings import current_drawing, new_page_key, upsert_drawing
from apps.api.drawings.runs import start_run
from apps.api.floors.lookup import get_floor
from apps.api.quality.assessments import AssessmentRow, load_assessment, read_view, save_assessment
from apps.api.quality.errors import QUALITY_DRAWING_CHANGED, QUALITY_LAYER_REVIEWED
from apps.api.quality.geometry import Ratios, corners_match, parse_homography, to_unrectified, validate_corner_ratios
from apps.api.quality.processing import ProcessedPage, process_corners, process_straighten
from apps.api.quality.schemas import QualityAssessmentOut, SetCornersIn
from apps.api.quality.settings import QualitySettings, get_quality_settings
from apps.api.spatial_read.documents import has_human_geometry
from packages.core.clock import Clock
from packages.core.error_codes import IMAGE_TOO_LARGE, NOT_FOUND
from packages.core.errors import AppError
from packages.db.models.drawings import PipelineRunRow, UploadRow
from packages.storage import keys
from packages.storage.port import ObjectStorage
from packages.vision.preprocess.types import Homography

_log: Final = logging.getLogger(__name__)

SKEW_CODE: Final = "SKEW_DETECTED"
"""Mã phát hiện nghiêng của B2-05a; #32 chỉ bỏ qua khi mã này vắng và góc dưới ngưỡng."""

Runner = Callable[[bytes, str], Awaitable[ProcessedPage]]
"""Xử lý ảnh của một đường ghi: nhận bytes nguồn và loại tệp, trả trang mới."""


@dataclass(frozen=True, slots=True)
class _State:
    """Sự thật của một tầng lúc đọc (bước 2); số thường để dùng được sau `rollback()`.

    `assessment` chỉ có khi còn khớp bản vẽ đang dùng (`drawing_id` và `pageKey`); dòng đo
    của bản vẽ đã bị thay là số cũ và bị bỏ.
    """

    project_id: str
    level_id: str
    floor_pk: int
    drawing_id: str
    page_key: str
    width_px: int
    height_px: int
    upload_id: str
    original_key: str
    sniffed_kind: str
    page_index: int
    assessment: AssessmentRow | None


@dataclass(frozen=True, slots=True)
class _Page:
    """Trang ứng với một tập góc: kích thước và homography (nguồn → trang) của nó."""

    width_px: int
    height_px: int
    homography: Homography


@dataclass(frozen=True, slots=True)
class _Job:
    """Một đường ghi đã lên kế hoạch: đọc trang nào, xử lý ra sao, ghi `corners`/`undo` gì."""

    current_page: bool
    run: Runner
    corners: Sequence[tuple[float, float]] | None
    undo: Mapping[str, Any] | None


async def _newer_upload_pending(db: AsyncSession, *, floor_pk: int, upload_id: str) -> bool:
    """Tầng có upload `complete` mới hơn upload của bản vẽ mà lượt mới nhất chưa `failed`.

    Lần tải mới đang xử lý thì #31/#32 không được thay lượt pipeline của nó; lần tải mới đã
    hỏng thì bản vẽ cũ vẫn sửa được ([6] bước 2).
    """
    created = select(UploadRow.created_at).where(UploadRow.id == upload_id).scalar_subquery()
    newer = (
        select(UploadRow.id)
        .where(UploadRow.floor_pk == floor_pk, UploadRow.status == "complete", UploadRow.created_at > created)
        .order_by(UploadRow.created_at.desc(), UploadRow.id.desc())
        .limit(1)
    )
    upload = (await db.execute(newer)).scalar_one_or_none()
    if upload is None:
        return False
    latest = (
        select(PipelineRunRow.status)
        .where(PipelineRunRow.upload_id == upload)
        .order_by(PipelineRunRow.created_at.desc(), PipelineRunRow.id.desc())
        .limit(1)
    )
    return (await db.execute(latest)).scalar_one_or_none() != "failed"


async def _check_editable(db: AsyncSession, *, floor_pk: int, upload_id: str) -> None:
    """Hai điều kiện chặn của bước 2: tầng đã duyệt (422) hoặc lần tải mới đang chạy (409)."""
    completed = select(PipelineRunRow.id).where(
        PipelineRunRow.upload_id == upload_id, PipelineRunRow.status == "completed"
    )
    if await has_human_geometry(db, floor_pk) and (await db.execute(completed.limit(1))).first() is not None:
        raise QUALITY_LAYER_REVIEWED.error()
    if await _newer_upload_pending(db, floor_pk=floor_pk, upload_id=upload_id):
        raise QUALITY_DRAWING_CHANGED.error()


async def _load_state(db: AsyncSession, *, project_id: str, level_id: str, locked: bool = False) -> _State:
    """Đọc và kiểm bước 2; `locked=True` (giao dịch cuối) khoá theo thứ tự BE-00 §7.

    Khoá `floors` → mọi `uploads` của tầng (chặn #7 chốt một lần tải mới chen vào) →
    `drawings` → `quality_assessments`. Tầng không có → 404 `floor`; chưa có bản vẽ → 404 `upload`.
    """
    floor = await get_floor(db, project_id=project_id, level_id=level_id, for_update=locked)
    if floor is None:
        raise NOT_FOUND.error(resource="floor")
    uploads = select(UploadRow).where(UploadRow.floor_pk == floor.pk)
    if locked:
        uploads = uploads.with_for_update()
    by_id = {row.id: row for row in (await db.execute(uploads)).scalars()}
    drawing = await current_drawing(db, floor.pk, for_update=locked)
    if drawing is None:
        raise NOT_FOUND.error(resource="upload")
    upload = by_id[drawing.upload_id]
    await _check_editable(db, floor_pk=floor.pk, upload_id=upload.id)
    row = await load_assessment(db, floor.pk, for_update=locked)
    fresh = row is not None and row.drawing_id == drawing.id and row.report["pageKey"] == drawing.page_key
    if upload.original_key is None or upload.sniffed_kind is None:
        raise ValueError(f"lượt tải {upload.id!r} đã complete mà thiếu tệp gốc")  # lỗi lược đồ, không phải dữ liệu vào
    return _State(
        project_id=project_id,
        level_id=level_id,
        floor_pk=floor.pk,
        drawing_id=drawing.id,
        page_key=drawing.page_key,
        width_px=drawing.width_px,
        height_px=drawing.height_px,
        upload_id=upload.id,
        original_key=upload.original_key,
        sniffed_kind=upload.sniffed_kind,
        page_index=upload.page_index,
        assessment=row if fresh else None,
    )


def _current_page(state: _State) -> _Page:
    """Trang đang dùng: homography đã lưu, hoặc ma trận đơn vị khi chưa có dòng đo."""
    if state.assessment is None:
        return _Page(state.width_px, state.height_px, Homography.identity(state.width_px, state.height_px))
    return _Page(state.width_px, state.height_px, parse_homography(state.assessment.homography))


def _undo_page(state: _State, ratios: Ratios, eps: float) -> _Page | None:
    """Trang **trước** khi bốn góc gần nhất được áp, nếu thân khớp `undo.corners` (client cũ hoàn tác)."""
    if state.assessment is None:
        return None
    undo = state.assessment.report["undo"]
    if undo is None or undo["corners"] is None or not corners_match(ratios, undo["corners"], eps):
        return None
    return _Page(undo["pageWidthPx"], undo["pageHeightPx"], parse_homography(undo["homography"]))


def _undo_of(state: _State) -> dict[str, Any]:
    """`undo` của lượt ghi mới: khung và homography của trang đang dùng, để hoàn tác lại được."""
    page = _current_page(state)
    frame = None if state.assessment is None else state.assessment.report["frame"]["corners"]
    return {
        "corners": frame,
        "pageWidthPx": page.width_px,
        "pageHeightPx": page.height_px,
        "homography": page.homography.to_json(),
    }


def _same_corners(state: _State, ratios: Ratios, eps: float) -> bool:
    """Góc (đã đổi sang trang chưa nắn) khớp góc người dùng đã áp → không có gì để làm."""
    applied = None if state.assessment is None else state.assessment.corners
    return applied is not None and corners_match(ratios, applied, eps)


def _skew_is_settled(state: _State, min_deg: float) -> bool:
    """Đã đo, không `SKEW_DETECTED` và `|skewDeg|` dưới ngưỡng → #32 không có gì để làm."""
    if state.assessment is None:
        return False
    report = state.assessment.report
    if any(finding["code"] == SKEW_CODE for finding in report["findings"]):
        return False
    return bool(abs(report["measurement"]["skewDeg"]) < min_deg)


async def _read_capped(storage: ObjectStorage, key: str, *, max_bytes: int) -> bytes:
    """Đọc cả object nhưng dừng khi vượt `max_bytes` (K13): quá trần → 422 `IMAGE_TOO_LARGE`."""
    buffer = bytearray()
    async for chunk in storage.open_read(key):
        buffer += chunk
        if len(buffer) > max_bytes:
            raise IMAGE_TOO_LARGE.error()
    return bytes(buffer)


async def _read_source(
    storage: ObjectStorage, state: _State, *, current_page: bool, max_bytes: int
) -> tuple[bytes, str]:
    """Bytes nguồn và loại tệp của việc xử lý.

    #32 đọc trang đang dùng (PNG). #31 đọc trang **chưa nắn**: `pages/{i}.png` nếu đã có
    (sau ML), không thì tệp gốc — nên góc luôn áp lên ảnh gốc, không nắn chồng.
    """
    if current_page:
        return await _read_capped(storage, state.page_key, max_bytes=max_bytes), "png"
    page = keys.upload_page(state.project_id, state.level_id, state.upload_id, state.page_index)
    if await storage.stat(page) is not None:
        return await _read_capped(storage, page, max_bytes=max_bytes), "png"
    return await _read_capped(storage, state.original_key, max_bytes=max_bytes), state.sniffed_kind


async def _commit_swap(
    db: AsyncSession, clock: Clock, state: _State, job: _Job, processed: ProcessedPage, new_key: str
) -> None:
    """Giao dịch cuối (bước 7): kiểm lại dưới khoá, `start_run` → `upsert_drawing` → `save_assessment`.

    Bản vẽ hay `page_key` đã khác lúc đọc, hoặc một hàm B2-04/D trả `None` (lượt bị thay), →
    409 `QUALITY_DRAWING_CHANGED`; người gọi rollback và xoá object mới.
    """
    fresh = await _load_state(db, project_id=state.project_id, level_id=state.level_id, locked=True)
    if (fresh.drawing_id, fresh.page_key) != (state.drawing_id, state.page_key):
        raise QUALITY_DRAWING_CHANGED.error()
    run = await start_run(db, upload_id=fresh.upload_id, clock=clock)
    drawing = await upsert_drawing(
        db,
        run_id=run.id,
        floor_pk=fresh.floor_pk,
        upload_id=fresh.upload_id,
        page_key=new_key,
        width_px=processed.width_px,
        height_px=processed.height_px,
        clock=clock,
    )
    saved = None
    if drawing is not None:
        saved = await save_assessment(
            db,
            run_id=run.id,
            floor_pk=fresh.floor_pk,
            drawing_id=drawing.id,
            page_key=new_key,
            width_px=processed.width_px,
            height_px=processed.height_px,
            report=processed.report,
            homography=processed.homography.to_json(),
            corners=job.corners,
            undo=job.undo,
            clock=clock,
        )
    if saved is None:
        raise QUALITY_DRAWING_CHANGED.error()
    await db.commit()


async def _discard_orphan(storage: ObjectStorage, key: str) -> None:
    """Xoá object trang của bên thua; lỗi kho chỉ được ghi log, **không** thay lỗi gốc.

    Chạy trong `finally` của một request đang thoát bằng 409/422: nếu `delete` ném thì lỗi kho
    sẽ đè lỗi thật và client nhận 503/500 thay vì mã có nghĩa. Chỉ bắt lỗi mà `ObjectStorage.delete`
    ném: `AppError` (kho local/S3 báo 503 khi đĩa đầy hay mất kết nối) và `OSError` (lỗi tệp local
    khác). Object sót lại do lịch dọn mồ côi 24 h của B2-04 nhặt.
    """
    try:
        await storage.delete(key)
    except (AppError, OSError) as exc:
        _log.warning("quality_orphan_delete_failed", extra={"object_key": key}, exc_info=exc)


async def _swap_page(
    db: AsyncSession, storage: ObjectStorage, clock: Clock, state: _State, job: _Job, settings: QualitySettings
) -> QualityAssessmentOut:
    """Bước 4-7 + dựng response: xử lý ngoài giao dịch, `put` trang mới, rồi đổi bản vẽ.

    Mọi đường thoát trước `commit` (lỗi hay 409) đều rollback và xoá object mới, nên không
    còn khoá nào bị giữ và không object mồ côi. Object đang được `page_key` trỏ tới không
    bao giờ bị ghi đè: khoá mới mỗi lần (`new_page_key`).
    """
    await db.rollback()  # K36: trả kết nối về pool trước khi đọc storage và xử lý ảnh
    max_bytes = settings.quality_page_max_bytes
    data, kind = await _read_source(storage, state, current_page=job.current_page, max_bytes=max_bytes)
    processed = await job.run(data, kind)
    new_key = new_page_key(
        project_id=state.project_id,
        level_id=state.level_id,
        upload_id=state.upload_id,
        page_index=state.page_index,
        clock=clock,
    )
    await storage.put(new_key, processed.png, content_type="image/png", max_bytes=max_bytes)
    committed = False
    try:
        await _commit_swap(db, clock, state, job, processed, new_key)
        committed = True
    finally:
        if not committed:
            await db.rollback()
            await _discard_orphan(storage, new_key)
    return await read_view(db, storage, project_id=state.project_id, level_id=state.level_id)


async def set_corners(
    db: AsyncSession,
    storage: ObjectStorage,
    *,
    project_id: str,
    level_id: str,
    body: SetCornersIn,
    clock: Clock,
) -> QualityAssessmentOut:
    """#31 — áp bốn góc người dùng chọn lên trang chưa nắn, ra trang mới và lượt pipeline mới.

    Góc trùng góc đã áp → 200 hiện trạng, không xử lý, không xếp hàng. Thân khớp
    `undo.corners` (client cũ hoàn tác) → đổi góc sang trang trước đó, nên không nắn chồng.
    """
    settings = get_quality_settings()
    ratios = validate_corner_ratios(
        [(corner.x_ratio, corner.y_ratio) for corner in body.corners],
        min_area=settings.quality_min_quad_area,
        eps=settings.quality_corner_eps,
    )
    state = await _load_state(db, project_id=project_id, level_id=level_id)
    page = _undo_page(state, ratios, settings.quality_corner_eps) or _current_page(state)
    unrectified = to_unrectified(
        ratios, page_width_px=page.width_px, page_height_px=page.height_px, homography=page.homography
    )
    if _same_corners(state, unrectified, settings.quality_corner_eps):
        return await read_view(db, storage, project_id=project_id, level_id=level_id)

    async def run(data: bytes, kind: str) -> ProcessedPage:
        """Nắn bytes nguồn theo góc đã đổi sang trang chưa nắn."""
        return await process_corners(data, kind=kind, page_index=state.page_index, corner_ratios=unrectified)

    job = _Job(current_page=False, run=run, corners=unrectified, undo=_undo_of(state))
    return await _swap_page(db, storage, clock, state, job, settings)


async def straighten(
    db: AsyncSession, storage: ObjectStorage, *, project_id: str, level_id: str, clock: Clock
) -> QualityAssessmentOut:
    """#32 — nắn nghiêng trang đang dùng; đã thẳng thì 200 hiện trạng, không lượt mới.

    `corners` giữ nguyên (góc người dùng đã chọn vẫn dựng lại được), `undo` bỏ: nắn không có
    "hoàn tác" qua #31.
    """
    settings = get_quality_settings()
    state = await _load_state(db, project_id=project_id, level_id=level_id)
    if _skew_is_settled(state, settings.quality_skew_min_deg):
        return await read_view(db, storage, project_id=project_id, level_id=level_id)
    old = _current_page(state).homography

    async def run(data: bytes, kind: str) -> ProcessedPage:
        """Dựng thẳng trang đang dùng (`kind` luôn là PNG nên không dùng)."""
        return await process_straighten(data, old_homography=old)

    kept = None if state.assessment is None else state.assessment.corners
    job = _Job(current_page=True, run=run, corners=kept, undo=None)
    return await _swap_page(db, storage, clock, state, job, settings)
