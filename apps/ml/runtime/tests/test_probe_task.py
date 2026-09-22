"""J-case của khuôn task suy luận qua task thăm dò khai trong test (BE-00 §7 "Test task").

Worker Celery **thật** chỉ nghe `ml.infer`; `step_done` đi tới `pipeline.cpu` mà không
worker nào nghe, nên đọc lại được bằng `LRANGE` và đếm theo `run_id` riêng của test.
Kho là `local_storage` (J02 vá `infer_context` trả kho hỏng); Redis là container thật.
"""

import asyncio
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray
from pydantic import BaseModel

from apps.ml.runtime import tasks_util
from apps.ml.runtime.settings import MlSettings
from apps.ml.runtime.tasks_util import InferContext, StepOutput, run_step, step_failed
from apps.ml.runtime.tests.helpers import FailingReads, infer_payload, some_id
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.messaging.celery_app import producer_app, send_task
from packages.messaging.redis import SyncRedis, broker_redis_sync
from packages.messaging.tasks import RETRY_EXHAUSTED, define_task
from packages.ml_contracts.artifacts import ObjectsResult, WallsResult, encode_mask, objects_to_json, walls_to_json
from packages.ml_contracts.fakes import FakeObjectDetector, FakeWallSegmenter
from packages.ml_contracts.payloads import InferStepPayload, ModelRef
from packages.ml_contracts.pinned import PINNED
from packages.ml_contracts.synthetic import render_plan
from packages.storage.local import LocalDiskStorage
from packages.testing.fixtures.messaging import WorkerFactory, queued_payloads

TASK = "ml.infer.tests.probe_step"
LISTEN, OUTBOX = "ml.infer", "pipeline.cpu"
WAIT_S = 30.0
PLAN = render_plan(77)

type Send = Callable[[str, BaseModel], None]
SENDER: list[Send] = [send_task]


async def probe_prepare(payload: InferStepPayload) -> str:
    """Bộ chạy theo `ML_BACKEND`: task thăm dò chỉ có bộ giả."""
    return tasks_util.infer_context().settings.ml_backend


def probe_step(image: NDArray[np.uint8], payload: InferStepPayload, backend: str | None) -> StepOutput:
    """Bước thăm dò: tường hay ô mở của bộ giả, theo họ của payload."""
    assert backend == "fake"
    if payload.step == "wallSegmentation":
        mask = FakeWallSegmenter().segment(image)
        return StepOutput({"walls.png": encode_mask(mask), "walls.json": walls_to_json(WallsResult(walls=()))})
    detections = FakeObjectDetector().detect(image)
    return StepOutput({"objects.json": objects_to_json(ObjectsResult(detections=detections))})


@define_task(name=TASK, payload=InferStepPayload, on_failed=step_failed)
async def ml_runtime_probe_step(payload: InferStepPayload) -> None:
    """Đúng khuôn thân task của B5-02…B5-04."""
    storage = tasks_util.infer_context().storage
    await run_step(payload, probe_step, storage=storage, prepare=probe_prepare, send=SENDER[0])


@pytest.fixture
def broker(messaging_env: None) -> Iterator[SyncRedis]:
    client = broker_redis_sync()
    client.delete(LISTEN, OUTBOX)
    SENDER[0] = send_task
    yield client
    client.delete(LISTEN, OUTBOX)
    SENDER[0] = send_task
    client.close()


@pytest.fixture
def context(local_storage: LocalDiskStorage, monkeypatch: pytest.MonkeyPatch) -> LocalDiskStorage:
    settings = MlSettings(ml_backend="fake")
    monkeypatch.setattr(tasks_util, "infer_context", lambda: InferContext(storage=local_storage, settings=settings))
    return local_storage


def results(client: SyncRedis, run_id: str) -> list[dict[str, object]]:
    return [item for item in queued_payloads(client, OUTBOX) if item.get("run_id") == run_id]


