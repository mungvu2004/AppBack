"""Task `ml.infer.walls.segment`: bước `wallSegmentation` của lượt pipeline (BE-00 §7, §9).

Thân task chỉ là khuôn `run_step` của B5-01 — đọc trang, chạy bộ tách, ghi `walls.json` và
`walls.png`, gửi `step_done` — nên luật riêng của bước nằm ở `prepare` và ở `step.py`.
`prepare` chạy **trước** khi đọc trang, nên payload sai họ hỏng mà không tốn một lượt tải
trang, và mã hỏng của bộ nạp model (M02, M03) tới thẳng B5-06c.

Khác `apps.ml.text`: họ tường **không có bản gốc**, `ModelRef` cổ điển không phải "chưa
kích hoạt" mà là đường lùi hình thái thật sự — nên `prepare` chỉ trả `None` và `step.py`
chọn nhánh. Luôn CPU: bước này không gọi `resolve_device`, không giữ khoá `gpu:0`.
"""

import asyncio
import logging
from pathlib import Path
from typing import Final

import numpy as np
import onnxruntime as ort  # type: ignore[import-untyped]  # onnxruntime 1.30 không có py.typed
from numpy.typing import NDArray

from apps.ml.runtime.errors import MODEL_VERSION_FAMILY_MISMATCH
from apps.ml.runtime.loader import load_onnx
from apps.ml.runtime.tasks_util import StepOutput, infer_context, run_step, step_failed
from apps.ml.walls.step import segment_page
from packages.messaging.tasks import PermanentError, define_task
from packages.ml_contracts.payloads import InferStepPayload
from packages.storage.port import ObjectStorage, read_all_capped
from packages.vision.walls.pdf_walls import VECTORS_MAX_BYTES, PageVectors

__all__ = ["MODEL_VERSION_FAMILY_MISMATCH", "STEP", "segment_walls"]

_log: Final = logging.getLogger(__name__)

STEP: Final = "wallSegmentation"

type _Prepared = tuple[ort.InferenceSession | None, PageVectors | None]


class _VectorsUnusableError(Exception):
    """`vectors.json` thiếu hay quá trần — bước lùi về vector hoá mặt nạ, không hỏng."""


async def _read_vectors(storage: ObjectStorage, payload: InferStepPayload) -> PageVectors | None:
    """Nét PDF của trang (`payload.vectors_key`), hay `None` khi không có hoặc không dùng được.

    Nét PDF chỉ là đường tốt hơn cho trang vector, mặt nạ vẫn đủ dựng tường: object thiếu, quá
    `VECTORS_MAX_BYTES` hay hỏng dạng → log cảnh báo (không khoá object) rồi `None`. Lỗi tạm của
    kho vẫn nổi lên để hàng đợi thử lại.
    """
    if payload.vectors_key is None:
        return None
    try:
        data = await read_all_capped(
            storage,
            payload.vectors_key,
            max_bytes=VECTORS_MAX_BYTES,
            too_large=_VectorsUnusableError,
            on_missing=_VectorsUnusableError,
        )
        return await asyncio.to_thread(PageVectors.from_json, data)
    except (_VectorsUnusableError, ValueError, RecursionError) as exc:
        _log.warning("walls_vectors_unusable", extra={"run_id": payload.run_id, "reason": type(exc).__name__})
        return None


async def _prepare(payload: InferStepPayload) -> _Prepared:
    """Phiên ONNX của lượt (hay `None` khi lượt không nạp model nào) và nét PDF của trang.

    `InferStepPayload` buộc `step == model.family`, nên kiểm `step` là kiểm cả hai. Bộ giả
    và đường cổ điển không đụng tới `load_onnx`; model thật chỉ tới `onnxruntime` qua nó
    (checksum, luật ONNX không tin, M02/M03) và mọi lỗi của nó đã có mã nên không bọc thêm.
    """
    if payload.step != STEP:
        raise PermanentError(MODEL_VERSION_FAMILY_MISMATCH)
    context = infer_context()
    vectors = await _read_vectors(context.storage, payload)
    if context.settings.ml_backend == "fake" or payload.model.is_classic:
        return None, vectors
    models_dir = Path(context.settings.ml_models_dir)
    return await load_onnx(context.storage, payload.model, models_dir=models_dir), vectors


def _segment(image: NDArray[np.uint8], payload: InferStepPayload, prepared: _Prepared | None) -> StepOutput:
    """Hai artifact của bước; `backend` đọc lại từ ngữ cảnh tiến trình như `prepare` đã đọc."""
    session, vectors = prepared or (None, None)
    output = segment_page(
        image,
        payload.model,
        backend=infer_context().settings.ml_backend,
        session=session,
        px_per_paper_mm=payload.px_per_paper_mm,
        run_id=payload.run_id,
        vectors=vectors,
    )
    return StepOutput(output.artifacts)


@define_task(name="ml.infer.walls.segment", payload=InferStepPayload, on_failed=step_failed)
async def segment_walls(payload: InferStepPayload) -> None:
    """Tách tường một trang đã nắn, ghi `walls.json` và `walls.png` (J01, J06)."""
    await run_step(payload, _segment, storage=infer_context().storage, prepare=_prepare)
