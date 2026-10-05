"""Lượt huấn luyện trong tiến trình pytest: Redis thật, kho đĩa thật, trainer tí hon CPU.

`send` là hàm ghi vào list (tầng trên của `send_task`, đã kiểm ở `test_tasks.py`), `exit` là
hàm ghi mã — test **không bao giờ** gọi `os._exit` thật: nó giết lượt pytest và mất độ phủ.
Mỗi test tự đặt claim như launcher làm (`SET claim_key token`) và xoá khoá của job khi xong.
"""

import asyncio
import hashlib
import importlib
import json
import os
import pickle
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Final, cast

import pytest
from onnx import TensorProto, helper
from pydantic import BaseModel
from redis.exceptions import RedisError

from apps.ml.runtime.gpu import GpuSlot
from apps.ml.runtime.loader import ONNX_FIRST_BYTE
from apps.ml.runtime.tests.helpers import external_tensor
from apps.ml.training_runner import runner as runner_module
from apps.ml.training_runner.errors import (
    DATASET_MANIFEST_MISMATCH,
    DATASET_OBJECT_MISMATCH,
    DATASET_SPLIT_EMPTY,
    INTERNAL,
    MODEL_FORMAT_UNSUPPORTED,
    TRAINING_CANCELLED,
    TRAINING_DISK_FULL,
    TRAINING_GPU_BUSY,
    TRAINING_METRICS_MISSING,
    TRAINING_SLOT_BUSY,
    TRAINING_TIMEOUT,
    TRAINING_TRAINER_MISSING,
)
from apps.ml.training_runner.keys import (
    FINISHED_TASK,
    cancel_key,
    claim_key,
    new_token,
    sample_key,
    weights_key,
)
from apps.ml.training_runner.runner import job_seed, run_training_job
from apps.ml.training_runner.settings import TrainingRunnerSettings
from apps.ml.training_runner.tests import support
from apps.ml.training_runner.tests.support import (
    Dataset,
    TinyTrainer,
    put_bytes,
    tiny_onnx,
    train_payload,
)
from apps.ml.training_runner.watchdog import StopState, Watchdog
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.core.errors import AppError
from packages.messaging.tasks import PermanentError, TransientError
from packages.ml_contracts.families import MetricName
from packages.ml_contracts.payloads import TrainingLogPayload, TrainJobPayload
from packages.ml_contracts.ports import TrainResult, TrainSpec
from packages.storage.keys import dataset_object
from packages.storage.local import LocalDiskStorage
from packages.testing.fixtures.clock import FakeClock

MAX_WALL_S: Final = 600.0


@dataclass
class Harness:
    """Phụ thuộc tiêm được của một lượt và những gì lượt đã gửi ra ngoài."""

    payload: TrainJobPayload
    token: str
    trainer: Any
    storage: LocalDiskStorage
    clock: FakeClock
    sent: list[tuple[str, BaseModel]]
    exits: list[int]
    settings: TrainingRunnerSettings
    redis: Any

    def run(self, **overrides: Any) -> int:
        """Chạy lượt với phụ thuộc của harness; `overrides` thay một tham số (ví dụ `disk_usage`)."""
        kwargs: dict[str, Any] = {
            "claim_token": self.token,
            "trainers": lambda: {self.trainer.family: self.trainer},
            "storage": self.storage,
            "send": self.record,
            "redis": self.redis,
            "clock": self.clock,
            "settings": self.settings,
            "exit": self.exits.append,
        }
        return run_training_job(self.payload, **(kwargs | overrides))

    def record(self, task: str, payload: BaseModel) -> None:
        """`Send` của lượt: ghi `(tên task, payload)` thay vì nói với broker thật."""
        self.sent.append((task, payload))

    def finished(self) -> list[dict[str, Any]]:
        """Thân mọi thông điệp `finished` của job này, theo thứ tự gửi."""
        return [
            payload.model_dump()
            for task, payload in self.sent
            if task == FINISHED_TASK and getattr(payload, "job_id", None) == self.payload.job_id
        ]

    def logs(self) -> list[tuple[str, dict[str, Any]]]:
        """`(template, params)` mọi dòng log job đã gửi."""
        return [
            (payload.template, dict(payload.params))
            for _task, payload in self.sent
            if isinstance(payload, TrainingLogPayload)
        ]


