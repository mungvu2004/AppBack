"""Lượt huấn luyện đầu-cuối, huỷ, nhịp tim, lỗi dữ liệu/model (khối [8]).

Một lượt `train` thật dùng chung cho `happy_path`, `m05`, `offline`, `log_templates` (fixture
phạm vi module): lượt đó là phần đắt nhất của bộ test, chạy lại bốn lần là vô ích. Các ca
huỷ/nhịp tim/loss không hữu hạn không cần trọng số thật nên dùng một `nn.Module` tí hon —
nó là torch **thật**, không phải mock (K23); chỉ hàm dựng model của `model.py` là bị vá.
"""

import logging
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import pytest
import torch
from torch import nn
from torch.nn import functional
from torch.utils.data import DataLoader

from apps.ml.runtime.trainers import discover_trainers
from apps.ml.training_runner.errors import TrainingStopped
from apps.ml.training_segformer import errors, loop, trainer
from apps.ml.training_segformer import model as segformer_model
from apps.ml.training_segformer.config import SegformerTrainConfig
from apps.ml.training_segformer.data import read_sample
from apps.ml.training_segformer.tests.support import (
    RecordingReporter,
    onnx_segmenter,
    train_spec,
    write_dataset,
    write_pinned_tiny_model,
    write_split,
)
from apps.ml.walls.spec import LOGITS_STRIDE
from packages.core.clock import SystemClock
from packages.messaging.payloads.training import render_log
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.artifacts import encode_mask
from packages.ml_contracts.ports import TrainResult
from packages.ml_contracts.synthetic import render_plan

_log: Final = logging.getLogger(__name__)
_CROP_PX: Final = 128
_CONFIG: Final = SegformerTrainConfig(crop_px=_CROP_PX, log_every_steps=1)


class _TinyNet(nn.Module):
    """Model nhỏ nhất đi đúng hợp đồng SegFormer: `(1,3,T,T)` → logits `(1,2,T/4,T/4)` + `loss`.

    Dùng cho các ca không cần trọng số ghim (huỷ, nhịp tim, loss NaN): nạp model tí hon thật
    tốn vài giây mỗi test mà không kiểm thêm điều gì. `broken=True` trả `loss` NaN để thử K
    `TRAINING_LOSS_NOT_FINITE` mà không vá `transformers`.
    """

    def __init__(self, *, broken: bool = False) -> None:
        """Một lớp chập stride `LOGITS_STRIDE` — đúng tỉ lệ logit mà `stitch_mask` chờ."""
        super().__init__()
        self.head = nn.Conv2d(3, 2, kernel_size=LOGITS_STRIDE, stride=LOGITS_STRIDE)
        self.broken = broken
        self.forwards = 0
        self.train_modes: list[bool] = []

    def forward(self, pixel_values: torch.Tensor, labels: torch.Tensor | None = None) -> "_TinyOut":
        """Logits + loss entropy chéo trên logits đã phóng về khổ nhãn, như `SegformerForSemanticSegmentation`."""
        self.forwards += 1
        logits = self.head(pixel_values)
        if labels is None:
            return _TinyOut(logits=logits, loss=None)
        self.train_modes.append(self.training)
        upsampled = functional.interpolate(logits, size=labels.shape[-2:], mode="bilinear")
        loss = functional.cross_entropy(upsampled, labels)
        return _TinyOut(logits=logits, loss=loss * float("nan") if self.broken else loss)


@dataclass(frozen=True, slots=True)
class _TinyOut:
    """Đầu ra kiểu `SemanticSegmenterOutput`: chỉ hai thuộc tính mà vòng và `metrics` dùng tới."""

    logits: torch.Tensor
    loss: torch.Tensor | None


class _CountingAdamW(torch.optim.AdamW):
    """`AdamW` thật, chỉ đếm số lần `step` — chứng minh `scaler.step` đi tới optimizer (M04, J04)."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Giữ nguyên chữ ký `AdamW`; bộ đếm bắt đầu 0."""
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]  # AdamW không chú kiểu *args
        self.steps = 0

    def step(self, closure: object = None) -> None:  # type: ignore[override]  # chữ ký AdamW rộng hơn
        """Đếm rồi gọi bước thật."""
        self.steps += 1
        super().step()


