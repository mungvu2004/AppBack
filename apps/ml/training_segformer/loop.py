"""Vòng huấn luyện SegFormer: epoch, bước tối ưu, số đo, nhịp tim, huỷ (khối [6]).

Nhập `torch` ở mức module — `trainer` chỉ nhập module này **trong** `train()`, nên
`discover_trainers()` vẫn không kéo `torch` vào tiến trình runner (khối [2]).
Không rẽ nhánh theo thiết bị: `autocast`/`GradScaler` luôn được dựng, chỉ `enabled` khác —
nhờ đó đường mã CPU trong test đi đúng các lệnh mà GPU đi (M04).
Mọi quyết định "có báo số đo không" chỉ dựa vào `step`: `step` tăng chặt trong từng split
nên `TrainingMetricsPayload` của B6-03a luôn nhận (M05).
"""

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

import torch
from torch.optim import AdamW
from torch.optim.lr_scheduler import LambdaLR
from torch.utils.data import DataLoader

from apps.ml.training_runner.errors import TrainingStopped
from apps.ml.training_segformer import metrics
from apps.ml.training_segformer.config import Precision, SegformerTrainConfig, effective_batch_size, precision_for
from apps.ml.training_segformer.data import WallSegDataset, sample_dirs
from apps.ml.training_segformer.errors import TRAINING_LOSS_NOT_FINITE
from packages.core.clock import Clock
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.payloads import MetricPoint
from packages.ml_contracts.ports import TrainReporter, TrainSpec

if TYPE_CHECKING:
    from torch import nn

__all__ = ["train_model"]

_METRIC: Final = "iou"


@dataclass
class _Progress:
    """Trạng thái chạy xuyên epoch: bước toàn cục, loss tích từ lần báo `train` trước, nhịp tim cuối."""

    step: int = 0
    loss_sum: float = 0.0
    loss_steps: int = 0
    last_beat: float = 0.0
    last_train_loss: float = 0.0


@dataclass(frozen=True, slots=True)
class _Loop:
    """Một lượt huấn luyện đã gom đủ phụ thuộc, tách khỏi `train_model` để hàm nào cũng ngắn."""

    model: "nn.Module"
    spec: TrainSpec
    config: SegformerTrainConfig
    data_dir: Path
    reporter: TrainReporter
    clock: Clock
    monotonic: Callable[[], float]
    optimizer: AdamW
    scheduler: LambdaLR
    scaler: torch.amp.GradScaler
    precision: Precision
    batch_size: int
    progress: _Progress = field(default_factory=_Progress)

    def run(self) -> None:
        """Chạy đủ `spec.epochs` epoch; mỗi epoch một `WallSegDataset` mới (epoch vào RNG mảnh cắt).

        Đặt `model.train()` ở **đầu mỗi** epoch, không chỉ một lần: đánh giá cuối epoch dùng
        `metrics.torch_run_tile`, hàm đó chuyển chính model sang `eval()` và float32.
        """
        for epoch in range(1, self.spec.epochs + 1):
            # `metrics.torch_run_tile` gọi `eval()` trên chính model này ở cuối mỗi epoch, nên
            # epoch sau phải bật lại chế độ huấn luyện — nếu không, dropout/norm chạy sai từ epoch 2.
            self.model.train()
            self.reporter.heartbeat(epoch)
            self.progress.last_beat = self.monotonic()
            self._run_epoch(epoch, self._loader(epoch))
            self._validate(epoch)

    def _loader(self, epoch: int) -> DataLoader[tuple[object, object]]:
        """`DataLoader` xáo bằng `Generator` seed `seed + epoch` — tái lập được (M06), mỗi epoch một thứ tự lô."""
        split_dir = self.data_dir / "train"
        dataset = WallSegDataset(split_dir, crop_px=self.config.crop_px, seed=self.spec.seed, epoch=epoch)
        return DataLoader(
            dataset,  # type: ignore[arg-type]  # Dataset là protocol cấu trúc, WallSegDataset khớp
            batch_size=self.batch_size,
            shuffle=True,
            generator=torch.Generator().manual_seed(self.spec.seed + epoch),
            num_workers=self.config.num_workers,
        )

    def _run_epoch(self, epoch: int, loader: DataLoader[tuple[object, object]]) -> None:
        """Mọi bước của một epoch; báo `train` mỗi `log_every_steps` bước và ở bước cuối epoch."""
        last_index = len(loader) - 1
        for index, batch in enumerate(loader):
            loss = self._optimizer_step(epoch, batch)
            self.progress.step += 1
            self.progress.loss_sum += loss
            self.progress.loss_steps += 1
            if self.progress.step % self.config.log_every_steps == 0 or index == last_index:
                self._report_train(epoch)
            self._maybe_heartbeat(epoch)

    def _optimizer_step(self, epoch: int, batch: tuple[torch.Tensor, torch.Tensor]) -> float:
        """Một bước tối ưu, hỏi huỷ **trước** khi tiêu tốn gì; loss không hữu hạn → `TRAINING_LOSS_NOT_FINITE`."""
        if self.reporter.cancelled():
            self.reporter.log("info", "training_cancelled", {"epoch": epoch})
            raise TrainingStopped
        pixel_values, labels = (tensor.to(self.spec.device) for tensor in batch)
        self.optimizer.zero_grad(set_to_none=True)
        with torch.autocast(
            self.spec.device,
            dtype=self.precision.autocast_dtype or torch.float32,
            enabled=self.precision.autocast_dtype is not None,
        ):
            loss = self.model(pixel_values=pixel_values, labels=labels).loss
        if not bool(torch.isfinite(loss)):
            raise PermanentError(TRAINING_LOSS_NOT_FINITE)
        self.scaler.scale(loss).backward()
        self.scaler.step(self.optimizer)
        self.scaler.update()
        self.scheduler.step()
        return float(loss.detach())

    def _maybe_heartbeat(self, epoch: int) -> None:
        """Nhịp tim trong epoch theo `monotonic` tiêm được — runner coi job im lặng quá lâu là treo (J07)."""
        now = self.monotonic()
        if now - self.progress.last_beat >= self.config.heartbeat_every_s:
            self.reporter.heartbeat(epoch)
            self.progress.last_beat = now

    def _report_train(self, epoch: int) -> None:
        """Điểm `train`: loss trung bình từ lần báo trước, làm tròn 6 chữ số, rồi đặt lại bộ tích."""
        loss = round(self.progress.loss_sum / self.progress.loss_steps, 6)
        self.progress.last_train_loss = loss
        self.progress.loss_sum = 0.0
        self.progress.loss_steps = 0
        self._metric(epoch, "train", loss=loss)

    def _validate(self, epoch: int) -> None:
        """IoU torch cuối epoch, cùng `step` với bước cuối; `guarded` hỏi huỷ trước mỗi lát (J04)."""
        run_tile = metrics.guarded(metrics.torch_run_tile(self.model, self.spec.device), self.reporter)
        # split kiểm rỗng đã bị `trainer` loại trước khi nạp model; `or 0.0` chỉ chặn `None` cho mypy.
        value = round(metrics.evaluate_iou(run_tile, self.data_dir / "validation") or 0.0, 4)
        self._metric(epoch, "validation", iou=value)
        self.reporter.log(
            "info",
            "training_epoch_finished",
            {"epoch": epoch, "loss": self.progress.last_train_loss, "metric": _METRIC, "value": value},
        )

    def _metric(self, epoch: int, split: Literal["train", "validation"], **values: float) -> None:
        """Gửi một điểm số đo; `recorded_at_ms` từ `clock` tiêm được, không `time.time()`."""
        self.reporter.metric(
            MetricPoint(
                step=self.progress.step,
                epoch=epoch,
                split=split,
                recorded_at_ms=int(self.clock.now().timestamp() * 1000),
                **values,
            )
        )


