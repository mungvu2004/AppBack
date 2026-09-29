"""Hai route đọc N28, N30 (B6-02 [6], [8]).

C07 của cả bốn `op` nằm ở `test_contract.py` — không viết lại.
"""

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.admin_ml_datasets.tests._helpers import DATASETS_PATH, DIMENSION, OPENING, WALL, versions_path
from apps.api.core.auth import Principal
from packages.testing.factories.admin_ml_datasets import make_dataset, make_dataset_version
from packages.testing.fixtures.api import auth_headers
from packages.testing.fixtures.clock import FakeClock


async def _get(client: httpx.AsyncClient, principal: Principal, path: str, **params: str | int) -> httpx.Response:
    return await client.get(path, headers=auth_headers(principal), params=params)


# ---------------------------------------------------------------------------
# N28 — ml_list_datasets
# ---------------------------------------------------------------------------


async def test_ml_list_datasets__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """200, mới nhất trước, bộ lọc `family` chỉ trả dataset của họ đó; item đúng bốn trường của dây."""
    wall = await make_dataset(db_session, family=WALL)
    opening = await make_dataset(db_session, family=OPENING)

    response = await _get(api_client, fake_principal, DATASETS_PATH, family=WALL)

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["id"] for item in items] == [wall.id]
    assert items[0] == {
        "id": wall.id,
        "name": wall.name,
        "family": WALL,
        "createdAt": items[0]["createdAt"],
    }
    both = await _get(api_client, fake_principal, DATASETS_PATH)
    assert {item["id"] for item in both.json()["items"]} == {wall.id, opening.id}