def _fake_monotonic(advance: float) -> Callable[[], float]:
    """Đồng hồ `monotonic` giả tăng `advance` giây mỗi lần hỏi (J07 cần tất định, không ngủ thật)."""
    ticks = [0.0]

    def monotonic() -> float:
        """Trả mốc hiện tại rồi tăng."""
        now = ticks[0]
        ticks[0] += advance
        return now

    return monotonic


@pytest.fixture(scope="module")
def trained(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[TrainResult, RecordingReporter, Path]]:
    """Một lượt `train` CPU thật (1 epoch, `crop_px=128`, model tí hon), mạng bị chặn suốt lượt.

    `test/` có một mẫu PNG cụt: lượt vẫn phải đạt, vì trainer không được đọc split đó.
    """
    root = tmp_path_factory.mktemp("trained")
    data_dir, models_dir, out_dir = root / "data", root / "models", root / "out"
    models_dir.mkdir()
    out_dir.mkdir()
    write_dataset(data_dir)
    broken = data_dir / "test" / "s9999"
    broken.mkdir(parents=True)
    (broken / "image.png").write_bytes(render_plan(0, width_px=800, height_px=600).image_png[:64])
    pinned = write_pinned_tiny_model(models_dir)
    reporter = RecordingReporter()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(socket.socket, "connect", _no_network)
        started = time.monotonic()
        result = trainer.SegformerTrainer(
            config=_CONFIG, models_dir=models_dir, pinned=pinned, clock=SystemClock()
        ).train(train_spec(), data_dir, out_dir, reporter)
        _log.info("lượt train chung: %.1f s", time.monotonic() - started)
        yield result, reporter, out_dir


def _no_network(*_args: object, **_kwargs: object) -> None:
    """Thay `socket.socket.connect`: mọi lần gọi là lỗi test (`local_files_only` phải đủ)."""
    raise AssertionError("không được mở kết nối mạng trong test")


def test_train_happy_path(trained: tuple[TrainResult, RecordingReporter, Path]) -> None:
    """`model.onnx` là tệp duy nhất, `metrics` đúng khoá `iou` ∈ [0, 1], log không chứa đường tệp."""
    result, reporter, out_dir = trained
    assert sorted(child.name for child in out_dir.iterdir()) == ["model.onnx"]
    assert result.onnx_path == out_dir / "model.onnx"
    assert set(result.metrics) == {"iou"}
    assert 0.0 <= result.metrics["iou"] <= 1.0
    keys = [template for _level, template, _params in reporter.logs]
    assert {"training_started", "training_epoch_finished", "training_exported", "training_parity"} <= set(keys)
    for _level, _template, params in reporter.logs:
        assert not any(character in str(value) for value in params.values() for character in "/\\")


def test_train_happy_path_onnx_loads(trained: tuple[TrainResult, RecordingReporter, Path]) -> None:
    """`SegformerOnnxSegmenter` nạp được ONNX đã xuất — hợp đồng vào/ra của B5-02 phải qua."""
    result, _reporter, _out_dir = trained
    assert onnx_segmenter(result.onnx_path) is not None


def test_train_m05_metrics_monotonic(trained: tuple[TrainResult, RecordingReporter, Path]) -> None:
    """`step` tăng chặt trong từng split, `epoch ≥ 1`, điểm `validation` cùng `step` với `train` cuối."""
    _result, reporter, _out_dir = trained
    assert reporter.metrics, "lượt train phải báo số đo"
    last: dict[str, int] = {}
    for point in reporter.metrics:
        assert point.epoch >= 1
        assert point.step > last.get(point.split, -1)
        last[point.split] = point.step
    trains = [point for point in reporter.metrics if point.split == "train"]
    validations = [point for point in reporter.metrics if point.split == "validation"]
    assert all(point.loss is not None and point.loss >= 0 for point in trains)
    assert all(point.iou is not None and 0.0 <= point.iou <= 1.0 for point in validations)
    assert validations[-1].step == trains[-1].step


def test_train_offline(trained: tuple[TrainResult, RecordingReporter, Path]) -> None:
    """Lượt chung chạy với `socket.socket.connect` bị chặn: không nhánh nào tải mạng."""
    result, _reporter, _out_dir = trained
    assert result.onnx_path.is_file()


