"""Token một lần: sinh, tra, dùng, thu hồi (B1-03 [6], BE-00 §5, §7).

**Không** nhập `fastapi`, `jwt`, `argon2`, cũng không nhập module nào của
`apps.api.auth` kéo theo chúng: task gửi thư (`apps/api/auth_recovery/jobs.py`, worker J)
nhập file này trong tiến trình worker, nơi ba gói đó không có (ranh giới ở [8]).

Bản rõ của token chỉ sống bên trong `issue_token`, không bao giờ được trả ra hay ghi log
(K11) — DB và mọi hàm công khai khác chỉ thấy `token_hash`.
"""

import base64
import hashlib
import hmac
import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from sqlalchemy import ColumnElement, and_, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth_recovery.settings import get_recovery_settings
from packages.core.clock import Clock
from packages.core.ids import new_id
from packages.core.keys import current_key
from packages.db.hooks import on_after_commit
from packages.db.models.auth_recovery import NONCE_LEN, OneTimeToken, TokenPurpose
from packages.messaging.celery_app import send_task
from packages.messaging.payloads.auth_recovery import MAX_TOKEN_IDS, SendTokenMailPayload

SEND_TOKEN_MAIL_TASK: Final = "default.auth_recovery.send_token_mail"  # noqa: S105 — tên task, không phải bí mật
_PENDING_KEY: Final = "appback_auth_recovery_pending_tokens"


@dataclass(frozen=True, slots=True)
class InvitationWindow:
    """Cửa sổ của lời mời mới nhất: lúc mời và lúc hết hạn (màn hiện "hết hạn" và nút gửi lại)."""

    invited_at: datetime
    expires_at: datetime


def derive_token(key: bytes, *, token_id: str, purpose: TokenPurpose, nonce: bytes) -> str:
    """Token 43 ký tự, tất định theo `(key, token_id, purpose, nonce)` — không lưu bản rõ."""
    mac = hmac.new(key, f"{token_id}|{purpose}|".encode() + nonce, hashlib.sha256).digest()
    return _b64url(mac)


def _b64url(data: bytes) -> str:
    """Base64 URL-safe không đệm `=` — dạng token đưa ra ngoài (link, thư)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def hash_token(token: str) -> str:
    """`sha256(token)` hex — cái duy nhất DB lưu, để tra token theo bản rõ người dùng gửi lên."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def active_clause(now: datetime) -> ColumnElement[bool]:
    """Điều kiện "còn hiệu lực": chưa dùng, chưa bị thay, chưa hết hạn — R và J dùng lại."""
    return and_(OneTimeToken.used_at.is_(None), OneTimeToken.superseded_at.is_(None), OneTimeToken.expires_at > now)


def _ttl_for(purpose: TokenPurpose) -> timedelta:
    """TTL theo mục đích: `invite_ttl_h` cho lời mời, `password_reset_ttl_min` cho quên mật khẩu (prompt [5])."""
    settings = get_recovery_settings()
    if purpose == "invite":
        return timedelta(hours=settings.invite_ttl_h)
    return timedelta(minutes=settings.password_reset_ttl_min)


def _new_token_row(*, user_id: str, purpose: TokenPurpose, clock: Clock, now: datetime) -> OneTimeToken:
    """Dựng một dòng token mới; token bản rõ chỉ sống trong khung hàm này (K11)."""
    token_id = new_id("tok", clock)
    nonce = secrets.token_bytes(NONCE_LEN)
    token = derive_token(current_key("token"), token_id=token_id, purpose=purpose, nonce=nonce)
    return OneTimeToken(
        id=token_id,
        user_id=user_id,
        purpose=purpose,
        token_hash=hash_token(token),
        nonce=nonce,
        expires_at=now + _ttl_for(purpose),
    )


_ACTIVE_WHERE: Final = text("used_at IS NULL AND superseded_at IS NULL")


async def issue_token(db: AsyncSession, *, user_id: str, purpose: TokenPurpose, clock: Clock) -> OneTimeToken:
    """Vô hiệu token còn hiệu lực cùng `(user_id, purpose)` rồi tạo token mới, trong giao dịch gọi.

    Hai lượt song song cùng người cùng mục đích có thể cùng thấy "chưa có token còn hiệu
    lực" và cùng chèn: chèn bằng `INSERT ... ON CONFLICT (user_id, purpose) WHERE <còn hiệu
    lực> DO NOTHING` nhắm đúng `ACTIVE_UNIQUE`, bên thua không ném lỗi mà chỉ 0 dòng, làm
    lại **một** lần (lần này sẽ thấy token của bên thắng và vô hiệu nó trước khi chèn). Không
    dùng savepoint (`begin_nested`): trên bản SQLAlchemy/asyncpg của repo, một `INSERT` bên
    trong savepoint tự bắn `after_commit` thật của toàn phiên khi savepoint đóng (xem "Nợ" của
    báo cáo B1-03) — `ON CONFLICT DO NOTHING` đạt cùng bất biến mà không cần savepoint.
    Gom `token_id` gửi thư sau commit, không gửi ngay (K17).
    """
    now = clock.now()
    token_row = await _try_insert(db, user_id=user_id, purpose=purpose, clock=clock, now=now)
    if token_row is None:
        token_row = await _try_insert(db, user_id=user_id, purpose=purpose, clock=clock, now=now)
    if token_row is None:
        raise RuntimeError("issue_token: xung đột ACTIVE_UNIQUE hai lần liên tiếp")
    _queue_send(db, token_row.id)
    return token_row


