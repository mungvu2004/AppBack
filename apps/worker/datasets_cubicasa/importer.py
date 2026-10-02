"""Lệnh nhập CubiCasa5K: nguồn → phiên bản dataset bất biến, qua đúng các hàm ghi của B6-02 (B6-02b [6]).

Ba kết cục, ba mã thoát ([2]): `ready` (0); `failed` (1) — bản đã tạo rồi chốt hỏng bằng
`fail_version`, tiền tố đã xoá; `refused` (2) — hỏng **trước** khi tạo bản, không ghi gì.
"""

import asyncio
import logging
import shutil
import tempfile
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Final, Literal

from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.exc import TimeoutError as SATimeoutError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.admin_ml_datasets.errors import (
    DATASET_BUILD_IN_PROGRESS,
    DATASET_EMPTY,
    DATASET_FAMILY_UNSUPPORTED,
    DATASET_TOO_LARGE,
)
from apps.api.admin_ml_datasets.versions import fail_version, finish_version, start_version, touch_version
from apps.worker.datasets.tasks import UNSUPPORTED_FAMILY, WALL_FAMILY, version_prefix
from apps.worker.datasets.writer import SampleWriter
from apps.worker.datasets_cubicasa.archive import (
    FileTooLargeError,
    SampleDir,
    UnsafeArchiveError,
    UnsafePathError,
    discover_samples,
    is_zip,
    read_regular,
    safe_extract,
)
from apps.worker.datasets_cubicasa.convert import (
    ImageChoice,
    boxes_from_labels,
    choose_image,
    ink_ratio,
    wall_mask_from_polygons,
)
from apps.worker.datasets_cubicasa.settings import CubiCasaSettings
from apps.worker.datasets_cubicasa.svg import SvgLabels, SvgRejectedError, parse_model_svg
from packages.core.clock import Clock
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.core.errors import AppError
from packages.core.ids import is_id
from packages.db.engine import session_scope
from packages.db.errors import translate_db_error
from packages.db.models.admin_ml_datasets import DatasetRow, DatasetVersionRow
from packages.messaging import PermanentError
from packages.ml_contracts.artifacts import ObjectsResult, encode_mask, objects_to_json, read_png_header
from packages.ml_contracts.datasets import SampleMeta, split_for
from packages.storage.port import ObjectStorage
from packages.vision.preprocess.errors import VisionError
from packages.vision.preprocess.raster import encode_png, load_raster
from packages.vision.preprocess.types import RgbImage

SkipReason = Literal[
    "unsafe_path",
    "bad_id",
    "duplicate_id",
    "svg_rejected",
    "svg_invalid",
    "too_many_labels",
    "no_image",
    "image_invalid",
    "no_labels",
]
"""Lý do bỏ một mẫu — khoá bộ đếm in trong báo cáo. `no_image`: thiếu `F1_scaled.png` (phương án 1)."""

Outcome = Literal["ready", "failed", "refused"]

EXIT_CODES: Final[Mapping[Outcome, int]] = {"ready": 0, "failed": 1, "refused": 2}


@dataclass(frozen=True, slots=True)
class ImportReport:
    """Kết quả một lượt nhập: đủ để lệnh in báo cáo và chọn mã thoát (B6-02b [2]).

    `code`: mã từ chối (`refused`) hay `failureCode` (`failed`), `None` khi `ready`; `reason`
    chỉ có với `ARCHIVE_UNSAFE`. Các bảng số đếm trên mọi mẫu đã dò (kể cả mẫu bị bỏ);
    `ink_ratios` khoá theo subset; `fits` khoá `"<subset>.x"` và `"<subset>.y"` — hai chiều
    là hai phân bố khác nhau (ảnh thật co không đều), trộn vào một dãy thì trung vị vô nghĩa.
    """

    outcome: Outcome
    code: str | None = None
    reason: str | None = None
    version_id: str | None = None
    split_counts: Mapping[str, int] = field(default_factory=dict)
    skipped: Mapping[str, int] = field(default_factory=dict)
    branches: Mapping[str, int] = field(default_factory=dict)
    ink_ratios: Mapping[str, tuple[float, ...]] = field(default_factory=dict)
    fits: Mapping[str, tuple[float, ...]] = field(default_factory=dict)
    unknown_fixtures: tuple[tuple[str, int], ...] = ()

    @property
    def exit_code(self) -> int:
        """Mã thoát của lệnh theo kết cục: 0 `ready`, 1 `failed`, 2 `refused`."""
        return EXIT_CODES[self.outcome]


