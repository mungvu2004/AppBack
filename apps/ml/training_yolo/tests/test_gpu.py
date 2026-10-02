"""Lượt huấn luyện GPU thật (khối [8] "GPU thật"): chỉ chạy trên máy có CUDA, không chạy trong cổng.

Marker `gpu` bị `addopts` loại; chạy tay bằng `pytest -m gpu apps/ml/training_yolo` trong ảnh `ml`
bản `cuda`. Dùng `yolov8n` **ghim thật** trong `ML_MODELS_DIR`, nên test này không dựng model giả.
"""

import dataclasses
import logging
import os
import time
from pathlib import Path
from typing import Final

import pytest

from apps.ml.training_segformer.tests.support import RecordingReporter, train_spec
from apps.ml.training_yolo.settings import YoloTrainSettings
from apps.ml.training_yolo.tests.support import write_objects_split
from apps.ml.training_yolo.trainer import YoloTrainer

_log: Final = logging.getLogger(__name__)
_PLANS: Final = 20


@pytest.mark.gpu
def test_gpu_training_run(tmp_path: Path) -> None:
    """20 mặt bằng, 1 epoch trên GPU; in VRAM đỉnh, thời gian và `map50` bằng `logging`."""
    import torch

    models_dir = Path(os.environ["ML_MODELS_DIR"])
    data_dir = tmp_path / "data"
    write_objects_split(data_dir, "train", range(_PLANS))
    write_objects_split(data_dir, "validation", range(_PLANS, _PLANS + 4))
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    reporter = RecordingReporter()
    torch.cuda.reset_peak_memory_stats()
    started = time.monotonic()
    result = YoloTrainer(settings=YoloTrainSettings(), models_dir=models_dir).train(
        dataclasses.replace(
            train_spec(family="openingAndFurnitureDetection", base_model="yolov8n", epochs=1), device="cuda"
        ),
        data_dir,
        out_dir,
        reporter,
    )
    _log.info(
        "GPU: %.1f s, VRAM đỉnh %.0f MiB, map50 %.4f",
        time.monotonic() - started,
        torch.cuda.max_memory_allocated() / (1024 * 1024),
        result.metrics["map50"],
    )
    assert result.onnx_path.is_file()
