"""Dựng dữ liệu thử cho task đánh giá: payload, kho, ONNX tí hon đúng 11 nhãn artifact.

Model ONNX và kho chập chờn **nhập lại** từ `apps/ml/objects/tests` (cùng họ, cùng khuôn
đầu ra) chứ không dựng bộ thứ hai; ở đây chỉ còn phần riêng của `ml_eval`.
"""

from pathlib import Path
from typing import Final

import numpy as np
from numpy.typing import NDArray

from apps.ml.objects.labels import ARTIFACT_LABELS
from apps.ml.objects.tests.helpers import put_sync, some_id
from apps.ml.objects.tests.onnx_models import make_const_yolo, storage_ref, yolo_output
from apps.ml.runtime.settings import MlSettings
from apps.ml.runtime.tasks_util import InferContext
from packages.core.object_keys import model_prefix
from packages.ml_contracts.payloads import EvaluateVersionPayload, ModelRef
from packages.storage.local import LocalDiskStorage

OBJECTS: Final = "openingAndFurnitureDetection"
NUM_CLASSES: Final = len(ARTIFACT_LABELS)
"""11 nhãn (`OBJECT_LABELS + ("other",)`): `labels_for` của bản storage trả bảng này."""

SEEDS: Final = (100, 101, 102)
"""Ba seed của tập kiểm, đủ cho J01 mà không chạy cả 40 mặt bằng."""


def const_yolo(*, channels: int = 4 + NUM_CLASSES, size: int = 640) -> bytes:
    """ONNX hằng trả một hộp duy nhất; `channels` lệch `4 + 11` để thử đường hỏng (J03)."""
    output: NDArray[np.float32] = np.zeros((1, channels, 16), dtype=np.float32)
    if channels == 4 + NUM_CLASSES:
        output = yolo_output([(100.0, 100.0, 40.0, 40.0, 0, 0.9)], nc=NUM_CLASSES)
    return make_const_yolo(output, input_shape=(1, 3, size, size))


def eval_payload(ref: ModelRef) -> EvaluateVersionPayload:
    """Payload đánh giá của chính bản model `ref` (schema buộc cùng `version_id`)."""
    return EvaluateVersionPayload(version_id=str(ref.version_id), model=ref)


def stored_model(storage: LocalDiskStorage, data: bytes) -> EvaluateVersionPayload:
    """Ghi bytes model vào kho dạng storage rồi trả payload trỏ vào nó."""
    ref, key = storage_ref(data)
    put_sync(storage, key, data)
    return eval_payload(ref)


def pinned_ref(family: str) -> ModelRef:
    """`ModelRef` dạng storage của một họ: đủ hợp lệ cho đường bộ giả (không nạp model nào).

    Dùng dạng storage chứ không dạng ghim vì họ `wallSegmentation` không có bản ghim nào
    mang ONNX, mà `ML_BACKEND=fake` thì không đường nào chạm tới trọng số.
    """
    version = some_id("mdl")
    return ModelRef(
        version_id=version,
        family=family,
        weights_key=f"{model_prefix(version)}model.onnx",
        pinned_name=None,
        checksum_sha256="0" * 64,
    )


def context(storage: LocalDiskStorage, models_dir: Path, *, backend: str = "onnx") -> InferContext:
    """Ngữ cảnh worker trỏ vào kho và thư mục model của test."""
    return InferContext(
        storage=storage,
        settings=MlSettings(ml_backend=backend, ml_models_dir=str(models_dir), ml_ort_threads=1),
    )


def pinned_yolo_ref() -> ModelRef:
    """`ModelRef` **ghim** `yolov8n` của họ dò vật (nhãn COCO, `labels_for` trả `COCO_LABELS`)."""
    return ModelRef(
        version_id=some_id("mdl"),
        family=OBJECTS,
        weights_key=None,
        pinned_name="yolov8n",
        checksum_sha256="0" * 64,
    )
