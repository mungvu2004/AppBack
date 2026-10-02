"""Độ chính xác theo thiết bị và cỡ lô hiệu dụng (khối [8] `test_train_m04_precision`).

Chạy trên torch CPU: `autocast("cuda")`/`GradScaler("cuda")` vẫn **dựng được** và tự tắt —
đó là lý do vòng huấn luyện không cần rẽ nhánh theo thiết bị. Không mock `torch` (K23).
"""

import pytest
import torch

from apps.ml.training_segformer.config import SegformerTrainConfig, effective_batch_size, precision_for


def test_train_m04_precision() -> None:
    """`cuda` → fp16 + scaler, `cpu` → float32 không scaler; cả hai dựng được trên torch CPU."""
    cuda = precision_for("cuda")
    assert cuda.autocast_dtype is torch.float16
    assert cuda.use_scaler is True
    cpu = precision_for("cpu")
    assert cpu.autocast_dtype is None
    assert cpu.use_scaler is False

    with pytest.warns(UserWarning, match="CUDA is not available"):
        scaler = torch.amp.GradScaler("cuda", enabled=cuda.use_scaler)
    assert scaler.is_enabled() is False, "không có GPU thì GradScaler tự tắt"
    with torch.autocast("cuda", dtype=cuda.autocast_dtype, enabled=True):
        assert torch.ones(1).dtype is torch.float32


def test_train_m04_effective_batch_size() -> None:
    """`batch_size=None` → 8 (`mitB0`/cuda), 4 (`mitB1`/cuda), 2 (cpu); giá trị đặt sẵn giữ nguyên."""
    auto = SegformerTrainConfig()
    assert auto.batch_size is None
    assert effective_batch_size(auto, "mitB0", "cuda") == 8
    assert effective_batch_size(auto, "mitB1", "cuda") == 4
    assert effective_batch_size(auto, "mitB0", "cpu") == 2
    assert effective_batch_size(auto, "mitB1", "cpu") == 2
    fixed = SegformerTrainConfig(batch_size=3)
    assert effective_batch_size(fixed, "mitB1", "cuda") == 3
    assert effective_batch_size(fixed, "mitB0", "cpu") == 3
