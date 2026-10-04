"""`Trainer` họ `openingAndFurnitureDetection` mà runner B6-03b tìm qua `discover_trainers()` (khối [2]).

Bất biến nhập: mức module chỉ `settings`, `packages.*`, `training_segformer.errors` (module thuần
hằng chuỗi) và thư viện chuẩn — `discover_trainers()` nhập **mọi** `apps.ml.*.trainer`, nên một
`import torch`/`onnxruntime` ở đây nạp vài trăm MB vào tiến trình API lẫn worker. `ultralytics`,
`torch`, `onnx`, `dataset` và các module nhập `onnxruntime` nhập trong hàm.
Thứ tự `train()` là hợp đồng: kiểm họ rồi so SHA `.pt` ghim **trước** khi nhập `ultralytics`
(K12 — tệp lạ không bao giờ tới bộ giải pickle). Mọi lối ra không thành công để `out_dir` rỗng:
runner đẩy nguyên thư mục lên storage, một `.pt` sót lại là trọng số không ghim lên kho.
"""

import math
import os
import shutil
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

from apps.ml.training_segformer import errors
from apps.ml.training_yolo.settings import YoloTrainSettings
from packages.core.clock import Clock, SystemClock
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.families import BASE_MODELS, TrainableFamily
from packages.ml_contracts.payloads import MetricPoint
from packages.ml_contracts.pinned import PINNED, PinnedWeights
from packages.ml_contracts.ports import TrainReporter, TrainResult, TrainSpec

__all__ = ["TRAINER", "YoloTrainer", "prepare_ultralytics"]

_FAMILY: Final[TrainableFamily] = "openingAndFurnitureDetection"
_OFFLINE_ENV: Final = {"YOLO_OFFLINE": "1", "YOLO_AUTOINSTALL": "false"}
"""Cùng giá trị `apps.ml.runtime.export_yolo._OFFLINE_ENV` (riêng tư ở đó, BE-00 §9)."""
_MAP50_KEY: Final = "metrics/mAP50(B)"
_RUN_NAME: Final = "run"
_prepared = False
"""Một lần mỗi tiến trình: cờ ngoại tuyến chỉ có tác dụng trước lần nhập `ultralytics` đầu tiên."""


def _always_amp(_model: Any) -> bool:
    """Bản thay `check_amp`: bản gốc tải một `.pt` không ghim để so AMP (M03, K12)."""
    return True


def prepare_ultralytics() -> Path:
    """Đặt `ultralytics` vào chế độ ngoại tuyến cho cả tiến trình; trả `YOLO_CONFIG_DIR`.

    Gọi được nhiều lần, chỉ làm việc lần đầu. Thư mục cấu hình tạo 0700 **trước** khi nhập
    (thư mục chưa có → ultralytics lùi về `/tmp/Ultralytics` dùng chung). Sau khi nhập: tắt
    đồng bộ, đặt sẵn `Arial.ttf` rỗng (`check_font` thiếu tệp thì tải thật dù `YOLO_OFFLINE=1`)
    và thay `check_amp` ở **cả hai** module — vá mỗi `utils.checks` thì `BaseTrainer` vẫn tải
    `.pt` không ghim (M03).
    """
    global _prepared
    config_dir = Path(tempfile.gettempdir()) / f"yolo-config-{os.getpid()}"
    if _prepared:
        return config_dir
    (config_dir / "Ultralytics").mkdir(mode=0o700, parents=True, exist_ok=True)
    config_dir.chmod(0o700)
    os.environ.update(_OFFLINE_ENV)
    os.environ["YOLO_CONFIG_DIR"] = str(config_dir)
    from apps.ml.runtime.ultralytics_import import import_ultralytics

    import_ultralytics()
    from ultralytics import settings as yolo_settings
    from ultralytics.engine import trainer as yolo_trainer
    from ultralytics.utils import checks

    yolo_settings.update({"sync": False})
    (config_dir / "Ultralytics" / "Arial.ttf").touch()
    checks.check_amp = _always_amp
    yolo_trainer.check_amp = _always_amp  # type: ignore[attr-defined]  # tên đã nhập sẵn vào module
    _prepared = True
    return config_dir


