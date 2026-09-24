"""Lịch gửi thư token, gửi lại thư chưa gửi, dọn token cũ (B1-03 [6], BE-00 §7, J01-J03, J06, J09)."""

import asyncio
import logging
import subprocess
import sys
from collections.abc import Awaitable, Callable, Iterator
from datetime import timedelta
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.auth_recovery import jobs, tokens
from apps.api.auth_recovery.jobs import (
    MAIL_REJECTED,
    PURGE_TOKENS_TASK,
    RESEND_UNSENT_TASK,
    TOKEN_KEY_ROTATED,
    purge_tokens,
    resend_unsent,
    run_purge_tokens,
    run_resend_unsent,
    run_send_token_mail,
    send_token_mail,
)
from apps.api.auth_recovery.settings import get_recovery_settings
from apps.api.auth_recovery.tests.support import seed_token
from apps.api.auth_recovery.tokens import SEND_TOKEN_MAIL_TASK, hash_token
from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.core.settings import reset_settings_cache
from packages.db.engine import GATE_CONNECT_TIMEOUT_S, create_engine, create_sessionmaker
from packages.db.hooks import after_commit_idle
from packages.db.models.auth_recovery import OneTimeToken
from packages.db.settings import DatabaseSettings, reset_database_settings_cache
from packages.mail.message import MailMessage
from packages.mail.sender import MailTransientError, MemoryMailer
from packages.mail.settings import reset_mail_settings_cache
from packages.messaging.celery_app import queue_for
from packages.messaging.payloads.auth_recovery import SendTokenMailPayload
from packages.messaging.redis import broker_redis_sync
from packages.messaging.schedules import schedule_entries
from packages.messaging.tasks import PermanentError, TransientError
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.mail import MailpitInbox, extract_token
from packages.testing.fixtures.messaging import queued_payloads
from packages.testing.fixtures.services import refused_url
from packages.testing.fixtures.storage import PUBLIC_BASE_URL, STORAGE_SECRET

REPO_ROOT: Final = Path(__file__).resolve().parents[4]
WORKER_BLOCKED: Final = ("fastapi", "starlette", "jwt", "argon2")
ROTATED_SECRET: Final = "khoa-moi-sau-khi-xoay-0000000000000"  # noqa: S105 — khoá giả của test
OTHER_SECRET: Final = "khoa-hoan-toan-khac-vong-xoay-000000"  # noqa: S105 — khoá giả của test


