"""#20 `notifications_mark_read`, #21 `notifications_mark_all_read` (B4-02 [8]): G* — C01 C02 C03."""

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.notifications.schemas import NotificationMarkReadBody
from apps.api.notifications.tests.support import post_json, remove_member, rows_of, seed_project
from packages.testing.factories.auth import make_user
from packages.testing.factories.notifications import make_notification

READ = "/api/notifications/read"
READ_ALL = "/api/notifications/read-all"

_TOO_MANY = ["ntf_" + "A" * 26] * 201


async def test_notifications_mark_read__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """204 thân rỗng; đọc lại qua session mới thấy `is_read`; dòng không được nêu vẫn chưa đọc."""
    user = await make_user(db_session)
    project = await seed_project(db_session, owner=user)
    first, second = [await make_notification(db_session, user=user, project=project) for _ in range(2)]
    await db_session.commit()

    response = await post_json(api_client, user, READ, {"ids": [first.id]})

    assert (response.status_code, response.content) == (204, b"")
    async with db_sessionmaker() as fresh:
        state = {row.id: row.is_read for row in await rows_of(fresh, user.id)}
    assert state == {first.id: True, second.id: False}


@pytest.mark.parametrize(
    "body",
    [{"ids": []}, {"ids": "x"}, {"ids": _TOO_MANY}, {"ids": [""]}, {"ids": ["a", 7]}, {"ids": ["x" * 65]}, {}],
)
async def test_notifications_mark_read__C02(api_client: httpx.AsyncClient, db_session: AsyncSession, body: Any) -> None:
    """`ids` rỗng, sai kiểu, 201 phần tử, id rỗng/quá dài/không phải chuỗi, thiếu `ids` → 422 `field:"ids"`."""
    user = await make_user(db_session)
    response = await post_json(api_client, user, READ, body)
    assert (response.status_code, response.json()["code"], response.json().get("field")) == (422, "VALIDATION", "ids")


async def test_notifications_mark_read__C02_body_not_object(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Thân là mảng → 422 `VALIDATION`."""
    user = await make_user(db_session)
    response = await post_json(api_client, user, READ, [])
    assert (response.status_code, response.json()["code"]) == (422, "VALIDATION")


@pytest.mark.parametrize("extra", [{"all": True}, {"x": 1}])
async def test_notifications_mark_read__C03(
    api_client: httpx.AsyncClient, db_session: AsyncSession, extra: dict[str, Any]
) -> None:
    """Khoá lạ (`all`, `x`) → 422 `VALIDATION`, không đổi dòng nào."""
    user = await make_user(db_session)
    project = await seed_project(db_session, owner=user)
    row = await make_notification(db_session, user=user, project=project)
    await db_session.commit()
    response = await post_json(api_client, user, READ, {"ids": [row.id], **extra})
    assert (response.status_code, response.json()["code"]) == (422, "VALIDATION")
    assert not (await rows_of(db_session, user.id))[0].is_read


async def test_notifications_mark_read__mixed_foreign_and_unknown_ids(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Lẫn id của mình, của người khác và id lạ → 204; dòng người khác vẫn chưa đọc."""
    mine, other = await make_user(db_session), await make_user(db_session)
    project = await seed_project(db_session, owner=mine, members=[other])
    own = await make_notification(db_session, user=mine, project=project)
    foreign = await make_notification(db_session, user=other, project=project)
    await db_session.commit()

    response = await post_json(api_client, mine, READ, {"ids": [own.id, foreign.id, "ntf_khong-co"]})

    assert response.status_code == 204
    assert [row.is_read for row in await rows_of(db_session, mine.id)] == [True]
    assert [row.is_read for row in await rows_of(db_session, other.id)] == [False]


async def test_notifications_mark_all_read__C01(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """204 thân rỗng; mọi dòng chưa đọc của người gọi (kể cả dòng bị ẩn ở #19) thành đã đọc; người khác giữ nguyên."""
    mine, other = await make_user(db_session), await make_user(db_session)
    project = await seed_project(db_session, owner=mine, members=[other])
    gone = await seed_project(db_session, owner=other, members=[mine])
    await make_notification(db_session, user=mine, project=project)
    await make_notification(db_session, user=mine, project=gone)
    await make_notification(db_session, user=other, project=project)
    await db_session.commit()
    await remove_member(db_session, gone, mine)

    response = await post_json(api_client, mine, READ_ALL, {})

    assert (response.status_code, response.content) == (204, b"")
    assert [row.is_read for row in await rows_of(db_session, mine.id)] == [True, True]
    assert [row.is_read for row in await rows_of(db_session, other.id)] == [False]


async def test_notifications_mark_all_read__C01_no_rows(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Không có dòng nào vẫn 204."""
    user = await make_user(db_session)
    assert (await post_json(api_client, user, READ_ALL, {})).status_code == 204


@pytest.mark.parametrize("body", [[], "x", 7, None])
async def test_notifications_mark_all_read__C02(
    api_client: httpx.AsyncClient, db_session: AsyncSession, body: Any
) -> None:
    """Thân không phải object (`[]`, chuỗi, số, `null`) → 422."""
    user = await make_user(db_session)
    response = await post_json(api_client, user, READ_ALL, body)
    assert (response.status_code, response.json()["code"]) == (422, "VALIDATION")


async def test_notifications_mark_all_read__C03(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Khoá lạ → 422 `VALIDATION`."""
    user = await make_user(db_session)
    response = await post_json(api_client, user, READ_ALL, {"x": 1})
    assert (response.status_code, response.json()["code"]) == (422, "VALIDATION")


def test_notification_mark_read_body__openapi_keeps_bounds() -> None:
    """NO-253 (3): lược đồ `ids` của #20 phơi `minItems`/`maxItems`/`maxLength` để `openapi.json` giữ ràng buộc."""
    ids = NotificationMarkReadBody.model_json_schema()["properties"]["ids"]
    assert (ids["minItems"], ids["maxItems"], ids["items"]["maxLength"]) == (1, 200, 64)