def test_log_templates_render(trained: tuple[TrainResult, RecordingReporter, Path]) -> None:
    """Mọi lời gọi `reporter.log` của lượt chung dựng được câu qua `render_log` (B6-03a)."""
    _result, reporter, _out_dir = trained
    for _level, template, params in reporter.logs:
        assert render_log(template, dict(params)) is not None, template


def test_train_m06_reproducible(trained: tuple[TrainResult, RecordingReporter, Path], tmp_path: Path) -> None:
    """Hai lượt cùng seed → dãy loss và iou bằng nhau; khác seed → mảnh cắt khác (so `WallSegDataset`)."""
    from apps.ml.training_segformer.data import WallSegDataset

    first, first_reporter, _out_dir = trained
    data_dir, models_dir, out_dir = tmp_path / "data", tmp_path / "models", tmp_path / "out"
    models_dir.mkdir()
    out_dir.mkdir()
    write_dataset(data_dir)
    pinned = write_pinned_tiny_model(models_dir)
    reporter = RecordingReporter()
    second = trainer.SegformerTrainer(config=_CONFIG, models_dir=models_dir, pinned=pinned, clock=SystemClock()).train(
        train_spec(), data_dir, out_dir, reporter
    )

    losses = [
        [point.loss for point in source.metrics if point.split == "train"] for source in (first_reporter, reporter)
    ]
    assert len(losses[0]) == len(losses[1])
    for left, right in zip(*losses, strict=True):
        assert left is not None
        assert right is not None
        assert abs(left - right) <= 1e-6
    assert second.metrics["iou"] == first.metrics["iou"]

    same = WallSegDataset(data_dir / "train", crop_px=_CROP_PX, seed=0, epoch=1)[0][0]
    other = WallSegDataset(data_dir / "train", crop_px=_CROP_PX, seed=1, epoch=1)[0][0]
    assert not torch.equal(torch.from_numpy(same), torch.from_numpy(other))


def _run_loop(
    data_dir: Path,
    reporter: RecordingReporter,
    *,
    advance: float = 0.0,
    broken: bool = False,
    config: SegformerTrainConfig = _CONFIG,
    epochs: int = 1,
) -> tuple[_TinyNet, _CountingAdamW]:
    """Chạy `loop.train_model` trên `_TinyNet` với optimizer đếm bước và `monotonic` giả."""
    net = _TinyNet(broken=broken)
    optimizers: list[_CountingAdamW] = []

    def optimizer_cls(*args: object, **kwargs: object) -> _CountingAdamW:
        """Bắt lại optimizer mà vòng dựng, để test đếm bước thật."""
        optimizers.append(_CountingAdamW(*args, **kwargs))
        return optimizers[-1]

    loop.train_model(
        net,
        spec=train_spec(epochs=epochs),
        config=config,
        data_dir=data_dir,
        reporter=reporter,
        clock=SystemClock(),
        monotonic=_fake_monotonic(advance),
        optimizer_cls=optimizer_cls,
    )
    return net, optimizers[0]


def test_train_j04_cancel(tmp_path: Path) -> None:
    """Huỷ từ bước 2 → `TrainingStopped`, không bước tối ưu nào sau đó, `out_dir` rỗng."""
    data_dir, out_dir = tmp_path / "data", tmp_path / "out"
    out_dir.mkdir()
    write_dataset(data_dir)
    (out_dir / "tam.bin").write_bytes(b"rac")
    reporter = RecordingReporter(cancel_when=lambda calls: calls >= 2)
    net = _TinyNet()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(segformer_model, "load_pretrained", lambda *_args: net)
        with pytest.raises(TrainingStopped):
            trainer.SegformerTrainer(config=_CONFIG, models_dir=tmp_path).train(
                train_spec(), data_dir, out_dir, reporter
            )
    assert list(out_dir.iterdir()) == []
    assert net.forwards == 1, "bước 2 phải dừng trước khi gọi model"
    assert ("info", "training_cancelled", {"epoch": 1}) in reporter.logs


