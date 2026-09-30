"""Tiền xử lý trang của `start` (B5-06a [6] bước 2-3): chọn đường, dựng/nắn trang, đo.

`choose_path` là hàm thuần trên dữ kiện GD1 đọc dưới khoá; `prepare_page` chạy **ngoài**
session (K36): đọc bản gốc hoặc `pages/{i}.png`, dựng, nắn, `assess`, ghi trang mới.
Mọi xử lý ảnh qua B2-05a có `max_pixels` (K13), chạy trên `asyncio.to_thread`;
`VisionError(code)` → `PermanentError(code)`; loại tệp lạ → `PermanentError("FILE_TYPE_MISMATCH")`.
KHUNG của nhánh prep: việc B viết thân (được thêm hàm riêng, không đổi các chữ ký dưới).
"""

import asyncio
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial
from typing import Any, Final, Literal

from apps.api.drawings.drawings import new_page_key
from apps.api.quality.assessments import AssessmentRow, Corners
from apps.worker.pipeline_orchestrate.settings import OrchestrateSettings
from packages.core.clock import Clock
from packages.core.error_codes import FILE_TYPE_MISMATCH, IMAGE_TOO_LARGE
from packages.db.models.drawings import DrawingRow
from packages.messaging.tasks import PermanentError
from packages.storage import keys
from packages.storage.port import ObjectStorage
from packages.vision.preprocess import (
    Homography,
    Quad,
    RgbImage,
    VisionError,
    effective_dpi,
    encode_png,
    find_frame,
    load_raster,
    pdf_page_size_pt,
    quad_from_ratios,
    quad_to_ratios,
    rectify,
    render_pdf_page,
)
from packages.vision.quality.assess import QualityReport, assess

PathKind = Literal["reuse", "user", "auto"]

PNG_CONTENT_TYPE: Final = "image/png"
MM_PER_INCH: Final = 25.4
_RASTER_KINDS: Final = frozenset({"png", "jpeg"})


@dataclass(frozen=True, slots=True)
class PageSource:
    """Dữ kiện lượt tải GD1 đọc dưới khoá — đủ để việc chậm chạy không cần session.

    `kind` là `uploads.sniffed_kind` (`"pdf"`, `"png"`, `"jpeg"`; khác → `FILE_TYPE_MISMATCH`);
    `level_id` là id công khai của tầng (khoá storage dùng nó, không dùng `floor_pk`).
    """

    run_id: str
    project_id: str
    level_id: str
    upload_id: str
    page_index: int
    original_key: str | None
    kind: str | None


@dataclass(frozen=True, slots=True)
class PagePlan:
    """Đường đã chọn ([6] bước 2) cùng dữ kiện riêng của đường đó.

    `reuse`: `reuse_page` = `(page_key, width_px, height_px)` của bản vẽ hiện có, không xử lý ảnh.
    `user`: `corners` = góc người dùng (tỉ lệ theo trang chưa nắn). `auto`: `corners` = `None`.
    """

    source: PageSource
    kind: PathKind
    corners: Corners | None = None
    reuse_page: tuple[str, int, int] | None = None


@dataclass(frozen=True, slots=True)
class PreparedPage:
    """Trang cho GD2 và `queue_infer`.

    `homography` (dạng `Homography.to_json()`), `report` là `None` chỉ ở đường `reuse` (GD2
    không ghi `drawings`/đo). `created_key`: khoá trang **mới** lượt này ghi (`new_page_key`) để
    GD2 xoá khi hỏng; không bao giờ là `pages/{i}.png`. `px_per_paper_mm` theo [6] bước 3.
    """

    page_key: str
    width_px: int
    height_px: int
    px_per_paper_mm: float | None
    homography: Mapping[str, Any] | None
    corners: Corners | None
    report: QualityReport | None
    created_key: str | None


@dataclass(frozen=True, slots=True)
class _Base:
    """Trang **chưa nắn** vừa dựng xong cùng dữ kiện chỉ pha dựng biết.

    `size_pt` là khổ trang PDF **vừa dựng lượt này**, mọi đường khác `None` — vì
    `px_per_paper_mm` chỉ đo được khi biết khổ giấy thật ([6] bước 3).
    """

    page: RgbImage
    size_pt: tuple[float, float] | None


@dataclass(frozen=True, slots=True)
class _Finished:
    """Trang cuối (đã nắn hoặc giữ nguyên) sau `rectify`, `assess`, `encode_png`.

    `png` là `None` ở đường (iii) không tìm được khung: trang cuối chính là `upload_page` đã
    ghi nên lượt này không sinh trang mới. `quad_scale` là `k` của [6] bước 3 (1,0 với `identity`).
    """

    homography: Homography
    report: QualityReport
    png: bytes | None
    quad_scale: float


