"""Gộp số đo và phát hiện chất lượng của một ảnh thành `QualityReport` (khối [6]).

Gói này **không** sinh id phát hiện, `sourceUrl` hay `expectedConfidence` (B2-05b làm)
và không đặt câu tiếng Việt vào `Finding`: mọi chữ hiển thị do FE dựng từ `code`, nên
BE chỉ trả mã, mức, vùng và số đo.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Literal

from packages.vision.preprocess.geometry import (
    SkewEstimate,
    WorkingImage,
    estimate_skew,
    find_frame_working,
    working_gray,
)
from packages.vision.preprocess.types import Quad, RgbImage
from packages.vision.quality.metrics import (
    WHOLE_IMAGE,
    Measurement,
    Region,
    contrast_score,
    densest_noise_region,
    lowest_contrast_region,
    noise_score,
    round_score,
    round_skew,
)
from packages.vision.quality.thresholds import (
    Level,
    classify_contrast,
    classify_noise,
    classify_perspective,
    classify_resolution,
    classify_skew,
    worst_level,
)

QUALITY_CODES: Final = (
    "RESOLUTION_TOO_LOW",
    "SKEW_DETECTED",
    "FRAME_NOT_FOUND",
    "LOW_CONTRAST",
    "HIGH_NOISE",
    "SKEW_NOT_MEASURED",
    "PERSPECTIVE_DETECTED",
)
"""Mã chất lượng, cũng là **thứ tự** phát hiện trong báo cáo.

