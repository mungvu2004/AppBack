"""`Trainer` họ `wallSegmentation` mà runner B6-03b tìm thấy qua `discover_trainers()` (khối [2]).

Bất biến nhập: module này chỉ nhập `config`, `errors`, `packages.*` và thư viện chuẩn ở mức
module — `discover_trainers()` nhập **mọi** `apps.ml.*.trainer` để dựng bảng họ, nên một
`import torch` ở đây sẽ nạp torch/onnxruntime vào tiến trình API lẫn worker. `torch` và các
module nặng (`data`, `loop`, `model`, `export`) nhập trong `train()`.
Thứ tự `train()` là hợp đồng: kiểm rẻ (họ, model gốc, split rỗng) trước mọi việc nặng, rồi
nạp trọng số ghim, huấn luyện, xuất. Mọi lối ra không thành công để `out_dir` sạch — runner
đẩy nguyên thư mục lên storage, một tệp tạm sót lại là một artifact rác.
"""

import shutil
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from apps.ml.training_segformer import errors
from apps.ml.training_segformer.config import SegformerTrainConfig, effective_batch_size
from packages.core.clock import Clock, SystemClock
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.families import BASE_MODELS, TrainableFamily
from packages.ml_contracts.pinned import PINNED, PinnedWeights
from packages.ml_contracts.ports import TrainReporter, TrainResult, TrainSpec

__all__ = ["TRAINER", "SegformerTrainer"]

_FAMILY: Final[TrainableFamily] = "wallSegmentation"


def _settings_models_dir() -> Path:
    """`ML_MODELS_DIR` đọc **lúc `train`**, không lúc nhập module: biến môi trường của worker mới tính.

    Nhập lười vì `apps.ml.runtime.settings` nằm trong gói nhập `onnxruntime`.
    """
    from apps.ml.runtime.settings import get_ml_settings

    return Path(get_ml_settings().ml_models_dir)


def _clear(out_dir: Path) -> None:
    """Trả `out_dir` về rỗng (vẫn tồn tại) sau một lượt hỏng: runner đẩy nguyên thư mục lên storage."""
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True, slots=True)
class SegformerTrainer:
    """Huấn luyện SegFormer tách tường; mọi phụ thuộc ngoài (đồng hồ, đường trọng số) tiêm được.

    `models_dir=None` → đọc cài đặt lúc `train` (test luôn tiêm để không chạm cache cài đặt
    dùng chung). `pinned` tiêm được để test dùng SHA của model tí hon, không tải mạng.
    """

    config: SegformerTrainConfig = field(default_factory=SegformerTrainConfig)
    models_dir: Path | None = None
    pinned: Mapping[str, PinnedWeights] = PINNED
    clock: Clock = field(default_factory=SystemClock)
    monotonic: Callable[[], float] = time.monotonic
    family: TrainableFamily = _FAMILY

    def train(self, spec: TrainSpec, data_dir: Path, out_dir: Path, reporter: TrainReporter) -> TrainResult:
        """Huấn luyện rồi xuất `out_dir/model.onnx`; trả đúng một số đo `iou` đo bằng ONNX đã xuất.

        `TRAINING_BASE_MODEL_MISMATCH` nếu họ hay model gốc không phải của trainer này (trước mọi
        lần đọc tệp); `DATASET_SPLIT_EMPTY` nếu `train/` hay `validation/` không có mẫu (`test/`
        không được đọc). Lỗi nạp trọng số, loss không hữu hạn, lệch tương đương là `PermanentError`;
        huỷ là `TrainingStopped`. Lối ra nào không thành công cũng dọn `out_dir`.
        """
        if spec.family != self.family or spec.base_model not in BASE_MODELS[self.family]:
            raise PermanentError(errors.TRAINING_BASE_MODEL_MISMATCH)
        from apps.ml.training_segformer import data

        counts = {split: len(data.sample_dirs(data_dir / split)) for split in ("train", "validation")}
        if not all(counts.values()):
            raise PermanentError(errors.DATASET_SPLIT_EMPTY)
        from apps.ml.training_segformer import export, loop
        from apps.ml.training_segformer import model as segformer_model

        models_dir = self.models_dir or _settings_models_dir()
        succeeded = False
        try:
            net = segformer_model.load_pretrained(models_dir, spec.base_model, self.pinned)
            self._log_started(spec, reporter, counts)
            loop.train_model(
                net,
                spec=spec,
                config=self.config,
                data_dir=data_dir,
                reporter=reporter,
                clock=self.clock,
                monotonic=self.monotonic,
            )
            iou = export.export_and_check(
                net,
                out_dir,
                data_dir / "validation",
                config=self.config,
                reporter=reporter,
            )
            succeeded = True
        finally:
            if not succeeded:
                _clear(out_dir)
        return TrainResult(onnx_path=out_dir / "model.onnx", metrics={"iou": iou})

    def _log_started(self, spec: TrainSpec, reporter: TrainReporter, counts: Mapping[str, int]) -> None:
        """`training_started` sau khi trọng số nạp được: trước đó lượt chạy còn có thể chết vì model."""
        reporter.log(
            "info",
            "training_started",
            {
                "base_model": spec.base_model,
                "device": spec.device,
                "train": counts["train"],
                "validation": counts["validation"],
                "batch_size": effective_batch_size(self.config, spec.base_model, spec.device),
            },
        )


TRAINER: Final = SegformerTrainer()
"""Thực thể `discover_trainers()` lấy; cài đặt mặc định, đồng hồ hệ thống."""
