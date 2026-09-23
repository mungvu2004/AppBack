"""Hàm công khai của `apps/api/auth` gọi thẳng: email, mật khẩu, cấu hình, token, phiên."""

import time
import unicodedata
from contextlib import AsyncExitStack
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from redis.exceptions import ResponseError
from sqlalchemy import CheckConstraint, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from apps.api.auth.emails import email_key, validate_wire_email
from apps.api.auth.passwords import HASH_WAIT_S, hash_password, hash_slot, needs_rehash, verify_password
from apps.api.auth.services import soft_redis
from apps.api.auth.sessions import check_session, revoke_by_cookie, revoke_sessions, start_session
from apps.api.auth.settings import get_auth_settings, reset_auth_settings_cache
from apps.api.auth.tests.support import cookie_value, session_row
from apps.api.auth.tokens import (
    next_refresh_token,
    parse_refresh_cookie,
    refresh_cookie_value,
    token_hash,
)
from packages.core.errors import AppError
from packages.core.settings import reset_settings_cache
from packages.db.base import Base
from packages.db.models.auth import RefreshSession, User
from packages.messaging.redis import AsyncRedis
from packages.testing.factories.auth import TEST_PASSWORD, make_user
from packages.testing.fixtures.clock import FakeClock


@pytest.mark.parametrize(
    ("raw", "stored"),
    [
        ("an@example.com", "an@example.com"),
        ("  Hoa.Binh+tag@Cty.VN  ", "Hoa.Binh+tag@Cty.VN"),
        ("o'neil_1-2@sub.domain.io", "o'neil_1-2@sub.domain.io"),
    ],
)
def test_wire_email_keeps_the_trimmed_form(raw: str, stored: str) -> None:
    """Email hợp lệ theo zod → bản trim (NFC); hoa thường giữ nguyên để hiển thị."""
    assert validate_wire_email(raw) == stored


def test_email_key_is_a_keyed_hash_of_the_normalized_email(auth_env: None) -> None:
    """32 ký tự hex, không phụ thuộc hoa thường/khoảng trắng, không chứa email thô."""
    key = email_key("An@Example.com")
    assert len(key) == 32
    assert int(key, 16) >= 0
    assert key == email_key("  an@example.COM ")
    assert key != email_key("binh@example.com")
    assert "example" not in key


async def test_passwords_are_compared_in_nfc(auth_env: None) -> None:
    """Băm từ NFD, kiểm bằng NFC (và ngược lại) đều khớp; mật khẩu khác thì không."""
    nfc_password = "Mật-khẩu-tiếng-Việt"  # noqa: S105 — mật khẩu giả của test
    hashed = await hash_password(unicodedata.normalize("NFD", nfc_password))
    assert await verify_password(hashed, nfc_password)
    assert not await verify_password(hashed, "mat-khau-khac-han")
    assert not needs_rehash(hashed)


async def test_no_hash_still_costs_one_verification(auth_env: None) -> None:
    """`None` (email lạ, người `pending`) → kiểm trên băm giả rồi luôn `False`."""
    assert await verify_password(None, TEST_PASSWORD) is False
    assert await verify_password(None, TEST_PASSWORD) is False


async def test_waiting_too_long_for_a_hash_slot_is_503(auth_env: None) -> None:
    """Mọi chỗ của executor băm đang bận quá `HASH_WAIT_S` → 503 `DEPENDENCY_UNAVAILABLE`."""
    async with AsyncExitStack() as held:
        for _ in range(get_auth_settings().password_hash_concurrency):
            await held.enter_async_context(hash_slot())
        started = time.monotonic()
        with pytest.raises(AppError, match="DEPENDENCY_UNAVAILABLE"):
            await hash_password(TEST_PASSWORD)
    assert time.monotonic() - started >= HASH_WAIT_S


