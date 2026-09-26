"""Kết quả đo chất lượng của trang đang dùng: ghi (worker), đọc (#30) và dựng response (B2-05b [2], [6]).

`save_assessment` là **cửa ghi duy nhất** của `quality_assessments`. Nó mở bằng `lock_run`
của B2-04 nên thừa hưởng thứ tự khoá `floors` → lượt chạy (BE-00 §7) và luật "không tin
worker": lượt đã kết thúc, đã bị thay, hay thuộc lượt tải khác bản vẽ thì trả `None` và
**không ghi gì**. Nó không `commit`: B5-06a gọi sau `upsert_drawing` trong cùng giao dịch.

`read_view` dựng `ImageQualityAssessment` bằng **một** truy vấn (tầng ⋈ bản vẽ ⟕ dòng đo);
dòng đo chỉ được tin khi `drawing_id` và `report.pageKey` còn khớp bản vẽ hiện tại.

Module này là "hàm worker nhập" (BE-00 §7): không `fastapi`/`starlette`.
"""

import logging
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from sqlalchemy import Row, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.drawings.drawings import drawing_url
from apps.api.drawings.runs import lock_run
from apps.api.quality.schemas import (
    CornerOut,
    FindingOut,
    FloorQualityOut,
    FrameOut,
    MeasurementOut,
    QualityAssessmentOut,
    RegionOut,
)
from packages.core.clock import Clock
from packages.core.error_codes import NOT_FOUND
from packages.db.models.drawings import DrawingRow
from packages.db.models.floors import FloorRow
from packages.db.models.quality import QualityAssessmentRow
from packages.storage.port import ObjectStorage
from packages.vision.preprocess.geometry import quad_to_ratios
from packages.vision.quality import QUALITY_CODES, QualityReport

_log: Final = logging.getLogger(__name__)

MAX_FLOORS: Final = 50
"""Trần số tầng của một dự án (B2-03) — chặn truy vấn đọc không giới hạn."""

_ULID: Final = re.compile(r"[0-9A-HJKMNP-TV-Z]{26}")
_DECIMALS: Final = 4

Corners = tuple[tuple[float, float], ...]


@dataclass(frozen=True, slots=True)
class AssessmentRow:
    """Ảnh chụp một dòng đo cho người gọi ngoài module (B5-06a); đông cứng.

    `corners` là bốn góc người dùng đã áp, tỉ lệ theo trang **chưa nắn**; `homography` dạng
    `RectifyResult.to_json()` để `Homography.from_json` đọc lại.
    """

    floor_pk: int
    drawing_id: str
    report: Mapping[str, Any]
    corners: Corners | None
    homography: Mapping[str, Any]


def _as_corners(raw: Sequence[Sequence[float]] | None) -> Corners | None:
    """jsonb (list lồng) hoặc chuỗi cặp số → tuple lồng; `None` giữ nguyên."""
    return None if raw is None else tuple((float(x), float(y)) for x, y in raw)


def report_to_json(
    report: QualityReport, *, page_key: str, width_px: int, height_px: int, undo: Mapping[str, Any] | None
) -> dict[str, Any]:
    """`QualityReport` (B2-05a) → JSON cột `report` ([5]).

    Số đo, vùng, mức lấy nguyên từ báo cáo; khung pixel → tỉ lệ bằng `quad_to_ratios`. Mã
    ngoài `QUALITY_CODES` bị bỏ và ghi log `quality_unknown_code` (K01): FE không có nhãn
    cho mã lạ nên gửi nó chỉ làm hỏng màn.
    """
    findings = []
    for finding in report.findings:
        if finding.code not in QUALITY_CODES:
            _log.warning("quality_unknown_code", extra={"code": finding.code})
            continue
        region = finding.region
        findings.append(
            {
                "code": finding.code,
                "severity": finding.severity,
                "region": {
                    "xRatio": region.x_ratio,
                    "yRatio": region.y_ratio,
                    "widthRatio": region.width_ratio,
                    "heightRatio": region.height_ratio,
                },
            }
        )
    measurement = report.measurement
    corners = None if report.frame is None else [list(p) for p in quad_to_ratios(report.frame, width_px, height_px)]
    return {
        "pageKey": page_key,
        "widthPx": width_px,
        "heightPx": height_px,
        "measurement": {
            "widthPx": measurement.width_px,
            "heightPx": measurement.height_px,
            "skewDeg": measurement.skew_deg,
            "contrastScore": measurement.contrast_score,
            "noiseScore": measurement.noise_score,
        },
        "findings": findings,
        "frame": {"isFound": corners is not None, "corners": corners},
        "undo": None if undo is None else dict(undo),
    }


