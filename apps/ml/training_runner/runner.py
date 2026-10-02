"""Lượt huấn luyện trong tiến trình con: claim → dataset → khoá → tải → trainer → kiểm → `finished`.

Thứ tự là hợp đồng (BE-00 §7, B6-03b [6]): claim trước mọi thứ nặng (không bao giờ nhập
`torch` khi lượt đã mất claim), dataset giải xong **trước** khi xếp hàng chờ khoá (dữ liệu
hỏng không giữ máy), `resolve_device`/`trainers()` chỉ sau khi giữ `training:slot`.

Lý do dừng do `probe()` chốt — gọi cả từ `reporter.cancelled()` (trainer hỏi) và từ luồng
canh (trainer lì không hỏi). Lý do quyết kết quả, không phải cách `train` kết thúc. Claim
mất là trường hợp riêng: lượt khác đã sở hữu job, nên không `put`, không gửi `finished`.
"""

import asyncio
import hashlib
import logging
import os
import shutil
import tempfile
import time
from collections.abc import Callable, Mapping
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import onnx
from google.protobuf.message import DecodeError  # type: ignore[import-untyped]  # protobuf không kèm stub
from redis.exceptions import RedisError

from apps.ml.runtime.device import resolve_device
from apps.ml.runtime.gpu import GpuSlot, gpu_slot
from apps.ml.runtime.loader import ONNX_FIRST_BYTE, has_external_data
from apps.ml.runtime.settings import get_ml_settings
from apps.ml.training_runner.dataset import DatasetPlan, check_disk, download, load_plan
from apps.ml.training_runner.errors import (
    GPU_LOCK_LOST,
    INTERNAL,
    MODEL_FORMAT_UNSUPPORTED,
    TRAINING_CANCELLED,
    TRAINING_CLAIM_LOST,
    TRAINING_GPU_BUSY,
    TRAINING_METRICS_MISSING,
    TRAINING_SLOT_BUSY,
    TRAINING_SLOT_LOST,
    TRAINING_TIMEOUT,
    TRAINING_TRAINER_MISSING,
    TrainingStopped,
)
from apps.ml.training_runner.keys import cancel_key, claim_key, weights_key
from apps.ml.training_runner.redis_sync import renew_if_owner
from apps.ml.training_runner.reporter import Reporter, Send
from apps.ml.training_runner.settings import TrainingRunnerSettings
from apps.ml.training_runner.slot import ClaimLease, TrainingSlot, claim_lease, training_slot
from apps.ml.training_runner.watchdog import StopState, Watchdog
from packages.core.clock import Clock
from packages.core.errors import AppError
from packages.messaging.redis import SyncRedis, sync_result
from packages.messaging.tasks import PermanentError, TransientError
from packages.ml_contracts.families import FAMILY_METRIC, MetricName, TrainableFamily
from packages.ml_contracts.payloads import TrainingFinishedPayload, TrainJobPayload
from packages.ml_contracts.ports import Trainer, TrainResult, TrainSpec
from packages.storage.port import ObjectStorage

_log: Final = logging.getLogger(__name__)

TMP_PREFIX: Final = "training-"
SEED_BYTES: Final = 4
WATCHDOG_MAX_POLL_S: Final = 1.0
_FAIL_REASONS: Final = frozenset({TRAINING_TIMEOUT, TRAINING_SLOT_LOST, GPU_LOCK_LOST})

type Trainers = Callable[[], Mapping[TrainableFamily, Trainer]]
type DiskUsage = Callable[[Path], Any]


@dataclass
class _Guards:
    """Ba thứ có thể mất giữa lượt; `probe()` đọc `lost` của cái nào đã giữ được."""

    claim: ClaimLease | None = None
    slot: TrainingSlot | None = None
    gpu: GpuSlot | None = None


