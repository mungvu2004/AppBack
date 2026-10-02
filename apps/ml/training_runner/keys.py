"""Khoá Redis, id bản model, khoá object trọng số của một job huấn luyện (B6-03b [2]).

Khai lại **đúng mẫu** của `packages/messaging/payloads/training.py` (B6-03a): runner không
được nhập module đó ([9]); `test_training_keys_literal` của hai bên ghim cùng chuỗi. Gộp hai
nơi là nợ của điều phối (NO-305).
"""

import secrets
from typing import Final, cast

from packages.core.ids import check_id
from packages.core.object_keys import check_key
from packages.ml_contracts.datasets import Split, sample_path
from packages.storage.keys import model_artifact

SLOT_KEY: Final = "training:slot"
"""Khoá "một job mỗi lúc" cho mọi thiết bị (BE-00 §7); `cuda` giữ thêm `gpu:0`."""

TOKEN_BYTES: Final = 16


def trained_version_id(job_id: str) -> str:
    """`mdl_` + ULID của `job_id` (một job ↔ một bản); `job_id` sai mẫu → `ValueError`."""
    return "mdl_" + check_id("job", job_id).removeprefix("job_")


def cancel_key(job_id: str) -> str:
    """Khoá huỷ: có mặt thì launcher không khởi chạy, runner dừng (BE-00 §7)."""
    return f"training:cancel:{job_id}"


def claim_key(job_id: str) -> str:
    """Khoá claim mang token 32 hex của lượt; chỉ người giữ token được gia hạn hay xoá."""
    return f"training:claim:{job_id}"


def new_token() -> str:
    """Token 32 hex của một lượt: giá trị claim và hậu tố tên object trọng số."""
    return secrets.token_hex(TOKEN_BYTES)


def weights_key(job_id: str, token: str) -> str:
    """Khoá object trọng số của lượt: `ml/models/<mdl>/weights-<token>.onnx` (BE-00 §8)."""
    return model_artifact(trained_version_id(job_id), f"weights-{token}.onnx")


def sample_key(dataset_version_id: str, path: str) -> str:
    """Khoá object một tệp mẫu: `ml/datasets/<dsv>/` + đường manifest `{split}/{sample_id}/{filename}` (B6-02).

    Không qua `dataset_object`: nó chỉ nhận tên một đoạn (NO-263), cùng cách lách với
    `apps/worker/datasets/writer.py` `_sample_key`. Đường không đủ ba đoạn hay sai luật `sample_path` → `ValueError`.
    """
    parts = path.split("/")
    if len(parts) != 3:
        raise ValueError(f"đường mẫu phải có ba đoạn: {path!r}")
    sample_path(cast("Split", parts[0]), parts[1], parts[2])
    return check_key(f"ml/datasets/{check_id('dsv', dataset_version_id)}/{path}")


START_TASK: Final = "ml.training.runner.start"
HEARTBEAT_TASK: Final = "default.training_bridge.heartbeat"
METRICS_TASK: Final = "default.training_bridge.metrics"
LOG_TASK: Final = "default.training_bridge.log"
FINISHED_TASK: Final = "default.training_bridge.finished"
"""Tên task với cầu nối B6-03a (`apps/worker/training_bridge/tasks.py:66-69`); khai lại, không nhập `apps.worker`."""