def test_train_j04_cancel_during_validation(tmp_path: Path) -> None:
    """Huỷ khi đang đánh giá → dừng trước lát kế, `out_dir` rỗng, không xuất gì."""
    data_dir, out_dir = tmp_path / "data", tmp_path / "out"
    out_dir.mkdir()
    write_dataset(data_dir)
    reporter = RecordingReporter(cancel_when=lambda calls: calls == 3)
    net = _TinyNet()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(segformer_model, "load_pretrained", lambda *_args: net)
        with pytest.raises(TrainingStopped):
            trainer.SegformerTrainer(config=_CONFIG, models_dir=tmp_path).train(
                train_spec(), data_dir, out_dir, reporter
            )
    assert list(out_dir.iterdir()) == []
    assert [point.split for point in reporter.metrics] == ["train", "train"]


def test_train_j07_heartbeat(tmp_path: Path) -> None:
    """`monotonic` tăng 31 s mỗi lần hỏi → nhịp tim mỗi bước; tăng 1 s → chỉ nhịp đầu epoch."""
    data_dir = tmp_path / "data"
    write_dataset(data_dir)
    fast = RecordingReporter()
    _net, optimizer = _run_loop(data_dir, fast, advance=31.0)
    assert optimizer.steps == 2, "4 ảnh, lô 2 → 2 bước"
    assert fast.heartbeats == [1, 1, 1], "một nhịp đầu epoch + một nhịp mỗi bước"

    slow = RecordingReporter()
    _run_loop(data_dir, slow, advance=1.0)
    assert slow.heartbeats == [1]


def test_train_loss_not_finite(tmp_path: Path) -> None:
    """Model trả `loss` NaN → `TRAINING_LOSS_NOT_FINITE`, `out_dir` rỗng, không xuất."""
    data_dir, out_dir = tmp_path / "data", tmp_path / "out"
    out_dir.mkdir()
    write_dataset(data_dir)
    (out_dir / "tam.bin").write_bytes(b"rac")
    net = _TinyNet(broken=True)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(segformer_model, "load_pretrained", lambda *_args: net)
        with pytest.raises(PermanentError) as caught:
            trainer.SegformerTrainer(config=_CONFIG, models_dir=tmp_path).train(
                train_spec(), data_dir, out_dir, RecordingReporter()
            )
    assert caught.value.code == errors.TRAINING_LOSS_NOT_FINITE
    assert list(out_dir.iterdir()) == []


def test_train_base_model_mismatch(tmp_path: Path) -> None:
    """Model gốc hay họ lạ → `TRAINING_BASE_MODEL_MISMATCH` trước khi đọc dữ liệu (`data_dir` không tồn tại)."""
    instance = trainer.SegformerTrainer(config=_CONFIG, models_dir=tmp_path)
    missing = tmp_path / "khong-co"
    for spec in (
        train_spec(base_model="yolov8n"),
        train_spec(family="openingAndFurnitureDetection", base_model="yolov8n"),
    ):
        with pytest.raises(PermanentError) as caught:
            instance.train(spec, missing, tmp_path, RecordingReporter())
        assert caught.value.code == errors.TRAINING_BASE_MODEL_MISMATCH
    assert not missing.exists()


def test_train_dataset_errors(tmp_path: Path) -> None:
    """Split rỗng → `DATASET_SPLIT_EMPTY` (không bước nào); mẫu hỏng → `DATASET_SAMPLE_INVALID`."""
    instance = trainer.SegformerTrainer(config=_CONFIG, models_dir=tmp_path)
    empty = tmp_path / "empty"
    write_split(empty, "train", 1, seed=0)
    with pytest.raises(PermanentError) as caught:
        instance.train(train_spec(), empty, tmp_path, RecordingReporter())
    assert caught.value.code == errors.DATASET_SPLIT_EMPTY

    only_validation = tmp_path / "only-validation"
    write_split(only_validation, "validation", 1, seed=0)
    with pytest.raises(PermanentError) as caught:
        instance.train(train_spec(), only_validation, tmp_path, RecordingReporter())
    assert caught.value.code == errors.DATASET_SPLIT_EMPTY
    assert SegformerTrainConfig().num_workers == 0

    sample = write_split(tmp_path / "bad", "train", 1, seed=0)[0]
    (sample / "walls.png").write_bytes(encode_mask(torch.zeros(4, 4, dtype=torch.bool).numpy()))
    with pytest.raises(PermanentError) as caught:
        read_sample(sample)
    assert caught.value.code == errors.DATASET_SAMPLE_INVALID

    truncated = write_split(tmp_path / "cut", "train", 1, seed=0)[0]
    (truncated / "image.png").write_bytes((truncated / "image.png").read_bytes()[:64])
    with pytest.raises(PermanentError) as caught:
        read_sample(truncated)
    assert caught.value.code == errors.DATASET_SAMPLE_INVALID

    big = write_split(tmp_path / "big", "train", 1, seed=0)[0]
    with pytest.raises(PermanentError) as caught:
        read_sample(big, max_pixels=16)
    assert caught.value.code == errors.DATASET_SAMPLE_INVALID


