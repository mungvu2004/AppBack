"""Test `Reporter` (B6-03b [8] "Tiến trình con và reporter", "Reporter"): gọi trực tiếp,
`send`/`sleep`/`monotonic`/`clock` đều tiêm được — không cần Redis/Celery thật ở đây.
"""

import logging
from dataclasses import dataclass, field
from typing import Final

import pytest
from pydantic import BaseModel

from apps.ml.training_runner.reporter import Reporter
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.core.errors import AppError
from packages.ml_contracts.payloads import MetricPoint, TrainingFinishedPayload

JOB: Final = "job_01J0000000000000000000000A"


@dataclass
class FakeClock:
    """`Clock` giả: giờ cố định, `monotonic()` phát từ `fake_clock.py` (B0-02) không cần ở đây."""

    epoch_ms: int = 1_700_000_000_000

    def now(self) -> "FakeDatetime":
        """Trả một đối tượng có `.timestamp()` giây từ `epoch_ms`."""
        return FakeDatetime(self.epoch_ms / 1000)


@dataclass
class FakeDatetime:
    """Thay cho `datetime.now()`: chỉ cần `.timestamp()` cho `Reporter._now_ms`."""

    seconds: float

    def timestamp(self) -> float:
        """Giây Unix cố định của test."""
        return self.seconds


@dataclass
class FakeMonotonic:
    """Đồng hồ đơn điệu giả: test tự đẩy `value` để mô phỏng thời gian trôi."""

    value: float = 0.0

    def __call__(self) -> float:
        """`monotonic()` tiêm vào `Reporter`."""
        return self.value


@dataclass
class RecordingSend:
    """`send` giả: ghi mọi lệnh gọi; `fail_times` lần gọi đầu ném `AppError`, còn lại thì đạt."""

    fail_times: int = 0
    calls: list[tuple[str, BaseModel]] = field(default_factory=list)
    _failed: int = 0

    def __call__(self, task: str, payload: BaseModel) -> None:
        """Ném `AppError` `fail_times` lần đầu, sau đó ghi lại và trả."""
        if self._failed < self.fail_times:
            self._failed += 1
            raise AppError(DEPENDENCY_UNAVAILABLE, retry_after=1)
        self.calls.append((task, payload))


@dataclass
class AlwaysFailSend:
    """`send` giả: luôn ném `AppError` — dùng cho test "hỏng mãi"."""

    calls: int = 0

    def __call__(self, task: str, payload: BaseModel) -> None:
        """Đếm lượt gọi rồi luôn ném `AppError`."""
        self.calls += 1
        raise AppError(DEPENDENCY_UNAVAILABLE, retry_after=1)


@dataclass
class RecordingSleep:
    """`sleep` giả: ghi lại mọi khoảng chờ được yêu cầu, không ngủ thật."""

    waited: list[float] = field(default_factory=list)

    def __call__(self, seconds: float) -> None:
        """Ghi lại `seconds` mà không chờ."""
        self.waited.append(seconds)


def _point(step: int, split: str = "train") -> MetricPoint:
    """Một `MetricPoint` hợp lệ tối thiểu (chỉ `loss`)."""
    return MetricPoint(step=step, epoch=1, split=split, recorded_at_ms=0, loss=0.1)


def _finished(status: str = "succeeded") -> TrainingFinishedPayload:
    """`TrainingFinishedPayload` hợp lệ tối thiểu cho `status`."""
    if status == "succeeded":
        return TrainingFinishedPayload(
            job_id=JOB,
            status="succeeded",
            weights_key="ml/models/mdl_x/weights-" + "0" * 32 + ".onnx",
            checksum_sha256="0" * 64,
            metrics={"iou": 0.5},
        )
    return TrainingFinishedPayload(job_id=JOB, status="failed", error_code="INTERNAL")


def _reporter(send: object, *, sleep: object = None, monotonic: object = None) -> Reporter:
    """`Reporter` của job `JOB`; `cancelled` luôn `False` (không test ở đây)."""
    kwargs: dict[str, object] = {
        "job_id": JOB,
        "send": send,
        "clock": FakeClock(),
        "monotonic": monotonic or FakeMonotonic(),
        "cancelled": lambda: False,
    }
    if sleep is not None:
        kwargs["sleep"] = sleep
    return Reporter(**kwargs)  # type: ignore[arg-type]  # kwargs lắp đúng chữ ký Reporter.__init__


def test_finish_retries_then_succeeds() -> None:
    """`send` hỏng 2 lần rồi đạt: đúng một `finished`, `sleep` được gọi với 2 rồi 4 giây."""
    send = RecordingSend(fail_times=2)
    sleep = RecordingSleep()
    reporter = _reporter(send, sleep=sleep)
    assert reporter.finish(_finished()) is True
    assert [task for task, _ in send.calls] == ["default.training_bridge.finished"]
    assert sleep.waited == [2.0, 4.0]