Năm mã đầu của HOP-DONG-MOI §7.4; hai mã cuối thêm cho G3-35 và nối **sau** để chỉ số
của năm mã cũ (dùng để sắp phát hiện ở `apps/api/quality`) không đổi:
`SKEW_NOT_MEASURED` = quá ít đoạn để đo nghiêng (`skewDeg` 0 lúc đó không có nghĩa
"thẳng"); `PERSPECTIVE_DETECTED` = méo hình thang, "Tự động nắn" (chỉ xoay) không sửa
được, phải chọn bốn góc (#31). FE nhận mã lạ mà không hỏng (`code` là chuỗi tự do).
"""

Severity = Literal["attention", "poor"]

_FRAME_NOT_FOUND_REGION: Final = Region(0.02, 0.02, 0.96, 0.96)
"""Vùng gợi ý khi không thấy khung: gần hết ảnh, chừa 2 % mỗi mép (khối [6])."""


@dataclass(frozen=True, slots=True)
class Finding:
    """Một phát hiện chất lượng: mã, mức, vùng và số đo đã làm tròn sinh ra nó.

    `metrics` được bọc `MappingProxyType` nên người giữ `Finding` không sửa được số
    đo đã chốt; mức chỉ có `attention` hoặc `poor` vì `good` thì không sinh phát hiện.
    """

    code: str
    severity: Severity
    region: Region
    metrics: Mapping[str, float]

    def __post_init__(self) -> None:
        """Bọc `metrics` thành `MappingProxyType` để số đo đã chốt không sửa được sau khi phát
        hiện đã sinh — người giữ `Finding` không đổi được con số mà FE sẽ hiện."""
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))


@dataclass(frozen=True, slots=True)
class QualityReport:
    """Số đo, danh sách phát hiện theo thứ tự `QUALITY_CODES`, và khung tìm được (nếu có)."""

    measurement: Measurement
    findings: tuple[Finding, ...]
    frame: Quad | None

    @property
    def level(self) -> Level:
        """Mức tệ nhất trong các phát hiện; không phát hiện nào → `"good"`."""
        return worst_level([finding.severity for finding in self.findings])


def _measure_working(img: RgbImage, work: WorkingImage) -> tuple[Measurement, SkewEstimate]:
    """Số đo trên bản làm việc đã dựng sẵn, kèm kết quả thô của bước đo nghiêng.

    Tách khỏi `measure` để `assess` dùng lại cả bản làm việc lẫn hộp bao, cờ đã đo và
    độ hội tụ mà không đo
    hai lần. Kích thước lấy của ảnh **gốc**, ba số còn lại của bản làm việc; cả ba đã
    làm tròn đúng số chữ số lên dây vì phân loại chạy trên chính số đã làm tròn.
    """
    skew = estimate_skew(work)
    measurement = Measurement(
        width_px=img.width_px,
        height_px=img.height_px,
        skew_deg=round_skew(skew.angle_deg),
        contrast_score=round_score(contrast_score(work.gray)),
        noise_score=round_score(noise_score(work.gray)),
    )
    return measurement, skew


def measure(img: RgbImage) -> Measurement:
    """Bốn số đo chất lượng của một ảnh, đã làm tròn (2 chữ số góc, 3 chữ số hai điểm)."""
    return _measure_working(img, working_gray(img))[0]


def _bbox_region(bbox: tuple[float, float, float, float] | None, width_px: int, height_px: int) -> Region:
    """Hộp bao `(x0, y0, x1, y1)` pixel ảnh gốc → `Region` tỉ lệ; `None` (< 4 đoạn) → cả ảnh.

    Kẹp về `[0, 1]`: hộp bao đổi từ bản làm việc sang ảnh gốc bằng phép chia cho
    `scale` nên có thể lố ra ngoài mép vài phần nghìn pixel.
    """
    if bbox is None:
        return WHOLE_IMAGE
    x0, x1 = (min(max(v / width_px, 0.0), 1.0) for v in (bbox[0], bbox[2]))
    y0, y1 = (min(max(v / height_px, 0.0), 1.0) for v in (bbox[1], bbox[3]))
    return Region(x0, y0, x1 - x0, y1 - y0)


def assess(img: RgbImage) -> QualityReport:
    """Số đo + phát hiện của một ảnh; thứ tự phát hiện cố định như `QUALITY_CODES`.

    Dựng bản làm việc **một lần** rồi truyền cho cả phần đo lẫn `find_frame_working`.
    Mỗi mã tối đa một phát hiện và chỉ sinh khi mức khác `good`, nên ảnh sạch, thẳng,
    có khung, đủ phân giải cho `findings` rỗng và `level == "good"`. Không đo được
    nghiêng (`SKEW_NOT_MEASURED`) hay méo hình thang (`PERSPECTIVE_DETECTED`) kéo mức
    xuống khỏi `good` (G3-35).
    """
    work = working_gray(img)
    measurement, estimate = _measure_working(img, work)
    bbox = estimate.segments_bbox
    frame = find_frame_working(work)
    findings: list[Finding] = []

    short_edge = float(min(measurement.width_px, measurement.height_px))
    resolution = classify_resolution(short_edge)
    if resolution != "good":
        findings.append(Finding(QUALITY_CODES[0], resolution, WHOLE_IMAGE, {"shortEdgePx": short_edge}))

    skew = classify_skew(measurement.skew_deg)
    if skew != "good":
        region = _bbox_region(bbox, measurement.width_px, measurement.height_px)
        findings.append(Finding(QUALITY_CODES[1], skew, region, {"skewDeg": measurement.skew_deg}))

    if frame is None:
        findings.append(Finding(QUALITY_CODES[2], "attention", _FRAME_NOT_FOUND_REGION, {}))

    contrast = classify_contrast(measurement.contrast_score)
    if contrast != "good":
        region = lowest_contrast_region(work.gray)
        findings.append(Finding(QUALITY_CODES[3], contrast, region, {"contrastScore": measurement.contrast_score}))

    noise = classify_noise(measurement.noise_score)
    if noise != "good":
        region = densest_noise_region(work.gray)
        findings.append(Finding(QUALITY_CODES[4], noise, region, {"noiseScore": measurement.noise_score}))

    if not estimate.is_measured:
        findings.append(Finding(QUALITY_CODES[5], "attention", WHOLE_IMAGE, {}))

    perspective = classify_perspective(estimate.perspective_deg)
    if perspective != "good" and estimate.perspective_deg is not None:
        region = _bbox_region(bbox, measurement.width_px, measurement.height_px)
        metrics = {"perspectiveDeg": round_skew(estimate.perspective_deg)}
        findings.append(Finding(QUALITY_CODES[6], perspective, region, metrics))

    return QualityReport(measurement, tuple(findings), frame)