def _clear(out_dir: Path) -> None:
    """Trả `out_dir` về rỗng (vẫn tồn tại) sau một lượt hỏng: runner đẩy nguyên thư mục lên storage."""
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)


def _loss_total(tloss: Any) -> float | None:
    """Tổng các thành phần loss của epoch; `None` khi `tloss` chưa có hay không đọc được thành số."""
    if tloss is None:
        return None
    values = tloss.values() if isinstance(tloss, Mapping) else tloss
    try:
        return float(sum(float(value) for value in values))
    except TypeError:
        return float(tloss)


def _map50_of(metrics: Any) -> float | None:
    """`metrics/mAP50(B)` của epoch vừa validate; `None` khi lượt không có pha validate."""
    if not isinstance(metrics, Mapping) or _MAP50_KEY not in metrics:
        return None
    return float(metrics[_MAP50_KEY])


def _in_domain(value: float | None, high: float | None) -> bool:
    """Số hữu hạn, `≥ 0` và (khi có `high`) `≤ high` — miền của `MetricPoint` cho `loss` và `map50`."""
    return value is not None and math.isfinite(value) and value >= 0 and (high is None or value <= high)


@dataclass
class _RunCallbacks:
    """Trạng thái callback của một lượt `Model.train`: huỷ, nhịp tim, điểm số đo.

    Tách khỏi `YoloTrainer` (frozen) vì bộ đếm batch và mốc nhịp tim đổi trong lượt. `step` của
    `MetricPoint` phải tăng ngặt trong từng split → dùng chung bộ đếm batch tích luỹ.
    """

    reporter: TrainReporter
    clock: Clock
    monotonic: Callable[[], float]
    heartbeat_every_s: float
    last_beat: float
    epochs: int = 0
    """Số epoch của `spec`: ultralytics gọi `on_fit_epoch_end` thêm một lần cho lượt validate cuối."""
    batches: int = 0
    epochs_done: int = 0
    last_map50: float | None = None

    def install(self, model: Any) -> None:
        """Gắn ba callback vào model; `add_callback` giữ nguyên callback mặc định của ultralytics."""
        model.add_callback("on_train_batch_end", self.on_train_batch_end)
        model.add_callback("on_val_batch_end", self.on_val_batch_end)
        model.add_callback("on_fit_epoch_end", self.on_fit_epoch_end)

    def on_train_batch_end(self, _trainer: Any) -> None:
        """Đếm batch rồi kiểm huỷ và nhịp tim."""
        self.batches += 1
        self._tick()

    def on_val_batch_end(self, _validator: Any) -> None:
        """Huỷ và nhịp tim cũng phải chạy trong pha validate: pha đó không có batch train nào."""
        self._tick()

    def _tick(self) -> None:
        """`TrainingStopped` khi `cancelled()`; nhịp tim khi đã qua `heartbeat_every_s` theo `monotonic` tiêm."""
        from apps.ml.training_runner.errors import TrainingStopped

        if self.reporter.cancelled():
            raise TrainingStopped
        now = self.monotonic()
        if now - self.last_beat >= self.heartbeat_every_s:
            self.last_beat = now
            self.reporter.heartbeat(self.epochs_done + 1)

    def on_fit_epoch_end(self, trainer: Any) -> None:
        """Một điểm `train` (loss) và một điểm `validation` (`map50`) cho mỗi epoch đã xong.

        Số ngoài miền `MetricPoint` hay không hữu hạn thì bỏ điểm đó và log `training_metric_skipped`
        đúng tên số đo bị bỏ: gửi lên sẽ làm cầu nối B6-03a từ chối cả lô. `last_map50` chỉ theo
        `map50` (loss hỏng không xoá điểm validation đã gửi); log `training_epoch_finished` cần cả hai.
        """
        self.epochs_done += 1
        epoch = self.epochs_done
        if epoch > self.epochs:
            return
        loss = _loss_total(getattr(trainer, "tloss", None))
        map50 = _map50_of(getattr(trainer, "metrics", None))
        self._emit(epoch, "loss", loss, high=None)
        self._emit(epoch, "map50", map50, high=1.0)
        if _in_domain(map50, 1.0):
            self.last_map50 = map50
            if _in_domain(loss, None):
                self.reporter.log(
                    "info",
                    "training_epoch_finished",
                    {"epoch": epoch, "loss": float(loss or 0.0), "metric": "map50", "value": float(map50 or 0.0)},
                )
        self.reporter.heartbeat(epoch)

    def _emit(self, epoch: int, name: Literal["loss", "map50"], value: float | None, *, high: float | None) -> None:
        """Gửi điểm `name` (`loss` → split train, `map50` → validation), hay log bỏ điểm khi số không dùng được."""
        if not _in_domain(value, high):
            self.reporter.log("warning", "training_metric_skipped", {"epoch": epoch, "metric": name})
            return
        train = name == "loss"
        self.reporter.metric(
            MetricPoint(
                step=self.batches,
                epoch=epoch,
                split="train" if train else "validation",
                recorded_at_ms=int(self.clock.now().timestamp() * 1000),
                loss=value if train else None,
                map50=None if train else value,
            )
        )


