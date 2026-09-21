"""Dựng dữ liệu thử cho test `apps.ml.runtime`: ONNX tí hon (BE-00 §9), payload, trang tổng hợp."""

import asyncio
import hashlib
from collections.abc import AsyncIterator, Sequence
from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

from packages.core.clock import SystemClock
from packages.core.errors import AppError
from packages.core.ids import IdPrefix, new_id
from packages.ml_contracts.payloads import InferStepPayload, ModelRef
from packages.storage.local import LocalDiskStorage
from packages.storage.port import CHUNK_SIZE, ObjectInfo, ObjectStorage

OPSETS = [helper.make_opsetid("", 17)]


def some_id(prefix: IdPrefix) -> str:
    return new_id(prefix, SystemClock())


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def model(
    nodes: Sequence[onnx.NodeProto],
    *,
    initializer: Sequence[TensorProto] = (),
    functions: Sequence[onnx.FunctionProto] = (),
    opsets: Sequence[onnx.OperatorSetIdProto] = OPSETS,
) -> onnx.ModelProto:
    """Model một vào `x` float [1], một ra `y`, `ir_version=10`, opset 17 (BE-00 §9)."""
    graph = helper.make_graph(
        list(nodes),
        "g",
        [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1])],
        [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1])],
        initializer=list(initializer),
    )
    return helper.make_model(graph, ir_version=10, opset_imports=list(opsets), functions=list(functions))


def add_model(value: float = 1.0) -> onnx.ModelProto:
    """`y = x + value` — model hợp lệ nhỏ nhất ORT chạy được."""
    constant = numpy_helper.from_array(np.array([value], dtype=np.float32), "c")
    return model([helper.make_node("Add", ["x", "c"], ["y"])], initializer=[constant])


def _counting_body() -> onnx.GraphProto:
    """Thân `Loop`: giữ điều kiện, cộng 1 mỗi vòng."""
    return helper.make_graph(
        [helper.make_node("Identity", ["cond_in"], ["cond_out"]), helper.make_node("Add", ["v_in", "one"], ["v_out"])],
        "body",
        [
            helper.make_tensor_value_info("i", TensorProto.INT64, []),
            helper.make_tensor_value_info("cond_in", TensorProto.BOOL, []),
            helper.make_tensor_value_info("v_in", TensorProto.FLOAT, [1]),
        ],
        [
            helper.make_tensor_value_info("cond_out", TensorProto.BOOL, []),
            helper.make_tensor_value_info("v_out", TensorProto.FLOAT, [1]),
        ],
        initializer=[numpy_helper.from_array(np.array([1.0], dtype=np.float32), "one")],
    )


def loop_model() -> onnx.ModelProto:
    """`Loop` 3 vòng cộng 1: hợp lệ với ORT, nhưng cấm ở dạng storage (BE-00 §9)."""
    trip = numpy_helper.from_array(np.array(3, dtype=np.int64), "trip")
    keep = numpy_helper.from_array(np.array(True), "keep")
    loop = helper.make_node("Loop", ["trip", "keep", "x"], ["y"], body=_counting_body())
    return model([loop], initializer=[trip, keep])


def branch_graph(nodes: Sequence[onnx.NodeProto], initializer: Sequence[TensorProto] = ()) -> onnx.GraphProto:
    """Đồ thị không vào, một ra `out` float [1] — dùng làm nhánh `If`."""
    output = helper.make_tensor_value_info("out", TensorProto.FLOAT, [1])
    return helper.make_graph(list(nodes), "hidden", [], [output], initializer=list(initializer))


def loop_graph(trips: int) -> onnx.GraphProto:
    """Nhánh `out = 0 + 1 x trips` tính bằng `Loop`."""
    return branch_graph(
        [helper.make_node("Loop", ["trip", "keep", "zero"], ["out"], body=_counting_body())],
        [
            numpy_helper.from_array(np.array(trips, dtype=np.int64), "trip"),
            numpy_helper.from_array(np.array(True), "keep"),
            numpy_helper.from_array(np.array([0.0], dtype=np.float32), "zero"),
        ],
    )


LOCAL = helper.make_opsetid("local", 1)


