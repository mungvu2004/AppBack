"""Task `ml.infer.objects.detect`: bước `openingAndFurnitureDetection` của lượt pipeline (BE-00 §7, §9).

Thân task chỉ là khuôn `run_step` của B5-01 — đọc trang, chạy bộ phát hiện, ghi
`objects.json`, gửi `step_done` — nên luật riêng của bước nằm ở `prepare`: họ model phải
đúng, `ML_BACKEND=fake` không nạp ONNX nào, và `ModelRef` cổ điển (chưa có bản kích hoạt
cho họ ô mở/đồ đạc) trả kết quả rỗng + `completed` thay vì hỏng lượt (như `apps.ml.text`).

Luôn CPU: bước này không gọi `resolve_device` và không bao giờ giữ khoá `gpu:0` (M04).
"""

import logging
from pathlib import Path
from typing import Final, cast

import numpy as np
from numpy.typing import NDArray

from apps.ml.objects.detector import YoloOnnxDetector
from apps.ml.objects.labels import labels_for
from apps.ml.runtime.loader import load_onnx
from apps.ml.runtime.tasks_util import StepOutput, infer_context, run_step, step_failed
from packages.messaging.tasks import PermanentError, define_task
from packages.ml_contracts.artifacts import DetectionPx, ObjectsResult, objects_to_json
from packages.ml_contracts.fakes import FakeObjectDetector
from packages.ml_contracts.payloads import InferStepPayload
from packages.ml_contracts.ports import ObjectDetector, RgbImage

__all__ = ["MODEL_VERSION_FAMILY_MISMATCH", "STEP", "objects_detect"]

_log: Final = logging.getLogger(__name__)

STEP: Final = "openingAndFurnitureDetection"
MODEL_VERSION_FAMILY_MISMATCH: Final = "MODEL_VERSION_FAMILY_MISMATCH"
"""Payload trỏ bước hay họ model khác — hằng chuỗi, không khai trong `ERRORS` ([2]).

Nợ: nên về `apps/ml/runtime/errors.py` (chủ B5-01) khi B5-02/B5-03/B5-04 hết khai trùng.
"""


class _InactiveDetector:
    """Bộ phát hiện của họ chưa có bản kích hoạt: trang nào cũng không có ô mở/đồ đạc nào."""

    def detect(self, image: RgbImage) -> tuple[DetectionPx, ...]:
        """Luôn rỗng; bước vẫn `completed` để lượt pipeline chạy tiếp."""
        return ()


async def _prepare(payload: InferStepPayload) -> ObjectDetector:
    """Chọn bộ phát hiện của lượt: bộ giả, bộ rỗng, hay `YoloOnnxDetector` trên model đã kiểm.

    `InferStepPayload` buộc `step == model.family`, nên kiểm `step` là kiểm cả hai (như
    `apps.ml.walls`, `apps.ml.text`). Model chỉ tới được `onnxruntime` qua `load_onnx`
    (checksum, luật ONNX không tin, M02/M03); mọi lỗi của nó đã là `PermanentError` có mã.

    Lệch khỏi prompt [6] bước 3: điều kiện "`ModelRef` không trỏ model nào" viết bằng
    `payload.model.is_classic` (đúng nghĩa "`weights_key`, `pinned_name` đều `None`").
    """
    if payload.step != STEP:
        raise PermanentError(MODEL_VERSION_FAMILY_MISMATCH)
    context = infer_context()
    if context.settings.ml_backend == "fake":
        return FakeObjectDetector()
    if payload.model.is_classic:
        _log.info("objects_model_inactive", extra={"run_id": payload.run_id})
        return _InactiveDetector()
    models_dir = Path(context.settings.ml_models_dir)
    session = await load_onnx(context.storage, payload.model, models_dir=models_dir)
    return YoloOnnxDetector(session, labels_for(payload.model))


def _detect(image: NDArray[np.uint8], payload: InferStepPayload, detector: ObjectDetector | None) -> StepOutput:
    """Artifact `objects.json` của bước.

    `detector` khai `| None` vì chữ ký chung của `run_step` cho phép bước không có
    `prepare`; bước này luôn có nên `cast` thay cho một nhánh chết không test nổi.
    """
    detections = cast("ObjectDetector", detector).detect(image)
    return StepOutput({"objects.json": objects_to_json(ObjectsResult(detections=detections))})


@define_task(name="ml.infer.objects.detect", payload=InferStepPayload, on_failed=step_failed)
async def objects_detect(payload: InferStepPayload) -> None:
    """Phát hiện ô mở và đồ đạc trên một trang đã nắn, ghi `objects.json` (J01, J06)."""
    await run_step(payload, _detect, storage=infer_context().storage, prepare=_prepare)
