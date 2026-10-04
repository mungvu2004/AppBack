"""Test `preprocess` của B5-06a: chọn đường (#31/#32), dựng/nắn trang, `px_per_paper_mm`.

Kho là `local_storage` thật của B0-04 (K23, không mock kho); ảnh và PDF sinh trong bộ nhớ
bằng `render_plan` và `packages/vision/preprocess/tests/synthetic.py` của B2-05a — không tệp
nhị phân trong repo, không tải mạng. `choose_path` là hàm thuần nên dựng `DrawingRow`,
`AssessmentRow` trực tiếp, không cần DB.
"""

import math
from collections.abc import Callable
from typing import Any

import pytest
from PIL import Image

from apps.api.quality.assessments import AssessmentRow, Corners
from apps.worker.pipeline_orchestrate.preprocess import (
    PagePlan,
    PageSource,
    choose_path,
    prepare_page,
)
from apps.worker.pipeline_orchestrate.settings import OrchestrateSettings
from apps.worker.pipeline_orchestrate.tests._helpers import LEVEL_ID
from packages.core.clock import Clock, SystemClock
from packages.core.ids import new_id
from packages.db.models.drawings import DrawingRow
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.synthetic import render_plan
from packages.storage import keys
from packages.storage.port import ObjectStorage
from packages.vision.preprocess import DEFAULT_DPI, effective_dpi
from packages.vision.preprocess.tests.synthetic import encode, jpeg_with_orientation, make_pdf
from packages.vision.quality.assess import QualityReport

MM_PER_INCH = 25.4
A4_PT = (595.0, 842.0)
INSET_CORNERS: Corners = ((0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9))
"""Góc người dùng thu vào 80 % mỗi chiều — đủ để `k` khác 1 một cách đo được."""


def _id(prefix: str) -> str:
    """Id ULID mới của `prefix` cho khoá object (không chạm DB)."""
    return new_id(prefix, SystemClock())  # type: ignore[arg-type]  # prefix là hằng hợp `IdPrefix` ở test này


def _source(kind: str | None, *, page_index: int = 0, original: bool = True) -> PageSource:
    """`PageSource` với id mới mỗi lần — mỗi test có cây khoá riêng trong kho."""
    project_id, upload_id = _id("prj"), _id("upl")
    original_key = keys.upload_original(project_id, LEVEL_ID, upload_id, "bin") if original else None
    return PageSource(
        run_id=_id("run"),
        project_id=project_id,
        level_id=LEVEL_ID,
        upload_id=upload_id,
        page_index=page_index,
        original_key=original_key,
        kind=kind,
    )


def _drawing(upload_id: str, *, page_key: str = "page.png", size: tuple[int, int] = (800, 600)) -> DrawingRow:
    """Dòng `drawings` rời (không session) đủ trường `choose_path` đọc."""
    row = DrawingRow()
    row.id = _id("drw")
    row.upload_id = upload_id
    row.page_key = page_key
    row.width_px, row.height_px = size
    return row


def _assessment(drawing: DrawingRow, *, page_key: str, corners: Corners | None) -> AssessmentRow:
    """Dòng `quality_assessments` rời; `report["pageKey"]` là thứ `choose_path` so để nhận #31."""
    report: dict[str, Any] = {"pageKey": page_key}
    return AssessmentRow(floor_pk=1, drawing_id=drawing.id, report=report, corners=corners, homography={})


def _settings(**overrides: Any) -> OrchestrateSettings:
    """`OrchestrateSettings` hạ trần cho test (J03, U06) — không đọc biến môi trường."""
    return OrchestrateSettings(**overrides)


async def _put(storage: ObjectStorage, key: str, data: bytes) -> None:
    """Đặt bytes vào kho thật với trần rộng (dựng dữ liệu vào, không phải phần đang đo)."""
    await storage.put(key, data, content_type="application/octet-stream", max_bytes=len(data) + 1)


async def _prepare(
    storage: ObjectStorage,
    clock: Clock,
    plan: PagePlan,
    settings: OrchestrateSettings | None = None,
) -> Any:
    """`prepare_page` với `settings` mặc định — bớt lặp ở mỗi test."""
    return await prepare_page(plan, storage=storage, settings=settings or _settings(), clock=clock)