def test_test_profile_is_refused_outside_app_env_test(auth_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """`ARGON2_PROFILE=test` với `APP_ENV=dev` → cấu hình hỏng ngay khi đọc."""
    monkeypatch.setenv("APP_ENV", "dev")
    reset_settings_cache()
    reset_auth_settings_cache()
    with pytest.raises(ValidationError, match="ARGON2_PROFILE=test"):
        get_auth_settings()


def test_limits_must_be_positive_and_within_the_charter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hạn mức 0, access token > 10 phút, cache > 5 s → cấu hình hỏng (fail-closed)."""
    for name, value in (
        ("LOGIN_FAILURE_LIMIT", "0"),
        ("ACCESS_TOKEN_TTL_S", "601"),
        ("AUTH_PRINCIPAL_CACHE_TTL_S", "6"),
    ):
        with monkeypatch.context() as scoped:
            scoped.setenv(name, value)
            reset_auth_settings_cache()
            with pytest.raises(ValidationError):
                get_auth_settings()
    reset_auth_settings_cache()


def test_refresh_chain_is_deterministic_per_key() -> None:
    """Token kế tiếp tất định, 43 ký tự base64url, đổi theo khoá; cookie khứ hồi được."""
    token = "a" * 43
    first, again = next_refresh_token(token, b"1" * 32), next_refresh_token(token, b"1" * 32)
    assert first == again
    assert len(first) == 43
    assert first != next_refresh_token(token, b"2" * 32)
    sid = uuid4()
    assert parse_refresh_cookie(refresh_cookie_value(sid, first)) == (sid, first)
    assert token_hash(first) != token_hash(token)


async def test_start_session_records_only_real_addresses(
    auth_env: None, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """`created_ip` chỉ nhận IP thật; `None` hay chuỗi lạ → không ghi."""
    user = await make_user(db_session)
    for ip in (None, "testclient"):
        sid = await start_session(db_session, Response(), user=user, remember=False, ip=ip, clock=fake_clock)
        await db_session.commit()
        assert (await session_row(db_session, sid)).created_ip is None


async def test_revoke_sessions_can_keep_the_current_one(
    auth_env: None, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """`except_sid` (đổi mật khẩu N13) giữ phiên đang dùng; lặp lại thì không còn gì để thu hồi."""
    user = await make_user(db_session)
    keep = await start_session(db_session, Response(), user=user, remember=True, ip=None, clock=fake_clock)
    other = await start_session(db_session, Response(), user=user, remember=True, ip=None, clock=fake_clock)
    await db_session.commit()
    revoked = await revoke_sessions(
        db_session, user_id=user.id, reason="password_change", clock=fake_clock, except_sid=keep
    )
    assert revoked == [other]
    assert (
        await revoke_sessions(db_session, user_id=user.id, reason="password_change", clock=fake_clock, except_sid=keep)
        == []
    )
    await db_session.commit()
    assert (await session_row(db_session, keep)).revoked_at is None
    assert (await session_row(db_session, other)).revoked_reason == "password_change"


async def test_revoke_by_cookie_ignores_what_it_cannot_match(
    auth_env: None, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Cookie thiếu, sai mẫu, hay token lạ → `None`, không thu hồi gì."""
    user = await make_user(db_session)
    response = Response()
    sid = await start_session(db_session, response, user=user, remember=True, ip=None, clock=fake_clock)
    await db_session.commit()
    cookie = cookie_value(response.headers.getlist("set-cookie")[0])
    assert await revoke_by_cookie(db_session, None, reason="logout", clock=fake_clock) is None
    assert await revoke_by_cookie(db_session, "rac", reason="logout", clock=fake_clock) is None
    stranger = refresh_cookie_value(UUID(sid), "b" * 43)
    assert await revoke_by_cookie(db_session, stranger, reason="logout", clock=fake_clock) is None
    assert await revoke_by_cookie(db_session, cookie, reason="logout", clock=fake_clock) == sid


async def test_check_session_rejects_a_malformed_sid(auth_env: None) -> None:
    """`sid` không phải UUID (B4-01 truyền từ token luồng) → 401 `SESSION_REVOKED`, không chạm DB."""
    with pytest.raises(AppError, match="SESSION_REVOKED"):
        await check_session(None, user_id="usr_x", sid="khong-phai-uuid", ver=0)  # type: ignore[arg-type]  # không được chạm tới `services`


async def test_soft_redis_raises_command_errors(cache_client: AsyncRedis) -> None:
    """Lỗi lệnh (sai kiểu khoá) là lỗi của mã: nổi lên, không bị nuốt như lỗi phụ thuộc."""
    await cache_client.rpush("khoa-danh-sach", "x")
    with pytest.raises(ResponseError, match="WRONGTYPE"):
        await soft_redis(cache_client.get("khoa-danh-sach"), "khong-duoc-log")


async def test_revocation_always_carries_a_reason(
    auth_env: None, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """`CHECK` ghép cặp: đặt `revoked_at` mà thiếu `revoked_reason` (module khác ghi sai) → DB từ chối."""
    user = await make_user(db_session)
    sid = await start_session(db_session, Response(), user=user, remember=True, ip=None, clock=fake_clock)
    await db_session.commit()
    with pytest.raises(IntegrityError, match="revoked_pair"):
        await db_session.execute(
            update(RefreshSession).where(RefreshSession.id == UUID(sid)).values(revoked_at=fake_clock.now())
        )
    await db_session.rollback()


async def test_check_constraint_names_match_the_model(auth_env: None, db_session: AsyncSession) -> None:
    """Tên `CHECK` trong DB (sau migration) đúng bằng tên model dựng theo quy ước — không ghép tiền tố hai lần."""
    rows = await db_session.execute(
        text(
            "SELECT conname FROM pg_constraint WHERE contype = 'c' "
            "AND conrelid IN ('users'::regclass, 'refresh_sessions'::regclass)"
        )
    )
    in_model = {
        str(constraint.name)
        for table in (Base.metadata.tables[User.__tablename__], Base.metadata.tables[RefreshSession.__tablename__])
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert {row[0] for row in rows} == in_model
    assert "ck_users_role" in in_model
