"""#44 `users_invite_users` và #45 `users_resend_invitation` (B1-05 [6], [8]).

#44: C01 C02 C03 C07 C15 C17 C18 C11 C16 + C10 riêng; #45: C01 C02 C03 C07 C08 C17 C18 + C10
riêng. Thư đi qua `issue_token` **sau commit**: test bắt lô `send_task` bằng
`capture_mail_batches` (không cần worker) và đếm token trong DB.
"""

import asyncio
from collections.abc import Sequence
from typing import Any

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.access.kinds import ActivityKind
from apps.api.auth_recovery.tests.support import seed_token
from apps.api.users import service
from apps.api.users.tests.support import (
    USERS,
    capture_mail_batches,
    count_tokens,
    make_admin,
    reload,
    send,
    users_limits,
)
from packages.core.text import normalize_email
from packages.db.models.auth import User
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.access import activity_rows, assert_one_activity
from packages.testing.fixtures.clock import FakeClock

pytestmark = pytest.mark.usefixtures("api_env")

INVITE = f"{USERS}/invitations"
INVITED_KEYS = {"email", "id", "invitedAt", "inviteExpiresAt", "lastActiveAt", "name", "projectCount", "role", "status"}
GHOST = "usr_01JABCDEFGHJKMNPQRSTVWXYZ0"


def _body(emails: Sequence[str], role: str = "engineer") -> dict[str, Any]:
    return {"emails": list(emails), "role": role}


async def _users_by_email(db: AsyncSession, *emails: str) -> list[User]:
    """Người chưa xoá mềm khớp `emails` (qua `normalize_email`), đọc mới từ DB."""
    keys = [normalize_email(email) for email in emails]
    stmt = (
        select(User)
        .where(User.email_normalized.in_(keys), User.deleted_at.is_(None))
        .execution_options(populate_existing=True)
    )
    return list((await db.execute(stmt)).scalars())


# --------------------------------------------------------------------------- #44


async def test_users_invite_users__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """201, người `pending` `usr_…`, trả theo thứ tự đầu vào (dù xử lý theo email), một lô thư sau commit."""
    admin = await make_admin(db_session)
    batches = capture_mail_batches(monkeypatch)
    response = await send(api_client, admin, "POST", INVITE, json=_body(["zeta@example.com", "alpha@example.com"]))
    assert response.status_code == 201
    rows = response.json()
    assert [row["email"] for row in rows] == ["zeta@example.com", "alpha@example.com"]
    assert all(
        row["status"] == "pending" and row["role"] == "engineer" and row["id"].startswith("usr_") for row in rows
    )
    assert all(row["projectCount"] == 0 and row["name"] for row in rows)
    assert len(batches) == 1
    assert len(batches[0]) == 2
    for row in rows:
        assert await count_tokens(db_session, row["id"], live_only=True) == 1