_log: Final = logging.getLogger(__name__)

SOURCE: Final = "cubicasa5k"
CREATED_BY: Final = "cli:datasets_cubicasa"
DATASET_NOT_FOUND: Final = "DATASET_NOT_FOUND"
ARCHIVE_UNSAFE: Final = "ARCHIVE_UNSAFE"
SOURCE_EMPTY: Final = "SOURCE_EMPTY"
SOURCE_INVALID: Final = "SOURCE_INVALID"
SOURCE_READ_FAILED: Final = "SOURCE_READ_FAILED"

SVG_NAME: Final = "model.svg"
IMAGE_NAME: Final = "F1_scaled.png"
TOUCH_EVERY_SAMPLES: Final = 50
TOUCH_EVERY: Final = timedelta(seconds=60)
UNKNOWN_FIXTURES_TOP: Final = 20


class _SourceReadError(RuntimeError):
    """`OSError` khi đọc tệp nguồn, bọc lại ngay trong `_convert_sample`.

    Bọc vì `OSError` của kho object (`storage.put`) phải nổi lên nguyên dạng (R-16): chỉ lỗi
    đọc **nguồn** mới là `SOURCE_READ_FAILED`, nên hai đường không được dùng chung một lớp.
    """


@dataclass(frozen=True, slots=True)
class _Converted:
    """Một mẫu đã đổi xong trong luồng phụ: byte sẵn sàng ghi, kèm số đo để báo cáo."""

    sample: SampleDir
    image: bytes
    walls: bytes | None
    objects: bytes | None
    width_px: int
    height_px: int
    branch: str
    fit_x: float
    fit_y: float
    ink: float | None
    unknown: Mapping[str, int]


@dataclass(slots=True)
class _Stats:
    """Số đếm cộng dồn của một lượt — đủ dựng `ImportReport` ở cả ba kết cục.

    `skipped` khởi tạo từ bộ đếm của `discover_samples` rồi cộng thêm lý do từng mẫu, nên báo
    cáo kể cả mẫu bị loại lúc dò (`bad_id`, `duplicate_id`, `unsafe_path`).
    """

    skipped: Counter[str]
    written: int = 0
    branches: Counter[str] = field(default_factory=Counter)
    unknown: Counter[str] = field(default_factory=Counter)
    ink: dict[str, list[float]] = field(default_factory=dict)
    fit: dict[str, list[float]] = field(default_factory=dict)

    def record(self, converted: _Converted) -> None:
        """Cộng nhánh, tên đồ lạ, `ink_ratio` và `fit` của một mẫu **đã ghi**, theo subset.

        `fit` vào hai dãy riêng (`.x`, `.y`) vì khổ ảnh / khổ `viewBox` của dữ liệu thật co
        không đều: một dãy trộn hai chiều thì min/p50/max không nói lên chiều nào lệch.
        """
        self.branches[converted.branch] += 1
        self.unknown.update(converted.unknown)
        subset = converted.sample.subset
        if converted.ink is not None:
            self.ink.setdefault(subset, []).append(converted.ink)
        self.fit.setdefault(f"{subset}.x", []).append(converted.fit_x)
        self.fit.setdefault(f"{subset}.y", []).append(converted.fit_y)

    def report(
        self,
        outcome: Outcome,
        *,
        code: str | None = None,
        version_id: str | None = None,
        split_counts: Mapping[str, int] | None = None,
    ) -> ImportReport:
        """Chốt báo cáo; `unknown_fixtures` chỉ giữ 20 tên nhiều nhất (phần đuôi là nhiễu)."""
        return ImportReport(
            outcome=outcome,
            code=code,
            version_id=version_id,
            split_counts=dict(split_counts or {}),
            skipped=dict(self.skipped),
            branches=dict(self.branches),
            ink_ratios={subset: tuple(values) for subset, values in self.ink.items()},
            fits={subset: tuple(values) for subset, values in self.fit.items()},
            unknown_fixtures=tuple(self.unknown.most_common(UNKNOWN_FIXTURES_TOP)),
        )


