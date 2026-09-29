"""Dựng dữ liệu thử cho `apps.ml.walls`: payload bước, `ModelRef` dạng storage, kho đồng bộ.

Chép khuôn từ `apps/ml/text/tests/helpers.py` chứ **không** nhập chéo: mỗi prompt sở hữu
thư mục của mình (BE-00 §2), và hai bước khác nhau ở họ model lẫn artifact.

Model ONNX tí hon nằm ở `onnx_fixtures.py` (cùng prompt, việc khác); `onnx_ref` nhập nó
**trong thân hàm** để các test không đụng ONNX vẫn nạp được module này.
"""

import asyncio
import hashlib

from packages.core.clock import SystemClock
from packages.core.ids import IdPrefix, new_id
from packages.core.object_keys import model_prefix
from packages.ml_contracts.payloads import InferStepPayload, ModelRef
from packages.storage.port import ObjectStorage

STEP = "wallSegmentation"


def some_id(prefix: IdPrefix) -> str:
    """Id mới đúng tiền tố (`run`, `mdl`, `upl`, …)."""
    return new_id(prefix, SystemClock())


def classic_ref() -> ModelRef:
    """`ModelRef` dạng cổ điển của họ tường: không có gì để nạp, bước đi đường hình thái."""
    return ModelRef(version_id=None, family=STEP, weights_key=None, pinned_name=None, checksum_sha256="")


def storage_ref(data: bytes, *, checksum: str | None = None) -> tuple[ModelRef, str]:
    """`ModelRef` dạng storage cho bytes trọng số, kèm khoá object phải ghi vào kho."""
    version = some_id("mdl")
    key = f"{model_prefix(version)}model.onnx"
    digest = checksum if checksum is not None else hashlib.sha256(data).hexdigest()
    return ModelRef(version_id=version, family=STEP, weights_key=key, pinned_name=None, checksum_sha256=digest), key


def infer_payload(
    *,
    width: int,
    height: int,
    model_ref: ModelRef | None = None,
    step: str = STEP,
    px_per_paper_mm: float | None = None,
) -> InferStepPayload:
    """Payload bước suy luận hợp lệ; model mặc định là dạng cổ điển của chính `step`."""
    prefix = f"projects/{some_id('prj')}/floors/L-ABCDEFGHIJ/uploads/{some_id('upl')}/"
    run = some_id("run")
    ref = model_ref or ModelRef(version_id=None, family=step, weights_key=None, pinned_name=None, checksum_sha256="")
    return InferStepPayload(
        run_id=run,
        step=step,
        page_key=f"{prefix}pages/0.png",
        width_px=width,
        height_px=height,
        artifact_prefix=f"{prefix}runs/{run}/{step}/",
        model=ref,
        px_per_paper_mm=px_per_paper_mm,
    )


def put_sync(storage: ObjectStorage, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    """Ghi một object từ test đồng bộ (worker thật chạy ngoài vòng sự kiện của test)."""
    asyncio.run(storage.put(key, data, content_type=content_type, max_bytes=len(data) + 1))


def read_sync(storage: ObjectStorage, key: str) -> bytes | None:
    """Nội dung object, hay `None` khi chưa có."""

    async def read() -> bytes | None:
        if await storage.stat(key) is None:
            return None
        return b"".join([chunk async for chunk in storage.open_read(key)])

    return asyncio.run(read())


def onnx_ref(storage: ObjectStorage, *, wrong_output: bool = False, checksum: str | None = None) -> ModelRef:
    """Ghi model SegFormer tí hon vào kho và trả `ModelRef` trỏ nó.

    `wrong_output=True` dựng bản ra `[1, 3, 256, 256]` — hình mà `SegformerOnnxSegmenter`
    phải từ chối (J03).
    """
    from apps.ml.walls.tests.onnx_fixtures import make_threshold_segformer, make_wrong_output_segformer

    data = make_wrong_output_segformer() if wrong_output else make_threshold_segformer()
    ref, key = storage_ref(data, checksum=checksum)
    put_sync(storage, key, data)
    return ref
