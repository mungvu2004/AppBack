"""Nhánh lẻ của `trainer.py` không đi qua một lượt huấn luyện thật (khối [8], độ phủ nhánh).

Lượt thật chỉ đi một đường trong mỗi nhánh phòng thủ (`tloss` kiểu cũ, thiếu `best.pt`, ONNX có
dữ liệu ngoài, chưa tới hạn nhịp tim). Đây là test đơn vị cho đúng những nhánh đó.
"""

from pathlib import Path

import pytest

from apps.ml.training_segformer.tests.support import RecordingReporter
from apps.ml.training_yolo.trainer import _best_weights, _check_export, _loss_total, _RunCallbacks
from packages.core.clock import SystemClock
from packages.messaging.tasks import PermanentError


class _ScalarLoss:
    """`trainer.tloss` của bản ultralytics cũ: tensor 0 chiều — `float()` được, lặp thì `TypeError`."""

    def __float__(self) -> float:
        """Giá trị loss của epoch."""
        return 2.5


def test_loss_total_handles_missing_and_scalar_tloss() -> None:
    """`None` → không có điểm; tensor 0 chiều → đọc bằng `float()`; dict → tổng các thành phần."""
    assert _loss_total(None) is None
    assert _loss_total(_ScalarLoss()) == pytest.approx(2.5)
    assert _loss_total({"box": 1.0, "cls": 0.5}) == pytest.approx(1.5)


def test_heartbeat_waits_for_the_interval() -> None:
    """Chưa qua `heartbeat_every_s` thì không gửi nhịp tim (nếu không, cầu nối ngập nhịp mỗi batch)."""
    reporter = RecordingReporter()
    callbacks = _RunCallbacks(
        reporter=reporter,
        clock=SystemClock(),
        monotonic=lambda: 0.0,
        heartbeat_every_s=60.0,
        last_beat=0.0,
        epochs=1,
    )
    callbacks.on_train_batch_end(None)
    assert reporter.heartbeats == []
    assert callbacks.batches == 1


def test_best_weights_falls_back_to_last(tmp_path: Path) -> None:
    """Không có `best.pt` (fitness không cải thiện) thì lấy `last.pt`; không có gì cả là lỗi."""
    weights = tmp_path / "ultralytics" / "run" / "weights"
    weights.mkdir(parents=True)
    with pytest.raises(PermanentError) as caught:
        _best_weights(tmp_path)
    assert caught.value.code == "MODEL_FORMAT_UNSUPPORTED"
    (weights / "last.pt").write_bytes(b"ckpt")
    assert _best_weights(tmp_path) == weights / "last.pt"
    (weights / "best.pt").write_bytes(b"ckpt")
    assert _best_weights(tmp_path) == weights / "best.pt"


def test_check_export_rejects_external_data(tmp_path: Path) -> None:
    """ONNX trỏ trọng số ra tệp ngoài không tự chứa: đẩy lên kho sẽ thành model hỏng."""
    import onnx
    from onnx import TensorProto, helper

    tensor = helper.make_tensor("w", TensorProto.FLOAT, [1], vals=[1.0])
    tensor.ClearField("float_data")
    tensor.data_location = TensorProto.EXTERNAL
    entry = tensor.external_data.add()
    entry.key, entry.value = "location", "w.bin"
    graph = helper.make_graph(
        [helper.make_node("Identity", ["w"], ["y"])],
        "g",
        [],
        [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1])],
        initializer=[tensor],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    target = tmp_path / "model.onnx"
    target.write_bytes(model.SerializeToString())
    with pytest.raises(PermanentError) as caught:
        _check_export(target)
    assert caught.value.code == "MODEL_FORMAT_UNSUPPORTED"
    assert onnx.__version__