class _Beat:
    """Nhịp sống `touch_version`: mỗi `TOUCH_EVERY_SAMPLES` mẫu hay `TOUCH_EVERY`, cái nào trước.

    Thưa hơn cả hai mốc thì lịch quét của B6-02 tưởng lượt treo và đóng bản đang chạy; mỗi mẫu
    một vòng DB thì một lượt 6.000 mẫu tốn 6.000 vòng mà không mua gì. `False` (bản không còn
    `building`) chỉ ghi cảnh báo: `finish_version` cuối lượt mới là chỗ phán quyết kết cục.
    """

    def __init__(self, clock: Clock) -> None:
        """Mốc đầu là lúc dựng, nên những mẫu đầu không ghi nhịp vô ích."""
        self._at = clock.now()
        self._samples = 0

    async def tick(
        self, sessionmaker: async_sessionmaker[AsyncSession], clock: Clock, *, version_id: str, samples: int
    ) -> None:
        """Ghi nhịp nếu tới một trong hai mốc, trong một session ngắn riêng (K22, K36)."""
        now = clock.now()
        if samples - self._samples < TOUCH_EVERY_SAMPLES and now - self._at < TOUCH_EVERY:
            return
        self._at, self._samples = now, samples
        async with session_scope(sessionmaker) as db:
            alive = await touch_version(db, version_id=version_id, clock=clock)
        if not alive:
            _log.warning("cubicasa_touch_skipped", extra={"version_id": version_id, "samples": samples})


def _refused(code: str, *, reason: str | None = None, skipped: Mapping[str, int] | None = None) -> ImportReport:
    """Báo cáo `refused`: không phiên bản nào được tạo, chỉ có mã (và `reason` của zip)."""
    return ImportReport(outcome="refused", code=code, reason=reason, skipped=dict(skipped or {}))


def _read_labels(sample: SampleDir, settings: CubiCasaSettings) -> SvgLabels | SkipReason:
    """`model.svg` → nhãn, hay lý do bỏ mẫu; `UnsafePathError`, `OSError` nổi lên cho người gọi.

    Hai `try` riêng vì `UnsafePathError` và `FileTooLargeError` đều là `ValueError`: gộp lời gọi
    đọc vào cùng khối với `parse_model_svg` thì một symlink sẽ bị kể thành `svg_invalid`.
    """
    try:
        data = read_regular(sample.path / SVG_NAME, max_bytes=settings.cubicasa_svg_max_bytes)
    except FileTooLargeError:
        return "svg_rejected"
    try:
        return parse_model_svg(data, max_bytes=settings.cubicasa_svg_max_bytes)
    except SvgRejectedError as exc:
        return exc.reason
    except ValueError:
        return "svg_invalid"


def _read_image(
    sample: SampleDir, labels: SvgLabels, settings: CubiCasaSettings
) -> tuple[RgbImage, ImageChoice] | SkipReason:
    """`F1_scaled.png` → ảnh đã nạp và lựa chọn ảnh, hay lý do bỏ mẫu.

    `sizes` chỉ chứa các ảnh **có thật** của mẫu, nên "không có ảnh nào dùng được" là **một**
    đường duy nhất: bảng rỗng → `choose_image` trả `None` → `no_image`. Hàm này không tự kết
    luận thiếu ảnh, vì luật chọn ảnh thuộc `convert.choose_image` (phương án 1 hôm nay chỉ nhận
    `F1_scaled.png`; thêm ứng viên sau này không phải sửa ở đây).

    Khổ đọc từ IHDR (`read_png_header`) và trần điểm ảnh của `load_raster` chặn bom giải nén
    **trước** khi Pillow giải một pixel nào (K13). Tệp quá dài hay hỏng là `image_invalid`; tệp
    không phải tệp thường ném `UnsafePathError`, `_convert_sample` đổi thành `unsafe_path`.
    """
    data: bytes | None = None
    try:
        data = read_regular(sample.path / IMAGE_NAME, max_bytes=settings.cubicasa_max_file_bytes)
    except FileTooLargeError:
        return "image_invalid"
    except FileNotFoundError:
        pass
    sizes: dict[str, tuple[int, int]] = {}
    if data is not None:
        try:
            header = read_png_header(data)
        except ValueError:
            return "image_invalid"
        sizes[IMAGE_NAME] = (header.width, header.height)
    choice = choose_image((labels.width, labels.height), sizes)
    if choice is None or data is None:
        return "no_image"
    try:
        return load_raster(data, max_pixels=settings.cubicasa_max_pixels), choice
    except VisionError:
        return "image_invalid"


