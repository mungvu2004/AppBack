"""Chạy lát qua `torch`, canh huỷ giữa lát, và IoU cộng dồn trên một split (khối [6]).

`torch` chỉ nhập trong `torch_run_tile` (lười); `apps.ml.walls.segformer` (kéo `onnxruntime`)
nhập ở mức module vì chính module này chỉ được `trainer.train()` nhập lười, không đi qua
`discover_trainers()`.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Final

import numpy as np
from numpy.typing import NDArray

from apps.ml.training_runner.errors import TrainingStopped
from apps.ml.training_segformer.data import read_sample, sample_dirs
from apps.ml.walls.segformer import RunTile, stitch_mask
from packages.ml_contracts.ports import TrainReporter
from packages.vision.walls.metrics import mask_overlap

if TYPE_CHECKING:
    import torch

__all__ = ["evaluate_iou", "guarded", "torch_run_tile"]

_log: Final = logging.getLogger(__name__)


def torch_run_tile(model: "torch.nn.Module", device: str) -> RunTile:
    """`RunTile` chạy `model` trên `device`, `eval()` + `inference_mode()`, float32 thuần (không autocast)."""
    import torch

    model = model.to(device=device, dtype=torch.float32)
    model.eval()

    def run_tile(tile: NDArray[np.float32]) -> NDArray[np.float32]:
        """Một lát `(1, 3, T, T)` float32 → logits `(1, 2, T/4, T/4)` numpy float32."""
        with torch.inference_mode():
            tensor = torch.from_numpy(tile).to(device=device, dtype=torch.float32)
            logits = model(pixel_values=tensor).logits
            result: NDArray[np.float32] = logits.to("cpu").numpy().astype(np.float32)
            return result

    return run_tile


def guarded(run_tile: RunTile, reporter: TrainReporter) -> RunTile:
    """`RunTile` bọc `run_tile`: hỏi `reporter.cancelled()` trước mỗi lát, đúng → `TrainingStopped`."""

    def wrapped(tile: NDArray[np.float32]) -> NDArray[np.float32]:
        """Huỷ trước khi chạy lát kế tiếp nếu `reporter` báo huỷ."""
        if reporter.cancelled():
            raise TrainingStopped
        return run_tile(tile)

    return wrapped


def evaluate_iou(run_tile: RunTile, split_dir: Path) -> float | None:
    """IoU cộng dồn `Σ giao / Σ hợp` trên mọi mẫu của `split_dir`; split rỗng → `None`.

    `Σ hợp == 0` → `1.0` như `mask_iou`. Không làm tròn: người gọi làm tròn theo nhu cầu.
    """
    dirs = sample_dirs(split_dir)
    if not dirs:
        return None
    intersection = 0
    union = 0
    for sample_dir in dirs:
        pixels, truth = read_sample(sample_dir)
        pred = stitch_mask(pixels, run_tile)
        sample_intersection, sample_union = mask_overlap(pred, truth)
        intersection += sample_intersection
        union += sample_union
    if union == 0:
        return 1.0
    return intersection / union
