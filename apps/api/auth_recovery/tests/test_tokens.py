"""Test `apps/api/auth_recovery/tokens.py`: sinh, tra, dùng, thu hồi token; đăng ký gửi thư (B1-03)."""

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import Executable, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.auth_recovery import tokens
from apps.api.auth_recovery.settings import get_recovery_settings, reset_recovery_settings_cache
from apps.api.auth_recovery.tests.support import seed_token
from apps.api.auth_recovery.tokens import (
    active_clause,
    consume_token,
    derive_token,
    find_active_token,
    hash_token,
    issue_token,
    latest_invitations,
    revoke_tokens,
)
from packages.core.clock import Clock, SystemClock
from packages.core.ids import new_id
from packages.db.hooks import after_commit_idle
from packages.db.models.auth_recovery import NONCE_LEN, OneTimeToken, TokenPurpose
from packages.messaging.payloads.auth_recovery import MAX_TOKEN_IDS, SendTokenMailPayload
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.clock import FakeClock

pytestmark = pytest.mark.usefixtures("api_env")


def _patch_send(monkeypatch: pytest.MonkeyPatch) -> list[SendTokenMailPayload]:
    """Thay `send_task` của module `tokens` bằng hàm ghi lại — đường nối riêng của bài test, không mock Redis."""
    sent: list[SendTokenMailPayload] = []

    def fake_send_task(name: str, payload: SendTokenMailPayload) -> None:
        assert name == tokens.SEND_TOKEN_MAIL_TASK
        sent.append(payload)

    monkeypatch.setattr(tokens, "send_task", fake_send_task)
    return sent