def local_function_model(
    nodes: Sequence[onnx.NodeProto], opsets: Sequence[onnx.OperatorSetIdProto] = OPSETS
) -> onnx.ModelProto:
    """Đồ thị chính chỉ gọi hàm cục bộ `local::F(a) -> b` có thân `nodes`."""
    function = helper.make_function("local", "F", ["a"], ["b"], list(nodes), list(opsets))
    return model([helper.make_node("F", ["x"], ["y"], domain="local")], functions=[function], opsets=[*opsets, LOCAL])


def hidden_in_function_default(
    hidden: onnx.GraphProto, opsets: Sequence[onnx.OperatorSetIdProto] = OPSETS
) -> onnx.ModelProto:
    """Hàm `F` dùng `hidden` qua **giá trị mặc định** của thuộc tính `body` (`ref_attr_name`).

    Đồ thị chính gọi `F` không truyền `body`: ORT thay mặc định vào lúc nạp, bộ inline của
    `onnx` thì không. Đây là đường review 2026-09-21 (finding #1) dựng để vượt luật cấu trúc.
    """
    branch = helper.make_node("If", ["c"], ["k"])
    for name in ("then_branch", "else_branch"):
        attribute = branch.attribute.add()
        attribute.name, attribute.ref_attr_name, attribute.type = name, "body", onnx.AttributeProto.GRAPH
    zero = numpy_helper.from_array(np.array([0.0], dtype=np.float32))
    nodes = [
        helper.make_node("Constant", [], ["zero_c"], value=zero),
        helper.make_node("Greater", ["a", "zero_c"], ["c1"]),
        helper.make_node("Squeeze", ["c1"], ["c"]),
        branch,
        helper.make_node("Add", ["a", "k"], ["b"]),
    ]
    hidden_model = local_function_model(nodes, opsets)
    hidden_model.functions[0].attribute_proto.append(helper.make_attribute("body", hidden))
    return hidden_model


def external_tensor(name: str, location: str = "../x") -> TensorProto:
    """Tensor trỏ dữ liệu ra tệp ngoài — thứ bộ nạp phải từ chối."""
    tensor = helper.make_tensor(name, TensorProto.FLOAT, [1], [0.0])
    tensor.ClearField("float_data")
    tensor.data_location = TensorProto.EXTERNAL
    entry = tensor.external_data.add()
    entry.key, entry.value = "location", location
    return tensor


def upload_prefix() -> str:
    return f"projects/{some_id('prj')}/floors/L-ABCDEFGHIJ/uploads/{some_id('upl')}/"


def infer_payload(
    *, step: str = "wallSegmentation", model_ref: ModelRef | None = None, width: int = 1600, height: int = 1200
) -> InferStepPayload:
    """Payload bước suy luận hợp lệ; model mặc định là dạng cổ điển của họ."""
    prefix, run = upload_prefix(), some_id("run")
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


def put_sync(storage: ObjectStorage, key: str, data: bytes) -> None:
    """Ghi một object từ test đồng bộ (test task chạy worker thật, không có vòng sự kiện)."""
    asyncio.run(storage.put(key, data, content_type="application/octet-stream", max_bytes=len(data) + 1))


class FailingReads(LocalDiskStorage):
    """Kho đĩa thật mà mọi lượt đọc ném `error` (kho hỏng, hay object vừa bị xoá).

    `pretend_size` cho `stat` báo object có thật: dựng đúng cảnh "bị xoá giữa `stat` và
    `open_read`" mà kho thật chỉ gặp khi có lượt dọn chạy song song.
    """

    def __init__(self, root: Path, error: AppError, *, pretend_size: int | None = None) -> None:
        super().__init__(root, SystemClock(), "https://x.test")
        self.error = error
        self.pretend_size = pretend_size

    async def stat(self, key: str) -> ObjectInfo | None:
        if self.pretend_size is None:
            return await super().stat(key)
        return ObjectInfo(key, self.pretend_size, "0" * 64, "application/octet-stream", "unknown", SystemClock().now())

    async def open_read(self, key: str, *, chunk_size: int = CHUNK_SIZE) -> AsyncIterator[bytes]:
        if chunk_size > 0:  # luôn đúng: lỗi nổi lên ở lượt đọc đầu, như kho thật
            raise self.error
        yield b""