@pytest.fixture(autouse=True)
def _core_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """`get_core_settings()` cần `APP_ENV`/`PUBLIC_BASE_URL`/`SECRET_KEY` để đọc được (B0-06)."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("PUBLIC_BASE_URL", PUBLIC_BASE_URL)
    monkeypatch.setenv("SECRET_KEY", STORAGE_SECRET)
    monkeypatch.delenv("SECRET_KEY_PREVIOUS", raising=False)
    reset_settings_cache()
    yield
    reset_settings_cache()


# --- send_token_mail — lõi ------------------------------------------------------------------


async def test_send_token_mail__J01(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock, mailpit_inbox: MailpitInbox
) -> None:
    """Gửi đúng: link đúng mẫu, `sent_at` được ghi, `subject` không chứa tên người nhận."""
    async with db_sessionmaker() as setup:
        user = await make_user(setup, name="Trần Thị B")
        row, _ = await seed_token(setup, user_id=user.id, purpose="invite", clock=fake_clock)

    sent = await run_send_token_mail(db_sessionmaker, fake_clock, [row.id])

    assert sent == 1
    message = mailpit_inbox.wait_for(user.email, timeout_s=5)
    assert user.name not in str(message["Subject"])
    link_token = extract_token(message)
    assert hash_token(link_token) == row.token_hash
    assert f"{PUBLIC_BASE_URL}/login/invitation#token=" in str(message["Text"])

    async with db_sessionmaker() as check:
        refreshed = await check.get(OneTimeToken, row.id)
    assert refreshed is not None
    assert refreshed.sent_at is not None


async def test_send_token_mail__J06(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock, memory_mailer: MemoryMailer
) -> None:
    """Token đã gửi hay đã bị thay bị bỏ ngay; giao lại sau khi gửi xong không gửi trùng."""
    async with db_sessionmaker() as setup:
        already_sent_user = await make_user(setup)
        superseded_user = await make_user(setup)
        fresh_user = await make_user(setup)
        already_sent, _ = await seed_token(
            setup, user_id=already_sent_user.id, purpose="invite", clock=fake_clock, sent_at=fake_clock.now()
        )
        superseded, _ = await seed_token(
            setup, user_id=superseded_user.id, purpose="invite", clock=fake_clock, superseded_at=fake_clock.now()
        )
        fresh, _ = await seed_token(setup, user_id=fresh_user.id, purpose="invite", clock=fake_clock)

    ids = [already_sent.id, superseded.id, fresh.id]
    sent = await run_send_token_mail(db_sessionmaker, fake_clock, ids)
    assert sent == 1
    assert len(memory_mailer.sent) == 1

    resent = await run_send_token_mail(db_sessionmaker, fake_clock, ids)
    assert resent == 0
    assert len(memory_mailer.sent) == 1


async def test_send_token_mail__J02(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SMTP không nối được → `MailTransientError` ánh xạ thành `TransientError` (J02, task sẽ thử lại)."""
    async with db_sessionmaker() as setup:
        user = await make_user(setup)
        row, _ = await seed_token(setup, user_id=user.id, purpose="invite", clock=fake_clock)

    parts = urlsplit(refused_url("smtp"))
    monkeypatch.setenv("MAIL_BACKEND", "smtp")
    monkeypatch.setenv("SMTP_HOST", parts.hostname or "127.0.0.1")
    monkeypatch.setenv("SMTP_PORT", str(parts.port))
    monkeypatch.setenv("SMTP_STARTTLS", "false")
    monkeypatch.setenv("MAIL_FROM", "no-reply@appback.test")
    reset_mail_settings_cache()

    with pytest.raises(TransientError):
        await run_send_token_mail(db_sessionmaker, fake_clock, [row.id])


