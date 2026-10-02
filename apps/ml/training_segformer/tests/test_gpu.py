"""Trần bộ nhớ GPU 6 GB của `mitB1` (khối [8], marker `gpu` — ngoài verify, container không có GPU).

Chạy bằng tay trên máy có CUDA: `pytest -m gpu apps/ml/training_segformer/tests/test_gpu.py`.
Trần 5,5 GiB chừa chỗ cho phân mảnh bộ cấp phát; vượt trần là đổi hợp đồng ENV §1, không phải
tinh chỉnh — vì vậy test khẳng định số, không chỉ in ra.
"""

import logging
import time
from pathlib import Path
from typing import Final

import pytest
import torch

from apps.ml.training_segformer import loop
from apps.ml.training_segformer.config import SegformerTrainConfig
from apps.ml.training_segformer.tests.support import RecordingReporter, write_split
from packages.core.clock import SystemClock
from packages.ml_contracts.ports import TrainSpec

_log: Final = logging.getLogger(__name__)
_MAX_BYTES: Final = int(5.5 * 1024**3)


@pytest.mark.gpu
def test_train_gpu_mitb1_fits_6gb(tmp_path: Path) -> None:
    """`mitB1`, 64 ảnh 1600x1200, 1 epoch, lô 4 @ 512, fp16 → `max_memory_allocated` ≤ 5,5 GiB.

    Không tự `.to("cuda")`: `loop.train_model` chuyển model theo `spec.device`.
    """
    from apps.ml.training_segformer import model as segformer_model
    from packages.ml_contracts.pinned import PINNED

    data_dir = tmp_path / "data"
    write_split(data_dir, "train", 64, seed=0)
    write_split(data_dir, "validation", 2, seed=1000)
    models_dir = Path(PINNED["mitB1"].name)
    net = segformer_model.load_pretrained(models_dir.parent, "mitB1", PINNED)
    spec = TrainSpec(
        job_id="job_gpu",
        family="wallSegmentation",
        base_model="mitB1",
        epochs=1,
        device="cuda",
        seed=0,
    )
    torch.cuda.reset_peak_memory_stats()
    started = time.monotonic()
    reporter = RecordingReporter()
    loop.train_model(
        net,
        spec=spec,
        config=SegformerTrainConfig(crop_px=512, batch_size=4),
        data_dir=data_dir,
        reporter=reporter,
        clock=SystemClock(),
        monotonic=time.monotonic,
    )
    peak = torch.cuda.max_memory_allocated()
    steps = max(len([point for point in reporter.metrics if point.split == "train"]), 1)
    _log.info(
        "gpu mitB1: %.2f s/bước, đỉnh %.2f GiB, iou %s",
        (time.monotonic() - started) / steps,
        peak / 1024**3,
        reporter.metrics[-1].iou,
    )
    assert peak <= _MAX_BYTES
