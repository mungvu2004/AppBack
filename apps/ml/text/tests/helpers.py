"""Dựng dữ liệu thử cho `apps.ml.text`: model nhận dạng tí hon, payload, kho hỏng tạm.

Model rec tí hon trả **hằng** cùng một mảng xác suất cho mọi ảnh vào (BE-00 §9 "Test":
model tí hon dựng trong test, không tải mạng), nên test task khẳng định được chuỗi đọc
ra mà không phụ thuộc chất lượng OCR thật — phần OCR thật đo riêng ở `test_reader_real`.
"""

import asyncio
import hashlib
from collections.abc import AsyncIterator, Sequence
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort  # type: ignore[import-untyped]  # onnxruntime 1.30 không có py.typed
from onnx import TensorProto, helper, numpy_helper

from apps.ml.runtime.loader import load_onnx
from packages.core.clock import SystemClock
from packages.core.errors import AppError
from packages.core.ids import IdPrefix, new_id
from packages.core.object_keys import model_prefix
from packages.ml_contracts.payloads import InferStepPayload, ModelRef
from packages.ml_contracts.pinned import PINNED
from packages.storage.local import LocalDiskStorage
from packages.storage.port import CHUNK_SIZE, ObjectStorage

STEP = "dimensionReading"
DIGITS = ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", ".")
"""Metadata `character` của model tí hon: mỗi dòng đúng một ký tự, như model thật."""

CHARACTERS = ("blank", *DIGITS, " ")
CONSTANT_TEXT = "3.600"
HIT_PROB = 0.9

_SEQUENCE = (
    CHARACTERS.index("3"),
    CHARACTERS.index("."),
    CHARACTERS.index("6"),
    CHARACTERS.index("0"),
    0,  # blank xen giữa: hai số 0 liền nhau không bị gộp
    CHARACTERS.index("0"),
)


def constant_probs(classes: int = len(CHARACTERS)) -> np.ndarray:
    """Mảng `(1, T, C)` mà mọi bước đều argmax về đúng `CONSTANT_TEXT` với tin cậy `HIT_PROB`."""
    probs = np.full((1, len(_SEQUENCE), classes), (1.0 - HIT_PROB) / (classes - 1), dtype=np.float32)
    for step, index in enumerate(_SEQUENCE):
        probs[0, step, index % classes] = HIT_PROB
    return probs


def rec_model(*, characters: Sequence[str] | None = DIGITS, classes: int = len(CHARACTERS)) -> onnx.ModelProto:
    """Model rec tí hon: một `Constant` ra `(1, T, classes)`, metadata `character` nếu có.

    `characters=None` dựng model **thiếu** metadata; `classes` lệch `len(characters) + 2`
    dựng model khai sai số lớp — hai cảnh `from_session` phải từ chối.
    """
    probs = constant_probs(classes)
    node = helper.make_node("Constant", [], ["y"], value=numpy_helper.from_array(probs, "probs"))
    graph = helper.make_graph(
        [node],
        "rec",
        [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1, 3, 48, "w"])],
        [helper.make_tensor_value_info("y", TensorProto.FLOAT, list(probs.shape))],
    )
    model = helper.make_model(graph, ir_version=10, opset_imports=[helper.make_opsetid("", 17)])
    if characters is not None:
        model.metadata_props.append(onnx.StringStringEntryProto(key="character", value="\n".join(characters)))
    return model


def some_id(prefix: IdPrefix) -> str:
    """Id mới đúng tiền tố (`run`, `mdl`, `upl`, …)."""
    return new_id(prefix, SystemClock())


def storage_ref(data: bytes, *, checksum: str | None = None) -> tuple[ModelRef, str]:
    """`ModelRef` dạng storage cho bytes trọng số, kèm khoá object phải ghi vào kho."""
    version = some_id("mdl")
    key = f"{model_prefix(version)}model.onnx"
    digest = checksum if checksum is not None else hashlib.sha256(data).hexdigest()
    return ModelRef(version_id=version, family=STEP, weights_key=key, pinned_name=None, checksum_sha256=digest), key


def infer_payload(*, width: int, height: int, model_ref: ModelRef | None = None, step: str = STEP) -> InferStepPayload:
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


class FlakyReads(LocalDiskStorage):
    """Kho đĩa thật hỏng `failures` lượt đọc đầu rồi đọc được (kho chập chờn, J02).

    `failures` âm nghĩa là hỏng mãi. Đếm theo tiến trình vì worker thử của B0-05 chạy
    trong chính tiến trình pytest.
    """

    def __init__(self, root: Path, error: AppError, *, failures: int) -> None:
        """`error` là lỗi tạm kho ném ra ở mỗi lượt đọc còn trong hạn `failures`."""
        super().__init__(root, SystemClock(), "https://x.test")
        self.error = error
        self.failures = failures
        self.attempts = 0

    async def open_read(self, key: str, *, chunk_size: int = CHUNK_SIZE) -> AsyncIterator[bytes]:
        """Lượt đọc thứ `n`: ném khi `n ≤ failures`, không thì đọc như kho thật."""
        self.attempts += 1
        if self.failures < 0 or self.attempts <= self.failures:
            raise self.error
        async for chunk in super().open_read(key, chunk_size=chunk_size):
            yield chunk


def wheel_rec_session(models_dir: Path) -> ort.InferenceSession:
    """Phiên ONNX nhận dạng của wheel, nạp qua `load_onnx` dạng **ghim** như lúc chạy thật.

    Kho không bị đụng tới (dạng ghim đọc tệp `models_dir/<tên>.onnx`), nhưng `load_onnx`
    vẫn đòi một kho nên truyền một `LocalDiskStorage` trên chính thư mục ấy.
    """
    pin = PINNED["rapidocrRec"]
    ref = ModelRef(
        version_id=some_id("mdl"),
        family=STEP,
        weights_key=None,
        pinned_name="rapidocrRec",
        checksum_sha256=str(pin.onnx_sha256),
    )
    storage = LocalDiskStorage(models_dir, SystemClock(), "https://x.test")
    return asyncio.run(load_onnx(storage, ref, models_dir=models_dir))
