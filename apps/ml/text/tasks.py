"""Task `ml.infer.text.read`: bước `dimensionReading` của lượt pipeline (BE-00 §7, §9).

Thân task chỉ là khuôn `run_step` của B5-01 — đọc trang, chạy bộ đọc, ghi `text.json`,
gửi `step_done` — nên ba luật riêng của bước nằm hết ở `prepare`: họ model phải đúng,
`ML_BACKEND=fake` không nạp ONNX nào, và `ModelRef` cổ điển (chưa có bản kích hoạt cho
họ đọc chữ) trả kết quả rỗng + `completed` thay vì hỏng lượt — B5-05 khi ấy lùi về tỉ
lệ khai ở dự án chứ không đoán (K19).

Luôn CPU: bước này không gọi `resolve_device` và không bao giờ giữ khoá `gpu:0`.
"""

import logging
from pathlib import Path
from typing import Final, cast

import numpy as np
from numpy.typing import NDArray

from apps.ml.runtime.loader import load_onnx
from apps.ml.runtime.tasks_util import StepOutput, infer_context, run_step, step_failed
from apps.ml.text.reader import RapidOcrReader
from packages.messaging.tasks import PermanentError, define_task
from packages.ml_contracts.artifacts import TextPx, TextResult, text_to_json
from packages.ml_contracts.fakes import FakeTextReader
from packages.ml_contracts.payloads import InferStepPayload
from packages.ml_contracts.ports import RgbImage, TextReader

__all__ = ["MODEL_VERSION_FAMILY_MISMATCH", "STEP", "text_read"]

_log: Final = logging.getLogger(__name__)

STEP: Final = "dimensionReading"
MODEL_VERSION_FAMILY_MISMATCH: Final = "MODEL_VERSION_FAMILY_MISMATCH"
"""Payload trỏ bước hay họ model khác — hằng chuỗi, không khai trong `ERRORS` ([2])."""


class _InactiveReader:
    """Bộ đọc của họ chưa có bản kích hoạt: trang nào cũng không có chữ nào."""

    def read(self, image: RgbImage) -> tuple[TextPx, ...]:
        """Luôn rỗng; bước vẫn `completed` để lượt pipeline chạy tiếp."""
        return ()


async def _prepare(payload: InferStepPayload) -> TextReader:
    """Chọn bộ đọc của lượt: bộ giả, bộ rỗng, hay `RapidOcrReader` trên model đã kiểm.

    Model chỉ tới được `onnxruntime` qua `load_onnx` (checksum, luật ONNX không tin,
    M02/M03); mọi lỗi của nó đã là `PermanentError` có mã nên không bọc thêm gì.
    """
    if payload.step != STEP or payload.model.family != STEP:
        raise PermanentError(MODEL_VERSION_FAMILY_MISMATCH)
    context = infer_context()
    if context.settings.ml_backend == "fake":
        return FakeTextReader()
    if payload.model.is_classic:
        _log.info("text_model_inactive", extra={"run_id": payload.run_id})
        return _InactiveReader()
    models_dir = Path(context.settings.ml_models_dir)
    session = await load_onnx(context.storage, payload.model, models_dir=models_dir)
    return RapidOcrReader.from_session(session, pinned_name=payload.model.pinned_name)


def _read(image: NDArray[np.uint8], payload: InferStepPayload, reader: TextReader | None) -> StepOutput:
    """Artifact `text.json` của bước.

    `reader` khai `| None` vì chữ ký chung của `run_step` cho phép bước không có
    `prepare`; bước này luôn có nên `cast` thay cho một nhánh chết không test nổi.
    """
    items = cast("TextReader", reader).read(image)
    return StepOutput({"text.json": text_to_json(TextResult(items=items))})


@define_task(name="ml.infer.text.read", payload=InferStepPayload, on_failed=step_failed)
async def text_read(payload: InferStepPayload) -> None:
    """Đọc chữ kích thước và nhãn phòng của một trang đã nắn, ghi `text.json` (J01, J06)."""
    await run_step(payload, _read, storage=infer_context().storage, prepare=_prepare)
