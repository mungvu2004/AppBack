"""J-case của `start_training_runner` (BE-00 §7 "Test task", B6-03b [8]).

`test_start_training_runner__J01`, `__J01_smoke` không thuộc việc này (A). Dịch vụ Redis
**thật**; `subprocess.Popen` vá được ở tầng này (D sẽ chạy tiến trình con thật qua
`celery_worker_factory`, nên task luôn chạy trong worker thật, không gọi thân trực tiếp).
"""

import json
import time
from collections.abc import Callable, Iterator
from typing import ClassVar

import pytest

from apps.ml.training_runner import tasks
from apps.ml.training_runner.errors import TRAINING_LAUNCH_FAILED
from apps.ml.training_runner.keys import START_TASK, cancel_key, claim_key
from apps.ml.training_runner.tests import support
from apps.ml.training_runner.tests.support import queued_messages, train_payload
from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.messaging.celery_app import producer_app, send_task
from packages.messaging.redis import SyncRedis, broker_redis_sync
from packages.testing.fixtures.messaging import WorkerFactory

LISTEN = "ml.training"
WAIT_S = 10.0


@pytest.fixture
def broker(messaging_env: None) -> Iterator[SyncRedis]:
    """Client broker thật (hàng `ml.training` + `default`), sạch đầu/cuối test (BE-00 §7 "Test task")."""
    client = broker_redis_sync()
    client.delete(LISTEN, "default")
    yield client
    client.delete(LISTEN, "default")
    client.close()


@pytest.fixture
def safe(messaging_env: None) -> Iterator[SyncRedis]:
    """Client DB an toàn (= `training_redis()`) cho claim/cancel của job thử."""
    client = tasks.training_redis()
    yield client
    client.close()


class _RecordedPopen:
    """Thay `subprocess.Popen`: nhớ `argv`/`kwargs`, thân JSON ghi vào stdin, không chạy gì thật."""

    calls: ClassVar[list[dict[str, object]]] = []

    def __init__(
        self, argv: list[str], *, stdin: object = None, start_new_session: bool = False, env: object = None
    ) -> None:
        """Nhớ `argv`/`start_new_session` của lệnh gọi; `self.stdin` trỏ về chính mình để nhận `write`."""
        self.argv = argv
        self.start_new_session = start_new_session
        self._written = b""
        self.stdin = self

    def write(self, data: bytes) -> None:
        """Ghi lại byte stdin thay cho pipe thật."""
        self._written += data

    def close(self) -> None:
        """Chốt lại thân JSON đã ghi để test đọc qua `calls`."""
        _RecordedPopen.calls.append(
            {"argv": self.argv, "start_new_session": self.start_new_session, "stdin": self._written}
        )

    def wait(self) -> int:
        """Luồng daemon của `tasks._launch` gọi hàm này; không tiến trình thật nên trả ngay."""
        return 0


@pytest.fixture(autouse=True)
def _clear_calls() -> Iterator[None]:
    """Mỗi test bắt đầu với sổ `_RecordedPopen.calls` trống."""
    _RecordedPopen.calls = []
    yield
    _RecordedPopen.calls = []


def _empty_dataset() -> support.Dataset:
    """Dataset giả không entries: `start_training_runner` chưa đọc dataset, chỉ claim + launch."""
    return support.Dataset(new_id("dsv", SystemClock()), "0" * 64, 0, ())


def _wait(predicate: Callable[[], object], what: str) -> None:
    """Chờ tới `WAIT_S` cho một điều kiện; quá hạn là hỏng, không im lặng bỏ qua.

    `object` chứ không `bool`: nơi gọi truyền thẳng hàm trả danh sách thông điệp và điều kiện là
    "danh sách đã không rỗng" — xét theo chân lý, đúng như `if` của Python.
    """
    deadline = time.monotonic() + WAIT_S
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError(f"quá {WAIT_S} giây mà chưa: {what}")


def test_start_training_runner_cancelled_before_launch(
    broker: SyncRedis, safe: SyncRedis, monkeypatch: pytest.MonkeyPatch, celery_worker_factory: WorkerFactory
) -> None:
    """`cancel_key` có mặt: không `SET NX`, không `Popen`, task ack mà không claim."""
    monkeypatch.setattr(tasks.subprocess, "Popen", _RecordedPopen)
    payload = train_payload(_empty_dataset())
    safe.set(cancel_key(payload.job_id), "1")
    with celery_worker_factory([LISTEN]):
        send_task(START_TASK, payload)
        _wait(lambda: broker.llen(LISTEN) == 0, "task ack")
        time.sleep(0.2)
    assert _RecordedPopen.calls == []
    assert not safe.exists(claim_key(payload.job_id))