def _settings(**overrides: Any) -> TrainingRunnerSettings:
    """Cài đặt nhỏ cho test: nhịp huỷ 0,05 s, grace 1 s, nhịp tim 60 s (không bắn trong lượt)."""
    values: dict[str, Any] = {
        "training_cancel_poll_s": 0.05,
        "training_stop_grace_s": 1,
        "training_heartbeat_s": 60,
        "training_max_wall_s": MAX_WALL_S,
        "training_claim_ttl_ms": 4_000,
    }
    return TrainingRunnerSettings(**(values | overrides))


def _dataset_key(version_id: str, name: str) -> str:
    """Khoá object dataset của test: `sample_key` cho đường mẫu nhiều đoạn, `dataset_object` cho manifest."""
    return sample_key(version_id, name) if "/" in name else dataset_object(version_id, name)


@pytest.fixture
def dataset(local_storage: LocalDiskStorage) -> Dataset:
    """Dataset thật (2 train, 1 validation) trên kho đĩa của test."""
    return asyncio.run(support.put_dataset(local_storage))


@pytest.fixture
def harness(
    dataset: Dataset,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    messaging_env: None,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Harness]:
    """Một lượt sẵn sàng: claim đã đặt như launcher, khoá của job được xoá khi test xong.

    Thư mục tạm riêng cho lượt (`tempfile.gettempdir`, như `test_purge_stale_tmp_removes_old_dirs`):
    sáu tiến trình xdist dùng chung `/tmp` của container, nên `_tmp_dirs()` quét thư mục chung sẽ
    thấy cả `training-*` của lượt đang sống ở tiến trình khác và đỏ ngẫu nhiên ([9] "song song").
    """
    from apps.ml.training_runner.redis_sync import training_redis

    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))

    client = training_redis()
    payload = train_payload(dataset, epochs=3)
    token = new_token()
    client.set(claim_key(payload.job_id), token)
    harness = Harness(
        payload=payload,
        token=token,
        trainer=TinyTrainer(),
        storage=local_storage,
        clock=fake_clock,
        sent=[],
        exits=[],
        settings=_settings(),
        redis=client,
    )
    try:
        yield harness
    finally:
        client.delete(claim_key(payload.job_id), cancel_key(payload.job_id))
        client.close()


def _busy_lock(harness: Harness) -> Callable[..., Any]:
    """Khoá luôn bận: mỗi lượt chờ nhả `TransientError` và đẩy `fake_clock` qua `wait_s`.

    Đồng hồ giả không tự chạy, nên nếu không đẩy thì vòng chờ của runner quay vô hạn: đúng
    cách một lượt chờ thật tiêu thời gian tường cho tới khi hết `training_max_wall_s`.
    """

    @contextmanager
    def busy(*, wait_s: float) -> Iterator[None]:
        """Không bao giờ giữ được khoá trong `wait_s` giây."""
        harness.clock.advance(timedelta(seconds=wait_s))
        raise TransientError(f"khoá bận sau {wait_s}s")
        yield  # `yield` chỉ để hàm thành generator cho `contextmanager`; không bao giờ tới

    return busy


def _canceller(harness: Harness) -> Callable[[], None]:
    """Móc `on_epoch` đặt `cancel_key` rồi ngủ quá một nhịp đọc huỷ (probe đọc Redis có throttle)."""

    def hook() -> None:
        """Đặt khoá huỷ của job rồi nhường một nhịp để `probe` được phép đọc Redis."""
        harness.redis.set(cancel_key(harness.payload.job_id), "1")
        time.sleep(harness.settings.training_cancel_poll_s * 2)

    return hook


def _tmp_dirs() -> list[Path]:
    """Thư mục `training-*` còn sót trong thư mục tạm của máy."""
    return [path for path in Path(tempfile.gettempdir()).glob("training-*") if path.is_dir()]


def _object_bytes(storage: LocalDiskStorage, key: str) -> bytes | None:
    """Byte của một object, hay `None` khi object không có (qua cổng kho, không đụng đĩa)."""

    async def read() -> bytes | None:
        """Đọc hết object nếu `stat` thấy nó."""
        if await storage.stat(key) is None:
            return None
        return b"".join([chunk async for chunk in storage.open_read(key)])

    return asyncio.run(read())


