"""Hai route ghi N33, N35 (B6-03a [6], [8], [9]) — Postgres, Redis thật (K23).

C07 của cả sáu `op` nằm ở `test_contract.py` — không viết lại.
`cancel_key` đọc bằng client `safe_redis` thật: TTL là bằng chứng duy nhất cho luật
"lượt N35 lặp không gia hạn khoá" (K18), và không có cách giả nào được phép (K23).
"""

import asyncio
from collections.abc import Iterator
from contextlib import suppress

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.redis import RedisContainer

from apps.api.access.kinds import ActivityKind
from apps.api.admin_ml_jobs.errors import (
    DATASET_FAMILY_MISMATCH,
    DATASET_VERSION_NOT_READY,
    TRAINING_BASE_MODEL_MISMATCH,
    TRAINING_JOB_NOT_CANCELLABLE,
)
from apps.api.admin_ml_jobs.settings import get_training_settings
from apps.api.admin_ml_jobs.tests._helpers import (
    JOBS_PATH,
    MISSING_JOB_ID,
    OPENING,
    TRAINING_QUEUE,
    WALL,
    cancel_path,
)
from apps.api.core.auth import Principal
from packages.db.models.admin_ml_datasets import DatasetVersionRow
from packages.db.models.admin_ml_jobs import TrainingJobRow
from packages.messaging.payloads.training import cancel_key
from packages.messaging.redis import broker_redis_sync, safe_redis_sync
from packages.messaging.settings import reset_messaging_settings_cache
from packages.testing.factories.admin_ml_datasets import make_dataset, make_dataset_version
from packages.testing.factories.admin_ml_jobs import make_training_job
from packages.testing.factories.admin_ml_registry import make_model_version
from packages.testing.fixtures.access import assert_one_activity
from packages.testing.fixtures.api import auth_headers
from packages.testing.fixtures.messaging import queued_payloads
from packages.testing.fixtures.services import ephemeral_redis


async def _post(
    client: httpx.AsyncClient, principal: Principal, path: str, json: object, **headers: str
) -> httpx.Response:
    """POST có token admin; `headers` thêm `Idempotency-Key` khi test cần."""
    return await client.post(path, headers={**auth_headers(principal), **headers}, json=json)


async def _ready_version(db: AsyncSession, family: str, *, status: str = "ready") -> DatasetVersionRow:
    """Một bản dataset của họ `family` ở trạng thái `status`."""
    dataset = await make_dataset(db, family=family)
    return await make_dataset_version(db, dataset=dataset, status=status)


def _body(version_id: str, *, family: str = OPENING, base_model: str = "yolov8n", epochs: int = 3) -> dict[str, object]:
    """Thân N33 hợp lệ cho một bản dataset."""
    return {"family": family, "datasetVersionId": version_id, "baseModel": base_model, "epochs": epochs}


# ---------------------------------------------------------------------------
# N33 — ml_create_job
# ---------------------------------------------------------------------------


async def test_ml_create_job__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """202 `queued`, `creatorId` lấy từ token (K05), `id` tiền tố `job_`."""
    version = await _ready_version(db_session, OPENING)

    response = await _post(api_client, fake_principal, JOBS_PATH, _body(version.id))

    body = response.json()
    assert response.status_code == 202
    assert body["status"] == "queued"
    assert body["id"].startswith("job_")
    assert body["creatorId"] == fake_principal.user_id
    assert body["datasetVersionId"] == version.id
    assert body["epochs"] == 3