def _convert_sample(sample: SampleDir, family: str, settings: CubiCasaSettings) -> _Converted | SkipReason:
    """Toàn bộ việc CPU của một mẫu (đọc tệp, đọc SVG, giải ảnh, dựng nhãn) — chạy trên `to_thread`.

    Một họ dataset dùng một loại nhãn: `wallSegmentation` cần mặt nạ tường, họ còn lại cần hộp
    cửa/đồ; thiếu nhãn của **họ của mình** thì bỏ mẫu `no_labels`. `ink_ratio` đo cho cả hai họ
    khi mặt nạ tường không rỗng (chỉ đo, chưa bỏ mẫu theo ngưỡng).
    """
    try:
        labels = _read_labels(sample, settings)
        if isinstance(labels, str):
            return labels
        loaded = _read_image(sample, labels, settings)
    except UnsafePathError:
        return "unsafe_path"
    except OSError as exc:
        raise _SourceReadError(str(sample.path)) from exc
    if isinstance(loaded, str):
        return loaded
    image, choice = loaded
    height_px, width_px = image.pixels.shape[:2]
    mask = wall_mask_from_polygons(labels, choice, width_px=width_px, height_px=height_px)
    boxes, unknown = boxes_from_labels(labels, choice, width_px=width_px, height_px=height_px)
    if family == WALL_FAMILY:
        if not mask.any():
            return "no_labels"
        walls, objects = encode_mask(mask), None
    else:
        if not boxes:
            return "no_labels"
        walls, objects = None, objects_to_json(ObjectsResult(detections=boxes))
    return _Converted(
        sample=sample,
        image=encode_png(image),
        walls=walls,
        objects=objects,
        width_px=width_px,
        height_px=height_px,
        branch=choice.branch,
        fit_x=choice.fit_x,
        fit_y=choice.fit_y,
        ink=ink_ratio(mask, image.pixels),
        unknown=unknown,
    )


async def _checked_family(sessionmaker: async_sessionmaker[AsyncSession], dataset_id: str) -> str | ImportReport:
    """Bước 1: họ của dataset, hay báo cáo `refused` — ba cửa kiểm trước khi chạm nguồn.

    Đọc họ trước `start_version` vì `start_version` ném `ValueError` cho dataset không tồn tại,
    còn hợp đồng lệnh đòi mã `DATASET_NOT_FOUND` và **không** tạo bản nào. Session chỉ-đọc rất
    ngắn, đóng trước mọi lượt I/O (K36).
    """
    if not is_id("dst", dataset_id):
        return _refused(DATASET_NOT_FOUND)
    async with sessionmaker() as db:
        stmt = select(DatasetRow.family).where(DatasetRow.id == dataset_id)
        family = (await db.execute(stmt)).scalar_one_or_none()
    if family is None:
        return _refused(DATASET_NOT_FOUND)
    if family == UNSUPPORTED_FAMILY:
        return _refused(DATASET_FAMILY_UNSUPPORTED)
    return family


async def _add_sample(writer: SampleWriter, converted: _Converted) -> None:
    """Ghi một mẫu: `group_key = cubicasa:<id>` quyết định split, `sample_id = cubicasa-<id>`.

    Nhóm theo `id` nguồn (không theo subset) nên nhập lại cùng mẫu luôn vào cùng tập (M06).
    """
    group_key = f"cubicasa:{converted.sample.sample_id}"
    sample_id = f"cubicasa-{converted.sample.sample_id}"
    await writer.add_sample(
        split=split_for(group_key),
        sample_id=sample_id,
        image=converted.image,
        walls=converted.walls,
        objects=converted.objects,
        meta=SampleMeta(
            sample_id=sample_id,
            group_key=group_key,
            width_px=converted.width_px,
            height_px=converted.height_px,
            mm_per_px=None,
            source=SOURCE,
        ),
    )