async def test_ml_list_datasets__C15(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """0, 1, 5 mục; `limit=3` → `nextCursor`, trang 2 đủ 2."""
    empty = await _get(api_client, fake_principal, DATASETS_PATH, family=WALL)
    assert empty.json() == {"items": []}

    one = await make_dataset(db_session, family=WALL)
    after_one = await _get(api_client, fake_principal, DATASETS_PATH, family=WALL)
    assert [item["id"] for item in after_one.json()["items"]] == [one.id]
    assert "nextCursor" not in after_one.json()

    others = [await make_dataset(db_session, family=WALL) for _ in range(4)]
    newest_first = [row.id for row in reversed([one, *others])]

    first = await _get(api_client, fake_principal, DATASETS_PATH, family=WALL, limit=3)
    cursor = first.json()["nextCursor"]
    second = await _get(api_client, fake_principal, DATASETS_PATH, family=WALL, limit=3, cursor=cursor)

    assert [item["id"] for item in first.json()["items"]] == newest_first[:3]
    assert [item["id"] for item in second.json()["items"]] == newest_first[3:]
    assert "nextCursor" not in second.json()


async def test_ml_list_datasets__C02(api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """`family` ngoài ba họ → 422 `field:"family"`; `limit=201` vượt trần 200 → 422 khung."""
    unknown = await _get(api_client, fake_principal, DATASETS_PATH, family="walls")
    too_many = await _get(api_client, fake_principal, DATASETS_PATH, limit=201)

    assert unknown.status_code == 422
    assert unknown.json()["code"] == "VALIDATION"
    assert unknown.json()["field"] == "family"
    assert too_many.status_code == 422


async def test_ml_list_datasets__no_family_filter(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """Không truyền `family` → mọi họ trong một trang (nhánh không lọc)."""
    wall = await make_dataset(db_session, family=WALL)
    dimension = await make_dataset(db_session, family=DIMENSION)

    response = await _get(api_client, fake_principal, DATASETS_PATH)

    assert {item["id"] for item in response.json()["items"]} == {wall.id, dimension.id}


async def test_ml_list_datasets_refuses_a_cursor_of_another_family(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, fake_principal: Principal
) -> None:
    """Cursor mang dấu vết bộ lọc `family`: dùng cho họ khác → 422 `CURSOR_INVALID`."""
    for minute in range(2):
        await make_dataset(db_session, family=WALL, created_at=fake_clock.now().replace(minute=minute))

    page = await _get(api_client, fake_principal, DATASETS_PATH, family=WALL, limit=1)
    reused = await _get(api_client, fake_principal, DATASETS_PATH, family=OPENING, cursor=page.json()["nextCursor"])

    assert reused.status_code == 422
    assert reused.json()["code"] == "CURSOR_INVALID"


async def test_ml_list_datasets__C17_shape(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """`DatasetOut`: đúng bộ khoá dây, không `createdBy`/`nameKey` (K01)."""
    row = await make_dataset(db_session, family=DIMENSION)

    response = await _get(api_client, fake_principal, DATASETS_PATH, family=DIMENSION)
    item = response.json()["items"][0]

    assert set(item) == {"createdAt", "family", "id", "name"}
    assert item["id"] == row.id


# ---------------------------------------------------------------------------
# N30 — ml_list_dataset_versions
# ---------------------------------------------------------------------------


async def test_ml_list_dataset_versions__C01_ready(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """Bản `ready`: `manifestSha256`, `splitCounts` (đủ ba khoá) có mặt; `failureCode` vắng."""
    dataset = await make_dataset(db_session, family=OPENING)
    version = await make_dataset_version(db_session, dataset=dataset, status="ready")

    response = await _get(api_client, fake_principal, versions_path(dataset.id))
    item = response.json()["items"][0]

    assert response.status_code == 200
    assert item["id"] == version.id
    assert item["status"] == "ready"
    assert item["manifestSha256"] == version.manifest_sha256
    assert item["splitCounts"] == {"train": 8, "validation": 1, "test": 1}
    assert "failureCode" not in item


async def test_ml_list_dataset_versions__C01_failed(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """Bản `failed`: `failureCode` có mặt; `manifestSha256`, `splitCounts` vắng."""
    dataset = await make_dataset(db_session, family=OPENING)
    await make_dataset_version(db_session, dataset=dataset, status="failed", failure_code="DATASET_TOO_LARGE")

    response = await _get(api_client, fake_principal, versions_path(dataset.id))
    item = response.json()["items"][0]

    assert item["status"] == "failed"
    assert item["failureCode"] == "DATASET_TOO_LARGE"
    assert {"manifestSha256", "splitCounts"}.isdisjoint(item)


async def test_ml_list_dataset_versions__C08(api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """Dataset không có **và** id sai mẫu đều 404 `resource:"dataset"`."""
    missing = await _get(api_client, fake_principal, versions_path("dst_01KB6020000000000000000404"))
    malformed = await _get(api_client, fake_principal, versions_path("khong-phai-id"))

    assert (missing.status_code, malformed.status_code) == (404, 404)
    for response in (missing, malformed):
        assert response.json()["code"] == "NOT_FOUND"
        assert response.json()["resource"] == "dataset"


async def test_ml_list_dataset_versions__C15_pages(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, fake_principal: Principal
) -> None:
    """5 bản, `limit=3` → trang 1 có 3 và `nextCursor`, trang 2 có đúng 2, `sequence` giảm dần."""
    dataset = await make_dataset(db_session, family=WALL)
    for seq in range(1, 6):
        await make_dataset_version(db_session, dataset=dataset, status="ready", sequence=seq)
    newest_first = list(range(5, 0, -1))

    first = await _get(api_client, fake_principal, versions_path(dataset.id), limit=3)
    cursor = first.json()["nextCursor"]
    second = await _get(api_client, fake_principal, versions_path(dataset.id), limit=3, cursor=cursor)

    assert [item["sequence"] for item in first.json()["items"]] == newest_first[:3]
    assert [item["sequence"] for item in second.json()["items"]] == newest_first[3:]
    assert "nextCursor" not in second.json()


async def test_ml_list_dataset_versions__C17_building(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """Bản `building`: vắng cả `manifestSha256`, `splitCounts`, `failureCode` (K02)."""
    dataset = await make_dataset(db_session, family=WALL)
    version = await make_dataset_version(db_session, dataset=dataset, status="building")

    response = await _get(api_client, fake_principal, versions_path(dataset.id))
    item = response.json()["items"][0]

    assert item["id"] == version.id
    assert {"manifestSha256", "splitCounts", "failureCode"}.isdisjoint(item)
    assert set(item) == {"createdAt", "datasetId", "id", "sequence", "source", "status"}


@pytest.mark.parametrize("query", [{"limit": 0}, {"limit": 201}])
async def test_ml_list_dataset_versions__C02_limit_bounds(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal, query: dict[str, int]
) -> None:
    """`limit` ngoài [1, 200] → 422 của khung."""
    dataset = await make_dataset(db_session, family=WALL)

    response = await _get(api_client, fake_principal, versions_path(dataset.id), **query)

    assert response.status_code == 422
