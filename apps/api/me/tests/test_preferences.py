"""`preferences` của `/api/me` (FE3D-B4): N11 luôn trả object, N12 gộp sâu bản vá, khoá lạ → 422."""

import asyncio

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.me.router import merge_preferences
from apps.api.me.tests.support import headers_of, principal_of
from packages.db.models.auth import User
from packages.testing.factories.auth import make_user

pytestmark = pytest.mark.usefixtures("api_env")

PATH = "/api/me"


async def _patch(client: httpx.AsyncClient, user: User, body: dict[str, object]) -> httpx.Response:
    return await client.patch(PATH, json=body, headers=headers_of(principal_of(user)))


async def _stored(sessionmaker: async_sessionmaker[AsyncSession], user_id: str) -> object:
    async with sessionmaker() as db:
        return await db.scalar(select(User.preferences).where(User.id == user_id))


async def test_me_read_profile__C01_preferences_default_empty(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Người chưa lưu gì → `preferences: {}` (khoá luôn có)."""
    user = await make_user(db_session)
    response = await api_client.get(PATH, headers=headers_of(principal_of(user)))
    assert response.status_code == 200
    assert response.json()["preferences"] == {}


async def test_me_update_profile__C01_preferences_deep_merge(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Khoá vắng giữ nguyên, khoá có giá trị ghi, `null` xoá; `tours` thay cả danh sách; GET đọc lại đúng."""
    user = await make_user(db_session)
    first = await _patch(
        api_client,
        user,
        {
            "preferences": {
                "appearance": {"themeChoice": "dark", "density": "compact"},
                "notifications": {
                    "aiCompleted": {"inApp": False, "email": True},
                    "projectInvite": {"inApp": True, "email": False},
                },
                "seen": {"welcome": True, "tours": ["editor3d"]},
            }
        },
    )
    assert first.status_code == 200
    second = await _patch(
        api_client,
        user,
        {
            "fullName": "Tên mới",
            "preferences": {
                "appearance": {"showGrid": True, "density": None},
                "notifications": {"projectInvite": None, "violationFound": {"inApp": True, "email": True}},
                "seen": {"tours": ["plan2d", "qc.rooms"]},
            },
        },
    )
    assert second.status_code == 200
    expected = {
        "appearance": {"themeChoice": "dark", "showGrid": True},
        "notifications": {
            "aiCompleted": {"inApp": False, "email": True},
            "violationFound": {"inApp": True, "email": True},
        },
        "seen": {"welcome": True, "tours": ["plan2d", "qc.rooms"]},
    }
    assert second.json()["preferences"] == expected
    assert second.json()["fullName"] == "Tên mới"
    assert await _stored(db_sessionmaker, user.id) == expected
    read = await api_client.get(PATH, headers=headers_of(principal_of(user)))
    assert read.json()["preferences"] == expected

    other_key = await _patch(api_client, user, {"phone": "0900000000"})
    assert other_key.json()["preferences"] == expected  # không gửi `preferences` → giữ nguyên

    cleared = await _patch(api_client, user, {"preferences": None})
    assert cleared.status_code == 200
    assert cleared.json()["preferences"] == {}
    assert await _stored(db_sessionmaker, user.id) == {}


@pytest.mark.parametrize(
    "bad_preferences",
    [
        {"notifications": {"commentMention": {"inApp": True, "email": False}}},
        {"notifications": {"aiCompleted": {"inApp": False}}},
        {"notifications": {"aiCompleted": {"inApp": "no", "email": True}}},
        {"appearance": {"themeChoice": "blue"}},
        {"appearance": {"showGrid": 1}},
        {"appearance": {"fontSize": 12}},
        {"seen": {"tours": ["a" + chr(0) + "b"]}},
        {"seen": {"tours": [""]}},
        {"seen": {"tours": [f"t{index}" for index in range(65)]}},
        {"sceneStyleId": "go-am"},
        [],
    ],
)
async def test_me_update_profile__C02_preferences_invalid(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    bad_preferences: object,
) -> None:
    """Loại thông báo lạ, ô thiếu kênh, sai kiểu/giá trị, khoá lạ, id tour bẩn hay quá 64 → 422, không ghi."""
    user = await make_user(db_session)
    response = await _patch(api_client, user, {"preferences": bad_preferences})
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"
    assert await _stored(db_sessionmaker, user.id) == {}


async def test_me_update_profile_preferences_session_revoked_when_user_deleted(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Chỉ gửi `preferences` mà người đã xoá mềm → 401 `SESSION_REVOKED` (nhánh đọc `FOR UPDATE`)."""
    user = await make_user(db_session)
    user.deleted_at = user.created_at
    await db_session.commit()
    response = await _patch(api_client, user, {"preferences": {"seen": {"welcome": True}}})
    assert response.status_code == 401
    assert response.json()["code"] == "SESSION_REVOKED"


def test_merge_preferences_does_not_mutate_inputs() -> None:
    """Hàm gộp trả bản mới; object lồng mới gộp vào giá trị cũ không phải object thì thay hẳn."""
    current: dict[str, object] = {"appearance": {"showGrid": True}, "seen": "rác"}
    patch: dict[str, object] = {"appearance": {"showGrid": None}, "seen": {"welcome": True}, "gone": None}
    assert merge_preferences(current, patch) == {"appearance": {}, "seen": {"welcome": True}}
    assert current == {"appearance": {"showGrid": True}, "seen": "rác"}


@pytest.mark.parametrize(
    ("patch", "expected"),
    [
        ({"notifications": {"aiCompleted": None}}, {"notifications": {}}),
        ({"appearance": {"density": None}}, {"appearance": {}}),
        ({"appearance": {"density": None, "showGrid": True}}, {"appearance": {"showGrid": True}}),
    ],
)
async def test_me_update_profile__C01_preferences_null_under_missing_parent(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    patch: dict[str, object],
    expected: dict[str, object],
) -> None:
    """Người `{}` gửi `null` dưới khoá cha chưa có → 200, `null` là xoá (không lưu rác), đọc lại hợp lệ."""
    user = await make_user(db_session)
    response = await _patch(api_client, user, {"preferences": patch})
    assert response.status_code == 200
    assert response.json()["preferences"] == expected
    assert await _stored(db_sessionmaker, user.id) == expected
    assert (await api_client.get(PATH, headers=headers_of(principal_of(user)))).status_code == 200


def test_merge_preferences_scalar_old_value_with_object_patch() -> None:
    """Giá trị cũ là scalar mà bản vá là object chứa `null` → gộp vào `{}`, `null` không lọt vào kết quả."""
    assert merge_preferences({"seen": 5}, {"seen": {"welcome": True, "tours": None}}) == {"seen": {"welcome": True}}


async def test_me_update_profile__C01_preferences_parallel_patches_keep_all(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Sáu PATCH song song, mỗi cái một khoá khác nhau → `FOR UPDATE` tuần tự hoá, không bản vá nào mất."""
    user = await make_user(db_session)
    patches: list[dict[str, object]] = [
        {"appearance": {"showGrid": True}},
        {"appearance": {"themeChoice": "dark"}},
        {"appearance": {"density": "compact"}},
        {"seen": {"welcome": True}},
        {"notifications": {"aiCompleted": {"inApp": False, "email": True}}},
        {"notifications": {"projectInvite": {"inApp": True, "email": False}}},
    ]
    responses = await asyncio.gather(*(_patch(api_client, user, {"preferences": patch}) for patch in patches))
    assert [response.status_code for response in responses] == [200] * len(patches)
    assert await _stored(db_sessionmaker, user.id) == {
        "appearance": {"showGrid": True, "themeChoice": "dark", "density": "compact"},
        "seen": {"welcome": True},
        "notifications": {
            "aiCompleted": {"inApp": False, "email": True},
            "projectInvite": {"inApp": True, "email": False},
        },
    }
