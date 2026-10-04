"""Test runtime của job huấn luyện (B6-03b [8] "Task", "Tiến trình con và reporter", "M-case").

Bốn tầng, dịch vụ **thật** ở cả bốn (K23: không `fakeredis`, không `task_always_eager`): Redis
Testcontainers (`messaging_env`), kho đĩa thật (`local_storage`), trainer tí hon CPU
(`support.TinyTrainer`).

- `__J01`: `run_training_job` trong tiến trình pytest với `send=send_task` thật — đủ bốn loại
  thông điệp trên hàng `default`, `finished(succeeded)` cuối.
- `__J01_smoke`: worker Celery thật (`celery_worker_factory`) chạy task, task mở **tiến trình con
  thật** `python -m apps.ml.training_runner` qua `TRAINING_TRAINER_OVERRIDE`; kiểm cả khoá trọng
  số, ONNX đọc lại được, checksum và claim đã trả.
- `cancel_while_waiting`: tiến trình Python mới (`_CANCEL_WHILE_WAITING_SCRIPT`) ghim rằng huỷ
  trong lúc chờ `SLOT_KEY` không bao giờ nhập `torch`, không gọi `resolve_device`/`trainers()`.
- M04 (bốn test `..._m04_*`): `ML_DEVICE` quyết khoá nào bị giữ — `cpu` chỉ `training_slot`,
  `cuda` giữ cả khoá `gpu:0`; job sau chờ khoá bận; mất khoá giữa epoch → `finished(failed)`
  mang đúng mã.
"""

import asyncio
import functools
import hashlib
import json
import logging
import os
import subprocess
import sys
import textwrap
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import onnx
import pytest
import torch
from pydantic import BaseModel

from apps.ml.runtime.gpu import GPU_LOCK_NAME
from apps.ml.training_runner import keys, runner
from apps.ml.training_runner import tasks as _tasks  # noqa: F401 — đăng ký START_TASK vào celery_test_app
from apps.ml.training_runner.errors import GPU_LOCK_LOST, TRAINING_SLOT_LOST
from apps.ml.training_runner.redis_sync import training_redis
from apps.ml.training_runner.settings import TrainingRunnerSettings
from apps.ml.training_runner.tests.support import (
    Dataset,
    TinyTrainer,
    for_job,
    put_dataset,
    queued_messages,
    read_object,
    train_payload,
)
from packages.core.clock import SystemClock
from packages.messaging.celery_app import send_task
from packages.messaging.payloads.training import WEIGHTS_NAME_RE
from packages.messaging.redis import SyncRedis, broker_redis_sync
from packages.storage.keys import model_artifact
from packages.storage.local import LocalDiskStorage
from packages.testing.fixtures.messaging import WorkerFactory
from packages.testing.fixtures.storage import PUBLIC_BASE_URL, STORAGE_SECRET

_log = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[4]
QUEUE = "default"
WAIT_S = 90.0


def _fail_exit(code: int) -> None:
    """`exit=` tiêm cho `run_training_job` khi test không mong luồng canh tự thoát."""
    raise AssertionError(f"exit({code}) không được gọi trong lượt thành công")


@pytest.fixture
def broker(messaging_env: None) -> Iterator[SyncRedis]:
    """Hàng `default` sạch ở đầu và cuối test (BE-00 §7 "Test task")."""
    client = broker_redis_sync()
    client.delete(QUEUE)
    yield client
    client.delete(QUEUE)
    client.close()


@pytest.fixture
def claim_client(messaging_env: None) -> Iterator[SyncRedis]:
    """Client DB an toàn của test: dọn claim/slot/cancel còn sót giữa các lượt chạy song song."""
    client = training_redis()
    yield client
    client.close()