def purge_stale_tmp(max_age_s: float) -> None:
    """Xoá thư mục `training-*` của lượt đã chết; lỗi xoá bỏ qua (đĩa có thể của lượt khác)."""
    cutoff = time.time() - max_age_s
    for path in Path(tempfile.gettempdir()).glob(f"{TMP_PREFIX}*"):
        try:
            stale = path.is_dir() and path.stat().st_mtime < cutoff
        except OSError:  # thư mục vừa bị lượt khác xoá: không phải việc của ta
            continue
        if stale:
            shutil.rmtree(path, ignore_errors=True)


def job_seed(job_id: str) -> int:
    """Seed tái lập được của lượt: 4 byte đầu SHA-256 của `job_id` (M06)."""
    return int.from_bytes(hashlib.sha256(job_id.encode()).digest()[:SEED_BYTES], "big")


def _cancel_requested(client: SyncRedis, job_id: str) -> bool:
    """`cancel_key` có mặt; Redis hỏng → log `WARNING` và coi như **không** huỷ (lượt chạy tiếp)."""
    try:
        return sync_result(client.exists(cancel_key(job_id)), int) > 0
    except (RedisError, AppError) as exc:
        _log.warning("training_cancel_probe_failed", extra={"job_id": job_id, "error": type(exc).__name__})
        return False


def _validated_weights(onnx_path: Path, out_dir: Path, max_bytes: int) -> bytes:
    """Byte ONNX của trainer, đã kiểm đường, cỡ, byte đầu, giải được, không tensor ngoài.

    Trainer không tin (B6-03b [7]): `.pt` pickle bắt đầu `0x80` nên bị byte đầu loại — mã
    này **không bao giờ** `pickle` hay `torch.load` (K12). Lệch nào → `MODEL_FORMAT_UNSUPPORTED`.
    """
    resolved = onnx_path.resolve()
    if not resolved.is_relative_to(out_dir.resolve()) or not resolved.is_file():
        raise PermanentError(MODEL_FORMAT_UNSUPPORTED)
    if resolved.stat().st_size > max_bytes:
        raise PermanentError(MODEL_FORMAT_UNSUPPORTED)
    data = resolved.read_bytes()
    if not data or data[0] != ONNX_FIRST_BYTE:
        raise PermanentError(MODEL_FORMAT_UNSUPPORTED)
    try:
        model = onnx.load_model_from_string(data)
    except DecodeError as exc:
        raise PermanentError(MODEL_FORMAT_UNSUPPORTED) from exc
    if has_external_data(model):
        raise PermanentError(MODEL_FORMAT_UNSUPPORTED)
    return data


def _validated_metrics(metrics: Mapping[MetricName, float], family: TrainableFamily) -> dict[str, float]:
    """Đúng **một** khoá `FAMILY_METRIC[family]`; thiếu, thừa hay sai tên → `TRAINING_METRICS_MISSING`."""
    expected: MetricName = FAMILY_METRIC[family]
    if set(metrics) != {expected}:
        raise PermanentError(TRAINING_METRICS_MISSING)
    return {expected: float(metrics[expected])}


