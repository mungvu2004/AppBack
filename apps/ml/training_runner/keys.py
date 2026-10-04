"""Khoá Redis, id bản model, khoá object trọng số của một job huấn luyện (B6-03b [2]).

`trained_version_id`, `cancel_key`, `claim_key` nhập lại từ `packages/messaging/payloads/training.py`
(B6-03a, một nguồn — NO-305): runner và cầu nối không thể lệch mẫu; `test_training_keys_literal`
của hai bên vẫn ghim cùng chuỗi.
"""

import secrets
from typing import Final, cast

from packages.messaging.payloads.training import cancel_key, claim_key, trained_version_id
from packages.ml_contracts.datasets import Split, sample_path
from packages.storage.keys import dataset_object, model_artifact

SLOT_KEY: Final = "training:slot"
"""Khoá "một job mỗi lúc" cho mọi thiết bị (BE-00 §7); `cuda` giữ thêm `gpu:0`."""

TOKEN_BYTES: Final = 16

__all__ = [
    "FINISHED_TASK",
    "HEARTBEAT_TASK",
    "LOG_TASK",
    "METRICS_TASK",
    "SLOT_KEY",
    "START_TASK",
    "TOKEN_BYTES",
    "cancel_key",
    "claim_key",
    "new_token",
    "sample_key",
    "trained_version_id",
    "weights_key",
]


def new_token() -> str:
    """Token 32 hex của một lượt: giá trị claim và hậu tố tên object trọng số."""
    return secrets.token_hex(TOKEN_BYTES)


def weights_key(job_id: str, token: str) -> str:
    """Khoá object trọng số của lượt: `ml/models/<mdl>/weights-<token>.onnx` (BE-00 §8)."""
    return model_artifact(trained_version_id(job_id), f"weights-{token}.onnx")


def sample_key(dataset_version_id: str, path: str) -> str:
    """Khoá object một tệp mẫu: `ml/datasets/<dsv>/` + đường manifest `{split}/{sample_id}/{filename}` (B6-02).

    Dựng qua `dataset_object` (một nguồn bố cục); trước đó kiểm đường đủ ba đoạn và đúng luật
    `sample_path`, nếu không → `ValueError`.
    """
    parts = path.split("/")
    if len(parts) != 3:
        raise ValueError(f"đường mẫu phải có ba đoạn: {path!r}")
    sample_path(cast("Split", parts[0]), parts[1], parts[2])
    return dataset_object(dataset_version_id, path)


START_TASK: Final = "ml.training.runner.start"
HEARTBEAT_TASK: Final = "default.training_bridge.heartbeat"
METRICS_TASK: Final = "default.training_bridge.metrics"
LOG_TASK: Final = "default.training_bridge.log"
FINISHED_TASK: Final = "default.training_bridge.finished"
"""Tên task với cầu nối B6-03a (`apps/worker/training_bridge/tasks.py:66-69`); khai lại, không nhập `apps.worker`."""