def test_start_training_runner__J04(harness: Harness) -> None:
    """Huỷ giữa epoch → `finished(cancelled)` cuối, thư mục tạm mất, không object trọng số."""
    before = set(_tmp_dirs())
    harness.trainer.on_epoch.append(_canceller(harness))
    assert harness.run() == 0
    assert [item["status"] for item in harness.finished()] == ["cancelled"]
    assert harness.sent[-1][0] == FINISHED_TASK
    assert ("training_cancelled", 1) in [
        (name, params["epoch"]) for name, params in harness.logs() if "epoch" in params
    ]
    assert set(_tmp_dirs()) <= before
    assert _object_bytes(harness.storage, weights_key(harness.payload.job_id, harness.token)) is None


def test_start_training_runner__J05(harness: Harness) -> None:
    """Đồng hồ giả vượt trần giờ giữa epoch → `finished(failed, TRAINING_TIMEOUT)`, tạm mất."""
    before = set(_tmp_dirs())
    harness.trainer.on_epoch.append(lambda: harness.clock.advance(timedelta(seconds=MAX_WALL_S + 1)))
    assert harness.run() == 0
    assert harness.finished() == [
        {
            "schema_version": 1,
            "job_id": harness.payload.job_id,
            "status": "failed",
            "weights_key": None,
            "checksum_sha256": None,
            "metrics": None,
            "error_code": TRAINING_TIMEOUT,
        }
    ]
    assert set(_tmp_dirs()) <= before


def test_run_training_job_success(harness: Harness) -> None:
    """Lượt thành công: object `weights-<token>.onnx` có, checksum khớp, `finished(succeeded)`."""
    assert harness.run() == 0
    (item,) = harness.finished()
    assert item["status"] == "succeeded"
    assert item["weights_key"] == weights_key(harness.payload.job_id, harness.token)
    assert item["metrics"] == {"iou": 0.5}
    data = _object_bytes(harness.storage, item["weights_key"])
    assert data is not None
    assert hashlib.sha256(data).hexdigest() == item["checksum_sha256"]
    assert harness.trainer.calls[0].epochs == 3


