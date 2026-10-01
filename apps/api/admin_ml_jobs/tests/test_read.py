"""Hai route đọc N32, N34 (B6-03a [6], [8]); Postgres thật.

C07 của cả sáu `op` nằm ở `test_contract.py` — không viết lại.
`ml_read_job__C01` chia theo **sáu** trạng thái (hậu tố như `admin_ml_datasets`): mỗi
trạng thái là một bộ trường khác nhau trên dây, và CHECK của bảng là bản sao DB của
chính luật ấy — một test "C01" chung sẽ bỏ qua năm bộ.
"""

from datetime import timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.admin_ml_jobs.tests._helpers import DIMENSION, JOBS_PATH, MISSING_JOB_ID, OPENING, WALL, job_path
from apps.api.core.auth import Principal
from packages.db.models.admin_ml_datasets import DatasetVersionRow
from packages.testing.factories.admin_ml_datasets import make_dataset, make_dataset_version
from packages.testing.factories.admin_ml_jobs import make_training_job
from packages.testing.factories.admin_ml_registry import make_model_version
from packages.testing.fixtures.api import auth_headers
from packages.testing.fixtures.clock import FakeClock


async def _get(client: httpx.AsyncClient, principal: Principal, path: str, **params: str | int) -> httpx.Response:
    """GET có token admin và query đã lọc."""
    return await client.get(path, headers=auth_headers(principal), params=params)


async def _ready_version(db: AsyncSession, family: str) -> DatasetVersionRow:
    """Một bản dataset `ready` của họ `family` (job nào cũng cần một FK hợp lệ)."""
    dataset = await make_dataset(db, family=family)
    return await make_dataset_version(db, dataset=dataset, status="ready")


# ---------------------------------------------------------------------------
# N32 — ml_list_jobs
# ---------------------------------------------------------------------------


async def test_ml_list_jobs__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """200, mới nhất trước; `family` và `status` lọc độc lập và cộng dồn."""
    wall_version = await _ready_version(db_session, WALL)
    opening_version = await _ready_version(db_session, OPENING)
    wall = await make_training_job(db_session, dataset_version_id=wall_version.id, family=WALL)
    opening = await make_training_job(
        db_session, dataset_version_id=opening_version.id, family=OPENING, status="running"
    )

    by_family = await _get(api_client, fake_principal, JOBS_PATH, family=WALL)
    by_status = await _get(api_client, fake_principal, JOBS_PATH, status="running")
    both = await _get(api_client, fake_principal, JOBS_PATH, family=WALL, status="running")
    unfiltered = await _get(api_client, fake_principal, JOBS_PATH)

    assert by_family.status_code == 200
    assert [item["id"] for item in by_family.json()["items"]] == [wall.id]
    assert [item["id"] for item in by_status.json()["items"]] == [opening.id]
    assert both.json()["items"] == []
    assert {item["id"] for item in unfiltered.json()["items"]} == {wall.id, opening.id}


@pytest.mark.parametrize("query", [{"family": "walls"}, {"status": "pending"}, {"family": DIMENSION}])
async def test_ml_list_jobs__C02(
    api_client: httpx.AsyncClient, fake_principal: Principal, query: dict[str, str]
) -> None:
    """`family` ngoài hai họ huấn luyện được (kể cả họ thứ ba) và `status` lạ → 422 có `field`."""
    response = await _get(api_client, fake_principal, JOBS_PATH, **query)

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"
    assert response.json()["field"] in {"family", "status"}


async def test_ml_list_jobs__C15(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, fake_principal: Principal
) -> None:
    """0, 1, 5 job; `limit=3` → `nextCursor`, trang 2 đủ 2; `limit=201` vượt trần 200 → 422."""
    version = await _ready_version(db_session, WALL)
    empty = await _get(api_client, fake_principal, JOBS_PATH, family=WALL)
    assert empty.json() == {"items": []}

    jobs = [
        await make_training_job(
            db_session,
            dataset_version_id=version.id,
            family=WALL,
            created_at=fake_clock.now() + timedelta(minutes=minute),
        )
        for minute in range(5)
    ]
    one_page = await _get(api_client, fake_principal, JOBS_PATH, family=WALL, limit=1)
    assert [item["id"] for item in one_page.json()["items"]] == [jobs[-1].id]

    newest_first = [job.id for job in reversed(jobs)]
    first = await _get(api_client, fake_principal, JOBS_PATH, family=WALL, limit=3)
    second = await _get(
        api_client, fake_principal, JOBS_PATH, family=WALL, limit=3, cursor=first.json()["nextCursor"]
    )
    over_limit = await _get(api_client, fake_principal, JOBS_PATH, limit=201)

    assert [item["id"] for item in first.json()["items"]] == newest_first[:3]
    assert [item["id"] for item in second.json()["items"]] == newest_first[3:]
    assert "nextCursor" not in second.json()
    assert over_limit.status_code == 422


