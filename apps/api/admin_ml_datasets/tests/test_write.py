"""Hai route ghi N29, N31 (B6-02 [6], [8], [9]) — Postgres, Redis thật (K23).

C07 của cả bốn `op` nằm ở `test_contract.py` — không viết lại.
"""

import asyncio
import unicodedata

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.access.kinds import ActivityKind
from apps.api.admin_ml_datasets.errors import DATASET_BUILD_IN_PROGRESS, DATASET_NAME_TAKEN
from apps.api.admin_ml_datasets.settings import reset_ml_datasets_settings_cache
from apps.api.admin_ml_datasets.tests._helpers import DATASET_QUEUE, DATASETS_PATH, OPENING, WALL, versions_path
from apps.api.core.auth import Principal
from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.db.models.admin_ml_datasets import DatasetVersionRow
from packages.db.models.projects import Project
from packages.messaging.redis import broker_redis_sync
from packages.testing.factories.admin_ml_datasets import make_dataset, make_dataset_version
from packages.testing.fixtures.access import assert_one_activity
from packages.testing.fixtures.api import auth_headers
from packages.testing.fixtures.messaging import queued_payloads


async def _post(
    client: httpx.AsyncClient, principal: Principal, path: str, json: object, **headers: str
) -> httpx.Response:
    """POST `json` bằng header của `principal` cộng `headers`."""
    return await client.post(path, headers={**auth_headers(principal), **headers}, json=json)


async def _make_projects(db: AsyncSession, n: int) -> list[str]:
    """`n` dự án vừa tạo, chưa xoá mềm."""
    clock = SystemClock()
    rows = [Project(id=new_id("prj", clock), name=f"p{i}", created_by="usr_test") for i in range(n)]
    db.add_all(rows)
    await db.commit()
    return sorted(row.id for row in rows)


# ---------------------------------------------------------------------------
# N29 — ml_create_dataset
# ---------------------------------------------------------------------------


async def test_ml_create_dataset__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """C01: tạo dataset trả 201 và đúng bốn khoá."""
    response = await _post(api_client, fake_principal, DATASETS_PATH, {"name": "bo du lieu 1", "family": WALL})

    body = response.json()
    assert response.status_code == 201
    assert set(body) == {"createdAt", "family", "id", "name"}
    assert body["name"] == "bo du lieu 1"
    assert body["family"] == WALL
    assert body["id"].startswith("dst_")


