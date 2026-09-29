"""Nhãn artifact và bảng nhãn theo model (B5-03 khối [1] "Nhãn", [6] "Model").

`ARTIFACT_LABELS` là mọi nhãn hợp lệ trong `objects.json`. Model ghim `yolov8n`/`yolov8s`
là YOLO COCO gốc (chưa huấn luyện lại): đầu ra của chúng là chỉ số lớp COCO, không phải
`ObjectLabel` — `COCO_LABELS` dịch **thẳng tại suy luận**, không sinh nhãn miền.

Lệch khỏi prompt: `COCO_TO_LABEL` khoá bằng tên lớp COCO (`"chair"`, …), không theo chỉ
số; bảng chỉ số → tên cho 6 lớp mượn của B5-03 khối [6] đứng ở đây rồi tra `COCO_TO_LABEL`.
Lệch khỏi prompt: `get_args(DetectionLabel)` trả lồng (`(Literal[...], Literal["other"])`,
`DetectionLabel = ObjectLabel | Literal["other"]` là Union hai vế) chứ không phải tuple
chuỗi phẳng — làm phẳng bằng `get_args` trên từng vế rồi nối.
"""

from collections.abc import Sequence
from typing import Final, get_args

from packages.ml_contracts.labels import COCO_TO_LABEL, DetectionLabel
from packages.ml_contracts.payloads import ModelRef

ARTIFACT_LABELS: Final[tuple[DetectionLabel, ...]] = tuple(
    label for part in get_args(DetectionLabel) for label in get_args(part)
)

_COCO_CLASS_NAMES: Final[dict[int, str]] = {
    56: "chair",
    57: "couch",
    59: "bed",
    60: "dining table",
    61: "toilet",
    71: "sink",
}
"""Chỉ số lớp COCO gốc → tên lớp, chỉ 6 lớp bảng khối [6] giữ lại; còn lại bỏ (`None`)."""

COCO_LABELS: Final[tuple[DetectionLabel | None, ...]] = tuple(
    COCO_TO_LABEL.get(_COCO_CLASS_NAMES.get(i, "")) for i in range(80)
)

PINNED_COCO_MODELS: Final = frozenset({"yolov8n", "yolov8s"})


def labels_for(ref: ModelRef) -> tuple[DetectionLabel | None, ...]:
    """Bảng nhãn theo chỉ số lớp của model: COCO gốc cho model ghim, artifact cho model đã huấn luyện."""
    if ref.pinned_name in PINNED_COCO_MODELS:
        return COCO_LABELS
    return ARTIFACT_LABELS


def check_labels(labels: Sequence[str | None]) -> None:
    """Mọi nhãn ngoài `ARTIFACT_LABELS` (và khác `None`) là lỗi cấu hình model → `ValueError`.

    Lệch khỏi prompt: prompt đặt luật này ở khối [6] "Model" (gọi trong
    `YoloOnnxDetector.__init__`); để ở `labels.py` để B nhập được mà không lặp lại tập nhãn.
    """
    valid = set(ARTIFACT_LABELS)
    bad = [label for label in labels if label is not None and label not in valid]
    if bad:
        raise ValueError(f"nhãn ngoài ARTIFACT_LABELS: {bad}")