async def _write_samples(
    sessionmaker: async_sessionmaker[AsyncSession],
    writer: SampleWriter,
    clock: Clock,
    *,
    samples: tuple[SampleDir, ...],
    family: str,
    version_id: str,
    settings: CubiCasaSettings,
    stats: _Stats,
) -> None:
    """Ghi tuần tự từng mẫu, một mẫu trong RAM mỗi lúc (K22); mẫu bỏ chỉ cộng bộ đếm.

    Vượt `cubicasa_max_samples` → `DATASET_TOO_LARGE` ngay ở mẫu vượt trần và **không** ghi
    mẫu đó: càng ghi thêm càng tốn kho rồi cũng bị xoá.
    """
    beat = _Beat(clock)
    for sample in samples:
        converted = await asyncio.to_thread(_convert_sample, sample, family, settings)
        if isinstance(converted, str):
            stats.skipped[converted] += 1
            continue
        stats.written += 1
        if stats.written > settings.cubicasa_max_samples:
            raise PermanentError(DATASET_TOO_LARGE)
        await _add_sample(writer, converted)
        stats.record(converted)
        await beat.tick(sessionmaker, clock, version_id=version_id, samples=stats.written)


async def _finish(
    sessionmaker: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
    clock: Clock,
    writer: SampleWriter,
    *,
    version_id: str,
    stats: _Stats,
) -> ImportReport:
    """Chốt lượt: 0 mẫu ghi được → `DATASET_EMPTY`; chốt được → `ready`.

    `finish_version` trả `False` nghĩa là bản không còn `building` (một phiên khác đã chốt nó
    `failed`): object dưới tiền tố không ai tham chiếu nữa nên xoá, và mã hỏng đọc lại từ DB
    thay vì đoán — chỉ DB biết vì sao bản bị chốt.
    """
    if stats.written == 0:
        raise PermanentError(DATASET_EMPTY)
    manifest, counts = await writer.finish()
    async with session_scope(sessionmaker) as db:
        done = await finish_version(
            db, version_id=version_id, manifest_sha256=manifest, split_counts=counts, clock=clock
        )
    if done:
        return stats.report("ready", version_id=version_id, split_counts=counts)
    await storage.delete_prefix(version_prefix(version_id))
    async with sessionmaker() as db:
        stmt = select(DatasetVersionRow.failure_code).where(DatasetVersionRow.id == version_id)
        code = (await db.execute(stmt)).scalar_one_or_none()
    _log.warning("cubicasa_finish_skipped", extra={"version_id": version_id, "failure_code": code})
    return stats.report("failed", code=code, version_id=version_id)


def _failure_code(exc: Exception) -> str | None:
    """`failureCode` của một lỗi lượt; `None` = lỗi không thuộc lượt này nên phải nổi lên (R-16).

    `AppError` khác `DEPENDENCY_UNAVAILABLE` (ví dụ lỗi lập trình của kho) và lỗi DB không dịch
    được đều không được âm thầm thành một bản `failed`: che chúng là che lỗi thật.
    """
    if isinstance(exc, _SourceReadError):
        return SOURCE_READ_FAILED
    if isinstance(exc, PermanentError):
        return exc.code
    if isinstance(exc, AppError):
        return DEPENDENCY_UNAVAILABLE.code if exc.code is DEPENDENCY_UNAVAILABLE else None
    translated = translate_db_error(exc)
    if translated is not None and translated.code is DEPENDENCY_UNAVAILABLE:
        return DEPENDENCY_UNAVAILABLE.code
    return None


async def _fail(
    sessionmaker: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
    clock: Clock,
    *,
    version_id: str,
    code: str,
    stats: _Stats,
) -> ImportReport:
    """Chốt bản `failed` rồi xoá tiền tố; **cả hai** bước hỏng chỉ ghi log `error`, vẫn trả `failed`.

    Lượt dọn thất bại không được biến kết cục thành ngoại lệ, kể cả khi chính DB chết: nếu
    `fail_version` ném thì bản còn `building`, và lịch quét của B6-02 sẽ đóng nó
    `DATASET_BUILD_TIMEOUT` rồi xoá tiền tố sau một giờ — rác luôn có người dọn lại. Ném ở đây
    chỉ làm lệnh thoát bằng traceback thay vì mã thoát 1 mà người vận hành đọc được.
    """
    try:
        async with session_scope(sessionmaker) as db:
            await fail_version(db, version_id=version_id, failure_code=code, clock=clock)
    except (DBAPIError, SATimeoutError):
        _log.exception("cubicasa_fail_version_failed", extra={"version_id": version_id, "failure_code": code})
    try:
        await storage.delete_prefix(version_prefix(version_id))
    except (AppError, OSError):
        _log.exception("cubicasa_cleanup_failed", extra={"version_id": version_id, "failure_code": code})
    return stats.report("failed", code=code, version_id=version_id)


