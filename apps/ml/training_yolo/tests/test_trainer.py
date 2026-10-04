"""Test `YoloTrainer` (khối [8] "Huấn luyện"): kiểm đầu vào, lượt CPU tí hon, nhánh cuda, huỷ, log.

Một lượt huấn luyện thật duy nhất (fixture `trained`, `scope="module"`) gánh mọi khẳng định của
lượt CPU — chạy lại cho từng khẳng định sẽ vượt trần 120 s. Mạng bị chặn ở mức `socket` cho cả
module: một lượt chỉ "ngoại tuyến" khi nó chạy xong với `connect` ném.
"""

import dataclasses
import itertools
import logging
import socket
import time
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, Final

import pytest

from apps.ml.training_segformer.tests.support import RecordingReporter, pinned_for, train_spec
from apps.ml.training_yolo.settings import YoloTrainSettings
from apps.ml.training_yolo.tests.support import write_micro_dataset
from apps.ml.training_yolo.trainer import TRAINER, YoloTrainer, prepare_ultralytics
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.families import TrainableFamily
from packages.ml_contracts.pinned import PinnedWeights, file_sha256

_log: Final = logging.getLogger(__name__)
_BASE: Final = "yolov8n"
_IMGSZ: Final = 320
_FAMILY: Final[TrainableFamily] = "openingAndFurnitureDetection"
_MICRO_SAMPLES: Final = 6
"""Số mẫu của `write_micro_dataset`; `build_yolo_dataset` hỏi `cancelled()` một lần mỗi mẫu (khối [2])."""


def _refuse(*_args: object, **_kwargs: object) -> None:
    """Bản thay `socket.socket.connect`: mọi lượt ra mạng trong test là lỗi (khối [9])."""
    raise AssertionError("test không được ra mạng")