def wait_for(predicate: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + WAIT_S
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError(f"quá {WAIT_S} giây mà chưa: {what}")


def stored(storage: LocalDiskStorage, key: str) -> bytes | None:
    """Nội dung object, đọc từ luồng không có vòng sự kiện."""

    async def read() -> bytes | None:
        if await storage.stat(key) is None:
            return None
        return b"".join([chunk async for chunk in storage.open_read(key)])

    return asyncio.run(read())


def with_page(storage: LocalDiskStorage, payload: InferStepPayload) -> InferStepPayload:
    asyncio.run(storage.put(payload.page_key, PLAN.image_png, content_type="image/png", max_bytes=len(PLAN.image_png)))
    return payload


def test_ml_runtime_probe_step__J01(
    broker: SyncRedis, context: LocalDiskStorage, celery_worker_factory: WorkerFactory
) -> None:
    """Chạy đúng: artifact đã nằm trong kho **trước** khi `step_done` được gửi."""
    payload = with_page(context, infer_payload())
    keys = [f"{payload.artifact_prefix}walls.json", f"{payload.artifact_prefix}walls.png"]
    seen_at_send: list[bool] = []

    def checking_send(name: str, result: BaseModel) -> None:
        seen_at_send.append(all(stored(context, key) is not None for key in keys))
        send_task(name, result)

    SENDER[0] = checking_send
    with celery_worker_factory([LISTEN]):
        send_task(TASK, payload)
        wait_for(lambda: bool(results(broker, payload.run_id)), "step_done")
    (result,) = results(broker, payload.run_id)
    assert seen_at_send == [True]
    assert result["status"] == "completed"
    assert result["artifact_keys"] == keys
    assert result["model_version_id"] is None
    assert result["step"] == "wallSegmentation"


def test_ml_runtime_probe_step__J01_fake_pinned(
    broker: SyncRedis, context: LocalDiskStorage, celery_worker_factory: WorkerFactory
) -> None:
    """`ML_BACKEND=fake` với model ghim: không nạp model nào, vẫn gửi đúng `version_id`."""
    pin = PINNED["yolov8n"]
    ref = ModelRef(
        version_id=some_id("mdl"),
        family="openingAndFurnitureDetection",
        weights_key=None,
        pinned_name="yolov8n",
        checksum_sha256=str(pin.onnx_sha256),
    )
    payload = with_page(context, infer_payload(step="openingAndFurnitureDetection", model_ref=ref))
    with celery_worker_factory([LISTEN]):
        send_task(TASK, payload)
        wait_for(lambda: bool(results(broker, payload.run_id)), "step_done")
    (result,) = results(broker, payload.run_id)
    assert (result["status"], result["model_version_id"]) == ("completed", ref.version_id)
    written = stored(context, f"{payload.artifact_prefix}objects.json")
    assert written == objects_to_json(ObjectsResult(detections=PLAN.detections))


def test_ml_runtime_probe_step__J02(
    broker: SyncRedis,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    celery_worker_factory: WorkerFactory,
) -> None:
    """Kho hỏng mãi: thử lại đủ bậc rồi `failed` `RETRY_EXHAUSTED`, đúng một thông điệp."""
    broken = FailingReads(tmp_path / "broken", DEPENDENCY_UNAVAILABLE.error(retry_after=5))
    settings = MlSettings(ml_backend="fake")
    monkeypatch.setattr(tasks_util, "infer_context", lambda: InferContext(storage=broken, settings=settings))
    payload = infer_payload()
    with celery_worker_factory([LISTEN]):
        send_task(TASK, payload)
        wait_for(lambda: bool(results(broker, payload.run_id)), "failed")
    (result,) = results(broker, payload.run_id)
    assert (result["status"], result["error_code"], result["artifact_keys"]) == ("failed", RETRY_EXHAUSTED, [])


def test_ml_runtime_probe_step__J02_broker(
    broker: SyncRedis, context: LocalDiskStorage, celery_worker_factory: WorkerFactory
) -> None:
    """Broker ném ở lượt gửi đầu: task thử lại, ghi đè cùng bytes, rồi gửi **đúng một** `step_done`."""
    attempts: list[int] = []

    def flaky_send(name: str, result: BaseModel) -> None:
        attempts.append(1)
        if len(attempts) == 1:
            raise DEPENDENCY_UNAVAILABLE.error(retry_after=5)
        send_task(name, result)

    SENDER[0] = flaky_send
    payload = with_page(context, infer_payload())
    with celery_worker_factory([LISTEN]):
        send_task(TASK, payload)
        wait_for(lambda: bool(results(broker, payload.run_id)), "step_done sau lượt thử lại")
    assert len(attempts) == 2
    assert [item["status"] for item in results(broker, payload.run_id)] == ["completed"]


def test_ml_runtime_probe_step__J03(
    broker: SyncRedis, context: LocalDiskStorage, celery_worker_factory: WorkerFactory
) -> None:
    """Lỗi vĩnh viễn (trang không còn): đúng một `failed` có mã, không artifact nào."""
    payload = infer_payload()
    with celery_worker_factory([LISTEN]):
        send_task(TASK, payload)
        wait_for(lambda: bool(results(broker, payload.run_id)), "failed")
    (result,) = results(broker, payload.run_id)
    assert (result["status"], result["error_code"]) == ("failed", "PIPELINE_ARTIFACT_MISSING")
    assert stored(context, f"{payload.artifact_prefix}walls.png") is None


def test_ml_runtime_probe_step__J06(
    broker: SyncRedis, context: LocalDiskStorage, celery_worker_factory: WorkerFactory
) -> None:
    """Giao lặp: cùng khoá, cùng nội dung, mỗi lượt một `step_done` giống nhau (trừ thời gian)."""
    payload = with_page(context, infer_payload())
    key = f"{payload.artifact_prefix}walls.png"
    with celery_worker_factory([LISTEN]):
        send_task(TASK, payload)
        wait_for(lambda: len(results(broker, payload.run_id)) == 1, "lượt giao đầu")
        first = stored(context, key)
        send_task(TASK, payload)
        wait_for(lambda: len(results(broker, payload.run_id)) == 2, "lượt giao lặp")
    assert stored(context, key) == first == encode_mask(PLAN.walls_mask)
    one, two = results(broker, payload.run_id)
    assert {k: v for k, v in one.items() if k != "duration_ms"} == {k: v for k, v in two.items() if k != "duration_ms"}


def test_ml_runtime_probe_step__J08(
    broker: SyncRedis, context: LocalDiskStorage, celery_worker_factory: WorkerFactory
) -> None:
    """Thông điệp độc: không chạy, không gửi; worker vẫn sống và làm tiếp thông điệp sau."""
    good = with_page(context, infer_payload())
    poison = {"schema_version": 1, "run_id": good.run_id, "step": "wallSegmentation"}
    with celery_worker_factory([LISTEN]):
        producer_app().send_task(TASK, args=[poison], queue=LISTEN)
        send_task(TASK, good)
        wait_for(lambda: bool(results(broker, good.run_id)), "thông điệp tốt sau thông điệp độc")
    assert [item["status"] for item in results(broker, good.run_id)] == ["completed"]
    assert broker.llen(LISTEN) == 0