async def _build(
    sessionmaker: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
    clock: Clock,
    *,
    samples: tuple[SampleDir, ...],
    dataset_id: str,
    family: str,
    settings: CubiCasaSettings,
    stats: _Stats,
) -> ImportReport:
    """Bước 4-7: mở bản, ghi mẫu, chốt; lỗi của lượt → bản `failed` kèm `failureCode`."""
    async with session_scope(sessionmaker) as db:
        version = await start_version(
            db, dataset_id=dataset_id, source=SOURCE, project_ids=None, created_by=CREATED_BY, clock=clock
        )
        version_id = None if version is None else version.id
    if version_id is None:
        return _refused(DATASET_BUILD_IN_PROGRESS.code, skipped=stats.skipped)
    writer = SampleWriter(storage, version_id)
    try:
        await _write_samples(
            sessionmaker,
            writer,
            clock,
            samples=samples,
            family=family,
            version_id=version_id,
            settings=settings,
            stats=stats,
        )
        return await _finish(sessionmaker, storage, clock, writer, version_id=version_id, stats=stats)
    except (AppError, PermanentError, DBAPIError, SATimeoutError, _SourceReadError) as exc:
        code = _failure_code(exc)
        if code is None:
            raise
        _log.warning("cubicasa_import_failed", extra={"version_id": version_id, "failure_code": code})
        return await _fail(sessionmaker, storage, clock, version_id=version_id, code=code, stats=stats)


async def _extract_source(src: Path, dest: Path, settings: CubiCasaSettings) -> ImportReport | None:
    """Giải zip nguồn vào `dest`; `None` khi xong, hay báo cáo `refused` của zip không an toàn."""
    try:
        await asyncio.to_thread(
            safe_extract,
            src,
            dest,
            max_files=settings.cubicasa_max_files,
            max_total_bytes=settings.cubicasa_max_total_bytes,
            max_file_bytes=settings.cubicasa_max_file_bytes,
            max_ratio=settings.cubicasa_max_ratio,
        )
    except UnsafeArchiveError as exc:
        return _refused(ARCHIVE_UNSAFE, reason=exc.reason)
    except OSError:
        _log.warning("cubicasa_extract_failed", extra={"src": str(src)})
        return _refused(SOURCE_INVALID)
    return None


def _make_work_dir(work_dir: Path) -> Path:
    """Thư mục tạm riêng của lượt dưới `CUBICASA_WORK_DIR` (tạo gốc nếu người vận hành chưa tạo)."""
    work_dir.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(dir=work_dir))


async def import_cubicasa(
    sessionmaker: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
    clock: Clock,
    *,
    src: Path,
    dataset_id: str,
    limit: int | None,
    settings: CubiCasaSettings,
) -> ImportReport:
    """Một lượt nhập CubiCasa5K: nguồn (thư mục hay zip) → một phiên bản dataset (B6-02b [6]).

    Thứ tự ba cửa kiểm là bất biến chính: dataset và họ **trước** khi chạm nguồn, nguồn an toàn
    **trước** khi mở phiên bản, nên mọi lỗi "từ chối" không để lại một bản `building` nào.
    Thư mục giải nén bị xoá trong `finally` bao cả lượt, kể cả khi lượt ném.
    """
    tmp: Path | None = None
    try:
        family = await _checked_family(sessionmaker, dataset_id)
        if isinstance(family, ImportReport):
            return family
        if await asyncio.to_thread(is_zip, src):
            tmp = await asyncio.to_thread(_make_work_dir, settings.cubicasa_work_dir)
            refused = await _extract_source(src, tmp, settings)
            if refused is not None:
                return refused
            root = tmp
        elif await asyncio.to_thread(src.is_dir):
            root = src
        else:
            return _refused(SOURCE_INVALID)
        samples, discovery = await asyncio.to_thread(discover_samples, root, limit=limit)
        if not samples:
            return _refused(SOURCE_EMPTY, skipped=discovery)
        stats = _Stats(skipped=Counter(discovery))
        return await _build(
            sessionmaker,
            storage,
            clock,
            samples=samples,
            dataset_id=dataset_id,
            family=family,
            settings=settings,
            stats=stats,
        )
    finally:
        if tmp is not None:
            await asyncio.to_thread(shutil.rmtree, tmp, ignore_errors=True)