def train_model(
    model: "nn.Module",
    *,
    spec: TrainSpec,
    config: SegformerTrainConfig,
    data_dir: Path,
    reporter: TrainReporter,
    clock: Clock,
    monotonic: Callable[[], float],
    optimizer_cls: Callable[..., AdamW] = AdamW,
) -> None:
    """Huấn luyện `model` tại chỗ; `optimizer_cls` tiêm được để test đếm bước thật, không mock `torch`.

    `torch.manual_seed(spec.seed)` một lần ở đây: mọi phép ngẫu nhiên của `torch` sau đó tái lập
    (M06). Lịch học giảm tuyến tính về 0 theo **tổng** bước của cả lượt, tính trước từ số mẫu nên
    không phải dựng dataset hai lần. Ném `TrainingStopped` (huỷ) hay `PermanentError` (loss không
    hữu hạn) — `trainer` là nơi dọn `out_dir`. Model được chuyển sang `spec.device` ở đây, không ở
    `trainer`: vòng là nơi duy nhất biết thiết bị nào thật sự chạy bước tối ưu.
    """
    torch.manual_seed(spec.seed)
    model.to(device=spec.device)
    precision = precision_for(spec.device)
    batch_size = effective_batch_size(config, spec.base_model, spec.device)
    steps_per_epoch = math.ceil(len(sample_dirs(data_dir / "train")) / batch_size)
    total_steps = max(spec.epochs * steps_per_epoch, 1)
    optimizer = optimizer_cls(model.parameters(), lr=config.lr, weight_decay=config.weight_decay)
    _Loop(
        model=model,
        spec=spec,
        config=config,
        data_dir=data_dir,
        reporter=reporter,
        clock=clock,
        monotonic=monotonic,
        optimizer=optimizer,
        scheduler=LambdaLR(optimizer, lambda step: max(0.0, 1.0 - step / total_steps)),
        scaler=torch.amp.GradScaler(spec.device, enabled=precision.use_scaler),
        precision=precision,
        batch_size=batch_size,
    ).run()
