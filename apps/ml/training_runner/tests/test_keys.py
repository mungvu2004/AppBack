"""Mẫu khoá Redis/object của runner trùng từng ký tự với B6-03a (B6-03b [8] "Khác")."""

import pytest

from apps.ml.training_runner.keys import (
    SLOT_KEY,
    cancel_key,
    claim_key,
    new_token,
    sample_key,
    trained_version_id,
    weights_key,
)
from packages.storage.keys import model_artifact

JOB = "job_01J0000000000000000000000A"


def test_training_keys_literal() -> None:
    """Cùng ca với `test_training_keys_literal` của B6-03a: đổi mẫu ở một bên là cầu nối mất job."""
    assert cancel_key(JOB) == "training:cancel:job_01J0000000000000000000000A"
    assert claim_key(JOB) == "training:claim:job_01J0000000000000000000000A"
    assert trained_version_id(JOB) == "mdl_01J0000000000000000000000A"
    weights = model_artifact("mdl_01J0000000000000000000000A", "weights-" + "0" * 32 + ".onnx")
    assert weights_key(JOB, "0" * 32) == weights
    assert SLOT_KEY == "training:slot"


def test_new_token_is_32_hex() -> None:
    """Token lượt là 32 hex và mỗi lượt một token mới (mẫu `WEIGHTS_NAME_RE` của cầu nối)."""
    first, second = new_token(), new_token()
    assert len(first) == 32
    assert int(first, 16) >= 0
    assert first != second


def test_sample_key_layout_and_rejects_bad_paths() -> None:
    """Khoá mẫu theo bố cục B6-02 (NO-263); đường lạ, thiếu đoạn hay leo thư mục bị chặn trước khi thành khoá."""
    dsv = "dsv_01J0000000000000000000000A"
    assert sample_key(dsv, "train/s0/image.png") == "ml/datasets/dsv_01J0000000000000000000000A/train/s0/image.png"
    for bad in ("train/s0", "train/../image.png", "other/s0/image.png", "train/s0/evil.sh", "a/b/c/d"):
        with pytest.raises(ValueError, match=r"ba đoạn|sai mẫu|lạ"):
            sample_key(dsv, bad)