def test_start_training_runner__J01(
    broker: SyncRedis, claim_client: SyncRedis, local_storage: LocalDiskStorage
) -> None:
    """`run_training_job` trong tiến trình pytest, `send=send_task` thật: đủ 4 loại thông điệp, `finished` cuối."""
    dataset = asyncio.run(put_dataset(local_storage))
    payload = train_payload(dataset)
    token = keys.new_token()
    claim_client.set(keys.claim_key(payload.job_id), token, nx=True, px=120_000)

    exit_code = runner.run_training_job(
        payload,
        claim_token=token,
        trainers=lambda: {payload.family: TinyTrainer(payload.family)},
        storage=local_storage,
        send=send_task,
        redis=claim_client,
        clock=SystemClock(),
        monotonic=time.monotonic,
        settings=TrainingRunnerSettings(),
        exit=_fail_exit,
    )

    assert exit_code == 0
    messages = for_job(queued_messages(broker, QUEUE), payload.job_id)
    kinds = [task for task, _ in messages]
    assert keys.HEARTBEAT_TASK in kinds
    assert keys.METRICS_TASK in kinds
    assert keys.LOG_TASK in kinds
    assert kinds[-1] == keys.FINISHED_TASK
    assert messages[-1][1]["status"] == "succeeded"


def _runner_env(*, storage_root: Path, redis_broker_url: str, ml_device: str = "cpu") -> dict[str, str]:
    """Biến môi trường một tiến trình con huấn luyện của tệp này cần (BE-00 §12).

    Một nguồn cho hai lối dùng: `_smoke_env` đặt chúng bằng `monkeypatch` (tiến trình con do task
    Celery mở, kế thừa `os.environ`), `cancel_while_waiting` phủ chúng lên `dict(os.environ)`.
    """
    return {
        "APP_ENV": "test",
        "ML_DEVICE": ml_device,
        "STORAGE_BACKEND": "local",
        "STORAGE_LOCAL_ROOT": str(storage_root),
        "PUBLIC_BASE_URL": PUBLIC_BASE_URL,
        "SECRET_KEY": STORAGE_SECRET,
        "REDIS_BROKER_URL": redis_broker_url,
        "PYTHONPATH": str(REPO_ROOT),
    }


def _smoke_env(monkeypatch: pytest.MonkeyPatch, *, storage_root: Path, redis_broker_url: str) -> None:
    """Môi trường kế thừa `os.environ` cho tiến trình con `python -m apps.ml.training_runner` (BE-00 §12)."""
    for name, value in _runner_env(storage_root=storage_root, redis_broker_url=redis_broker_url).items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("TRAINING_TRAINER_OVERRIDE", "apps.ml.training_runner.tests.support:TRAINER")


def test_start_training_runner__J01_smoke(
    broker: SyncRedis,
    local_storage: LocalDiskStorage,
    celery_worker_factory: WorkerFactory,
    monkeypatch: pytest.MonkeyPatch,
    redis_broker_url: str,
    tmp_path: Path,
) -> None:
    """`celery_worker_factory(["ml.training"])` + tiến trình con thật qua `TRAINING_TRAINER_OVERRIDE`."""
    dataset = asyncio.run(put_dataset(local_storage))
    payload = train_payload(dataset)
    _smoke_env(monkeypatch, storage_root=tmp_path / "objects", redis_broker_url=redis_broker_url)

    with celery_worker_factory(["ml.training"]):
        send_task(keys.START_TASK, payload)
        deadline = time.monotonic() + WAIT_S
        finished: list[dict[str, object]] = []
        while time.monotonic() < deadline:
            finished = [
                msg
                for task, msg in for_job(queued_messages(broker, QUEUE), payload.job_id)
                if task == keys.FINISHED_TASK
            ]
            if finished:
                break
            time.sleep(0.2)

    assert len(finished) == 1, finished
    assert finished[0]["status"] == "succeeded"
    messages = for_job(queued_messages(broker, QUEUE), payload.job_id)
    assert any(task == keys.METRICS_TASK for task, _ in messages)
    assert any(task == keys.LOG_TASK for task, _ in messages)

    weights_key = str(finished[0]["weights_key"])
    prefix = model_artifact(keys.trained_version_id(payload.job_id), "placeholder")
    prefix_dir = prefix.rsplit("/", 1)[0] + "/"
    assert weights_key.startswith(prefix_dir)
    assert WEIGHTS_NAME_RE.match(weights_key.rsplit("/", 1)[-1])

    data = asyncio.run(read_object(local_storage, weights_key))
    model = onnx.load_model_from_string(data)
    assert model.ir_version >= 1
    assert hashlib.sha256(data).hexdigest() == finished[0]["checksum_sha256"]

    client = training_redis()
    try:
        assert client.get(keys.claim_key(payload.job_id)) is None
    finally:
        client.close()