def test_choose_path__reuse_when_report_matches_drawing() -> None:
    """Cùng lượt tải, đo trỏ đúng bản vẽ và đúng `pageKey` → (i) dùng lại, không xử lý ảnh."""
    source = _source("pdf")
    drawing = _drawing(source.upload_id, page_key="pages/0-ABC.png")
    plan = choose_path(source, drawing, _assessment(drawing, page_key="pages/0-ABC.png", corners=INSET_CORNERS))
    assert plan.kind == "reuse"
    assert plan.reuse_page == ("pages/0-ABC.png", 800, 600)


def test_choose_path__user_when_corners_without_matching_report() -> None:
    """Cùng lượt tải, có góc nhưng `pageKey` lệch (trang đã đổi) → (ii) nắn lại theo góc."""
    source = _source("pdf")
    drawing = _drawing(source.upload_id, page_key="pages/0-NEW.png")
    plan = choose_path(source, drawing, _assessment(drawing, page_key="pages/0-OLD.png", corners=INSET_CORNERS))
    assert plan.kind == "user"
    assert plan.corners == INSET_CORNERS


def test_choose_path__auto_for_new_upload_over_old_corners() -> None:
    """Upload **mới** trên tầng có góc cũ → (iii) tự động: góc cũ đo trên trang khác."""
    source = _source("pdf")
    drawing = _drawing(_id("upl"), page_key="pages/0-OLD.png")
    plan = choose_path(source, drawing, _assessment(drawing, page_key="pages/0-OLD.png", corners=INSET_CORNERS))
    assert plan.kind == "auto"
    assert plan.corners is None


@pytest.mark.parametrize("with_drawing", [False, True])
def test_choose_path__auto_without_assessment(with_drawing: bool) -> None:
    """Chưa có dòng đo (hoặc chưa có bản vẽ) → (iii) tự động."""
    source = _source("pdf")
    drawing = _drawing(source.upload_id) if with_drawing else None
    assert choose_path(source, drawing, None).kind == "auto"


def test_choose_path__auto_when_corners_empty() -> None:
    """Cùng lượt tải, `pageKey` lệch và **không** góc → (iii): không có gì để áp lại."""
    source = _source("png")
    drawing = _drawing(source.upload_id, page_key="pages/0-NEW.png")
    plan = choose_path(source, drawing, _assessment(drawing, page_key="pages/0-OLD.png", corners=None))
    assert plan.kind == "auto"


async def test_prepare_page__reuse_touches_no_storage(local_storage: ObjectStorage, fake_clock: Clock) -> None:
    """(i) trả ngay trang của bản vẽ: không trang mới, không đo, `px_per_paper_mm` là `None`."""
    source = _source("pdf")
    plan = PagePlan(source=source, kind="reuse", reuse_page=("pages/0-ABC.png", 1234, 567))
    prepared = await _prepare(local_storage, fake_clock, plan)
    assert (prepared.page_key, prepared.width_px, prepared.height_px) == ("pages/0-ABC.png", 1234, 567)
    assert prepared.created_key is None
    assert (prepared.px_per_paper_mm, prepared.homography, prepared.report, prepared.corners) == (
        None,
        None,
        None,
        None,
    )
    page_key = keys.upload_page(source.project_id, source.level_id, source.upload_id, source.page_index)
    assert await local_storage.stat(page_key) is None


async def test_prepare_page__px_per_paper_mm_of_pdf_without_frame(
    local_storage: ObjectStorage, fake_clock: Clock
) -> None:
    """PDF (iii) không khung: giữ trang `upload_page`, `identity`, `px_per_paper_mm` = `dpi / 25.4`."""
    source = _source("pdf")
    assert source.original_key is not None
    await _put(local_storage, source.original_key, make_pdf(1))
    prepared = await _prepare(local_storage, fake_clock, PagePlan(source=source, kind="auto"))
    page_key = keys.upload_page(source.project_id, source.level_id, source.upload_id, source.page_index)
    assert (prepared.page_key, prepared.created_key, prepared.corners) == (page_key, None, None)
    expected = effective_dpi(*A4_PT, DEFAULT_DPI, _settings().pipeline_max_pixels) / MM_PER_INCH
    assert prepared.px_per_paper_mm is not None
    assert math.isclose(prepared.px_per_paper_mm, expected, rel_tol=0.0, abs_tol=1e-9)
    assert prepared.homography is not None
    assert prepared.homography["widthPx"] == prepared.homography["sourceWidthPx"]


