"""`Reporter`: kênh một job dùng để báo nhịp tim, số đo, log, kết thúc tới cầu nối B6-03a.

Thoả `TrainReporter` (B5-01, `packages/ml_contracts/ports.py`) nên trainer tí hon lẫn trainer
thật dùng được như nhau. Gửi hỏng ở nhịp tim/số đo/log không dừng lượt huấn luyện (BE-00 §9,
§7 "Tiến trình huấn luyện"); chỉ `finish` mới gửi lại có hạn vì cầu nối cần biết job đã xong.
"""

import logging
import threading
import time
from collections.abc import Callable, Mapping
from typing import Final, Literal

from pydantic import BaseModel

from apps.ml.runtime.lease import JOIN_TIMEOUT_S
from apps.ml.training_runner.keys import FINISHED_TASK, HEARTBEAT_TASK, LOG_TASK, METRICS_TASK
from packages.core.clock import Clock
from packages.core.errors import AppError
from packages.ml_contracts.payloads import (
    MAX_METRIC_POINTS,
    MetricPoint,
    TrainingFinishedPayload,
    TrainingHeartbeatPayload,
    TrainingLogPayload,
    TrainingMetricsPayload,
)
from packages.ml_contracts.ports import LogParam

type Send = Callable[[str, BaseModel], None]
"""Chữ ký chung B6-03b: thật = `send_task` của `packages.messaging.celery_app`."""

_log: Final = logging.getLogger(__name__)

_FLUSH_EVERY_POINTS: Final = 100
_FLUSH_EVERY_S: Final = 10.0
_FINISH_RETRIES: Final = 6


def _backoff_s(attempt: int) -> float:
    """Lùi của lần gửi lại `attempt` (0-based): `min(60, 2 * 2**attempt)` giây (2,4,8,16,32,60)."""
    return min(60.0, 2.0 * 2.0**attempt)