def test_start_training_runner__J06(
    broker: SyncRedis, safe: SyncRedis, monkeypatch: pytest.MonkeyPatch, celery_worker_factory: WorkerFactory
) -> None:
    """Claim đã có token khác giữ: không `Popen`, claim vẫn mang token cũ sau lượt (J06)."""
    monkeypatch.setattr(tasks.subprocess, "Popen", _RecordedPopen)
    payload = train_payload(_empty_dataset())
    safe.set(claim_key(payload.job_id), "existing-token", nx=True, px=120_000)
    with celery_worker_factory([LISTEN]):
        send_task(START_TASK, payload)
        _wait(lambda: broker.llen(LISTEN) == 0, "task ack")
        time.sleep(0.2)
    assert _RecordedPopen.calls == []
    assert safe.get(claim_key(payload.job_id)) == "existing-token"


def test_start_training_runner__J03(
    broker: SyncRedis, safe: SyncRedis, monkeypatch: pytest.MonkeyPatch, celery_worker_factory: WorkerFactory
) -> None:
    """`Popen` ném `OSError`: `finished(failed, TRAINING_LAUNCH_FAILED)` trên `default`, claim đã xoá."""

    def failing(*args: object, **kwargs: object) -> None:
        """Thay `Popen`: luôn ném `OSError` (ví dụ Python không khởi chạy được)."""
        raise OSError("boom")

    monkeypatch.setattr(tasks.subprocess, "Popen", failing)
    payload = train_payload(_empty_dataset())
    with celery_worker_factory([LISTEN]):
        send_task(START_TASK, payload)
        _wait(lambda: support.for_job(queued_messages(broker, "default"), payload.job_id), "finished(failed)")
    messages = support.for_job(queued_messages(broker, "default"), payload.job_id)
    assert len(messages) == 1
    task, body = messages[0]
    assert task == tasks.FINISHED_TASK
    assert (body["status"], body["error_code"]) == ("failed", TRAINING_LAUNCH_FAILED)
    assert not safe.exists(claim_key(payload.job_id))


class _StdinWriteFailsPopen:
    """`Popen` "chạy được" nhưng ghi stdin hỏng: `_launch` phải `kill()` nó trước khi xoá claim."""

    killed: ClassVar[list[bool]] = []

    def __init__(
        self, argv: list[str], *, stdin: object = None, start_new_session: bool = False, env: object = None
    ) -> None:
        """Giả `Popen` "chạy được": `self.stdin` trỏ về chính mình để `write` ném hỏng."""
        self.stdin = self

    def write(self, data: bytes) -> None:
        """Ghi stdin hỏng (ống đã đóng phía bên kia, ví dụ)."""
        raise OSError("broken pipe")

    def close(self) -> None:
        """Không bao giờ tới đây: `write` đã ném trước."""

    def kill(self) -> None:
        """Runner phải gọi hàm này khi ghi stdin hỏng sau khi tiến trình đã khởi chạy."""
        _StdinWriteFailsPopen.killed.append(True)

    def wait(self) -> int:
        """Không gọi tới nếu `_launch` đã ném trước khi tới luồng daemon `proc.wait()`."""
        return 0


def test_start_training_runner_kills_process_when_stdin_write_fails(
    broker: SyncRedis, safe: SyncRedis, monkeypatch: pytest.MonkeyPatch, celery_worker_factory: WorkerFactory
) -> None:
    """Ghi stdin hỏng **sau** khi `Popen` đã chạy: `kill()` tiến trình, xoá claim, báo đúng một `finished`."""
    _StdinWriteFailsPopen.killed = []
    monkeypatch.setattr(tasks.subprocess, "Popen", _StdinWriteFailsPopen)
    payload = train_payload(_empty_dataset())
    with celery_worker_factory([LISTEN]):
        send_task(START_TASK, payload)
        _wait(lambda: support.for_job(queued_messages(broker, "default"), payload.job_id), "finished(failed)")
    assert _StdinWriteFailsPopen.killed == [True]
    messages = support.for_job(queued_messages(broker, "default"), payload.job_id)
    assert len(messages) == 1
    assert (messages[0][1]["status"], messages[0][1]["error_code"]) == ("failed", TRAINING_LAUNCH_FAILED)
    assert not safe.exists(claim_key(payload.job_id))


