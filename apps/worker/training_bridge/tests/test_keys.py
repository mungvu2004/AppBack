"""Test khoá Redis, id bản model, mẫu tên trọng số, nhãn bản (B6-03a [8] `test_training_keys_literal`).

Ca này dùng chung với B6-03b (hai bên tự khai cùng mẫu vì chưa nhập được nhau — prompt gốc).
"""

from datetime import UTC, datetime

import pytest

from apps.api.admin_ml_registry.registry import clean_label
from apps.worker.training_bridge.messages import trained_version_label
from packages.core.ids import check_id
from packages.messaging.payloads.training import WEIGHTS_NAME_RE, cancel_key, claim_key, trained_version_id

_JOB_ID = "job_01J0000000000000000000000A"


def test_training_keys_literal() -> None:
    """`job_01J0000000000000000000000A` → ba chuỗi khoá/id nguyên văn [8]."""
    assert cancel_key(_JOB_ID) == "training:cancel:job_01J0000000000000000000000A"
    assert claim_key(_JOB_ID) == "training:claim:job_01J0000000000000000000000A"
    assert trained_version_id(_JOB_ID) == "mdl_01J0000000000000000000000A"


def test_training_keys_literal_weights_name_matches() -> None:
    """`weights-` + 32 số `0` + `.onnx` khớp `WEIGHTS_NAME_RE`."""
    assert WEIGHTS_NAME_RE.fullmatch("weights-" + "0" * 32 + ".onnx")


def test_trained_version_id_rejects_malformed_job_id() -> None:
    """Id sai mẫu `job_<ULID>` → `ValueError` (lỗi lập trình, id luôn đọc từ DB)."""
    with pytest.raises(ValueError, match="job"):
        trained_version_id("not-a-job-id")


def test_trained_version_label_within_80_chars_and_clean_label_accepts() -> None:
    """Nhãn ≤ 80 ký tự, qua được `clean_label` (một luật nhãn với dây)."""
    label = trained_version_label(base_model="yolov8n", epochs=3, finished_at=datetime(2026, 10, 1, 12, 30, tzinfo=UTC))
    assert label == "huấn luyện yolov8n · 3 epoch · 2026-10-01 12:30"
    assert 1 <= len(label) <= 80
    assert clean_label(label) == label


def test_trained_version_label_matches_id_pattern_sample() -> None:
    """`check_id("job", …)` vẫn chấp nhận id mẫu dùng trong test này (tiền đề của mẫu khoá)."""
    assert check_id("job", _JOB_ID) == _JOB_ID
