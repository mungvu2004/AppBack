"""N24 `ml_activate_version` — ghi có version trên dòng họ (B6-01 [6] bước 1-5, [8]).

Hai nhóm test, cố ý tách:

- `__Cxx` là ma trận case chung (C01, C02, C03, C08, C09, C09b, C14, C17, C18);
- các tên "theo việc" ở cuối kiểm **luật kích hoạt** của khối [8]: họ lệch, định dạng lệch,
  bản chưa đánh giá, quay về bản gốc, đặt lại đúng bản đang kích hoạt, `null` đúng và sai họ.

C07 đã có ở `test_contract.py` (P); không viết lại.
"""

import asyncio
from typing import Any

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.access.kinds import ActivityKind
from apps.api.admin_ml_registry.registry import active_versions
from apps.api.admin_ml_registry.tests._helpers import BASELINE_OPENING, DIMENSION, FAMILIES_PATH, OPENING, WALL
from apps.api.core.auth import Principal
from packages.core.ids import new_id
from packages.db.models.admin_ml_registry import ModelFamilyRow, ModelVersionRow
from packages.testing.factories.admin_ml_registry import make_model_version
from packages.testing.fixtures.access import assert_one_activity
from packages.testing.fixtures.api import auth_headers
from packages.testing.fixtures.clock import FakeClock


def _body(base_version: int, version_id: str | None) -> dict[str, Any]:
    """Thân GV của N24: `{baseVersion, body: {versionId}}` (W20)."""
    return {"baseVersion": base_version, "body": {"versionId": version_id}}


async def _activate(
    client: httpx.AsyncClient, principal: Principal, family: str, body: dict[str, Any]
) -> httpx.Response:
    """Một lượt PUT của `admin`; `body` truyền thô để test C03 gửi được cả khoá lạ."""
    return await client.put(f"{FAMILIES_PATH}/{family}/active", headers=auth_headers(principal), json=body)


async def _family(sessionmaker: async_sessionmaker[AsyncSession], family: str) -> ModelFamilyRow:
    """Dòng họ đọc bằng **session mới**: route commit ở session khác, identity map cũ là dữ liệu cũ."""
    async with sessionmaker() as session:
        return (await session.scalars(select(ModelFamilyRow).where(ModelFamilyRow.family == family))).one()


async def _evaluate_baseline_opening(db: AsyncSession) -> None:
    """Bản gốc của họ `openingAndFurnitureDetection` thành `completed` — việc thật của `ml_eval`.

    Dữ liệu gốc của revision là `pending`, mà N24 chỉ kích hoạt bản `completed`: không có bước
    tắt này thì hai test "quay về bản gốc" và "đặt lại bản đang kích hoạt" không dựng được.
    """
    await db.execute(
        update(ModelVersionRow)
        .where(ModelVersionRow.id == BASELINE_OPENING)
        .values(evaluation_status="completed", metrics={"map50": 0.5})
    )
    await db.commit()


def _other_admin(clock: FakeClock) -> Principal:
    """Một `admin` **khác** `fake_principal` — dùng cho C09 và C09b (người ghi khác)."""
    return Principal(user_id=new_id("usr", clock), session_id="sid-khac", role="admin")


# ---------------------------------------------------------------------------
# Ma trận case
# ---------------------------------------------------------------------------


async def test_ml_activate_version__C01(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_principal: Principal,
) -> None:
    """Kích hoạt một bản `completed` `onnx`: 200, `revision` 0 → 1, `activeVersionId` là bản ấy."""
    row = await make_model_version(db_session, family=OPENING)

    response = await _activate(api_client, fake_principal, OPENING, _body(0, row.id))

    stored = await _family(db_sessionmaker, OPENING)

    assert response.status_code == 200
    assert response.json() == {"activeVersionId": row.id, "family": OPENING, "revision": 1}
    assert (stored.active_version_id, stored.revision) == (row.id, 1)