def choose_path(source: PageSource, drawing: DrawingRow | None, assessment: AssessmentRow | None) -> PagePlan:
    """Chọn (i) dùng lại / (ii) góc người dùng / (iii) tự động theo [6] bước 2 (#31/#32).

    Bản vẽ của lượt tải **khác** (upload mới trên tầng đã nắn tay) luôn về (iii): góc và báo cáo
    cũ đo trên trang khác nên áp lại sẽ nắn sai.
    """
    if drawing is None or drawing.upload_id != source.upload_id or assessment is None:
        return PagePlan(source=source, kind="auto")
    if assessment.drawing_id == drawing.id and assessment.report.get("pageKey") == drawing.page_key:
        reuse = (drawing.page_key, drawing.width_px, drawing.height_px)
        return PagePlan(source=source, kind="reuse", reuse_page=reuse)
    if assessment.corners:
        return PagePlan(source=source, kind="user", corners=assessment.corners)
    return PagePlan(source=source, kind="auto")


async def _offload[ResultT](fn: Callable[[], ResultT]) -> ResultT:
    """Chạy việc ảnh trên luồng riêng (K36); `VisionError` → `PermanentError` cùng mã ([6] bước 3)."""
    try:
        return await asyncio.to_thread(fn)
    except VisionError as exc:
        raise PermanentError(exc.code) from exc


async def _read_capped(storage: ObjectStorage, key: str, *, max_bytes: int) -> bytes:
    """Đọc cả object nhưng dừng ngay khi vượt `max_bytes` (K13) → `PermanentError("IMAGE_TOO_LARGE")`."""
    buffer = bytearray()
    async for chunk in storage.open_read(key):
        buffer += chunk
        if len(buffer) > max_bytes:
            raise PermanentError(IMAGE_TOO_LARGE.code)
    return bytes(buffer)


def _render_base(data: bytes, kind: str, page_index: int, settings: OrchestrateSettings) -> tuple[_Base, bytes]:
    """Bản gốc → trang chưa nắn + PNG để ghi lên `upload_page`; PDF kèm khổ trang.

    Khổ trang PDF đọc **trước** khi dựng (`pdf_page_size_pt` không dựng ảnh) để `px_per_paper_mm`
    không phải giữ `data` sống qua các pha sau. Chạy trong `asyncio.to_thread`.
    """
    limit = settings.PIPELINE_MAX_PIXELS
    if kind == "pdf":
        size_pt = pdf_page_size_pt(data, page_index)
        page = render_pdf_page(data, page_index, dpi=settings.PIPELINE_PDF_DPI, max_pixels=limit)
    else:
        size_pt = None
        page = load_raster(data, max_pixels=limit)
    return _Base(page=page, size_pt=size_pt), encode_png(page)


def _quad_scale(homography: Homography, quad: Quad) -> float:
    """`k` của [6] bước 3: pixel trang nắn trên pixel cạnh trên/dưới dài nhất của `quad` nguồn.

    Chỉ đường (ii)/(iii) có khung gọi tới; đường giữ nguyên trang dùng thẳng 1,0 trong `_finish`.
    """
    top_left, top_right, bottom_right, bottom_left = quad.points
    return homography.width_px / max(math.dist(top_right, top_left), math.dist(bottom_right, bottom_left))


def _finish(page: RgbImage, quad: Quad | None, settings: OrchestrateSettings) -> _Finished:
    """Nắn (nếu có `quad`), đo chất lượng, mã hoá PNG trang mới. Chạy trong `asyncio.to_thread`.

    `quad is None` giữ nguyên trang: `Homography.identity` và `png=None` vì trang cuối đã nằm
    trong kho ở khoá `upload_page`. Bỏ tham chiếu ảnh nguồn ngay sau `rectify` để đỉnh bộ nhớ
    không giữ cùng lúc trang chưa nắn, trang nắn và PNG.
    """
    if quad is None:
        return _Finished(Homography.identity(page.width_px, page.height_px), assess(page), None, 1.0)
    result = rectify(page, quad, max_pixels=settings.PIPELINE_MAX_PIXELS)
    del page
    final = result.image
    return _Finished(result.homography, assess(final), encode_png(final), _quad_scale(result.homography, quad))