async def test_prepare_page__px_per_paper_mm_scales_by_quad_edge(
    local_storage: ObjectStorage, fake_clock: Clock
) -> None:
    """PDF (ii) góc thu 80 %: `px_per_paper_mm` = `dpi / 25.4 · k`, `k` theo cạnh trên/dưới của quad."""
    source = _source("pdf")
    assert source.original_key is not None
    await _put(local_storage, source.original_key, make_pdf(1))
    plan = PagePlan(source=source, kind="user", corners=INSET_CORNERS)
    prepared = await _prepare(local_storage, fake_clock, plan)
    assert prepared.homography is not None
    quad_edge = 0.8 * float(prepared.homography["sourceWidthPx"])
    scale = float(prepared.homography["widthPx"]) / quad_edge
    expected = effective_dpi(*A4_PT, DEFAULT_DPI, _settings().pipeline_max_pixels) / MM_PER_INCH * scale
    assert prepared.px_per_paper_mm is not None
    assert math.isclose(prepared.px_per_paper_mm, expected, rel_tol=0.0, abs_tol=1e-9)
    assert prepared.corners == INSET_CORNERS
    assert prepared.created_key == prepared.page_key
    assert "/pages/0-" in prepared.created_key


async def test_prepare_page__px_per_paper_mm_none_for_raster(local_storage: ObjectStorage, fake_clock: Clock) -> None:
    """PNG: không biết khổ giấy nên `px_per_paper_mm` là `None`, nhưng vẫn đo và ghi trang."""
    source = _source("png")
    assert source.original_key is not None
    await _put(local_storage, source.original_key, render_plan(3).image_png)
    plan = PagePlan(source=source, kind="user", corners=INSET_CORNERS)
    prepared = await _prepare(local_storage, fake_clock, plan)
    assert prepared.px_per_paper_mm is None
    assert isinstance(prepared.report, QualityReport)
    assert prepared.created_key is not None
    assert await local_storage.stat(prepared.created_key) is not None


async def test_prepare_page__jpeg_exif_rotation_swaps_size(local_storage: ObjectStorage, fake_clock: Clock) -> None:
    """U01: JPEG `Orientation 6` (xoay 90°) → `width_px`/`height_px` của trang hoán vị."""
    source = _source("jpeg")
    assert source.original_key is not None
    await _put(local_storage, source.original_key, jpeg_with_orientation(400, 200, 6))
    prepared = await _prepare(local_storage, fake_clock, PagePlan(source=source, kind="auto"))
    assert (prepared.width_px, prepared.height_px) == (200, 400)


def _gray16_png() -> bytes:
    """PNG xám 16-bit đầy dải — đường hạ 16 → 8 bit của B2-05a (U02)."""
    return encode(Image.new("I;16", (320, 240), 65535), "PNG")


def _alpha_png() -> bytes:
    """PNG RGBA trong suốt hoàn toàn — nền phải hoá trắng, không hoá đen (U02)."""
    return encode(Image.new("RGBA", (320, 240), (0, 0, 0, 0)), "PNG")


def _cmyk_jpeg() -> bytes:
    """JPEG CMYK của máy quét — phải đổi được về RGB 8-bit (U02)."""
    return encode(Image.new("CMYK", (320, 240), (0, 0, 0, 0)), "JPEG")


@pytest.mark.parametrize(
    ("kind", "make"),
    [("png", _gray16_png), ("png", _alpha_png), ("jpeg", _cmyk_jpeg)],
    ids=["png16", "png_alpha", "jpeg_cmyk"],
)
async def test_prepare_page__odd_raster_modes_complete(
    kind: str, make: Callable[[], bytes], local_storage: ObjectStorage, fake_clock: Clock
) -> None:
    """U02: PNG 16-bit, PNG alpha và JPEG CMYK đều về RGB 8-bit và chạy hết bước tiền xử lý."""
    source = _source(kind)
    assert source.original_key is not None
    await _put(local_storage, source.original_key, make())
    prepared = await _prepare(local_storage, fake_clock, PagePlan(source=source, kind="auto"))
    assert (prepared.width_px, prepared.height_px) == (320, 240)
    assert isinstance(prepared.report, QualityReport)


async def test_prepare_page__encrypted_pdf_raises_pdf_unreadable(
    local_storage: ObjectStorage, fake_clock: Clock
) -> None:
    """U04: PDF có `user_password` → `PermanentError("PDF_UNREADABLE")` (không thử lại)."""
    source = _source("pdf")
    assert source.original_key is not None
    await _put(local_storage, source.original_key, make_pdf(1, encrypt="user_password"))
    with pytest.raises(PermanentError) as caught:
        await _prepare(local_storage, fake_clock, PagePlan(source=source, kind="auto"))
    assert caught.value.code == "PDF_UNREADABLE"