async def test_ml_activate_version__C02(api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """`versionId` phải là chuỗi hoặc `null`; số 5 → 422 `VALIDATION`."""
    response = await _activate(api_client, fake_principal, OPENING, {"baseVersion": 0, "body": {"versionId": 5}})

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"


async def test_ml_activate_version__C03(api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """Khoá lạ ở vỏ ngoài **và** trong `body` đều 422 `VALIDATION` (`WireRequest` cấm extra)."""
    outer = await _activate(api_client, fake_principal, WALL, _body(0, None) | {"note": "x"})
    inner = await _activate(api_client, fake_principal, WALL, {"baseVersion": 0, "body": {"versionId": None, "q": 1}})

    assert (outer.status_code, inner.status_code) == (422, 422)
    assert {outer.json()["code"], inner.json()["code"]} == {"VALIDATION"}


async def test_ml_activate_version__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """Họ lạ → 404 `modelFamily`; bản không có → 404 `modelVersion` (hai `resource` khác nhau)."""
    await make_model_version(db_session, family=OPENING)

    unknown_family = await _activate(api_client, fake_principal, "walls", _body(0, None))
    unknown_version = await _activate(api_client, fake_principal, OPENING, _body(0, "mdl_01KB6010000000000000000404"))

    assert (unknown_family.status_code, unknown_version.status_code) == (404, 404)
    assert unknown_family.json()["resource"] == "modelFamily"
    assert unknown_version.json()["resource"] == "modelVersion"


async def test_ml_activate_version__C09_stale(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal, fake_clock: FakeClock
) -> None:
    """Người khác đã ghi xong: base 0 trên `revision` 1 → 409 `currentVersion 1`, `remoteChanges: []`."""
    first = await make_model_version(db_session, family=OPENING)
    second = await make_model_version(db_session, family=OPENING)
    assert (await _activate(api_client, fake_principal, OPENING, _body(0, first.id))).status_code == 200

    response = await _activate(api_client, _other_admin(fake_clock), OPENING, _body(0, second.id))

    assert response.status_code == 409
    assert response.json()["currentVersion"] == 1
    assert response.json()["remoteChanges"] == []


async def test_ml_activate_version__C09_ahead(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """`baseVersion` **lớn hơn** hiện tại cũng là xung đột: base 7 trên `revision` 0 → 409."""
    row = await make_model_version(db_session, family=OPENING)

    response = await _activate(api_client, fake_principal, OPENING, _body(7, row.id))

    assert response.status_code == 409
    assert response.json()["code"] == "VERSION_CONFLICT"
    assert response.json()["currentVersion"] == 0
    assert response.json()["remoteChanges"] == []


async def test_ml_activate_version__C09_missing(api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """Thiếu `baseVersion` → 428 `PRECONDITION_REQUIRED`, do guard của khung trước Pydantic."""
    response = await _activate(api_client, fake_principal, WALL, {"body": {"versionId": None}})

    assert response.status_code == 428
    assert response.json()["code"] == "PRECONDITION_REQUIRED"


async def test_ml_activate_version__C09b(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_principal: Principal,
) -> None:
    """Cùng người, cùng thân, base = `revision` - 1 → 200 hiện trạng, không tăng, không ghi nhật ký lần hai."""
    row = await make_model_version(db_session, family=OPENING)
    assert (await _activate(api_client, fake_principal, OPENING, _body(0, row.id))).status_code == 200

    repeat = await _activate(api_client, fake_principal, OPENING, _body(0, row.id))

    stored = await _family(db_sessionmaker, OPENING)

    assert repeat.status_code == 200
    assert repeat.json()["revision"] == 1
    assert stored.revision == 1
    await assert_one_activity(
        db_sessionmaker, actor_id=fake_principal.user_id, kind=ActivityKind.MODEL_ACTIVATE, object_code=row.id
    )


async def test_ml_activate_version__C09b_other(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal, fake_clock: FakeClock
) -> None:
    """Cùng thân nhưng **người khác** không phải lượt lặp: 409, không im lặng nuốt lượt ghi."""
    row = await make_model_version(db_session, family=OPENING)
    assert (await _activate(api_client, fake_principal, OPENING, _body(0, row.id))).status_code == 200

    response = await _activate(api_client, _other_admin(fake_clock), OPENING, _body(0, row.id))

    assert response.status_code == 409
    assert response.json()["currentVersion"] == 1


async def test_ml_activate_version__C14(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_principal: Principal,
    fake_clock: FakeClock,
) -> None:
    """Hai người cùng base 0, hai bản khác nhau, song song → một 200 một 409; bản của bên thắng."""
    first = await make_model_version(db_session, family=OPENING)
    second = await make_model_version(db_session, family=OPENING)

    results = await asyncio.gather(
        _activate(api_client, fake_principal, OPENING, _body(0, first.id)),
        _activate(api_client, _other_admin(fake_clock), OPENING, _body(0, second.id)),
    )

    stored = await _family(db_sessionmaker, OPENING)
    winner = next(response for response in results if response.status_code == 200)

    assert sorted(response.status_code for response in results) == [200, 409]
    assert stored.revision == 1
    assert stored.active_version_id == winner.json()["activeVersionId"]


async def test_ml_activate_version__C17(api_client: httpx.AsyncClient, fake_principal: Principal) -> None:
    """Họ tường chưa kích hoạt gì, gửi `null`: 200 và `activeVersionId` **vắng** (W2, K02)."""
    response = await _activate(api_client, fake_principal, WALL, _body(0, None))

    assert response.status_code == 200
    assert response.json() == {"family": WALL, "revision": 0}


async def test_ml_activate_version__C18(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_principal: Principal,
) -> None:
    """Đúng một dòng `model.activate` mang id bản và nhãn bản (K05: người thực hiện từ `Principal`)."""
    row = await make_model_version(db_session, family=DIMENSION, label="bản đo chữ")

    assert (await _activate(api_client, fake_principal, DIMENSION, _body(0, row.id))).status_code == 200

    logged = await assert_one_activity(
        db_sessionmaker, actor_id=fake_principal.user_id, kind=ActivityKind.MODEL_ACTIVATE, object_code=row.id
    )

    assert logged.object_label == "bản đo chữ"


# ---------------------------------------------------------------------------
# Luật kích hoạt của khối [8] ("Luật N24")
# ---------------------------------------------------------------------------


async def test_set_active_version_rejects_a_version_of_another_family(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """Bản của họ khác → 422 `MODEL_VERSION_FAMILY_MISMATCH`, không bao giờ ghi chéo họ."""
    row = await make_model_version(db_session, family=DIMENSION)

    response = await _activate(api_client, fake_principal, OPENING, _body(0, row.id))

    assert response.status_code == 422
    assert response.json()["code"] == "MODEL_VERSION_FAMILY_MISMATCH"


async def test_set_active_version_rejects_a_safetensors_version(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal
) -> None:
    """`safetensors` dù `completed` vẫn không chạy được suy luận → `MODEL_FORMAT_UNSUPPORTED`."""
    row = await make_model_version(db_session, family=OPENING, weights_format="safetensors")

    response = await _activate(api_client, fake_principal, OPENING, _body(0, row.id))

    assert response.status_code == 422
    assert response.json()["code"] == "MODEL_FORMAT_UNSUPPORTED"


@pytest.mark.parametrize("status", ["pending", "running", "failed"])
async def test_set_active_version_rejects_a_version_that_is_not_evaluated(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_principal: Principal, status: str
) -> None:
    """Chưa `completed` (kể cả `failed`) → `MODEL_VERSION_NOT_EVALUATED`: chưa ai biết nó đo được bao nhiêu."""
    row = await make_model_version(db_session, family=OPENING, status=status)

    response = await _activate(api_client, fake_principal, OPENING, _body(0, row.id))

    assert response.status_code == 422
    assert response.json()["code"] == "MODEL_VERSION_NOT_EVALUATED"


async def test_set_active_version_rolls_back_to_the_baseline_version(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_principal: Principal,
) -> None:
    """Đường lùi của họ ghim: kích hoạt bản mới rồi quay về bản gốc → họ trỏ lại bản gốc.

    Khẳng định cuối đi qua `registry.active_versions` — đúng hàm mà pipeline đọc để ghim model
    (BE-00 §9): bản gốc quay lại phải ra `ModelRef` **dạng ghim**, không dạng storage của bản mới.
    """
    await _evaluate_baseline_opening(db_session)
    new_version = await make_model_version(db_session, family=OPENING)
    assert (await _activate(api_client, fake_principal, OPENING, _body(0, new_version.id))).status_code == 200

    back = await _activate(api_client, fake_principal, OPENING, _body(1, BASELINE_OPENING))

    stored = await _family(db_sessionmaker, OPENING)
    active = await active_versions(db_session)

    assert back.json() == {"activeVersionId": BASELINE_OPENING, "family": OPENING, "revision": 2}
    assert stored.active_version_id == BASELINE_OPENING
    assert active[OPENING].version_id == BASELINE_OPENING
    assert active[OPENING].pinned_name is not None


async def test_set_active_version_keeps_the_revision_when_nothing_changes(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_principal: Principal,
) -> None:
    """Đặt lại **đúng** bản đang kích hoạt: 200 hiện trạng, `revision` không tăng, không nhật ký."""
    await _evaluate_baseline_opening(db_session)

    response = await _activate(api_client, fake_principal, OPENING, _body(0, BASELINE_OPENING))

    stored = await _family(db_sessionmaker, OPENING)

    assert response.json() == {"activeVersionId": BASELINE_OPENING, "family": OPENING, "revision": 0}
    assert (stored.revision, stored.last_writer_id) == (0, None)


async def test_set_active_version_rejects_null_outside_the_wall_family(
    api_client: httpx.AsyncClient, fake_principal: Principal
) -> None:
    """`null` là "chạy đường cổ điển", chỉ họ tường có đường ấy → họ khác nhận 422."""
    response = await _activate(api_client, fake_principal, DIMENSION, _body(0, None))

    assert response.status_code == 422
    assert response.json()["code"] == "MODEL_VERSION_FAMILY_MISMATCH"


async def test_set_active_version_clears_the_wall_family_with_null(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_principal: Principal,
) -> None:
    """Họ tường đang có bản kích hoạt, gửi `null` → 200 vắng `activeVersionId`, đúng 1 dòng nhật ký."""
    row = await make_model_version(db_session, family=WALL)
    assert (await _activate(api_client, fake_principal, WALL, _body(0, row.id))).status_code == 200

    cleared = await _activate(api_client, fake_principal, WALL, _body(1, None))

    stored = await _family(db_sessionmaker, WALL)

    assert cleared.json() == {"family": WALL, "revision": 2}
    assert stored.active_version_id is None
    logged = await assert_one_activity(
        db_sessionmaker, actor_id=fake_principal.user_id, kind=ActivityKind.MODEL_ACTIVATE, object_code=WALL
    )
    assert logged.object_label == "đường cổ điển"