_CANCEL_WHILE_WAITING_SCRIPT: Final = textwrap.dedent(
    """
    import json, sys, time
    from apps.ml.training_runner import runner, keys
    from apps.ml.training_runner.redis_sync import training_redis
    from apps.ml.training_runner.settings import TrainingRunnerSettings
    from packages.core.clock import SystemClock
    from packages.ml_contracts.payloads import TrainJobPayload
    from packages.storage.factory import create_storage
    from packages.storage.settings import get_storage_settings

    payload = TrainJobPayload.model_validate(json.loads({payload_json!r}))
    claim_token = {claim_token!r}

    def _device_fail(setting):
        raise AssertionError("resolve_device không được gọi khi huỷ trong lúc chờ khoá")

    def _trainers_fail():
        raise AssertionError("trainers() không được gọi khi huỷ trong lúc chờ khoá")

    def _gpu_fail(**kwargs):
        raise AssertionError("gpu_slot không được gọi khi huỷ trong lúc chờ khoá")

    runner.resolve_device = _device_fail
    runner.gpu_slot = _gpu_fail

    storage = create_storage(get_storage_settings(), None, SystemClock())
    redis = training_redis()
    finished = []

    def send(name, body):
        if name == keys.FINISHED_TASK:
            finished.append(body.model_dump(mode="json"))

    settings = TrainingRunnerSettings(training_cancel_poll_s=1.0)
    started = time.monotonic()
    runner.run_training_job(
        payload,
        claim_token=claim_token,
        trainers=_trainers_fail,
        storage=storage,
        send=send,
        redis=redis,
        clock=SystemClock(),
        monotonic=time.monotonic,
        settings=settings,
        exit=lambda code: (_ for _ in ()).throw(AssertionError(f"exit({{code}}) không mong đợi")),
    )
    elapsed = time.monotonic() - started
    print(json.dumps({{"torch": "torch" in sys.modules, "finished": finished, "elapsed": elapsed}}))
    """
)
"""Thân tiến trình con của `cancel_while_waiting`; dùng qua `.format(payload_json=…, claim_token=…)`.

Hằng module chứ không chuỗi trong thân test: R-08 chặn hàm test quá 50 dòng và script này là **dữ
liệu** của test, không phải logic. Dấu ngoặc nhọn của chính script phải nhân đôi (`{{…}}`).
"""


@pytest.mark.perf
def test_run_training_job_cancel_while_waiting(
    claim_client: SyncRedis,
    local_storage: LocalDiskStorage,
    redis_broker_url: str,
    tmp_path: Path,
) -> None:
    """Token khác giữ `SLOT_KEY`, `cancel_key` có → huỷ trước khi nhập `torch` hay chạy trainer."""
    dataset = asyncio.run(put_dataset(local_storage))
    payload = train_payload(dataset)
    other_token = "khac-" + keys.new_token()
    claim_client.set(keys.SLOT_KEY, other_token, px=60_000)
    claim_client.set(keys.cancel_key(payload.job_id), "1", px=60_000)
    claim_token = keys.new_token()
    claim_client.set(keys.claim_key(payload.job_id), claim_token, nx=True, px=120_000)

    script = _CANCEL_WHILE_WAITING_SCRIPT.format(
        payload_json=json.dumps(payload.model_dump(mode="json")), claim_token=claim_token
    )
    env = dict(os.environ) | _runner_env(
        storage_root=tmp_path / "objects", redis_broker_url=redis_broker_url, ml_device="auto"
    )
    result = subprocess.run(  # noqa: S603 — trình thông dịch của chính venv, mã cố định
        [sys.executable, "-c", script], cwd=REPO_ROOT, env=env, capture_output=True, text=True, check=False, timeout=60
    )

    assert result.returncode == 0, result.stderr
    outcome = json.loads(result.stdout.strip().splitlines()[-1])
    assert outcome["finished"], result.stderr
    assert outcome["finished"][-1]["status"] == "cancelled"
    _log.info("cancel_wait_elapsed_s=%.3f", outcome["elapsed"])
    assert outcome["elapsed"] <= 10
    assert outcome["torch"] is False