async def test_ml_create_dataset__C02_name_bounds(api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """`name` rỗng, hay 81 ký tự → 422 `field:"name"`."""
    empty = await _post(api_client, fake_principal, DATASETS_PATH, {"name": "", "family": WALL})
    too_long = await _post(api_client, fake_principal, DATASETS_PATH, {"name": "x" * 81, "family": WALL})

    assert empty.status_code == 422
    assert empty.json()["field"] == "name"
    assert too_long.status_code == 422
    assert too_long.json()["field"] == "name"


async def test_ml_create_dataset__C02_family(api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """C02: họ lạ bị 422 ở trường `family`."""
    response = await _post(api_client, fake_principal, DATASETS_PATH, {"name": "x", "family": "walls"})

    assert response.status_code == 422
    assert response.json()["field"] == "family"


async def test_ml_create_dataset__C03(api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """Khoá lạ → 422 `VALIDATION`."""
    response = await _post(
        api_client, fake_principal, DATASETS_PATH, {"name": "x", "family": WALL, "createdBy": "usr_x"}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"


async def test_ml_create_dataset__C16_nfc(api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """`name` NFD vào → NFC ra, khoảng trắng hai đầu không tính."""
    nfd_name = unicodedata.normalize("NFD", "bo du lieu a")
    response = await _post(api_client, fake_principal, DATASETS_PATH, {"name": f"  {nfd_name}  ", "family": WALL})

    assert response.json()["name"] == unicodedata.normalize("NFC", nfd_name)


async def test_ml_create_dataset__name_taken(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """Tên đã dùng, không phân biệt hoa thường → 409 `DATASET_NAME_TAKEN`."""
    await make_dataset(db_session, family=WALL, name="Ten Bo")

    response = await _post(api_client, fake_principal, DATASETS_PATH, {"name": "ten bo", "family": OPENING})

    assert response.status_code == DATASET_NAME_TAKEN.status
    assert response.json()["code"] == DATASET_NAME_TAKEN.code


async def test_ml_create_dataset__C14_concurrent_same_name(
    api_client: httpx.AsyncClient, fake_principal: Principal
) -> None:
    """Hai N29 song song cùng tên khác hoa thường → một 201, một 409 (một dòng `datasets`)."""
    first, second = await asyncio.gather(
        _post(api_client, fake_principal, DATASETS_PATH, {"name": "Trung Lap", "family": WALL}),
        _post(api_client, fake_principal, DATASETS_PATH, {"name": "trung lap", "family": WALL}),
    )

    statuses = sorted([first.status_code, second.status_code])
    assert statuses == [201, 409]


async def test_ml_create_dataset__C18(
    api_client: httpx.AsyncClient, db_sessionmaker: async_sessionmaker[AsyncSession], fake_principal: Principal
) -> None:
    """C18: tạo dataset ghi đúng một dòng hoạt động."""
    response = await _post(api_client, fake_principal, DATASETS_PATH, {"name": "bo du lieu hoat dong", "family": WALL})

    activity = await assert_one_activity(
        db_sessionmaker,
        actor_id=fake_principal.user_id,
        kind=ActivityKind.DATASET_CREATE,
        object_code=response.json()["id"],
    )
    assert activity.object_label == "bo du lieu hoat dong"


# ---------------------------------------------------------------------------
# N31 — ml_build_dataset_version
# ---------------------------------------------------------------------------


async def test_ml_build_dataset_version__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """202, `building`; N31 lần hai (sau khi bản 1 `ready`) → `sequence 2`, bản 1 giữ manifest."""
    dataset = await make_dataset(db_session, family=WALL)
    first_version = await make_dataset_version(db_session, dataset=dataset, status="ready", sequence=1)

    response = await _post(api_client, fake_principal, versions_path(dataset.id), {})

    body = response.json()
    assert response.status_code == 202
    assert body["status"] == "building"
    assert body["sequence"] == 2

    await db_session.refresh(first_version)
    assert first_version.status == "ready"
    assert first_version.manifest_sha256 is not None


async def test_ml_build_dataset_version__C17(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """Thân 202 của bản `building` **vắng** `manifestSha256`, `splitCounts`, `failureCode` (W2, K02).

    Và vắng luôn cột nội bộ `projectIds`, `requeueCount`, `buildStartedAt`, `createdBy` (K01) — đây là
    thân dây duy nhất FE thấy ngay sau khi bấm dựng, nên nó là chỗ dễ lộ cột nội bộ nhất.
    """
    dataset = await make_dataset(db_session, family=WALL)
    project_ids = await _make_projects(db_session, 1)

    response = await _post(api_client, fake_principal, versions_path(dataset.id), {"projectIds": project_ids})

    body = response.json()
    assert response.status_code == 202
    assert body["status"] == "building"
    assert set(body) == {"id", "datasetId", "sequence", "status", "source", "createdAt"}


async def test_ml_build_dataset_version__C02_project_ids(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """C02: `projectIds` rỗng, sai dạng hay quá giới hạn đều 422."""
    dataset = await make_dataset(db_session, family=WALL)
    project_ids = await _make_projects(db_session, 2)

    empty = await _post(api_client, fake_principal, versions_path(dataset.id), {"projectIds": []})
    malformed = await _post(api_client, fake_principal, versions_path(dataset.id), {"projectIds": ["abc"]})
    missing = await _post(api_client, fake_principal, versions_path(dataset.id), {"projectIds": ["prj_MISSING"]})

    assert empty.status_code == 422
    assert malformed.status_code == 422
    assert malformed.json()["field"] == "projectIds"
    assert missing.status_code == 422
    assert missing.json()["field"] == "projectIds"

    ok = await _post(api_client, fake_principal, versions_path(dataset.id), {"projectIds": project_ids})
    assert ok.status_code == 202


async def test_ml_build_dataset_version__C02_project_ids_over_max(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Trần `DATASET_PROJECT_IDS_MAX` = 500; đây kiểm hạ trần để không dựng 501 dự án thật."""
    dataset = await make_dataset(db_session, family=WALL)
    project_ids = await _make_projects(db_session, 3)
    monkeypatch.setenv("DATASET_PROJECT_IDS_MAX", "2")
    reset_ml_datasets_settings_cache()
    try:
        response = await _post(api_client, fake_principal, versions_path(dataset.id), {"projectIds": project_ids})
    finally:
        monkeypatch.undo()
        reset_ml_datasets_settings_cache()

    assert response.status_code == 422
    assert response.json()["field"] == "projectIds"


async def test_ml_build_dataset_version__C02_project_soft_deleted(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """C02: dự án đã xoá mềm bị từ chối."""
    dataset = await make_dataset(db_session, family=WALL)
    clock = SystemClock()
    deleted = Project(id=new_id("prj", clock), name="da xoa", created_by="usr_test", deleted_at=clock.now())
    db_session.add(deleted)
    await db_session.commit()

    response = await _post(api_client, fake_principal, versions_path(dataset.id), {"projectIds": [deleted.id]})

    assert response.status_code == 422
    assert response.json()["field"] == "projectIds"


async def test_ml_build_dataset_version__C03(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """C03: khoá lạ trong thân bị 422."""
    dataset = await make_dataset(db_session, family=WALL)

    response = await _post(api_client, fake_principal, versions_path(dataset.id), {"unexpected": True})

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"


async def test_ml_build_dataset_version__C08(api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """C08: dataset không có thì 404 `dataset`."""
    response = await _post(api_client, fake_principal, versions_path("dst_01KB6020000000000000000404"), {})

    assert response.status_code == 404
    assert response.json()["resource"] == "dataset"


async def test_ml_build_dataset_version__already_building(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """Đã có bản `building` thì lượt xây mới bị 409."""
    dataset = await make_dataset(db_session, family=WALL)
    await make_dataset_version(db_session, dataset=dataset, status="building")

    response = await _post(api_client, fake_principal, versions_path(dataset.id), {})

    assert response.status_code == DATASET_BUILD_IN_PROGRESS.status
    assert response.json()["code"] == DATASET_BUILD_IN_PROGRESS.code


async def test_ml_build_dataset_version__C14_concurrent(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """Hai N31 song song → một 202, một 409, đúng một dòng `building`."""
    dataset = await make_dataset(db_session, family=WALL)

    first, second = await asyncio.gather(
        _post(api_client, fake_principal, versions_path(dataset.id), {}),
        _post(api_client, fake_principal, versions_path(dataset.id), {}),
    )

    statuses = sorted([first.status_code, second.status_code])
    assert statuses == [202, 409]


async def test_ml_build_dataset_version__C18(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_principal: Principal,
) -> None:
    """C18: xây bản mới ghi đúng một dòng hoạt động."""
    dataset = await make_dataset(db_session, family=WALL, name="bo hoat dong")

    response = await _post(api_client, fake_principal, versions_path(dataset.id), {})

    activity = await assert_one_activity(
        db_sessionmaker,
        actor_id=fake_principal.user_id,
        kind=ActivityKind.DATASET_BUILD,
        object_code=response.json()["id"],
    )
    assert activity.object_label == "bo hoat dong"


async def test_ml_build_dataset_version__C10_queue_once(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal, messaging_env: None
) -> None:
    """Lặp cùng `Idempotency-Key`: cùng response, **một** phiên bản, **một** thông điệp (Redis thật)."""
    dataset = await make_dataset(db_session, family=WALL)
    broker = broker_redis_sync()
    broker.delete(DATASET_QUEUE)
    headers = {"Idempotency-Key": "khoa-dung-mot-lan-01"}
    try:
        first = await _post(api_client, fake_principal, versions_path(dataset.id), {}, **headers)
        second = await _post(api_client, fake_principal, versions_path(dataset.id), {}, **headers)

        assert (first.status_code, second.status_code) == (202, 202)
        assert first.json() == second.json()
        version_count = (
            await db_session.execute(
                select(func.count()).select_from(DatasetVersionRow).where(DatasetVersionRow.dataset_id == dataset.id)
            )
        ).scalar_one()
        assert version_count == 1
        payloads = queued_payloads(broker, DATASET_QUEUE)
    finally:
        broker.delete(DATASET_QUEUE)
        broker.close()

    assert len(payloads) == 1
    assert payloads[0]["dataset_version_id"] == first.json()["id"]
