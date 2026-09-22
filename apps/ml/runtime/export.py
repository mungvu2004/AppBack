"""Xuất ONNX tất định từ model `torch` (huấn luyện B6-04a/b, bản ghim lúc build).

Cùng model, cùng đầu vào mẫu → cùng từng byte ở mọi tiến trình: checksum của phiên bản
model là SHA-256 của chính tệp này, nên hai lượt xuất khác byte là hai model khác nhau
với N26/B6-01. `normalize_onnx` bỏ mọi thứ phụ thuộc lúc/nơi xuất (giờ xuất trong
`metadata_props`, phiên bản bộ xuất, `doc_string` mang đường dẫn tệp nguồn) và ghi
protobuf với thứ tự trường cố định.

Dùng bộ xuất TorchScript (`dynamo=False`): bộ xuất dynamo của torch 2.14 luôn ra opset 18
(bộ chuyển xuống 17 hỏng với `ReduceMean`), trái hợp đồng opset 17.
"""

import hashlib
import itertools
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Final

import onnx

from apps.ml.runtime.loader import has_external_data, iter_graphs, iter_nodes

if TYPE_CHECKING:
    import torch

MODEL_MAX_BYTES_FOR_EXPORT: Final = 2 * 1024**3
"""Protobuf không chứa được model ≥ 2 GiB mà không dùng dữ liệu ngoài (bị cấm, BE-00 §9)."""


def normalize_onnx(data: bytes) -> bytes:
    """Bỏ `doc_string` ở mọi cấp, `producer_version`, mọi `metadata_props`; từ chối dữ liệu ngoài.

    **Chỉ** cho `export_onnx`, `export_yolo`: model của nhà cung cấp chép nguyên (giữ
    `metadata_props` như bảng ký tự của RapidOCR).
    """
    model = onnx.load_model_from_string(data)
    if has_external_data(model):
        raise ValueError("ONNX xuất ra có dữ liệu ngoài")
    model.doc_string = ""
    model.producer_version = ""
    del model.metadata_props[:]
    for function in model.functions:
        function.doc_string = ""
    for graph in iter_graphs(model):
        graph.doc_string = ""
        for value in (*graph.input, *graph.output, *graph.value_info):
            value.doc_string = ""
        for tensor in graph.initializer:
            tensor.doc_string = ""
    for node in iter_nodes(model):
        node.doc_string = ""
    normalized: bytes = model.SerializeToString(deterministic=True)
    return normalized


def write_atomic(path: Path, data: bytes) -> str:
    """Ghi qua tệp tạm cùng thư mục rồi `os.replace`; trả SHA-256 của nội dung đã ghi."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(data)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return hashlib.sha256(data).hexdigest()


def export_onnx(model: "torch.nn.Module", sample: "torch.Tensor", path: Path, *, opset: int = 17) -> str:
    """Xuất `model` (chế độ `eval`, không gradient) ra `path`; trả SHA-256 của tệp.

    Model ≥ 2 GiB (tham số + buffer) → `ValueError` trước khi xuất. `torch` nhập trong hàm:
    `write_atomic`, `normalize_onnx` dùng ở CLI build mà không cần torch.
    """
    import torch

    size = sum(
        tensor.numel() * tensor.element_size() for tensor in itertools.chain(model.parameters(), model.buffers())
    )
    if size >= MODEL_MAX_BYTES_FOR_EXPORT:
        raise ValueError(f"model {size} byte ≥ 2 GiB, không xuất được không dữ liệu ngoài")
    model.eval()
    with tempfile.TemporaryDirectory() as workdir, torch.no_grad():
        raw = Path(workdir) / "model.onnx"
        torch.onnx.export(model, (sample,), str(raw), opset_version=opset, external_data=False, dynamo=False)
        data = normalize_onnx(raw.read_bytes())
    return write_atomic(path, data)
