"""Nhánh lẻ của `trainer.py` không đi qua một lượt huấn luyện thật (khối [8], độ phủ nhánh).

Lượt thật chỉ đi một đường trong mỗi nhánh phòng thủ (`tloss` kiểu cũ, thiếu `best.pt`, ONNX có
dữ liệu ngoài, chưa tới hạn nhịp tim). Đây là test đơn vị cho đúng những nhánh đó.
"""

from pathlib import Path
from types import SimpleNamespace

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


def _callbacks(reporter: RecordingReporter, *, monotonic: float = 0.0) -> _RunCallbacks:
    """Callback một epoch với đồng hồ nhịp tim đứng yên ở `monotonic` và mốc nhịp tim cuối ở 0."""
    return _RunCallbacks(
        reporter=reporter,
        clock=SystemClock(),
        monotonic=lambda: monotonic,
        heartbeat_every_s=60.0,
        last_beat=0.0,
        epochs=2,
    )


def test_on_fit_epoch_end__epoch_without_validation_skips_map50_not_loss() -> None:
    """Epoch không có pha validate: một điểm `train`, log bỏ đúng `map50` (không log `loss` lần hai) (NO-320)."""
    reporter = RecordingReporter()
    callbacks = _callbacks(reporter)
    callbacks.on_fit_epoch_end(SimpleNamespace(tloss={"box": 1.0}, metrics={}))
    assert [p.split for p in reporter.metrics] == ["train"]
    skipped = [params["metric"] for _level, template, params in reporter.logs if template == "training_metric_skipped"]
    assert skipped == ["map50"]
    assert callbacks.last_map50 is None


def test_on_fit_epoch_end__nan_loss_keeps_the_valid_map50() -> None:
    """`loss` NaN mà `map50` hợp lệ: điểm validation đã gửi thì `last_map50` phải nhận nó (NO-320)."""
    reporter = RecordingReporter()
    callbacks = _callbacks(reporter)
    callbacks.on_fit_epoch_end(SimpleNamespace(tloss={"box": float("nan")}, metrics={"metrics/mAP50(B)": 0.4}))
    assert [(p.split, p.map50) for p in reporter.metrics] == [("validation", 0.4)]
    assert callbacks.last_map50 == pytest.approx(0.4)
    skipped = [params["metric"] for _level, template, params in reporter.logs if template == "training_metric_skipped"]
    assert skipped == ["loss"]
    assert "training_epoch_finished" not in [template for _level, template, _params in reporter.logs]


def test_on_val_batch_end__sends_heartbeat_once_interval_passed() -> None:
    """Pha validate không có batch train: `on_val_batch_end` vẫn gửi nhịp tim khi qua hạn, và hỏi huỷ (NO-321)."""
    reporter = RecordingReporter()
    callbacks = _callbacks(reporter, monotonic=61.0)
    callbacks.on_val_batch_end(None)
    assert reporter.heartbeats == [1]
    assert reporter.cancel_checks == 1


def test_heartbeat_epochs_never_decrease_nor_exceed_spec_epochs() -> None:
    """Pha `final_eval` chạy sau epoch cuối: nhịp tim không được báo `epochs + 1`, rồi `_export` báo `epochs` (lùi)."""
    reporter = RecordingReporter()
    clock = [0.0]
    callbacks = _RunCallbacks(
        reporter=reporter,
        clock=SystemClock(),
        monotonic=lambda: clock[0],
        heartbeat_every_s=1.0,
        last_beat=0.0,
        epochs=2,
    )
    for _ in range(2):
        clock[0] += 2.0
        callbacks.on_train_batch_end(None)
        callbacks.on_fit_epoch_end(SimpleNamespace(tloss={"box": 1.0}, metrics={"metrics/mAP50(B)": 0.4}))
    clock[0] += 2.0
    callbacks.on_val_batch_end(None)
    reporter.heartbeat(2)  # `_export` báo `spec.epochs`
    assert reporter.heartbeats == sorted(reporter.heartbeats)
    assert max(reporter.heartbeats) <= 2


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
