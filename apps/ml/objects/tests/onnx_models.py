"""ONNX tí hon cho họ phát hiện ô mở/đồ đạc (BE-00 §9). Khuôn chép từ `apps/ml/walls/tests/onnx_fixtures.py`
và `helpers.py` (B5-02) chứ không nhập chéo (mỗi prompt sở hữu thư mục của mình, BE-00 §2).

Model "hằng" giả lập một đầu ra YOLO cố định: `Constant` mang mảng đáp án, cộng thêm
`0 · ReduceSum(x)` để đồ thị thật sự dùng `x` (không thì ORT có thể tối ưu bỏ đầu vào).
"""

import asyncio
import hashlib
from collections.abc import Sequence
from pathlib import Path
from typing import Final

import numpy as np
import onnxruntime as ort  # type: ignore[import-untyped]  # onnxruntime 1.30 không có py.typed
from numpy.typing import NDArray
from onnx import NodeProto, TensorProto, helper, numpy_helper

from apps.ml.runtime.loader import load_onnx
from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.core.object_keys import model_prefix
from packages.ml_contracts.payloads import ModelRef
from packages.storage.port import ObjectStorage

_OPSET: Final = helper.make_opsetid("", 17)
_FAMILY: Final = "openingAndFurnitureDetection"


def yolo_output(
    boxes: Sequence[tuple[float, float, float, float, int, float]], *, nc: int, anchors: int = 16
) -> NDArray[np.float32]:
    """Mảng đầu ra YOLO `(1, 4+nc, anchors)`: mỗi hộp `(cx, cy, w, h, cls, score)` chiếm một anchor.

    Cột lớp là chỉ số `cls` được đặt `score`, các lớp khác 0 (dạng logits-per-class chuẩn
    YOLOv8); anchor còn dư (ngoài `len(boxes)`) giữ nguyên 0 — không hộp nào giải mã ra đó.
    """
    if len(boxes) > anchors:
        raise ValueError("nhiều hộp hơn anchors")
    out = np.zeros((1, 4 + nc, anchors), dtype=np.float32)
    for i, (cx, cy, w, h, cls, score) in enumerate(boxes):
        out[0, 0, i] = cx
        out[0, 1, i] = cy
        out[0, 2, i] = w
        out[0, 3, i] = h
        out[0, 4 + cls, i] = score
    return out


def _model(
    nodes: Sequence[NodeProto],
    *,
    input_shape: Sequence[int | str],
    output_shape: Sequence[int | str],
    initializer: Sequence[TensorProto] = (),
) -> bytes:
    """Model một đồ thị `x -> y`, `ir_version=10`, opset 17; chiều `str` = chiều động."""
    graph = helper.make_graph(
        list(nodes),
        "yolo",
        [helper.make_tensor_value_info("x", TensorProto.FLOAT, list(input_shape))],
        [helper.make_tensor_value_info("y", TensorProto.FLOAT, list(output_shape))],
        initializer=list(initializer),
    )
    model = helper.make_model(graph, ir_version=10, opset_imports=[_OPSET])
    return bytes(model.SerializeToString())


def make_const_yolo(output: NDArray[np.float32], *, input_shape: Sequence[int | str] = (1, 3, 640, 640)) -> bytes:
    """Model `x -> y` với `y` hằng `output`; hình vào khai đúng `input_shape` (chuỗi = chiều động)."""
    const_y = numpy_helper.from_array(output.astype(np.float32), "const_y")
    zero = numpy_helper.from_array(np.array(0.0, dtype=np.float32), "zero")
    nodes = [
        helper.make_node("Constant", [], ["const_y_val"], value=const_y),
        helper.make_node("ReduceSum", ["x"], ["x_sum"], keepdims=0),
        helper.make_node("Mul", ["x_sum", "zero"], ["zero_sum"]),
        helper.make_node("Add", ["const_y_val", "zero_sum"], ["y"]),
    ]
    return _model(nodes, input_shape=input_shape, output_shape=output.shape, initializer=[zero])


def make_runtime_broken_yolo(*, size: int = 640, nc: int) -> bytes:
    """Đồ thị nạp được, hình khai đúng hợp đồng, nhưng `Reshape` theo hình của một hằng khác cỡ vỡ lúc chạy.

    Mẫu `make_runtime_broken_segformer` (`apps/ml/walls/tests/onnx_fixtures.py:90`): hình đích
    lấy từ `Shape` của một `Constant`, không nạp trực tiếp, nên bộ nạp không thấy xung đột lúc
    dựng đồ thị — chỉ `session.run` mới cố ép sai số phần tử.
    """
    anchors = 16
    declared = (1, 4 + nc, anchors)
    dummy = numpy_helper.from_array(np.zeros((1, 4 + nc, anchors + 1), dtype=np.float32), "dummy")
    nodes = [
        helper.make_node("Shape", ["dummy"], ["target_shape"]),
        helper.make_node("Reshape", ["x", "target_shape"], ["y"]),
    ]
    return _model(nodes, input_shape=[1, 3, size, size], output_shape=list(declared), initializer=[dummy])


def storage_ref(data: bytes, *, checksum: str | None = None) -> tuple[ModelRef, str]:
    """`ModelRef` dạng storage cho bytes model, kèm khoá object phải ghi vào kho trước."""
    version = new_id("mdl", SystemClock())
    key = f"{model_prefix(version)}model.onnx"
    digest = checksum if checksum is not None else hashlib.sha256(data).hexdigest()
    ref = ModelRef(version_id=version, family=_FAMILY, weights_key=key, pinned_name=None, checksum_sha256=digest)
    return ref, key


def load_session(storage: ObjectStorage, data: bytes) -> ort.InferenceSession:
    """Ghi `data` vào kho theo `storage_ref` rồi nạp qua `load_onnx` thật (đồng bộ, cho test)."""
    ref, key = storage_ref(data)

    async def run() -> ort.InferenceSession:
        """Ghi bytes model vào kho rồi nạp qua `load_onnx` thật (dạng storage, không đụng `models_dir`)."""
        await storage.put(key, data, content_type="application/octet-stream", max_bytes=len(data) + 1)
        return await load_onnx(storage, ref, models_dir=Path("/nonexistent"))

    return asyncio.run(run())