def test_trainer_discovered() -> None:
    """`discover_trainers()` trả đúng `TRAINER`; nhập `trainer` không kéo `torch`/`onnxruntime` vào."""
    assert discover_trainers()["wallSegmentation"] is trainer.TRAINER
    assert trainer.TRAINER.family == "wallSegmentation"
    probe = (
        "import sys; import apps.ml.training_segformer.trainer; "
        "assert not {'torch', 'onnxruntime'} & set(sys.modules), sorted(set(sys.modules))[:5]"
    )
    completed = subprocess.run(  # noqa: S603 — argv cố định, không dữ liệu ngoài
        [sys.executable, "-c", probe], capture_output=True, text=True, check=False
    )
    assert completed.returncode == 0, completed.stderr


def test_settings_models_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`models_dir=None` → `ML_MODELS_DIR` đọc lúc `train`, không lúc nhập module (cache do fixture autouse dọn)."""
    monkeypatch.setenv("ML_MODELS_DIR", str(tmp_path))
    assert trainer._settings_models_dir() == tmp_path


def test_loader__generator_seed_differs_per_epoch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Mỗi epoch một seed xáo riêng (`seed + epoch`), cùng `seed` + `epoch` thì tái lập được (M06, NO-318 P3-9)."""
    seeds: list[int] = []
    real = DataLoader

    def _spy(*args: Any, **kwargs: Any) -> object:
        """Ghi seed của `generator` mà vòng đưa vào `DataLoader` thật."""
        generator = kwargs["generator"]
        assert isinstance(generator, torch.Generator)
        seeds.append(generator.initial_seed())
        return real(*args, **kwargs)

    monkeypatch.setattr(loop, "DataLoader", _spy)
    data_dir = tmp_path / "data"
    write_dataset(data_dir)
    _run_loop(data_dir, RecordingReporter(), epochs=2)
    assert len(seeds) == 2
    assert seeds[0] != seeds[1]


def test_trainer__keyword_only_and_family_fixed() -> None:
    """Ctor chỉ nhận keyword và không cho tiêm `family` (khối [2], NO-318 P3-10)."""
    ctor: Any = trainer.SegformerTrainer
    with pytest.raises(TypeError):
        ctor(SegformerTrainConfig())
    with pytest.raises(TypeError):
        ctor(family="openingAndFurnitureDetection")
    assert trainer.SegformerTrainer().family == "wallSegmentation"


def test_train_metrics_log_every_steps(tmp_path: Path) -> None:
    """`log_every_steps=3` với 2 bước/epoch → chỉ một điểm `train` ở bước cuối epoch, không ở bước 1."""
    data_dir = tmp_path / "data"
    write_dataset(data_dir)
    reporter = RecordingReporter()
    _run_loop(data_dir, reporter, config=SegformerTrainConfig(crop_px=_CROP_PX, log_every_steps=3))
    trains = [point for point in reporter.metrics if point.split == "train"]
    assert [point.step for point in trains] == [2]


def test_train_two_epochs_stay_in_train_mode(tmp_path: Path) -> None:
    """`metrics.torch_run_tile` để model ở `eval()` cuối epoch 1 → epoch 2 phải được bật lại `train()`."""
    data_dir = tmp_path / "data"
    write_dataset(data_dir)
    reporter = RecordingReporter()
    net, optimizer = _run_loop(data_dir, reporter, epochs=2)
    assert optimizer.steps == 4, "2 epoch x 2 bước"
    assert net.train_modes == [True] * 4, "mọi bước tối ưu phải chạy ở chế độ train"
    assert [point.epoch for point in reporter.metrics if point.split == "validation"] == [1, 2]