def test_run_training_job_split_empty(
    dataset: Dataset, local_storage: LocalDiskStorage, harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`validation` 0 mục → `DATASET_SPLIT_EMPTY` và khoá không bao giờ được chờ."""

    def forbidden(**_kwargs: Any) -> Any:
        """Khoá bị gọi là sai thứ tự bước 2/3 (dữ liệu hỏng không được giữ máy)."""
        raise AssertionError("không được chờ khoá khi dataset hỏng")

    monkeypatch.setattr(runner_module, "training_slot", forbidden)
    monkeypatch.setattr(runner_module, "gpu_slot", forbidden)
    empty = asyncio.run(support.put_dataset(local_storage, train=1, validation=0))
    harness.payload = train_payload(empty)
    harness.redis.set(claim_key(harness.payload.job_id), harness.token)
    assert harness.run() == 0
    assert harness.finished()[0]["error_code"] == DATASET_SPLIT_EMPTY


def test_run_training_job_claim_lost(harness: Harness) -> None:
    """Token khác ghi đè claim giữa lượt → không `put`, không `finished`, claim người khác còn."""
    other = new_token()

    def steal() -> None:
        """Lượt khác chiếm claim; chờ luồng gia hạn của lease thấy token lạ (TTL/4 = 1 s)."""
        harness.redis.set(claim_key(harness.payload.job_id), other)
        time.sleep(harness.settings.training_claim_ttl_ms / 1_000 / 2)

    harness.trainer.on_epoch.append(steal)
    assert harness.run() == 1
    assert harness.finished() == []
    assert _object_bytes(harness.storage, weights_key(harness.payload.job_id, harness.token)) is None
    assert harness.redis.get(claim_key(harness.payload.job_id)) == other


def test_run_training_job_watchdog(harness: Harness) -> None:
    """Trainer lì: luồng canh nổ sau grace → `exit(1)`, đúng một `finished(cancelled)`, tạm mất."""
    before = set(_tmp_dirs())
    harness.trainer = TinyTrainer(ignore_cancel=True, stall_s=3)
    harness.trainer.on_epoch.append(_canceller(harness))
    assert harness.run() == 1
    assert harness.exits == [1]
    assert [item["status"] for item in harness.finished()] == ["cancelled"]
    assert set(_tmp_dirs()) <= before


def test_run_training_job_disk_full(harness: Harness) -> None:
    """`disk_usage` giả đo **sau** khi giữ khoá → `TRAINING_DISK_FULL`, trainer không chạy."""
    seen: list[bool] = []

    @dataclass(frozen=True)
    class Usage:
        """Kết quả `disk_usage` giả: đĩa gần đầy."""

        total: int = 1_000
        used: int = 999
        free: int = 1

    def disk_usage(_path: Path) -> Usage:
        """Ghi lại rằng khoá đã giữ xong lúc đo (bước 4 đứng sau bước 3)."""
        seen.append(harness.redis.exists("training:slot") == 1)
        return Usage()

    assert harness.run(disk_usage=disk_usage) == 0
    assert seen == [True]
    assert harness.finished()[0]["error_code"] == TRAINING_DISK_FULL
    assert harness.trainer.calls == []


def test_run_training_job_seed(harness: Harness) -> None:
    """Cùng `job_id` hai lượt → cùng seed, đúng công thức 4 byte đầu SHA-256."""
    assert harness.run() == 0
    assert harness.run() == 0
    expected = int.from_bytes(hashlib.sha256(harness.payload.job_id.encode()).digest()[:4], "big")
    assert [call.seed for call in harness.trainer.calls] == [expected, expected]
    assert job_seed(harness.payload.job_id) == expected


def test_run_training_job_m02(harness: Harness, dataset: Dataset) -> None:
    """Mẫu bị ghi lại lệch một byte → `DATASET_OBJECT_MISMATCH` (băm khi tải, M02)."""
    sample = dataset.entries[0]
    key = _dataset_key(dataset.version_id, sample.path)
    original = _object_bytes(harness.storage, key) or b""
    asyncio.run(put_bytes(harness.storage, key, bytes([original[0] ^ 0xFF]) + original[1:]))
    assert harness.run() == 0
    assert harness.finished()[0]["error_code"] == DATASET_OBJECT_MISMATCH
    assert harness.trainer.calls == []


def test_run_training_job_manifest_mismatch(harness: Harness) -> None:
    """Manifest bị ghi lại khác nội dung đã băm → `DATASET_MANIFEST_MISMATCH`, không chạy trainer."""
    asyncio.run(put_bytes(harness.storage, _dataset_key(harness.payload.dataset_version_id, "manifest.jsonl"), b"x\n"))
    assert harness.run() == 0
    assert harness.finished()[0]["error_code"] == DATASET_MANIFEST_MISMATCH
    assert harness.trainer.calls == []


def test_run_training_job_m03(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """`.pt` pickle và ONNX có tensor ngoài → `MODEL_FORMAT_UNSUPPORTED`, không `put`."""

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        """Runner không bao giờ được giải pickle của trainer (K12)."""
        raise AssertionError("runner không được pickle")

    monkeypatch.setattr(pickle, "load", forbidden)
    monkeypatch.setattr(pickle, "loads", forbidden)
    harness.trainer = _WeightsTrainer(b"\x80\x04\x95payload")
    assert harness.run() == 0
    assert harness.finished()[0]["error_code"] == MODEL_FORMAT_UNSUPPORTED
    harness.sent.clear()
    harness.trainer = _WeightsTrainer(_external_onnx())
    assert harness.run() == 0
    assert harness.finished()[0]["error_code"] == MODEL_FORMAT_UNSUPPORTED
    assert _object_bytes(harness.storage, weights_key(harness.payload.job_id, harness.token)) is None


def test_run_training_job_trainer_missing(harness: Harness) -> None:
    """Họ của payload không có trainer → `TRAINING_TRAINER_MISSING`."""
    assert harness.run(trainers=dict) == 0
    assert harness.finished()[0]["error_code"] == TRAINING_TRAINER_MISSING


def test_run_training_job_maps_a_trainer_claimed_cancel_to_internal(harness: Harness) -> None:
    """Trainer ném `PermanentError(TRAINING_CANCELLED)` mà lượt chưa huỷ → `finished(failed, INTERNAL)`.

    `TRAINING_CANCELLED` là lý do dừng, [2] ghi nó **không bao giờ** lên dây: trainer báo huỷ khi
    runner không huỷ là trainer sai, nên mã gửi đi phải là `INTERNAL`.
    """

    def claim_cancelled() -> None:
        """Móc cuối epoch: trainer tự nhận "đã huỷ" dù `cancel_key` chưa bao giờ được đặt."""
        raise PermanentError(TRAINING_CANCELLED)

    harness.trainer.on_epoch.append(claim_cancelled)
    assert harness.run() == 0
    assert [item["error_code"] for item in harness.finished()] == [INTERNAL]
    assert ("training_failed", INTERNAL) in [(name, params.get("code")) for name, params in harness.logs()]
    assert _object_bytes(harness.storage, weights_key(harness.payload.job_id, harness.token)) is None


def test_run_training_job_lets_the_stop_reason_beat_a_trainer_error(harness: Harness) -> None:
    """Đã có lý do dừng rồi trainer mới ném `PermanentError` → kết quả theo **lý do dừng**, không theo mã ấy.

    Trainer thấy huỷ nhưng ném sai lớp lỗi (`PermanentError` thay `TrainingStopped`): lượt vẫn phải
    báo `cancelled`, vì lý do dừng quyết kết quả chứ không phải cách `train` kết thúc (BE-00 §9).
    """
    harness.trainer.on_epoch.append(_canceller(harness))
    harness.trainer.on_epoch.append(lambda: (_ for _ in ()).throw(PermanentError(TRAINING_METRICS_MISSING)))
    assert harness.run() == 0
    assert [item["status"] for item in harness.finished()] == ["cancelled"]
    assert [item.get("error_code") for item in harness.finished()] == [None]


def test_run_training_job_metrics_missing(harness: Harness) -> None:
    """Trainer trả số đo của họ khác → `TRAINING_METRICS_MISSING`, không `put`."""
    harness.trainer = _WeightsTrainer(tiny_onnx(), metrics={"map50": 0.5})
    assert harness.run() == 0
    assert harness.finished()[0]["error_code"] == TRAINING_METRICS_MISSING
    assert _object_bytes(harness.storage, weights_key(harness.payload.job_id, harness.token)) is None


def test_run_training_job_cancel_before_download(harness: Harness) -> None:
    """`cancel_key` có trước lượt → `finished(cancelled)`, không tải, không trainer."""
    harness.redis.set(cancel_key(harness.payload.job_id), "1")
    assert harness.run() == 0
    assert [item["status"] for item in harness.finished()] == ["cancelled"]
    assert harness.trainer.calls == []


def test_run_training_job_finish_unsent(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """`finish` trả `False` (broker chết) → trả 1 và object trọng số **vẫn còn** (không xoá)."""
    from apps.ml.training_runner import reporter as reporter_module

    def never(_task: str, _payload: BaseModel) -> None:
        """Mọi lần gửi đều hỏng bằng lỗi phụ thuộc — đúng lớp lỗi reporter thử lại rồi bỏ."""
        raise AppError(DEPENDENCY_UNAVAILABLE, retry_after=1)

    monkeypatch.setattr(reporter_module, "_FINISH_RETRIES", 0)
    assert harness.run(send=never) == 1
    assert _object_bytes(harness.storage, weights_key(harness.payload.job_id, harness.token)) is not None


def test_stop_state_first_reason_wins() -> None:
    """`StopState.request` đầu tiên chốt lý do; lần sau không đổi được."""
    stop = StopState()
    assert stop.reason is None
    stop.request("A")
    stop.request("B")
    assert stop.reason == "A"


def test_watchdog_does_not_fire_when_train_returns() -> None:
    """`train_returned()` trước khi hết grace → `on_expire` không bao giờ chạy."""
    stop = StopState()
    fired: list[str] = []
    watchdog = Watchdog(stop, grace_s=0.05, poll_s=0.01, probe=lambda: stop.request("A"), on_expire=fired.append)
    watchdog.start()
    watchdog.train_returned()
    watchdog.stop()
    assert fired == []


def test_watchdog_fires_once_after_grace() -> None:
    """Có lý do mà `train` không trả sau grace → `on_expire(reason)` đúng một lần."""
    stop = StopState()
    fired: list[str] = []
    done = threading.Event()

    def on_expire(reason: str) -> None:
        """Ghi lý do và báo test đi tiếp."""
        fired.append(reason)
        done.set()

    watchdog = Watchdog(stop, grace_s=0.0, poll_s=0.01, probe=lambda: stop.request("A"), on_expire=on_expire)
    watchdog.start()
    assert done.wait(5)
    watchdog.stop()
    assert fired == ["A"]
    assert watchdog.expired


@dataclass
class _WeightsTrainer:
    """Trainer ghi đúng byte test muốn vào `out_dir/model.onnx` (kiểm bước 8)."""

    data: bytes
    metrics: Mapping[MetricName, float] | None = None
    family: str = "wallSegmentation"
    calls: list[TrainSpec] = None  # type: ignore[assignment]  # khởi tạo trong __post_init__

    def __post_init__(self) -> None:
        """List `calls` riêng cho mỗi trainer (dataclass không chia sẻ mặc định biến đổi)."""
        self.calls = []

    def train(self, spec: TrainSpec, _data_dir: Path, out_dir: Path, _reporter: Any) -> TrainResult:
        """Ghi byte đã cho; không epoch, không hỏi huỷ (chỉ kiểm hậu xử lý)."""
        self.calls.append(spec)
        path = out_dir / "model.onnx"
        path.write_bytes(self.data)
        return TrainResult(onnx_path=path, metrics=self.metrics or {"iou": 0.5})


def _external_onnx() -> bytes:
    """ONNX hợp lệ về cú pháp nhưng có tensor trỏ dữ liệu ra ngoài (M03)."""
    graph = helper.make_graph(
        [helper.make_node("Identity", ["x"], ["y"])],
        "ext",
        [helper.make_tensor_value_info("x", TensorProto.FLOAT, [1])],
        [helper.make_tensor_value_info("y", TensorProto.FLOAT, [1])],
        initializer=[external_tensor("w")],
    )
    model = helper.make_model(graph, ir_version=10, opset_imports=[helper.make_opsetid("", 17)])
    return bytes(model.SerializeToString())


def _main_run(payload: TrainJobPayload, token: str, env: dict[str, str]) -> tuple[int, str]:
    """Chạy `python -m apps.ml.training_runner` thật với stdin hợp đồng; trả (mã thoát, stderr)."""
    request = json.dumps({"claim_token": token, "payload": payload.model_dump(mode="json")})
    completed = subprocess.run(
        [sys.executable, "-m", "apps.ml.training_runner"],
        input=request.encode(),
        capture_output=True,
        env=env,
        check=False,
        timeout=110,
    )
    return completed.returncode, completed.stderr.decode("utf-8", "replace")


def test_main_rejects_broken_stdin() -> None:
    """stdin không phải JSON hợp đồng → `main()` log và thoát 1 (handler cuối)."""
    env = dict(os.environ) | {"APP_ENV": "test"}
    completed = subprocess.run(
        [sys.executable, "-m", "apps.ml.training_runner"],
        input=b"{",
        capture_output=True,
        env=env,
        check=False,
        timeout=110,
    )
    assert completed.returncode == 1


def test_main_runs_override_trainer(harness: Harness, tmp_path: Path) -> None:
    """Tiến trình con thật + `TRAINING_TRAINER_OVERRIDE` (`APP_ENV=test`) → thoát 0."""
    storage_root = tmp_path / "objects"
    env = dict(os.environ) | {
        "APP_ENV": "test",
        "ML_DEVICE": "cpu",
        "STORAGE_BACKEND": "local",
        "STORAGE_LOCAL_ROOT": str(storage_root),
        "TRAINING_TRAINER_OVERRIDE": "apps.ml.training_runner.tests.support:TRAINER",
        "TRAINING_MAX_WALL_S": str(MAX_WALL_S),
    }
    harness.payload = train_payload(Dataset(harness.payload.dataset_version_id, harness.payload.manifest_sha256, 0, ()))
    harness.redis.set(claim_key(harness.payload.job_id), harness.token)
    code, stderr = _main_run(harness.payload, harness.token, env)
    assert code == 0, stderr


def test_purge_stale_tmp_removes_old_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Thư mục `training-*` cũ hơn trần giờ bị xoá; thư mục mới và tệp lạ thì không."""
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    old = tmp_path / "training-old"
    old.mkdir()
    os.utime(old, (0, 0))
    fresh = tmp_path / "training-fresh"
    fresh.mkdir()
    stray = tmp_path / "training-file"
    stray.write_bytes(b"x")
    runner_module.purge_stale_tmp(60)
    assert not old.exists()
    assert fresh.is_dir()
    assert stray.is_file()


def test_cancel_probe_survives_redis_error() -> None:
    """Redis hỏng lúc đọc `cancel_key` → coi như không huỷ (lượt không bị giết vì hạ tầng)."""

    class Broken:
        """Client ném `RedisError` ở mọi lệnh."""

        def exists(self, _key: str) -> int:
            """Luôn hỏng như Redis mất kết nối."""
            raise RedisError("mất kết nối")

    assert runner_module._cancel_requested(cast("Any", Broken()), "job_01J0000000000000000000000A") is False


def test_validated_weights_rejects_bad_models(tmp_path: Path) -> None:
    """Ngoài `out_dir`, quá trần, byte đầu lạ và protobuf hỏng đều → `MODEL_FORMAT_UNSUPPORTED`."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    outside = tmp_path / "model.onnx"
    outside.write_bytes(tiny_onnx())
    inside = out_dir / "model.onnx"
    inside.write_bytes(tiny_onnx())
    garbage = out_dir / "garbage.onnx"
    garbage.write_bytes(bytes([ONNX_FIRST_BYTE]) + b"\xff" * 8)
    for path, max_bytes in ((outside, 1 << 20), (inside, 4), (garbage, 1 << 20)):
        with pytest.raises(PermanentError, match=MODEL_FORMAT_UNSUPPORTED):
            runner_module._validated_weights(path, out_dir, max_bytes)
    assert runner_module._validated_weights(inside, out_dir, 1 << 20) == tiny_onnx()


def test_run_training_job_slot_busy(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """Khoá `training:slot` bận tới hết trần giờ → `TRAINING_SLOT_BUSY`, có log `training_gpu_waiting`."""

    monkeypatch.setattr(runner_module, "training_slot", _busy_lock(harness))
    harness.settings = _settings(training_max_wall_s=0.2)
    assert harness.run() == 0
    assert harness.finished()[0]["error_code"] == TRAINING_SLOT_BUSY
    assert "training_gpu_waiting" in [name for name, _params in harness.logs()]


def test_run_training_job_cuda_holds_gpu(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """`cuda` giữ thêm `gpu:0` trước khi gọi trainer; `cpu` không bao giờ gọi `gpu_slot`."""
    held: list[str] = []

    @contextmanager
    def fake_gpu(*, wait_s: float) -> Iterator[GpuSlot]:
        """Khoá GPU giả: ghi lại là đã giữ, không chạm Redis."""
        held.append(f"gpu:{wait_s}")
        yield GpuSlot(token=1, lost=threading.Event())

    monkeypatch.setattr(runner_module, "resolve_device", lambda _setting: "cuda")
    monkeypatch.setattr(runner_module, "gpu_slot", fake_gpu)
    assert harness.run() == 0
    assert harness.finished()[0]["status"] == "succeeded"
    assert len(held) == 1
    assert harness.trainer.calls[0].device == "cuda"


def test_run_training_job_gpu_busy(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """`cuda` mà `gpu:0` bận tới hết trần giờ → `TRAINING_GPU_BUSY`."""

    monkeypatch.setattr(runner_module, "resolve_device", lambda _setting: "cuda")
    monkeypatch.setattr(runner_module, "gpu_slot", _busy_lock(harness))
    harness.settings = _settings(training_max_wall_s=0.2)
    assert harness.run() == 0
    assert harness.finished()[0]["error_code"] == TRAINING_GPU_BUSY


def test_run_training_job_claim_renew_refused(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """Gia hạn claim trước `put` trả `False` → không `put`, không `finished`, trả 1."""
    monkeypatch.setattr(runner_module, "renew_if_owner", lambda *_args: False)
    assert harness.run() == 1
    assert harness.finished() == []
    assert _object_bytes(harness.storage, weights_key(harness.payload.job_id, harness.token)) is None


def test_run_training_job_watchdog_timeout(harness: Harness) -> None:
    """Trainer lì + quá trần giờ → luồng canh gửi `finished(failed, TRAINING_TIMEOUT)` rồi `exit(1)`."""
    harness.trainer = TinyTrainer(ignore_cancel=True, stall_s=3)
    harness.trainer.on_epoch.append(lambda: harness.clock.advance(timedelta(seconds=MAX_WALL_S + 1)))
    assert harness.run() == 1
    assert harness.exits == [1]
    assert [item["error_code"] for item in harness.finished()] == [TRAINING_TIMEOUT]


def test_main_ignores_override_outside_test_env(harness: Harness, tmp_path: Path) -> None:
    """`TRAINING_TRAINER_OVERRIDE` ngoài `APP_ENV=test` bị bỏ qua → `discover_trainers` không có họ ấy.

    Lượt vẫn chạy tới `finished(failed, TRAINING_TRAINER_MISSING)`: bỏ qua override là quyết định
    bảo mật ([5]), không phải lỗi hạ tầng, nên tiến trình con thoát 0 sau khi báo cho cầu nối.
    """
    env = dict(os.environ) | {
        "APP_ENV": "dev",
        "ML_DEVICE": "cpu",
        "STORAGE_BACKEND": "local",
        "STORAGE_LOCAL_ROOT": str(tmp_path / "objects"),
        "TRAINING_TRAINER_OVERRIDE": "apps.ml.training_runner.tests.support:TRAINER",
    }
    code, stderr = _main_run(harness.payload, harness.token, env)
    assert code == 0, stderr
    # Dòng phân biệt "override bị bỏ qua" với "override được nạp": nếu `_trainers` nạp `TRAINER` của
    # test thì lượt sẽ chạy xong và không có dòng này (không như `test_main_runs_override_trainer`).
    assert "training_trainer_override_ignored" in stderr
    assert _object_bytes(harness.storage, weights_key(harness.payload.job_id, harness.token)) is None


def test_main_crash_log_masks_secret_values() -> None:
    """Crash của `main()` đi qua logger đã che: loại ngoại lệ + mã lỗi còn, giá trị bí mật trong thông điệp
    ngoại lệ (ở đây `ValidationError` lặp lại đầu vào) không lộ ra stderr (FIX-345)."""
    request = {"claim_token": "t", "payload": {"job_id": "S3_SECRET_KEY=abcW10leak password=xyzW10leak"}}
    completed = subprocess.run(
        [sys.executable, "-m", "apps.ml.training_runner"],
        input=json.dumps(request).encode(),
        capture_output=True,
        env=dict(os.environ) | {"APP_ENV": "test"},
        check=False,
        timeout=110,
    )
    stderr = completed.stderr.decode("utf-8", "replace")
    assert completed.returncode == 1
    assert "abcW10leak" not in stderr
    assert "xyzW10leak" not in stderr
    record = json.loads(next(line for line in stderr.splitlines() if "training_runner_crashed" in line))
    assert record["excType"] == "ValidationError"
    assert record["code"] == INTERNAL


def test_report_internal_logs_when_broker_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """`_report_internal`: job chưa biết id thì im; broker hỏng thì log chứ không ném."""
    from apps.ml.training_runner import __main__ as main_module

    sent: list[str] = []

    def broken(task: str, _payload: BaseModel) -> None:
        """Broker hỏng đúng lớp lỗi `send_task` dùng."""
        sent.append(task)
        raise AppError(DEPENDENCY_UNAVAILABLE, retry_after=1)

    monkeypatch.setattr(main_module, "send_task", broken)
    main_module._report_internal("")
    assert sent == []
    main_module._report_internal("job_01J0000000000000000000000A")
    assert sent == [FINISHED_TASK]


def test_main_trainers_honours_app_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """`_trainers`: không override → `discover_trainers`; override chỉ nạp khi `APP_ENV=test`."""
    from apps.ml.runtime.trainers import discover_trainers
    from apps.ml.training_runner import __main__ as main_module

    monkeypatch.setenv("APP_ENV", "test")
    assert main_module._trainers(_settings()) is discover_trainers
    override = _settings(training_trainer_override="apps.ml.training_runner.tests.support:TRAINER")
    # Test khác có thể xoá `apps.ml.*` khỏi `sys.modules` (NO-310): `support` nhập ở đầu file và bản
    # `_trainers` vừa nạp là hai lớp khác nhau, nên lấy đích ngay lúc này và so danh tính.
    expected = importlib.import_module("apps.ml.training_runner.tests.support").TRAINER
    loaded = main_module._trainers(override)()
    assert list(loaded) == [expected.family]
    assert loaded[expected.family] is expected
    monkeypatch.setenv("APP_ENV", "dev")
    assert main_module._trainers(override) is discover_trainers
