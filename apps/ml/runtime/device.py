"""Chọn thiết bị cho huấn luyện và xuất ONNX (`ML_DEVICE`, M04).

Suy luận luôn chạy `onnxruntime` CPU (BE-00 §9); thiết bị chỉ quyết định nơi `torch`
chạy. `torch` nhập **trong hàm**: tiến trình suy luận không bao giờ phải nạp nó.
"""

from typing import Literal

from apps.ml.runtime.errors import ML_DEVICE_UNAVAILABLE
from packages.messaging.tasks import PermanentError

Device = Literal["cpu", "cuda"]


def resolve_device(setting: Literal["auto", "cpu", "cuda"]) -> Device:
    """`auto` → `cuda` khi có, không thì `cpu`; `cuda` mà máy không có → `ML_DEVICE_UNAVAILABLE`.

    Khi trả `cuda`, người gọi phải giữ `gpu_slot` suốt lượt dùng GPU (một tác vụ GPU mỗi lúc).
    """
    if setting == "cpu":
        return "cpu"
    # torch chỉ nạp khi thật sự cần hỏi GPU: tiến trình suy luận không có nó (BE-00 §9).
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if setting == "cuda":
        raise PermanentError(ML_DEVICE_UNAVAILABLE)
    return "cpu"