def test_start_training_runner__J08(
    broker: SyncRedis, monkeypatch: pytest.MonkeyPatch, celery_worker_factory: WorkerFactory
) -> None:
    """Payload độc (thiếu trường): worker ack, không `Popen`, không thông điệp `finished`."""
    monkeypatch.setattr(tasks.subprocess, "Popen", _RecordedPopen)
    job_id = new_id("job", SystemClock())
    poison = {"schema_version": 1, "job_id": job_id}
    with celery_worker_factory([LISTEN]):
        producer_app().send_task(START_TASK, args=[poison], queue=LISTEN)
        _wait(lambda: broker.llen(LISTEN) == 0, "thông điệp độc đã ack")
        time.sleep(0.2)
    assert _RecordedPopen.calls == []
    assert support.for_job(queued_messages(broker, "default"), job_id) == []


def test_start_training_runner_launches_process(
    broker: SyncRedis, safe: SyncRedis, monkeypatch: pytest.MonkeyPatch, celery_worker_factory: WorkerFactory
) -> None:
    """Lượt khởi chạy thành công: `argv`, `start_new_session=True` đúng; stdin đúng chữ ký chung."""
    monkeypatch.setattr(tasks.subprocess, "Popen", _RecordedPopen)
    payload = train_payload(_empty_dataset())
    with celery_worker_factory([LISTEN]):
        send_task(START_TASK, payload)
        _wait(lambda: _RecordedPopen.calls, "Popen được gọi")
        time.sleep(0.2)
    assert len(_RecordedPopen.calls) == 1
    call = _RecordedPopen.calls[0]
    assert call["argv"] == [tasks.sys.executable, "-m", "apps.ml.training_runner"]
    assert call["start_new_session"] is True
    sent = json.loads(call["stdin"])  # type: ignore[arg-type]  # bytes JSON
    assert sent["payload"]["job_id"] == payload.job_id
    token = sent["claim_token"]
    assert len(token) == 32
    assert safe.get(claim_key(payload.job_id)) == token


def test_start_training_runner_child_env_is_allowlisted(safe: SyncRedis, monkeypatch: pytest.MonkeyPatch) -> None:
    """SEC-020: con huấn luyện nhận `env=` lọc theo danh sách cho phép — không thừa hưởng khoá/mật khẩu của `ml`."""
    seen: dict[str, object] = {}

    class _EnvPopen(_RecordedPopen):
        """`_RecordedPopen` nhớ thêm `env` của lệnh gọi."""

        def __init__(self, argv: list[str], **kwargs: object) -> None:
            """Ghi `kwargs` rồi chuyển phần còn lại cho bản gốc."""
            seen.update(kwargs)
            super().__init__(argv, stdin=kwargs.get("stdin"), start_new_session=bool(kwargs.get("start_new_session")))

    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s3cret")
    monkeypatch.setenv("SMTP_PASSWORD", "x")
    monkeypatch.setenv("SECRET_KEY", "k" * 32)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    monkeypatch.setenv("PYTHONPATH", "/opt/appback")
    monkeypatch.setenv("REDIS_BROKER_URL", "redis://redis-broker:6379/0")
    ml_s3_value = "ml-s3-value"
    monkeypatch.setenv("S3_SECRET_KEY", ml_s3_value)
    monkeypatch.setenv("TRAINING_MAX_WALL_S", "60")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_JSON", "false")
    monkeypatch.setattr(tasks.subprocess, "Popen", _EnvPopen)
    payload = train_payload(_empty_dataset())
    tasks._launch(payload, "t" * 32, "claim", safe)
    assert "env" in seen, "Popen được gọi không có env= — con thừa hưởng toàn bộ môi trường"
    env = seen["env"]
    assert isinstance(env, dict)
    for leaked in ("AWS_SECRET_ACCESS_KEY", "SMTP_PASSWORD", "SECRET_KEY", "DATABASE_URL"):
        assert leaked not in env
    assert env["PYTHONPATH"] == "/opt/appback"
    assert env["REDIS_BROKER_URL"] == "redis://redis-broker:6379/0"
    assert env["S3_SECRET_KEY"] == ml_s3_value
    assert env["TRAINING_MAX_WALL_S"] == "60"
    assert (env["LOG_LEVEL"], env["LOG_JSON"]) == ("DEBUG", "false"), "con mất cấu hình log của cha (F17)"
