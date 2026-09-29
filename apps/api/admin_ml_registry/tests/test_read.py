"""Ba route đọc của registry: N23, N25, N27 (B6-01 [6], [8]).

Dữ liệu nền của mọi test ở đây là **dữ liệu gốc của revision** (hai bản `pending` ghim, ba dòng
họ `revision 0`) — không dựng lại bằng factory, vì đúng trạng thái sau `upgrade head` mới là thứ
FE gặp ở lần mở màn đầu tiên.

C07 của cả ba `op` đã có ở `test_contract.py` (P); không viết lại.
"""

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.admin_ml_registry.tests._helpers import (
    BASELINE_DIMENSION,
    BASELINE_OPENING,
    DIMENSION,
    FAMILIES_PATH,
    OPENING,
    VERSIONS_PATH,
    WALL,
)
from apps.api.core.auth import Principal
from packages.db.models.admin_ml_registry import ModelVersionRow
from packages.ml_contracts.families import MODEL_FAMILIES
from packages.testing.factories.admin_ml_registry import make_model_version
from packages.testing.fixtures.api import auth_headers
from packages.testing.fixtures.clock import FakeClock
from packages.testing.golden import attach_context


def _without_request_id(response: httpx.Response) -> dict[str, object]:
    """Thân lỗi bỏ `requestId` — nó khác nhau từng lượt, không phải phần hợp đồng của mã lỗi."""
    return {key: value for key, value in response.json().items() if key != "requestId"}


async def _get(client: httpx.AsyncClient, principal: Principal, path: str, **params: str | int) -> httpx.Response:
    """Một lượt GET của `admin` — mọi test đọc đi qua đây để không chép header ba lần."""
    return await client.get(path, headers=auth_headers(principal), params=params)


# ---------------------------------------------------------------------------
# N23 — ml_list_families
# ---------------------------------------------------------------------------