def _settings_models_dir() -> Path:
    """`ML_MODELS_DIR` đọc **lúc `train`**, không lúc nhập module: biến môi trường của worker mới tính.

    Nhập lười vì `apps.ml.runtime.settings` nằm trong gói nhập `onnxruntime`.
    """
    from apps.ml.runtime.settings import get_ml_settings

    return Path(get_ml_settings().ml_models_dir)


def _best_weights(out_dir: Path) -> Path:
    """`best.pt` của lượt, lùi `last.pt` (ultralytics chỉ ghi `best.pt` khi fitness có cải thiện).

    Thiếu cả hai → `MODEL_FORMAT_UNSUPPORTED`: lượt xong mà không có trọng số là artifact hỏng.
    """
    from apps.ml.runtime.errors import MODEL_FORMAT_UNSUPPORTED

    weights = out_dir / "ultralytics" / _RUN_NAME / "weights"
    for name in ("best.pt", "last.pt"):
        candidate = weights / name
        if candidate.is_file():
            return candidate
    raise PermanentError(MODEL_FORMAT_UNSUPPORTED)


def _check_export(onnx_path: Path) -> None:
    """ONNX vừa sinh phải tự chứa, hợp lệ và dựng được `YoloOnnxDetector` — nếu không, đừng đẩy lên kho.

    Bắt đúng lớp lỗi (`ValidationError` của `onnx`, `ORT_ERRORS`), không `except Exception` (R-16);
    `YoloOnnxDetector` tự ném `PermanentError(MODEL_FORMAT_UNSUPPORTED)` khi hình dạng sai.
    """
    import onnx
    import onnxruntime as ort  # type: ignore[import-untyped]  # onnxruntime 1.30 không có py.typed
    from google.protobuf.message import DecodeError  # type: ignore[import-untyped]  # protobuf không có stub

    from apps.ml.objects.detector import YoloOnnxDetector
    from apps.ml.objects.labels import ARTIFACT_LABELS
    from apps.ml.runtime.errors import MODEL_FORMAT_UNSUPPORTED, ORT_ERRORS

    data = onnx_path.read_bytes()
    try:
        model = onnx.load_from_string(data)
        onnx.checker.check_model(model)
    except (onnx.checker.ValidationError, DecodeError) as exc:
        raise PermanentError(MODEL_FORMAT_UNSUPPORTED) from exc
    if any(tensor.data_location == onnx.TensorProto.EXTERNAL for tensor in model.graph.initializer):
        raise PermanentError(MODEL_FORMAT_UNSUPPORTED)
    try:
        session = ort.InferenceSession(data, providers=["CPUExecutionProvider"])
    except ORT_ERRORS as exc:
        raise PermanentError(MODEL_FORMAT_UNSUPPORTED) from exc
    YoloOnnxDetector(session, ARTIFACT_LABELS)