class _Run:
    """Một lượt huấn luyện: giữ trạng thái chung của chín bước để từng bước ngắn và kiểm được."""

    def __init__(
        self,
        payload: TrainJobPayload,
        *,
        claim_token: str,
        trainers: Trainers,
        storage: ObjectStorage,
        send: Send,
        redis: SyncRedis,
        clock: Clock,
        monotonic: Callable[[], float],
        settings: TrainingRunnerSettings,
        exit_process: Callable[[int], None],
        disk_usage: DiskUsage,
    ) -> None:
        """Chốt phụ thuộc tiêm được của lượt; chưa chạm Redis, đĩa hay trainer."""
        self.payload = payload
        self.token = claim_token
        self.trainers = trainers
        self.storage = storage
        self.redis = redis
        self.clock = clock
        self.monotonic = monotonic
        self.settings = settings
        self.exit_process = exit_process
        self.disk_usage = disk_usage
        self.started = clock.now()
        self.stop = StopState()
        self.guards = _Guards()
        self.watchdog: Watchdog | None = None
        self.tmp: Path | None = None
        self._last_poll = -float("inf")
        self.reporter = Reporter(
            job_id=payload.job_id,
            send=send,
            clock=clock,
            monotonic=monotonic,
            cancelled=self._cancelled,
        )

    def probe(self) -> None:
        """Soát năm lý do dừng; lý do đầu thắng, Redis đọc tối đa mỗi `training_cancel_poll_s`."""
        if self.stop.reason is not None:
            return
        now = self.monotonic()
        if now - self._last_poll >= self.settings.training_cancel_poll_s:
            self._last_poll = now
            if _cancel_requested(self.redis, self.payload.job_id):
                self.stop.request(TRAINING_CANCELLED)
                return
        if (self.clock.now() - self.started).total_seconds() > self.settings.training_max_wall_s:
            self.stop.request(TRAINING_TIMEOUT)
            return
        self._probe_locks()

    def _probe_locks(self) -> None:
        """Khoá nào đã giữ mà `lost` bật → lý do dừng của chính khoá đó."""
        lost = (
            (self.guards.slot, TRAINING_SLOT_LOST),
            (self.guards.gpu, GPU_LOCK_LOST),
            (self.guards.claim, TRAINING_CLAIM_LOST),
        )
        for guard, reason in lost:
            if guard is not None and guard.lost.is_set():
                self.stop.request(reason)
                return

    def _cancelled(self) -> bool:
        """`reporter.cancelled()` của trainer: soát rồi trả "có lý do dừng" (BE-00 §9)."""
        self.probe()
        return self.stop.reason is not None

    def _guard_stop(self) -> None:
        """Soát ngay; đã có lý do dừng → `TrainingStopped` để `execute` dựng kết quả theo lý do."""
        if self._cancelled():
            raise TrainingStopped

    def _remaining_s(self) -> float:
        """Giây còn lại của trần giờ lượt (`training_max_wall_s` trừ phần đã chạy)."""
        return self.settings.training_max_wall_s - (self.clock.now() - self.started).total_seconds()

    def _acquire(self, stack: ExitStack, factory: Callable[..., Any], busy_code: str) -> Any:
        """Chờ một khoá theo lượt ≤ `training_cancel_poll_s`, soát huỷ giữa hai lượt, hết giờ → `busy_code`."""
        waited = False
        while True:
            remaining = self._remaining_s()
            if remaining <= 0:
                raise PermanentError(busy_code)
            try:
                return stack.enter_context(factory(wait_s=min(self.settings.training_cancel_poll_s, remaining)))
            except TransientError:
                if not waited:
                    self.reporter.log("info", "training_gpu_waiting", {})
                    waited = True
                self._guard_stop()

    def _prepare(self, stack: ExitStack, runner: asyncio.Runner) -> tuple[Path, Path, DatasetPlan]:
        """Bước 2: huỷ sớm → dừng; thư mục tạm; giải manifest **trước** khi xếp hàng chờ khoá."""
        self._guard_stop()
        tmp = Path(tempfile.mkdtemp(prefix=TMP_PREFIX))
        self.tmp = tmp
        stack.callback(shutil.rmtree, tmp, ignore_errors=True)
        data_dir, out_dir = tmp / "data", tmp / "out"
        data_dir.mkdir()
        out_dir.mkdir()
        plan = runner.run(load_plan(self.storage, self.payload))
        return data_dir, out_dir, plan

    def _hold_locks(self, stack: ExitStack) -> str:
        """Bước 3: giữ `training:slot`, rồi `resolve_device`/`trainers()`; `cuda` giữ thêm `gpu:0`."""
        self.guards.slot = self._acquire(stack, training_slot, TRAINING_SLOT_BUSY)
        device: str = resolve_device(get_ml_settings().ml_device)
        if device == "cuda":
            self.guards.gpu = self._acquire(stack, gpu_slot, TRAINING_GPU_BUSY)
        self._guard_stop()
        return device

    def _train(self, device: str, data_dir: Path, out_dir: Path) -> TrainResult:
        """Bước 5-7: trainer của họ, dưới nhịp tim và luồng canh; trả kết quả thô (chưa tin)."""
        trainer = self.trainers().get(self.payload.family)
        if trainer is None:
            raise PermanentError(TRAINING_TRAINER_MISSING)
        spec = TrainSpec(
            job_id=self.payload.job_id,
            family=self.payload.family,
            base_model=self.payload.base_model,
            epochs=self.payload.epochs,
            device="cuda" if device == "cuda" else "cpu",
            seed=job_seed(self.payload.job_id),
        )
        watchdog = Watchdog(
            self.stop,
            grace_s=self.settings.training_stop_grace_s,
            poll_s=min(self.settings.training_cancel_poll_s, WATCHDOG_MAX_POLL_S),
            probe=self.probe,
            on_expire=self._on_expire,
            monotonic=self.monotonic,
        )
        self.watchdog = watchdog
        watchdog.start()
        try:
            return trainer.train(spec, data_dir, out_dir, self.reporter)
        finally:
            watchdog.train_returned()

    def _publish(self, runner: asyncio.Runner, result: TrainResult, out_dir: Path) -> int:
        """Bước 8: kiểm ONNX và số đo, gia hạn claim, `put` trọng số, `finished(succeeded)`."""
        data = _validated_weights(result.onnx_path, out_dir, self.settings.training_weights_max_bytes)
        metrics = _validated_metrics(result.metrics, self.payload.family)
        if not renew_if_owner(
            self.redis, claim_key(self.payload.job_id), self.token, self.settings.training_claim_ttl_ms
        ):
            return self._claim_lost()
        key = weights_key(self.payload.job_id, self.token)
        runner.run(
            self.storage.put(
                key,
                data,
                content_type="application/octet-stream",
                max_bytes=self.settings.training_weights_max_bytes,
            )
        )
        return self._send_finished(
            TrainingFinishedPayload(
                job_id=self.payload.job_id,
                status="succeeded",
                weights_key=key,
                checksum_sha256=hashlib.sha256(data).hexdigest(),
                metrics=metrics,
            )
        )

    def _claim_lost(self) -> int:
        """Lượt khác sở hữu job: chỉ log máy chủ, không `put`, không `finished` (BE-00 §7)."""
        _log.warning("training_claim_lost", extra={"job_id": self.payload.job_id})
        return 1

    def _send_finished(self, payload: TrainingFinishedPayload) -> int:
        """Gửi `finished` một lần duy nhất; luồng canh đã nổ → nó đã gửi, ta chỉ trả 1."""
        if self._expired():
            return 1
        return 0 if self.reporter.finish(payload) else 1

    def _expired(self) -> bool:
        """Luồng canh đã nổ: nó đã log và gửi `finished`, lượt chính không được gửi lần nữa."""
        return self.watchdog is not None and self.watchdog.expired

    def _stopped(self, reason: str) -> int:
        """Kết quả theo lý do dừng: huỷ → `cancelled`, quá giờ/mất khoá → `failed`, mất claim → im."""
        if self._expired():
            return 1
        if reason == TRAINING_CLAIM_LOST:
            return self._claim_lost()
        if reason == TRAINING_CANCELLED:
            self.reporter.log("info", "training_cancelled", {"epoch": self.reporter.last_epoch})
            return self._send_finished(TrainingFinishedPayload(job_id=self.payload.job_id, status="cancelled"))
        return self._failed(reason if reason in _FAIL_REASONS else INTERNAL)

    def _failed(self, code: str) -> int:
        """`finished(failed, code)` kèm dòng log job `training_failed {code}` (mã, không văn bản lỗi)."""
        if self._expired():
            return 1
        self.reporter.log("error", "training_failed", {"code": code})
        return self._send_finished(
            TrainingFinishedPayload(job_id=self.payload.job_id, status="failed", error_code=code)
        )

    def _on_expire(self, reason: str) -> None:
        """Luồng canh nổ: dọn thư mục tạm, gửi `finished` theo lý do rồi `exit(1)` (tiêm được)."""
        if self.tmp is not None:
            shutil.rmtree(self.tmp, ignore_errors=True)
        if reason == TRAINING_CLAIM_LOST:
            self._claim_lost()
        elif reason == TRAINING_CANCELLED:
            self.reporter.log("info", "training_cancelled", {"epoch": self.reporter.last_epoch})
            self.reporter.finish(TrainingFinishedPayload(job_id=self.payload.job_id, status="cancelled"))
        else:
            code = reason if reason in _FAIL_REASONS else INTERNAL
            self.reporter.log("error", "training_failed", {"code": code})
            self.reporter.finish(TrainingFinishedPayload(job_id=self.payload.job_id, status="failed", error_code=code))
        self.exit_process(1)

    def _pipeline(self, stack: ExitStack, runner: asyncio.Runner) -> int:
        """Bước 2-8 của lượt; mọi lối dừng thoát bằng `TrainingStopped` hay `PermanentError`."""
        data_dir, out_dir, plan = self._prepare(stack, runner)
        device = self._hold_locks(stack)
        self.reporter.heartbeat(0)
        stack.callback(self.reporter.start_heartbeats(self.settings.training_heartbeat_s))
        check_disk(data_dir.parent, plan.total_bytes, disk_usage=self.disk_usage)
        runner.run(download(self.storage, self.payload, plan, data_dir))
        try:
            result = self._train(device, data_dir, out_dir)
        except OSError:
            # Luồng canh đã nổ: nó xoá thư mục tạm rồi `exit(1)`. Trong test `exit` được tiêm nên
            # trainer vẫn chạy tiếp và vỡ khi ghi file — lượt đã báo xong, chỉ trả mã thoát.
            if self.watchdog is not None and self.watchdog.expired:
                return 1
            raise
        if self.stop.reason is not None:
            return self._stopped(self.stop.reason)
        return self._publish(runner, result, out_dir)

    def _stop_watchdog(self) -> None:
        """Dừng luồng canh khi thoát khối (sau khi `train` đã trả hay đã ném)."""
        if self.watchdog is not None:
            self.watchdog.stop()

    def execute(self) -> int:
        """Chín bước của lượt; `finally` của `ExitStack` dọn luồng, khoá, claim và thư mục tạm."""
        with ExitStack() as stack:
            runner = stack.enter_context(asyncio.Runner())
            self.guards.claim = stack.enter_context(
                claim_lease(self.redis, self.payload.job_id, self.token, ttl_ms=self.settings.training_claim_ttl_ms)
            )
            stack.callback(self._stop_watchdog)
            purge_stale_tmp(self.settings.training_max_wall_s)
            try:
                return self._pipeline(stack, runner)
            except TrainingStopped:
                return self._stopped(self.stop.reason or INTERNAL)
            except PermanentError as exc:
                reason = self.stop.reason
                if reason is not None:
                    return self._stopped(reason)
                # Trainer báo huỷ mà lượt chưa có lý do dừng là lỗi của trainer: `TRAINING_CANCELLED`
                # không bao giờ được lên dây dưới dạng `failed` ([2]), nên gửi `INTERNAL`.
                return self._failed(INTERNAL if exc.code == TRAINING_CANCELLED else exc.code)


def run_training_job(
    payload: TrainJobPayload,
    *,
    claim_token: str,
    trainers: Trainers,
    storage: ObjectStorage,
    send: Send,
    redis: SyncRedis,
    clock: Clock,
    monotonic: Callable[[], float] = time.monotonic,
    settings: TrainingRunnerSettings,
    exit: Callable[[int], None] = os._exit,
    disk_usage: DiskUsage = shutil.disk_usage,
) -> int:
    """Chạy một lượt huấn luyện; trả 0 khi `finished` đã gửi, 1 khi không gửi được hay claim mất.

    Dùng **một** `asyncio.Runner` cho cả lượt (kho object là async, trainer là đồng bộ).
    Không ném lỗi nghiệp vụ: mọi mã thành `finished(failed, <mã>)`; lỗi lạ do `main()` bắt.
    """
    return _Run(
        payload,
        claim_token=claim_token,
        trainers=trainers,
        storage=storage,
        send=send,
        redis=redis,
        clock=clock,
        monotonic=monotonic,
        settings=settings,
        exit_process=exit,
        disk_usage=disk_usage,
    ).execute()
