"""ONNX tí hon cho họ tường (BE-00 §9): ngưỡng trung bình kênh giả lập SegFormer 2 lớp.

`ReduceMean` theo kênh → `AveragePool` 4x4 bước 4 → `Concat(Z, Neg(Z))`: lớp `WALL_CLASS`
thắng ở điểm tối (giá trị chuẩn hoá càng âm, `Z` càng âm, `-Z` càng dương). Dùng để D
(`step`/`tasks`) nạp qua `load_onnx` và để C (`segformer.py`) kiểm ghép lát/kiểm hợp đồng.
"""

from collections.abc import Sequence
from typing import Final

import numpy as np
from onnx import NodeProto, TensorProto, helper, numpy_helper

from apps.ml.walls.spec import LOGITS_STRIDE, TILE_PX

__all__ = [
    "make_runtime_broken_segformer",
    "make_threshold_segformer",
    "make_two_input_segformer",
    "make_wrong_input_segformer",
    "make_wrong_output_segformer",
]

_OPSET: Final = helper.make_opsetid("", 17)
_LOGITS_PX: Final = TILE_PX // LOGITS_STRIDE


def _threshold_nodes(*, classes: int = 2) -> list[NodeProto]:
    """`y[c] = ±trung bình kênh gộp `LOGITS_STRIDE`x`LOGITS_STRIDE``; `classes=3` lặp lớp 0 cho J03."""
    reduce_mean = helper.make_node("ReduceMean", ["x"], ["channel_mean"], axes=[1], keepdims=1)
    avg_pool = helper.make_node(
        "AveragePool", ["channel_mean"], ["z"], kernel_shape=[LOGITS_STRIDE] * 2, strides=[LOGITS_STRIDE] * 2
    )
    neg = helper.make_node("Neg", ["z"], ["neg_z"])
    concat_inputs = ["z", "neg_z"] if classes == 2 else ["z", "neg_z", "z"]
    concat = helper.make_node("Concat", concat_inputs, ["y"], axis=1)
    return [reduce_mean, avg_pool, neg, concat]


def _model(
    nodes: Sequence[NodeProto],
    *,
    input_shape: Sequence[int],
    output_shape: Sequence[int],
    extra_inputs: Sequence[str] = (),
    initializer: Sequence[TensorProto] = (),
) -> bytes:
    """Model một đồ thị `x[, extra_inputs] -> y`, `ir_version=10`, opset 17 (mẫu `helpers.py` của B5-01)."""
    inputs = [helper.make_tensor_value_info("x", TensorProto.FLOAT, list(input_shape))]
    inputs += [helper.make_tensor_value_info(name, TensorProto.FLOAT, list(input_shape)) for name in extra_inputs]
    graph = helper.make_graph(
        list(nodes),
        "segformer",
        inputs,
        [helper.make_tensor_value_info("y", TensorProto.FLOAT, list(output_shape))],
        initializer=list(initializer),
    )
    model = helper.make_model(graph, ir_version=10, opset_imports=[_OPSET])
    return bytes(model.SerializeToString())


def make_threshold_segformer() -> bytes:
    """Đúng hợp đồng: vào `[1,3,1024,1024]`, ra `[1,2,256,256]`."""
    return _model(_threshold_nodes(), input_shape=[1, 3, TILE_PX, TILE_PX], output_shape=[1, 2, _LOGITS_PX, _LOGITS_PX])


def make_wrong_output_segformer() -> bytes:
    """Ra `[1,3,256,256]` (3 lớp) — sai hợp đồng, cho J03 của D."""
    return _model(
        _threshold_nodes(classes=3), input_shape=[1, 3, TILE_PX, TILE_PX], output_shape=[1, 3, _LOGITS_PX, _LOGITS_PX]
    )


def make_wrong_input_segformer(size: int = 512) -> bytes:
    """Vào `[1,3,512,512]` — tự nhất quán (ra `[1,2,128,128]`) nhưng lệch hợp đồng vào."""
    small = size // LOGITS_STRIDE
    return _model(_threshold_nodes(), input_shape=[1, 3, size, size], output_shape=[1, 2, small, small])


def make_two_input_segformer() -> bytes:
    """Hai đầu vào cùng hình — `__init__` phải từ chối dù ra đúng hợp đồng."""
    return _model(
        _threshold_nodes(),
        input_shape=[1, 3, TILE_PX, TILE_PX],
        output_shape=[1, 2, _LOGITS_PX, _LOGITS_PX],
        extra_inputs=["x2"],
    )


def make_runtime_broken_segformer() -> bytes:
    """Đồ thị nạp được, hình khai đúng hợp đồng, nhưng `Reshape` theo hình tính từ `Shape` vỡ lúc chạy.

    `target_shape` là `Shape` của một hằng số `[1,2,256,256]` — không phải hằng nạp trực
    tiếp — nên bộ nạp không suy được xung đột lúc dựng đồ thị; `Reshape` chỉ vỡ khi
    `session.run` cố ép `1x3x1024x1024` phần tử vào `1x2x256x256` phần tử.
    """
    dummy = numpy_helper.from_array(np.zeros((1, 2, _LOGITS_PX, _LOGITS_PX), dtype=np.float32), "dummy")
    nodes = [
        helper.make_node("Shape", ["dummy"], ["target_shape"]),
        helper.make_node("Reshape", ["x", "target_shape"], ["y"]),
    ]
    return _model(
        nodes,
        input_shape=[1, 3, TILE_PX, TILE_PX],
        output_shape=[1, 2, _LOGITS_PX, _LOGITS_PX],
        initializer=[dummy],
    )