@dataclass(frozen=True, slots=True)
class YoloTrainer:
    """Huấn luyện YOLO dò cửa/đồ đạc; đồng hồ, thư mục trọng số và bản ghim đều tiêm được.

    `models_dir=None` → đọc cài đặt lúc `train` (test luôn tiêm: cache cài đặt rò dưới xdist).
    `pinned` tiêm được để test dùng SHA của `.pt` tí hon dựng tại chỗ, không tải mạng.
    """

    settings: YoloTrainSettings = field(default_factory=YoloTrainSettings)
    pinned: Mapping[str, PinnedWeights] = PINNED
    models_dir: Path | None = None
    clock: Clock = field(default_factory=SystemClock)
    monotonic: Callable[[], float] = time.monotonic
    family: TrainableFamily = _FAMILY

    def train(self, spec: TrainSpec, data_dir: Path, out_dir: Path, reporter: TrainReporter) -> TrainResult:
        """Huấn luyện rồi xuất `out_dir/model.onnx`; trả đúng số đo `map50` của epoch cuối.

        `TRAINING_BASE_MODEL_MISMATCH` khi họ hay model gốc không phải của trainer này;
        `MODEL_CHECKSUM_MISMATCH` khi `.pt` ghim thiếu hay lệch SHA (cả hai **trước** khi nhập
        `ultralytics`); `DATASET_SPLIT_EMPTY`/`DATASET_SAMPLE_INVALID` từ `build_yolo_dataset`;
        `TRAINING_METRICS_MISSING` khi không epoch nào cho `map50`; `MODEL_FORMAT_UNSUPPORTED`
        khi ONNX vừa xuất không dựng được bộ chạy. Huỷ là `TrainingStopped`. Lối ra không thành
        công nào cũng để `out_dir` rỗng; lượt đạt để lại đúng `model.onnx`.
        """
        if spec.family != self.family or spec.base_model not in BASE_MODELS[self.family]:
            raise PermanentError(errors.TRAINING_BASE_MODEL_MISMATCH)
        pt = self._pinned_pt(spec.base_model)
        prepare_ultralytics()
        work_dir = Path(tempfile.mkdtemp(prefix="yolo-", dir=out_dir.parent))
        succeeded = False
        try:
            map50 = self._run(spec, data_dir, work_dir, out_dir, reporter, pt)
            succeeded = True
        finally:
            shutil.rmtree(out_dir / "ultralytics", ignore_errors=True)
            shutil.rmtree(work_dir, ignore_errors=True)
            if not succeeded:
                _clear(out_dir)
        return TrainResult(onnx_path=out_dir / "model.onnx", metrics={"map50": map50})

    def _pinned_pt(self, base_model: str) -> Path:
        """Đường `.pt` ghim đã so SHA-256 theo khúc; thiếu hay lệch → `MODEL_CHECKSUM_MISMATCH` (K12, M03)."""
        from apps.ml.runtime.errors import MODEL_CHECKSUM_MISMATCH
        from packages.ml_contracts.pinned import file_sha256

        weights = self.pinned[base_model]
        models_dir = self.models_dir if self.models_dir is not None else _settings_models_dir()
        pt = models_dir / base_model / weights.files[0].filename
        if not pt.is_file() or file_sha256(pt) != weights.source_sha256:
            raise PermanentError(MODEL_CHECKSUM_MISMATCH)
        return pt

    def _run(
        self,
        spec: TrainSpec,
        data_dir: Path,
        work_dir: Path,
        out_dir: Path,
        reporter: TrainReporter,
        pt: Path,
    ) -> float:
        """Dataset → `Model.train` → xuất ONNX đã kiểm; trả `map50` của epoch cuối."""
        from apps.ml.training_runner.errors import TRAINING_METRICS_MISSING
        from apps.ml.training_yolo import dataset as yolo_dataset

        built = yolo_dataset.build_yolo_dataset(
            data_dir,
            work_dir,
            tile_px=self.settings.imgsz,
            keep_every=self.settings.background_keep_every,
            cancelled=reporter.cancelled,
        )
        reporter.log(
            "info",
            "training_dataset_ready",
            {
                "train_tiles": built.train_tiles,
                "validation_tiles": built.validation_tiles,
                "skipped_boxes": built.skipped_boxes,
            },
        )
        callbacks = self._fit(spec, built, pt, out_dir, reporter)
        if callbacks.last_map50 is None:
            raise PermanentError(TRAINING_METRICS_MISSING)
        self._export(spec, out_dir, reporter)
        return callbacks.last_map50

    def _fit(
        self,
        spec: TrainSpec,
        built: Any,
        pt: Path,
        out_dir: Path,
        reporter: TrainReporter,
    ) -> _RunCallbacks:
        """Chạy `Model.train` với đúng bộ tham số khối [6]; trả bộ callback đã thu số đo."""
        from ultralytics import YOLO  # type: ignore[attr-defined]  # ultralytics không khai __all__ cho YOLO

        cuda = spec.device == "cuda"
        batch = int(self.settings.batch_cuda[spec.base_model] if cuda else self.settings.batch_cpu)
        reporter.log(
            "info",
            "training_started",
            {
                "base_model": spec.base_model,
                "device": spec.device,
                "train": built.train_tiles,
                "validation": built.validation_tiles,
                "batch_size": batch,
            },
        )
        callbacks = _RunCallbacks(
            reporter=reporter,
            clock=self.clock,
            monotonic=self.monotonic,
            heartbeat_every_s=self.settings.heartbeat_every_s,
            last_beat=self.monotonic(),
            epochs=spec.epochs,
        )
        model = YOLO(str(pt))
        callbacks.install(model)
        model.train(
            data=str(built.yaml_path),
            epochs=spec.epochs,
            imgsz=self.settings.imgsz,
            batch=batch,
            workers=self.settings.workers,
            device=0 if cuda else "cpu",
            amp=cuda,
            seed=spec.seed,
            deterministic=True,
            plots=False,
            project=str(out_dir / "ultralytics"),
            name=_RUN_NAME,
            exist_ok=True,
            val=True,
            cache=False,
            verbose=False,
        )
        return callbacks

    def _export(self, spec: TrainSpec, out_dir: Path, reporter: TrainReporter) -> None:
        """`best.pt` (lùi `last.pt`) → `out_dir/model.onnx` đã kiểm; nhịp tim ngay trước và sau khi xuất."""
        from apps.ml.runtime.export_yolo import export_yolo
        from packages.ml_contracts.pinned import file_sha256

        best = _best_weights(out_dir)
        onnx_path = out_dir / "model.onnx"
        reporter.heartbeat(spec.epochs)
        export_yolo(
            best,
            onnx_path,
            source_sha256=file_sha256(best),
            imgsz=self.settings.imgsz,
            opset=17,
            device="cpu",
        )
        reporter.heartbeat(spec.epochs)
        _check_export(onnx_path)
        reporter.log("info", "training_exported", {"size_mib": round(onnx_path.stat().st_size / (1024 * 1024), 3)})


TRAINER: Final = YoloTrainer()
"""Thực thể `discover_trainers()` lấy; cài đặt mặc định, đồng hồ hệ thống."""