@contextmanager
def _count_executes(db: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> Iterator[list[int]]:
    """Đếm số lần `db.execute` chạy trong khối `with` — kiểm không N+1 (R-20)."""
    counter = [0]
    original_execute = db.execute

    async def counting_execute(statement: Executable, *args: Any, **kwargs: Any) -> Any:
        counter[0] += 1
        return await original_execute(statement, *args, **kwargs)

    monkeypatch.setattr(db, "execute", counting_execute)
    yield counter


async def _active_count(db: AsyncSession, *, user_id: str, purpose: TokenPurpose, clock: Clock) -> int:
    rows = await db.execute(
        select(OneTimeToken.id).where(
            OneTimeToken.user_id == user_id, OneTimeToken.purpose == purpose, active_clause(clock.now())
        )
    )
    return len(rows.all())


# --- derive_token / hash_token -----------------------------------------------------------


def test_derive_token_is_43_chars_and_deterministic() -> None:
    """Cùng đầu vào → cùng token, đúng 43 ký tự (base64url, không đệm `=`)."""
    key = b"k" * 32
    nonce = b"n" * NONCE_LEN
    token = derive_token(key, token_id="tok_A", purpose="invite", nonce=nonce)  # noqa: S106 — id giả của test
    assert len(token) == 43
    assert "=" not in token
    assert derive_token(key, token_id="tok_A", purpose="invite", nonce=nonce) == token  # noqa: S106 — id giả


def test_derive_token_changes_with_key_nonce_or_purpose() -> None:
    """Đổi khoá, nonce, hay mục đích → token khác (không đụng nhau khi xoay khoá)."""
    key, nonce = b"k" * 32, b"n" * NONCE_LEN
    base = derive_token(key, token_id="tok_A", purpose="invite", nonce=nonce)  # noqa: S106 — id giả của test
    assert derive_token(b"z" * 32, token_id="tok_A", purpose="invite", nonce=nonce) != base  # noqa: S106
    assert derive_token(key, token_id="tok_A", purpose="invite", nonce=b"m" * NONCE_LEN) != base  # noqa: S106
    assert derive_token(key, token_id="tok_A", purpose="password_reset", nonce=nonce) != base  # noqa: S106


def test_hash_token_is_64_hex_chars() -> None:
    digest = hash_token("bat-ky-token-nao")
    assert len(digest) == 64
    assert int(digest, 16) >= 0


# --- issue_token --------------------------------------------------------------------------


async def test_issue_token_supersedes_previous_same_purpose_only(
    db_session: AsyncSession, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lần hai cùng `(user, purpose)` vô hiệu token cũ; mục đích khác không bị đụng."""
    _patch_send(monkeypatch)
    user = await make_user(db_session)
    first = await issue_token(db_session, user_id=user.id, purpose="password_reset", clock=fake_clock)
    await db_session.commit()
    second = await issue_token(db_session, user_id=user.id, purpose="password_reset", clock=fake_clock)
    await db_session.commit()
    await db_session.refresh(first)
    assert first.superseded_at is not None
    assert await _active_count(db_session, user_id=user.id, purpose="password_reset", clock=fake_clock) == 1

    invite = await issue_token(db_session, user_id=user.id, purpose="invite", clock=fake_clock)
    await db_session.commit()
    await db_session.refresh(second)
    assert second.superseded_at is None
    assert invite.superseded_at is None


async def test_issue_token_expires_at_matches_purpose_ttl(
    db_session: AsyncSession, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`expires_at` = lúc phát + TTL đúng theo `RecoverySettings` của từng mục đích."""
    _patch_send(monkeypatch)
    user = await make_user(db_session)
    settings = get_recovery_settings()
    invite = await issue_token(db_session, user_id=user.id, purpose="invite", clock=fake_clock)
    reset_token = await issue_token(db_session, user_id=user.id, purpose="password_reset", clock=fake_clock)
    await db_session.commit()
    assert invite.expires_at == fake_clock.now() + timedelta(hours=settings.invite_ttl_h)
    assert reset_token.expires_at == fake_clock.now() + timedelta(minutes=settings.password_reset_ttl_min)


async def test_issue_token_concurrent_same_user_keeps_one_active(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hai giao dịch thật cùng phát token cho một người → sau khi cả hai commit, đúng một token còn hiệu lực."""
    _patch_send(monkeypatch)
    async with db_sessionmaker() as setup:
        user = await make_user(setup)

    async def run() -> None:
        async with db_sessionmaker() as db:
            await issue_token(db, user_id=user.id, purpose="password_reset", clock=fake_clock)
            await db.commit()
            await after_commit_idle(db)

    await asyncio.gather(run(), run())

    async with db_sessionmaker() as check:
        assert await _active_count(check, user_id=user.id, purpose="password_reset", clock=fake_clock) == 1


# --- callback sau commit (gửi thư theo lô) -------------------------------------------------


async def test_issue_token_batches_one_send_task_per_transaction(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ba `issue_token` (ba người) trong một giao dịch → đúng một `send_task` với ba id.

    Người dùng tạo trên session riêng (`make_user` tự commit), tách khỏi giao dịch đang so.
    """
    sent = _patch_send(monkeypatch)
    async with db_sessionmaker() as setup:
        users = [await make_user(setup) for _ in range(3)]

    async with db_sessionmaker() as db:
        issued = [await issue_token(db, user_id=user.id, purpose="invite", clock=fake_clock) for user in users]
        assert sent == []  # chưa commit, chưa gửi (K17)
        await db.commit()
        await after_commit_idle(db)
    assert len(sent) == 1
    assert sorted(sent[0].token_ids) == sorted(row.id for row in issued)


async def test_issue_token_rollback_drops_pending_without_leaking(
    db_session: AsyncSession, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rollback không gửi; giao dịch kế tiếp trên cùng session không mang id đã bỏ."""
    sent = _patch_send(monkeypatch)
    dropped_user = await make_user(db_session)
    await issue_token(db_session, user_id=dropped_user.id, purpose="invite", clock=fake_clock)
    await db_session.rollback()
    await after_commit_idle(db_session)
    assert sent == []

    kept_user = await make_user(db_session)
    kept = await issue_token(db_session, user_id=kept_user.id, purpose="invite", clock=fake_clock)
    await db_session.commit()
    await after_commit_idle(db_session)
    assert len(sent) == 1
    assert sent[0].token_ids == [kept.id]


async def test_issue_token_sends_in_batches_of_max_50(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hơn `MAX_TOKEN_IDS` id trong một giao dịch → nhiều lô, mỗi lô tối đa `MAX_TOKEN_IDS`."""
    sent = _patch_send(monkeypatch)
    async with db_sessionmaker() as setup:
        user = await make_user(setup)

    total = MAX_TOKEN_IDS + 1
    async with db_sessionmaker() as db:
        for _ in range(total):
            await issue_token(db, user_id=user.id, purpose="invite", clock=fake_clock)
        await db.commit()
        await after_commit_idle(db)
    assert [len(payload.token_ids) for payload in sent] == [MAX_TOKEN_IDS, 1]
    assert sum(len(payload.token_ids) for payload in sent) == total


# --- latest_invitations --------------------------------------------------------------------


async def test_latest_invitations_returns_latest_unused_even_expired(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Lấy lời mời `invite` mới nhất chưa dùng/chưa bị thay, kể cả đã hết hạn; loại đã dùng/bị thay."""
    fresh_user = await make_user(db_session)
    expired_user = await make_user(db_session)
    used_user = await make_user(db_session)
    superseded_user = await make_user(db_session)
    none_user = await make_user(db_session)

    older_row, _ = await seed_token(db_session, user_id=fresh_user.id, purpose="invite", clock=fake_clock, commit=False)
    older_row.superseded_at = fake_clock.now()  # một người chỉ có một invite còn hiệu lực (ACTIVE_UNIQUE)
    await db_session.flush()
    expired_row, _ = await seed_token(
        db_session, user_id=expired_user.id, purpose="invite", clock=fake_clock, ttl=timedelta(seconds=-1), commit=False
    )
    await seed_token(
        db_session, user_id=used_user.id, purpose="invite", clock=fake_clock, used_at=fake_clock.now(), commit=False
    )
    await seed_token(
        db_session,
        user_id=superseded_user.id,
        purpose="invite",
        clock=fake_clock,
        superseded_at=fake_clock.now(),
        commit=False,
    )
    fake_clock.advance(timedelta(minutes=5))
    newer_row, _ = await seed_token(db_session, user_id=fresh_user.id, purpose="invite", clock=fake_clock, commit=False)
    await db_session.commit()

    result = await latest_invitations(
        db_session, [fresh_user.id, expired_user.id, used_user.id, superseded_user.id, none_user.id]
    )

    assert set(result) == {fresh_user.id, expired_user.id}
    assert result[fresh_user.id].invited_at == newer_row.created_at
    assert result[expired_user.id].expires_at == expired_row.expires_at


async def test_latest_invitations_empty_input_runs_no_query(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`user_ids` rỗng → `{}`, không chạm DB."""
    with _count_executes(db_session, monkeypatch) as counter:
        assert await latest_invitations(db_session, []) == {}
    assert counter[0] == 0


async def test_latest_invitations_runs_a_single_query(
    db_session: AsyncSession, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nhiều người trong một lệnh gọi vẫn chỉ một câu `SELECT` (không N+1, R-20)."""
    users = [await make_user(db_session) for _ in range(3)]
    for user in users:
        await seed_token(db_session, user_id=user.id, purpose="invite", clock=fake_clock, commit=False)
    await db_session.commit()

    with _count_executes(db_session, monkeypatch) as counter:
        result = await latest_invitations(db_session, [user.id for user in users])
    assert counter[0] == 1
    assert set(result) == {user.id for user in users}


# --- revoke_tokens / find_active_token / consume_token --------------------------------------


async def test_revoke_tokens_by_purpose_then_all(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    user = await make_user(db_session)
    invite, _ = await seed_token(db_session, user_id=user.id, purpose="invite", clock=fake_clock, commit=False)
    reset_row, _ = await seed_token(
        db_session, user_id=user.id, purpose="password_reset", clock=fake_clock, commit=False
    )
    await db_session.commit()

    await revoke_tokens(db_session, user_id=user.id, clock=fake_clock, purpose="invite")
    await db_session.commit()
    await db_session.refresh(invite)
    await db_session.refresh(reset_row)
    assert invite.superseded_at is not None
    assert reset_row.superseded_at is None

    await revoke_tokens(db_session, user_id=user.id, clock=fake_clock)
    await db_session.commit()
    await db_session.refresh(reset_row)
    assert reset_row.superseded_at is not None


async def test_find_active_token_rejects_wrong_purpose_value_or_window(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    user = await make_user(db_session)
    _, plain = await seed_token(db_session, user_id=user.id, purpose="password_reset", clock=fake_clock, commit=False)
    await db_session.commit()
    now = fake_clock.now()

    assert await find_active_token(db_session, token=plain, purpose="password_reset", now=now) is not None
    assert await find_active_token(db_session, token=plain, purpose="invite", now=now) is None
    assert await find_active_token(db_session, token="x" * 43, purpose="password_reset", now=now) is None
    later = now + timedelta(hours=2)
    assert await find_active_token(db_session, token=plain, purpose="password_reset", now=later) is None


async def test_consume_token_wins_once_then_loses(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    user = await make_user(db_session)
    row, _ = await seed_token(db_session, user_id=user.id, purpose="invite", clock=fake_clock, commit=False)
    await db_session.commit()
    now = fake_clock.now()

    assert await consume_token(db_session, token_id=row.id, now=now) is True
    await db_session.commit()
    assert await consume_token(db_session, token_id=row.id, now=now) is False


async def test_consume_token_false_when_expired_or_superseded(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    user = await make_user(db_session)
    now = fake_clock.now()
    expired, _ = await seed_token(
        db_session, user_id=user.id, purpose="invite", clock=fake_clock, ttl=timedelta(seconds=-1), commit=False
    )
    superseded, _ = await seed_token(
        db_session, user_id=user.id, purpose="password_reset", clock=fake_clock, superseded_at=now, commit=False
    )
    await db_session.commit()

    assert await consume_token(db_session, token_id=expired.id, now=now) is False
    assert await consume_token(db_session, token_id=superseded.id, now=now) is False


# --- SendTokenMailPayload --------------------------------------------------------------------


def test_send_token_mail_payload_bounds_and_id_format() -> None:
    good_id = new_id("tok", SystemClock())
    assert SendTokenMailPayload(token_ids=[good_id]).token_ids == [good_id]
    with pytest.raises(ValidationError):
        SendTokenMailPayload(token_ids=[])
    with pytest.raises(ValidationError):
        SendTokenMailPayload(token_ids=[new_id("tok", SystemClock()) for _ in range(MAX_TOKEN_IDS + 1)])
    with pytest.raises(ValidationError):
        SendTokenMailPayload(token_ids=[new_id("usr", SystemClock())])


# --- RecoverySettings --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "INVITE_TTL_H",
        "PASSWORD_RESET_TTL_MIN",
        "PASSWORD_RESET_COOLDOWN_MIN",
        "RECOVERY_IP_LIMIT",
        "RECOVERY_IP_WINDOW_S",
        "TOKEN_PURGE_AFTER_D",
        "RESEND_UNSENT_AFTER_S",
    ],
)
def test_recovery_settings_reject_non_positive(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    for bad in ("0", "-1"):
        with monkeypatch.context() as scoped:
            scoped.setenv(name, bad)
            reset_recovery_settings_cache()
            with pytest.raises(ValidationError):
                get_recovery_settings()
    reset_recovery_settings_cache()