async def test_send_token_mail__J03(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
    smtp_reject_server: tuple[str, int],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Người nhận bị SMTP từ chối hẳn (550) → `PermanentError(MAIL_REJECTED)`, không thử lại.

    NO-149a: log `token_mail_failed` phải giữ `smtp_code` (550) — trước sửa, `except MailRejectedError`
    không đọc `exc.smtp_code` nên log không phân biệt được 550 với 554.
    """
    async with db_sessionmaker() as setup:
        user = await make_user(setup)
        row, _ = await seed_token(setup, user_id=user.id, purpose="password_reset", clock=fake_clock)

    host, port = smtp_reject_server
    monkeypatch.setenv("MAIL_BACKEND", "smtp")
    monkeypatch.setenv("SMTP_HOST", host)
    monkeypatch.setenv("SMTP_PORT", str(port))
    monkeypatch.setenv("SMTP_STARTTLS", "false")
    monkeypatch.setenv("MAIL_FROM", "no-reply@appback.test")
    reset_mail_settings_cache()

    with caplog.at_level(logging.ERROR), pytest.raises(PermanentError) as excinfo:
        await run_send_token_mail(db_sessionmaker, fake_clock, [row.id])
    assert excinfo.value.code == MAIL_REJECTED

    record = next(r for r in caplog.records if r.msg == "token_mail_failed" and r.token_id == row.id)  # type: ignore[attr-defined]
    assert record.smtp_code == 550  # type: ignore[attr-defined]

    async with db_sessionmaker() as check:
        refreshed = await check.get(OneTimeToken, row.id)
    assert refreshed is not None
    assert refreshed.sent_at is not None  # NO-143: cô lập khỏi resend_unsent dù chưa tới hộp thư


async def test_send_token_mail__J01_isolates_bad_token_from_batch(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock, memory_mailer: MemoryMailer
) -> None:
    """NO-143: một token hỏng vĩnh viễn không giết cả lô — token tốt **sau** nó trong lô vẫn tới.

    Trên mã cũ (trước NO-143), `run_send_token_mail` ném `PermanentError` ngay ở token đầu hỏng,
    nên `good_row` không bao giờ được gửi và `memory_mailer.sent` rỗng — test này đỏ trên mã đó.
    Token hỏng bị cô lập (`superseded_at`) nên `run_resend_unsent` không dựng lại nó nữa.
    """
    async with db_sessionmaker() as setup:
        bad_user = await make_user(setup)
        good_user = await make_user(setup)
        bad_row, _ = await seed_token(setup, user_id=bad_user.id, purpose="invite", clock=fake_clock)
        good_row, _ = await seed_token(setup, user_id=good_user.id, purpose="invite", clock=fake_clock)
    async with db_sessionmaker() as corrupt:
        # Không khoá nào (hiện tại hay cũ) còn khớp — mô phỏng khoá đã rơi khỏi `SECRET_KEY_PREVIOUS`.
        await corrupt.execute(update(OneTimeToken).where(OneTimeToken.id == bad_row.id).values(token_hash="0" * 64))
        await corrupt.commit()

    with pytest.raises(PermanentError) as excinfo:
        await run_send_token_mail(db_sessionmaker, fake_clock, [bad_row.id, good_row.id])
    assert excinfo.value.code == TOKEN_KEY_ROTATED

    assert len(memory_mailer.sent) == 1
    assert memory_mailer.sent[0].to == good_user.email

    async with db_sessionmaker() as check:
        bad_after = await check.get(OneTimeToken, bad_row.id)
        good_after = await check.get(OneTimeToken, good_row.id)
    assert bad_after is not None
    assert bad_after.superseded_at is not None
    assert good_after is not None
    assert good_after.sent_at is not None

    requeued = await run_resend_unsent(db_sessionmaker, fake_clock)
    assert requeued == 0  # token hỏng đã superseded — không còn "active", không bị dựng lại


async def test_send_token_mail__logs_isolated_failure_before_later_transient(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    memory_mailer: MemoryMailer,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """NO-149b: mã lỗi vĩnh viễn của token đầu không bị nuốt khi token SAU nó ném `TransientError`.

    Trên mã cũ, `run_send_token_mail` chỉ ném `PermanentError(first_failure)` **sau khi hết vòng**;
    `TransientError` của `transient_row` nổi lên trước, làm dòng đó không bao giờ chạy tới — không
    ai log token hỏng của `bad_row`. Test này đỏ trên mã đó (không tìm thấy bản ghi log) vì log chỉ
    tồn tại ở cuối vòng.
    """
    async with db_sessionmaker() as setup:
        bad_user = await make_user(setup)
        transient_user = await make_user(setup)
        bad_row, _ = await seed_token(
            setup, user_id=bad_user.id, purpose="invite", clock=fake_clock, created_at=fake_clock.now()
        )
        fake_clock.advance(timedelta(seconds=1))
        transient_row, _ = await seed_token(
            setup, user_id=transient_user.id, purpose="invite", clock=fake_clock, created_at=fake_clock.now()
        )
    async with db_sessionmaker() as corrupt:
        # Không khoá nào còn khớp — cô lập ngay ở `_resolve_plain_token`, trước khi chạm mailer.
        await corrupt.execute(update(OneTimeToken).where(OneTimeToken.id == bad_row.id).values(token_hash="0" * 64))
        await corrupt.commit()

    class _TransientMailer:
        def send(self, message: MailMessage) -> None:
            raise MailTransientError(451)

    monkeypatch.setattr(jobs, "create_mailer", lambda _settings: _TransientMailer())

    with caplog.at_level(logging.ERROR), pytest.raises(TransientError):
        await run_send_token_mail(db_sessionmaker, fake_clock, [bad_row.id, transient_row.id])

    record = next(
        (r for r in caplog.records if r.msg == "token_mail_failed" and getattr(r, "token_id", None) == bad_row.id),
        None,
    )
    assert record is not None
    assert record.code == TOKEN_KEY_ROTATED  # type: ignore[attr-defined]
    assert record.smtp_code is None  # type: ignore[attr-defined]

    async with db_sessionmaker() as check:
        bad_after = await check.get(OneTimeToken, bad_row.id)
    assert bad_after is not None
    assert bad_after.superseded_at is not None  # cô lập đã ghi dù batch cuối cùng ném TransientError


def test_send_token_mail_task_is_registered_under_tokens_constant() -> None:
    """Tên task Celery khớp hằng `SEND_TOKEN_MAIL_TASK` mà `tokens.py` dùng để gửi (`issue_token`)."""
    assert send_token_mail.name == SEND_TOKEN_MAIL_TASK


def test_on_send_token_mail_failed_logs_only_ids_and_code(caplog: pytest.LogCaptureFixture) -> None:
    """`on_failed` chỉ ghi `token_ids` và mã, không email/token/link (K11)."""
    payload = SendTokenMailPayload(token_ids=[new_id("tok", SystemClock())])

    with caplog.at_level(logging.ERROR):
        jobs._on_send_token_mail_failed(payload, MAIL_REJECTED)

    record = next(r for r in caplog.records if r.msg == "token_mail_failed")
    assert record.token_ids == payload.token_ids  # type: ignore[attr-defined]
    assert record.code == MAIL_REJECTED  # type: ignore[attr-defined]


async def _seed_on_url[ResultT](db_url: str, work: Callable[[AsyncSession], Awaitable[ResultT]]) -> ResultT:
    """Chạy `work` trên engine riêng của vòng `asyncio.run` hiện tại (test đồng bộ gọi `.apply()`).

    Task chạy qua `.apply()` tự có vòng sự kiện riêng (`asyncio.Runner`); test seed dữ liệu bằng
    một vòng `asyncio.run` khác, tách biệt, nên không đụng "vòng đang chạy" của `Runner.run()`.
    """
    engine = create_engine(DatabaseSettings(database_url=db_url, db_connect_timeout_s=int(GATE_CONNECT_TIMEOUT_S)))
    try:
        async with create_sessionmaker(engine)() as session:
            return await work(session)
    finally:
        await engine.dispose()


def test_send_token_mail_task_wiring_smoke(
    db_url: str, messaging_env: None, memory_mailer: MemoryMailer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`.apply()` chạy hàm task mỏng thật (`worker_sessionmaker()`/`SystemClock()`), phủ dòng gọi lõi.

    Test đồng bộ (không `async def`): xem docstring `_seed_on_url`. Token seed bằng `SystemClock()`
    thật (không `fake_clock`): hàm task mỏng dùng giờ thật, `expires_at` phải nằm trong tương lai
    thật để token còn hiệu lực lúc task chạy.
    """

    async def _seed(session: AsyncSession) -> OneTimeToken:
        user = await make_user(session)
        row, _ = await seed_token(session, user_id=user.id, purpose="invite", clock=SystemClock())
        return row

    row = asyncio.run(_seed_on_url(db_url, _seed))
    monkeypatch.setenv("DATABASE_URL", db_url)
    reset_database_settings_cache()
    try:
        payload = SendTokenMailPayload(token_ids=[row.id])
        result = send_token_mail.apply(args=[payload.model_dump(mode="json")])
        assert result.state == "SUCCESS"
        assert len(memory_mailer.sent) == 1
    finally:
        reset_database_settings_cache()


async def test_send_token_mail_rotated_key_still_resolves(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    memory_mailer: MemoryMailer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Token phát bằng khoá cũ vẫn gửi được khi khoá cũ chuyển sang `SECRET_KEY_PREVIOUS`."""
    async with db_sessionmaker() as setup:
        user = await make_user(setup)
        row, plain = await seed_token(setup, user_id=user.id, purpose="password_reset", clock=fake_clock)

    monkeypatch.setenv("SECRET_KEY", ROTATED_SECRET)
    monkeypatch.setenv("SECRET_KEY_PREVIOUS", STORAGE_SECRET)
    reset_settings_cache()

    sent = await run_send_token_mail(db_sessionmaker, fake_clock, [row.id])

    assert sent == 1
    assert extract_token(memory_mailer.sent[0]) == plain


async def test_send_token_mail_key_mismatch_raises_rotated(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    memory_mailer: MemoryMailer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Không khoá nào (hiện tại hay cũ) khớp `token_hash` → `PermanentError(TOKEN_KEY_ROTATED)`."""
    async with db_sessionmaker() as setup:
        user = await make_user(setup)
        row, _ = await seed_token(setup, user_id=user.id, purpose="invite", clock=fake_clock)

    monkeypatch.setenv("SECRET_KEY", OTHER_SECRET)
    monkeypatch.delenv("SECRET_KEY_PREVIOUS", raising=False)
    reset_settings_cache()

    with pytest.raises(PermanentError) as excinfo:
        await run_send_token_mail(db_sessionmaker, fake_clock, [row.id])
    assert excinfo.value.code == TOKEN_KEY_ROTATED


# --- resend_unsent ----------------------------------------------------------------------------


async def test_resend_unsent__J01(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock, messaging_env: None
) -> None:
    """Token còn hiệu lực, chưa gửi, tạo quá `resend_unsent_after_s` → xếp lại gửi."""
    settings = get_recovery_settings()
    async with db_sessionmaker() as setup:
        user = await make_user(setup)
        old_row, _ = await seed_token(
            setup,
            user_id=user.id,
            purpose="invite",
            clock=fake_clock,
            created_at=fake_clock.now() - timedelta(seconds=settings.resend_unsent_after_s + 1),
        )

    queue = queue_for(SEND_TOKEN_MAIL_TASK)
    client = broker_redis_sync()
    try:
        client.delete(queue)
        queued = await run_resend_unsent(db_sessionmaker, fake_clock)
        assert queued == 1
        payloads = queued_payloads(client, queue)
        assert payloads == [{"schema_version": 1, "token_ids": [old_row.id]}]
    finally:
        client.close()


async def test_resend_unsent__J06(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    messaging_env: None,
    memory_mailer: MemoryMailer,
) -> None:
    """Token mới hơn `resend_unsent_after_s` chưa được chọn; token đã gửi rồi không bị quét lại."""
    settings = get_recovery_settings()
    async with db_sessionmaker() as setup:
        old_user = await make_user(setup)
        new_user = await make_user(setup)
        old_row, _ = await seed_token(
            setup,
            user_id=old_user.id,
            purpose="invite",
            clock=fake_clock,
            created_at=fake_clock.now() - timedelta(seconds=settings.resend_unsent_after_s + 1),
        )
        await seed_token(
            setup,
            user_id=new_user.id,
            purpose="invite",
            clock=fake_clock,
            created_at=fake_clock.now() - timedelta(seconds=settings.resend_unsent_after_s - 1),
        )

    queued_first = await run_resend_unsent(db_sessionmaker, fake_clock)
    assert queued_first == 1  # chỉ token cũ, token mới chưa tới hạn

    await run_send_token_mail(db_sessionmaker, fake_clock, [old_row.id])
    queued_second = await run_resend_unsent(db_sessionmaker, fake_clock)
    assert queued_second == 0  # token cũ đã có sent_at, không bị chọn lại


def test_resend_unsent_smoke(db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test khói: gọi hàm lịch thật (`SystemClock()`, `worker_sessionmaker()`); DB rỗng nên không gửi gì."""
    monkeypatch.setenv("DATABASE_URL", db_url)
    reset_database_settings_cache()
    try:
        resend_unsent()
    finally:
        reset_database_settings_cache()


def test_resend_unsent_schedule_is_registered() -> None:
    entries = {entry.name: entry for entry in schedule_entries()}
    assert entries[RESEND_UNSENT_TASK].function == "resend_unsent"


# --- purge_tokens -------------------------------------------------------------------------------


async def test_purge_tokens__J01(db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock) -> None:
    """Xoá token dùng/hết hạn/bị thay quá `token_purge_after_d`; giữ token còn trong hạn."""
    settings = get_recovery_settings()
    overdue = timedelta(days=settings.token_purge_after_d) + timedelta(seconds=1)
    async with db_sessionmaker() as setup:
        user = await make_user(setup)
        doomed, _ = await seed_token(
            setup, user_id=user.id, purpose="invite", clock=fake_clock, used_at=fake_clock.now() - overdue
        )
        kept, _ = await seed_token(setup, user_id=user.id, purpose="password_reset", clock=fake_clock)

    removed = await run_purge_tokens(db_sessionmaker, fake_clock)

    assert removed == 1
    async with db_sessionmaker() as check:
        assert await check.get(OneTimeToken, doomed.id) is None
        assert await check.get(OneTimeToken, kept.id) is not None


async def test_purge_tokens__J06(db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock) -> None:
    """Giao lặp: lượt thứ hai không xoá thêm gì."""
    settings = get_recovery_settings()
    overdue = timedelta(days=settings.token_purge_after_d) + timedelta(seconds=1)
    async with db_sessionmaker() as setup:
        user = await make_user(setup)
        await seed_token(
            setup, user_id=user.id, purpose="invite", clock=fake_clock, superseded_at=fake_clock.now() - overdue
        )

    assert await run_purge_tokens(db_sessionmaker, fake_clock) == 1
    assert await run_purge_tokens(db_sessionmaker, fake_clock) == 0


async def test_purge_tokens_runs_in_batches(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Lô nhỏ hơn số dòng phải xoá: vòng lặp chạy tiếp cho tới hết."""
    settings = get_recovery_settings()
    overdue = timedelta(days=settings.token_purge_after_d) + timedelta(seconds=1)
    async with db_sessionmaker() as setup:
        user = await make_user(setup)
        for _ in range(3):
            await seed_token(
                setup, user_id=user.id, purpose="invite", clock=fake_clock, used_at=fake_clock.now() - overdue
            )
            fake_clock.advance(timedelta(seconds=1))

    assert await run_purge_tokens(db_sessionmaker, fake_clock, batch=1) == 3


def test_purge_tokens_smoke(db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test khói: gọi hàm lịch thật (`SystemClock()`, `worker_sessionmaker()`); DB rỗng nên không xoá gì."""
    monkeypatch.setenv("DATABASE_URL", db_url)
    reset_database_settings_cache()
    try:
        purge_tokens()
    finally:
        reset_database_settings_cache()


def test_purge_tokens_schedule_is_registered() -> None:
    entries = {entry.name: entry for entry in schedule_entries()}
    assert entries[PURGE_TOKENS_TASK].function == "purge_tokens"


# --- payload không mang bí mật, J09 --------------------------------------------------------------


async def test_issued_token_payload_carries_no_secrets(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock, messaging_env: None
) -> None:
    """Sau `issue_token` + commit, thông điệp thô trên broker không chứa token, email hay `#token=`."""
    queue = queue_for(SEND_TOKEN_MAIL_TASK)
    client = broker_redis_sync()
    try:
        client.delete(queue)
        async with db_sessionmaker() as db:
            user = await make_user(db)
            await tokens.issue_token(db, user_id=user.id, purpose="invite", clock=fake_clock)
            await db.commit()
            await after_commit_idle(db)

        payloads = queued_payloads(client, queue)
        assert len(payloads) == 1
        assert set(payloads[0]) == {"schema_version", "token_ids"}
        raw = repr(payloads[0])
        assert user.email not in raw
        assert "#token=" not in raw
    finally:
        client.close()


async def test_issue_token_rollback_leaves_broker_empty(
    db_session: AsyncSession, fake_clock: FakeClock, messaging_env: None
) -> None:
    """Giao dịch gọi `issue_token` rồi rollback → không có thông điệp trên broker (J09)."""
    queue = queue_for(SEND_TOKEN_MAIL_TASK)
    client = broker_redis_sync()
    try:
        client.delete(queue)
        user = await make_user(db_session)
        await tokens.issue_token(db_session, user_id=user.id, purpose="invite", clock=fake_clock)
        await db_session.rollback()
        await after_commit_idle(db_session)

        assert queued_payloads(client, queue) == []
    finally:
        client.close()


# --- ranh giới nhập -------------------------------------------------------------------------------


def test_jobs_import_without_web_or_crypto_packages() -> None:
    """Worker nhập `apps.api.auth_recovery.jobs` để chạy task/beat: nhập được khi ba gói web/crypto bị chặn."""
    blocked = "; ".join(f"sys.modules[{name!r}] = None" for name in WORKER_BLOCKED)
    result = subprocess.run(  # noqa: S603 — trình thông dịch của chính tiến trình test, mã cố định
        [sys.executable, "-c", f"import sys; {blocked}; import apps.api.auth_recovery.jobs"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