async def _load_base(plan: PagePlan, *, storage: ObjectStorage, settings: OrchestrateSettings) -> tuple[_Base, str]:
    """Trang chưa nắn của `plan` và khoá `upload_page` của nó; ghi trang lên kho nếu vừa dựng.

    `upload_page` đã có (lượt trước, hay #31 sau ML) → đọc lại nó, không dựng lại và không ghi,
    nên `px_per_paper_mm` của lượt đó là `None`. Loại tệp ngoài `pdf|png|jpeg` (kể cả thiếu
    `original_key`) → `PermanentError("FILE_TYPE_MISMATCH")`.
    """
    source = plan.source
    page_key = keys.upload_page(source.project_id, source.level_id, source.upload_id, source.page_index)
    if await storage.stat(page_key) is not None:
        stored = await _read_capped(storage, page_key, max_bytes=settings.PIPELINE_PAGE_MAX_BYTES)
        page = await _offload(partial(load_raster, stored, max_pixels=settings.PIPELINE_MAX_PIXELS))
        return _Base(page=page, size_pt=None), page_key
    kind = source.kind
    if source.original_key is None or kind is None or (kind != "pdf" and kind not in _RASTER_KINDS):
        raise PermanentError(FILE_TYPE_MISMATCH.code)
    data = await _read_capped(storage, source.original_key, max_bytes=settings.PIPELINE_ORIGINAL_MAX_BYTES)
    base, png = await _offload(partial(_render_base, data, kind, source.page_index, settings))
    del data
    await storage.put(page_key, png, content_type=PNG_CONTENT_TYPE, max_bytes=settings.PIPELINE_PAGE_MAX_BYTES)
    return base, page_key


def _source_quad(plan: PagePlan, page: RgbImage) -> Quad | None:
    """`quad` nguồn của đường (ii)/(iii); `None` nghĩa là giữ nguyên trang ([6] bước 2).

    Có `corners` (chỉ đường (ii) mang) → dùng góc người dùng; không thì đi tìm khung (iii).
    """
    if plan.corners is not None:
        return quad_from_ratios(plan.corners, page.width_px, page.height_px)
    return find_frame(page)


def _corners_of(plan: PagePlan, quad: Quad | None, page: RgbImage) -> Corners | None:
    """Góc lưu vào `quality_assessments`: giữ góc người dùng ở (ii), đổi khung tìm được sang tỉ lệ ở (iii)."""
    if plan.kind == "user":
        return plan.corners
    return None if quad is None else quad_to_ratios(quad, page.width_px, page.height_px)


async def _write_page(
    plan: PagePlan, png: bytes, *, storage: ObjectStorage, settings: OrchestrateSettings, clock: Clock
) -> str:
    """Ghi trang đã nắn vào một khoá **mới** (`new_page_key`) và trả khoá đó.

    Khoá mới mỗi lượt nên URL ký của trang cũ không bao giờ trỏ vào ảnh khác (W23); GD2 xoá
    khoá này khi lượt bị thay.
    """
    source = plan.source
    key = new_page_key(
        project_id=source.project_id,
        level_id=source.level_id,
        upload_id=source.upload_id,
        page_index=source.page_index,
        clock=clock,
    )
    await storage.put(key, png, content_type=PNG_CONTENT_TYPE, max_bytes=settings.PIPELINE_PAGE_MAX_BYTES)
    return key


async def prepare_page(
    plan: PagePlan, *, storage: ObjectStorage, settings: OrchestrateSettings, clock: Clock
) -> PreparedPage:
    """Việc chậm của [6] bước 3 cho `plan`; không mở session, không ghi DB.

    Đường (i) trả ngay trang của bản vẽ hiện có, không chạm kho. Các đường khác dựng trang chưa
    nắn, chọn `quad`, nắn, đo, ghi trang mới; `px_per_paper_mm` chỉ có với PDF vừa dựng lượt này.
    """
    if plan.reuse_page is not None:  # chỉ đường (i) mang `reuse_page`
        key, width_px, height_px = plan.reuse_page
        return PreparedPage(key, width_px, height_px, None, None, None, None, None)
    base, page_key = await _load_base(plan, storage=storage, settings=settings)
    page, size_pt = base.page, base.size_pt
    del base  # bỏ tham chiếu cuối tới PNG trang chưa nắn trước khi cấp phát trang nắn
    quad = await _offload(partial(_source_quad, plan, page))
    corners = _corners_of(plan, quad, page)
    done = await _offload(partial(_finish, page, quad, settings))
    del page
    created_key = None
    if done.png is not None:
        created_key = await _write_page(plan, done.png, storage=storage, settings=settings, clock=clock)
    px_per_paper_mm = None
    if size_pt is not None:
        dpi = effective_dpi(*size_pt, settings.PIPELINE_PDF_DPI, settings.PIPELINE_MAX_PIXELS)
        px_per_paper_mm = dpi / MM_PER_INCH * done.quad_scale
    return PreparedPage(
        page_key=created_key or page_key,
        width_px=done.homography.width_px,
        height_px=done.homography.height_px,
        px_per_paper_mm=px_per_paper_mm,
        homography=done.homography.to_json(),
        corners=corners,
        report=done.report,
        created_key=created_key,
    )