async def test_prepare_page__huge_pdf_page_fits_max_pixels(local_storage: ObjectStorage, fake_clock: Clock) -> None:
    """U06: trang 5.000 pt với trần 4.000.000 điểm ảnh → `w · h` ≤ trần (PDF **co**, không ném)."""
    source = _source("pdf")
    assert source.original_key is not None
    await _put(local_storage, source.original_key, make_pdf(1, size=(5000.0, 5000.0)))
    limit = 4_000_000
    prepared = await _prepare(
        local_storage, fake_clock, PagePlan(source=source, kind="auto"), _settings(pipeline_max_pixels=limit)
    )
    assert prepared.width_px * prepared.height_px <= limit


async def test_prepare_page__raster_over_max_pixels_raises(local_storage: ObjectStorage, fake_clock: Clock) -> None:
    """J03: raster vượt `PIPELINE_MAX_PIXELS` → `IMAGE_TOO_LARGE` (`load_raster` ném, không co)."""
    source = _source("png")
    assert source.original_key is not None
    await _put(local_storage, source.original_key, render_plan(5, width_px=1600, height_px=1200).image_png)
    with pytest.raises(PermanentError) as caught:
        await _prepare(
            local_storage, fake_clock, PagePlan(source=source, kind="auto"), _settings(pipeline_max_pixels=1_000_000)
        )
    assert caught.value.code == "IMAGE_TOO_LARGE"


async def test_prepare_page__original_over_byte_cap_raises(local_storage: ObjectStorage, fake_clock: Clock) -> None:
    """Trần byte bản gốc: `PIPELINE_ORIGINAL_MAX_BYTES` nhỏ hơn tệp → `IMAGE_TOO_LARGE` trước khi dựng."""
    source = _source("pdf")
    assert source.original_key is not None
    await _put(local_storage, source.original_key, make_pdf(1))
    with pytest.raises(PermanentError) as caught:
        await _prepare(
            local_storage,
            fake_clock,
            PagePlan(source=source, kind="auto"),
            _settings(pipeline_original_max_bytes=16),
        )
    assert caught.value.code == "IMAGE_TOO_LARGE"


@pytest.mark.parametrize("kind", ["dwg", None], ids=["unknown_kind", "missing_kind"])
async def test_prepare_page__odd_kind_raises_file_type_mismatch(
    kind: str | None, local_storage: ObjectStorage, fake_clock: Clock
) -> None:
    """Loại tệp ngoài `pdf|png|jpeg` → `PermanentError("FILE_TYPE_MISMATCH")`, không đọc bản gốc."""
    with pytest.raises(PermanentError) as caught:
        await _prepare(local_storage, fake_clock, PagePlan(source=_source(kind), kind="auto"))
    assert caught.value.code == "FILE_TYPE_MISMATCH"


async def test_prepare_page__missing_original_key_raises_file_type_mismatch(
    local_storage: ObjectStorage, fake_clock: Clock
) -> None:
    """Lượt tải thiếu `original_key` (dữ liệu hỏng) → `FILE_TYPE_MISMATCH`, không `open_read`."""
    with pytest.raises(PermanentError) as caught:
        await _prepare(local_storage, fake_clock, PagePlan(source=_source("pdf", original=False), kind="auto"))
    assert caught.value.code == "FILE_TYPE_MISMATCH"


async def test_prepare_page__stored_page_skips_original(local_storage: ObjectStorage, fake_clock: Clock) -> None:
    """Trang đã có trong kho → đọc nó, **không** đọc bản gốc (khoá gốc bỏ trống) và không đo giấy."""
    source = _source("pdf", page_index=2)
    page_key = keys.upload_page(source.project_id, source.level_id, source.upload_id, source.page_index)
    await _put(local_storage, page_key, render_plan(7).image_png)
    prepared = await _prepare(local_storage, fake_clock, PagePlan(source=source, kind="user", corners=INSET_CORNERS))
    assert prepared.px_per_paper_mm is None
    assert prepared.created_key is not None
    assert prepared.created_key != page_key
    assert source.original_key is not None
    assert await local_storage.stat(source.original_key) is None
