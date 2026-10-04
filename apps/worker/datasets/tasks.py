"""Task `default.datasets.build_version`: dựng một phiên bản dataset từ tầng đã duyệt (B6-02 [6] "Task").

Ba bất biến giữ cho một bản `ready` không bao giờ bị hỏng bởi một lượt chạy muộn:

1. **Khoá rào trước mỗi lượt ghi.** `SafeLock.hold` tự gia hạn, nhưng một lượt dựng dài hơn
   TTL nhiều lần nên writer gọi lại `renew` trước **mỗi** `put` (`SampleWriter(before_put=…)`).
   `renew` trả `False` → `_StoppedError`: dừng ngay, **không** ghi thêm, **không** `finish_version`,
   **không** `delete_prefix` — chủ khoá mới đang dựng lại cùng tiền tố.
2. **Session ngắn, không giữ khi chạm storage** (K22, K36): mỗi bước mở session riêng và đóng
   trước lượt `put`/`stat`/`open_read` kế tiếp; ảnh trang chảy thẳng từ `open_read` vào `put`,
   không qua một `bytes` nào của cả dataset.
3. **Chỉ `versions.py` ghi trạng thái**, và cả bốn hàm ở đó lọc `status = 'building'`, nên mọi
   chuyển trạng thái muộn là no-op thay vì sửa một bản đã chốt.

Tầng không dựng được mẫu bị **bỏ theo lý do** (đếm, log một dòng cuối lượt) chứ không làm hỏng
cả lượt: một dự án thiếu tỉ lệ không được phép chặn 1.999 tầng còn lại.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import AsyncGenerator, AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Final, Literal

from sqlalchemy import Row, Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.admin_ml_datasets.errors import DATASET_EMPTY, DATASET_FAMILY_UNSUPPORTED, DATASET_TOO_LARGE
from apps.api.admin_ml_datasets.settings import get_ml_datasets_settings
from apps.api.admin_ml_datasets.versions import fail_version, finish_version, touch_version
from apps.api.drawings.drawings import current_drawing
from apps.api.spatial_read.codec import DocumentCorruptError
from apps.api.spatial_read.documents import load_document
from apps.worker.datasets.render import object_boxes, wall_mask
from apps.worker.datasets.writer import SampleWriter
from packages.core.clock import Clock, SystemClock
from packages.db.engine import session_scope, worker_sessionmaker
from packages.db.models.admin_ml_datasets import DatasetRow, DatasetVersionRow
from packages.db.models.drawings import PipelineRunRow
from packages.db.models.floors import FloorRow
from packages.db.models.projects import Project
from packages.db.models.spatial import FloorChangeLogRow, FloorDocumentRow
from packages.messaging import (
    LockBusy,
    LockLost,
    PermanentError,
    SafeLock,
    define_task,
    runner,
    safe_redis,
)
from packages.messaging.payloads.datasets import BUILD_VERSION_TASK, BuildDatasetVersionPayload
from packages.ml_contracts.artifacts import ObjectsResult, encode_mask, objects_to_json, read_png_header
from packages.ml_contracts.datasets import DATASET_MAX_BYTES, SampleMeta, split_for
from packages.storage.keys import dataset_version_prefix
from packages.storage.port import ObjectStorage
from packages.vision.preprocess.sniff import sniff_kind

if TYPE_CHECKING:
    from packages.domain.spatial.model import Furniture, Opening, SpatialLayer, Wall

_log: Final = logging.getLogger(__name__)

LOCK_TTL_MS: Final = 60_000
LOCK_RENEW_MS: Final = 20_000
"""Gia hạn ở một phần ba TTL: mất một lượt gia hạn vì Redis chậm vẫn chưa mất khoá."""

FLOOR_BATCH: Final = 200
TOUCH_EVERY_SAMPLES: Final = 50
TOUCH_EVERY: Final = timedelta(seconds=60)
BUILD_SOURCE: Final = "approvedFloors"
WALL_FAMILY: Final = "wallSegmentation"
UNSUPPORTED_FAMILY: Final = "dimensionReading"
LIVE_RUN_STATUSES: Final = ("pending", "running")
USER_PREFIX: Final = "usr_"

SkipReason = Literal[
    "no_document",
    "no_drawing",
    "no_scale",
    "document_corrupt",
    "pipeline_pending",
    "drawing_after_review",
    "no_labels",
    "labels_unapproved",
    "no_image",
    "image_mismatch",
    "duplicate_image",
]
"""Lý do bỏ một tầng — khoá của bộ đếm in ra log cuối lượt ([6] bước 5, 6)."""


class _StoppedError(Exception):
    """Lượt này phải dừng im lặng: khoá đã mất, hay bản không còn `building`.

    Khác `PermanentError`: không có ai để báo hỏng — bản đã thuộc về một lượt khác, và
    `on_failed` chạy ở đây sẽ đánh `failed` một bản người khác đang dựng hợp lệ.
    """


@dataclass(frozen=True, slots=True)
class _Candidate:
    """Một tầng đã qua hết cửa lọc: đủ nhãn đạt, có bản vẽ và tỉ lệ, sẵn sàng thành mẫu."""

    floor_pk: int
    project_id: str
    level_id: str
    layer: SpatialLayer
    mm_per_px: float
    page_key: str
    width_px: int
    height_px: int


@dataclass(frozen=True, slots=True)
class _Fence:
    """Rào khoá của lượt dựng: writer gọi `check` trước mỗi `put`."""

    lock: SafeLock
    token: int

    async def check(self) -> None:
        """Khoá còn là của lượt này thì trả về; mất rồi → `_StoppedError`."""
        if not await self.lock.renew(self.token):
            raise _StoppedError("lock_lost")


class _Beat:
    """Nhịp sống `touch_version`: mỗi `TOUCH_EVERY_SAMPLES` mẫu hay `TOUCH_EVERY`, cái nào tới trước.

    Nhịp thưa hơn cả hai mốc thì lịch `sweep_dataset_version_builds` sẽ tưởng lượt này treo và
    đóng bản đang chạy; nhịp mỗi mẫu thì một lượt 2.000 tầng tốn 2.000 vòng DB không mua gì.
    """

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._at = clock.now()
        self._samples = 0

    async def tick(self, sessionmaker: async_sessionmaker[AsyncSession], *, version_id: str, samples: int) -> None:
        """Ghi nhịp nếu tới hạn; bản không còn `building` → `_StoppedError` (dừng như mất khoá, bước 7)."""
        now = self._clock.now()
        if samples - self._samples < TOUCH_EVERY_SAMPLES and now - self._at < TOUCH_EVERY:
            return
        self._at, self._samples = now, samples
        async with session_scope(sessionmaker) as db:
            alive = await touch_version(db, version_id=version_id, clock=self._clock)
        if not alive:
            raise _StoppedError("not_building")


def version_prefix(version_id: str) -> str:
    """Tiền tố object của một phiên bản — cùng chuỗi `SampleWriter` dựng khoá mẫu dưới đó (`keys`)."""
    return dataset_version_prefix(version_id)


def _labels(layer: SpatialLayer, family: str) -> tuple[Wall | Opening | Furniture, ...]:
    """Thực thể nhãn của họ ([6] bước 5): tường + ô mở `door`, hay ô mở + đồ đạc."""
    if family == WALL_FAMILY:
        return (*layer.walls, *(opening for opening in layer.openings if opening.kind == "door"))
    return (*layer.openings, *layer.furniture)


def _label_skip(layer: SpatialLayer, family: str) -> SkipReason | None:
    """Lý do bỏ theo nhãn, `None` khi tầng có nhãn và **mọi** nhãn đã đạt.

    "Đạt" = người tự vẽ (`source == "human"`) hoặc người đã duyệt (`reviewed`); một ô mở AI
    chưa duyệt làm cả tầng bị bỏ, vì mẫu huấn luyện thiếu một cửa còn tệ hơn không có mẫu.
    """
    labels = _labels(layer, family)
    if not labels:
        return "no_labels"
    approved = all(label.source == "human" or label.reviewed for label in labels)
    return None if approved else "labels_unapproved"


def _floor_page(after_pk: int, project_ids: Sequence[str] | None) -> Select[tuple[int, str, str]]:
    """Một lô ≤ `FLOOR_BATCH` tầng ứng viên theo `floors.pk` tăng ([6] bước 4).

    Phân trang theo khoá (`pk > after_pk`) chứ không `OFFSET`: lô sau không phải quét lại lô
    trước, và tầng mới chèn giữa lượt không làm lệch cửa sổ.
    """
    stmt = (
        select(FloorRow.pk, FloorRow.project_id, FloorRow.level_id)
        .join(Project, Project.id == FloorRow.project_id)
        .join(FloorDocumentRow, FloorDocumentRow.floor_pk == FloorRow.pk)
        .where(FloorRow.deleted_at.is_(None), Project.deleted_at.is_(None), FloorRow.pk > after_pk)
        .order_by(FloorRow.pk)
        .limit(FLOOR_BATCH)
    )
    return stmt if project_ids is None else stmt.where(FloorRow.project_id.in_(project_ids))


async def _pipeline_pending(db: AsyncSession, upload_id: str) -> bool:
    """Lượt tải của bản vẽ hiện tại còn lượt `pipeline_runs` chưa kết thúc.

    Ảnh trang có thể bị lượt đang chạy thay ngay sau khi ta đọc, nên nhãn hiện có chưa chắc
    thuộc ảnh này — bỏ tầng chứ không ghi một mẫu có thể lệch (`pipeline_pending`).
    """
    stmt = (
        select(PipelineRunRow.id)
        .where(PipelineRunRow.upload_id == upload_id, PipelineRunRow.status.in_(LIVE_RUN_STATUSES))
        .limit(1)
    )
    return (await db.execute(stmt)).first() is not None


async def _reviewed_after(db: AsyncSession, floor_pk: int, uploaded_at: datetime) -> bool:
    """Có lượt ghi của **người** (`usr_…`) từ lúc ảnh này tải lên trở đi.

    Không có dòng nào như thế nghĩa là nhãn đang có được duyệt **trước** bản vẽ hiện tại:
    `drawing_after_review` ([6] bước 5). `system:pipeline` không tính — đó là AI ghi.
    """
    stmt = (
        select(FloorChangeLogRow.id)
        .where(
            FloorChangeLogRow.floor_pk == floor_pk,
            FloorChangeLogRow.changed_by.startswith(USER_PREFIX),
            FloorChangeLogRow.changed_at >= uploaded_at,
        )
        .limit(1)
    )
    return (await db.execute(stmt)).first() is not None


async def _read_floor(db: AsyncSession, floor: Row[tuple[int, str, str]], family: str) -> _Candidate | SkipReason:
    """Đọc tài liệu + bản vẽ của một tầng trong **một** session ngắn; trả ứng viên hay lý do bỏ."""
    try:
        document = await load_document(db, floor.pk)
    except DocumentCorruptError:
        _log.warning("dataset_floor_corrupt", extra={"floor_pk": floor.pk})
        return "document_corrupt"
    if document is None:
        return "no_document"
    drawing = await current_drawing(db, floor.pk)
    if drawing is None:
        return "no_drawing"
    if document.scale_mm_per_px is None:
        return "no_scale"
    if await _pipeline_pending(db, drawing.upload_id):
        return "pipeline_pending"
    if not await _reviewed_after(db, floor.pk, drawing.uploaded_at):
        return "drawing_after_review"
    label_skip = _label_skip(document.layer, family)
    if label_skip is not None:
        return label_skip
    return _Candidate(
        floor_pk=floor.pk,
        project_id=floor.project_id,
        level_id=floor.level_id,
        layer=document.layer,
        mm_per_px=float(document.scale_mm_per_px),
        page_key=drawing.page_key,
        width_px=drawing.width_px,
        height_px=drawing.height_px,
    )


def _ihdr_matches(head: bytes, candidate: _Candidate) -> bool:
    """IHDR của khúc đầu đúng khổ dòng `drawings`; PNG cụt hay IHDR lạ → `False`.

    Khổ lệch nghĩa là ảnh trong kho không phải ảnh mà nhãn được vẽ trên — hộp px sẽ sai.
    """
    try:
        header = read_png_header(head)
    except ValueError:
        return False
    return header.width == candidate.width_px and header.height == candidate.height_px


async def _chain(head: bytes, rest: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    """Khúc đầu đã đọc để kiểm, rồi phần còn lại: `put` thấy nguyên tệp, RAM chỉ giữ một khúc."""
    yield head
    async for chunk in rest:
        yield chunk


async def _close(reader: AsyncIterator[bytes]) -> None:
    """Đóng bộ duyệt bỏ giữa đường — kho local trả bộ sinh đang giữ một tệp mở."""
    if isinstance(reader, AsyncGenerator):
        await reader.aclose()


async def _page_stream(storage: ObjectStorage, candidate: _Candidate) -> AsyncIterator[bytes] | None:
    """Luồng byte của trang, đã kiểm `sniff_kind == "png"` và IHDR; sai → `None` (bỏ tầng)."""
    reader = storage.open_read(candidate.page_key)
    head = await anext(reader, b"")
    if sniff_kind(head) != "png" or not _ihdr_matches(head, candidate):
        await _close(reader)
        return None
    return _chain(head, reader)


def _label_files(candidate: _Candidate, family: str) -> tuple[bytes | None, bytes | None]:
    """(`walls.png`, `objects.json`) của họ — đúng một trong hai có mặt ([6] bước 6)."""
    if family == WALL_FAMILY:
        mask = wall_mask(
            candidate.layer.walls,
            width_px=candidate.width_px,
            height_px=candidate.height_px,
            mm_per_px=candidate.mm_per_px,
            openings=candidate.layer.openings,
        )
        return encode_mask(mask), None
    boxes = object_boxes(
        candidate.layer,
        width_px=candidate.width_px,
        height_px=candidate.height_px,
        mm_per_px=candidate.mm_per_px,
    )
    return None, objects_to_json(ObjectsResult(detections=boxes))


async def _write_sample(
    writer: SampleWriter, candidate: _Candidate, *, family: str, image: AsyncIterator[bytes]
) -> None:
    """Một mẫu: `split` theo **dự án** (M06), `sample_id = {project}_{level}`, nhãn theo họ."""
    sample_id = f"{candidate.project_id}_{candidate.level_id}"
    walls, objects = _label_files(candidate, family)
    meta = SampleMeta(
        sample_id=sample_id,
        group_key=candidate.project_id,
        width_px=candidate.width_px,
        height_px=candidate.height_px,
        mm_per_px=candidate.mm_per_px,
        source=BUILD_SOURCE,
    )
    await writer.add_sample(
        split=split_for(candidate.project_id),
        sample_id=sample_id,
        image=image,
        walls=walls,
        objects=objects,
        meta=meta,
    )


async def _add_floor(
    sessionmaker: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
    writer: SampleWriter,
    *,
    floor: Row[tuple[int, str, str]],
    family: str,
    seen: dict[str, int],
) -> SkipReason | None:
    """Ghi mẫu của một tầng; trả lý do bỏ, hay `None` khi đã ghi.

    Session đóng **trước** lượt `stat`/`open_read`/`put` đầu tiên (K22, K36). Trùng ảnh nhận
    theo `stat(page_key).sha256`: tầng duyệt theo `floors.pk` tăng nên bản giữ lại luôn là
    `floors.pk` nhỏ nhất, không phải "bản gặp sau đè bản gặp trước".
    """
    async with sessionmaker() as db:
        found = await _read_floor(db, floor, family)
    if isinstance(found, str):
        return found
    info = await storage.stat(found.page_key)
    if info is None:
        return "no_image"
    if info.sha256 in seen:
        return "duplicate_image"
    stream = await _page_stream(storage, found)
    if stream is None:
        return "image_mismatch"
    await _write_sample(writer, found, family=family, image=stream)
    seen[info.sha256] = found.floor_pk
    return None


async def _write_samples(
    sessionmaker: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
    clock: Clock,
    writer: SampleWriter,
    *,
    version_id: str,
    family: str,
    project_ids: Sequence[str] | None,
) -> int:
    """Duyệt mọi tầng ứng viên theo lô và ghi mẫu; trả số mẫu đã ghi.

    Vượt `DATASET_MAX_SAMPLES` → `DATASET_TOO_LARGE` ngay ở mẫu vượt trần, không đợi hết vòng:
    một dataset quá to càng ghi thêm càng tốn kho rồi cũng bị xoá.
    """
    max_samples = get_ml_datasets_settings().dataset_max_samples
    skipped: Counter[str] = Counter()
    seen: dict[str, int] = {}
    beat = _Beat(clock)
    samples = 0
    after_pk = 0
    while True:
        async with sessionmaker() as db:
            floors = (await db.execute(_floor_page(after_pk, project_ids))).all()
        if not floors:
            break
        after_pk = floors[-1].pk
        for floor in floors:
            reason = await _add_floor(sessionmaker, storage, writer, floor=floor, family=family, seen=seen)
            if reason is not None:
                skipped[reason] += 1
                continue
            samples += 1
            if samples > max_samples:
                raise PermanentError(DATASET_TOO_LARGE)
            await beat.tick(sessionmaker, version_id=version_id, samples=samples)
    _log.info("dataset_build_scan", extra={"version_id": version_id, "samples": samples, "skipped": dict(skipped)})
    return samples


async def _claim(
    sessionmaker: async_sessionmaker[AsyncSession], clock: Clock, *, version_id: str
) -> tuple[str, list[str] | None] | None:
    """Nhận lượt dựng: bản còn `building` → ghi `build_started_at`, trả `(họ, project_ids)`.

    `None` khi bản đã `ready`/`failed` hay không còn (giao lặp, K18) — lượt này không làm gì.
    `FOR UPDATE OF dataset_versions` giữ hai lượt cùng id nối đuôi nhau ngay cả khi khoá Redis
    bị mất; session đóng trước bất kỳ lượt chạm storage nào (bước 2).
    """
    stmt = (
        select(DatasetVersionRow.status, DatasetVersionRow.project_ids, DatasetRow.family)
        .join(DatasetRow, DatasetRow.id == DatasetVersionRow.dataset_id)
        .where(DatasetVersionRow.id == version_id)
        .with_for_update(of=DatasetVersionRow)
    )
    async with session_scope(sessionmaker) as db:
        row = (await db.execute(stmt)).first()
        if row is None or row.status != "building":
            return None
        now = clock.now()
        await db.execute(
            update(DatasetVersionRow)
            .where(DatasetVersionRow.id == version_id)
            .values(build_started_at=now, updated_at=now)
        )
        return row.family, row.project_ids


async def _finish(
    sessionmaker: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
    clock: Clock,
    *,
    version_id: str,
    manifest: str,
    counts: Mapping[str, int],
) -> None:
    """Chốt `ready` ([6] bước 9); `False` → đọc lại trạng thái, chỉ xoá tiền tố khi bản đã `failed`.

    Không xoá khi bản đã `ready`: đó là một lượt khác đã dựng xong và object dưới tiền tố là
    của nó. Đọc lại chứ không đoán, vì "không còn `building`" có hai nghĩa rất khác nhau.
    """
    async with session_scope(sessionmaker) as db:
        done = await finish_version(
            db, version_id=version_id, manifest_sha256=manifest, split_counts=counts, clock=clock
        )
    if done:
        return
    async with sessionmaker() as db:
        stmt = select(DatasetVersionRow.status).where(DatasetVersionRow.id == version_id)
        status = (await db.execute(stmt)).scalar_one_or_none()
    _log.warning("dataset_build_finish_skipped", extra={"version_id": version_id, "status": status})
    if status == "failed":
        await storage.delete_prefix(version_prefix(version_id))


async def _build_held(
    sessionmaker: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
    clock: Clock,
    *,
    version_id: str,
    fence: _Fence,
    sample_max_bytes: int,
) -> None:
    """Thân lượt dựng, chạy khi đã giữ khoá: bước 2-9 của [6]."""
    claim = await _claim(sessionmaker, clock, version_id=version_id)
    if claim is None:
        _log.info("dataset_build_not_building", extra={"version_id": version_id})
        return
    family, project_ids = claim
    if family == UNSUPPORTED_FAMILY:
        raise PermanentError(DATASET_FAMILY_UNSUPPORTED)
    # Dọn lượt chết giữa chừng trước khi ghi: manifest chỉ kể object của lượt này, nên tệp mẫu
    # sót lại của lượt trước sẽ là rác không dòng nào tham chiếu (bước 2).
    #
    # Rào khoá **trước** lượt dọn (NO-273): `_claim` mở và đóng một session, nên giữa nó và dòng
    # dưới có một khe thời gian thật. Mất khoá trong khe đó nghĩa là một lượt khác đã nhận cùng
    # phiên bản và có thể đã ghi object; `delete_prefix` khi ấy xoá **của nó**. Đây đúng là bất
    # biến số 1 của module: mất khoá → không ghi, không finish, **không** `delete_prefix`.
    await fence.check()
    await storage.delete_prefix(version_prefix(version_id))
    writer = SampleWriter(storage, version_id, max_bytes=sample_max_bytes, before_put=fence.check)
    samples = await _write_samples(
        sessionmaker, storage, clock, writer, version_id=version_id, family=family, project_ids=project_ids
    )
    if samples == 0:
        raise PermanentError(DATASET_EMPTY)
    manifest, counts = await writer.finish()
    await fence.check()
    await _finish(sessionmaker, storage, clock, version_id=version_id, manifest=manifest, counts=counts)


async def run_build_dataset_version(
    sessionmaker: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
    clock: Clock,
    *,
    version_id: str,
    sample_max_bytes: int = DATASET_MAX_BYTES,
) -> None:
    """Một lượt dựng đầy đủ dưới khoá `datasets:build:{dsv}` (tài nguyên do người gọi truyền).

    Khoá đang bị giữ (`LockBusy`, giao lặp J06) hay mất giữa lượt (`LockLost`, `_StoppedError`) chỉ
    ghi log rồi trả về: **không** ném, vì `on_failed` khi đó sẽ đánh `failed` một bản mà lượt
    khác đang dựng hợp lệ. Lỗi thật của lượt (`PermanentError`) vẫn nổi lên cho `define_task`.

    `sample_max_bytes` chỉ để test hạ trần dataset xuống vài trăm byte; đường thật luôn dùng
    `DATASET_MAX_BYTES` của `ml_contracts` (một trần, một nguồn).
    """
    lock = SafeLock(safe_redis(), f"datasets:build:{version_id}", ttl_ms=LOCK_TTL_MS)
    try:
        async with lock.hold(LOCK_RENEW_MS) as token:
            await _build_held(
                sessionmaker,
                storage,
                clock,
                version_id=version_id,
                fence=_Fence(lock, token),
                sample_max_bytes=sample_max_bytes,
            )
    except LockBusy:
        _log.info("dataset_build_busy", extra={"version_id": version_id})
    except (LockLost, _StoppedError) as exc:
        _log.warning("dataset_build_stopped", extra={"version_id": version_id, "reason": type(exc).__name__})


async def run_fail_dataset_version(
    sessionmaker: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
    clock: Clock,
    *,
    version_id: str,
    code: str,
) -> None:
    """Chốt `failed` rồi xoá tiền tố — xoá **sau** commit (`on_failed`, [6]).

    `fail_version` trả `False` (bản đã `ready`, hay một lượt khác đã chốt `failed`) → không xoá
    gì: tiền tố của một bản `ready` không bao giờ bị lượt hỏng của quá khứ dọn mất.
    """
    async with session_scope(sessionmaker) as db:
        failed = await fail_version(db, version_id=version_id, failure_code=code, clock=clock)
    if failed:
        await storage.delete_prefix(version_prefix(version_id))


def open_storage(clock: Clock) -> ObjectStorage:
    """Kho thật của tiến trình worker; `None` cho `CoreSettings` vì worker không ký URL (NO-085).

    `create_storage` nhập trễ: `minio` là phụ thuộc nặng mà mọi lượt dò module `apps.worker.*`
    sẽ phải nạp nếu nhập ở đầu file (khuôn `apps/api/library/assets.py`).
    """
    from packages.storage.factory import create_storage
    from packages.storage.settings import get_storage_settings

    return create_storage(get_storage_settings(), None, clock)


async def _fail_with_process_resources(version_id: str, code: str) -> None:
    """Chốt `failed` bằng tài nguyên thật của tiến trình, dựng **trong** vòng sự kiện.

    `worker_sessionmaker()` gọi `asyncio.get_running_loop()` để gắn engine vào đúng vòng sự kiện,
    nên nó không dựng được ở ngoài `runner().run(...)` — gọi ở đó ném `RuntimeError`.
    """
    clock = SystemClock()
    await run_fail_dataset_version(worker_sessionmaker(), open_storage(clock), clock, version_id=version_id, code=code)


def _on_build_failed(payload: BuildDatasetVersionPayload, code: str) -> None:
    """`on_failed`: đánh `failed` rồi dọn tiền tố, trên vòng sự kiện dùng chung của tiến trình.

    `define_task` gọi `on_failed` đồng bộ, nên phải qua `runner()` — cùng vòng sự kiện đã tạo
    engine asyncpg và client Redis, không `asyncio.run` riêng (BE-00 §7).
    """
    _log.error("dataset_build_failed", extra={"version_id": payload.dataset_version_id, "code": code})
    runner().run(_fail_with_process_resources(payload.dataset_version_id, code))


@define_task(name=BUILD_VERSION_TASK, payload=BuildDatasetVersionPayload, on_failed=_on_build_failed)
async def build_dataset_version(payload: BuildDatasetVersionPayload) -> None:
    """Hàm task mỏng: dựng tài nguyên thật rồi gọi lõi (khuôn `apps/api/auth_recovery/jobs.py`)."""
    clock = SystemClock()
    await run_build_dataset_version(
        worker_sessionmaker(), open_storage(clock), clock, version_id=payload.dataset_version_id
    )
