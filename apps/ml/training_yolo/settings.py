"""Hằng kỹ thuật một lượt huấn luyện YOLO (khối [2] B6-04b); chỉ thư viện chuẩn ở mức module.

`trainer` nhập module này lúc `discover_trainers()`, nên ở đây không có `torch`/`ultralytics`.
Batch luôn là `int`: `ultralytics` hiểu số thực là bật AutoBatch (dò bộ nhớ GPU, không tất định).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

__all__ = ["YoloTrainSettings"]


def _default_cuda_batch() -> Mapping[str, int]:
    """Batch trên GPU 6 GB @ `imgsz=640`, AMP (ENV §1); đo lại bằng `test_gpu`."""
    return MappingProxyType({"yolov8n": 16, "yolov8s": 8})


@dataclass(frozen=True, slots=True)
class YoloTrainSettings:
    """`imgsz` cũng là cạnh lát dataset (cùng lưới suy luận B5-03); `background_keep_every` giữ 1/k lát nền."""

    imgsz: int = 640
    batch_cpu: int = 4
    batch_cuda: Mapping[str, int] = field(default_factory=_default_cuda_batch)
    workers: int = 0
    heartbeat_every_s: float = 60
    background_keep_every: int = 4