async def _try_insert(
    db: AsyncSession, *, user_id: str, purpose: TokenPurpose, clock: Clock, now: datetime
) -> OneTimeToken | None:
    """Vô hiệu token cũ (idempotent) rồi thử chèn; `None` nếu thua cuộc đua `ACTIVE_UNIQUE`."""
    await db.execute(
        update(OneTimeToken)
        .where(OneTimeToken.user_id == user_id, OneTimeToken.purpose == purpose, active_clause(now))
        .values(superseded_at=now)
    )
    candidate = _new_token_row(user_id=user_id, purpose=purpose, clock=clock, now=now)
    stmt = (
        pg_insert(OneTimeToken)
        .values(
            id=candidate.id,
            user_id=candidate.user_id,
            purpose=candidate.purpose,
            token_hash=candidate.token_hash,
            nonce=candidate.nonce,
            expires_at=candidate.expires_at,
        )
        .on_conflict_do_nothing(index_elements=["user_id", "purpose"], index_where=_ACTIVE_WHERE)
        .returning(OneTimeToken)
    )
    # `returning(OneTimeToken)`: INSERT kiểu ORM, trả về đối tượng đã gắn vào session (dùng
    # `db.refresh()` được sau) thay vì chỉ giá trị cột thô; `None` khi `ON CONFLICT` bỏ dòng.
    return (await db.execute(stmt)).scalars().first()


def _queue_send(db: AsyncSession, token_id: str) -> None:
    """Gom `token_id` vào lô của giao dịch hiện tại; đăng ký đúng một callback mỗi giao dịch.

    Khoá lô theo transaction (`get_transaction()`) để nhiều lệnh trong cùng một giao dịch
    gộp thành một `send_task`; và để giao dịch kế tiếp trên cùng session — kể cả trước khi
    callback này chạy — không lẫn danh sách với giao dịch trước (K11).
    """
    sync = db.sync_session
    txn = sync.get_transaction()
    batches: dict[object, list[str]] = db.info.setdefault(_PENDING_KEY, {})
    pending = batches.get(txn)
    if pending is None:
        pending = []
        batches[txn] = pending
        on_after_commit(db, lambda: _dispatch_batches(batches.pop(txn, pending)))
    pending.append(token_id)


def _dispatch_batches(token_ids: list[str]) -> None:
    """Gửi `send_task` theo lô ≤ `MAX_TOKEN_IDS`; hàm đồng bộ (`on_after_commit` đòi vậy)."""
    for start in range(0, len(token_ids), MAX_TOKEN_IDS):
        chunk = token_ids[start : start + MAX_TOKEN_IDS]
        send_task(SEND_TOKEN_MAIL_TASK, SendTokenMailPayload(token_ids=chunk))


async def latest_invitations(db: AsyncSession, user_ids: Sequence[str]) -> dict[str, InvitationWindow]:
    """Lời mời mới nhất chưa dùng/chưa bị thay của mỗi người, **kể cả đã hết hạn**; một truy vấn."""
    if not user_ids:
        return {}
    stmt = (
        select(OneTimeToken.user_id, OneTimeToken.created_at, OneTimeToken.expires_at)
        .distinct(OneTimeToken.user_id)
        .where(
            OneTimeToken.user_id.in_(user_ids),
            OneTimeToken.purpose == "invite",
            OneTimeToken.used_at.is_(None),
            OneTimeToken.superseded_at.is_(None),
        )
        .order_by(OneTimeToken.user_id, OneTimeToken.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    return {row.user_id: InvitationWindow(invited_at=row.created_at, expires_at=row.expires_at) for row in rows}


async def revoke_tokens(db: AsyncSession, *, user_id: str, clock: Clock, purpose: TokenPurpose | None = None) -> None:
    """Vô hiệu mọi token còn hiệu lực của người này (một mục đích, hoặc tất cả khi `None`)."""
    now = clock.now()
    conditions = [OneTimeToken.user_id == user_id, active_clause(now)]
    if purpose is not None:
        conditions.append(OneTimeToken.purpose == purpose)
    await db.execute(update(OneTimeToken).where(*conditions).values(superseded_at=now))


async def find_active_token(
    db: AsyncSession, *, token: str, purpose: TokenPurpose, now: datetime
) -> OneTimeToken | None:
    """Token còn hiệu lực khớp bản rõ `token` và `purpose`, hay `None` — không phân biệt lý do sai."""
    stmt = select(OneTimeToken).where(
        OneTimeToken.token_hash == hash_token(token), OneTimeToken.purpose == purpose, active_clause(now)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def consume_token(db: AsyncSession, *, token_id: str, now: datetime) -> bool:
    """Đánh dấu đã dùng nếu còn hiệu lực; `False` (0 dòng) khi hai request đua nhau, một bên thua."""
    stmt = (
        update(OneTimeToken)
        .where(OneTimeToken.id == token_id, active_clause(now))
        .values(used_at=now)
        .returning(OneTimeToken.id)
    )
    result = await db.execute(stmt)
    return result.first() is not None