async def test_ml_list_jobs__C17(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """Job `queued`: vắng `currentEpoch`, `startedAt`, `endedAt`, `resultModelVersionId`, `failureCode` (K02)."""
    version = await _ready_version(db_session, WALL)
    job = await make_training_job(db_session, dataset_version_id=version.id, family=WALL)

    item = (await _get(api_client, fake_principal, JOBS_PATH, family=WALL)).json()["items"][0]

    assert item["id"] == job.id
    assert set(item) == {
        "baseModel",
        "createdAt",
        "creatorId",
        "datasetVersionId",
        "epochs",
        "family",
        "id",
        "status",
    }


async def test_ml_list_jobs_refuses_a_cursor_of_another_filter(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, fake_principal: Principal
) -> None:
    """Cursor mang dấu vết `(family, status)`: dùng cho bộ lọc khác → 422 `CURSOR_INVALID`."""
    version = await _ready_version(db_session, WALL)
    for minute in range(2):
        await make_training_job(
            db_session,
            dataset_version_id=version.id,
            family=WALL,
            created_at=fake_clock.now() + timedelta(minutes=minute),
        )

    page = await _get(api_client, fake_principal, JOBS_PATH, family=WALL, limit=1)
    reused = await _get(api_client, fake_principal, JOBS_PATH, cursor=page.json()["nextCursor"])

    assert reused.status_code == 422
    assert reused.json()["code"] == "CURSOR_INVALID"


# ---------------------------------------------------------------------------
# N34 — ml_read_job
# ---------------------------------------------------------------------------


async def test_ml_read_job__C01_queued(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """`queued`: đủ bảy trường bắt buộc, vắng cả năm trường theo trạng thái."""
    version = await _ready_version(db_session, OPENING)
    job = await make_training_job(db_session, dataset_version_id=version.id, family=OPENING, epochs=7)

    response = await _get(api_client, fake_principal, job_path(job.id))

    body = response.json()
    assert response.status_code == 200
    assert body["id"] == job.id
    assert body["status"] == "queued"
    assert body["epochs"] == 7
    assert body["baseModel"] == "yolov8n"
    assert body["datasetVersionId"] == version.id
    assert body["creatorId"] == job.creator_id
    assert {"startedAt", "endedAt", "currentEpoch", "resultModelVersionId", "failureCode"}.isdisjoint(body)


async def test_ml_read_job__C01_running(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """`running`: có `startedAt`, `currentEpoch`; vắng `endedAt`."""
    version = await _ready_version(db_session, OPENING)
    job = await make_training_job(
        db_session, dataset_version_id=version.id, family=OPENING, status="running", current_epoch=2
    )

    body = (await _get(api_client, fake_principal, job_path(job.id))).json()

    assert body["status"] == "running"
    assert body["currentEpoch"] == 2
    assert body["startedAt"] is not None
    assert "endedAt" not in body


async def test_ml_read_job__C01_cancelling(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """`cancelling`: có `startedAt`, chưa có `endedAt` (job vẫn đang dừng dở)."""
    version = await _ready_version(db_session, OPENING)
    job = await make_training_job(db_session, dataset_version_id=version.id, family=OPENING, status="cancelling")

    body = (await _get(api_client, fake_principal, job_path(job.id))).json()

    assert body["status"] == "cancelling"
    assert body["startedAt"] is not None
    assert "endedAt" not in body


async def test_ml_read_job__C01_cancelled(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """`cancelled`: có `endedAt`, vắng `failureCode` và `resultModelVersionId`."""
    version = await _ready_version(db_session, OPENING)
    job = await make_training_job(db_session, dataset_version_id=version.id, family=OPENING, status="cancelled")

    body = (await _get(api_client, fake_principal, job_path(job.id))).json()

    assert body["status"] == "cancelled"
    assert body["endedAt"] is not None
    assert {"failureCode", "resultModelVersionId"}.isdisjoint(body)


async def test_ml_read_job__C01_failed(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """`failed`: `failureCode` có mặt (hằng chuỗi của cầu nối), `resultModelVersionId` vắng."""
    version = await _ready_version(db_session, OPENING)
    job = await make_training_job(
        db_session,
        dataset_version_id=version.id,
        family=OPENING,
        status="failed",
        failure_code="TRAINING_METRICS_MISSING",
    )

    body = (await _get(api_client, fake_principal, job_path(job.id))).json()

    assert body["status"] == "failed"
    assert body["failureCode"] == "TRAINING_METRICS_MISSING"
    assert "resultModelVersionId" not in body


async def test_ml_read_job__C01_succeeded(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """`succeeded`: `resultModelVersionId` trỏ bản model có thật, `failureCode` vắng."""
    version = await _ready_version(db_session, OPENING)
    model = await make_model_version(db_session, family=OPENING, training=True)
    job = await make_training_job(
        db_session,
        dataset_version_id=version.id,
        family=OPENING,
        status="succeeded",
        result_model_version_id=model.id,
    )

    body = (await _get(api_client, fake_principal, job_path(job.id))).json()

    assert body["status"] == "succeeded"
    assert body["resultModelVersionId"] == model.id
    assert body["endedAt"] is not None
    assert "failureCode" not in body


async def test_ml_read_job__C08(api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """Job không có **và** id sai mẫu đều 404 `resource:"trainingJob"`."""
    missing = await _get(api_client, fake_principal, job_path(MISSING_JOB_ID))
    malformed = await _get(api_client, fake_principal, job_path("khong-phai-id"))

    assert (missing.status_code, malformed.status_code) == (404, 404)
    for response in (missing, malformed):
        assert response.json()["code"] == "NOT_FOUND"
        assert response.json()["resource"] == "trainingJob"


async def test_ml_read_job__C17(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """Năm trường tuỳ chọn của `queued` **vắng khoá**, không `null` (W2)."""
    version = await _ready_version(db_session, WALL)
    job = await make_training_job(db_session, dataset_version_id=version.id, family=WALL)

    body = (await _get(api_client, fake_principal, job_path(job.id))).json()

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