@dataclass(frozen=True, slots=True)
class M04:
    """Bàn thử M04: `run()` chạy một lượt thật, và những gì lượt ấy đã chạm (`gpu_calls`).

    `run` là method chứ không hàm lồng trong fixture: R-08 chặn hàm quá 50 dòng, và cách này
    cho mỗi test một tên tham số rõ (`m04.run(device=…)`) thay vì một closure không gọi lại được.
    """

    redis: SyncRedis
    storage: LocalDiskStorage
    monkeypatch: pytest.MonkeyPatch
    dataset: Dataset
    gpu_calls: list[float]
    gpu_key: str

    def run(
        self, *, device: str, on_epoch: list[Callable[[], None]], poll_s: float = 5.0
    ) -> tuple[dict[str, object], list[str]]:
        """Một lượt `run_training_job` thật; trả payload `finished` và danh sách template log job."""
        self.monkeypatch.setenv("ML_DEVICE", device)
        payload = train_payload(self.dataset)
        token = keys.new_token()
        self.redis.set(keys.claim_key(payload.job_id), token, nx=True, px=120_000)
        finished: dict[str, object] = {}
        logs: list[str] = []

        def send(name: str, body: BaseModel) -> None:
            """Thu `finished` và template log; `send` thật là `send_task` (ở đây không cần broker)."""
            dump = body.model_dump(mode="json")
            if name == keys.FINISHED_TASK:
                finished.update(dump)
            elif name == keys.LOG_TASK:
                logs.append(str(dump["template"]))

        trainer = TinyTrainer(payload.family, on_epoch=on_epoch)
        runner.run_training_job(
            payload,
            claim_token=token,
            trainers=lambda: {payload.family: trainer},
            storage=self.storage,
            send=send,
            redis=self.redis,
            clock=SystemClock(),
            monotonic=time.monotonic,
            settings=TrainingRunnerSettings(training_cancel_poll_s=poll_s),
            exit=_fail_exit,
        )
        return finished, logs


@pytest.fixture
def m04(claim_client: SyncRedis, local_storage: LocalDiskStorage, monkeypatch: pytest.MonkeyPatch) -> M04:
    """Khoá slot/GPU TTL 600 ms (test không phải chờ 60 s), `gpu_slot` thật nhưng có theo dõi.

    `torch.cuda.is_available` luôn `True` để nhánh `cuda` đi hết đường thật; `ML_DEVICE` do mỗi
    lượt `run` đặt; fixture `ml_settings_cache` (autouse toàn cục, `packages/testing/fixtures/ml_settings.py`)
    xoá cache trước và sau mỗi test nên không ai thừa hưởng `ML_DEVICE` của ai.
    """
    gpu_calls: list[float] = []
    real_gpu_slot = runner.gpu_slot  # type: ignore[attr-defined]  # vá theo tên module nội bộ, chu-ky B6-03b cho phép
    fast_training_slot = functools.partial(
        runner.training_slot,  # type: ignore[attr-defined]  # vá theo tên module nội bộ, chu-ky B6-03b cho phép
        ttl_ms=600,
        renew_every_ms=150,
    )

    def spying_gpu_slot(*, wait_s: float) -> object:
        """`gpu_slot` thật, ghi lại mỗi lần runner xin khoá GPU (chỉ nhánh cuda được xin)."""
        gpu_calls.append(wait_s)
        return real_gpu_slot(wait_s=wait_s, ttl_ms=600, renew_every_ms=150)

    monkeypatch.setattr(runner, "training_slot", fast_training_slot)
    monkeypatch.setattr(runner, "gpu_slot", spying_gpu_slot)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    return M04(
        redis=claim_client,
        storage=local_storage,
        monkeypatch=monkeypatch,
        dataset=asyncio.run(put_dataset(local_storage)),
        gpu_calls=gpu_calls,
        gpu_key=f"lock:{GPU_LOCK_NAME}",
    )


