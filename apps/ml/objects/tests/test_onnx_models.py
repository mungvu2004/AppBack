"""Test `apps.ml.objects.tests.onnx_models` chạy thật (K23) — helper, không phải test riêng nó là mã nghiệp vụ.

Chép khuôn `apps/ml/walls/tests/test_tasks.py`/`helpers.py` (B5-02) cho `local_storage`.
"""

import hashlib
from collections.abc import Iterator

import numpy as np
import pytest

from apps.ml.objects.tests.onnx_models import (
    load_session,
    make_const_yolo,
    make_runtime_broken_yolo,
    storage_ref,
    yolo_output,
)
from apps.ml.runtime.errors import ORT_ERRORS
from apps.ml.runtime.loader import clear_session_cache
from packages.storage.local import LocalDiskStorage


@pytest.fixture(autouse=True)
def _clear_cache() -> Iterator[None]:
    """Cache phiên ONNX sạch trước và sau mỗi test (checksum trùng giữa các test khác nhau)."""
    clear_session_cache()
    yield
    clear_session_cache()


def test_load_session__const_yolo_runs_to_expected_array(local_storage: LocalDiskStorage) -> None:
    """`make_const_yolo` + `load_session`: phiên nạp được, `session.run` ra đúng mảng hằng đã khai."""
    output = yolo_output([(320.0, 240.0, 100.0, 80.0, 2, 0.9)], nc=10)
    data = make_const_yolo(output)
    session = load_session(local_storage, data)

    assert [i.shape for i in session.get_inputs()] == [[1, 3, 640, 640]]
    assert [o.shape for o in session.get_outputs()] == [list(output.shape)]

    x = np.zeros((1, 3, 640, 640), dtype=np.float32)
    (result,) = session.run(None, {"x": x})
    np.testing.assert_array_equal(result, output)


def test_load_session__const_yolo_declares_dynamic_dims(local_storage: LocalDiskStorage) -> None:
    """`input_shape` chứa chuỗi ("height"/"width") → model khai chiều động đúng như truyền vào."""
    output = yolo_output([], nc=10)
    data = make_const_yolo(output, input_shape=(1, 3, "height", "width"))
    session = load_session(local_storage, data)

    assert session.get_inputs()[0].shape == [1, 3, "height", "width"]


def test_load_session__runtime_broken_yolo_raises_ort_error(local_storage: LocalDiskStorage) -> None:
    """`make_runtime_broken_yolo`: nạp được, nhưng `session.run` ném lỗi ORT thật (vỡ lúc chạy)."""
    data = make_runtime_broken_yolo(nc=10)
    session = load_session(local_storage, data)

    x = np.zeros((1, 3, 640, 640), dtype=np.float32)
    with pytest.raises(ORT_ERRORS):
        session.run(None, {"x": x})


def test_storage_ref__checksum_matches_data_sha256() -> None:
    """`storage_ref` tính checksum thật của bytes, khoá đúng khuôn `ml/models/.../model.onnx`, họ đúng."""
    data = b"some onnx bytes"
    ref, key = storage_ref(data)

    assert ref.checksum_sha256 == hashlib.sha256(data).hexdigest()
    assert key.startswith("ml/models/")
    assert key.endswith("/model.onnx")
    assert ref.family == "openingAndFurnitureDetection"
