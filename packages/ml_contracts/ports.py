"""Cổng suy luận và huấn luyện: bộ chạy ONNX (B5-02…B5-04) và bộ giả (`fakes.py`) cùng một mặt.

Ảnh vào mọi cổng suy luận là trang đã nắn RGB 8 bit `(H, W, 3)` (HOP-DONG-MOI §4.2);
kết quả theo pixel của chính ảnh đó. Trainer (B6-04a/b) nhận thư mục dataset đã kiểm
manifest và báo tiến độ qua `TrainReporter`, không tự nói chuyện với hàng đợi.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

import numpy as np
from numpy.typing import NDArray

from packages.ml_contracts.artifacts import DetectionPx, TextPx
from packages.ml_contracts.families import MetricName, TrainableFamily
from packages.ml_contracts.payloads import MetricPoint

type RgbImage = NDArray[np.uint8]
type LogParam = str | int | float | bool


class WallSegmenter(Protocol):
    """Ảnh trang → mặt nạ tường `(H, W)` bool, cùng khổ ảnh."""

    def segment(self, image: RgbImage) -> NDArray[np.bool_]: ...


class ObjectDetector(Protocol):
    """Ảnh trang → ô mở và đồ đạc."""

    def detect(self, image: RgbImage) -> tuple[DetectionPx, ...]: ...


class TextReader(Protocol):
    """Ảnh trang → chuỗi đọc được (kích thước, nhãn phòng) kèm hộp."""

    def read(self, image: RgbImage) -> tuple[TextPx, ...]: ...


@dataclass(frozen=True, slots=True)
class TrainSpec:
    """Tham số một lượt huấn luyện; `seed` để lượt chạy tái lập được (M06)."""

    job_id: str
    family: TrainableFamily
    base_model: str
    epochs: int
    device: Literal["cpu", "cuda"]
    seed: int


class TrainReporter(Protocol):
    """Kênh trainer báo ra ngoài; `cancelled()` phải được hỏi giữa mọi bước (BE-00 §9)."""

    def heartbeat(self, epoch: int) -> None: ...

    def metric(self, point: MetricPoint) -> None: ...

    def log(
        self, level: Literal["info", "warning", "error"], template: str, params: Mapping[str, LogParam]
    ) -> None: ...

    def cancelled(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class TrainResult:
    """ONNX đã xuất (qua `export_onnx`) và đúng một số đo của họ."""

    onnx_path: Path
    metrics: Mapping[MetricName, float]


class Trainer(Protocol):
    """Một họ huấn luyện được; `discover_trainers` dò `apps.ml.<module>.trainer.TRAINER`."""

    @property
    def family(self) -> TrainableFamily: ...

    def train(self, spec: TrainSpec, data_dir: Path, out_dir: Path, reporter: TrainReporter) -> TrainResult: ...