def test_finish_exhausts_and_logs_unsent(caplog: pytest.LogCaptureFixture) -> None:
    """`send` hỏng mãi: `finish` trả `False`, log `training_finished_unsent`, 6 lần chờ."""
    send = AlwaysFailSend()
    sleep = RecordingSleep()
    reporter = _reporter(send, sleep=sleep)
    with caplog.at_level(logging.ERROR, logger="apps.ml.training_runner.reporter"):
        result = reporter.finish(_finished(status="failed"))
    assert result is False
    assert len(sleep.waited) == 6
    assert send.calls == 7
    unsent = [r for r in caplog.records if r.message == "training_finished_unsent"]
    assert len(unsent) == 1
    assert unsent[0].job_id == JOB  # type: ignore[attr-defined]  # extra= của logging.error


def test_metric_flushes_at_100_points() -> None:
    """Gom tới điểm 100 thì xả đúng một lô 100 điểm (không cần đợi 10 s)."""
    send = RecordingSend()
    reporter = _reporter(send)
    for step in range(100):
        reporter.metric(_point(step))
    assert len(send.calls) == 1
    task, payload = send.calls[0]
    assert task == "default.training_bridge.metrics"
    assert len(payload.points) == 100  # type: ignore[attr-defined]  # TrainingMetricsPayload.points


def test_metric_flushes_after_10s() -> None:
    """Chưa đủ 100 điểm nhưng đã quá 10 s từ lần xả trước: xả ngay."""
    monotonic = FakeMonotonic(0.0)
    send = RecordingSend()
    reporter = _reporter(send, monotonic=monotonic)
    reporter.metric(_point(0))
    monotonic.value = 10.0
    reporter.metric(_point(1))
    assert len(send.calls) == 1
    assert len(send.calls[0][1].points) == 2  # type: ignore[attr-defined]  # BaseModel, thật là TrainingMetricsPayload


def test_metrics_flush_before_finished() -> None:
    """Số đo chưa xả được xả trước khi `finished` đi, nên `finished` luôn là thông điệp cuối."""
    send = RecordingSend()
    reporter = _reporter(send)
    reporter.metric(_point(0))
    assert reporter.finish(_finished()) is True
    tasks_sent = [task for task, _ in send.calls]
    assert tasks_sent == ["default.training_bridge.metrics", "default.training_bridge.finished"]


def test_log_line_increments() -> None:
    """`params["line"]` tăng dần từ 1 qua các lần gọi `log`."""
    send = RecordingSend()
    reporter = _reporter(send)
    reporter.log("info", "training_epoch_finished", {"epoch": 1})
    reporter.log("info", "training_epoch_finished", {"epoch": 2})
    lines = [p.params["line"] for _, p in send.calls]  # type: ignore[attr-defined]  # thật là TrainingLogPayload
    assert lines == [1, 2]


def test_send_failure_on_log_does_not_raise(caplog: pytest.LogCaptureFixture) -> None:
    """`log` gửi hỏng: log máy chủ `training_send_failed`, không ném lại."""
    reporter = _reporter(AlwaysFailSend())
    with caplog.at_level(logging.WARNING, logger="apps.ml.training_runner.reporter"):
        reporter.log("info", "training_epoch_finished", {"epoch": 1})
    failed = [r for r in caplog.records if r.message == "training_send_failed"]
    assert len(failed) == 1


def test_send_failure_on_heartbeat_does_not_raise(caplog: pytest.LogCaptureFixture) -> None:
    """`heartbeat` gửi hỏng: log máy chủ `training_send_failed`, không ném lại."""
    reporter = _reporter(AlwaysFailSend())
    with caplog.at_level(logging.WARNING, logger="apps.ml.training_runner.reporter"):
        reporter.heartbeat(1)
    failed = [r for r in caplog.records if r.message == "training_send_failed"]
    assert len(failed) == 1


def test_heartbeat_thread_sends_and_stops_cleanly() -> None:
    """Luồng nhịp tim gửi ≥ 2 nhịp với `interval_s=0.05` rồi dừng sạch (hàm dừng trả, `join` xong)."""
    send = RecordingSend()
    reporter = _reporter(send)
    reporter.heartbeat(0)
    stop = reporter.start_heartbeats(0.05)
    import time

    time.sleep(0.15)
    stop()
    heartbeats = [task for task, _ in send.calls if task == "default.training_bridge.heartbeat"]
    assert len(heartbeats) >= 2


def test_metric_drops_regressed_step(caplog: pytest.LogCaptureFixture) -> None:
    """Điểm có `step` lùi trong cùng split bị bỏ + log `WARNING`, không làm hỏng cả lô."""
    send = RecordingSend()
    reporter = _reporter(send)
    reporter.metric(_point(5))
    with caplog.at_level(logging.WARNING, logger="apps.ml.training_runner.reporter"):
        reporter.metric(_point(3))
    reporter.flush_metrics()
    assert len(send.calls) == 1
    points = send.calls[0][1].points  # type: ignore[attr-defined]  # BaseModel, thật là TrainingMetricsPayload
    assert [p.step for p in points] == [5]
    regressed = [r for r in caplog.records if r.message == "training_metric_step_regressed"]
    assert len(regressed) == 1
