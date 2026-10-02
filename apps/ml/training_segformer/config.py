"""Cấu hình một lượt huấn luyện SegFormer và chọn độ chính xác theo thiết bị (khối [2], [6]).

Chỉ thư viện chuẩn ở mức module: `torch` nhập trong `precision_for`, nên nhập `config`
(qua `trainer`) lúc `discover_trainers` không kéo `torch` vào tiến trình.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, Literal

if TYPE_CHECKING:
    import torch

__all__ = ["Precision", "SegformerTrainConfig", "effective_batch_size", "precision_for"]

Device = Literal["cpu", "cuda"]

_CUDA_BATCH: Final = MappingProxyType({"mitB0": 8, "mitB1": 4})
"""Batch mặc định trên GPU 6 GB @ `crop_px=512`, fp16 (ENV §1); đo lại bằng `test_gpu`."""
_CPU_BATCH: Final = 2


@dataclass(frozen=True, slots=True)
class SegformerTrainConfig:
    """Hằng kỹ thuật của một lượt (khối [2]); `batch_size=None` → `effective_batch_size`."""

    crop_px: int = 512
    batch_size: int | None = None
    lr: float = 6e-5
    weight_decay: float = 0.01
    num_workers: int = 0
    log_every_steps: int = 10
    heartbeat_every_s: float = 30
    parity_min_agreement: float = 0.999
    parity_images: int = 2


@dataclass(frozen=True, slots=True)
class Precision:
    """`autocast_dtype=None` tắt autocast; `use_scaler` bật `GradScaler` (chỉ fp16 cần)."""

    autocast_dtype: "torch.dtype | None"
    use_scaler: bool


def effective_batch_size(config: SegformerTrainConfig, base_model: str, device: Device) -> int:
    """Batch đặt sẵn giữ nguyên; `None` → `mitB0` 8, `mitB1` 4 trên `cuda`, 2 trên `cpu` (khối [6])."""
    if config.batch_size is not None:
        return config.batch_size
    if device == "cuda":
        return _CUDA_BATCH[base_model]
    return _CPU_BATCH


def precision_for(device: Device) -> Precision:
    """`cuda` → fp16 + scaler; `cpu` → float32 thuần. Vòng không rẽ nhánh theo thiết bị (khối [6])."""
    import torch

    if device == "cuda":
        return Precision(autocast_dtype=torch.float16, use_scaler=True)
    return Precision(autocast_dtype=None, use_scaler=False)
