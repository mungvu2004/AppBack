"""Lõi bước `wallSegmentation`: ảnh trang → mặt nạ tường → `walls.json` + `walls.png`.

Tách khỏi `tasks.py` để chạy được **không** cần kho, broker hay vòng sự kiện: ba nhánh
bộ tách (giả, cổ điển, ONNX) chỉ khác nhau ở cách dựng mặt nạ, phần còn lại — kiểm khổ,
vector hoá, kẹp trần `MAX_WALLS`, đổi sang hợp đồng `WallPx` — dùng chung một đường mã
nên J06/M01 (cùng vào → cùng bytes) không phụ thuộc nhánh nào.

Nhánh cổ điển kẹp `confidence ≤ CLASSIC_CONFIDENCE_CAP`: đó là heuristic hình thái, B5-05
không được đọc nó chắc ngang một model đã huấn luyện.
"""

import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal, cast

import numpy as np
import onnxruntime as ort  # type: ignore[import-untyped]  # onnxruntime 1.30 không có py.typed
from numpy.typing import NDArray

from apps.ml.runtime.errors import MODEL_FORMAT_UNSUPPORTED
from apps.ml.walls.segformer import SegformerOnnxSegmenter
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.artifacts import MAX_WALLS, PointPx, WallPx, WallsResult, encode_mask, walls_to_json
from packages.ml_contracts.fakes import FakeWallSegmenter
from packages.ml_contracts.payloads import ModelRef
from packages.ml_contracts.ports import RgbImage
from packages.vision.preprocess.types import RgbImage as CheckedRgbImage
from packages.vision.walls.classic import classic_wall_mask, default_min_thickness_px
from packages.vision.walls.types import WallSegment
from packages.vision.walls.vectorize import keep_longest, vectorize_with_stats

__all__ = ["CLASSIC_CONFIDENCE_CAP", "WallsStepOutput", "segment_page", "to_wall_px"]

_log: Final = logging.getLogger(__name__)

CLASSIC_CONFIDENCE_CAP: Final = 0.5
"""Trần độ tin của đường lùi cổ điển: hình thái học không chắc bằng model đã huấn luyện."""

type Used = Literal["onnx", "classic", "fake"]


@dataclass(frozen=True, slots=True)
class WallsStepOutput:
    """Artifact của bước, kèm nhánh đã dùng và số phần tử bỏ (`spur`, `short`, `cap`).

    `used` và `dropped` không đi vào artifact — chúng là số đo cho log và test, còn
    `run_step` chỉ lấy `artifacts`.
    """

    artifacts: dict[str, bytes]
    used: Used
    dropped: Mapping[str, int]


def to_wall_px(seg: WallSegment) -> WallPx:
    """`WallSegment` (numpy thuần) → `WallPx` (hợp đồng), giữ nguyên từng con số.

    Làm tròn đã xong ở `vectorize_with_stats` ([6] bước 11); đổi kiểu ở đây mà tính lại
    số nào thì `walls.json` của cùng một mặt nạ sẽ lệch giữa hai lượt giao (J06).
    """
    return WallPx(
        start=PointPx(x=seg.start[0], y=seg.start[1]),
        end=PointPx(x=seg.end[0], y=seg.end[1]),
        thickness_px=seg.thickness_px,
        confidence=seg.confidence,
    )


def _mask_of(
    image: RgbImage,
    model: ModelRef,
    *,
    backend: str,
    session: ort.InferenceSession | None,
    px_per_paper_mm: float | None,
) -> tuple[NDArray[np.bool_], Used]:
    """Mặt nạ tường của trang và tên nhánh đã dựng nó.

    `ML_BACKEND=fake` thắng mọi thứ (M01: không model nào được nạp trong lượt giả);
    `ModelRef` cổ điển (`is_classic`) không có gì để nạp nên đi đường hình thái
    (`classic_wall_mask`: mở bỏ nét mảnh rồi lấp khe cửa sổ, nên mặt nạ có thể chứa điểm
    không có mực — dải giữa các nét cửa sổ, tường vẽ rỗng hai nét); còn lại
    `prepare` đã nạp `session` nên `cast` thay cho một nhánh chết không test nổi.

    Lệch khỏi prompt: `classic_wall_mask` nhận `RgbImage` của `packages.vision.preprocess`
    (dataclass có `.pixels`), không phải `ports.RgbImage` (alias mảng) — bọc ở đây, một view
    chỉ đọc trên chính mảng của `run_step`, không chép điểm ảnh.
    """
    if backend == "fake":
        return FakeWallSegmenter().segment(image), "fake"
    if model.is_classic:
        height, width = image.shape[:2]
        thickness = default_min_thickness_px(width, height, px_per_paper_mm)
        return classic_wall_mask(CheckedRgbImage(image), min_thickness_px=thickness), "classic"
    segmenter = SegformerOnnxSegmenter(cast("ort.InferenceSession", session))
    return segmenter.segment(image), "onnx"


def _capped(seg: WallSegment) -> WallSegment:
    """Cùng đoạn, độ tin không quá `CLASSIC_CONFIDENCE_CAP`."""
    if seg.confidence <= CLASSIC_CONFIDENCE_CAP:
        return seg
    return WallSegment(seg.start, seg.end, seg.thickness_px, CLASSIC_CONFIDENCE_CAP)


def segment_page(
    image: RgbImage,
    model: ModelRef,
    *,
    backend: str,
    session: ort.InferenceSession | None,
    px_per_paper_mm: float | None = None,
    run_id: str | None = None,
) -> WallsStepOutput:
    """Tách tường một trang đã nắn; cùng ảnh + cùng nhánh → cùng bytes artifact (J06, M01).

    Mặt nạ khác khổ ảnh là model sai hợp đồng, không phải trang xấu →
    `MODEL_FORMAT_UNSUPPORTED`. Quá `MAX_WALLS` đoạn thì giữ các đoạn dài nhất và đếm
    `cap`, vì `WallsResult` từ chối nhiều hơn thế.
    """
    started = time.monotonic()
    mask, used = _mask_of(image, model, backend=backend, session=session, px_per_paper_mm=px_per_paper_mm)
    mask_ms = _since(started)
    if mask.shape != image.shape[:2]:
        raise PermanentError(MODEL_FORMAT_UNSUPPORTED)
    vectorized = time.monotonic()
    result = vectorize_with_stats(mask)
    walls = result.walls
    dropped = {**result.dropped, "cap": max(0, len(walls) - MAX_WALLS)}
    if dropped["cap"]:
        walls = keep_longest(walls, MAX_WALLS)
    if used == "classic":
        walls = tuple(_capped(seg) for seg in walls)
    vector_ms = _since(vectorized)
    encoded = time.monotonic()
    artifacts = {
        "walls.json": walls_to_json(WallsResult(walls=tuple(to_wall_px(seg) for seg in walls))),
        "walls.png": encode_mask(mask),
    }
    _log.info(
        "walls_segmented",
        extra={
            "run_id": run_id,
            "used": used,
            "walls": len(walls),
            "dropped": dropped,
            "mask_ms": mask_ms,
            "vectorize_ms": vector_ms,
            "encode_ms": _since(encoded),
        },
    )
    return WallsStepOutput(artifacts=artifacts, used=used, dropped=dropped)


def _since(started: float) -> int:
    """Mili giây trôi qua từ một mốc `time.monotonic()`."""
    return int((time.monotonic() - started) * 1000)