async def test_ml_list_families__C01(api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """Sau migrate: đủ ba họ đúng thứ tự `pipeline.ts:50-52`, hai họ ghim đã kích hoạt bản gốc."""
    response = await _get(api_client, fake_principal, FAMILIES_PATH)

    body = response.json()
    attach_context(response, familyOrder=[item["family"] for item in body["items"]])

    assert response.status_code == 200
    assert [item["family"] for item in body["items"]] == list(MODEL_FAMILIES)
    assert [item["revision"] for item in body["items"]] == [0, 0, 0]
    assert body["items"][1]["activeVersionId"] == BASELINE_OPENING
    assert body["items"][2]["activeVersionId"] == BASELINE_DIMENSION


async def test_ml_list_families__C15(api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """Hai lượt giống hệt cho cùng một thân, và `nextCursor` **vắng**: ba họ không phân trang."""
    first = await _get(api_client, fake_principal, FAMILIES_PATH)
    second = await _get(api_client, fake_principal, FAMILIES_PATH)

    assert (first.status_code, second.status_code) == (200, 200)
    assert first.json() == second.json()
    assert "nextCursor" not in first.json()


async def test_ml_list_families__C17(api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """Họ tường chưa có bản nào: `activeVersionId` **vắng**, không `null` (W2, K02)."""
    response = await _get(api_client, fake_principal, FAMILIES_PATH)

    wall = next(item for item in response.json()["items"] if item["family"] == WALL)

    assert set(wall) == {"family", "revision"}


# ---------------------------------------------------------------------------
# N25 — ml_list_versions
# ---------------------------------------------------------------------------


async def test_ml_list_versions__C01(api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """Không lọc: đúng hai bản gốc `pending`, mới nhất trước, không `nextCursor`."""
    response = await _get(api_client, fake_principal, VERSIONS_PATH)

    body = response.json()

    assert response.status_code == 200
    assert {item["id"] for item in body["items"]} == {BASELINE_OPENING, BASELINE_DIMENSION}
    assert {item["evaluationStatus"] for item in body["items"]} == {"pending"}
    assert "nextCursor" not in body


async def test_ml_list_versions__C01_completed(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """Một bản đã đánh giá: `metrics` ra dây với đúng khoá của họ, số JSON `float`."""
    row = await make_model_version(db_session, family=OPENING)

    response = await _get(api_client, fake_principal, VERSIONS_PATH, family=OPENING)

    items = response.json()["items"]

    assert items[0]["id"] == row.id
    assert items[0]["metrics"] == {"map50": pytest.approx(0.74)}
    assert items[0]["evaluationStatus"] == "completed"


async def test_ml_list_versions__C02(api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """`family` ngoài ba họ → 422 `field:"family"`; `limit` vượt trần 200 → 422 của khung."""
    unknown = await _get(api_client, fake_principal, VERSIONS_PATH, family="walls")
    too_many = await _get(api_client, fake_principal, VERSIONS_PATH, limit=201)

    assert unknown.status_code == 422
    assert unknown.json()["code"] == "VALIDATION"
    assert unknown.json()["field"] == "family"
    assert too_many.status_code == 422


async def test_ml_list_versions__C15(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """Họ không có bản nào → `items: []`; thêm đúng một bản → đúng một dòng, không `nextCursor`."""
    empty = await _get(api_client, fake_principal, VERSIONS_PATH, family=WALL)
    row = await make_model_version(db_session, family=WALL, status="pending")
    one = await _get(api_client, fake_principal, VERSIONS_PATH, family=WALL)

    assert empty.json() == {"items": []}
    assert [item["id"] for item in one.json()["items"]] == [row.id]
    assert "nextCursor" not in one.json()


async def test_ml_list_versions__C15_pages(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, fake_principal: Principal
) -> None:
    """5 bản, `limit=3` → trang 1 có 3 và `nextCursor`, trang 2 có đúng 2 và hết cursor."""
    rows = [
        await make_model_version(db_session, family=WALL, created_at=fake_clock.now().replace(minute=minute))
        for minute in range(5)
    ]
    newest_first = [row.id for row in reversed(rows)]

    first = await _get(api_client, fake_principal, VERSIONS_PATH, family=WALL, limit=3)
    cursor = first.json()["nextCursor"]
    second = await _get(api_client, fake_principal, VERSIONS_PATH, family=WALL, limit=3, cursor=cursor)

    assert [item["id"] for item in first.json()["items"]] == newest_first[:3]
    assert [item["id"] for item in second.json()["items"]] == newest_first[3:]
    assert "nextCursor" not in second.json()


async def test_ml_list_versions__C17(api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """Bản gốc `pending`: `metrics`, `trainingJobId`, `datasetVersionId` **vắng** (W2, K02)."""
    response = await _get(api_client, fake_principal, VERSIONS_PATH, family=DIMENSION)

    item = response.json()["items"][0]

    assert item["id"] == BASELINE_DIMENSION
    assert {"metrics", "trainingJobId", "datasetVersionId"}.isdisjoint(item)


async def test_ml_list_versions_refuses_a_cursor_of_another_family(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, fake_principal: Principal
) -> None:
    """Cursor mang dấu vết bộ lọc: dùng lại cho họ khác → 422 `CURSOR_INVALID` (W22)."""
    for minute in range(2):
        await make_model_version(db_session, family=WALL, created_at=fake_clock.now().replace(minute=minute))

    page = await _get(api_client, fake_principal, VERSIONS_PATH, family=WALL, limit=1)
    reused = await _get(api_client, fake_principal, VERSIONS_PATH, family=OPENING, cursor=page.json()["nextCursor"])

    assert reused.status_code == 422
    assert reused.json()["code"] == "CURSOR_INVALID"


# ---------------------------------------------------------------------------
# N27 — ml_read_version
# ---------------------------------------------------------------------------


async def test_ml_read_version__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """Một bản đã đánh giá đọc lại đủ trường dây, `metrics` đúng khoá của họ."""
    row = await make_model_version(db_session, family=DIMENSION, label="bản đã đo")

    response = await _get(api_client, fake_principal, f"{VERSIONS_PATH}/{row.id}")

    body = response.json()

    assert response.status_code == 200
    assert (body["id"], body["label"], body["family"]) == (row.id, "bản đã đo", DIMENSION)
    assert body["metrics"] == {"cer": pytest.approx(0.05)}


async def test_ml_read_version__C08(api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """Id không có **và** id sai mẫu đều là 404 `modelVersion` — không phân biệt (không máy dò)."""
    missing = await _get(api_client, fake_principal, f"{VERSIONS_PATH}/mdl_01KB6010000000000000000404")
    malformed = await _get(api_client, fake_principal, f"{VERSIONS_PATH}/khong-phai-id")

    # `requestId` khác nhau từng lượt (dấu vết log), nên so phần **nói cho client** của thân.
    told = [_without_request_id(response) for response in (missing, malformed)]

    assert (missing.status_code, malformed.status_code) == (404, 404)
    assert told[0] == told[1]
    assert told[0] == {"code": "NOT_FOUND", "resource": "modelVersion"}


async def test_ml_read_version__C17(api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """Bản gốc `pending` đọc một mình: ba trường tuỳ chọn vắng, không cột nội bộ nào (K01)."""
    response = await _get(api_client, fake_principal, f"{VERSIONS_PATH}/{BASELINE_OPENING}")

    body = response.json()

    assert set(body) == {
        "checksumSha256",
        "createdAt",
        "creatorId",
        "evaluationStatus",
        "family",
        "id",
        "label",
        "weightsFormat",
    }
    assert body["creatorId"] == "system:pipeline"


async def test_ml_read_version_never_leaks_the_weights_location(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """K01: `weightsKey`, `pinnedName`, `evaluationAttempts`, mã đánh giá không ra dây bao giờ."""
    row: ModelVersionRow = await make_model_version(db_session, family=OPENING)

    body = (await _get(api_client, fake_principal, f"{VERSIONS_PATH}/{row.id}")).json()

    assert row.weights_key is not None
    assert {"weightsKey", "pinnedName", "evaluationAttempts", "evaluationErrorCode"}.isdisjoint(body)