def _block_loaders(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chặn `ultralytics.YOLO` và `torch.load`: ca kiểm đầu vào không được chạm bộ giải pickle (K12)."""
    import torch

    prepare_ultralytics()
    import ultralytics

    monkeypatch.setattr(ultralytics, "YOLO", _refuse)
    monkeypatch.setattr(torch, "load", _refuse)


@pytest.fixture(scope="module", autouse=True)
def offline_calls() -> Iterator[list[object]]:
    """Chặn `socket.connect` và spy `requests.head` cho cả module; trả danh sách lời gọi `head`."""
    import requests

    calls: list[object] = []
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(socket.socket, "connect", _refuse)
        patch.setattr(requests, "head", lambda *a, **k: calls.append((a, k)))
        yield calls


@pytest.fixture(scope="module")
def tiny_pt(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Mapping[str, PinnedWeights]]:
    """`.pt` tí hon dựng ngoại tuyến từ `yolov8n.yaml`, kèm bản ghim mang SHA thật của nó."""
    prepare_ultralytics()
    from ultralytics import YOLO  # type: ignore[attr-defined]  # ultralytics không khai __all__ cho YOLO

    models_dir = tmp_path_factory.mktemp("models")
    target = models_dir / _BASE
    target.mkdir()
    YOLO(f"{_BASE}.yaml").save(target / f"{_BASE}.pt")
    return models_dir, pinned_for(file_sha256(target / f"{_BASE}.pt"), _BASE)


def _trainer(
    tiny_pt: tuple[Path, Mapping[str, PinnedWeights]],
    **kwargs: Any,
) -> YoloTrainer:
    """`YoloTrainer` của test: `imgsz=320`, `models_dir` và `pinned` tiêm, `monotonic` nhảy 60 s mỗi lần."""
    models_dir, pinned = tiny_pt
    ticks = itertools.count(0.0, 60.0)
    defaults: dict[str, Any] = {
        "settings": YoloTrainSettings(imgsz=_IMGSZ),
        "pinned": pinned,
        "models_dir": models_dir,
        "monotonic": lambda: next(ticks),
    }
    return YoloTrainer(**{**defaults, **kwargs})


def _spec(**kwargs: Any) -> Any:
    """`TrainSpec` họ dò vật, model gốc `yolov8n`, CPU."""
    return train_spec(family=_FAMILY, base_model=_BASE, **kwargs)


@pytest.fixture(scope="module")
def trained(
    tmp_path_factory: pytest.TempPathFactory, tiny_pt: tuple[Path, Mapping[str, PinnedWeights]]
) -> tuple[Any, RecordingReporter, Path]:
    """Lượt CPU tí hon 2 epoch dùng chung cho mọi khẳng định của khối [8]; in thời gian bằng `logging`."""
    base = tmp_path_factory.mktemp("cpu-run")
    data_dir = write_micro_dataset(base / "data")
    out_dir = base / "out"
    out_dir.mkdir()
    reporter = RecordingReporter()
    started = time.monotonic()
    result = _trainer(tiny_pt).train(_spec(epochs=2), data_dir, out_dir, reporter)
    _log.info("lượt CPU tí hon: %.1f s", time.monotonic() - started)
    return result, reporter, out_dir


def test_cpu_run_exports_loadable_onnx(trained: tuple[Any, RecordingReporter, Path]) -> None:
    """`model.onnx` dựng được `YoloOnnxDetector`, đầu vào `(1, 3, 320, 320)` (khối [8])."""
    import onnxruntime as ort  # type: ignore[import-untyped]  # onnxruntime 1.30 không có py.typed

    from apps.ml.objects.detector import YoloOnnxDetector
    from apps.ml.objects.labels import ARTIFACT_LABELS

    result, _reporter, out_dir = trained
    assert result.onnx_path == out_dir / "model.onnx"
    session = ort.InferenceSession(result.onnx_path.read_bytes(), providers=["CPUExecutionProvider"])
    assert session.get_inputs()[0].shape == [1, 3, _IMGSZ, _IMGSZ]
    assert YoloOnnxDetector(session, ARTIFACT_LABELS).input_px == _IMGSZ


def test_cpu_run_reports_metric_points(trained: tuple[Any, RecordingReporter, Path]) -> None:
    """Mỗi epoch một điểm `train` và một điểm `validation`; `step` tăng ngặt, thời điểm không giảm."""
    result, reporter, _out_dir = trained
    train_points = [p for p in reporter.metrics if p.split == "train"]
    validation = [p for p in reporter.metrics if p.split == "validation"]
    assert len(train_points) == 2
    assert len(validation) == 2
    for points in (train_points, validation):
        assert [p.step for p in points] == sorted({p.step for p in points})
    assert [p.recorded_at_ms for p in reporter.metrics] == sorted(p.recorded_at_ms for p in reporter.metrics)
    assert all(p.loss is not None and p.loss >= 0 for p in train_points)
    assert all(p.map50 is not None and 0.0 <= p.map50 <= 1.0 for p in validation)
    assert result.metrics == {"map50": validation[-1].map50}
    assert len(reporter.heartbeats) >= 2


def test_cpu_run_leaves_only_onnx(trained: tuple[Any, RecordingReporter, Path]) -> None:
    """Lượt đạt để lại đúng `model.onnx`: không `.pt`, không thư mục `ultralytics`, không `yolo-*`."""
    _result, _reporter, out_dir = trained
    assert [p.name for p in out_dir.rglob("*")] == ["model.onnx"]
    assert list(out_dir.rglob("*.pt")) == []
    assert list(out_dir.parent.glob("yolo-*")) == []


def test_cpu_run_stays_offline(trained: tuple[Any, RecordingReporter, Path], offline_calls: list[object]) -> None:
    """Lượt chạy xong với `connect` bị chặn; `settings["sync"]` tắt, `Arial.ttf` có sẵn, `requests.head` không gọi."""
    prepare_ultralytics()
    from ultralytics import settings as yolo_settings

    assert yolo_settings["sync"] is False
    assert (prepare_ultralytics() / "Ultralytics" / "Arial.ttf").is_file()
    assert offline_calls == []


def test_check_amp_replaced_in_both_modules() -> None:
    """`check_amp` ở `utils.checks` và `engine.trainer` là bản thay, trả `True` khi mạng bị chặn (M03)."""
    prepare_ultralytics()
    from ultralytics.engine import trainer as yolo_trainer
    from ultralytics.utils import checks

    with pytest.MonkeyPatch.context() as patch:
        import torch

        patch.setattr(torch, "load", _refuse)
        assert checks.check_amp(None) is True  # type: ignore[no-untyped-call]  # ultralytics không chú kiểu
        assert yolo_trainer.check_amp(None) is True  # type: ignore[attr-defined, no-untyped-call]  # như trên


@pytest.mark.parametrize(
    ("family", "base_model"),
    [(_FAMILY, "mitB0"), ("wallSegmentation", _BASE)],
    ids=["base-model-of-other-family", "wrong-family"],
)
def test_rejects_foreign_spec(
    tmp_path: Path,
    tiny_pt: tuple[Path, Mapping[str, PinnedWeights]],
    family: TrainableFamily,
    base_model: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Họ sai hay model gốc lạ → `TRAINING_BASE_MODEL_MISMATCH` trước khi chạm `YOLO`, `torch.load`."""
    _block_loaders(monkeypatch)
    spec = train_spec(family=family, base_model=base_model)
    with pytest.raises(PermanentError) as caught:
        _trainer(tiny_pt).train(spec, tmp_path, tmp_path, RecordingReporter())
    assert caught.value.code == "TRAINING_BASE_MODEL_MISMATCH"


def test_rejects_weights_with_wrong_sha(
    tmp_path: Path, tiny_pt: tuple[Path, Mapping[str, PinnedWeights]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`.pt` ghim lệch SHA → `MODEL_CHECKSUM_MISMATCH`, không bộ giải pickle nào chạy (K12)."""
    _block_loaders(monkeypatch)
    trainer = _trainer(tiny_pt, pinned=pinned_for("0" * 64, _BASE))
    with pytest.raises(PermanentError) as caught:
        trainer.train(_spec(), tmp_path, tmp_path, RecordingReporter())
    assert caught.value.code == "MODEL_CHECKSUM_MISMATCH"


class _FakeUltralyticsTrainer:
    """Bộ `trainer` giả mà callback nhận ở nhánh `cuda`: đủ `tloss` và `metrics` cho một epoch."""

    def __init__(self, map50: float | None) -> None:
        """`map50=None` dựng epoch không có số đo (ca `TRAINING_METRICS_MISSING`)."""
        self.tloss = {"box": 1.0, "cls": 0.5}
        self.metrics = {} if map50 is None else {"metrics/mAP50(B)": map50}


def _fake_train(
    out_dir: Path,
    map50: float | None,
    recorded: dict[str, Any],
) -> Any:
    """Bản thay `Model.train`: ghi tham số, tạo `best.pt` rỗng rồi chạy callback của một epoch."""

    def run(self: Any, **kwargs: Any) -> None:
        """Ghi `kwargs`, dựng `best.pt` giả rồi phát callback."""
        recorded.update(kwargs)
        weights = out_dir / "ultralytics" / "run" / "weights"
        weights.mkdir(parents=True, exist_ok=True)
        (weights / "best.pt").write_bytes(b"not-a-real-checkpoint")
        for callback in self.callbacks["on_train_batch_end"]:
            callback(None)
        for callback in self.callbacks["on_fit_epoch_end"]:
            callback(_FakeUltralyticsTrainer(map50))

    return run


@pytest.fixture(scope="module")
def originals() -> dict[str, object]:
    """Bản gốc của hai thuộc tính `fake_run` vá, chụp lần đầu fixture được dùng trong module — với `fake_run` là
    trước lần vá đầu; `test_zz_fake_run_restores_originals` chạy lẻ thì chụp ngay lúc đó."""
    prepare_ultralytics()
    from ultralytics.engine import model as model_module

    from apps.ml.runtime import export_yolo as export_module

    return {"export_yolo": export_module.export_yolo, "Model.train": model_module.Model.train}


@pytest.fixture
def fake_run(
    tmp_path: Path, trained: tuple[Any, RecordingReporter, Path], originals: dict[str, object]
) -> Iterator[tuple[Path, Path, dict[str, Any], dict[str, Any], pytest.MonkeyPatch]]:
    """Vá `Model.train` và `export_yolo` (chỉ hai chỗ này, khối [8]); `export_yolo` chép ONNX đã xuất thật.

    Trả cả `patch`: test cần vá đè hai thuộc tính này phải vá qua CHÍNH context này, không qua fixture
    `monkeypatch` — hai MonkeyPatch hoàn tác lệch thứ tự sẽ trả `export_yolo` về bản giả thay vì bản gốc,
    rò sang test sau cùng tiến trình (FIX-137: `apps/ml/runtime/tests/test_export.py` nhận ONNX "sha").
    """
    result, _reporter, _out = trained
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    data_dir = write_micro_dataset(tmp_path / "data")
    train_args: dict[str, Any] = {}
    export_args: dict[str, Any] = {}
    payload = result.onnx_path.read_bytes()

    def fake_export(_pt: Path, target: Path, **kwargs: Any) -> str:
        """Ghi lại tham số rồi chép ONNX thật để bước kiểm xuất vẫn chạy trên tệp hợp lệ."""
        export_args.update(kwargs)
        target.write_bytes(payload)
        return "sha"

    prepare_ultralytics()
    from ultralytics.engine import model as model_module

    from apps.ml.runtime import export_yolo as export_module

    assert export_module.export_yolo is originals["export_yolo"]
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(export_module, "export_yolo", fake_export)
        patch.setattr(model_module.Model, "train", _fake_train(out_dir, 0.5, train_args))
        yield data_dir, out_dir, train_args, export_args, patch


@pytest.mark.parametrize(("base_model", "batch"), [("yolov8n", 16), ("yolov8s", 8)])
def test_cuda_branch_uses_gpu_arguments(
    fake_run: tuple[Path, Path, dict[str, Any], dict[str, Any], pytest.MonkeyPatch],
    tiny_pt: tuple[Path, Mapping[str, PinnedWeights]],
    base_model: str,
    batch: int,
) -> None:
    """`device="cuda"` → `device=0`, `amp=True`, `batch` theo model gốc, `plots=False` (CI không GPU)."""
    data_dir, out_dir, train_args, _export_args, _patch = fake_run
    models_dir, _pinned = tiny_pt
    pinned = {**pinned_for(file_sha256(models_dir / "yolov8n" / "yolov8n.pt"), "yolov8n")}
    pinned[base_model] = pinned["yolov8n"]
    (models_dir / base_model).mkdir(exist_ok=True)
    (models_dir / base_model / "yolov8n.pt").write_bytes((models_dir / "yolov8n" / "yolov8n.pt").read_bytes())
    spec = dataclasses.replace(train_spec(family=_FAMILY, base_model=base_model, epochs=1), device="cuda")
    _trainer(tiny_pt, pinned=pinned).train(spec, data_dir, out_dir, RecordingReporter())
    assert train_args["device"] == 0
    assert train_args["amp"] is True
    assert train_args["batch"] == batch
    assert train_args["plots"] is False


def test_missing_metrics_fails_the_run(
    fake_run: tuple[Path, Path, dict[str, Any], dict[str, Any], pytest.MonkeyPatch],
    tiny_pt: tuple[Path, Mapping[str, PinnedWeights]],
) -> None:
    """Không epoch nào cho `map50` → `TRAINING_METRICS_MISSING` và `out_dir` rỗng."""
    prepare_ultralytics()
    from ultralytics.engine import model as model_module

    data_dir, out_dir, train_args, _export_args, patch = fake_run
    patch.setattr(model_module.Model, "train", _fake_train(out_dir, None, train_args))
    with pytest.raises(PermanentError) as caught:
        _trainer(tiny_pt).train(_spec(epochs=1), data_dir, out_dir, RecordingReporter())
    assert caught.value.code == "TRAINING_METRICS_MISSING"
    assert list(out_dir.iterdir()) == []


def test_broken_export_is_rejected(
    fake_run: tuple[Path, Path, dict[str, Any], dict[str, Any], pytest.MonkeyPatch],
    tiny_pt: tuple[Path, Mapping[str, PinnedWeights]],
) -> None:
    """ONNX xuất ra không giải được → `MODEL_FORMAT_UNSUPPORTED`, không artifact nào ở lại."""
    from apps.ml.runtime import export_yolo as export_module

    data_dir, out_dir, _train_args, _export_args, patch = fake_run

    def broken(_pt: Path, target: Path, **_kwargs: Any) -> str:
        """Ghi byte không phải ONNX."""
        target.write_bytes(b"\x00\x01not-an-onnx-graph")
        return "sha"

    patch.setattr(export_module, "export_yolo", broken)
    with pytest.raises(PermanentError) as caught:
        _trainer(tiny_pt).train(_spec(epochs=1), data_dir, out_dir, RecordingReporter())
    assert caught.value.code == "MODEL_FORMAT_UNSUPPORTED"
    assert list(out_dir.iterdir()) == []


@pytest.mark.parametrize("cancel_at", [1, _MICRO_SAMPLES + 1], ids=["while-tiling", "after-first-batch"])
def test_cancel_stops_the_run(
    fake_run: tuple[Path, Path, dict[str, Any], dict[str, Any], pytest.MonkeyPatch],
    tiny_pt: tuple[Path, Mapping[str, PinnedWeights]],
    cancel_at: int,
) -> None:
    """Huỷ lúc đang lát hay sau batch đầu → `TrainingStopped`, không `model.onnx`, không rác tạm (J04)."""
    from apps.ml.training_runner.errors import TrainingStopped

    data_dir, out_dir, _train_args, _export_args, _patch = fake_run
    reporter = RecordingReporter(cancel_when=lambda calls: calls >= cancel_at)
    with pytest.raises(TrainingStopped):
        _trainer(tiny_pt).train(_spec(epochs=1), data_dir, out_dir, reporter)
    assert list(out_dir.iterdir()) == []
    assert list(out_dir.parent.glob("yolo-*")) == []


def test_log_templates_render(trained: tuple[Any, RecordingReporter, Path]) -> None:
    """Mọi dòng log ghi được phải khớp mẫu BE-00 §9 và không mang đường dẫn hay URL."""
    from packages.messaging.payloads.training import render_log

    _result, reporter, _out_dir = trained
    assert [level for level, _key, _params in reporter.logs if level == "error"] == []
    for _level, key, params in reporter.logs:
        assert render_log(key, params) is not None
        assert not any(mark in str(value) for value in params.values() for mark in ("/", "\\", "://"))


def test_discover_trainers_finds_this_trainer() -> None:
    """Runner B6-03b phải tìm thấy `TRAINER` theo họ `openingAndFurnitureDetection`."""
    from apps.ml.runtime.trainers import discover_trainers

    assert discover_trainers()[_FAMILY] is TRAINER


def test_zz_fake_run_restores_originals(originals: dict[str, object]) -> None:
    """FIX-137: `export_yolo` và `Model.train` là bản gốc — chạy cả tệp thì so với bản chụp trước lần vá đầu của
    `fake_run` (không bản giả nào rò qua các test trước); chạy lẻ thì bản chụp là chính giá trị hiện tại."""
    prepare_ultralytics()
    from ultralytics.engine import model as model_module

    from apps.ml.runtime import export_yolo as export_module

    assert export_module.export_yolo is originals["export_yolo"]
    assert model_module.Model.train is originals["Model.train"]


def test_trainer__keyword_only_and_family_fixed() -> None:
    """Ctor chỉ nhận keyword và không cho tiêm `family` (khối [2], cùng lệch P3-10 của segformer)."""
    ctor: Any = YoloTrainer
    with pytest.raises(TypeError):
        ctor(YoloTrainSettings())
    with pytest.raises(TypeError):
        ctor(family="wallSegmentation")
    assert YoloTrainer().family == _FAMILY