async def test_users_invite_users__C17(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Người mới: có `invitedAt`/`inviteExpiresAt`, `lastActiveAt: null` có khoá, không `avatarUrl` (K01, K02)."""
    admin = await make_admin(db_session)
    row = (await send(api_client, admin, "POST", INVITE, json=_body(["moi@example.com"]))).json()[0]
    assert set(row) == INVITED_KEYS
    assert row["lastActiveAt"] is None


async def test_users_invite_users__C18(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Mỗi người một dòng `user.invite`: actor là người thực hiện, `objectCode` là id, nhãn là email."""
    admin = await make_admin(db_session)
    rows = (await send(api_client, admin, "POST", INVITE, json=_body(["a1@example.com", "a2@example.com"]))).json()
    for row in rows:
        entry = await assert_one_activity(
            db_sessionmaker, actor_id=admin.id, kind=ActivityKind.USER_INVITE, object_code=row["id"]
        )
        assert entry.object_label == row["email"]
    assert len(await activity_rows(db_sessionmaker, kind=ActivityKind.USER_INVITE)) == 2


@pytest.mark.parametrize(
    "bad",
    [
        {"emails": [], "role": "engineer"},
        {"emails": "a@example.com", "role": "engineer"},
        {"emails": ["a@example.com"], "role": "root"},
        {"emails": ["a@example.com"]},
        {"emails": [7], "role": "engineer"},
    ],
)
async def test_users_invite_users__C02(
    api_client: httpx.AsyncClient, db_session: AsyncSession, bad: dict[str, Any]
) -> None:
    """Thân sai kiểu/giá trị/thiếu → 422 `VALIDATION`; không tạo ai."""
    admin = await make_admin(db_session)
    response = await send(api_client, admin, "POST", INVITE, json=bad)
    assert (response.status_code, response.json()["code"]) == (422, "VALIDATION")
    assert await _users_by_email(db_session, "a@example.com") == []


async def test_users_invite_users__C03(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Khoá lạ trong thân → 422 `VALIDATION`."""
    admin = await make_admin(db_session)
    response = await send(api_client, admin, "POST", INVITE, json={**_body(["a@example.com"]), "x": 1})
    assert (response.status_code, response.json()["code"]) == (422, "VALIDATION")


@pytest.mark.parametrize("role", ["engineer", "viewer"])
async def test_users_invite_users__C07(api_client: httpx.AsyncClient, db_session: AsyncSession, role: str) -> None:
    """Không phải admin → 403, không tạo ai."""
    caller = await make_user(db_session, role=role)
    response = await send(api_client, caller, "POST", INVITE, json=_body(["a@example.com"]))
    assert (response.status_code, response.json()["code"]) == (403, "FORBIDDEN")
    assert await _users_by_email(db_session, "a@example.com") == []


async def test_users_invite_users__C15(
    api_client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Trần lô = 3: 1 email, đúng 3 email đều qua; 4 email → 422 `field:"emails"`, không tạo ai."""
    admin = await make_admin(db_session)
    with users_limits(monkeypatch, invite_batch_max=3):
        one = await send(api_client, admin, "POST", INVITE, json=_body(["c1@example.com"]))
        exact = await send(api_client, admin, "POST", INVITE, json=_body([f"c{i}@example.com" for i in (2, 3, 4)]))
        over = await send(api_client, admin, "POST", INVITE, json=_body([f"d{i}@example.com" for i in range(4)]))
    assert (one.status_code, exact.status_code, len(exact.json())) == (201, 201, 3)
    assert (over.status_code, over.json()["code"], over.json()["field"]) == (422, "VALIDATION", "emails")
    assert await _users_by_email(db_session, "d0@example.com") == []


async def test_users_invite_users_default_batch_cap_is_50(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """51 email → 422 `field:"emails"`, không tạo ai."""
    admin = await make_admin(db_session)
    response = await send(api_client, admin, "POST", INVITE, json=_body([f"lo{i}@example.com" for i in range(51)]))
    assert (response.status_code, response.json()["field"]) == (422, "emails")
    assert await _users_by_email(db_session, "lo0@example.com") == []


@pytest.mark.parametrize(
    "bad_email",
    [chr(0xE1) + "nh@cty.vn", chr(0x17F) + "@example.com", chr(0x212A) + "@example.com", "khong-phai-email", " "],
)
async def test_users_invite_users_rejects_non_wire_emails(
    api_client: httpx.AsyncClient, db_session: AsyncSession, bad_email: str
) -> None:
    """Email ngoài `validate_wire_email` (không ASCII, U+017F, Kelvin U+212A) → 422 `field:"emails"` (K37)."""
    admin = await make_admin(db_session)
    response = await send(api_client, admin, "POST", INVITE, json=_body(["hop-le@example.com", bad_email]))
    assert (response.status_code, response.json()["field"]) == (422, "emails")
    assert await _users_by_email(db_session, "hop-le@example.com") == []


async def test_users_invite_users__C16(
    api_client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, fake_clock: FakeClock
) -> None:
    """Email khác hoa thường trùng người `pending` có sẵn: giữ người đó, đổi vai, thay token, thư mới khác token."""
    admin = await make_admin(db_session)
    pending = await make_user(db_session, status="pending", password=None, email="Mai.Lan@example.com", role="viewer")
    old, _ = await seed_token(db_session, user_id=pending.id, purpose="invite", clock=fake_clock)
    batches = capture_mail_batches(monkeypatch)
    response = await send(api_client, admin, "POST", INVITE, json=_body(["mai.lan@EXAMPLE.com"], "engineer"))
    assert response.status_code == 201
    assert response.json()[0]["id"] == pending.id
    stored = await reload(db_session, pending.id)
    assert (stored.role, stored.token_version) == ("engineer", 1)
    assert len(await _users_by_email(db_session, "MAI.LAN@example.com")) == 1
    assert await count_tokens(db_session, pending.id) == 2
    assert await count_tokens(db_session, pending.id, live_only=True) == 1
    assert len(batches) == 1
    assert old.id not in batches[0]


async def test_users_invite_users_dedupes_by_normalized_email(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Hai email chỉ khác hoa thường → một người, giữ lần đầu."""
    admin = await make_admin(db_session)
    rows = (await send(api_client, admin, "POST", INVITE, json=_body(["Ai@example.com", "ai@EXAMPLE.com"]))).json()
    assert [row["email"] for row in rows] == ["Ai@example.com"]


async def test_users_invite_users_long_local_part_truncates_name(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Phần trước `@` dài 130 ký tự → `name` đúng 120 ký tự, không 500."""
    admin = await make_admin(db_session)
    local = "x" * 130
    response = await send(api_client, admin, "POST", INVITE, json=_body([f"{local}@example.com"]))
    assert response.status_code == 201
    assert response.json()[0]["name"] == "x" * 120


@pytest.mark.parametrize("taken_status", ["active", "disabled"])
async def test_users_invite_users_taken_email_fails_whole_batch(
    api_client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, taken_status: str
) -> None:
    """Một email đã `active`/`disabled` trong lô 3 → 422 `USER_EMAIL_TAKEN`, không tạo ai, không thư."""
    admin = await make_admin(db_session)
    await make_user(db_session, status=taken_status, email="da-co@example.com")
    batches = capture_mail_batches(monkeypatch)
    emails = ["moi1@example.com", "da-co@example.com", "moi2@example.com"]
    response = await send(api_client, admin, "POST", INVITE, json=_body(emails))
    assert (response.status_code, response.json()["code"], response.json()["field"]) == (
        422,
        "USER_EMAIL_TAKEN",
        "emails",
    )
    assert await _users_by_email(db_session, "moi1@example.com", "moi2@example.com") == []
    assert batches == []


async def test_users_invite_users_frees_email_of_deleted_user(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Email của người đã xoá mềm mời lại được, ra người mới có `id` khác."""
    admin = await make_admin(db_session)
    gone = await make_user(db_session, email="cu@example.com")
    await db_session.execute(update(User).where(User.id == gone.id).values(deleted_at=User.created_at))
    await db_session.commit()
    response = await send(api_client, admin, "POST", INVITE, json=_body(["cu@example.com"]))
    assert (response.status_code, response.json()[0]["id"] != gone.id) == (201, True)


async def test_users_invite_users_actor_demoted_in_db_is_forbidden(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Admin bị hạ vai trong DB (cache còn) mời `role:"admin"` → 403, không tạo ai."""
    actor, _other = await make_admin(db_session), await make_admin(db_session)
    await db_session.execute(update(User).where(User.id == actor.id).values(role="engineer"))
    await db_session.commit()
    actor.role = "admin"
    response = await send(api_client, actor, "POST", INVITE, json=_body(["vip@example.com"], "admin"))
    assert (response.status_code, response.json()["code"]) == (403, "FORBIDDEN")
    assert await _users_by_email(db_session, "vip@example.com") == []


async def test_users_invite_users_parallel_batches_in_opposite_order(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Hai lô `[a,b]` và `[b,a]` song song từ hai admin: cả hai 201 (không 503, không 500), mỗi email đúng một người."""
    first, second = await make_admin(db_session), await make_admin(db_session)
    forward, backward = ["a@example.com", "b@example.com"], ["b@example.com", "a@example.com"]
    responses = await asyncio.gather(
        send(api_client, first, "POST", INVITE, json=_body(forward)),
        send(api_client, second, "POST", INVITE, json=_body(backward)),
    )
    assert [r.status_code for r in responses] == [201, 201]
    assert len(await _users_by_email(db_session, *forward)) == 2
    assert {row["id"] for row in responses[0].json()} == {row["id"] for row in responses[1].json()}


async def test_users_invite_users_lost_race_reuses_pending(
    api_client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Thua tranh chấp `uq_users_email`: `ON CONFLICT` bỏ dòng, đọc lại thấy người `pending` → dùng lại, 201."""
    admin = await make_admin(db_session)
    winner = await make_user(db_session, status="pending", password=None, email="thang@example.com")
    _stale_first_lookup(monkeypatch)
    response = await send(api_client, admin, "POST", INVITE, json=_body(["thang@example.com"]))
    assert (response.status_code, response.json()[0]["id"]) == (201, winner.id)


async def test_users_invite_users_lost_race_to_active_is_taken(
    api_client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Thua tranh chấp cho người đã `active` → 422 `USER_EMAIL_TAKEN`, không 500."""
    admin = await make_admin(db_session)
    await make_user(db_session, email="thang@example.com")
    _stale_first_lookup(monkeypatch)
    response = await send(api_client, admin, "POST", INVITE, json=_body(["thang@example.com"]))
    assert (response.status_code, response.json()["code"]) == (422, "USER_EMAIL_TAKEN")


def _stale_first_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lần tra email đầu của #44 thấy "chưa có ai" (bản chụp cũ), các lần sau tra thật — dựng đúng cuộc đua."""
    real = service._lock_by_emails
    calls: list[int] = []

    async def stale(db: AsyncSession, keys: Sequence[str]) -> dict[str, User]:
        calls.append(1)
        return {} if len(calls) == 1 else await real(db, keys)

    monkeypatch.setattr(service, "_lock_by_emails", stale)


async def test_users_invite_users__C11(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """30 lượt/giờ theo người thực hiện; lượt 31 → 429 `RATE_LIMITED` + `Retry-After`; #45 chung xô đếm."""
    admin = await make_admin(db_session)
    for _ in range(30):
        assert (await send(api_client, admin, "POST", INVITE, json={})).status_code == 422
    blocked = await send(api_client, admin, "POST", INVITE, json=_body(["a@example.com"]))
    assert (blocked.status_code, blocked.json()["code"]) == (429, "RATE_LIMITED")
    assert "retry-after" in blocked.headers
    resend = await send(api_client, admin, "POST", f"{INVITE}/{GHOST}/resend", json={})
    assert resend.status_code == 429


async def test_users_invite_users__C10(
    api_client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lặp cùng `Idempotency-Key` và thân: response đã lưu, **không** phát token/thư lần hai (K17)."""
    admin = await make_admin(db_session)
    batches = capture_mail_batches(monkeypatch)
    headers = {"Idempotency-Key": "khoa-moi-mot-lan-01"}
    first = await send(api_client, admin, "POST", INVITE, json=_body(["lap@example.com"]), headers=headers)
    second = await send(api_client, admin, "POST", INVITE, json=_body(["lap@example.com"]), headers=headers)
    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json() == second.json()
    assert await count_tokens(db_session, first.json()[0]["id"]) == 1
    assert len(batches) == 1
    reused = await send(api_client, admin, "POST", INVITE, json=_body(["khac@example.com"]), headers=headers)
    assert (reused.status_code, reused.json()["code"]) == (422, "IDEMPOTENCY_KEY_REUSED")


# --------------------------------------------------------------------------- #45


def _resend(user_id: str) -> str:
    return f"{INVITE}/{user_id}/resend"


async def _pending_with_invite(db: AsyncSession, clock: FakeClock) -> User:
    """Người `pending` đã có một lời mời còn hạn."""
    user = await make_user(db, status="pending", password=None)
    await seed_token(db, user_id=user.id, purpose="invite", clock=clock)
    return user


async def test_users_resend_invitation__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """200, token cũ bị thay bằng token mới, đúng một lô thư sau commit."""
    admin, target = await make_admin(db_session), await _pending_with_invite(db_session, fake_clock)
    batches = capture_mail_batches(monkeypatch)
    response = await send(api_client, admin, "POST", _resend(target.id), json={})
    assert (response.status_code, response.json()["status"]) == (200, "pending")
    assert "invitedAt" in response.json()
    assert await count_tokens(db_session, target.id) == 2
    assert await count_tokens(db_session, target.id, live_only=True) == 1
    assert len(batches) == 1


async def test_users_resend_invitation__C18(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
) -> None:
    """Nhật ký `user.invite_resend` do admin thực hiện, `objectLabel` là email."""
    admin, target = await make_admin(db_session), await _pending_with_invite(db_session, fake_clock)
    await send(api_client, admin, "POST", _resend(target.id), json={})
    row = await assert_one_activity(
        db_sessionmaker, actor_id=admin.id, kind=ActivityKind.USER_INVITE_RESEND, object_code=target.id
    )
    assert row.object_label == target.email


async def test_users_resend_invitation__C17(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Khoá tuỳ chọn đúng: có lời mời, không `avatarUrl`, `lastActiveAt: null` có khoá."""
    admin, target = await make_admin(db_session), await _pending_with_invite(db_session, fake_clock)
    body = (await send(api_client, admin, "POST", _resend(target.id), json={})).json()
    assert set(body) == INVITED_KEYS


async def test_users_resend_invitation__C02(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Thân không phải object → 422 `VALIDATION`."""
    admin = await make_admin(db_session)
    response = await send(api_client, admin, "POST", _resend(GHOST), json=[])
    assert (response.status_code, response.json()["code"]) == (422, "VALIDATION")


async def test_users_resend_invitation__C03(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Khoá lạ trong thân → 422 `VALIDATION`."""
    admin = await make_admin(db_session)
    response = await send(api_client, admin, "POST", _resend(GHOST), json={"x": 1})
    assert (response.status_code, response.json()["code"]) == (422, "VALIDATION")


@pytest.mark.parametrize("role", ["engineer", "viewer"])
async def test_users_resend_invitation__C07(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, role: str
) -> None:
    """Không phải admin → 403."""
    caller, target = await make_user(db_session, role=role), await _pending_with_invite(db_session, fake_clock)
    assert (await send(api_client, caller, "POST", _resend(target.id), json={})).status_code == 403


async def test_users_resend_invitation__C08(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Không có người → 404 `resource:"user"`."""
    admin = await make_admin(db_session)
    response = await send(api_client, admin, "POST", _resend(GHOST), json={})
    assert (response.status_code, response.json()["resource"]) == (404, "user")


@pytest.mark.parametrize("status", ["active", "disabled"])
async def test_users_resend_invitation_not_pending(
    api_client: httpx.AsyncClient, db_session: AsyncSession, status: str
) -> None:
    """Người không `pending` → 422 `USER_NOT_PENDING`."""
    admin, target = await make_admin(db_session), await make_user(db_session, status=status)
    response = await send(api_client, admin, "POST", _resend(target.id), json={})
    assert (response.status_code, response.json()["code"]) == (422, "USER_NOT_PENDING")


async def test_users_resend_invitation__C10(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lặp cùng `Idempotency-Key`: response đã lưu, **không** `issue_token` lần hai (K17)."""
    admin, target = await make_admin(db_session), await _pending_with_invite(db_session, fake_clock)
    batches = capture_mail_batches(monkeypatch)
    headers = {"Idempotency-Key": "khoa-gui-lai-01"}
    first = await send(api_client, admin, "POST", _resend(target.id), json={}, headers=headers)
    second = await send(api_client, admin, "POST", _resend(target.id), json={}, headers=headers)
    assert (first.status_code, second.status_code) == (200, 200)
    assert first.json() == second.json()
    assert await count_tokens(db_session, target.id) == 2
    assert len(batches) == 1


async def test_users_invite_users_batch_cap_counts_before_dedupe(
    api_client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Trần = 3: 4 phần tử (bỏ trùng còn 2) vẫn 422 `field:"emails"`; không tạo ai, không thư."""
    admin = await make_admin(db_session)
    batches = capture_mail_batches(monkeypatch)
    emails = ["a@example.com", "A@example.com", "b@example.com", "B@example.com"]
    with users_limits(monkeypatch, invite_batch_max=3):
        response = await send(api_client, admin, "POST", INVITE, json=_body(emails))
    assert (response.status_code, response.json()["code"], response.json()["field"]) == (422, "VALIDATION", "emails")
    assert await _users_by_email(db_session, "a@example.com", "b@example.com") == []
    assert batches == []