async def save_assessment(
    db: AsyncSession,
    *,
    run_id: str,
    floor_pk: int,
    drawing_id: str,
    page_key: str,
    width_px: int,
    height_px: int,
    report: QualityReport,
    homography: Mapping[str, Any],
    corners: Sequence[tuple[float, float]] | None = None,
    undo: Mapping[str, Any] | None = None,
    clock: Clock,
) -> AssessmentRow | None:
    """Ghi (upsert theo `floor_pk`) kết quả đo của một lượt chạy; `None` = không ghi gì.

    `None` khi lượt chạy đã kết thúc/bị thay (`lock_run`), thuộc tầng khác, hoặc upload của
    lượt khác upload của bản vẽ `drawing_id` — kết quả muộn không được đè kết quả mới hơn
    (BE-00 §7). Còn lại ghi **đúng** giá trị truyền vào, không suy diễn thêm.
    """
    run = await lock_run(db, run_id=run_id)
    if run is None or run.floor_pk != floor_pk:
        return None
    drawing_stmt = select(DrawingRow.upload_id).where(DrawingRow.id == drawing_id, DrawingRow.floor_pk == floor_pk)
    if (await db.execute(drawing_stmt)).scalar_one_or_none() != run.upload_id:
        return None

    now = clock.now()
    saved = AssessmentRow(
        floor_pk=floor_pk,
        drawing_id=drawing_id,
        report=report_to_json(report, page_key=page_key, width_px=width_px, height_px=height_px, undo=undo),
        corners=_as_corners(corners),
        homography=dict(homography),
    )
    values = {
        "drawing_id": saved.drawing_id,
        "report": saved.report,
        "corners": None if saved.corners is None else [list(p) for p in saved.corners],
        "homography": saved.homography,
        "updated_at": now,
    }
    stmt = insert(QualityAssessmentRow).values(floor_pk=floor_pk, created_at=now, **values)
    await db.execute(stmt.on_conflict_do_update(index_elements=["floor_pk"], set_=values))
    return saved


async def load_assessment(db: AsyncSession, floor_pk: int, *, for_update: bool = False) -> AssessmentRow | None:
    """Dòng đo của một tầng; `for_update=True` khi người gọi sắp ghi (khoá dòng, BE-00 §7)."""
    stmt = select(QualityAssessmentRow).where(QualityAssessmentRow.floor_pk == floor_pk)
    if for_update:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None
    return AssessmentRow(row.floor_pk, row.drawing_id, row.report, _as_corners(row.corners), row.homography)


def _r4(value: float) -> float:
    """Kẹp [0, 1] rồi làm tròn 4 chữ số — dạng toạ độ trên dây."""
    return round(min(max(float(value), 0.0), 1.0), _DECIMALS)


def _region_out(region: Mapping[str, Any]) -> RegionOut:
    """Vùng từ JSON đã lưu, làm tròn và kẹp."""
    return RegionOut(**{key: _r4(region[key]) for key in ("xRatio", "yRatio", "widthRatio", "heightRatio")})


