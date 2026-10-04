"""Xuất ONNX từ model `torch` đã huấn luyện, kiểm định dạng và tương đương trước khi trả IoU (khối [6]).

Chỉ `trainer.train()` nhập lười module này; ở đây `torch`, `onnx`, `onnxruntime` nhập thoải
mái ở mức module. Không tự dọn `out_dir` lúc lỗi — `trainer.py` dọn.
"""

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Final

import numpy as np
import onnx
import onnxruntime as ort  # type: ignore[import-untyped]  # onnxruntime 1.30 không có py.typed
import torch
from google.protobuf.message import DecodeError  # type: ignore[import-untyped]  # protobuf không kèm stub
from numpy.typing import NDArray

from apps.ml.runtime.errors import ORT_ERRORS
from apps.ml.runtime.export import export_onnx
from apps.ml.runtime.loader import has_external_data
from apps.ml.training_segformer import metrics as segformer_metrics
from apps.ml.training_segformer.config import SegformerTrainConfig
from apps.ml.training_segformer.data import read_sample, sample_dirs
from apps.ml.training_segformer.errors import DATASET_SPLIT_EMPTY, MODEL_EXPORT_MISMATCH, MODEL_FORMAT_UNSUPPORTED
from apps.ml.walls.segformer import SegformerOnnxSegmenter, stitch_mask
from apps.ml.walls.spec import TILE_PX
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.ports import TrainReporter

__all__ = ["export_and_check"]

_ONNX_FILENAME: Final = "model.onnx"


def _unsupported() -> PermanentError:
    """Lỗi chung cho ONNX xuất ra không đạt hợp đồng (không tiết lộ chi tiết)."""
    return PermanentError(MODEL_FORMAT_UNSUPPORTED)


class _LogitsOnly(torch.nn.Module):
    """Bọc model SegFormer để đồ thị ONNX chỉ có đúng một tensor ra (`logits`)."""

    def __init__(self, inner: torch.nn.Module) -> None:
        """Giữ `inner` (bản CPU float32 đã `eval()`) làm thuộc tính con."""
        super().__init__()
        self.inner = inner

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Chỉ trả `logits`, bỏ phần còn lại của `SemanticSegmenterOutput`."""
        logits: torch.Tensor = self.inner(pixel_values=x).logits
        return logits


def _check_exported_format(onnx_path: Path, out_dir: Path) -> bytes:
    """Chỉ một tệp trong `out_dir`, proto giải được, không dữ liệu ngoài, `onnx.checker` đạt; trả byte ONNX.

    `has_external_data` chạy **trước** `check_model`: checker đã từ chối tensor ngoài thiếu tệp phụ
    bằng `ValidationError`, nên đặt sau nó thì nhánh này không bao giờ tới được.
    """
    if any(path != onnx_path for path in out_dir.iterdir()):
        raise _unsupported()
    try:
        onnx_model = onnx.load(str(onnx_path), load_external_data=False)
        if has_external_data(onnx_model):
            raise _unsupported()
        onnx.checker.check_model(onnx_model)
    except (DecodeError, onnx.checker.ValidationError) as exc:
        raise _unsupported() from exc
    return onnx_path.read_bytes()


def _parity_agreement(
    onnx_tile: Callable[[NDArray[np.float32]], NDArray[np.float32]],
    torch_tile: Callable[[NDArray[np.float32]], NDArray[np.float32]],
    validation_dir: Path,
    *,
    config: SegformerTrainConfig,
    reporter: TrainReporter,
) -> float:
    """Tỉ lệ điểm ảnh ONNX và `torch` cho cùng nhãn trên `config.parity_images` mẫu đầu (1.0 nếu không có mẫu)."""
    matches = 0
    total_px = 0
    for sample_dir in sample_dirs(validation_dir)[: config.parity_images]:
        pixels, _truth = read_sample(sample_dir)
        onnx_mask = stitch_mask(pixels, segformer_metrics.guarded(onnx_tile, reporter))
        torch_mask = stitch_mask(pixels, segformer_metrics.guarded(torch_tile, reporter))
        matches += int(np.count_nonzero(onnx_mask == torch_mask))
        total_px += onnx_mask.size
    return 1.0 if total_px == 0 else matches / total_px


def export_and_check(
    model: torch.nn.Module,
    out_dir: Path,
    validation_dir: Path,
    *,
    config: SegformerTrainConfig,
    reporter: TrainReporter,
) -> float:
    """Xuất `model` ra `out_dir/model.onnx`, kiểm định dạng + tương đương, trả IoU ONNX đã làm tròn 4.

    Thứ tự: xuất → `_check_exported_format` (một tệp, không dữ liệu ngoài, `onnx.checker`) →
    log `training_exported` → `_parity_agreement` với bản gốc (huỷ giữa chừng → `TrainingStopped`) →
    log `training_parity` → `agreement < parity_min_agreement` → `MODEL_EXPORT_MISMATCH` → IoU trên
    cả split (`None` → `PermanentError(DATASET_SPLIT_EMPTY)`).
    """
    cpu_model = copy.deepcopy(model).to("cpu", torch.float32).eval()
    onnx_path = out_dir / _ONNX_FILENAME
    export_onnx(_LogitsOnly(cpu_model), torch.zeros(1, 3, TILE_PX, TILE_PX), onnx_path, opset=17)
    data = _check_exported_format(onnx_path, out_dir)
    reporter.log("info", "training_exported", {"size_mib": round(len(data) / 2**20, 2)})

    session = ort.InferenceSession(data, providers=["CPUExecutionProvider"])
    SegformerOnnxSegmenter(session)
    input_name = session.get_inputs()[0].name
    output_name = session.get_outputs()[0].name

    def onnx_tile(tile: NDArray[np.float32]) -> NDArray[np.float32]:
        """Lát → logits qua phiên ONNX vừa xuất; lỗi `onnxruntime` → `MODEL_FORMAT_UNSUPPORTED`."""
        try:
            result: NDArray[np.float32] = session.run([output_name], {input_name: tile})[0]
        except ORT_ERRORS as exc:
            raise _unsupported() from exc
        return result

    torch_tile = segformer_metrics.torch_run_tile(cpu_model, "cpu")
    agreement = _parity_agreement(onnx_tile, torch_tile, validation_dir, config=config, reporter=reporter)
    reporter.log("info", "training_parity", {"agreement": round(agreement, 6)})
    if agreement < config.parity_min_agreement:
        raise PermanentError(MODEL_EXPORT_MISMATCH)

    iou = segformer_metrics.evaluate_iou(segformer_metrics.guarded(onnx_tile, reporter), validation_dir)
    if iou is None:
        raise PermanentError(DATASET_SPLIT_EMPTY)
    return round(iou, 4)