async def test_ml_create_job__C02(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """`family` lạ, `epochs` ngoài 1-300, `datasetVersionId` sai mẫu → 422 `VALIDATION` có `field`."""
    version = await _ready_version(db_session, OPENING)
    bad_family = await _post(api_client, fake_principal, JOBS_PATH, _body(version.id, family="walls"))
    bad_epochs = await _post(api_client, fake_principal, JOBS_PATH, _body(version.id, epochs=301))
    bad_id = await _post(api_client, fake_principal, JOBS_PATH, _body("dst_01KB6030000000000000000001"))

    for response, field in ((bad_family, "family"), (bad_epochs, "epochs"), (bad_id, "datasetVersionId")):
        assert response.status_code == 422
        assert response.json()["code"] == "VALIDATION"
        assert response.json()["field"] == field


async def test_ml_create_job__C03(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """Khoá lạ trong thân → 422 `VALIDATION`."""
    version = await _ready_version(db_session, OPENING)

    response = await _post(api_client, fake_principal, JOBS_PATH, {**_body(version.id), "creatorId": "usr_x"})

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"


async def test_ml_create_job__C17(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """Thân 202 của job `queued` vắng cả năm trường theo trạng thái (W2, K02)."""
    version = await _ready_version(db_session, OPENING)

    body = (await _post(api_client, fake_principal, JOBS_PATH, _body(version.id))).json()

    assert {"currentEpoch", "startedAt", "endedAt", "resultModelVersionId", "failureCode"}.isdisjoint(body)
    assert set(body) == {
        "baseModel",
        "createdAt",
        "creatorId",
        "datasetVersionId",
        "epochs",
        "family",
        "id",
        "status",
    }


async def test_ml_create_job__C18(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_principal: Principal,
) -> None:
    """Một dòng `activity_log` `training.create`, `objectLabel` là họ ([6])."""
    version = await _ready_version(db_session, WALL)

    response = await _post(api_client, fake_principal, JOBS_PATH, _body(version.id, family=WALL, base_model="mitB0"))

    activity = await assert_one_activity(
        db_sessionmaker,
        actor_id=fake_principal.user_id,
        kind=ActivityKind.TRAINING_CREATE,
        object_code=response.json()["id"],
    )
    assert activity.object_label == WALL


async def test_ml_create_job__version_not_ready(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """Bản `building` và bản `failed` → 422 `DATASET_VERSION_NOT_READY`."""
    building = await _ready_version(db_session, OPENING, status="building")
    failed = await _ready_version(db_session, OPENING, status="failed")

    for version in (building, failed):
        response = await _post(api_client, fake_principal, JOBS_PATH, _body(version.id))
        assert response.status_code == DATASET_VERSION_NOT_READY.status
        assert response.json()["code"] == DATASET_VERSION_NOT_READY.code


async def test_ml_create_job__family_mismatch(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """Dataset họ tường + job họ cửa/nội thất → 422 `DATASET_FAMILY_MISMATCH`."""
    version = await _ready_version(db_session, WALL)

    response = await _post(api_client, fake_principal, JOBS_PATH, _body(version.id, family=OPENING))

    assert response.status_code == DATASET_FAMILY_MISMATCH.status
    assert response.json()["code"] == DATASET_FAMILY_MISMATCH.code


async def test_ml_create_job__base_model_mismatch(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """`yolov8n` cho họ tường → 422 `TRAINING_BASE_MODEL_MISMATCH`, không `VALIDATION`."""
    version = await _ready_version(db_session, WALL)

    response = await _post(api_client, fake_principal, JOBS_PATH, _body(version.id, family=WALL))

    assert response.status_code == TRAINING_BASE_MODEL_MISMATCH.status
    assert response.json()["code"] == TRAINING_BASE_MODEL_MISMATCH.code


async def test_ml_create_job__missing_version(api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """Bản dataset không có → 404 `resource:"datasetVersion"` (không 422)."""
    response = await _post(api_client, fake_principal, JOBS_PATH, _body("dsv_01KB6030000000000000000404"))

    assert response.status_code == 404
    assert response.json()["resource"] == "datasetVersion"


async def test_ml_create_job__J09_rollback_leaves_no_message(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal, messaging_env: None
) -> None:
    """J09 — lượt hỏng (họ lệch) rollback: không dòng `training_jobs`, không thông điệp (K17)."""
    version = await _ready_version(db_session, WALL)
    broker = broker_redis_sync()
    broker.delete(TRAINING_QUEUE)
    try:
        response = await _post(api_client, fake_principal, JOBS_PATH, _body(version.id, family=OPENING))
        jobs = (await db_session.execute(select(func.count()).select_from(TrainingJobRow))).scalar_one()
        queued = broker.llen(TRAINING_QUEUE)
    finally:
        broker.delete(TRAINING_QUEUE)
        broker.close()

    assert response.status_code == DATASET_FAMILY_MISMATCH.status
    assert jobs == 0
    assert queued == 0


async def test_ml_create_job__C10_queue_once(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_principal: Principal,
    messaging_env: None,
) -> None:
    """Lặp cùng `Idempotency-Key`: cùng response, **một** job, **một** thông điệp, **một** dòng nhật ký."""
    version = await _ready_version(db_session, OPENING)
    broker = broker_redis_sync()
    broker.delete(TRAINING_QUEUE)
    headers = {"Idempotency-Key": "khoa-tao-job-mot-lan-01"}
    try:
        first = await _post(api_client, fake_principal, JOBS_PATH, _body(version.id), **headers)
        second = await _post(api_client, fake_principal, JOBS_PATH, _body(version.id), **headers)

        assert (first.status_code, second.status_code) == (202, 202)
        assert first.json() == second.json()
        jobs = (await db_session.execute(select(func.count()).select_from(TrainingJobRow))).scalar_one()
        payloads = queued_payloads(broker, TRAINING_QUEUE)
    finally:
        broker.delete(TRAINING_QUEUE)
        broker.close()

    assert jobs == 1
    assert len(payloads) == 1
    assert payloads[0]["job_id"] == first.json()["id"]
    assert payloads[0]["manifest_sha256"] == version.manifest_sha256
    await assert_one_activity(
        db_sessionmaker,
        actor_id=fake_principal.user_id,
        kind=ActivityKind.TRAINING_CREATE,
        object_code=first.json()["id"],
    )


# ---------------------------------------------------------------------------
# N35 — ml_cancel_job
# ---------------------------------------------------------------------------


async def test_ml_cancel_job__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal, messaging_env: None
) -> None:
    """`queued` → `cancelled` + `endedAt`; `running` → `cancelling`; cả hai đặt `cancel_key`."""
    version = await _ready_version(db_session, OPENING)
    queued = await make_training_job(db_session, dataset_version_id=version.id, family=OPENING)
    running = await make_training_job(db_session, dataset_version_id=version.id, family=OPENING, status="running")
    client = safe_redis_sync()
    try:
        first = await _post(api_client, fake_principal, cancel_path(queued.id), {})
        second = await _post(api_client, fake_principal, cancel_path(running.id), {})

        assert (first.status_code, second.status_code) == (200, 200)
        assert first.json()["status"] == "cancelled"
        assert first.json()["endedAt"] is not None
        assert second.json()["status"] == "cancelling"
        assert "endedAt" not in second.json()
        assert client.get(cancel_key(queued.id)) == "1"
        assert client.get(cancel_key(running.id)) == "1"
    finally:
        client.delete(cancel_key(queued.id), cancel_key(running.id))
        client.close()


async def test_ml_cancel_job__C02(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """Thân không phải object → 422 `VALIDATION` (thân N35 là `{}`)."""
    version = await _ready_version(db_session, OPENING)
    job = await make_training_job(db_session, dataset_version_id=version.id, family=OPENING)

    response = await _post(api_client, fake_principal, cancel_path(job.id), ["huy"])

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"


async def test_ml_cancel_job__C03(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """Khoá lạ trong thân → 422 `VALIDATION`; job không đổi trạng thái."""
    version = await _ready_version(db_session, OPENING)
    job = await make_training_job(db_session, dataset_version_id=version.id, family=OPENING)

    response = await _post(api_client, fake_principal, cancel_path(job.id), {"reason": "doi y"})

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"
    await db_session.refresh(job)
    assert job.status == "queued"


async def test_ml_cancel_job__C08(api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """Job không có **và** id sai mẫu đều 404 `resource:"trainingJob"`."""
    missing = await _post(api_client, fake_principal, cancel_path(MISSING_JOB_ID), {})
    malformed = await _post(api_client, fake_principal, cancel_path("khong-phai-id"), {})

    assert (missing.status_code, malformed.status_code) == (404, 404)
    for response in (missing, malformed):
        assert response.json()["resource"] == "trainingJob"


async def test_ml_cancel_job__C17(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal, messaging_env: None
) -> None:
    """Thân của job `cancelled` vắng `failureCode`, `resultModelVersionId`, `currentEpoch`."""
    version = await _ready_version(db_session, OPENING)
    job = await make_training_job(db_session, dataset_version_id=version.id, family=OPENING)
    client = safe_redis_sync()
    try:
        body = (await _post(api_client, fake_principal, cancel_path(job.id), {})).json()
    finally:
        client.delete(cancel_key(job.id))
        client.close()

    assert {"failureCode", "resultModelVersionId", "currentEpoch", "startedAt"}.isdisjoint(body)
    assert set(body) == {
        "baseModel",
        "createdAt",
        "creatorId",
        "datasetVersionId",
        "endedAt",
        "epochs",
        "family",
        "id",
        "status",
    }


async def test_ml_cancel_job__C18(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_principal: Principal,
    messaging_env: None,
) -> None:
    """Một dòng `activity_log` `training.cancel`, `objectLabel` là họ."""
    version = await _ready_version(db_session, WALL)
    job = await make_training_job(db_session, dataset_version_id=version.id, family=WALL, status="running")
    client = safe_redis_sync()
    try:
        await _post(api_client, fake_principal, cancel_path(job.id), {})
    finally:
        client.delete(cancel_key(job.id))
        client.close()

    activity = await assert_one_activity(
        db_sessionmaker, actor_id=fake_principal.user_id, kind=ActivityKind.TRAINING_CANCEL, object_code=job.id
    )
    assert activity.object_label == WALL


@pytest.mark.parametrize("status", ["cancelling", "cancelled"])
async def test_ml_cancel_job__no_effect(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal, status: str
) -> None:
    """`cancelling|cancelled` → 200 không tác dụng: không đổi trạng thái, không đặt khoá (K18)."""
    version = await _ready_version(db_session, OPENING)
    job = await make_training_job(db_session, dataset_version_id=version.id, family=OPENING, status=status)
    client = safe_redis_sync()
    client.delete(cancel_key(job.id))
    try:
        response = await _post(api_client, fake_principal, cancel_path(job.id), {})

        assert response.status_code == 200
        assert response.json()["status"] == status
        assert client.get(cancel_key(job.id)) is None
    finally:
        client.close()


@pytest.mark.parametrize("status", ["succeeded", "failed"])
async def test_ml_cancel_job__not_cancellable(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal, status: str
) -> None:
    """`succeeded|failed` → 409 `TRAINING_JOB_NOT_CANCELLABLE` (mã riêng để F-12 rẽ được)."""
    version = await _ready_version(db_session, OPENING)
    model = await make_model_version(db_session, family=OPENING, training=True) if status == "succeeded" else None
    job = await make_training_job(
        db_session,
        dataset_version_id=version.id,
        family=OPENING,
        status=status,
        result_model_version_id=model.id if model is not None else None,
    )

    response = await _post(api_client, fake_principal, cancel_path(job.id), {})

    assert response.status_code == TRAINING_JOB_NOT_CANCELLABLE.status
    assert response.json()["code"] == TRAINING_JOB_NOT_CANCELLABLE.code


async def test_ml_cancel_job__C10_once(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_principal: Principal,
    messaging_env: None,
) -> None:
    """Lặp N35: một dòng nhật ký và TTL `cancel_key` **không** được đặt lại (K18).

    TTL đọc trước/sau lượt lặp; lượt hai rơi vào nhánh "không tác dụng" nên nó không
    gọi `SET … EX` lần nữa, và TTL chỉ đi xuống theo thời gian thật.
    """
    version = await _ready_version(db_session, OPENING)
    job = await make_training_job(db_session, dataset_version_id=version.id, family=OPENING, status="running")
    client = safe_redis_sync()
    client.delete(cancel_key(job.id))
    try:
        first = await _post(api_client, fake_principal, cancel_path(job.id), {})
        ttl_before = client.ttl(cancel_key(job.id))
        second = await _post(api_client, fake_principal, cancel_path(job.id), {})
        ttl_after = client.ttl(cancel_key(job.id))
    finally:
        client.delete(cancel_key(job.id))
        client.close()

    assert (first.status_code, second.status_code) == (200, 200)
    assert second.json()["status"] == "cancelling"
    assert ttl_before <= get_training_settings().training_cancel_ttl_s
    assert ttl_after <= ttl_before
    await assert_one_activity(
        db_sessionmaker, actor_id=fake_principal.user_id, kind=ActivityKind.TRAINING_CANCEL, object_code=job.id
    )


async def test_ml_cancel_job__C14_concurrent(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_principal: Principal,
    messaging_env: None,
) -> None:
    """Hai N35 song song trên cùng job → cả hai 200, đúng **một** dòng nhật ký (`FOR UPDATE`)."""
    version = await _ready_version(db_session, OPENING)
    job = await make_training_job(db_session, dataset_version_id=version.id, family=OPENING, status="running")
    client = safe_redis_sync()
    client.delete(cancel_key(job.id))
    try:
        first, second = await asyncio.gather(
            _post(api_client, fake_principal, cancel_path(job.id), {}),
            _post(api_client, fake_principal, cancel_path(job.id), {}),
        )
    finally:
        client.delete(cancel_key(job.id))
        client.close()

    assert sorted([first.status_code, second.status_code]) == [200, 200]
    assert {first.json()["status"], second.json()["status"]} == {"cancelling"}
    await assert_one_activity(
        db_sessionmaker, actor_id=fake_principal.user_id, kind=ActivityKind.TRAINING_CANCEL, object_code=job.id
    )


async def test_ml_cancel_job__C13_redis_down(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    fake_principal: Principal,
    dead_redis: tuple[RedisContainer, str],
) -> None:
    """Redis dừng → 503 `DEPENDENCY_UNAVAILABLE`, rollback: job vẫn `running` ([6] N35)."""
    container, _shared_url = dead_redis
    version = await _ready_version(db_session, OPENING)
    job = await make_training_job(db_session, dataset_version_id=version.id, family=OPENING, status="running")

    container.stop()
    response = await _post(api_client, fake_principal, cancel_path(job.id), {})

    assert response.status_code == 503
    assert response.json()["code"] == "DEPENDENCY_UNAVAILABLE"
    await db_session.refresh(job)
    assert job.status == "running"


@pytest.fixture
def dead_redis(monkeypatch: pytest.MonkeyPatch, redis_broker_url: str) -> Iterator[tuple[RedisContainer, str]]:
    """Redis `noeviction` riêng đã trỏ `REDIS_BROKER_URL` vào; trả (container, URL dùng chung).

    Khuôn của `apps/api/notifications/tests/test_notify.py` — `service._arm_cancel_key` dựng
    client theo cài đặt hiện hành, nên dừng container này mới mô phỏng được Redis chết mà
    không chạm Redis dùng chung của cả lượt chạy (K23).
    """
    container = ephemeral_redis("noeviction")
    url = f"redis://{container.get_container_host_ip()}:{container.get_exposed_port(6379)}/0"
    monkeypatch.setenv("REDIS_BROKER_URL", url)
    reset_messaging_settings_cache()
    try:
        yield container, redis_broker_url
    finally:
        with suppress(Exception):  # test đã tự dừng container
            container.stop()
        reset_messaging_settings_cache()