def _findings_out(report: Mapping[str, Any], *, level_id: str, drop_frame: bool) -> list[FindingOut]:
    """Phát hiện có `id` `"{level_id}.{code}.{n}.{u}"`; `n` đếm từ 1 trong từng mã theo `(y, x)`.

    `u` là ULID cuối của `pageKey` nên id đứng yên qua các lượt đọc cùng trang và đổi khi
    trang mới (khoá mới) — FE không giấu phát hiện còn lại dưới dấu "đã xử lý". Khoá không có
    ULID nào (dòng đo cũ hay khoá dựng tay) thì `u` là **cả khoá**: id vẫn ổn định và khác nhau
    giữa các trang, còn hơn để `IndexError` biến một lượt đọc thành 500 (NO-226).
    `drop_frame` bỏ `FRAME_NOT_FOUND` khi người dùng đã áp góc.
    """
    found = _ULID.findall(report["pageKey"])
    ulid = found[-1] if found else report["pageKey"]
    kept = [
        (finding, _region_out(finding["region"]))
        for finding in report["findings"]
        if not (drop_frame and finding["code"] == "FRAME_NOT_FOUND")
    ]
    kept.sort(key=lambda item: (QUALITY_CODES.index(item[0]["code"]), item[1].y_ratio, item[1].x_ratio))
    seen: Counter[str] = Counter()
    out = []
    for finding, region in kept:
        code = finding["code"]
        seen[code] += 1
        out.append(
            FindingOut(
                id=f"{level_id}.{code}.{seen[code]}.{ulid}", code=code, severity=finding["severity"], region=region
            )
        )
    return out


def _frame_out(report: Mapping[str, Any], *, corners_applied: bool) -> FrameOut:
    """Góc đã áp → `{isFound: true}`; không thì theo báo cáo, `corners` chỉ khi tìm thấy."""
    if corners_applied:
        return FrameOut(is_found=True)
    frame = report["frame"]
    if not frame["isFound"]:
        return FrameOut(is_found=False)
    return FrameOut(is_found=True, corners=[CornerOut(x_ratio=_r4(x), y_ratio=_r4(y)) for x, y in frame["corners"]])


def _floor_out(row: Row[Any], *, source_url: str) -> FloorQualityOut:
    """Một tầng từ một hàng của truy vấn `read_view`; chưa đo → chỉ `findings: []`."""
    report = row.report
    measured = report is not None and row.assessed_drawing_id == row.drawing_id and report["pageKey"] == row.page_key
    base = {"floor_id": row.level_id, "floor_name": row.name, "source_url": source_url, "is_measured": measured}
    if not measured:
        return FloorQualityOut(**base, findings=[])
    applied = row.corners is not None
    measurement = report["measurement"]
    return FloorQualityOut(
        **base,
        findings=_findings_out(report, level_id=row.level_id, drop_frame=applied),
        measurement=None if measurement is None else MeasurementOut.model_validate(measurement),
        frame=_frame_out(report, corners_applied=applied),
    )


async def read_view(
    db: AsyncSession, storage: ObjectStorage, *, project_id: str, level_id: str
) -> QualityAssessmentOut:
    """Dựng `ImageQualityAssessment` (#30, và 200 của #31/#32) bằng **một** truy vấn.

    `floors` = tầng chưa xoá **có bản vẽ đang dùng**, sắp `(floor_order, pk)`, ≤ 50; không
    tầng nào → 404 `upload`. `floorId` = `level_id` nếu tầng đó có bản vẽ, không thì phần tử
    đầu. Không kiểm `level_id` tồn tại: người gọi đã `get_floor` (404 `floor`).
    """
    stmt = (
        select(
            FloorRow.level_id,
            FloorRow.name,
            DrawingRow.id.label("drawing_id"),
            DrawingRow.page_key,
            QualityAssessmentRow.drawing_id.label("assessed_drawing_id"),
            QualityAssessmentRow.report,
            QualityAssessmentRow.corners,
        )
        .join(DrawingRow, DrawingRow.floor_pk == FloorRow.pk)
        .outerjoin(QualityAssessmentRow, QualityAssessmentRow.floor_pk == FloorRow.pk)
        .where(FloorRow.project_id == project_id, FloorRow.deleted_at.is_(None))
        .order_by(FloorRow.floor_order, FloorRow.pk)
        .limit(MAX_FLOORS)
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        raise NOT_FOUND.error(resource="upload")
    floors = [_floor_out(row, source_url=await drawing_url(storage, row.page_key)) for row in rows]
    focus = level_id if any(floor.floor_id == level_id for floor in floors) else floors[0].floor_id
    return QualityAssessmentOut(project_id=project_id, floor_id=focus, floors=floors)