def test_run_training_job_m04_waits_for_a_busy_slot(m04: M04) -> None:
    """Token khác đang giữ `SLOT_KEY` → lượt chờ, log `training_gpu_waiting`, rồi vẫn xong."""
    m04.redis.set(keys.SLOT_KEY, "khac-" + keys.new_token(), px=2_000)
    threading.Timer(1.0, lambda: m04.redis.delete(keys.SLOT_KEY)).start()

    finished, logs = m04.run(device="cpu", on_epoch=[], poll_s=0.5)

    assert finished.get("status") == "succeeded"
    assert "training_gpu_waiting" in logs
    assert m04.gpu_calls == []


def test_run_training_job_m04_cpu_skips_the_gpu_lock(m04: M04) -> None:
    """`ML_DEVICE=cpu` chỉ giữ `training_slot`: `gpu_slot` không bao giờ được gọi."""
    finished, _ = m04.run(device="cpu", on_epoch=[])

    assert finished.get("status") == "succeeded"
    assert m04.gpu_calls == []


def test_run_training_job_m04_cuda_holds_both_locks(m04: M04) -> None:
    """`ML_DEVICE=cuda` giữ **cả** `SLOT_KEY` và khoá `gpu:0` suốt mọi epoch, xin GPU đúng một lần."""

    def check_both_locks() -> None:
        """Móc mỗi epoch: nhánh cuda phải giữ cả hai khoá."""
        assert m04.redis.exists(keys.SLOT_KEY) == 1
        assert m04.redis.exists(m04.gpu_key) == 1

    finished, _ = m04.run(device="cuda", on_epoch=[check_both_locks])

    assert finished.get("status") == "succeeded"
    assert len(m04.gpu_calls) == 1


@pytest.mark.parametrize(
    ("device", "lock", "code"),
    [("cpu", "slot", TRAINING_SLOT_LOST), ("cuda", "gpu", GPU_LOCK_LOST)],
)
def test_run_training_job_m04_fails_when_a_lock_is_lost(m04: M04, device: str, lock: str, code: str) -> None:
    """Khoá bị xoá dưới chân runner giữa epoch → `finished(failed)` mang đúng mã của khoá ấy."""
    key = keys.SLOT_KEY if lock == "slot" else m04.gpu_key

    def drop_key() -> None:
        """Móc mỗi epoch: xoá khoá rồi nhường một nhịp để luồng gia hạn bật `lost`."""
        m04.redis.delete(key)
        time.sleep(0.4)

    finished, _ = m04.run(device=device, on_epoch=[drop_key])

    assert finished.get("status") == "failed"
    assert finished.get("error_code") == code


def test_tasks_import_without_db_or_torch() -> None:
    """`apps.ml.training_runner.tasks` nhập được khi `sqlalchemy`, `torch` bị chặn (BE-00 §12)."""
    script = textwrap.dedent(
        """
        import importlib, importlib.abc, sys

        class Block(importlib.abc.MetaPathFinder):
            def find_spec(self, name, path=None, target=None):
                top = name.split(".")[0]
                if top in ("sqlalchemy", "torch"):
                    raise ImportError("chặn " + name)
                return None

        sys.meta_path.insert(0, Block())
        importlib.import_module("apps.ml.training_runner.tasks")
        print("ok")
        """
    )
    result = subprocess.run(  # noqa: S603 — trình thông dịch của chính venv, mã cố định
        [sys.executable, "-c", script], cwd=REPO_ROOT, capture_output=True, text=True, check=False, timeout=120
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"