class Reporter:
    """Một job huấn luyện, một `Reporter`: gom số đo, đếm dòng log, gửi `finished` có lùi.

    `cancelled` là hàm tiêm (runner quyết lý do dừng thật, [6] bước 6); `Reporter` chỉ chuyển
    tiếp. Không khoá luồng cho `metric`/`log`: trainer gọi tuần tự trên luồng của chính nó,
    chỉ `start_heartbeats` chạy trên luồng riêng và chỉ đụng `last_epoch` (đọc/ghi int, an toàn GIL).
    """

    def __init__(
        self,
        *,
        job_id: str,
        send: Send,
        clock: Clock,
        monotonic: Callable[[], float],
        cancelled: Callable[[], bool],
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Gắn job vào các hàm tiêm: `send` gửi thông điệp, `clock`/`monotonic`/`sleep` cho test giả."""
        self._job_id = job_id
        self._send = send
        self._clock = clock
        self._monotonic = monotonic
        self._cancelled = cancelled
        self._sleep = sleep
        self._points: list[MetricPoint] = []
        self._last_flush = monotonic()
        self._line = 0
        self.last_epoch = 0  # công khai: runner đọc để log `training_cancelled`

    def heartbeat(self, epoch: int) -> None:
        """Gửi nhịp tim của `epoch`; nhớ lại cho luồng nhịp tim nền (`start_heartbeats`)."""
        self.last_epoch = epoch
        self._send_or_log(
            HEARTBEAT_TASK, TrainingHeartbeatPayload(job_id=self._job_id, epoch=epoch, sent_at_ms=self._now_ms())
        )

    def metric(self, point: MetricPoint) -> None:
        """Gom `point` theo thứ tự gọi; xả khi đủ 100 điểm hay đã quá 10 s từ lần xả trước."""
        self._points.append(point)
        if len(self._points) >= _FLUSH_EVERY_POINTS or self._monotonic() - self._last_flush >= _FLUSH_EVERY_S:
            self.flush_metrics()

    def flush_metrics(self) -> None:
        """Gửi hết số đo đang gom theo lô ≤ 500 điểm; bỏ điểm phạm luật bước (không hỏng cả lô)."""
        if not self._points:
            self._last_flush = self._monotonic()
            return
        batches = _batched_valid(self._points)
        self._points = []
        self._last_flush = self._monotonic()
        for batch in batches:
            self._send_or_log(METRICS_TASK, TrainingMetricsPayload(job_id=self._job_id, points=batch))

    def log(self, level: Literal["info", "warning", "error"], template: str, params: Mapping[str, LogParam]) -> None:
        """Gửi một dòng log với `params["line"]` tăng dần từ 1 trong job này."""
        self._line += 1
        full: dict[str, LogParam] = {**params, "line": self._line}
        self._send_or_log(
            LOG_TASK, TrainingLogPayload(job_id=self._job_id, level=level, template=template, params=full)
        )

    def cancelled(self) -> bool:
        """Chuyển tiếp hàm huỷ tiêm vào: runner quyết lý do dừng, `Reporter` không tự biết."""
        return self._cancelled()

    def finish(self, payload: TrainingFinishedPayload) -> bool:
        """Xả số đo rồi gửi `finished`; gửi lại tới 6 lần, lùi 2-60 s (BE-00 §7). `False` = đã hết lượt."""
        self.flush_metrics()
        for attempt in range(_FINISH_RETRIES + 1):
            try:
                self._send(FINISHED_TASK, payload)
                return True
            except AppError:
                if attempt == _FINISH_RETRIES:
                    break
                self._sleep(_backoff_s(attempt))
        _log.error("training_finished_unsent", extra={"job_id": self._job_id})
        return False

    def start_heartbeats(self, interval_s: float) -> Callable[[], None]:
        """Luồng daemon: gửi `heartbeat(last_epoch)` mỗi `interval_s`; trả hàm dừng (đặt cờ + `join`)."""
        stop = threading.Event()

        def loop() -> None:
            """Thân luồng: chờ `interval_s` (dừng sớm nếu ai gọi hàm dừng), rồi báo nhịp tim cuối."""
            while not stop.wait(interval_s):
                self.heartbeat(self.last_epoch)

        thread = threading.Thread(target=loop, daemon=True)
        thread.start()

        def cancel() -> None:
            """Dừng luồng nhịp tim: đặt cờ rồi chờ luồng thoát, trần `JOIN_TIMEOUT_S` như `slot`/`watchdog`."""
            stop.set()
            thread.join(JOIN_TIMEOUT_S)

        return cancel

    def _now_ms(self) -> int:
        """Giờ hiện tại của `clock` ở milliseconds (Unix epoch)."""
        return int(self._clock.now().timestamp() * 1000)

    def _send_or_log(self, task: str, payload: BaseModel) -> None:
        """Gửi một thông điệp phụ (nhịp tim/số đo/log); gửi hỏng → log máy chủ, không ném lại."""
        try:
            self._send(task, payload)
        except AppError as exc:
            _log.warning("training_send_failed", extra={"job_id": self._job_id, "task": task, "error": exc.code.code})


def _batched_valid(points: list[MetricPoint]) -> list[tuple[MetricPoint, ...]]:
    """Bỏ điểm có `step` lùi/lặp trong cùng `split` (log `WARNING`), rồi chia lô ≤ `MAX_METRIC_POINTS`."""
    kept: list[MetricPoint] = []
    last: dict[str, int] = {}
    for point in points:
        previous = last.get(point.split, -1)
        if point.step <= previous:
            _log.warning("training_metric_step_regressed", extra={"split": point.split, "step": point.step})
            continue
        last[point.split] = point.step
        kept.append(point)
    return [tuple(kept[i : i + MAX_METRIC_POINTS]) for i in range(0, len(kept), MAX_METRIC_POINTS)] if kept else []
