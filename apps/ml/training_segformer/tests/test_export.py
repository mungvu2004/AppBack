"""Test `export.export_and_check`: từ chối dữ liệu ngoài, bất khớp tương đương, ca thật (khối [6])."""

import copy
import logging
import time
from pathlib import Path
from typing import cast

import onnxruntime as ort  # type: ignore[import-untyped]  # onnxruntime 1.30 không có py.typed
import pytest
import torch
from onnx import TensorProto, helper

from apps.ml.training_runner.errors import TrainingStopped
from apps.ml.training_segformer import export as segformer_export
from apps.ml.training_segformer import model as segformer_model
from apps.ml.training_segformer.config import SegformerTrainConfig
from apps.ml.training_segformer.errors import MODEL_EXPORT_MISMATCH, MODEL_FORMAT_UNSUPPORTED
from apps.ml.training_segformer.tests.support import (
    RecordingReporter,
    onnx_segmenter,
    write_dataset,
    write_pinned_tiny_model,
)
from packages.messaging.payloads.training import render_log
from packages.messaging.tasks import PermanentError


def _tiny_model(tmp_path: Path) -> torch.nn.Module:
    """Model tí hon tiêm sẵn checksum khớp, để test không chạm mạng (khối [5])."""
    models_dir = tmp_path / "models"
    return segformer_model.load_pretrained(models_dir, "mitB0", write_pinned_tiny_model(models_dir))


def test_export_rejects_external_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`export_onnx` giả ghi ONNX có tensor ngoài + tệp phụ → `MODEL_FORMAT_UNSUPPORTED`."""

    def _fake_export_onnx(_model: object, _sample: object, path: Path, *, opset: int) -> str:
        """Dựng ONNX hợp lệ về cấu trúc nhưng có một initializer trỏ dữ liệu ngoài."""
        value_in = helper.make_tensor_value_info("x", TensorProto.FLOAT, [1])
        value_out = helper.make_tensor_value_info("y", TensorProto.FLOAT, [1])
        weight = helper.make_tensor("w", TensorProto.FLOAT, [1], [1.0])
        weight.data_location = TensorProto.EXTERNAL
        entry = weight.external_data.add()
        entry.key = "location"
        entry.value = "weights.bin"
        node = helper.make_node("Add", ["x", "w"], ["y"])
        graph = helper.make_graph([node], "g", [value_in], [value_out], [weight])
        onnx_model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", opset)])
        path.write_bytes(onnx_model.SerializeToString())
        (path.parent / "weights.bin").write_bytes(b"\x00\x00\x80?")
        return "unused"

    monkeypatch.setattr(segformer_export, "export_onnx", _fake_export_onnx)
    model = _tiny_model(tmp_path)
    data_dir = tmp_path / "data"
    write_dataset(data_dir)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    reporter = RecordingReporter()
    with pytest.raises(PermanentError) as excinfo:
        segformer_export.export_and_check(
            model, out_dir, data_dir / "validation", config=SegformerTrainConfig(), reporter=reporter
        )
    assert excinfo.value.code == MODEL_FORMAT_UNSUPPORTED


def test_export_rejects_garbage_onnx_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`export_onnx` giả ghi byte rác → `onnx.load` ném `DecodeError` → `MODEL_FORMAT_UNSUPPORTED`."""

    def _fake_export_onnx(_model: object, _sample: object, path: Path, *, opset: int) -> str:
        """Ghi byte rác duy nhất vào `path` — không phải `ModelProto` giải được."""
        path.write_bytes(b"\xff\xfe\x00not-a-real-onnx-model")
        return "unused"

    monkeypatch.setattr(segformer_export, "export_onnx", _fake_export_onnx)
    model = _tiny_model(tmp_path)
    data_dir = tmp_path / "data"
    write_dataset(data_dir)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    reporter = RecordingReporter()
    with pytest.raises(PermanentError) as excinfo:
        segformer_export.export_and_check(
            model, out_dir, data_dir / "validation", config=SegformerTrainConfig(), reporter=reporter
        )
    assert excinfo.value.code == MODEL_FORMAT_UNSUPPORTED


