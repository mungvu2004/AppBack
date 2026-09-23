"""Gửi thư token một lần, gửi lại thư chưa gửi, dọn token cũ (B1-03 [6], BE-00 §7).

`apps/worker` nhập module này để chạy task/beat: **không** nhập `fastapi`, `jwt`,
`argon2`, cũng không nhập module nào của `apps.api.auth` kéo theo chúng (khối [8]).

Payload chỉ mang `token_id` (K11): `send_token_mail` tự tra token trong DB rồi tính lại
token bản rõ bằng khoá đang có hiệu lực (`verification_keys`), không bao giờ đưa token
lên hàng đợi. Gửi ít nhất một lần: token đã có `sent_at` bị bỏ qua ngay ở câu truy vấn
(J06), nên thử lại giữa chừng một lô không gửi trùng những token đã xong.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Final, cast

from sqlalchemy import CursorResult, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.auth_recovery.messages import build_token_mail
from apps.api.auth_recovery.settings import get_recovery_settings
from apps.api.auth_recovery.tokens import SEND_TOKEN_MAIL_TASK, active_clause, derive_token, hash_token
from packages.core.clock import Clock, SystemClock
from packages.core.keys import verification_keys
from packages.db.engine import worker_sessionmaker
from packages.db.models.auth import User
from packages.db.models.auth_recovery import OneTimeToken, TokenPurpose
from packages.mail.sender import MailRejectedError, MailTransientError, create_mailer
from packages.mail.settings import get_mail_settings
from packages.messaging import periodic
from packages.messaging.celery_app import send_task
from packages.messaging.payloads.auth_recovery import MAX_TOKEN_IDS, SendTokenMailPayload
from packages.messaging.tasks import PermanentError, TransientError, define_task

_log: Final = logging.getLogger(__name__)

RESEND_UNSENT_TASK: Final = "default.auth_recovery.resend_unsent"
PURGE_TOKENS_TASK: Final = "default.auth_recovery.purge_tokens"
RESEND_EVERY: Final = timedelta(minutes=5)
PURGE_EVERY: Final = timedelta(hours=24)

RESEND_SELECT_LIMIT: Final = 500
"""Trần một lượt quét `resend_unsent`; lượt sau (5 phút) quét tiếp phần còn lại."""
PURGE_BATCH: Final = 1000
PURGE_MAX_BATCHES: Final = 100
"""Trần vòng lặp xoá, cùng khuôn `apps/api/auth/jobs.py::run_purge_sessions` (R-21)."""

TOKEN_KEY_ROTATED: Final = "TOKEN_KEY_ROTATED"  # noqa: S105 — mã lỗi, không phải bí mật
MAIL_REJECTED: Final = "MAIL_REJECTED"


def _resolve_plain_token(row: Any, keys: tuple[bytes, ...]) -> str | None:
    """Tính lại token bản rõ khớp `token_hash` bằng lần lượt các khoá còn xác thực được.

    Hàm đồng bộ thuần: nhận dữ liệu dòng đã đọc, không tự truy vấn — dò được đủ nhánh dù
    coverage bỏ sót dòng ngay sau `await` của SQLAlchemy async (NO-130).
    """
    purpose = cast("TokenPurpose", row.purpose)
    for key in keys:
        candidate = derive_token(key, token_id=row.id, purpose=purpose, nonce=row.nonce)
        if hash_token(candidate) == row.token_hash:
            return candidate
    return None


def _on_send_token_mail_failed(payload: SendTokenMailPayload, code: str) -> None:
    """Ghi log hỏng cho lô: chỉ `token_ids` và mã, không email/token/link (K11)."""
    _log.error("token_mail_failed", extra={"token_ids": payload.token_ids, "code": code})


async def _mark_permanent_failure(
    sessionmaker: async_sessionmaker[AsyncSession], *, token_id: str, now: datetime, code: str
) -> None:
    """Cô lập **riêng** token hỏng vĩnh viễn khỏi tập quét bù của `run_resend_unsent` (prompt [6]:
    lỗi vĩnh viễn là cho token đó, không phải cho cả lô — NO-143).

    Không đổi schema: `TOKEN_KEY_ROTATED` (không khoá nào còn xác thực được) → `superseded_at`,
    vì token này không bao giờ dựng lại được nữa, đúng nghĩa "đã bị thay". `MAIL_REJECTED` (SMTP
    550 vĩnh viễn) → `sent_at`, vì đã thực sự thử giao và bị từ chối hẳn — `resend_unsent` chỉ
    nhặt `sent_at IS NULL` nên token này rời tập quét bù mà không giả vờ đã gửi thành công theo
    nghĩa mail thật sự tới (không có cột nào khác để phân biệt, và giá trị `sent_at` không bao giờ
    được đọc lại để suy "đã gửi thành công", chỉ để lọc quét bù).
    """
    async with sessionmaker() as db:
        column = OneTimeToken.superseded_at if code == TOKEN_KEY_ROTATED else OneTimeToken.sent_at
        await db.execute(update(OneTimeToken).where(OneTimeToken.id == token_id).values({column: now}))
        await db.commit()


async def _mark_sent(sessionmaker: async_sessionmaker[AsyncSession], *, token_id: str, now: datetime) -> None:
    """Đánh dấu một token đã gửi xong bằng một phiên riêng, ngắn (K36 phỏng theo)."""
    async with sessionmaker() as db:
        await db.execute(
            update(OneTimeToken).where(OneTimeToken.id == token_id, OneTimeToken.sent_at.is_(None)).values(sent_at=now)
        )
        await db.commit()


async def _send_one(
    sessionmaker: async_sessionmaker[AsyncSession], mailer: Any, row: Any, *, keys: tuple[bytes, ...], now: datetime
) -> str | None:
    """Gửi một token; trả mã lỗi vĩnh viễn (đã cô lập token đó), hay `None` khi gửi xong.

    `MailTransientError` ném thẳng `TransientError` — không cô lập, thử lại **cả lô** an toàn vì
    token đã gửi ở lượt trước đã có `sent_at` (J06 idempotent theo đó).
    """
    plain = _resolve_plain_token(row, keys)
    if plain is None:
        await _mark_permanent_failure(sessionmaker, token_id=row.id, now=now, code=TOKEN_KEY_ROTATED)
        return TOKEN_KEY_ROTATED
    message = build_token_mail(
        purpose=cast("TokenPurpose", row.purpose), to=row.email, name=row.name, token=plain, expires_at=row.expires_at
    )
    try:
        mailer.send(message)
    except MailTransientError as exc:
        raise TransientError from exc
    except MailRejectedError:
        await _mark_permanent_failure(sessionmaker, token_id=row.id, now=now, code=MAIL_REJECTED)
        return MAIL_REJECTED
    await _mark_sent(sessionmaker, token_id=row.id, now=now)
    return None


async def run_send_token_mail(
    sessionmaker: async_sessionmaker[AsyncSession], clock: Clock, token_ids: list[str]
) -> int:
    """Gửi thư cho từng token của lô còn phải gửi; trả số thư đã gửi thành công.

    Một truy vấn đọc hết token của lô (kèm email/tên người nhận qua join, không N+1). Lỗi vĩnh
    viễn của **một** token (`_send_one`) không dừng cả lô: token đó bị cô lập rồi vòng đi tiếp;
    hết vòng mới ném **một** `PermanentError` gom mã đầu tiên gặp, để `on_failed` log đúng
    `token_ids` của lô + mã (K11) mà không làm mất các token khác đã gửi được (NO-143).
    """
    keys = verification_keys("token")
    now = clock.now()
    async with sessionmaker() as db:
        stmt = (
            select(
                OneTimeToken.id,
                OneTimeToken.purpose,
                OneTimeToken.token_hash,
                OneTimeToken.nonce,
                OneTimeToken.expires_at,
                User.email,
                User.name,
            )
            .join(User, User.id == OneTimeToken.user_id)
            .where(OneTimeToken.id.in_(token_ids), OneTimeToken.sent_at.is_(None), active_clause(now))
        )
        rows = (await db.execute(stmt)).all()
    mailer = create_mailer(get_mail_settings())
    sent = 0
    first_failure: str | None = None
    for row in rows:
        code = await _send_one(sessionmaker, mailer, row, keys=keys, now=now)
        if code is None:
            sent += 1
        elif first_failure is None:
            first_failure = code
    if first_failure is not None:
        raise PermanentError(first_failure)
    return sent


@define_task(name=SEND_TOKEN_MAIL_TASK, payload=SendTokenMailPayload, on_failed=_on_send_token_mail_failed)
async def send_token_mail(payload: SendTokenMailPayload) -> None:
    """Hàm task mỏng: chỉ dựng tài nguyên thật rồi gọi lõi (mẫu `apps/api/auth/jobs.py`)."""
    await run_send_token_mail(worker_sessionmaker(), SystemClock(), payload.token_ids)


async def run_resend_unsent(sessionmaker: async_sessionmaker[AsyncSession], clock: Clock) -> int:
    """Quét token còn hiệu lực, chưa gửi, tạo quá `resend_unsent_after_s` → gửi lại theo lô; trả số id đã xếp lại."""
    cutoff = clock.now() - timedelta(seconds=get_recovery_settings().resend_unsent_after_s)
    async with sessionmaker() as db:
        stmt = (
            select(OneTimeToken.id)
            .where(OneTimeToken.sent_at.is_(None), OneTimeToken.created_at < cutoff, active_clause(clock.now()))
            .order_by(OneTimeToken.created_at)
            .limit(RESEND_SELECT_LIMIT)
        )
        ids = list((await db.execute(stmt)).scalars().all())
    for start in range(0, len(ids), MAX_TOKEN_IDS):
        send_task(SEND_TOKEN_MAIL_TASK, SendTokenMailPayload(token_ids=ids[start : start + MAX_TOKEN_IDS]))
    return len(ids)


@periodic(RESEND_UNSENT_TASK, every=RESEND_EVERY)
async def resend_unsent() -> None:
    """Hàm lịch mỏng: dựng tài nguyên thật rồi gọi lõi."""
    await run_resend_unsent(worker_sessionmaker(), SystemClock())


async def run_purge_tokens(
    sessionmaker: async_sessionmaker[AsyncSession], clock: Clock, *, batch: int = PURGE_BATCH
) -> int:
    """Xoá token hết hạn/đã dùng/bị thay quá `token_purge_after_d`; trả số dòng đã xoá (khuôn `purge_sessions`)."""
    cutoff = clock.now() - timedelta(days=get_recovery_settings().token_purge_after_d)
    dead = or_(OneTimeToken.expires_at < cutoff, OneTimeToken.used_at < cutoff, OneTimeToken.superseded_at < cutoff)
    removed = 0
    async with sessionmaker() as db:
        for _ in range(PURGE_MAX_BATCHES):
            doomed = select(OneTimeToken.id).where(dead).limit(batch)
            result = cast(
                "CursorResult[Any]", await db.execute(delete(OneTimeToken).where(OneTimeToken.id.in_(doomed)))
            )
            await db.commit()
            removed += result.rowcount
            if result.rowcount < batch:
                break
    _log.info("auth_recovery_tokens_purged", extra={"removed": removed})
    return removed


@periodic(PURGE_TOKENS_TASK, every=PURGE_EVERY)
async def purge_tokens() -> None:
    """Hàm lịch mỏng: dựng tài nguyên thật rồi gọi lõi."""
    await run_purge_tokens(worker_sessionmaker(), SystemClock())
