"""Dựng dữ liệu cho mọi test của `apps/api/quality` (việc D dùng, việc R dùng lại).

`make_drawn_floor` dựng tầng + upload `complete` + bản vẽ đang dùng qua factory sẵn có;
`measure_floor` thêm một lượt chạy `pending` và ghi dòng đo qua `save_assessment` (đường ghi
thật, không chèn thẳng). `sample_report` dựng `QualityReport` bằng tay — không cần ảnh.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.drawings.runs import RunRow, start_run
from apps.api.quality.assessments import AssessmentRow, save_assessment
from packages.core.clock import Clock
from packages.db.models.drawings import DrawingRow, UploadRow
from packages.db.models.floors import FloorRow
from packages.db.models.projects import Project
from packages.storage.port import ObjectStorage
from packages.testing.factories.drawings import make_complete_upload, make_drawing, png_bytes
from packages.testing.factories.floors import make_floor
from packages.vision.preprocess.types import Homography, Quad
from packages.vision.quality import Finding, Measurement, QualityReport, Region

WIDTH, HEIGHT = 800, 600
PNG = png_bytes(WIDTH, HEIGHT)
FULL_QUAD = Quad(((0.0, 0.0), (WIDTH, 0.0), (WIDTH, HEIGHT), (0.0, HEIGHT)))


@dataclass(frozen=True, slots=True)
class DrawnFloor:
    """Tầng đã có bản vẽ đang dùng (và upload gốc của nó)."""

    project: Project
    floor: FloorRow
    upload: UploadRow
    drawing: DrawingRow


def finding(
    code: str, *, x: float = 0.1, y: float = 0.1, severity: Literal["attention", "poor"] = "attention"
) -> Finding:
    """Một phát hiện vùng `0.2 x 0.2` tại `(x, y)`."""
    return Finding(code=code, severity=severity, region=Region(x, y, 0.2, 0.2), metrics={})


def sample_report(*findings: Finding, frame: Quad | None = FULL_QUAD) -> QualityReport:
    """Báo cáo dựng tay: số đo cố định, khung `frame` theo pixel của trang `WIDTH x HEIGHT`."""
    measurement = Measurement(width_px=WIDTH, height_px=HEIGHT, skew_deg=0.4, contrast_score=0.8, noise_score=0.9)
    return QualityReport(measurement=measurement, findings=tuple(findings), frame=frame)


def identity_json() -> dict[str, object]:
    """Homography đơn vị của trang mẫu, dạng cột `homography`."""
    return Homography.identity(WIDTH, HEIGHT).to_json()


async def make_drawn_floor(
    db: AsyncSession,
    storage: ObjectStorage,
    *,
    project: Project,
    order: int | None = None,
    name: str | None = None,
    png: bytes = PNG,
    original: bytes | None = None,
    file_name: str = "ban-ve.png",
) -> DrawnFloor:
    """Tầng mới + upload `complete` + bản vẽ đang dùng.

    Mặc định trang là PNG `WIDTH x HEIGHT` chỉ có đầu tệp (đủ cho test đọc). Test route cần
    ảnh giải mã được thì đưa `png` thật; `original`/`file_name` khác `png` khi tệp gốc là PDF,
    tệp cụt, hay ảnh quá lớn.
    """
    floor = await make_floor(db, project=project, order=order, name=name)
    upload = await make_complete_upload(
        db, storage, project=project, floor=floor, data=original or png, file_name=file_name
    )
    drawing = await make_drawing(db, storage, upload=upload, png=png)
    return DrawnFloor(project, floor, upload, drawing)


async def measure_floor(
    db: AsyncSession,
    clock: Clock,
    drawn: DrawnFloor,
    report: QualityReport,
    *,
    corners: Sequence[tuple[float, float]] | None = None,
    undo: dict[str, object] | None = None,
    width_px: int = WIDTH,
    height_px: int = HEIGHT,
    homography: Mapping[str, object] | None = None,
) -> tuple[RunRow, AssessmentRow]:
    """Mở lượt `pending` cho upload của tầng rồi `save_assessment` trên bản vẽ hiện tại.

    Kích thước và homography mặc định là của trang mẫu `WIDTH x HEIGHT` (ma trận đơn vị); test
    có ảnh thật đưa kích thước ảnh, hoặc một homography lệch cỡ để thử 409.
    """
    run = await start_run(db, upload_id=drawn.upload.id, clock=clock)
    saved = await save_assessment(
        db,
        run_id=run.id,
        floor_pk=drawn.floor.pk,
        drawing_id=drawn.drawing.id,
        page_key=drawn.drawing.page_key,
        width_px=width_px,
        height_px=height_px,
        report=report,
        homography=homography if homography is not None else Homography.identity(width_px, height_px).to_json(),
        corners=corners,
        undo=undo,
        clock=clock,
    )
    assert saved is not None
    return run, saved