def test_export_parity_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`export_onnx` giả: đảo dấu weight/bias `decode_head.classifier` rồi xuất thật → `MODEL_EXPORT_MISMATCH`."""
    from apps.ml.runtime.export import export_onnx as real_export_onnx

    def _flipped_export_onnx(wrapped_model: torch.nn.Module, sample: torch.Tensor, path: Path, *, opset: int) -> str:
        """Đảo dấu lớp phân loại của **bản sao** rồi xuất bản sao — model gốc dùng để so sánh không đổi."""
        mutated = cast(segformer_export._LogitsOnly, copy.deepcopy(wrapped_model))
        inner = mutated.inner
        head = inner.decode_head
        classifier = cast(torch.nn.Conv2d, head.classifier)  # type: ignore[union-attr]  # head là Module thật
        with torch.no_grad():
            classifier.weight.mul_(-1.0)
            assert classifier.bias is not None
            classifier.bias.mul_(-1.0)
        return real_export_onnx(mutated, sample, path, opset=opset)

    monkeypatch.setattr(segformer_export, "export_onnx", _flipped_export_onnx)
    model = _tiny_model(tmp_path)
    data_dir = tmp_path / "data"
    write_dataset(data_dir)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    reporter = RecordingReporter()
    with pytest.raises(PermanentError) as excinfo:
        segformer_export.export_and_check(
            model, out_dir, data_dir / "validation", config=SegformerTrainConfig(), reporter=reporter
        )
    assert excinfo.value.code == MODEL_EXPORT_MISMATCH


def test_export_and_check_real_model(tmp_path: Path) -> None:
    """Model tí hon thật: `model.onnx` duy nhất, nạp được qua `SegformerOnnxSegmenter`, IoU hợp lệ, log đủ."""
    model = _tiny_model(tmp_path)
    data_dir = tmp_path / "data"
    write_dataset(data_dir)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    reporter = RecordingReporter()
    start = time.monotonic()
    iou = segformer_export.export_and_check(
        model, out_dir, data_dir / "validation", config=SegformerTrainConfig(), reporter=reporter
    )
    logging.getLogger(__name__).info("export_and_check thật %.3fs iou=%.4f", time.monotonic() - start, iou)
    assert 0.0 <= iou <= 1.0
    written = list(out_dir.iterdir())
    assert written == [out_dir / "model.onnx"]

    onnx_segmenter(out_dir / "model.onnx")

    exported = next(params for level, template, params in reporter.logs if template == "training_exported")
    parity = next(params for level, template, params in reporter.logs if template == "training_parity")
    assert render_log("training_exported", exported) is not None
    assert render_log("training_parity", parity) is not None


def test_export_rejects_external_data_without_extra_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ONNX hợp lệ cấu trúc, một tệp duy nhất, nhưng tensor trỏ dữ liệu ngoài → `MODEL_FORMAT_UNSUPPORTED`."""

    def _fake_export_onnx(_model: object, _sample: object, path: Path, *, opset: int) -> str:
        """Ghi đúng một tệp `model.onnx` nhưng initializer đánh dấu `EXTERNAL` (dữ liệu không kèm theo)."""
        value_in = helper.make_tensor_value_info("x", TensorProto.FLOAT, [1])
        value_out = helper.make_tensor_value_info("y", TensorProto.FLOAT, [1])
        weight = helper.make_tensor("w", TensorProto.FLOAT, [1], [1.0])
        weight.data_location = TensorProto.EXTERNAL
        entry = weight.external_data.add()
        entry.key = "location"
        entry.value = "weights.bin"
        node = helper.make_node("Add", ["x", "w"], ["y"])
        graph = helper.make_graph([node], "g", [value_in], [value_out], [weight])
        onnx_model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", opset)])
        path.write_bytes(onnx_model.SerializeToString())
        return "unused"

    monkeypatch.setattr(segformer_export, "export_onnx", _fake_export_onnx)
    model = _tiny_model(tmp_path)
    data_dir = tmp_path / "data"
    write_dataset(data_dir)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    reporter = RecordingReporter()
    with pytest.raises(PermanentError) as excinfo:
        segformer_export.export_and_check(
            model, out_dir, data_dir / "validation", config=SegformerTrainConfig(), reporter=reporter
        )
    assert excinfo.value.code == MODEL_FORMAT_UNSUPPORTED


def test_export_onnx_runtime_error_is_format_unsupported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`session.run` ném lỗi `onnxruntime` thật (`ORT_ERRORS`) → `MODEL_FORMAT_UNSUPPORTED`."""
    from onnxruntime.capi.onnxruntime_pybind11_state import Fail  # type: ignore[import-untyped]  # không stub

    model = _tiny_model(tmp_path)
    data_dir = tmp_path / "data"
    write_dataset(data_dir)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    reporter = RecordingReporter()
    real_session_cls = ort.InferenceSession

    class _FailingSession:
        """Phiên giả: vào/ra giống thật nhưng `run` luôn ném lỗi `onnxruntime`."""

        def __init__(self, data: bytes, providers: list[str]) -> None:
            """Dựng phiên thật để `get_inputs`/`get_outputs` đúng hợp đồng B5-02."""
            self._real = real_session_cls(data, providers=providers)

        def get_inputs(self) -> object:
            """Uỷ quyền cho phiên thật."""
            return self._real.get_inputs()

        def get_outputs(self) -> object:
            """Uỷ quyền cho phiên thật."""
            return self._real.get_outputs()

        def run(self, *_args: object, **_kwargs: object) -> object:
            """Luôn ném lỗi `onnxruntime` thật để kiểm nhánh `ORT_ERRORS`."""
            raise Fail("lỗi onnxruntime giả lập cho test")

    monkeypatch.setattr("apps.ml.training_segformer.export.ort.InferenceSession", _FailingSession)
    with pytest.raises(PermanentError) as excinfo:
        segformer_export.export_and_check(
            model, out_dir, data_dir / "validation", config=SegformerTrainConfig(), reporter=reporter
        )
    assert excinfo.value.code == MODEL_FORMAT_UNSUPPORTED


def test_export_and_check_validation_split_empty(tmp_path: Path) -> None:
    """`validation_dir` không có mẫu nào (nhưng không rỗng tới mức bỏ qua tương đương) → `DATASET_SPLIT_EMPTY`."""
    model = _tiny_model(tmp_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    reporter = RecordingReporter()
    with pytest.raises(PermanentError) as excinfo:
        segformer_export.export_and_check(
            model, out_dir, tmp_path / "no_such_validation", config=SegformerTrainConfig(), reporter=reporter
        )
    from apps.ml.training_segformer.errors import DATASET_SPLIT_EMPTY

    assert excinfo.value.code == DATASET_SPLIT_EMPTY


def test_export_and_check_cancelled_during_parity_raises(tmp_path: Path) -> None:
    """Huỷ ngay khi tương đương bắt đầu chạy lát → `TrainingStopped`."""
    model = _tiny_model(tmp_path)
    data_dir = tmp_path / "data"
    write_dataset(data_dir)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    reporter = RecordingReporter(cancel_when=lambda calls: calls >= 1)
    with pytest.raises(TrainingStopped):
        segformer_export.export_and_check(
            model, out_dir, data_dir / "validation", config=SegformerTrainConfig(), reporter=reporter
        )
